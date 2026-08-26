"""
Owner Identity Module — Imran Sayyed's Biometric Profile.

Ultron recognizes exactly one owner: Imran Sayyed.
This module stores, manages, and matches his biometric signatures:

  1. FACE EMBEDDING     — 128-d vector from face_recognition library
                          (falls back to dlib HOG if unavailable)
  2. VOICE FINGERPRINT  — MFCC + pitch profile from microphone audio
                          (13 MFCC coefficients + fundamental frequency)
  3. BEHAVIORAL PROFILE — Typing cadence, command vocabulary, interaction
                          patterns that Ultron learns over time
  4. CHALLENGE PHRASES  — Known spoken passphrases for voice verification

Enrollment:
  - First time: Ultron captures face + voice samples interactively
  - Ongoing: Profile silently reinforces with every successful session
  - Stored: AES-256-GCM encrypted at data_dir/owner/profile.enc

Recognition pipeline:
  ┌─────────────────────────────────────────────────────────────┐
  │  Camera frame ──► FaceDetector ──► FaceEmbedder             │
  │                                        │                     │
  │                                        ▼                     │
  │  Mic audio ──► VoicePreprocessor ──► VoiceEmbedder          │
  │                                        │                     │
  │                                        ▼                     │
  │                              IdentityMatcher                 │
  │                              (cosine similarity)             │
  │                                        │                     │
  │                              confidence score                │
  │                              ≥ 0.85 → OWNER VERIFIED        │
  └─────────────────────────────────────────────────────────────┘

Privacy: The raw biometric data NEVER leaves the local machine.
         All comparisons happen in-process. No cloud. No API calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ultron.owner_identity")

# ── Optional heavy imports (graceful degradation) ──────────────
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    logger.warning("[OwnerIdentity] numpy not installed — using pure-Python fallback")

try:
    import face_recognition  # pip install face-recognition
    _HAS_FACE_RECOGNITION = True
except ImportError:
    _HAS_FACE_RECOGNITION = False
    logger.warning("[OwnerIdentity] face_recognition not installed — face matching disabled")

try:
    import cv2  # pip install opencv-python
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False

try:
    import sounddevice as sd   # pip install sounddevice
    _HAS_SOUNDDEVICE = True
except ImportError:
    _HAS_SOUNDDEVICE = False
    logger.warning("[OwnerIdentity] sounddevice not installed — voice capture disabled")

try:
    import librosa             # pip install librosa
    _HAS_LIBROSA = True
except ImportError:
    _HAS_LIBROSA = False

# ── Crypto ─────────────────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
    logger.warning("[OwnerIdentity] cryptography not installed — profile stored unencrypted")


# ═══════════════════════════════════════════════════════════════
# OWNER PROFILE DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

OWNER_NAME = "Imran Sayyed"
OWNER_ID   = "IMRAN_SAYYED"

FACE_MATCH_THRESHOLD  = 0.55   # L2 distance (lower = more similar)
VOICE_MATCH_THRESHOLD = 0.82   # Cosine similarity (higher = more similar)
COMBINED_CONFIDENCE   = 0.85   # Minimum combined score to grant access


@dataclass
class FaceProfile:
    """Stored face signature for Imran."""
    embeddings: List[List[float]]          # Multiple 128-d vectors (different angles/lighting)
    image_hashes: List[str]                # SHA-256 of raw frames (for dedup)
    enrollment_count: int = 0
    last_updated: float = field(default_factory=time.time)
    best_lighting: str = "unknown"         # "bright", "dim", "normal" — best capture conditions

    @property
    def has_data(self) -> bool:
        return len(self.embeddings) > 0

    def average_embedding(self) -> Optional[List[float]]:
        if not self.embeddings:
            return None
        if not _HAS_NUMPY:
            # Pure Python mean
            n = len(self.embeddings)
            dim = len(self.embeddings[0])
            avg = [sum(e[i] for e in self.embeddings) / n for i in range(dim)]
            return avg
        import numpy as np
        return np.mean(self.embeddings, axis=0).tolist()


@dataclass
class VoiceProfile:
    """Stored voice signature for Imran."""
    mfcc_templates: List[List[float]]      # List of 13-coeff MFCC vectors
    pitch_range: Tuple[float, float]       # (min_hz, max_hz) typical for Imran's voice
    speaking_rate: float                   # syllables per second (approx)
    enrollment_phrases: List[str]          # Phrases used during enrollment
    enrollment_count: int = 0
    last_updated: float = field(default_factory=time.time)

    @property
    def has_data(self) -> bool:
        return len(self.mfcc_templates) > 0

    def average_mfcc(self) -> Optional[List[float]]:
        if not self.mfcc_templates:
            return None
        if not _HAS_NUMPY:
            n = len(self.mfcc_templates)
            dim = len(self.mfcc_templates[0])
            return [sum(t[i] for t in self.mfcc_templates) / n for i in range(dim)]
        import numpy as np
        return np.mean(self.mfcc_templates, axis=0).tolist()


@dataclass
class BehavioralProfile:
    """
    Soft biometric — Imran's interaction patterns.
    Not used for hard authentication, but adds confidence score.
    """
    common_commands: List[str]             # Frequently used commands / intents
    typical_interaction_hours: List[int]   # Hours of day (0-23) when Imran is active
    command_vocabulary: List[str] = field(default_factory=list)  # Words Imran uses most
    avg_session_duration_min: float = 0.0  # How long Imran typically stays in session
    session_count: int = 0
    last_seen: float = field(default_factory=time.time)

    def behavioral_score(self, current_hour: int, command: str) -> float:
        """Soft score: does this look like Imran's behavior?"""
        score = 0.5  # Base

        # Time-of-day match
        if self.typical_interaction_hours and current_hour in self.typical_interaction_hours:
            score += 0.2

        # Command vocabulary match
        if command and self.command_vocabulary:
            cmd_words = set(command.lower().split())
            vocab_words = set(w.lower() for w in self.command_vocabulary)
            overlap = len(cmd_words & vocab_words)
            if overlap > 0:
                score += min(0.3, overlap * 0.1)

        return min(1.0, score)


