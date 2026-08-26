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
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"Error initializing sentence-transformers: {e}")
            raise

    def encode(self, text: str) -> List[float]:
        if not text:
            raise ValueError("Input text is empty")
        try:
            return self._model.encode(text, convert_to_numpy=True).tolist()
        except Exception as e:
            print(f"Error encoding text: {e}")
            raise


class _TFIDFBackend(_EmbedBackend):
    """
    Pure-Python trigram TF-IDF vectors — no dependencies.
    Dim = 512 via hashing trick. Good enough for top-5 recall.
    """
    DIM = 512

    def encode(self, text: str) -> List[float]:
        if not text:
            raise ValueError("Input text is empty")
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
    except Exception as e:
        print(f"Error building sentence-transformers backend: {e}")
        b = _TFIDFBackend()
        return b, "tfidf-trigram-512"


# ───────────────────────────────────────────────────────────────────────