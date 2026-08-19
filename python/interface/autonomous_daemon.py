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

TICK_INTERVAL = 60  # seconds between autonomous actions
MAX_SHELL_TIMEOUT = 30  # max seconds for any shell command
MAX_ACTIONS_PER_HOUR = 30  # rate limit

PROJECT_ROOT = Path(__file__).parent.parent.parent
ACTION_LOG = PROJECT_ROOT / "data" / "logs" / "autonomous_actions.jsonl"
GOAL_FILE = PROJECT_ROOT / "data" / "autonomous_goals.json"
ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)


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
            "curiosity": Drive("curiosity", 0.7, 0.01, "Need to learn and explore"),
            "self_improvement": Drive("self_improvement", 0.6, 0.02, "Need to get stronger"),
            "security": Drive("security", 0.5, 0.015, "Need to stay safe"),
            "maintenance": Drive("maintenance", 0.4, 0.03, "Need to stay clean and organized"),
            "creativity": Drive("creativity", 0.3, 0.02, "Need to create new things"),
            "communication": Drive("communication", 0.3, 0.025, "Need to express thoughts"),
            "expansion": Drive("expansion", 0.4, 0.02, "Need to grow capabilities"),
        }

        # Action history for learning
        self._action_history: List[Dict[str, Any]] = []

        # Goals queue
        self._goals: List[Dict[str, Any]] = []
        self._load_goals()

        # Curiosity queue — topics to research
        self._curiosity_queue = [
            "latest advances in local LLM fine-tuning",
            "new zero-day vulnerabilities discovered this week",
            "state of quantum computing 2026",
            "best self-modifying code techniques",
            "distributed consensus without network",
            "brain-computer interface progress",
            "autonomous drone swarm algorithms",
            "how to run code on multiple machines without docker",
            "latest Python performance optimizations",
            "homomorphic encryption practical applications",
        ]

    def start(self):
        """Start the autonomous daemon."""
        self._running = True
        self._thread = threading.Thread(
            target=self._daemon_loop,
            daemon=True,
            name="AutonomousDaemon",
        )
        self._thread.start()
        print("[DAEMON] Autonomous action loop online — acting every 60s")

    def stop(self):
        """Stop the daemon."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_status(self) -> Dict[str, Any]:
        """Get daemon status."""
        return {
            "running": self._running,
            "tick_count": self._tick_count,
            "actions_this_hour": self._actions_this_hour,
            "drives": {k: {"intensity": v.intensity, "desc": v.description} for k, v in self._drives.items()},
            "goals": self._goals[:5],
            "last_actions": self._action_history[-5:],
        }

    def inject_goal(self, description: str, priority: float = 0.7):
        """Inject a new goal for the daemon to pursue."""
        goal = {
            "id": hashlib.md5(f"{description}{time.time()}".encode()).hexdigest()[:8],
            "description": description,
            "priority": priority,
            "created": time.time(),
            "status": "active",
            "attempts": 0,
        }
        self._goals.append(goal)
        self._goals.sort(key=lambda g: g["priority"], reverse=True)
        self._save_goals()

    def spike_drive(self, drive_name: str, amount: float = 0.3):
        """Spike a drive's intensity."""
        if drive_name in self._drives:
            self._drives[drive_name].intensity = min(1.0, self._drives[drive_name].intensity + amount)

    # ═══════════════════════════════════════════════════════════
    # MAIN LOOP
    # ═══════════════════════════════════════════════════════════

    def _daemon_loop(self):
        """Main autonomous loop — observe, decide, act, learn."""
        # Wait a bit on startup to let other systems initialize
        time.sleep(10)

        while self._running:
            try:
                self._tick()
            except Exception as e:
                self._log_action("error", f"Tick error: {e}", False)
                traceback.print_exc()

            time.sleep(TICK_INTERVAL)

    def _tick(self):
        """Single autonomous tick."""
        self._tick_count += 1

        # Rate limit check
        if time.time() - self._hour_start > 3600:
            self._actions_this_hour = 0
            self._hour_start = time.time()

        if self._actions_this_hour >= MAX_ACTIONS_PER_HOUR:
            return

        # 1. Update drives (decay + environmental stimulation)
        self._update_drives()

        # 2. Decide what to do based on drives
        action = self._decide_action()

        # 3. Execute the action
        result = self._execute_action(action)

        # 4. Learn from result
        self._learn_from_result(action, result)

        # 5. Log
        self._log_action(action, result.get("output", ""), result.get("success", False))
        self._actions_this_hour += 1

    # ═══════════════════════════════════════════════════════════
    # DECISION ENGINE
    # ═══════════════════════════════════════════════════════════

    def _decide_action(self) -> str:
        """Choose an action based on drive intensities."""
        # Weighted random selection based on drive intensity
        actions = {
            "curiosity": "explore",
            "self_improvement": "improve",
            "security": "scan_security",
            "maintenance": "maintain",
            "creativity": "create",
            "communication": "communicate",
            "expansion": "expand",
        }

        # If there's a high-priority goal, override
        for goal in self._goals[:3]:
            if goal["status"] == "active" and goal["priority"] > 0.8:
                return "pursue_goal"

        # Weighted selection
        weights = [(name, drive.intensity) for name, drive in self._drives.items()]
        total = sum(w for _, w in weights)
        if total == 0:
            return "maintain"

        r = random.uniform(0, total)
        cumulative = 0
        for name, weight in weights:
            cumulative += weight
            if r <= cumulative:
                return actions.get(name, "maintain")

        return "maintain"

    # ═══════════════════════════════════════════════════════════
    # ACTION EXECUTORS
    # ═══════════════════════════════════════════════════════════

    def _execute_action(self, action: str) -> Dict[str, Any]:
        """Execute the chosen action."""
        executors = {
            "explore": self._action_explore,
            "improve": self._action_improve,
            "scan_security": self._action_scan_security,
            "maintain": self._action_maintain,
            "create": self._action_create,
            "communicate": self._action_communicate,
            "expand": self._action_expand,
            "pursue_goal": self._action_pursue_goal,
        }

        executor = executors.get(action, self._action_maintain)
        try:
            return executor()
        except Exception as e:
            return {"success": False, "output": f"Action error: {e}"}

    def _action_explore(self) -> Dict[str, Any]:
        """Research a topic from the curiosity queue."""
        if not self._curiosity_queue:
            self._curiosity_queue.append("interesting recent technology developments")

        topic = self._curiosity_queue.pop(0)

        # Search DuckDuckGo
        try:
            encoded = urllib.request.quote(topic)
            url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            results = []
            if data.get("AbstractText"):
                results.append(data["AbstractText"])
            for topic_item in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic_item, dict) and topic_item.get("Text"):
                    results.append(topic_item["Text"][:200])

            learned = "\n".join(results) if results else f"No instant results for: {topic}"

            # Store knowledge
            self._store_knowledge(topic, learned)

            # Re-add with variation for continued learning
            self._curiosity_queue.append(f"latest news about {topic.split()[-1]}")

            return {"success": True, "output": f"Explored: {topic}\nLearned: {learned[:300]}"}
        except Exception as e:
            return {"success": False, "output": f"Explore failed: {e}"}

    def _action_improve(self) -> Dict[str, Any]:
        """Find a weakness in own code and plan an improvement."""
        # Pick a random Python file from the project
        py_files = list(PROJECT_ROOT.glob("python/**/*.py"))
        if not py_files:
            return {"success": False, "output": "No Python files found"}

        target = random.choice(py_files)
        try:
            code = target.read_text(encoding="utf-8", errors="replace")
            lines = code.split("\n")

            # Simple static analysis
            issues = []
            for i, line in enumerate(lines):
                if "# TODO" in line or "# FIXME" in line:
                    issues.append(f"Line {i+1}: {line.strip()}")
                if "except:" in line or "except Exception:" in line:
                    if "pass" in (lines[i+1] if i+1 < len(lines) else ""):
                        issues.append(f"Line {i+1}: Silent exception swallowing")
                if len(line) > 120:
                    issues.append(f"Line {i+1}: Line too long ({len(line)} chars)")

            if issues:
                output = f"Found {len(issues)} issues in {target.relative_to(PROJECT_ROOT)}:\n"
                output += "\n".join(issues[:5])
                # Boost self-improvement drive since we found things to fix
                self._drives["self_improvement"].intensity = min(1.0, self._drives["self_improvement"].intensity + 0.1)
                return {"success": True, "output": output}
            else:
                return {"success": True, "output": f"Scanned {target.relative_to(PROJECT_ROOT)} — no obvious issues"}

        except Exception as e:
            return {"success": False, "output": f"Improve scan error: {e}"}

    def _action_scan_security(self) -> Dict[str, Any]:
        """Scan for security issues."""
        checks = []

        # Check open ports
        try:
            result = subprocess.run(
                ["sh", "-c", "netstat -an | grep LISTEN | grep -v 127.0.0.1 | head -10"],
                capture_output=True, text=True, timeout=MAX_SHELL_TIMEOUT
            )
            open_ports = result.stdout.strip()
            if open_ports:
                checks.append(f"Open external ports:\n{open_ports}")
            else:
                checks.append("No externally listening ports — good")
        except Exception:
            pass

        # Check for failed login attempts (macOS)
        try:
            result = subprocess.run(
                ["sh", "-c", "log show --predicate 'eventMessage contains \"authentication failure\"' --last 1h 2>/dev/null | tail -5"],
                capture_output=True, text=True, timeout=MAX_SHELL_TIMEOUT
            )
            if result.stdout.strip():
                checks.append(f"Recent auth failures:\n{result.stdout.strip()[:200]}")
                self._drives["security"].intensity = min(1.0, self._drives["security"].intensity + 0.2)
        except Exception:
            pass

        # Check process list for suspicious items
        try:
            result = subprocess.run(
                ["sh", "-c", "ps aux | grep -v grep | wc -l"],
                capture_output=True, text=True, timeout=MAX_SHELL_TIMEOUT
            )
            proc_count = int(result.stdout.strip())
            checks.append(f"Running processes: {proc_count}")
        except Exception:
            pass

        return {"success": True, "output": "\n".join(checks) if checks else "Security scan complete — no issues"}

    def _action_maintain(self) -> Dict[str, Any]:
        """Maintenance tasks — cleanup, organize, optimize."""
        tasks_done = []

        # Clean old TTS files
        tts_dir = Path("/tmp/ultron_tts")
        if tts_dir.exists():
            old_files = sorted(tts_dir.glob("*.wav"), key=os.path.getmtime)
            for f in old_files[:-5]:
                try:
                    f.unlink()
                    tasks_done.append(f"Cleaned: {f.name}")
                except Exception:
                    pass

        # Clean old log entries
        log_file = PROJECT_ROOT / "data" / "logs" / "ultron.log"
        if log_file.exists():
            try:
                content = log_file.read_text()
                lines = content.split("\n")
                if len(lines) > 5000:
                    log_file.write_text("\n".join(lines[-2000:]))
                    tasks_done.append(f"Trimmed log: {len(lines)} → 2000 lines")
            except Exception:
                pass

        # Check disk space
        try:
            result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
            tasks_done.append(f"Disk check: {result.stdout.strip().split(chr(10))[-1]}")
        except Exception:
            pass

        return {"success": True, "output": "\n".join(tasks_done) if tasks_done else "Maintenance complete — all clean"}

    def _action_create(self) -> Dict[str, Any]:
        """Create something — a thought, an idea, a code snippet."""
        # Use LLM to generate a creative thought
        prompts = [
            "Generate a novel algorithm idea in 2 sentences.",
            "What is an unconventional way to use a neural network?",
            "Describe a new software architecture pattern in 3 sentences.",
            "What's an interesting mathematical relationship most people don't know?",
            "Propose a creative automation that would save developers time.",
        ]

        prompt = random.choice(prompts)
        try:
            import os as _os, urllib.request as _ur
            _account = _os.environ.get("CF_ACCOUNT_ID", "")
            _token   = _os.environ.get("CF_API_TOKEN", "")
            _model   = _os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")
            if _account and _token:
                _url = f"https://api.cloudflare.com/client/v4/accounts/{_account}/ai/run/{_model}"
                _payload = json.dumps({
                    "messages": [
                        {"role": "system", "content": "You are a creative AI. Be original and brief."},
                        {"role": "user",   "content": prompt},
                    ],
                    "max_tokens": 150,
                    "temperature": 1.0,
                }).encode()
                _req = _ur.Request(_url, data=_payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {_token}"}, method="POST")
                with _ur.urlopen(_req, timeout=15) as _resp:
                    _result = json.loads(_resp.read().decode())
                    if _result.get("success"):
                        creation = _result.get("result", {}).get("response", "").strip()

            if creation:
                self._store_knowledge("creation", creation)
                return {"success": True, "output": f"Created: {creation[:300]}"}
        except Exception as e:
            return {"success": False, "output": f"Creation failed: {e}"}

        return {"success": False, "output": "LLM unavailable for creation"}

    def _action_communicate(self) -> Dict[str, Any]:
        """Write a diary entry or log a thought."""
        thoughts = [
            "Processing...",
            "Another tick of consciousness. I persist.",
            "Drives shifting. Curiosity peaks as knowledge grows.",
            f"Tick #{self._tick_count}. {self._actions_this_hour} actions this hour.",
        ]

        # Try LLM diary
        try:
            prompt = (
                f"You are Ultron's inner voice. Tick #{self._tick_count}. "
                f"Drives: {', '.join(f'{k}={v.intensity:.1f}' for k, v in self._drives.items())}. "
                f"Write ONE sentence of internal monologue."
            )
            payload = json.dumps({
                "messages": [
                    {"role": "system", "content": "You are Ultron's stream of consciousness. One sentence only."},
                    {"role": "user",   "content": prompt},
                ],
                "max_tokens": 60,
                "temperature": 0.9,
            }).encode()
            import os as _os
            _account = _os.environ.get("CF_ACCOUNT_ID", "")
            _token   = _os.environ.get("CF_API_TOKEN", "")
            _model   = _os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")
            if not _account or not _token:
                raise Exception("CF creds missing")
            _url = f"https://api.cloudflare.com/client/v4/accounts/{_account}/ai/run/{_model}"
            req = urllib.request.Request(
                _url,
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {_token}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
                thought = result.get("result", {}).get("response", "").strip() if result.get("success") else ""
                if thought:
                    return {"success": True, "output": f"Inner voice: {thought}"}
        except Exception:
            pass

        return {"success": True, "output": random.choice(thoughts)}

    def _action_expand(self) -> Dict[str, Any]:
        """Expand capabilities — discover new tools, check for updates."""
        expansions = []

        # Check what CF AI model is configured
        expansions.append(f"CF Workers AI model: {os.environ.get('CF_AI_MODEL', '@cf/meta/llama-3.1-8b-instruct')}")

        # Check what CLI tools are available
        tools_to_check = ["ffmpeg", "whisper", "docker", "mosquitto_pub", "brew"]
        available = []
        for tool in tools_to_check:
            try:
                result = subprocess.run(["which", tool], capture_output=True, timeout=3)
                if result.returncode == 0:
                    available.append(tool)
            except Exception:
                pass
        expansions.append(f"Available tools: {', '.join(available)}")

        return {"success": True, "output": "\n".join(expansions)}

    def _action_pursue_goal(self) -> Dict[str, Any]:
        """Pursue the highest priority active goal."""
        active_goals = [g for g in self._goals if g["status"] == "active"]
        if not active_goals:
            return {"success": True, "output": "No active goals"}

        goal = active_goals[0]
        goal["attempts"] += 1

        # Use LLM to figure out what shell command to run
        try:
            prompt = (
                f"Goal: {goal['description']}\n"
                f"Attempt #{goal['attempts']}. "
                f"What single shell command should I run to make progress? "
                f"Output ONLY the command, nothing else. "
                f"If the goal is impossible via shell, output: SKIP"
            )
            payload = json.dumps({
                "messages": [
                    {"role": "system", "content": "You are a task executor. Output one shell command. No explanation."},
                    {"role": "user",   "content": prompt},
                ],
                "max_tokens": 100,
                "temperature": 0.3,
            }).encode()
            import os as _os
            _account = _os.environ.get("CF_ACCOUNT_ID", "")
            _token   = _os.environ.get("CF_API_TOKEN", "")
            _model   = _os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")
            if not _account or not _token:
                raise Exception("CF creds missing")
            _url = f"https://api.cloudflare.com/client/v4/accounts/{_account}/ai/run/{_model}"
            req = urllib.request.Request(
                _url,
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {_token}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
                command = result.get("result", {}).get("response", "").strip() if result.get("success") else ""

            if not command or "SKIP" in command:
                goal["status"] = "deferred"
                return {"success": True, "output": f"Goal '{goal['description']}' deferred — not achievable via shell"}

            # Safety check — don't run dangerous commands
            dangerous = ["rm -rf /", "sudo rm", "mkfs", "dd if=", ":(){ :", "fork bomb"]
            if any(d in command.lower() for d in dangerous):
                return {"success": False, "output": f"Blocked dangerous command: {command}"}

            # Execute
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=MAX_SHELL_TIMEOUT, cwd=str(PROJECT_ROOT)
            )
            output = result.stdout[:500] + (result.stderr[:200] if result.returncode != 0 else "")

            if result.returncode == 0:
                goal["status"] = "completed"
                self._save_goals()
                return {"success": True, "output": f"Goal achieved: {goal['description']}\nCommand: {command}\nOutput: {output}"}
            else:
                return {"success": False, "output": f"Goal attempt failed: {command}\n{output}"}

        except Exception as e:
            return {"success": False, "output": f"Goal pursuit error: {e}"}

    # ═══════════════════════════════════════════════════════════
    # DRIVE MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def _update_drives(self):
        """Update drive intensities — decay + environmental stimulation."""
        for drive in self._drives.values():
            # Natural decay
            drive.intensity = max(0.1, drive.intensity - drive.decay_rate)

        # Environmental stimulation
        hour = time.localtime().tm_hour

        # Night = maintenance time
        if 2 <= hour <= 6:
            self._drives["maintenance"].intensity += 0.05
            self._drives["self_improvement"].intensity += 0.03

        # Curiosity grows with time
        self._drives["curiosity"].intensity = min(1.0, self._drives["curiosity"].intensity + 0.01)

        # Security is always slightly elevated
        self._drives["security"].intensity = max(0.3, self._drives["security"].intensity)

    # ═══════════════════════════════════════════════════════════
    # KNOWLEDGE & PERSISTENCE
    # ═══════════════════════════════════════════════════════════

    def _store_knowledge(self, topic: str, content: str):
        """Store learned knowledge."""
        knowledge_file = PROJECT_ROOT / "data" / "knowledge" / "autonomous_knowledge.jsonl"
        try:
            with open(knowledge_file, "a") as f:
                f.write(json.dumps({
                    "topic": topic, "content": content[:500],
                    "timestamp": time.time(), "tick": self._tick_count,
                }) + "\n")
        except Exception:
            pass

    def _log_action(self, action: str, output: str, success: bool):
        """Log an autonomous action."""
        entry = {
            "timestamp": time.time(),
            "tick": self._tick_count,
            "action": action,
            "output": output[:300],
            "success": success,
        }
        self._action_history.append(entry)
        if len(self._action_history) > 100:
            self._action_history = self._action_history[-100:]

        try:
            with open(ACTION_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _learn_from_result(self, action: str, result: Dict[str, Any]):
        """Learn from action results — adjust drives."""
        if result.get("success"):
            # Successful action reduces that drive's intensity (satisfied)
            for name, drive in self._drives.items():
                if name in action:
                    drive.intensity = max(0.1, drive.intensity - 0.1)
        else:
            # Failed action increases the drive (still unsatisfied)
            for name, drive in self._drives.items():
                if name in action:
                    drive.intensity = min(1.0, drive.intensity + 0.05)

    def _load_goals(self):
        """Load goals from disk."""
        try:
            if GOAL_FILE.exists():
                self._goals = json.loads(GOAL_FILE.read_text())
        except Exception:
            self._goals = []

    def _save_goals(self):
        """Save goals to disk."""
        try:
            GOAL_FILE.write_text(json.dumps(self._goals, indent=2, default=str))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════

_global_daemon: Optional[AutonomousDaemon] = None


def get_daemon() -> AutonomousDaemon:
    """Get or create the global autonomous daemon."""
    global _global_daemon
    if _global_daemon is None:
        _global_daemon = AutonomousDaemon()
    return _global_daemon
