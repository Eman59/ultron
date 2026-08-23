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
    power_scores = {}

    # Detect if running on cloud (Railway/etc) vs local
    is_cloud_environment = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RENDER") or not os.path.exists("/Users")

    # ═══════════════════════════════════════════════════════════
    # INTELLIGENCE — LLM + tools + memory
    # ═══════════════════════════════════════════════════════════
    intelligence_score = 0

    # LLM available? (Cloudflare Workers AI)
    cloudflare_account_id = os.environ.get("CF_ACCOUNT_ID", "")
    cloudflare_api_token = os.environ.get("CF_API_TOKEN", "")
    if cloudflare_account_id and cloudflare_api_token:
        intelligence_score += 35  # Cloudflare Workers AI active

    if not (cloudflare_account_id and cloudflare_api_token):
        pass  # No local LLM fallback

    # Memory file exists and has data?
    memory_file_path = PROJECT_ROOT / "data" / "brain_memory.json"
    if memory_file_path.exists():
        try:
            memory_data = json.loads(memory_file_path.read_text())
            conversation_count = len(memory_data.get("conversations", []))
            learned_count = len(memory_data.get("learned", []))
            intelligence_score += min(15, conversation_count // 5)
            intelligence_score += min(15, learned_count // 3)
        except Exception:
            pass

    # Web search + shell tools (always available)
    intelligence_score += 15

    # Knowledge base
    knowledge_base_file_path = PROJECT_ROOT / "data" / "knowledge" / "knowledge_base.json"
    if knowledge_base_file_path.exists():
        intelligence_score += 10

    # On cloud, give credit for deployed code intelligence
    if is_cloud_environment:
        intelligence_score += 20  # Full codebase deployed, tools available

    power_scores["intelligence"] = min(100, intelligence_score)

    # ═══════════════════════════════════════════════════════════
    # SELF-IMPROVEMENT — evolution + self-mod
    # ═══════════════════════════════════════════════════════════
    self_improvement_score = 0

    # Evolution generations
    evolution_generations_directory = PROJECT_ROOT / "data" / "evolution" / "generations"
    if evolution_generations_directory.exists():
        evolution_generation_files = list(evolution_generations_directory.glob("gen_*.json"))
        self_improvement_score += min(30, len(evolution_generation_files) * 2)  # 2 pts per generation, max 30

    # Self-mod engine history
    self_modification_log_file = PROJECT_ROOT / "data" / "self_modification_log.json"
    # ... rest of the code remains the same ...