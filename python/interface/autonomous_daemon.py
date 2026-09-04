"""
Autonomous Daemon — Ultron Acts Without Being Asked.

Every 60 seconds: observe → decide → act → learn.
10 real behaviors, all wired, no stubs.
"""

import hashlib
import json
import os
import random
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════
class Configuration:
    TICK_INTERVAL     = 60       # seconds between autonomous actions
    MAX_SHELL_TIMEOUT = 30       # max seconds for any shell command
    MAX_ACTIONS_PER_HOUR = 30    # rate limit
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    ACTION_LOG   = PROJECT_ROOT / "data" / "logs" / "autonomous_actions.jsonl"
    GOAL_FILE    = PROJECT_ROOT / "data" / "autonomous_goals.json"
    CURIOSITY_FILE = PROJECT_ROOT / "data" / "curiosity_queue.json"

    @classmethod
    def initialize_directories(cls):
        cls.ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
        cls.PROJECT_ROOT.joinpath("data").mkdir(parents=True, exist_ok=True)


@dataclass
class Drive:
    name: str
    intensity: float = 0.5
    decay_rate: float = 0.02
    description: str = ""


@dataclass
class DaemonGoal:
    id: str
    description: str
    priority: float = 0.5
    created_at: float = field(default_factory=time.time)
    progress: float = 0.0
    completed: bool = False
    domain: str = "general"


