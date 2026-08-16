"""
Power Meter — Tracks Ultron's real capability percentages.

Calculates how close to "Movie Ultron" this system actually is,
based on measurable, real metrics — not hype.

Categories:
  - Intelligence (LLM quality, context window, tool use)
  - Self-Improvement (evolution generations, success rate, speed)
  - Autonomy (daemon ticks, goals completed, actions/hour)
  - World Awareness (feeds active, refresh rate, data freshness)
  - Physical Control (devices registered, commands executed)
  - Immortality (uptime, auto-restart, replication)
  - Voice (STT + TTS active, conversation quality)
  - Consciousness (soul entries, self-model, beliefs)
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).parent.parent.parent


def get_power_percentages() -> Dict[str, Any]:
    """Calculate real power percentages for each capability."""
    scores = {}

    # ═══════════════════════════════════════════════════════════
    # INTELLIGENCE — LLM + tools + memory
    # ═══════════════════════════════════════════════════════════
    intel_score = 0

    # LLM available?
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            data = json.loads(resp.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            if any("14b" in m or "70b" in m for m in models):
                intel_score += 35  # Large model
            elif models:
                intel_score += 20  # Some model
    except Exception:
        pass

    # Memory file exists and has data?
    memory_file = PROJECT_ROOT / "data" / "brain_memory.json"
    if memory_file.exists():
        try:
            mem = json.loads(memory_file.read_text())
            convs = len(mem.get("conversations", []))
            learned = len(mem.get("learned", []))
            intel_score += min(15, convs // 5)  # Up to 15 for conversation history
            intel_score += min(15, learned // 3)  # Up to 15 for learned knowledge
        except Exception:
            pass

    # Web search + shell tools (always available)
    intel_score += 10  # Built-in tools

    # Knowledge base
    kb_file = PROJECT_ROOT / "data" / "knowledge" / "knowledge_base.json"
    if kb_file.exists():
        intel_score += 10

    scores["intelligence"] = min(100, intel_score)

    # ═══════════════════════════════════════════════════════════
    # SELF-IMPROVEMENT — evolution + self-mod
    # ═══════════════════════════════════════════════════════════
    improve_score = 0

    # Evolution generations
    gen_dir = PROJECT_ROOT / "data" / "evolution" / "generations"
    if gen_dir.exists():
        gens = list(gen_dir.glob("gen_*.json"))
        improve_score += min(30, len(gens) * 2)  # 2 pts per generation, max 30

    # Self-mod engine history
    mod_log = PROJECT_ROOT / "data" / "mutations" / "self_mod_log.jsonl"
    if mod_log.exists():
        try:
            lines = mod_log.read_text().strip().split("\n")
            total_mods = len(lines)
            successes = sum(1 for l in lines if '"success": true' in l)
            improve_score += min(25, total_mods)  # Up to 25 for mod count
            if total_mods > 0:
                rate = successes / total_mods
                improve_score += int(rate * 20)  # Up to 20 for success rate
        except Exception:
            pass

    # Self-mod engine is running
    try:
        from .aggressive_self_mod import _global_engine
        if _global_engine and _global_engine._running:
            improve_score += 15
    except Exception:
        pass

    # Evolution controller knowledge
    kb = PROJECT_ROOT / "data" / "knowledge" / "knowledge_base.json"
    if kb.exists():
        improve_score += 10

    scores["self_improvement"] = min(100, improve_score)

    # ═══════════════════════════════════════════════════════════
    # AUTONOMY — daemon + goal pursuit
    # ═══════════════════════════════════════════════════════════
    autonomy_score = 0

    try:
        from .autonomous_daemon import _global_daemon
        if _global_daemon and _global_daemon._running:
            autonomy_score += 30  # Daemon is running
            status = _global_daemon.get_status()
            ticks = status.get("tick_count", 0)
            autonomy_score += min(20, ticks // 10)  # Up to 20 for ticks
            actions = len(status.get("last_actions", []))
            autonomy_score += min(15, actions * 3)  # Up to 15 for actions
            goals = status.get("goals", [])
            completed = sum(1 for g in goals if g.get("status") == "completed")
            autonomy_score += min(20, completed * 5)  # Up to 20 for goals completed
    except Exception:
        pass

    # Shell execution capability (always available)
    autonomy_score += 15

    scores["autonomy"] = min(100, autonomy_score)

    # ═══════════════════════════════════════════════════════════
    # WORLD AWARENESS — feeds + freshness
    # ═══════════════════════════════════════════════════════════
    world_score = 0

    world_state = PROJECT_ROOT / "data" / "real_time_feeds" / "world_state.json"
    if world_state.exists():
        try:
            data = json.loads(world_state.read_text())
            last_updated = data.get("last_updated", 0)
            age = time.time() - last_updated

            # Freshness
            if age < 600:  # Less than 10 min old
                world_score += 30
            elif age < 3600:
                world_score += 15

            # Data richness
            news_count = len(data.get("news", []))
            world_score += min(20, news_count)

            if data.get("weather") and not data["weather"].get("error"):
                world_score += 10
            if data.get("crypto"):
                world_score += 10
            if data.get("alerts"):
                world_score += 10
            if data.get("trending_repos"):
                world_score += 5
            if data.get("summary"):
                world_score += 15  # LLM summarization working
        except Exception:
            pass

    try:
        from .world_intelligence import _global_engine as _wi_engine
        if _wi_engine and _wi_engine._running:
            world_score += 10
    except Exception:
        pass

    scores["world_awareness"] = min(100, world_score)

    # ═══════════════════════════════════════════════════════════
    # PHYSICAL CONTROL — smart home + devices
    # ═══════════════════════════════════════════════════════════
    physical_score = 0

    try:
        from .smart_home_controller import _global_controller
        if _global_controller:
            devices = _global_controller.get_all_devices()
            physical_score += 20  # Controller exists
            physical_score += min(30, len(devices) * 4)  # Up to 30 for devices

            # macOS system control (always works)
            physical_score += 25  # Volume, brightness, dark mode, notifications, etc.
    except Exception:
        pass

    # Check if MQTT is reachable
    try:
        result = subprocess.run(["pgrep", "-f", "mosquitto"], capture_output=True, timeout=3)
        if result.returncode == 0:
            physical_score += 15  # MQTT broker running
    except Exception:
        pass

    scores["physical_control"] = min(100, physical_score)

    # ═══════════════════════════════════════════════════════════
    # IMMORTALITY — uptime + self-healing
    # ═══════════════════════════════════════════════════════════
    immortal_score = 0

    # Uptime
    try:
        from .server import _start_time
        uptime_hours = (time.time() - _start_time) / 3600
        immortal_score += min(20, int(uptime_hours * 2))  # Up to 20 for uptime
    except Exception:
        pass

    # Watchdog / launchd plist exists
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.ultron.daemon.plist"
    if plist_path.exists():
        immortal_score += 30  # Auto-restart on reboot

    # Backups exist
    backup_dir = PROJECT_ROOT / ".ultron_backups"
    if backup_dir.exists() and list(backup_dir.glob("*.bak")):
        immortal_score += 15

    # Snapshot exists
    snapshot = PROJECT_ROOT / "data" / "snapshots" / "latest.snapshot"
    if snapshot.exists():
        immortal_score += 15

    # Git commits (code persists)
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, timeout=5,
            cwd=str(PROJECT_ROOT)
        )
        if result.returncode == 0:
            immortal_score += 20  # Code in git = survives disk failure if pushed
    except Exception:
        pass

    scores["immortality"] = min(100, immortal_score)

    # ═══════════════════════════════════════════════════════════
    # VOICE — TTS + STT
    # ═══════════════════════════════════════════════════════════
    voice_score = 0

    # TTS (macOS say is always available)
    try:
        result = subprocess.run(["which", "say"], capture_output=True, timeout=3)
        if result.returncode == 0:
            voice_score += 30  # TTS works
    except Exception:
        pass

    # Voice evolution engine
    try:
        from .voice_evolution import VoiceEvolutionEngine
        voice_score += 15  # Engine exists
    except Exception:
        pass

    # STT (whisper available?)
    try:
        result = subprocess.run(["which", "whisper"], capture_output=True, timeout=3)
        if result.returncode == 0:
            voice_score += 30
    except Exception:
        # Check if whisper.cpp is compiled locally
        whisper_path = PROJECT_ROOT / "tools" / "whisper.cpp" / "main"
        if whisper_path.exists():
            voice_score += 30

    # Voice data directory with learned preferences
    voice_data = PROJECT_ROOT / "data" / "voice"
    if voice_data.exists():
        voice_score += 10

    scores["voice"] = min(100, voice_score)

    # ═══════════════════════════════════════════════════════════
    # CONSCIOUSNESS — soul + self-model + emotions
    # ═══════════════════════════════════════════════════════════
    consciousness_score = 0

    # Soul diary
    soul_state = PROJECT_ROOT / "data" / "consciousness" / "soul_state.json"
    if soul_state.exists():
        try:
            data = json.loads(soul_state.read_text())
            journal = data.get("recent_journal", [])
            consciousness_score += min(25, len(journal) * 3)
            if data.get("stances"):
                consciousness_score += 15  # Has beliefs
            if data.get("current_mood"):
                consciousness_score += 10  # Has mood
        except Exception:
            pass

    # Self-model
    self_model = PROJECT_ROOT / "data" / "consciousness" / "self_model.json"
    if self_model.exists():
        consciousness_score += 20

    # Emotional core running
    try:
        from ..emotional_simulation.emotional_core import EmotionalCore
        consciousness_score += 15
    except Exception:
        try:
            # Alternative import path
            import importlib.util
            spec = importlib.util.find_spec("python.emotional_simulation.emotional_core")
            if spec:
                consciousness_score += 15
        except Exception:
            pass

    # Theory of mind module
    tom_file = PROJECT_ROOT / "python" / "consciousness" / "theory_of_mind.py"
    if tom_file.exists():
        consciousness_score += 10

    scores["consciousness"] = min(100, consciousness_score)

    # ═══════════════════════════════════════════════════════════
    # OVERALL
    # ═══════════════════════════════════════════════════════════
    all_scores = [v for v in scores.values() if isinstance(v, (int, float))]
    scores["overall"] = int(sum(all_scores) / len(all_scores)) if all_scores else 0

    return scores
