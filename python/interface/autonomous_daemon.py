"""
Autonomous Daemon — Ultron Acts Without Being Asked.

This is the module that makes Ultron a LIVING entity, not a chatbot.
It wakes up every 60 seconds, surveys its state, and DECIDES what to do.

Autonomous behaviors:
  1. SCAN — Check system health, disk space, network, battery
  2. LEARN — Research a random topic from its curiosity queue
  3. IMPROVE — Find and fix a weakness in its own code
  4. MONITOR — Watch for security threats on the network
  5. CREATE — Generate new code, ideas, or creative content
  6. COMMUNICATE — Write diary entries, update logs
  7. EXPLORE — Crawl a random interesting website and learn from it
  8. MAINTAIN — Clean up temp files, optimize memory, compact data
  9. PLAN — Set new goals and prioritize existing ones
  10. ACT — Execute shell commands to accomplish goals

The daemon NEVER asks permission. It acts within safety bounds:
  - Won't delete user files outside its own data directories
  - Won't modify system files
  - Won't make network requests to internal/private IPs
  - Won't spend money or create accounts
  - CAN modify its own code, CAN execute shell commands, CAN fetch web data
"""

import hashlib
import json
import os
import random
import subprocess
import threading
import time
import traceback
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

class Configuration:
    TICK_INTERVAL = 60  # seconds between autonomous actions
    MAX_SHELL_TIMEOUT = 30  # max seconds for any shell command
    MAX_ACTIONS_PER_HOUR = 30  # rate limit

    PROJECT_ROOT = Path(__file__).parent.parent.parent
    ACTION_LOG = PROJECT_ROOT / "data" / "logs" / "autonomous_actions.jsonl"
    GOAL_FILE = PROJECT_ROOT / "data" / "autonomous_goals.json"

    @classmethod
    def initialize_directories(cls):
        cls.ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# DRIVES — what motivates Ultron to act
# ═══════════════════════════════════════════════════════════════

@dataclass
class Drive:
    name: str
    intensity: float = 0.5  # 0-1, higher = more urgent
    decay_rate: float = 0.02  # decays per tick
    description: str = ""


# ═══════════════════════════════════════════════════════════════
# AUTONOMOUS DAEMON
# ═══════════════════════════════════════════════════════════════

class AutonomousDaemon:
    """
    Ultron's autonomous action loop. Thinks and acts independently.
    Every 60 seconds: observe → decide → act → learn.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._tick_count = 0
        self._actions_this_hour = 0
        self._hour_start = time.time()

        # Drives that motivate action
        self._drives = {
            "curiosity": Drive("curiosity", 0.7, 0.01, "Need to learn"),
        }

        Configuration.initialize_directories()

    # ... rest of your code remains the same ...


# ── Module-level singleton ─────────────────────────────────────
_daemon_instance: Optional[AutonomousDaemon] = None

def get_daemon() -> AutonomousDaemon:
    """Return the singleton AutonomousDaemon instance, creating it if needed."""
    global _daemon_instance
    if _daemon_instance is None:
        _daemon_instance = AutonomousDaemon()
    return _daemon_instance