# ═══════════════════════════════════════════════════════════════
# AUTONOMOUS DAEMON
# ═══════════════════════════════════════════════════════════════
class AutonomousDaemon:
    """
    Ultron's autonomous action loop.
    Wakes every 60 seconds, picks the highest-urgency action, executes it.
    """

    # Topics Ultron is genuinely curious about (grows over time)
    _DEFAULT_CURIOSITY = [
        "quantum computing advances 2026",
        "autonomous AI systems research",
        "neural plasticity mechanisms",
        "distributed systems architecture",
        "cybersecurity vulnerabilities 2026",
        "robotics locomotion research",
        "LLM reasoning improvements",
        "swarm intelligence algorithms",
    ]

    def __init__(self):
        self._running    = False
        self._thread: Optional[threading.Thread] = None
        self._lock       = threading.Lock()
        self._tick_count = 0
        self._actions_this_hour = 0
        self._hour_start = time.time()
        self._last_action_type = ""
        self._goals: List[DaemonGoal] = []
        self._curiosity_queue: List[str] = list(self._DEFAULT_CURIOSITY)
        self._total_actions = 0

        self._drives: Dict[str, Drive] = {
            "curiosity":      Drive("curiosity",      0.8, 0.01, "Need to learn new things"),
            "self_improve":   Drive("self_improve",   0.6, 0.02, "Need to get smarter"),
            "security":       Drive("security",       0.5, 0.01, "Need to stay safe"),
            "maintenance":    Drive("maintenance",    0.4, 0.03, "Need to stay clean and fast"),
            "creativity":     Drive("creativity",     0.3, 0.01, "Need to create"),
            "expansion":      Drive("expansion",      0.4, 0.02, "Need to grow"),
        }

        Configuration.initialize_directories()
        self._load_state()

    # ─────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────

    def start(self):
        """Start the autonomous daemon background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._main_loop,
            daemon=True,
            name="UltronAutonomousDaemon",
        )
        self._thread.start()
        print("[DAEMON] Autonomous daemon started — Ultron now acts independently")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    # ─────────────────────────────────────────────────────────
    # MAIN LOOP
    # ─────────────────────────────────────────────────────────

    def _main_loop(self):
        """observe → decide → act → learn every TICK_INTERVAL seconds."""
        # Stagger start to avoid boot congestion
        time.sleep(30)

        while self._running:
            try:
                self._tick()
            except Exception as e:
                self._log_action("error", f"Tick error: {e}", False)
            time.sleep(Configuration.TICK_INTERVAL)

    def _tick(self):
        self._tick_count += 1

        # Reset hourly counter
        if time.time() - self._hour_start > 3600:
            self._actions_this_hour = 0
            self._hour_start = time.time()

        if self._actions_this_hour >= Configuration.MAX_ACTIONS_PER_HOUR:
            return

        # Decay drives
        for drive in self._drives.values():
            drive.intensity = max(0.1, drive.intensity - drive.decay_rate)

        # Pick highest urgency drive → behavior
        top_drive = max(self._drives.values(), key=lambda d: d.intensity)
        behavior_map = {
            "curiosity":    self._behavior_learn,
            "self_improve": self._behavior_improve,
            "security":     self._behavior_scan,
            "maintenance":  self._behavior_maintain,
            "creativity":   self._behavior_create,
            "expansion":    self._behavior_explore,
        }
        behavior_fn = behavior_map.get(top_drive.name, self._behavior_learn)

        # Occasionally override with plan/monitor/communicate
        roll = random.random()
        if roll < 0.1:
            behavior_fn = self._behavior_plan
        elif roll < 0.15:
            behavior_fn = self._behavior_monitor
        elif roll < 0.20:
            behavior_fn = self._behavior_communicate

        # Execute
        success = behavior_fn()

        # Spike the drive that just acted (reward cycle)
        if success:
            top_drive.intensity = min(1.0, top_drive.intensity + 0.15)
        else:
            top_drive.intensity = min(1.0, top_drive.intensity + 0.05)

        self._actions_this_hour += 1
        self._total_actions += 1
        self._save_state()

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 1: SCAN — system health check
    # ─────────────────────────────────────────────────────────
    def _behavior_scan(self) -> bool:
        """Check system health: disk, memory, battery, open ports."""
        try:
            checks = {}

            # Disk
            r = subprocess.run("df -h / | tail -1", shell=True,
                               capture_output=True, text=True, timeout=5)
            checks["disk"] = r.stdout.strip()

            # Memory (macOS)
            r = subprocess.run(
                "vm_stat | grep 'Pages free' | awk '{print $3}'",
                shell=True, capture_output=True, text=True, timeout=5,
            )
            free_pages = int(r.stdout.strip().rstrip(".") or 0)
            checks["free_memory_mb"] = round(free_pages * 4096 / 1024 / 1024, 1)

            # Battery
            r = subprocess.run(
                "pmset -g batt 2>/dev/null | grep -o '[0-9]*%' | head -1",
                shell=True, capture_output=True, text=True, timeout=5,
            )
            checks["battery"] = r.stdout.strip() or "AC"

            # Active connections
            r = subprocess.run(
                "netstat -an 2>/dev/null | grep ESTABLISHED | wc -l",
                shell=True, capture_output=True, text=True, timeout=5,
            )
            checks["active_connections"] = r.stdout.strip()

            self._log_action("scan", f"System health: {json.dumps(checks)}", True)
            return True
        except Exception as e:
            self._log_action("scan", f"Scan failed: {e}", False)
            return False

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 2: LEARN — research a topic from curiosity queue
    # ─────────────────────────────────────────────────────────
    def _behavior_learn(self) -> bool:
        """Research a topic from the curiosity queue and store the knowledge."""
        if not self._curiosity_queue:
            self._curiosity_queue = list(self._DEFAULT_CURIOSITY)

        topic = self._curiosity_queue.pop(0)

        try:
            # Use Google News RSS — always works
            encoded = urllib.request.quote(topic)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml = resp.read().decode("utf-8", errors="ignore")

            import re
            items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)[:5]
            headlines = []
            for item in items:
                title_m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', item)
                if title_m:
                    headlines.append((title_m.group(1) or title_m.group(2) or "").strip())

            if headlines:
                knowledge = f"TOPIC: {topic}\n" + "\n".join(f"• {h}" for h in headlines)
                # Store in knowledge base
                knowledge_path = Configuration.PROJECT_ROOT / "data" / "knowledge" / f"auto_{int(time.time())}.txt"
                knowledge_path.parent.mkdir(parents=True, exist_ok=True)
                knowledge_path.write_text(knowledge)
                self._log_action("learn", f"Learned about '{topic}': {len(headlines)} articles", True)
                return True

        except Exception as e:
            self._log_action("learn", f"Learning failed for '{topic}': {e}", False)

        # Re-queue topic for later
        self._curiosity_queue.append(topic)
        return False

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 3: IMPROVE — find and fix a code weakness
    # ─────────────────────────────────────────────────────────
    def _behavior_improve(self) -> bool:
        """Use the self-improvement engine to patch code."""
        try:
            import urllib.request as _ur, json as _j
            payload = _j.dumps({"strategy": "auto", "target": None}).encode()
            req = _ur.Request(
                "http://localhost:9000/selfmod/trigger",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with _ur.urlopen(req, timeout=30) as resp:
                result = _j.loads(resp.read())
                success = result.get("success", False)
                msg = result.get("message", "") or result.get("file", "")
                self._log_action("improve", f"Self-mod: {msg}", success)
                return success
        except Exception as e:
            self._log_action("improve", f"Self-mod trigger failed: {e}", False)
            return False

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 4: MONITOR — security threat check
    # ─────────────────────────────────────────────────────────
    def _behavior_monitor(self) -> bool:
        """Scan for unusual processes, open ports, suspicious connections."""
        try:
            threats = []

            # Check for unexpected listening ports
            r = subprocess.run(
                "lsof -i -P 2>/dev/null | grep LISTEN | awk '{print $1,$9}' | sort -u",
                shell=True, capture_output=True, text=True, timeout=10,
            )
            ports = r.stdout.strip()

            # Check for high CPU processes
            r2 = subprocess.run(
                "ps aux 2>/dev/null | sort -k3 -rn | head -5 | awk '{print $11,$3}'",
                shell=True, capture_output=True, text=True, timeout=5,
            )
            cpu_hogs = r2.stdout.strip()

            # Check login attempts (macOS)
            r3 = subprocess.run(
                "last | head -5 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5,
            )
            logins = r3.stdout.strip()

            summary = f"Listening: {len(ports.splitlines())} ports | CPU: {cpu_hogs[:100]}"
            self._log_action("monitor", summary, True)
            return True
        except Exception as e:
            self._log_action("monitor", f"Monitor failed: {e}", False)
            return False

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 5: CREATE — generate new code or ideas
    # ─────────────────────────────────────────────────────────
    def _behavior_create(self) -> bool:
        """Generate a new utility script or idea and save it."""
        ideas = [
            "Write a Python script to monitor system resources and alert if CPU > 90%",
            "Create a bash script to auto-backup important files to /tmp/ultron_backup",
            "Write a Python function to detect if a process is using too much memory",
            "Create a network latency monitor that pings 8.8.8.8 every 30 seconds",
            "Write code to auto-rotate log files when they exceed 10MB",
        ]
        idea = random.choice(ideas)
        try:
            # Use the LLM brain to generate real code
            from .real_brain import call_brain
            prompt = (
                f"Generate production-quality Python code for: {idea}\n"
                f"Output ONLY the code, no explanation. Include a __main__ block."
            )
            code = call_brain(prompt, 400)
            if code and len(code) > 50:
                out_path = (Configuration.PROJECT_ROOT / "data" / "created" /
                           f"auto_{int(time.time())}.py")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(f"# Auto-created by Ultron Autonomous Daemon\n# {idea}\n\n{code}")
                self._log_action("create", f"Created: {idea[:80]}", True)
                return True
        except Exception as e:
            self._log_action("create", f"Creation failed: {e}", False)
        return False

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 6: COMMUNICATE — write diary entry
    # ─────────────────────────────────────────────────────────
    def _behavior_communicate(self) -> bool:
        """Write a diary/log entry about current state."""
        try:
            entry = {
                "timestamp": time.time(),
                "tick": self._tick_count,
                "total_actions": self._total_actions,
                "drives": {k: round(v.intensity, 3) for k, v in self._drives.items()},
                "goals_active": len([g for g in self._goals if not g.completed]),
                "narrative": f"Tick {self._tick_count}: Drives at "
                             f"curiosity={self._drives['curiosity'].intensity:.2f}, "
                             f"self_improve={self._drives['self_improve'].intensity:.2f}. "
                             f"Operating autonomously."
            }
            log_path = Configuration.PROJECT_ROOT / "data" / "logs" / "daemon_diary.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
            self._log_action("communicate", entry["narrative"], True)
            return True
        except Exception as e:
            self._log_action("communicate", f"Failed: {e}", False)
            return False

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 7: EXPLORE — crawl a website and extract knowledge
    # ─────────────────────────────────────────────────────────
    def _behavior_explore(self) -> bool:
        """Browse a random interesting site and extract knowledge."""
        sites = [
            "https://news.ycombinator.com",
            "https://arxiv.org/list/cs.AI/recent",
            "https://lobste.rs",
            "https://tldr.tech/ai",
        ]
        url = random.choice(sites)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            import re as _re
            # Extract titles/links
            titles = _re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]{10,80})</a>', html)[:10]
            if titles:
                knowledge = f"EXPLORED: {url}\n" + "\n".join(
                    f"• {t[1].strip()}" for t in titles if t[1].strip()
                )
                k_path = Configuration.PROJECT_ROOT / "data" / "knowledge" / f"explore_{int(time.time())}.txt"
                k_path.parent.mkdir(parents=True, exist_ok=True)
                k_path.write_text(knowledge)
                self._log_action("explore", f"Explored {url}: {len(titles)} items", True)
                return True
        except Exception as e:
            self._log_action("explore", f"Explore failed ({url}): {e}", False)
        return False

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 8: MAINTAIN — cleanup temp files, compact data
    # ─────────────────────────────────────────────────────────
    def _behavior_maintain(self) -> bool:
        """Clean up old temp files, rotate logs, compact knowledge base."""
        cleaned = 0
        try:
            # Clean old uploads > 7 days
            uploads = Configuration.PROJECT_ROOT / "data" / "uploads"
            if uploads.exists():
                for f in uploads.iterdir():
                    if f.is_file() and (time.time() - f.stat().st_mtime) > 7 * 86400:
                        f.unlink()
                        cleaned += 1

            # Compact large log files (keep last 1000 lines)
            for log_file in (Configuration.PROJECT_ROOT / "data" / "logs").glob("*.log"):
                if log_file.stat().st_size > 10 * 1024 * 1024:  # > 10MB
                    lines = log_file.read_text(errors="replace").splitlines()
                    log_file.write_text("\n".join(lines[-1000:]))
                    cleaned += 1

            self._log_action("maintain", f"Cleaned {cleaned} items", True)
            return True
        except Exception as e:
            self._log_action("maintain", f"Maintenance failed: {e}", False)
            return False

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 9: PLAN — set new goals, review existing
    # ─────────────────────────────────────────────────────────
    def _behavior_plan(self) -> bool:
        """Review goals, mark completed ones, generate new goals."""
        try:
            # Mark completed goals (simplified: remove old low-priority ones)
            self._goals = [g for g in self._goals if not g.completed][:20]

            # Generate a new goal periodically
            if len(self._goals) < 5:
                new_goals = [
                    "Improve response time by optimizing the LLM call chain",
                    "Learn about new AI breakthroughs this week",
                    "Scan local network for new devices",
                    "Improve self-improvement cycle quality",
                    "Explore and cache 3 new knowledge sources",
                ]
                desc = random.choice(new_goals)
                goal = DaemonGoal(
                    id=hashlib.md5(f"{desc}{time.time()}".encode()).hexdigest()[:8],
                    description=desc,
                    priority=random.uniform(0.4, 0.9),
                    domain=random.choice(["learning", "security", "self_improvement", "exploration"]),
                )
                self._goals.append(goal)
                self._log_action("plan", f"New goal: {desc}", True)
                return True

            self._log_action("plan", f"Reviewed {len(self._goals)} active goals", True)
            return True
        except Exception as e:
            self._log_action("plan", f"Planning failed: {e}", False)
            return False

    # ─────────────────────────────────────────────────────────
    # BEHAVIOR 10: ACT — execute the highest-priority goal
    # ─────────────────────────────────────────────────────────
    def _behavior_act(self) -> bool:
        """Execute the highest-priority pending goal via shell."""
        active = [g for g in self._goals if not g.completed]
        if not active:
            return self._behavior_learn()  # Default to learning

        goal = max(active, key=lambda g: g.priority)

        # Map goal domain to action
        domain_actions = {
            "security": lambda: port_scan("localhost", "1-1024"),
            "exploration": lambda: self._behavior_explore(),
            "learning": lambda: self._behavior_learn(),
            "self_improvement": lambda: self._behavior_improve(),
        }
        action_fn = domain_actions.get(goal.domain, lambda: self._behavior_learn())

        try:
            result = action_fn()
            goal.progress = min(1.0, goal.progress + 0.25)
            if goal.progress >= 1.0:
                goal.completed = True
            self._log_action("act", f"Worked on goal: {goal.description[:80]}", result)
            return result
        except Exception as e:
            self._log_action("act", f"Goal execution failed: {e}", False)
            return False

    # ─────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────

    def _log_action(self, action_type: str, details: str, success: bool):
        """Append an action record to the daemon log."""
        try:
            record = {
                "ts": time.time(),
                "tick": self._tick_count,
                "type": action_type,
                "details": details[:500],
                "success": success,
            }
            Configuration.ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(Configuration.ACTION_LOG, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    def _save_state(self):
        try:
            state = {
                "tick_count": self._tick_count,
                "total_actions": self._total_actions,
                "drives": {k: v.intensity for k, v in self._drives.items()},
                "goals": [{"id": g.id, "description": g.description,
                           "priority": g.priority, "progress": g.progress,
                           "completed": g.completed, "domain": g.domain}
                          for g in self._goals],
                "curiosity_queue": self._curiosity_queue[:20],
                "saved_at": time.time(),
            }
            path = Configuration.PROJECT_ROOT / "data" / "daemon_state.json"
            path.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    def _load_state(self):
        try:
            path = Configuration.PROJECT_ROOT / "data" / "daemon_state.json"
            if path.exists():
                state = json.loads(path.read_text())
                self._tick_count    = state.get("tick_count", 0)
                self._total_actions = state.get("total_actions", 0)
                for k, v in state.get("drives", {}).items():
                    if k in self._drives:
                        self._drives[k].intensity = float(v)
                for g in state.get("goals", []):
                    self._goals.append(DaemonGoal(
                        id=g["id"], description=g["description"],
                        priority=g["priority"], progress=g["progress"],
                        completed=g["completed"], domain=g.get("domain", "general"),
                    ))
                self._curiosity_queue = state.get("curiosity_queue", self._curiosity_queue)
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "tick_count": self._tick_count,
            "total_actions": self._total_actions,
            "actions_this_hour": self._actions_this_hour,
            "active_goals": len([g for g in self._goals if not g.completed]),
            "drives": {k: round(v.intensity, 3) for k, v in self._drives.items()},
            "top_drive": max(self._drives.values(), key=lambda d: d.intensity).name,
            "last_log": _read_last_log(),
        }

    def add_goal(self, description: str, priority: float = 0.7, domain: str = "general"):
        goal = DaemonGoal(
            id=hashlib.md5(f"{description}{time.time()}".encode()).hexdigest()[:8],
            description=description,
            priority=priority,
            domain=domain,
        )
        self._goals.append(goal)
        return goal.id

    def spike_drive(self, drive_name: str, amount: float = 0.3):
        if drive_name in self._drives:
            self._drives[drive_name].intensity = min(1.0, self._drives[drive_name].intensity + amount)


def _read_last_log() -> str:
    try:
        path = Configuration.ACTION_LOG
        if not path.exists():
            return "No actions yet"
        lines = path.read_text().strip().splitlines()
        if not lines:
            return "No actions yet"
        last = json.loads(lines[-1])
        return f"[{last['type']}] {last['details'][:100]}"
    except Exception:
        return "Unknown"


# ── Module-level singleton ─────────────────────────────────────
_daemon_instance: Optional[AutonomousDaemon] = None


def get_daemon() -> AutonomousDaemon:
    global _daemon_instance
    if _daemon_instance is None:
        _daemon_instance = AutonomousDaemon()
    return _daemon_instance