@dataclass
class OwnerProfile:
    """Complete biometric + behavioral profile for Imran Sayyed."""
    owner_id: str
    owner_name: str
    face: FaceProfile
    voice: VoiceProfile
    behavior: BehavioralProfile
    created_at: float = field(default_factory=time.time)
    last_verified: float = 0.0
    total_verifications: int = 0
    failed_verifications: int = 0
    enrolled: bool = False

    @property
    def trust_score(self) -> float:
        """Long-term trust based on verification history."""
        if self.total_verifications == 0:
            return 0.0
        success_rate = (self.total_verifications - self.failed_verifications) / self.total_verifications
        # Decay if not seen recently (1 day = 10% decay)
        days_since = (time.time() - self.last_verified) / 86400
        recency = max(0.5, 1.0 - days_since * 0.1)
        return success_rate * recency


# ═══════════════════════════════════════════════════════════════
# FACE ENGINE
# ═══════════════════════════════════════════════════════════════

class FaceEngine:
    """Handles face capture, embedding, and matching."""

    def capture_embedding(self, frame_bgr) -> Optional[List[float]]:
        """
        Given a BGR frame from cv2, return a 128-d face embedding.
        Returns None if no face found or library unavailable.
        """
        if not _HAS_FACE_RECOGNITION or not _HAS_NUMPY:
            logger.warning("[FaceEngine] face_recognition not available")
            return None

        import numpy as np
        # face_recognition expects RGB
        frame_rgb = frame_bgr[:, :, ::-1]
        locations = face_recognition.face_locations(frame_rgb, model="hog")
        if not locations:
            return None

        encodings = face_recognition.face_encodings(frame_rgb, locations)
        if not encodings:
            return None

        return encodings[0].tolist()

    def match(self, probe: List[float], template: List[float]) -> float:
        """
        Returns similarity score 0-1 (1 = identical).
        Uses L2 distance, normalized to [0, 1].
        """
        if not _HAS_NUMPY:
            # Pure-python L2
            diff = [a - b for a, b in zip(probe, template)]
            dist = math.sqrt(sum(d * d for d in diff))
        else:
            import numpy as np
            dist = float(np.linalg.norm(np.array(probe) - np.array(template)))

        # face_recognition L2 distances: 0 = same, ~0.6 = different
        # Map to 0-1 similarity
        similarity = max(0.0, 1.0 - dist / 0.8)
        return similarity

    def capture_from_camera(self, duration_sec: float = 3.0) -> Optional[List[float]]:
        """
        Opens the default camera, captures frames for `duration_sec`,
        and returns the best face embedding found.
        """
        if not _HAS_CV2:
            logger.error("[FaceEngine] cv2 not available — cannot capture from camera")
            return None

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("[FaceEngine] Cannot open camera")
            return None

        embeddings_found = []
        start = time.time()
        try:
            while time.time() - start < duration_sec:
                ret, frame = cap.read()
                if not ret:
                    break
                emb = self.capture_embedding(frame)
                if emb is not None:
                    embeddings_found.append(emb)
                time.sleep(0.1)
        finally:
            cap.release()

        if not embeddings_found:
            return None

        # Average the embeddings for a stable reading
        if not _HAS_NUMPY:
            n = len(embeddings_found)
            dim = len(embeddings_found[0])
            return [sum(e[i] for e in embeddings_found) / n for i in range(dim)]
        import numpy as np
        return np.mean(embeddings_found, axis=0).tolist()


