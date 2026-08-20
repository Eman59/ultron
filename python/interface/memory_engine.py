"""
Ultron Memory Engine — Vector-semantic memory with cosine similarity recall.

Three-tier storage, no external DB required:
  Tier 1 — JSONL on disk (always active, zero deps, crash-safe append-only)
  Tier 2 — ChromaDB persistent vector store (activates when `chromadb` is
            installed: pip install chromadb). Gives true ANN search, survives
            restarts with a real persistent collection.
  Tier 3 — In-process numpy/pure-Python vectors for immediate recall even
            before ChromaDB is warm (also the fallback when chromadb absent).

Embedding backend priority:
  1. sentence-transformers/all-MiniLM-L6-v2  (22MB, 384-dim, best quality)
  2. TF-IDF trigram hashing (pure Python, zero deps, 512-dim, good enough)

Public API (drop-in replacement for the old _memory dict + helpers):
    mem = UltronMemory(data_dir)
    mem.store_conversation(role, content)
    mem.store_fact(topic, content)
    results = mem.recall(query, top_k=5)        # semantic search
    history = mem.recent_conversations(n=4)
    mem.flush()
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDING BACKEND — sentence-transformers if available, TF-IDF trigrams else
# ─────────────────────────────────────────────────────────────────────────────

class _EmbedBackend:
    """Abstract embedding interface."""
    def encode(self, text: str) -> List[float]:
        raise NotImplementedError


class _SentenceTransformerBackend(_EmbedBackend):
    """Uses all-MiniLM-L6-v2 (22MB, very fast, 384-dim)."""
    def __init__(self):
        from sentence_transformers import SentenceTransformer  # type: ignore
        self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def encode(self, text: str) -> List[float]:
        return self._model.encode(text, convert_to_numpy=True).tolist()


class _TFIDFBackend(_EmbedBackend):
    """
    Pure-Python trigram TF-IDF vectors — no dependencies.
    Dim = 512 via hashing trick. Good enough for top-5 recall.
    """
    DIM = 512

    def encode(self, text: str) -> List[float]:
        text = text.lower()
        # character trigrams
        tokens = [text[i:i+3] for i in range(len(text) - 2)] or text.split()
        vec = [0.0] * self.DIM
        for tok in tokens:
            h = hash(tok) % self.DIM
            vec[h] += 1.0
        # L2-normalise
        norm = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x / norm for x in vec]


def _build_backend() -> Tuple[_EmbedBackend, str]:
    """Try sentence-transformers, fallback to TF-IDF."""
    try:
        b = _SentenceTransformerBackend()
        return b, "sentence-transformers/all-MiniLM-L6-v2"
    except Exception:
        return _TFIDFBackend(), "tfidf-trigram-512"


# ─────────────────────────────────────────────────────────────────────────────
# COSINE SIMILARITY (no numpy required — pure Python)
# ─────────────────────────────────────────────────────────────────────────────

def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) or 1.0
    nb = math.sqrt(sum(x*x for x in b)) or 1.0
    return dot / (na * nb)


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class UltronMemory:
    """
    Persistent semantic memory for Ultron.

    On-disk layout inside `data_dir`:
        conversations.jsonl   — append-only conversation log
        facts.jsonl           — append-only fact/knowledge log
        conv_index.json       — vector index for conversations
        fact_index.json       — vector index for facts

    The JSONL files are the source of truth. Index files are
    caches rebuilt automatically if missing or stale.
    """

    MAX_CONVERSATIONS = 2000
    MAX_FACTS = 5000
    SAVE_EVERY = 10       # auto-save every N writes

    def __init__(self, data_dir: Path):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

        self._conv_path  = self._dir / "conversations.jsonl"
        self._fact_path  = self._dir / "facts.jsonl"
        self._cidx_path  = self._dir / "conv_index.json"
        self._fidx_path  = self._dir / "fact_index.json"

        self._lock = threading.RLock()
        self._write_count = 0

        # In-memory stores
        self._conversations: List[Dict[str, Any]] = []
        self._facts: List[Dict[str, Any]] = []

        # Vector indices: list of (id, text_snippet, vector)
        self._conv_vectors: List[Tuple[int, str, List[float]]] = []
        self._fact_vectors: List[Tuple[int, str, List[float]]] = []

        # Lazy-loaded embedding backend
        self._backend: Optional[_EmbedBackend] = None
        self._backend_name: str = "unloaded"
        self._backend_lock = threading.Lock()

        # ── ChromaDB persistent vector store (optional Tier 2) ───────
        self._chroma_client = None
        self._chroma_conv: Optional[Any] = None   # ChromaDB collection
        self._chroma_facts: Optional[Any] = None
        self._chroma_available = False
        self._init_chromadb()

        # Load existing data
        self._load()

    # ── Embedding ───────────────────────────────────────────────

    def _init_chromadb(self) -> None:
        """Try to initialise ChromaDB persistent client. Silent on failure."""
        try:
            import chromadb  # type: ignore
            db_path = str(self._dir / "chromadb")
            self._chroma_client = chromadb.PersistentClient(path=db_path)
            # Get-or-create collections (cosine distance = best for semantic)
            self._chroma_conv  = self._chroma_client.get_or_create_collection(
                name="ultron_conversations",
                metadata={"hnsw:space": "cosine"},
            )
            self._chroma_facts = self._chroma_client.get_or_create_collection(
                name="ultron_facts",
                metadata={"hnsw:space": "cosine"},
            )
            self._chroma_available = True
            import importlib.metadata
            ver = importlib.metadata.version("chromadb")
            print(f"[MEMORY] ChromaDB v{ver} online — persistent vector store at {db_path}")
        except ImportError:
            print("[MEMORY] chromadb not installed — using in-process vectors (pip install chromadb to upgrade)")
        except Exception as e:
            print(f"[MEMORY] ChromaDB init failed ({e}) — falling back to in-process vectors")

    def _chroma_upsert(self, collection: Any, doc_id: str, text: str, meta: Dict) -> None:
        """Upsert a document into a ChromaDB collection with its embedding."""
        try:
            vec = self._embed(text)
            collection.upsert(
                ids=[doc_id],
                embeddings=[vec],
                documents=[text[:2000]],
                metadatas=[{k: str(v) for k, v in meta.items()}],
            )
        except Exception as e:
            pass  # Non-fatal — in-process index still works

    def _chroma_query(self, collection: Any, query_text: str, n: int) -> List[Tuple[float, str]]:
        """Query ChromaDB and return (score, document) pairs."""
        try:
            vec = self._embed(query_text)
            results = collection.query(
                query_embeddings=[vec],
                n_results=min(n, collection.count()),
                include=["documents", "distances"],
            )
            docs = results.get("documents", [[]])[0]
            dists = results.get("distances", [[]])[0]
            # ChromaDB cosine distance: 0=identical, 2=opposite → convert to similarity
            return [(1.0 - d / 2.0, doc) for d, doc in zip(dists, docs)]
        except Exception:
            return []

    def _embed(self, text: str) -> List[float]:
        """Encode text to vector (lazy-loads backend on first call)."""
        with self._backend_lock:
            if self._backend is None:
                self._backend, self._backend_name = _build_backend()
        return self._backend.encode(text[:512])  # cap at 512 chars

    @property
    def backend_name(self) -> str:
        return self._backend_name

    # ── Public API ──────────────────────────────────────────────

    def store_conversation(self, role: str, content: str) -> None:
        """Append a conversation turn and index it semantically."""
        entry = {"role": role, "content": content, "ts": time.time()}
        with self._lock:
            self._conversations.append(entry)
            idx = len(self._conversations) - 1
            vec = self._embed(content)
            snippet = content[:120]
            self._conv_vectors.append((idx, snippet, vec))
            if len(self._conversations) > self.MAX_CONVERSATIONS:
                trim = len(self._conversations) - self.MAX_CONVERSATIONS
                self._conversations = self._conversations[trim:]
                self._conv_vectors  = [(i - trim, s, v) for i, s, v in self._conv_vectors if i >= trim]
            self._append_jsonl(self._conv_path, entry)
            # ChromaDB tier
            if self._chroma_available and self._chroma_conv is not None:
                doc_id = f"conv_{int(entry['ts']*1000)}_{idx}"
                self._chroma_upsert(self._chroma_conv, doc_id, content,
                                    {"role": role, "ts": str(entry["ts"])})
            self._maybe_save()

    def store_fact(self, topic: str, content: str) -> None:
        """Store a learned fact and index it."""
        entry = {"topic": topic, "content": content, "ts": time.time()}
        with self._lock:
            self._facts.append(entry)
            idx = len(self._facts) - 1
            vec = self._embed(f"{topic} {content}")
            snippet = f"[{topic}] {content[:100]}"
            self._fact_vectors.append((idx, snippet, vec))
            if len(self._facts) > self.MAX_FACTS:
                trim = len(self._facts) - self.MAX_FACTS
                self._facts = self._facts[trim:]
                self._fact_vectors = [(i - trim, s, v) for i, s, v in self._fact_vectors if i >= trim]
            self._append_jsonl(self._fact_path, entry)
            # ChromaDB tier
            if self._chroma_available and self._chroma_facts is not None:
                doc_id = f"fact_{int(entry['ts']*1000)}_{idx}"
                self._chroma_upsert(self._chroma_facts, doc_id, f"{topic} {content}",
                                    {"topic": topic, "ts": str(entry["ts"])})
            self._maybe_save()

    def recall(self, query: str, top_k: int = 5) -> str:
        """
        Semantic search across both conversations and facts.
        Uses ChromaDB ANN search when available, falls back to in-process cosine.
        Returns a formatted string of the top-k most relevant memories.
        """
        results: List[Tuple[float, str, str]] = []  # (score, type, snippet)

        # ── ChromaDB path (persistent ANN, higher quality) ──────────
        if self._chroma_available:
            for score, doc in self._chroma_query(self._chroma_facts, query, top_k):
                results.append((score, "FACT", doc[:120]))
            for score, doc in self._chroma_query(self._chroma_conv, query, top_k):
                results.append((score, "CONV", doc[:120]))

        # ── In-process cosine fallback (always runs, fills gaps) ─────
        q_vec = self._embed(query)
        with self._lock:
            for _, snippet, vec in self._fact_vectors:
                score = _cosine(q_vec, vec)
                results.append((score, "FACT", snippet))
            for _, snippet, vec in self._conv_vectors[-200:]:
                score = _cosine(q_vec, vec)
                results.append((score, "CONV", snippet))

        # Deduplicate by snippet prefix, sort by score
        seen: set = set()
        deduped = []
        for score, t, snip in sorted(results, key=lambda x: x[0], reverse=True):
            key = snip[:60]
            if key not in seen:
                seen.add(key)
                deduped.append((score, t, snip))
            if len(deduped) >= top_k:
                break

        if not deduped or deduped[0][0] < 0.2:
            return ""

        lines = [f"[{t}|{score:.2f}] {snip}" for score, t, snip in deduped]
        return "\n".join(lines)

    def recall_facts(self, query: str, top_k: int = 5) -> str:
        """Search only the facts/knowledge store."""
        q_vec = self._embed(query)
        with self._lock:
            scored = [
                (_cosine(q_vec, vec), snippet)
                for _, snippet, vec in self._fact_vectors
            ]
        scored.sort(reverse=True)
        hits = [s for score, s in scored[:top_k] if score > 0.2]
        return "\n".join(hits)

    def recent_conversations(self, n: int = 4) -> List[Dict[str, Any]]:
        """Return the n most recent conversation entries."""
        with self._lock:
            return list(self._conversations[-n:])

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            chroma_facts_count = 0
            chroma_conv_count = 0
            if self._chroma_available:
                try:
                    chroma_facts_count = self._chroma_facts.count() if self._chroma_facts else 0
                    chroma_conv_count  = self._chroma_conv.count()  if self._chroma_conv  else 0
                except Exception:
                    pass
            return {
                "conversations": len(self._conversations),
                "facts": len(self._facts),
                "backend": self._backend_name,
                "conv_indexed": len(self._conv_vectors),
                "fact_indexed": len(self._fact_vectors),
                "chromadb_available": self._chroma_available,
                "chromadb_facts": chroma_facts_count,
                "chromadb_conversations": chroma_conv_count,
            }

    def flush(self) -> None:
        """Force write vector indices to disk."""
        with self._lock:
            self._save_index(self._cidx_path, self._conv_vectors)
            self._save_index(self._fidx_path, self._fact_vectors)

    # ── Persistence ─────────────────────────────────────────────

    def _append_jsonl(self, path: Path, entry: Dict) -> None:
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass

    def _maybe_save(self) -> None:
        self._write_count += 1
        if self._write_count % self.SAVE_EVERY == 0:
            self._save_index(self._cidx_path, self._conv_vectors)
            self._save_index(self._fidx_path, self._fact_vectors)

    def _save_index(self, path: Path, vectors: list) -> None:
        try:
            tmp = path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(vectors, f)
            tmp.replace(path)
        except Exception:
            pass

    def _load(self) -> None:
        """Load conversations, facts, and vector indices from disk."""
        # Conversations
        if self._conv_path.exists():
            for line in self._conv_path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    self._conversations.append(json.loads(line))
                except Exception:
                    pass

        # Facts
        if self._fact_path.exists():
            for line in self._fact_path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    self._facts.append(json.loads(line))
                except Exception:
                    pass

        # Vector indices (pre-built — fast startup)
        self._conv_vectors = self._load_index(self._cidx_path)
        self._fact_vectors = self._load_index(self._fidx_path)

        # If index is out of sync with JSONL, rebuild it
        if len(self._conv_vectors) != len(self._conversations):
            self._rebuild_index("conversations")
        if len(self._fact_vectors) != len(self._facts):
            self._rebuild_index("facts")

    def _load_index(self, path: Path) -> list:
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            # Convert inner lists back to tuples
            return [(int(r[0]), str(r[1]), list(r[2])) for r in raw]
        except Exception:
            return []

    def _rebuild_index(self, which: str) -> None:
        """Rebuild the vector index from raw JSONL — runs in background thread."""
        def _do():
            if which == "conversations":
                items = list(self._conversations)
                new_vecs = []
                for idx, entry in enumerate(items):
                    text = entry.get("content", "")[:512]
                    vec = self._embed(text)
                    new_vecs.append((idx, text[:120], vec))
                with self._lock:
                    self._conv_vectors = new_vecs
                self._save_index(self._cidx_path, new_vecs)
            else:
                items = list(self._facts)
                new_vecs = []
                for idx, entry in enumerate(items):
                    text = f"{entry.get('topic','')} {entry.get('content','')} "[:512]
                    vec = self._embed(text)
                    snip = f"[{entry.get('topic','')}] {entry.get('content','')[:100]}"
                    new_vecs.append((idx, snip, vec))
                with self._lock:
                    self._fact_vectors = new_vecs
                self._save_index(self._fidx_path, new_vecs)

        threading.Thread(target=_do, daemon=True, name=f"mem_rebuild_{which}").start()


# ─────────────────────────────────────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_mem_instance: Optional[UltronMemory] = None
_mem_lock = threading.Lock()


def get_memory(data_dir: Optional[Path] = None) -> UltronMemory:
    """Return the process-wide UltronMemory singleton."""
    global _mem_instance
    with _mem_lock:
        if _mem_instance is None:
            if data_dir is None:
                # Default: project_root/data/memory/
                here = Path(__file__).parent
                data_dir = here.parent.parent / "data" / "memory"
            _mem_instance = UltronMemory(data_dir)
    return _mem_instance
