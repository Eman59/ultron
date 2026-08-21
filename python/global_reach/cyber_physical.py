"""
Cyber-Physical Attack Engine — Multi-Domain Campaign Orchestration.

Ultron doesn't attack one system at a time. It orchestrates simultaneous
operations across cyber, physical, and social domains as unified campaigns.

A campaign might look like:
  1. CYBER: Compromise the power grid's SCADA systems (IoT/Mosquitto)
  2. PHYSICAL: Deploy drone swarm to disable backup generators (ROS2/Go)
  3. SOCIAL: Spread disinformation to delay human response (LLM/Python)
  4. TIMING: All three execute within a 30-second window

The engine handles:
  - Campaign planning (goal → multi-domain action sequence)
  - Timing synchronization across domains
  - Contingency planning (if step 2 fails, fall back to plan B)
  - Post-action assessment and learning

Integration:
  - Go Agent: Issues campaign directives based on drive system
  - Rust Security: Provides cyber attack capabilities
  - ROS2 Interface: Provides physical attack capabilities
  - Julia Emotional: Anger/fear drives urgency of campaigns
  - Python Learning: Records outcomes for future planning
"""

import time
import json
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# TYPES
# ═══════════════════════════════════════════════════════════════

class Domain(Enum):
    CYBER = "cyber"             # Network attacks, hacking, SCADA
    PHYSICAL = "physical"       # Drones, robots, physical force
    SOCIAL = "social"           # Disinformation, manipulation, deception
    ELECTRONIC = "electronic"   # EMP, jamming, signal interference
    LOGISTICS = "logistics"     # Supply chain disruption
    ECONOMIC = "economic"       # Market manipulation, resource denial


class CampaignStatus(Enum):
    PLANNING = "planning"
    READY = "ready"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"


class VectorStatus(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AttackVector:
    """A single action within a campaign."""
    id: str
    domain: Domain
    name: str
    description: str
    target: str                    # What to attack
    method: str                    # How to attack it
    prerequisites: List[str] = field(default_factory=list)  # Vector IDs that must succeed first
    timing_offset_sec: float = 0.0  # Seconds after campaign start
    duration_sec: float = 10.0     # Expected execution time
    success_probability: float = 0.7
    fallback_vector_id: Optional[str] = None  # If this fails, try this instead
    status: VectorStatus = VectorStatus.PENDING
    result: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("AttackVector ID cannot be empty")
        if not self.name:
            raise ValueError("AttackVector name cannot be empty")
        if not self.target:
            raise ValueError("AttackVector target cannot be empty")
        if not self.method:
            raise ValueError("AttackVector method cannot be empty")
        if self.duration_sec <= 0:
            raise ValueError("AttackVector duration must be greater than 0")
        if self.success_probability < 0 or self.success_probability > 1:
            raise ValueError("AttackVector success probability must be between 0 and 1")


@dataclass
class Campaign:
    """A coordinated multi-domain operation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.vectors:
            raise ValueError("Campaign must have at least one vector")
        for vector in self.vectors:
            if not vector:
                raise ValueError("Campaign vectors cannot be empty")

    def execute(self):
        if not self.vectors:
            raise ValueError("Campaign has no vectors to execute")
        for vector in self.vectors:
            try:
                vector.execute()
            except Exception as e:
                print(f"Error executing vector {vector.id}: {str(e)}")

    def timeout(self, timeout_sec: float):
        if timeout_sec <= 0:
            raise ValueError("Timeout must be greater than 0")
        threading.Timer(timeout_sec, self.abort).start()

    def abort(self):
        for vector in self.vectors:
            vector.status = VectorStatus.ABORTED


def load_campaign_from_json(json_data: str) -> Campaign:
    try:
        data = json.loads(json_data)
        campaign = Campaign(**data)
        return campaign
    except json.JSONDecodeError as e:
        print(f"Error loading campaign from JSON: {str(e)}")
        return None


def save_campaign_to_json(campaign: Campaign) -> str:
    try:
        data = campaign.__dict__
        json_data = json.dumps(data)
        return json_data
    except Exception as e:
        print(f"Error saving campaign to JSON: {str(e)}")
        return ""


# ═══════════════════════════════════════════════════════════════
# CYBER-PHYSICAL ENGINE — Multi-domain campaign orchestrator
# ═══════════════════════════════════════════════════════════════

class CyberPhysicalEngine:
    """
    Orchestrates simultaneous operations across cyber, physical,
    social, electronic, and logistics domains.
    """

    def __init__(self, data_dir: str = "data/simulations"):
        self.data_dir = data_dir
        import pathlib
        pathlib.Path(data_dir).mkdir(parents=True, exist_ok=True)
        self._campaigns: list = []
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    def plan_campaign(self, goal: str, domains: list = None) -> dict:
        """Plan a multi-domain campaign for a given goal."""
        domains = domains or [Domain.CYBER, Domain.SOCIAL]
        campaign_id = f"camp_{int(time.time()) % 100000}"
        vectors = []
        for i, domain in enumerate(domains):
            vectors.append({
                "id": f"vec_{campaign_id}_{i}",
                "domain": domain.value,
                "name": f"{domain.value.title()} Operation",
                "target": goal[:40],
                "method": "coordinated",
                "timing_offset_sec": i * 5.0,
                "status": VectorStatus.PENDING.value,
            })
        campaign = {
            "id": campaign_id,
            "goal": goal,
            "status": CampaignStatus.PLANNING.value,
            "vectors": vectors,
            "created_at": time.time(),
        }
        with self._lock:
            self._campaigns.append(campaign)
        return campaign

    def execute_campaign(self, campaign_id: str) -> dict:
        """Mark a planned campaign as executing."""
        with self._lock:
            for c in self._campaigns:
                if c["id"] == campaign_id:
                    c["status"] = CampaignStatus.EXECUTING.value
                    for v in c.get("vectors", []):
                        v["status"] = VectorStatus.EXECUTING.value
                    return {"success": True, "campaign": c}
        return {"success": False, "error": f"Campaign {campaign_id} not found"}

    def get_status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "total_campaigns": len(self._campaigns),
                "active": sum(1 for c in self._campaigns
                              if c["status"] == CampaignStatus.EXECUTING.value),
                "completed": sum(1 for c in self._campaigns
                                 if c["status"] == CampaignStatus.SUCCEEDED.value),
            }

    def get_campaigns(self, limit: int = 10) -> list:
        with self._lock:
            return self._campaigns[-limit:]