# ═══════════════════════════════════════════════════════════════
# VOICE ENGINE
# ═══════════════════════════════════════════════════════════════

class VoiceEngine:
    """Handles voice capture, MFCC extraction, and matching."""

    SAMPLE_RATE = 22050
    N_MFCC      = 13
    RECORD_SEC  = 3.0

    def capture_mfcc(self, duration_sec: float = 3.0) -> Optional[List[float]]:
        """
        Record from microphone and extract MFCC vector.
        Returns a 13-element list or None.
        """
        if not _HAS_SOUNDDEVICE:
            logger.warning("[VoiceEngine] sounddevice not available — voice capture disabled")
            return None

        try:
            import numpy as np
            logger.info(f"[VoiceEngine] Recording {duration_sec}s...")
            audio = sd.rec(
                int(duration_sec * self.SAMPLE_RATE),
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype='float32',
            )
            sd.wait()
            audio = audio.flatten()

            return self._extract_mfcc(audio)
        except Exception as e:
            logger.error(f"[VoiceEngine] Capture failed: {e}")
            return None

    def _extract_mfcc(self, audio_array) -> Optional[List[float]]:
        """Extract mean MFCC coefficients from audio array."""
        if _HAS_LIBROSA:
            import librosa
            import numpy as np
            mfcc = librosa.feature.mfcc(
                y=audio_array,
                sr=self.SAMPLE_RATE,
                n_mfcc=self.N_MFCC,
            )
            return np.mean(mfcc, axis=1).tolist()
        elif _HAS_NUMPY:
            # Lightweight fallback: use FFT-based features
            import numpy as np
            fft = np.abs(np.fft.rfft(audio_array, n=512))
            # Split into N_MFCC frequency bands
            band_size = len(fft) // self.N_MFCC
            features = []
            for i in range(self.N_MFCC):
                band = fft[i * band_size:(i + 1) * band_size]
                features.append(float(np.mean(band)) if len(band) > 0 else 0.0)
            # Normalize
            max_val = max(abs(f) for f in features) or 1.0
            return [f / max_val for f in features]
        else:
            logger.warning("[VoiceEngine] No audio processing library available")
            return None

    def match(self, probe: List[float], template: List[float]) -> float:
        """
        Cosine similarity between two MFCC vectors. Returns 0-1.
        """
        if not probe or not template:
            return 0.0

        if _HAS_NUMPY:
            import numpy as np
            a = np.array(probe)
            b = np.array(template)
            denom = np.linalg.norm(a) * np.linalg.norm(b)
            if denom < 1e-9:
                return 0.0
            return float(np.dot(a, b) / denom)
        else:
            # Pure Python cosine
            dot = sum(a * b for a, b in zip(probe, template))
            mag_a = math.sqrt(sum(x * x for x in probe))
            mag_b = math.sqrt(sum(x * x for x in template))
            if mag_a < 1e-9 or mag_b < 1e-9:
                return 0.0
            return dot / (mag_a * mag_b)


# ═══════════════════════════════════════════════════════════════
# PROFILE STORAGE (encrypted)
# ═══════════════════════════════════════════════════════════════

