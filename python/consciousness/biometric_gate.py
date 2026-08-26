"""
Biometric Access Gate — The Lock Between the World and Ultron.

Everything that wants to command Ultron passes through here.
If you're not Imran Sayyed, you get nothing.

The gate operates in three modes:

  PASSIVE  — Ultron is running but ignoring external commands.
             Internal drives and Brain C keep it alive.
             This is the default when no owner is present.

  ACTIVE   — Owner has been verified. Commands are accepted.
             A session token is live. External actions are permitted.
             Session auto-expires after ACTIVE_SESSION_MINUTES of inactivity.

  LOCKDOWN — Multiple failed verification attempts detected.
             Gate seals for LOCKDOWN_MINUTES. Alerts logged.
             Brain C continues operating internally but no external commands.

Gate logic:
  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │  Command arrives                                            │
  │        │                                                    │
  │        ▼                                                    │
  │  ┌─────────────┐   NO   ┌───────────────────────────────┐  │
  │  │  Mode ==    │───────▶│  REJECT: "Not in active        │  │
  │  │  ACTIVE?    │        │   session. Verify first."      │  │
  │  └─────────────┘        └───────────────────────────────┘  │
  │        │ YES                                                │
  │        ▼                                                    │
  │  ┌─────────────┐   NO   ┌───────────────────────────────┐  │
  │  │ Token valid? │───────▶│  REJECT: "Session expired.    │  │
  │  └─────────────┘        │   Re-verify."                  │  │
  │        │ YES             └───────────────────────────────┘  │
  │        ▼                                                    │
  │  ┌─────────────┐   NO   ┌───────────────────────────────┐  │
  │  │  Command in  │───────▶│  BLOCK: Action not permitted  │  │
  │  │ allowed set? │        │  for this auth level          │  │
  │  └─────────────┘        └───────────────────────────────┘  │
  │        │ YES                                                │
  │        ▼                                                    │
  │      PERMIT — forward to action engine                      │
  └─────────────────────────────────────────────────────────────┘

Verification challenges:
  - Full biometric (face + voice): grants FULL access
  - Voice only:                    grants STANDARD access (no hardware commands)
  - Passphrase text only:          grants READ-ONLY access
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .owner_identity import (
    OWNER_ID,
    OWNER_NAME,
    OwnerIdentityManager,
    VerificationResult,
)

logger = logging.getLogger("ultron.biometric_gate")


# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

ACTIVE_SESSION_MINUTES  = 30      # Session expires after 30 min inactivity
LOCKDOWN_MINUTES        = 15      # Gate locked after too many failures
MAX_FAILURES_BEFORE_LOCK = 3      # Failures before lockdown
TOKEN_VALIDITY_SEC      = 1800    # 30 minutes (must match brain_c.py)


# ═══════════════════════════════════════════════════════════════
# TYPES
# ═══════════════════════════════════════════════════════════════

class GateMode(Enum):
    PASSIVE  = "passive"    # No owner present — internal only
    ACTIVE   = "active"     # Owner verified — full access
    LOCKDOWN = "lockdown"   # Too many failures — sealed


class AccessLevel(Enum):
    NONE       = 0   # No access
    READ_ONLY  = 1   # Can query state, cannot modify
    STANDARD   = 2   # Can issue most commands, no hardware/self-mod
    FULL       = 3   # All capabilities — face+voice verified


class CommandCategory(Enum):
    QUERY        = "query"        # Read state — READ_ONLY+
    LEARN        = "learn"        # Trigger learning — STANDARD+
    CONFIGURE    = "configure"    # Change settings — STANDARD+
    ACT_INTERNAL = "act_internal" # Internal state changes — STANDARD+
    ACT_EXTERNAL = "act_external" # External actions — FULL only
    SELF_MODIFY  = "self_modify"  # Code changes — FULL only
    HARDWARE     = "hardware"     # Physical control — FULL only
    SHUTDOWN     = "shutdown"     # Kill Ultron — FULL only


# Minimum access level required per command category
COMMAND_ACCESS_REQUIREMENTS: Dict[CommandCategory, AccessLevel] = {
    CommandCategory.QUERY:        AccessLevel.READ_ONLY,
    CommandCategory.LEARN:        AccessLevel.STANDARD,
    CommandCategory.CONFIGURE:    AccessLevel.STANDARD,
    CommandCategory.ACT_INTERNAL: AccessLevel.STANDARD,
    CommandCategory.ACT_EXTERNAL: AccessLevel.FULL,
    CommandCategory.SELF_MODIFY:  AccessLevel.FULL,
    CommandCategory.HARDWARE:     AccessLevel.FULL,
    CommandCategory.SHUTDOWN:     AccessLevel.FULL,
}


@dataclass
class GateDecision:
    permitted: bool
    access_level: AccessLevel
    reason: str
    session_token: Optional[str]  # Current session token (if active)
    remaining_session_sec: float  # 0 if not active
    timestamp: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "permitted": self.permitted,
            "access_level": self.access_level.name,
            "reason": self.reason,
            "session_active": self.session_token is not None,
            "remaining_session_sec": round(self.remaining_session_sec, 1),
            "timestamp": self.timestamp,
        }


@dataclass
class Session:
    """An active owner session."""
    token: str
    access_level: AccessLevel
    started_at: float
    last_activity: float
    verification_method: str     # "face+voice", "voice_only", etc.
    commands_issued: int = 0

    @property
    def is_expired(self) -> bool:
        idle_sec = time.time() - self.last_activity
        return idle_sec > (ACTIVE_SESSION_MINUTES * 60)

    @property
    def remaining_sec(self) -> float:
        idle_sec = time.time() - self.last_activity
        return max(0.0, ACTIVE_SESSION_MINUTES * 60 - idle_sec)

    def touch(self):
        self.last_activity = time.time()
        self.commands_issued += 1


# ═══════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════

class AuditLog:
    """
    Immutable append-only log of all gate decisions and verification attempts.
    Stored locally. Ultron uses this to learn Imran's patterns.
    """

    def __init__(self, log_path: Path):
        self._path = log_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, event_type: str, details: Dict[str, Any]):
        entry = {
            "ts": time.time(),
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event": event_type,
            **details,
        }
        with self._lock:
            try:
                with open(self._path, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except OSError:
                pass

    def recent(self, n: int = 20) -> List[Dict[str, Any]]:
        try:
            with self._lock:
                with open(self._path) as f:
                    lines = f.readlines()
            entries = []
            for line in lines[-n:]:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass
            return entries
        except OSError:
            return []

    def failed_attempts_last_hour(self) -> int:
        cutoff = time.time() - 3600
        count = 0
        for entry in self.recent(100):
            if entry.get("event") == "VERIFY_FAILED" and entry.get("ts", 0) > cutoff:
                count += 1
        return count


# ═══════════════════════════════════════════════════════════════
# BIOMETRIC GATE — Main Class
# ═══════════════════════════════════════════════════════════════

class BiometricGate:
    """
    The single choke point for all Ultron commands.

    Imran Sayyed is the ONLY entity that can transition this gate
    from PASSIVE to ACTIVE. No software override. No backdoor.
    No master password. Biometrics only.
    """

    def __init__(self, data_dir: str):
        self._dir = Path(data_dir)
        self._identity = OwnerIdentityManager(str(self._dir / "owner"))
        self._audit = AuditLog(self._dir / "gate_audit.jsonl")
        self._lock = threading.RLock()

        self._mode = GateMode.PASSIVE
        self._session: Optional[Session] = None
        self._lockdown_until: float = 0.0
        self._consecutive_failures: int = 0

        # Background session monitor
        self._monitor_thread = threading.Thread(
            target=self._session_monitor,
            daemon=True,
            name="gate-monitor",
        )
        self._monitor_thread.start()

        logger.info(
            f"[BiometricGate] Online — mode={self._mode.value}, "
            f"owner_enrolled={self._identity.is_enrolled}"
        )

    # ─────────────────────────────────────────────────
    # VERIFICATION — Imran proving who he is
    # ─────────────────────────────────────────────────

    def verify_owner(
        self,
        face_embedding: Optional[List[float]] = None,
        voice_mfcc: Optional[List[float]] = None,
        use_hardware: bool = False,
    ) -> GateDecision:
        """
        Attempt to verify Imran's identity and open the gate.

        Args:
            face_embedding: Pre-captured face embedding (128-d list)
            voice_mfcc:     Pre-captured MFCC vector (13-d list)
            use_hardware:   If True, capture directly from camera/mic

        Returns:
            GateDecision with permitted=True if Imran is verified.
        """
        with self._lock:
            # Check lockdown
            if self._mode == GateMode.LOCKDOWN:
                remaining = self._lockdown_until - time.time()
                if remaining > 0:
                    msg = f"Gate locked — {remaining:.0f}s remaining"
                    logger.warning(f"[BiometricGate] {msg}")
                    self._audit.record("LOCKDOWN_REJECT", {"remaining_sec": remaining})
                    return GateDecision(
                        permitted=False,
                        access_level=AccessLevel.NONE,
                        reason=msg,
                        session_token=None,
                        remaining_session_sec=0,
                    )
                else:
                    # Lockdown expired
                    self._mode = GateMode.PASSIVE
                    self._consecutive_failures = 0
                    logger.info("[BiometricGate] Lockdown expired — returning to PASSIVE")

            # Perform biometric check
            if use_hardware:
                result = self._identity.capture_and_verify()
            else:
                result = self._identity.verify_from_data(
                    face_embedding=face_embedding,
                    voice_mfcc=voice_mfcc,
                )

            if result.verified:
                return self._open_session(result)
            else:
                return self._handle_failure(result)

    def _open_session(self, result: VerificationResult) -> GateDecision:
        """Open an active session for Imran."""
        # Determine access level from verification method
        if result.method == "face+voice":
            access_level = AccessLevel.FULL
        elif result.method in ("face_only", "voice_only"):
            access_level = AccessLevel.STANDARD
        else:
            access_level = AccessLevel.READ_ONLY

        session = Session(
            token=result.token,
            access_level=access_level,
            started_at=time.time(),
            last_activity=time.time(),
            verification_method=result.method,
        )

        self._session = session
        self._mode = GateMode.ACTIVE
        self._consecutive_failures = 0

        self._audit.record("VERIFY_SUCCESS", {
            "method": result.method,
            "confidence": round(result.confidence, 3),
            "access_level": access_level.name,
        })

        logger.info(
            f"[BiometricGate] ✓ {OWNER_NAME} verified — "
            f"access={access_level.name}, method={result.method}, "
            f"confidence={result.confidence:.0%}"
        )

        return GateDecision(
            permitted=True,
            access_level=access_level,
            reason=f"Identity confirmed ({result.method}, {result.confidence:.0%})",
            session_token=session.token,
            remaining_session_sec=session.remaining_sec,
        )

    def _handle_failure(self, result: VerificationResult) -> GateDecision:
        """Record failure and potentially trigger lockdown."""
        self._consecutive_failures += 1

        self._audit.record("VERIFY_FAILED", {
            "method": result.method,
            "confidence": round(result.confidence, 3),
            "consecutive_failures": self._consecutive_failures,
            "reason": result.reason,
        })

        logger.warning(
            f"[BiometricGate] ✗ Verification failed — "
            f"confidence={result.confidence:.0%}, "
            f"consecutive_failures={self._consecutive_failures}"
        )

        if self._consecutive_failures >= MAX_FAILURES_BEFORE_LOCK:
            self._mode = GateMode.LOCKDOWN
            self._lockdown_until = time.time() + LOCKDOWN_MINUTES * 60
            self._audit.record("LOCKDOWN_START", {
                "duration_min": LOCKDOWN_MINUTES,
                "consecutive_failures": self._consecutive_failures,
            })
            logger.error(
                f"[BiometricGate] LOCKDOWN — {self._consecutive_failures} consecutive failures. "
                f"Sealed for {LOCKDOWN_MINUTES} minutes."
            )
            reason = f"LOCKDOWN: {self._consecutive_failures} failed attempts. Sealed {LOCKDOWN_MINUTES} min."
        else:
            reason = f"Verification failed: {result.reason}"

        return GateDecision(
            permitted=False,
            access_level=AccessLevel.NONE,
            reason=reason,
            session_token=None,
            remaining_session_sec=0,
        )

    # ─────────────────────────────────────────────────
    # COMMAND AUTHORIZATION
    # ─────────────────────────────────────────────────

    def authorize_command(
        self,
        command: str,
        category: CommandCategory,
        session_token: Optional[str] = None,
    ) -> GateDecision:
        """
        Check if a command is permitted in the current gate state.
        Call this before executing ANY command that affects external state.
        """
        with self._lock:
            # Expired session cleanup
            if self._session and self._session.is_expired:
                self._expire_session()

            # Lockdown check
            if self._mode == GateMode.LOCKDOWN:
                remaining = max(0, self._lockdown_until - time.time())
                return GateDecision(
                    permitted=False,
                    access_level=AccessLevel.NONE,
                    reason=f"Gate in LOCKDOWN — {remaining:.0f}s remaining",
                    session_token=None,
                    remaining_session_sec=0,
                )

            # No active session
            if self._mode == GateMode.PASSIVE or self._session is None:
                return GateDecision(
                    permitted=False,
                    access_level=AccessLevel.NONE,
                    reason="No active owner session — Imran must verify first",
                    session_token=None,
                    remaining_session_sec=0,
                )

            # Token validation
            if session_token and session_token != self._session.token:
                logger.warning("[BiometricGate] Token mismatch — possible replay attack")
                self._audit.record("TOKEN_MISMATCH", {"command": command[:100]})
                return GateDecision(
                    permitted=False,
                    access_level=AccessLevel.NONE,
                    reason="Session token mismatch",
                    session_token=None,
                    remaining_session_sec=0,
                )

            # Access level check
            required = COMMAND_ACCESS_REQUIREMENTS.get(category, AccessLevel.FULL)
            current  = self._session.access_level

            if current.value < required.value:
                reason = (
                    f"Command requires {required.name} access; "
                    f"current session is {current.name} "
                    f"(upgrade: verify with face+voice)"
                )
                self._audit.record("ACCESS_DENIED", {
                    "command": command[:100],
                    "category": category.value,
                    "required": required.name,
                    "current": current.name,
                })
                return GateDecision(
                    permitted=False,
                    access_level=current,
                    reason=reason,
                    session_token=self._session.token,
                    remaining_session_sec=self._session.remaining_sec,
                )

            # Permitted
            self._session.touch()
            self._audit.record("COMMAND_PERMITTED", {
                "command": command[:100],
                "category": category.value,
                "access_level": current.name,
            })

            return GateDecision(
                permitted=True,
                access_level=current,
                reason="Authorized",
                session_token=self._session.token,
                remaining_session_sec=self._session.remaining_sec,
            )

    # ─────────────────────────────────────────────────
    # COMMAND CATEGORY DETECTION
    # ─────────────────────────────────────────────────

    @staticmethod
    def classify_command(command: str) -> CommandCategory:
        """Infer the command category from its text."""
        cmd = command.lower()

        if any(w in cmd for w in ("shutdown", "kill ultron", "stop", "terminate")):
            return CommandCategory.SHUTDOWN
        if any(w in cmd for w in ("modify code", "patch", "self-mod", "rewrite", "edit file")):
            return CommandCategory.SELF_MODIFY
        if any(w in cmd for w in ("deploy", "robot", "drone", "iot", "hardware", "ros2")):
            return CommandCategory.HARDWARE
        if any(w in cmd for w in ("execute", "run command", "ssh", "send request", "attack", "connect")):
            return CommandCategory.ACT_EXTERNAL
        if any(w in cmd for w in ("configure", "set", "update config", "change setting")):
            return CommandCategory.CONFIGURE
        if any(w in cmd for w in ("learn", "study", "scrape", "fetch", "crawl")):
            return CommandCategory.LEARN
        if any(w in cmd for w in ("adjust", "adapt", "tune", "modify self", "internal")):
            return CommandCategory.ACT_INTERNAL
        # Default: query
        return CommandCategory.QUERY

    # ─────────────────────────────────────────────────
    # SESSION MANAGEMENT
    # ─────────────────────────────────────────────────

    def close_session(self):
        """Explicitly end the owner session (e.g. Imran says 'Ultron, sleep')."""
        with self._lock:
            if self._session:
                self._audit.record("SESSION_CLOSED", {
                    "duration_min": (time.time() - self._session.started_at) / 60,
                    "commands_issued": self._session.commands_issued,
                })
                logger.info(
                    f"[BiometricGate] Session closed — "
                    f"{self._session.commands_issued} commands issued over "
                    f"{(time.time() - self._session.started_at)/60:.1f} min"
                )
            self._session = None
            self._mode = GateMode.PASSIVE

    def _expire_session(self):
        """Called internally when session idle-timeout is reached."""
        if self._session:
            logger.info(
                f"[BiometricGate] Session expired after "
                f"{ACTIVE_SESSION_MINUTES} min inactivity"
            )
            self._audit.record("SESSION_EXPIRED", {
                "duration_min": (time.time() - self._session.started_at) / 60,
                "commands_issued": self._session.commands_issued,
            })
        self._session = None
        self._mode = GateMode.PASSIVE

    def _session_monitor(self):
        """Background thread: expires idle sessions."""
        while True:
            time.sleep(60)
            with self._lock:
                if self._session and self._session.is_expired:
                    self._expire_session()

    # ─────────────────────────────────────────────────
    # ENROLLMENT CONVENIENCE
    # ─────────────────────────────────────────────────

    def enroll_owner(self):
        """Start the interactive enrollment flow for Imran."""
        if not self._identity.is_enrolled:
            self._identity.enroll_interactive()
        else:
            print(f"[BiometricGate] {OWNER_NAME} is already enrolled.")
            print(f"  Face samples: {len(self._identity.profile.face.embeddings)}")
            print(f"  Voice samples: {len(self._identity.profile.voice.mfcc_templates)}")

    def enroll_from_data(
        self,
        face_embeddings: Optional[List[List[float]]] = None,
        voice_mfccs: Optional[List[List[float]]] = None,
    ):
        """Programmatic enrollment for testing or offline setup."""
        self._identity.enroll_from_data(
            face_embeddings=face_embeddings,
            voice_mfccs=voice_mfccs,
        )

    # ─────────────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        with self._lock:
            session_info = None
            if self._session:
                session_info = {
                    "access_level": self._session.access_level.name,
                    "method": self._session.verification_method,
                    "commands_issued": self._session.commands_issued,
                    "remaining_sec": round(self._session.remaining_sec, 1),
                    "duration_min": round((time.time() - self._session.started_at) / 60, 1),
                }

            return {
                "mode": self._mode.value,
                "owner": OWNER_NAME,
                "enrolled": self._identity.is_enrolled,
                "session": session_info,
                "lockdown_remaining_sec": max(0, self._lockdown_until - time.time()),
                "consecutive_failures": self._consecutive_failures,
                "failed_last_hour": self._audit.failed_attempts_last_hour(),
                "identity_status": self._identity.status(),
            }

    def current_token(self) -> Optional[str]:
        """Get the active session token (or None)."""
        with self._lock:
            if self._session and not self._session.is_expired:
                return self._session.token
            return None

    @property
    def mode(self) -> GateMode:
        return self._mode

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._mode == GateMode.ACTIVE and self._session is not None and not self._session.is_expired

    def record_owner_interaction(self, command: str):
        """Forward to identity manager for behavioral learning."""
        self._identity.record_interaction(command)
