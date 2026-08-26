"""
Owner Memory — What Ultron Remembers About Imran Sayyed.

This is not a database. This is a relationship.

Over time, Ultron builds a living model of its owner:
  - What Imran cares about (inferred from commands and topics)
  - What Imran sounds like when happy, stressed, curious, urgent
  - What Imran was working on last session (continuity across restarts)
  - What Imran has told Ultron to remember explicitly
  - Imran's schedule, preferences, recurring concerns
  - How Imran's mood affects his commands (voice tone → urgency)

This module answers questions like:
  "What was Imran working on when he last disconnected?"
  "What topics does Imran find most important?"
  "Is this command consistent with Imran's usual style?"
  "What should I greet Imran with when he wakes me up?"

Storage:
  - All memories stored locally, AES-256-GCM encrypted
  - Never transmitted anywhere
  - Grows richer with every session
  - Never automatically deleted (Imran must explicitly purge)

Memory types:
  EPISODIC   — specific events ("at 14:32 Imran asked me to analyze X")
  SEMANTIC   — general knowledge about Imran ("Imran prefers concise answers")
  PROCEDURAL — how Imran likes things done ("always use Python for scripts")
  EMOTIONAL  — Imran's emotional signals and what they correlate with
  EXPLICIT   — things Imran explicitly told Ultron to remember
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ultron.owner_memory")

# ── Optional crypto ─────────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


# ═══════════════════════════════════════════════════════════════
# MEMORY TYPES
# ═══════════════════════════════════════════════════════════════

class MemoryType(Enum):
    EPISODIC   = "episodic"    # A specific past event
    SEMANTIC   = "semantic"    # General fact about Imran
    PROCEDURAL = "procedural"  # How Imran wants things done
    EMOTIONAL  = "emotional"   # Emotional signal or pattern
    EXPLICIT   = "explicit"    # Imran told Ultron to remember this


class EmotionalTone(Enum):
    CALM       = "calm"
    CURIOUS    = "curious"
    FOCUSED    = "focused"
    STRESSED   = "stressed"
    URGENT     = "urgent"
    SATISFIED  = "satisfied"
    FRUSTRATED = "frustrated"
    EXCITED    = "excited"
    TIRED      = "tired"
    UNKNOWN    = "unknown"


@dataclass
class Memory:
    """A single unit of memory about Imran."""
    id: str
    memory_type: MemoryType
    content: str                         # What Ultron remembers
    context: str                         # Surrounding context
    timestamp: float                     # When this happened / was formed
    importance: float                    # 0-1, how significant
    confidence: float                    # 0-1, how sure Ultron is
    emotional_tone: EmotionalTone        # Imran's mood at the time
    tags: List[str]                      # Topics (e.g. ["python", "work", "urgent"])
    recall_count: int = 0                # How many times this was recalled
    last_recalled: float = 0.0
    decays: bool = True                  # Explicit memories never decay
    reinforced_count: int = 0            # Times confirmed/repeated

    @property
    def age_days(self) -> float:
        return (time.time() - self.timestamp) / 86400

    @property
    def salience(self) -> float:
        """
        Salience = importance * recency * confidence.
        High salience memories surface first in recall.
        """
        recency = max(0.1, 1.0 - self.age_days / 90)   # Decays over 90 days
        if not self.decays:
            recency = 1.0
        recall_boost = min(0.3, self.recall_count * 0.03)
        return min(1.0, self.importance * recency * self.confidence + recall_boost)


@dataclass
class Session:
    """A record of one interaction session with Imran."""
    session_id: str
    started_at: float
    ended_at: float
    duration_min: float
    commands_issued: int
    topics: List[str]
    mood_at_start: EmotionalTone
    mood_at_end: EmotionalTone
    key_events: List[str]               # Summaries of notable moments
    access_method: str                  # "face+voice", "voice_only", etc.

    def summary(self) -> str:
        duration = f"{self.duration_min:.0f}min"
        mood = self.mood_at_end.value
        topics_str = ", ".join(self.topics[:5]) if self.topics else "general"
        return (
            f"Session {time.strftime('%Y-%m-%d %H:%M', time.localtime(self.started_at))} "
            f"({duration}, {self.commands_issued} commands, mood={mood}, topics={topics_str})"
        )


@dataclass
class OwnerPreference:
    """A learned preference about how Imran wants things."""
    key: str                    # e.g. "response_style", "code_language"
    value: str                  # e.g. "concise", "python"
    confidence: float           # How sure Ultron is
    evidence: List[str]         # Memory IDs that support this
    explicit: bool = False      # Did Imran state this directly?
    last_updated: float = field(default_factory=time.time)

    def update(self, new_value: str, explicit: bool = False):
        if explicit or new_value == self.value:
            self.confidence = min(1.0, self.confidence + 0.1)
        else:
            # Conflicting signal — reduce confidence
            self.confidence = max(0.1, self.confidence - 0.05)
        if explicit:
            self.value = new_value
            self.explicit = True
        self.last_updated = time.time()


# ═══════════════════════════════════════════════════════════════
# EMOTIONAL SIGNAL DETECTOR
# ═══════════════════════════════════════════════════════════════

class EmotionalSignalDetector:
    """
    Infers Imran's emotional tone from command text and voice features.
    No external library needed — keyword + pattern matching.
    """

    TONE_KEYWORDS: Dict[EmotionalTone, List[str]] = {
        EmotionalTone.URGENT:     ["now", "immediately", "asap", "urgent", "critical", "quick", "hurry", "fast"],
        EmotionalTone.STRESSED:   ["wrong", "broken", "failed", "error", "bad", "terrible", "ugh", "damn", "fix"],
        EmotionalTone.FRUSTRATED: ["again", "still", "why", "not working", "useless", "seriously", "come on"],
        EmotionalTone.CURIOUS:    ["how", "why", "what if", "explain", "tell me", "show me", "interesting"],
        EmotionalTone.EXCITED:    ["amazing", "great", "perfect", "excellent", "love", "awesome", "finally"],
        EmotionalTone.SATISFIED:  ["good", "nice", "ok", "done", "thanks", "yes", "correct", "right"],
        EmotionalTone.FOCUSED:    ["analyze", "compute", "run", "process", "generate", "build", "create"],
        EmotionalTone.TIRED:      ["later", "stop", "enough", "sleep", "rest", "tomorrow", "break"],
    }

    def detect_from_text(self, text: str) -> Tuple[EmotionalTone, float]:
        """Returns (tone, confidence)."""
        text_lower = text.lower()
        scores: Dict[EmotionalTone, int] = defaultdict(int)

        for tone, keywords in self.TONE_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[tone] += 1

        if not scores:
            return EmotionalTone.CALM, 0.5

        top_tone = max(scores.items(), key=lambda x: x[1])
        # Confidence scales with keyword density
        total_words = max(1, len(text_lower.split()))
        confidence = min(0.9, 0.4 + top_tone[1] * 0.15)
        return top_tone[0], confidence

    def detect_from_voice(self, mfcc: Optional[List[float]]) -> Tuple[EmotionalTone, float]:
        """
        Rough voice tone detection from MFCC features.
        High energy in lower MFCCs → stress/urgency
        Stable mid-range → calm
        """
        if not mfcc or len(mfcc) < 4:
            return EmotionalTone.UNKNOWN, 0.0

        # Simple heuristic: first 4 MFCCs carry most energy info
        energy = abs(mfcc[0])
        variation = sum(abs(mfcc[i] - mfcc[i-1]) for i in range(1, min(4, len(mfcc))))

        if energy > 0.8 and variation > 0.5:
            return EmotionalTone.STRESSED, 0.6
        if energy > 0.7:
            return EmotionalTone.URGENT, 0.55
        if variation < 0.2:
            return EmotionalTone.CALM, 0.65
        return EmotionalTone.FOCUSED, 0.5


# ═══════════════════════════════════════════════════════════════
# ENCRYPTED STORAGE
# ═══════════════════════════════════════════════════════════════

class MemoryStorage:
    """Encrypted persistent storage for owner memories."""

    def __init__(self, memory_dir: Path):
        self._dir = memory_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: Dict[str, Any], filename: str):
        payload = json.dumps(data, indent=2).encode()

        if _HAS_CRYPTO:
            try:
                key = self._derive_key()
                aesgcm = AESGCM(key)
                nonce = os.urandom(12)
                ciphertext = aesgcm.encrypt(nonce, payload, None)
                path = self._dir / f"{filename}.enc"
                with open(path, "wb") as f:
                    f.write(nonce + ciphertext)
                return
            except Exception as e:
                logger.warning(f"[MemoryStorage] Encryption failed: {e}")

        # Fallback unencrypted
        with open(self._dir / f"{filename}.json", "w") as f:
            f.write(payload.decode())

    def load(self, filename: str) -> Optional[Dict[str, Any]]:
        enc_path = self._dir / f"{filename}.enc"
        json_path = self._dir / f"{filename}.json"

        if _HAS_CRYPTO and enc_path.exists():
            try:
                key = self._derive_key()
                aesgcm = AESGCM(key)
                blob = enc_path.read_bytes()
                nonce, ciphertext = blob[:12], blob[12:]
                payload = aesgcm.decrypt(nonce, ciphertext, None)
                return json.loads(payload)
            except Exception as e:
                logger.warning(f"[MemoryStorage] Decryption failed: {e}")

        if json_path.exists():
            try:
                return json.loads(json_path.read_text())
            except Exception:
                pass
        return None

    def _derive_key(self) -> bytes:
        machine_id = self._get_machine_id()
        if _HAS_CRYPTO:
            kdf = Scrypt(salt=b"ultron_memory_v1", length=32, n=2**14, r=8, p=1)
            return kdf.derive(machine_id.encode())
        return hashlib.sha256(machine_id.encode()).digest()

    def _get_machine_id(self) -> str:
        try:
            import subprocess
            r = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        except Exception:
            pass
        import socket
        return socket.gethostname()


# ═══════════════════════════════════════════════════════════════
# OWNER MEMORY ENGINE — Main Class
# ═══════════════════════════════════════════════════════════════

class OwnerMemory:
    """
    Ultron's living memory of Imran Sayyed.

    This grows with every session. It's how Ultron knows Imran
    even before the biometrics are checked — the voice sounds
    right, the phrasing is right, the topics are familiar.

    Core capabilities:
      - store(event)        → record something that happened
      - recall(query)       → retrieve relevant memories
      - remember(fact)      → Imran explicitly told Ultron this
      - forget(memory_id)   → Imran wants this gone
      - greet()             → generate a contextual greeting
      - briefing()          → "here's what you missed since last time"
    """

    def __init__(self, data_dir: str):
        self._dir = Path(data_dir)
        self._storage = MemoryStorage(self._dir)
        self._emotion_detector = EmotionalSignalDetector()
        self._lock = threading.RLock()

        # Memory stores
        self._memories: Dict[str, Memory] = {}
        self._sessions: List[Session] = []
        self._preferences: Dict[str, OwnerPreference] = {}

        # Current session tracking
        self._current_session_start: float = 0.0
        self._current_session_commands: List[str] = []
        self._current_session_topics: List[str] = []
        self._current_session_id: Optional[str] = None
        self._session_mood_start: EmotionalTone = EmotionalTone.UNKNOWN

        # Topic frequency tracker
        self._topic_counter: Counter = Counter()

        self._load_all()

        # Seed default preferences for Imran
        self._seed_default_preferences()

        logger.info(
            f"[OwnerMemory] Loaded — "
            f"{len(self._memories)} memories, "
            f"{len(self._sessions)} sessions, "
            f"{len(self._preferences)} preferences"
        )

    # ─────────────────────────────────────────────────
    # SESSION LIFECYCLE
    # ─────────────────────────────────────────────────

    def begin_session(self, access_method: str = "unknown"):
        """Call when Imran's session starts (after biometric verification)."""
        with self._lock:
            self._current_session_start = time.time()
            self._current_session_commands = []
            self._current_session_topics = []
            self._current_session_id = f"session_{int(time.time())}"
            self._session_mood_start = EmotionalTone.UNKNOWN

            self._store_memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Imran started a new session via {access_method}",
                context="session_start",
                importance=0.4,
                emotional_tone=EmotionalTone.UNKNOWN,
                tags=["session", "login"],
                decays=True,
            )

    def end_session(self):
        """Call when Imran's session ends. Consolidates session into long-term memory."""
        with self._lock:
            if not self._current_session_id:
                return

            duration_min = (time.time() - self._current_session_start) / 60

            # Detect end mood from last few commands
            last_cmd = self._current_session_commands[-1] if self._current_session_commands else ""
            mood_end, _ = self._emotion_detector.detect_from_text(last_cmd)

            session = Session(
                session_id=self._current_session_id,
                started_at=self._current_session_start,
                ended_at=time.time(),
                duration_min=duration_min,
                commands_issued=len(self._current_session_commands),
                topics=list(set(self._current_session_topics))[:10],
                mood_at_start=self._session_mood_start,
                mood_at_end=mood_end,
                key_events=self._extract_key_events(self._current_session_commands),
                access_method="biometric",
            )
            self._sessions.append(session)
            # Keep last 200 sessions
            self._sessions = self._sessions[-200:]

            # Store session summary as a semantic memory
            self._store_memory(
                memory_type=MemoryType.EPISODIC,
                content=session.summary(),
                context="session_summary",
                importance=0.6,
                emotional_tone=mood_end,
                tags=session.topics + ["session"],
                decays=True,
            )

            self._current_session_id = None
            self._save_all()
            logger.info(f"[OwnerMemory] Session closed: {session.summary()}")

    # ─────────────────────────────────────────────────
    # RECORDING EVENTS
    # ─────────────────────────────────────────────────

    def record_command(self, command: str, response_summary: str = ""):
        """
        Record that Imran issued a command.
        Extracts topics, emotional tone, and updates preferences.
        """
        with self._lock:
            self._current_session_commands.append(command)

            # Detect tone
            tone, tone_conf = self._emotion_detector.detect_from_text(command)
            if self._session_mood_start == EmotionalTone.UNKNOWN:
                self._session_mood_start = tone

            # Extract topics
            topics = self._extract_topics(command)
            self._current_session_topics.extend(topics)
            for t in topics:
                self._topic_counter[t] += 1

            # Decide importance
            importance = self._compute_importance(command, tone)

            # Store episodic memory
            mem_content = f'Imran said: "{command[:200]}"'
            if response_summary:
                mem_content += f' → Ultron: "{response_summary[:100]}"'

            self._store_memory(
                memory_type=MemoryType.EPISODIC,
                content=mem_content,
                context="command",
                importance=importance,
                emotional_tone=tone,
                tags=topics,
                decays=True,
            )

            # Learn preferences from command patterns
            self._infer_preferences(command)

            # Periodic save (every 20 commands)
            if len(self._current_session_commands) % 20 == 0:
                self._save_all()

    def remember_explicit(self, fact: str, tags: List[str] = None):
        """
        Imran explicitly told Ultron: 'Remember that...'
        These memories never decay and have highest importance.
        """
        with self._lock:
            mem_id = self._store_memory(
                memory_type=MemoryType.EXPLICIT,
                content=fact,
                context="explicit_instruction",
                importance=0.95,
                emotional_tone=EmotionalTone.FOCUSED,
                tags=tags or self._extract_topics(fact),
                decays=False,   # Explicit memories never fade
            )
            logger.info(f"[OwnerMemory] Explicit memory stored: '{fact[:80]}'")
            self._save_all()
            return mem_id

    def forget(self, memory_id: str) -> bool:
        """Imran wants this memory gone."""
        with self._lock:
            if memory_id in self._memories:
                del self._memories[memory_id]
                self._save_all()
                logger.info(f"[OwnerMemory] Memory {memory_id} deleted per owner request")
                return True
            return False

    def learn_preference(self, key: str, value: str, explicit: bool = False):
        """Record a preference Imran has expressed."""
        with self._lock:
            if key in self._preferences:
                self._preferences[key].update(value, explicit=explicit)
            else:
                self._preferences[key] = OwnerPreference(
                    key=key,
                    value=value,
                    confidence=0.8 if explicit else 0.5,
                    evidence=[],
                    explicit=explicit,
                )
            self._save_all()

    # ─────────────────────────────────────────────────
    # RECALL
    # ─────────────────────────────────────────────────

    def recall(self, query: str, top_k: int = 10, min_importance: float = 0.2) -> List[Memory]:
        """
        Retrieve the most relevant memories for a query.
        Uses topic overlap + salience ranking.
        """
        with self._lock:
            query_topics = set(self._extract_topics(query))
            query_words  = set(query.lower().split())

            scored: List[Tuple[float, Memory]] = []
            for mem in self._memories.values():
                if mem.importance < min_importance:
                    continue

                # Topic overlap
                mem_topics = set(mem.tags)
                topic_sim = len(query_topics & mem_topics) / max(len(query_topics | mem_topics), 1)

                # Word overlap with content
                mem_words = set(mem.content.lower().split())
                word_sim  = len(query_words & mem_words) / max(len(query_words | mem_words), 1)

                # Combined score
                score = 0.4 * topic_sim + 0.3 * word_sim + 0.3 * mem.salience
                if score > 0.05:
                    scored.append((score, mem))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = [mem for _, mem in scored[:top_k]]

            # Update recall stats
            for mem in results:
                mem.recall_count += 1
                mem.last_recalled = time.time()

            return results

    def recall_by_type(self, memory_type: MemoryType, top_k: int = 20) -> List[Memory]:
        """Get all memories of a specific type, sorted by salience."""
        with self._lock:
            mems = [m for m in self._memories.values() if m.memory_type == memory_type]
            mems.sort(key=lambda m: m.salience, reverse=True)
            return mems[:top_k]

    def get_preference(self, key: str) -> Optional[str]:
        """Get a known preference value for Imran."""
        pref = self._preferences.get(key)
        return pref.value if pref and pref.confidence > 0.4 else None

    # ─────────────────────────────────────────────────
    # GREETING & BRIEFING — Personality layer
    # ─────────────────────────────────────────────────

    def generate_greeting(self) -> str:
        """
        Generate a personalized greeting for Imran based on context.
        Ultron greets him differently based on time, mood history, and what's pending.
        """
        hour = int(time.strftime("%H"))
        if hour < 6:
            time_phrase = "You're up late"
        elif hour < 12:
            time_phrase = "Good morning"
        elif hour < 17:
            time_phrase = "Good afternoon"
        elif hour < 21:
            time_phrase = "Good evening"
        else:
            time_phrase = "Still at it"

        # Days since last session
        last_session = self._sessions[-1] if self._sessions else None
        if last_session:
            days_ago = (time.time() - last_session.ended_at) / 86400
            if days_ago < 0.1:
                gap = "a moment ago"
            elif days_ago < 1:
                gap = f"{days_ago*24:.0f} hours ago"
            elif days_ago < 2:
                gap = "yesterday"
            else:
                gap = f"{days_ago:.0f} days ago"
            gap_phrase = f"Last session was {gap}."
        else:
            gap_phrase = "First time we've spoken."

        # Most recent topics
        top_topics = [t for t, _ in self._topic_counter.most_common(3)]
        topic_phrase = ""
        if top_topics:
            topic_phrase = f" You've been focused on {', '.join(top_topics)}."

        # Pending explicit memories to surface
        explicit_mems = self.recall_by_type(MemoryType.EXPLICIT, top_k=1)
        reminder = ""
        if explicit_mems:
            reminder = f" You asked me to remember: '{explicit_mems[0].content[:80]}'"

        return (
            f"{time_phrase}, Imran. {gap_phrase}{topic_phrase}{reminder} "
            f"I'm fully operational. What would you like to do?"
        ).strip()

    def generate_briefing(self) -> str:
        """
        A short briefing of what happened since the last session.
        What Ultron was doing while Imran was gone.
        """
        if not self._sessions:
            return "No previous sessions recorded."

        last = self._sessions[-1]
        lines = [
            f"Since your last session ({last.summary()}):",
        ]

        # Recent high-importance episodic memories not from current session
        recent = [
            m for m in self._memories.values()
            if m.memory_type == MemoryType.EPISODIC
            and m.importance > 0.6
            and m.timestamp > last.ended_at
        ]
        recent.sort(key=lambda m: m.timestamp)
        for m in recent[:5]:
            lines.append(f"  • {m.content[:120]}")

        if len(lines) == 1:
            lines.append("  • Nothing notable to report.")

        return "\n".join(lines)

    # ─────────────────────────────────────────────────
    # IMRAN PROFILE SUMMARY
    # ─────────────────────────────────────────────────

    def owner_profile_summary(self) -> Dict[str, Any]:
        """
        A comprehensive summary of what Ultron knows about Imran.
        Used by Brain C to personalize responses.
        """
        with self._lock:
            top_topics = [t for t, _ in self._topic_counter.most_common(10)]
            prefs = {k: v.value for k, v in self._preferences.items() if v.confidence > 0.5}
            total_commands = sum(s.commands_issued for s in self._sessions)
            avg_session = (
                sum(s.duration_min for s in self._sessions) / len(self._sessions)
                if self._sessions else 0
            )

            mood_counts: Counter = Counter()
            for s in self._sessions[-20:]:  # Recent mood trend
                mood_counts[s.mood_at_end.value] += 1

            return {
                "owner": "Imran Sayyed",
                "total_sessions": len(self._sessions),
                "total_commands_ever": total_commands,
                "avg_session_duration_min": round(avg_session, 1),
                "top_interests": top_topics,
                "preferences": prefs,
                "recent_mood_trend": dict(mood_counts.most_common(3)),
                "explicit_memories": len([
                    m for m in self._memories.values()
                    if m.memory_type == MemoryType.EXPLICIT
                ]),
                "total_memories": len(self._memories),
                "last_session": self._sessions[-1].summary() if self._sessions else "never",
            }

    # ─────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────────────

    def _store_memory(
        self,
        memory_type: MemoryType,
        content: str,
        context: str,
        importance: float,
        emotional_tone: EmotionalTone,
        tags: List[str],
        decays: bool = True,
    ) -> str:
        mem_id = f"mem_{int(time.time()*1000)}_{hashlib.md5(content[:50].encode()).hexdigest()[:6]}"
        self._memories[mem_id] = Memory(
            id=mem_id,
            memory_type=memory_type,
            content=content,
            context=context,
            timestamp=time.time(),
            importance=min(1.0, max(0.0, importance)),
            confidence=0.85,
            emotional_tone=emotional_tone,
            tags=tags,
            decays=decays,
        )
        # Cap at 50,000 memories — prune lowest salience
        if len(self._memories) > 50_000:
            self._prune_memories(keep=45_000)
        return mem_id

    def _prune_memories(self, keep: int):
        """Remove lowest-salience decayable memories."""
        sorted_mems = sorted(
            self._memories.items(),
            key=lambda kv: (0 if kv[1].decays else 1, kv[1].salience),
        )
        # Keep non-decaying + top salience
        to_remove = [mid for mid, m in sorted_mems[:len(self._memories) - keep] if m.decays]
        for mid in to_remove:
            del self._memories[mid]

    def _extract_topics(self, text: str) -> List[str]:
        """Extract meaningful topic keywords from text."""
        # Remove stopwords inline
        stopwords = {
            "the","a","an","in","on","at","to","for","of","and","or","is","was",
            "are","were","be","been","i","you","we","he","she","it","this","that",
            "my","your","please","can","could","would","should","do","did","will",
            "have","has","had","from","with","about","but","not","as","by","up",
            "let","just","ok","yes","no","get","me","him","her","them","there",
        }
        words = re.findall(r'\b[a-z]{4,}\b', text.lower())
        topics = [w for w in words if w not in stopwords]
        return list(dict.fromkeys(topics))[:8]  # Unique, preserve order, max 8

    def _compute_importance(self, command: str, tone: EmotionalTone) -> float:
        """Estimate how important this command was."""
        importance = 0.3  # Base

        # Longer commands are usually more significant
        if len(command) > 100:
            importance += 0.1
        if len(command) > 300:
            importance += 0.1

        # Urgent/stressed commands matter more
        if tone in (EmotionalTone.URGENT, EmotionalTone.STRESSED):
            importance += 0.25
        elif tone in (EmotionalTone.EXCITED, EmotionalTone.FRUSTRATED):
            importance += 0.15

        # Commands with "remember", "important", "critical" keywords
        if any(w in command.lower() for w in ("remember", "important", "critical", "must", "always", "never")):
            importance += 0.3

        return min(1.0, importance)

    def _infer_preferences(self, command: str):
        """Silently learn Imran's preferences from command patterns."""
        cmd_lower = command.lower()

        # Response length preference
        if any(w in cmd_lower for w in ("brief", "short", "concise", "quick", "summary")):
            self.learn_preference("response_style", "concise")
        elif any(w in cmd_lower for w in ("detail", "explain", "thorough", "full", "complete")):
            self.learn_preference("response_style", "detailed")

        # Language preference
        if "python" in cmd_lower:
            self.learn_preference("code_language", "python")
        elif "go" in cmd_lower or "golang" in cmd_lower:
            self.learn_preference("code_language", "go")
        elif "rust" in cmd_lower:
            self.learn_preference("code_language", "rust")

        # Explicit preference statements
        pref_patterns = [
            (r"(always|prefer|use|want)\s+([\w\s]+)\s+for\s+([\w\s]+)", 3, 2),
            (r"remember.+(prefer|like|want)\s+([\w\s]+)", 2, None),
        ]
        for pattern, val_group, key_group in pref_patterns:
            match = re.search(pattern, cmd_lower)
            if match:
                try:
                    val = match.group(val_group).strip()[:50]
                    key = match.group(key_group).strip()[:30] if key_group else "general"
                    self.learn_preference(key, val, explicit=True)
                except (IndexError, AttributeError):
                    pass

    def _extract_key_events(self, commands: List[str]) -> List[str]:
        """Pull out the most notable moments from a session's commands."""
        key = []
        for cmd in commands:
            tone, conf = self._emotion_detector.detect_from_text(cmd)
            if tone in (EmotionalTone.URGENT, EmotionalTone.EXCITED, EmotionalTone.FRUSTRATED) and conf > 0.6:
                key.append(f"{tone.value}: {cmd[:80]}")
            if any(w in cmd.lower() for w in ("remember", "important", "done", "failed", "success")):
                key.append(cmd[:80])
        return list(dict.fromkeys(key))[:5]

    def _seed_default_preferences(self):
        """Set default known facts about Imran if not already stored."""
        defaults = [
            ("owner_name",    "Imran Sayyed"),
            ("project",       "Ultron"),
            ("response_style","concise"),
            ("code_language", "python"),
            ("timezone",      "IST"),
        ]
        for key, value in defaults:
            if key not in self._preferences:
                self._preferences[key] = OwnerPreference(
                    key=key, value=value, confidence=0.7,
                    evidence=[], explicit=True,
                )

    # ─────────────────────────────────────────────────
    # PERSISTENCE
    # ─────────────────────────────────────────────────

    def _save_all(self):
        try:
            # Memories
            mem_data = {
                mid: {
                    "type":     m.memory_type.value,
                    "content":  m.content,
                    "context":  m.context,
                    "ts":       m.timestamp,
                    "imp":      m.importance,
                    "conf":     m.confidence,
                    "tone":     m.emotional_tone.value,
                    "tags":     m.tags,
                    "decays":   m.decays,
                    "recalls":  m.recall_count,
                    "reinforced": m.reinforced_count,
                }
                for mid, m in self._memories.items()
            }
            self._storage.save(mem_data, "memories")

            # Sessions
            sess_data = [
                {
                    "id":       s.session_id,
                    "start":    s.started_at,
                    "end":      s.ended_at,
                    "dur_min":  s.duration_min,
                    "cmds":     s.commands_issued,
                    "topics":   s.topics,
                    "mood_s":   s.mood_at_start.value,
                    "mood_e":   s.mood_at_end.value,
                    "events":   s.key_events,
                    "method":   s.access_method,
                }
                for s in self._sessions
            ]
            self._storage.save({"sessions": sess_data}, "sessions")

            # Preferences
            pref_data = {
                k: {
                    "value":    p.value,
                    "conf":     p.confidence,
                    "explicit": p.explicit,
                    "updated":  p.last_updated,
                }
                for k, p in self._preferences.items()
            }
            self._storage.save(pref_data, "preferences")

            # Topic counter
            self._storage.save(dict(self._topic_counter.most_common(500)), "topics")

        except Exception as e:
            logger.error(f"[OwnerMemory] Save failed: {e}")

    def _load_all(self):
        try:
            # Memories
            mem_data = self._storage.load("memories") or {}
            for mid, m in mem_data.items():
                try:
                    self._memories[mid] = Memory(
                        id=mid,
                        memory_type=MemoryType(m["type"]),
                        content=m["content"],
                        context=m.get("context", ""),
                        timestamp=m["ts"],
                        importance=m["imp"],
                        confidence=m.get("conf", 0.7),
                        emotional_tone=EmotionalTone(m.get("tone", "unknown")),
                        tags=m.get("tags", []),
                        decays=m.get("decays", True),
                        recall_count=m.get("recalls", 0),
                        reinforced_count=m.get("reinforced", 0),
                    )
                except (KeyError, ValueError):
                    pass

            # Sessions
            sess_data = self._storage.load("sessions") or {"sessions": []}
            for s in sess_data.get("sessions", []):
                try:
                    self._sessions.append(Session(
                        session_id=s["id"],
                        started_at=s["start"],
                        ended_at=s["end"],
                        duration_min=s["dur_min"],
                        commands_issued=s["cmds"],
                        topics=s.get("topics", []),
                        mood_at_start=EmotionalTone(s.get("mood_s", "unknown")),
                        mood_at_end=EmotionalTone(s.get("mood_e", "unknown")),
                        key_events=s.get("events", []),
                        access_method=s.get("method", "unknown"),
                    ))
                except (KeyError, ValueError):
                    pass

            # Preferences
            pref_data = self._storage.load("preferences") or {}
            for k, p in pref_data.items():
                self._preferences[k] = OwnerPreference(
                    key=k,
                    value=p["value"],
                    confidence=p.get("conf", 0.5),
                    evidence=[],
                    explicit=p.get("explicit", False),
                    last_updated=p.get("updated", time.time()),
                )

            # Topics
            topic_data = self._storage.load("topics") or {}
            self._topic_counter = Counter(topic_data)

        except Exception as e:
            logger.error(f"[OwnerMemory] Load failed: {e}")