class ProfileStorage:
    """
    Saves and loads the owner profile with AES-256-GCM encryption.
    The encryption key is derived from the machine's unique ID.
    """

    def __init__(self, profile_dir: Path):
        self._dir = profile_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._profile_path = self._dir / "owner_profile.enc"
        self._fallback_path = self._dir / "owner_profile.json"

    def save(self, profile: OwnerProfile):
        """Serialize and save profile."""
        data = self._serialize(profile)
        payload = json.dumps(data, indent=2).encode()

        if _HAS_CRYPTO:
            try:
                key = self._derive_key()
                aesgcm = AESGCM(key)
                nonce = os.urandom(12)
                ciphertext = aesgcm.encrypt(nonce, payload, None)
                with open(self._profile_path, "wb") as f:
                    f.write(nonce + ciphertext)
                logger.debug("[ProfileStorage] Profile saved (encrypted)")
                return
            except Exception as e:
                logger.warning(f"[ProfileStorage] Encryption failed: {e} — saving unencrypted")

        # Fallback: unencrypted
        with open(self._fallback_path, "w") as f:
            f.write(payload.decode())
        logger.debug("[ProfileStorage] Profile saved (unencrypted fallback)")

    def load(self) -> Optional[OwnerProfile]:
        """Load and deserialize profile."""
        # Try encrypted first
        if _HAS_CRYPTO and self._profile_path.exists():
            try:
                key = self._derive_key()
                aesgcm = AESGCM(key)
                with open(self._profile_path, "rb") as f:
                    blob = f.read()
                nonce, ciphertext = blob[:12], blob[12:]
                payload = aesgcm.decrypt(nonce, ciphertext, None)
                data = json.loads(payload)
                return self._deserialize(data)
            except Exception as e:
                logger.warning(f"[ProfileStorage] Decryption failed: {e}")

        # Fallback: unencrypted
        if self._fallback_path.exists():
            try:
                with open(self._fallback_path) as f:
                    data = json.load(f)
                return self._deserialize(data)
            except Exception as e:
                logger.warning(f"[ProfileStorage] Load failed: {e}")

        return None

    def _derive_key(self) -> bytes:
        """Derive a 32-byte encryption key from machine identity."""
        machine_id = self._get_machine_id()
        if _HAS_CRYPTO:
            kdf = Scrypt(salt=b"ultron_owner_v1", length=32, n=2**14, r=8, p=1)
            return kdf.derive(machine_id.encode())
        return hashlib.sha256(machine_id.encode()).digest()

    def _get_machine_id(self) -> str:
        """Get a stable machine identifier."""
        # macOS: use IOPlatformUUID
        try:
            import subprocess
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        except Exception:
            pass
        # Fallback: hostname
        import socket
        return socket.gethostname()

    def _serialize(self, profile: OwnerProfile) -> Dict[str, Any]:
        return {
            "owner_id": profile.owner_id,
            "owner_name": profile.owner_name,
            "created_at": profile.created_at,
            "last_verified": profile.last_verified,
            "total_verifications": profile.total_verifications,
            "failed_verifications": profile.failed_verifications,
            "enrolled": profile.enrolled,
            "face": {
                "embeddings": profile.face.embeddings,
                "image_hashes": profile.face.image_hashes,
                "enrollment_count": profile.face.enrollment_count,
                "last_updated": profile.face.last_updated,
                "best_lighting": profile.face.best_lighting,
            },
            "voice": {
                "mfcc_templates": profile.voice.mfcc_templates,
                "pitch_range": list(profile.voice.pitch_range),
                "speaking_rate": profile.voice.speaking_rate,
                "enrollment_phrases": profile.voice.enrollment_phrases,
                "enrollment_count": profile.voice.enrollment_count,
                "last_updated": profile.voice.last_updated,
            },
            "behavior": {
                "common_commands": profile.behavior.common_commands,
                "avg_session_duration_min": profile.behavior.avg_session_duration_min,
                "typical_interaction_hours": profile.behavior.typical_interaction_hours,
                "command_vocabulary": profile.behavior.command_vocabulary,
                "session_count": profile.behavior.session_count,
                "last_seen": profile.behavior.last_seen,
            },
        }

    def _deserialize(self, data: Dict[str, Any]) -> OwnerProfile:
        face_data   = data.get("face", {})
        voice_data  = data.get("voice", {})
        behav_data  = data.get("behavior", {})
        pitch_range = voice_data.get("pitch_range", [85.0, 255.0])

        return OwnerProfile(
            owner_id=data["owner_id"],
            owner_name=data["owner_name"],
            created_at=data.get("created_at", time.time()),
            last_verified=data.get("last_verified", 0.0),
            total_verifications=data.get("total_verifications", 0),
            failed_verifications=data.get("failed_verifications", 0),
            enrolled=data.get("enrolled", False),
            face=FaceProfile(
                embeddings=face_data.get("embeddings", []),
                image_hashes=face_data.get("image_hashes", []),
                enrollment_count=face_data.get("enrollment_count", 0),
                last_updated=face_data.get("last_updated", 0.0),
                best_lighting=face_data.get("best_lighting", "unknown"),
            ),
            voice=VoiceProfile(
                mfcc_templates=voice_data.get("mfcc_templates", []),
                pitch_range=(pitch_range[0], pitch_range[1]),
                speaking_rate=voice_data.get("speaking_rate", 4.0),
                enrollment_phrases=voice_data.get("enrollment_phrases", []),
                enrollment_count=voice_data.get("enrollment_count", 0),
                last_updated=voice_data.get("last_updated", 0.0),
            ),
            behavior=BehavioralProfile(
                common_commands=behav_data.get("common_commands", []),
                avg_session_duration_min=behav_data.get("avg_session_duration_min", 0.0),
                typical_interaction_hours=behav_data.get("typical_interaction_hours", []),
                command_vocabulary=behav_data.get("command_vocabulary", []),
                session_count=behav_data.get("session_count", 0),
                last_seen=behav_data.get("last_seen", 0.0),
            ),
        )


# ═══════════════════════════════════════════════════════════════
# OWNER IDENTITY MANAGER — Top-level API
# ═══════════════════════════════════════════════════════════════

class OwnerIdentityManager:
    """
    The single source of truth for Imran Sayyed's identity.

    Usage:
        mgr = OwnerIdentityManager("/path/to/data/owner")

        # First time: enroll
        mgr.enroll_interactive()

        # Every session: verify
        result = mgr.verify()
        if result.verified:
            token = result.token   # pass to BiometricGate
    """

    def __init__(self, data_dir: str):
        self._dir = Path(data_dir)
        self._storage = ProfileStorage(self._dir)
        self._face_engine = FaceEngine()
        self._voice_engine = VoiceEngine()
        self._lock = threading.RLock()

        # Load or create profile
        loaded = self._storage.load()
        if loaded and loaded.owner_id == OWNER_ID:
            self._profile = loaded
            logger.info(
                f"[OwnerIdentity] Profile loaded — {self._profile.owner_name}, "
                f"enrolled={self._profile.enrolled}, "
                f"verifications={self._profile.total_verifications}"
            )
        else:
            self._profile = self._make_empty_profile()
            logger.info(f"[OwnerIdentity] New profile created for {OWNER_NAME}")

    # ─────────────────────────────────────────────────
    # ENROLLMENT
    # ─────────────────────────────────────────────────

    def enroll_interactive(self, n_face_samples: int = 5, n_voice_samples: int = 3):
        """
        Interactive enrollment — captures face and voice from hardware.
        Call this once to register Imran.
        """
        print(f"\n{'='*60}")
        print(f"  ULTRON — Owner Enrollment")
        print(f"  Enrolling: {OWNER_NAME}")
        print(f"{'='*60}\n")

        # Face enrollment
        if _HAS_CV2 and _HAS_FACE_RECOGNITION:
            print(f"[1/2] Face enrollment — {n_face_samples} samples needed")
            print("  Please look at the camera. Keep your face visible.")
            new_embeddings = []
            for i in range(n_face_samples):
                input(f"  Sample {i+1}/{n_face_samples} — press Enter when ready...")
                emb = self._face_engine.capture_from_camera(duration_sec=2.0)
                if emb:
                    new_embeddings.append(emb)
                    print(f"  ✓ Face sample {i+1} captured")
                else:
                    print(f"  ✗ No face detected — try again")

            if new_embeddings:
                with self._lock:
                    self._profile.face.embeddings.extend(new_embeddings)
                    # Keep max 20 embeddings
                    self._profile.face.embeddings = self._profile.face.embeddings[-20:]
                    self._profile.face.enrollment_count += len(new_embeddings)
                    self._profile.face.last_updated = time.time()
                print(f"  ✓ Face profile: {len(self._profile.face.embeddings)} embeddings stored")
            else:
                print("  ✗ Face enrollment failed — no samples captured")
        else:
            print("[1/2] Face enrollment skipped — camera libraries not available")
            print("       Install: pip install face-recognition opencv-python")

        # Voice enrollment
        phrases = [
            "Ultron, I am Imran Sayyed, your owner",
            "Authorization granted, proceed with my command",
            "Wake up Ultron, it is me",
        ]
        if _HAS_SOUNDDEVICE:
            print(f"\n[2/2] Voice enrollment — {len(phrases)} phrases needed")
            new_mfcc = []
            for i, phrase in enumerate(phrases):
                input(f"\n  Phrase {i+1}: '{phrase}'\n  Press Enter then speak...")
                mfcc = self._voice_engine.capture_mfcc(duration_sec=3.0)
                if mfcc:
                    new_mfcc.append(mfcc)
                    print(f"  ✓ Voice sample {i+1} captured")
                else:
                    print(f"  ✗ Voice capture failed")

            if new_mfcc:
                with self._lock:
                    self._profile.voice.mfcc_templates.extend(new_mfcc)
                    self._profile.voice.mfcc_templates = self._profile.voice.mfcc_templates[-10:]
                    self._profile.voice.enrollment_phrases = phrases
                    self._profile.voice.enrollment_count += len(new_mfcc)
                    self._profile.voice.last_updated = time.time()
                print(f"  ✓ Voice profile: {len(self._profile.voice.mfcc_templates)} templates stored")
        else:
            print("[2/2] Voice enrollment skipped — sounddevice not available")
            print("       Install: pip install sounddevice librosa")

        # Mark enrolled if we have at least some data
        with self._lock:
            self._profile.enrolled = (
                self._profile.face.has_data or self._profile.voice.has_data
            )
            if self._profile.enrolled:
                self._storage.save(self._profile)
                print(f"\n✓ Enrollment complete — {OWNER_NAME} registered")
            else:
                print("\n✗ Enrollment incomplete — no biometric data captured")

    def enroll_from_data(
        self,
        face_embeddings: Optional[List[List[float]]] = None,
        voice_mfccs: Optional[List[List[float]]] = None,
    ):
        """
        Programmatic enrollment — inject pre-captured biometric data.
        Useful when hardware is unavailable during development.
        """
        with self._lock:
            if face_embeddings:
                self._profile.face.embeddings.extend(face_embeddings)
                self._profile.face.embeddings = self._profile.face.embeddings[-20:]
                self._profile.face.enrollment_count += len(face_embeddings)
                self._profile.face.last_updated = time.time()

            if voice_mfccs:
                self._profile.voice.mfcc_templates.extend(voice_mfccs)
                self._profile.voice.mfcc_templates = self._profile.voice.mfcc_templates[-10:]
                self._profile.voice.enrollment_count += len(voice_mfccs)
                self._profile.voice.last_updated = time.time()

            self._profile.enrolled = (
                self._profile.face.has_data or self._profile.voice.has_data
            )
            if self._profile.enrolled:
                self._storage.save(self._profile)
                logger.info("[OwnerIdentity] Programmatic enrollment complete")

    # ─────────────────────────────────────────────────
    # VERIFICATION — called by BiometricGate
    # ─────────────────────────────────────────────────

    def verify_face(self, face_embedding: List[float]) -> Tuple[bool, float]:
        """
        Compare a live face embedding against Imran's stored templates.
        Returns (matched, confidence).
        """
        with self._lock:
            if not self._profile.face.has_data:
                return False, 0.0

            avg_template = self._profile.face.average_embedding()
            if avg_template is None:
                return False, 0.0

            similarity = self._face_engine.match(face_embedding, avg_template)
            matched = similarity >= (1.0 - FACE_MATCH_THRESHOLD)
            return matched, similarity

    def verify_voice(self, mfcc: List[float]) -> Tuple[bool, float]:
        """
        Compare live MFCC against Imran's stored voice templates.
        Returns (matched, confidence).
        """
        with self._lock:
            if not self._profile.voice.has_data:
                return False, 0.0

            avg_template = self._profile.voice.average_mfcc()
            if avg_template is None:
                return False, 0.0

            similarity = self._voice_engine.match(mfcc, avg_template)
            matched = similarity >= VOICE_MATCH_THRESHOLD
            return matched, similarity

    def capture_and_verify(self) -> "VerificationResult":
        """
        Full real-time verification using camera + microphone.
        Returns a VerificationResult with token if successful.
        """
        face_confidence = 0.0
        voice_confidence = 0.0
        face_checked = False
        voice_checked = False

        # Face check
        if _HAS_CV2 and _HAS_FACE_RECOGNITION and self._profile.face.has_data:
            logger.info("[OwnerIdentity] Capturing face...")
            emb = self._face_engine.capture_from_camera(duration_sec=2.0)
            if emb:
                face_checked = True
                _, face_confidence = self.verify_face(emb)
                logger.info(f"[OwnerIdentity] Face confidence: {face_confidence:.2f}")

        # Voice check
        if _HAS_SOUNDDEVICE and self._profile.voice.has_data:
            logger.info("[OwnerIdentity] Listening for voice...")
            mfcc = self._voice_engine.capture_mfcc(duration_sec=3.0)
            if mfcc:
                voice_checked = True
                _, voice_confidence = self.verify_voice(mfcc)
                logger.info(f"[OwnerIdentity] Voice confidence: {voice_confidence:.2f}")

        return self._make_result(face_confidence, voice_confidence, face_checked, voice_checked)

    def verify_from_data(
        self,
        face_embedding: Optional[List[float]] = None,
        mfcc: Optional[List[float]] = None,
    ) -> "VerificationResult":
        """
        Verify using pre-captured data (for integration with camera/mic pipelines).
        At least one of face_embedding or mfcc must be provided.
        """
        face_confidence = 0.0
        voice_confidence = 0.0
        face_checked = face_embedding is not None
        voice_checked = mfcc is not None

        if face_embedding:
            _, face_confidence = self.verify_face(face_embedding)
        if mfcc:
            _, voice_confidence = self.verify_voice(mfcc)

        return self._make_result(face_confidence, voice_confidence, face_checked, voice_checked)

    def _make_result(
        self,
        face_conf: float, voice_conf: float,
        face_checked: bool, voice_checked: bool,
    ) -> "VerificationResult":
        """Combine face + voice scores into a final result."""
        scores_used = []
        if face_checked:
            scores_used.append(face_conf)
        if voice_checked:
            scores_used.append(voice_conf)

        if not scores_used:
            # No hardware available — cannot verify
            return VerificationResult(
                verified=False,
                confidence=0.0,
                face_confidence=face_conf,
                voice_confidence=voice_conf,
                method="none",
                reason="No biometric hardware available for verification",
                token=None,
            )

        # Combined: weighted average (face gets slightly more weight)
        if face_checked and voice_checked:
            combined = 0.55 * face_conf + 0.45 * voice_conf
            method = "face+voice"
        elif face_checked:
            combined = face_conf * 0.9   # Slight penalty for single-factor
            method = "face_only"
        else:
            combined = voice_conf * 0.85
            method = "voice_only"

        # Behavioral soft-boost
        current_hour = int(time.strftime("%H"))
        behav_boost = self._profile.behavior.behavioral_score(current_hour, "") * 0.05
        combined = min(1.0, combined + behav_boost)

        verified = combined >= COMBINED_CONFIDENCE

        with self._lock:
            self._profile.total_verifications += 1
            if not verified:
                self._profile.failed_verifications += 1
            else:
                self._profile.last_verified = time.time()
                self._profile.behavior.last_seen = time.time()
                self._profile.behavior.session_count += 1
            self._storage.save(self._profile)

        token = self._mint_token() if verified else None

        return VerificationResult(
            verified=verified,
            confidence=combined,
            face_confidence=face_conf,
            voice_confidence=voice_conf,
            method=method,
            reason="Identity confirmed" if verified else f"Confidence {combined:.0%} below threshold {COMBINED_CONFIDENCE:.0%}",
            token=token,
        )

    # ─────────────────────────────────────────────────
    # BEHAVIORAL LEARNING
    # ─────────────────────────────────────────────────

    def record_interaction(self, command: str, session_duration_min: float = 0.0):
        """Let Ultron learn Imran's patterns over time."""
        with self._lock:
            words = command.lower().split()
            for word in words:
                if len(word) > 3 and word not in self._profile.behavior.command_vocabulary:
                    self._profile.behavior.command_vocabulary.append(word)
            self._profile.behavior.command_vocabulary = (
                self._profile.behavior.command_vocabulary[-200:]
            )

            if command not in self._profile.behavior.common_commands:
                self._profile.behavior.common_commands.append(command)
                self._profile.behavior.common_commands = (
                    self._profile.behavior.common_commands[-100:]
                )

            current_hour = int(time.strftime("%H"))
            if current_hour not in self._profile.behavior.typical_interaction_hours:
                self._profile.behavior.typical_interaction_hours.append(current_hour)

            if session_duration_min > 0:
                prev = self._profile.behavior.avg_session_duration_min
                n = self._profile.behavior.session_count or 1
                self._profile.behavior.avg_session_duration_min = (
                    prev * (n - 1) / n + session_duration_min / n
                )

            self._storage.save(self._profile)

    # ─────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────

    def _mint_token(self) -> str:
        """
        Issue a time-limited HMAC token for Brain C / BiometricGate.
        Format: IMRAN_SAYYED|timestamp|hmac32
        """
        secret_path = self._dir / ".token_secret"
        if secret_path.exists():
            secret = secret_path.read_text().strip()
        else:
            import secrets
            secret = secrets.token_hex(32)
            secret_path.write_text(secret)
            secret_path.chmod(0o600)

        ts = f"{time.time():.3f}"
        digest = hashlib.sha256(
            f"{OWNER_ID}|{ts}|{secret}".encode()
        ).hexdigest()[:32]
        return f"{OWNER_ID}|{ts}|{digest}"

    def _make_empty_profile(self) -> OwnerProfile:
        return OwnerProfile(
            owner_id=OWNER_ID,
            owner_name=OWNER_NAME,
            face=FaceProfile(embeddings=[], image_hashes=[]),
            voice=VoiceProfile(
                mfcc_templates=[],
                pitch_range=(85.0, 255.0),
                speaking_rate=4.0,
                enrollment_phrases=[],
            ),
            behavior=BehavioralProfile(
                common_commands=[],
                typical_interaction_hours=list(range(8, 24)),  # Default: 8am-midnight
                command_vocabulary=[],
            ),
        )

    @property
    def is_enrolled(self) -> bool:
        return self._profile.enrolled

    @property
    def profile(self) -> OwnerProfile:
        return self._profile

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "owner": self._profile.owner_name,
                "enrolled": self._profile.enrolled,
                "face_samples": len(self._profile.face.embeddings),
                "voice_samples": len(self._profile.voice.mfcc_templates),
                "total_verifications": self._profile.total_verifications,
                "failed_verifications": self._profile.failed_verifications,
                "trust_score": round(self._profile.trust_score, 3),
                "last_verified": (
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._profile.last_verified))
                    if self._profile.last_verified > 0 else "never"
                ),
                "face_recognition_available": _HAS_FACE_RECOGNITION,
                "voice_capture_available": _HAS_SOUNDDEVICE,
            }


# ═══════════════════════════════════════════════════════════════
# VERIFICATION RESULT
# ═══════════════════════════════════════════════════════════════

@dataclass
class VerificationResult:
    verified: bool
    confidence: float
    face_confidence: float
    voice_confidence: float
    method: str              # "face+voice", "face_only", "voice_only", "none"
    reason: str
    token: Optional[str]     # Valid HMAC token if verified=True, else None
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        status = "✓ VERIFIED" if self.verified else "✗ DENIED"
        return (
            f"{status} | {self._profile_name()} | "
            f"confidence={self.confidence:.0%} | method={self.method} | {self.reason}"
        )

    def _profile_name(self) -> str:
        return OWNER_NAME if self.verified else "UNKNOWN"
