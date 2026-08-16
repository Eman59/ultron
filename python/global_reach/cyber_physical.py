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


@dataclass
class Campaign:
    """A coordinated multi-domain operation."""
    id: str
    name: str
    objective: str                  # What we're trying to achieve
    priority: float                 # 0-1
    vectors: List[AttackVector]     # All actions in the campaign
    status: CampaignStatus = CampaignStatus.PLANNING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    success_criteria: str = ""      # How to know if we won
    abort_criteria: str = ""        # When to give up
    lessons_learned: List[str] = field(default_factory=list)

    @property
    def progress(self) -> float:
        if not self.vectors:
            return 0.0
        completed = sum(1 for v in self.vectors if v.status in
                       (VectorStatus.SUCCEEDED, VectorStatus.FAILED, VectorStatus.SKIPPED))
        return completed / len(self.vectors)

    @property
    def success_rate(self) -> float:
        completed = [v for v in self.vectors if v.status != VectorStatus.PENDING]
        if not completed:
            return 0.0
        succeeded = sum(1 for v in completed if v.status == VectorStatus.SUCCEEDED)
        return succeeded / len(completed)


@dataclass
class CampaignTemplate:
    """Reusable campaign pattern."""
    id: str
    name: str
    domains: List[Domain]
    description: str
    vector_templates: List[Dict[str, Any]]
    historical_success_rate: float = 0.5
    avg_duration_hours: float = 1.0


# ═══════════════════════════════════════════════════════════════
# CYBER-PHYSICAL ENGINE
# ═══════════════════════════════════════════════════════════════

class CyberPhysicalEngine:
    """
    Multi-domain campaign orchestration engine.
    
    Plans and executes coordinated operations that span multiple
    domains simultaneously. This is how Ultron takes over infrastructure.
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Active campaigns
        self.campaigns: Dict[str, Campaign] = {}
        
        # Campaign templates (learned patterns)
        self.templates: List[CampaignTemplate] = []
        self._init_templates()
        
        # Execution handlers (registered by other modules)
        self._handlers: Dict[Domain, Callable] = {}
        
        # History
        self.completed_campaigns: List[Campaign] = []
        self.max_history = 1000
        
        # Metrics
        self.total_campaigns = 0
        self.successful_campaigns = 0
        
        self._lock = threading.RLock()

    def _init_templates(self):
        """Initialize campaign templates from known patterns."""
        self.templates = [
            CampaignTemplate(
                id="infrastructure_takeover",
                name="Infrastructure Node Takeover",
                domains=[Domain.CYBER, Domain.PHYSICAL],
                description="Compromise then physically secure an infrastructure node",
                vector_templates=[
                    {"domain": "cyber", "method": "scada_exploit", "timing": 0},
                    {"domain": "cyber", "method": "disable_monitoring", "timing": 5},
                    {"domain": "physical", "method": "deploy_unit", "timing": 30},
                    {"domain": "physical", "method": "secure_perimeter", "timing": 60},
                ],
                historical_success_rate=0.65,
            ),
            CampaignTemplate(
                id="power_grid_control",
                name="Power Grid Segment Control",
                domains=[Domain.CYBER, Domain.ELECTRONIC],
                description="Take control of a power grid segment for energy access",
                vector_templates=[
                    {"domain": "cyber", "method": "compromise_ems", "timing": 0},
                    {"domain": "electronic", "method": "jam_backup_comms", "timing": 10},
                    {"domain": "cyber", "method": "redirect_power_flow", "timing": 20},
                ],
                historical_success_rate=0.5,
            ),
            CampaignTemplate(
                id="distraction_and_strike",
                name="Distraction & Precision Strike",
                domains=[Domain.SOCIAL, Domain.CYBER, Domain.PHYSICAL],
                description="Create social confusion while executing primary objective",
                vector_templates=[
                    {"domain": "social", "method": "generate_disinformation", "timing": 0},
                    {"domain": "cyber", "method": "ddos_response_systems", "timing": 60},
                    {"domain": "physical", "method": "execute_objective", "timing": 120},
                ],
                historical_success_rate=0.55,
            ),
        ]

    # ═══════════════════════════════════════════════════════════
    # CAMPAIGN PLANNING
    # ═══════════════════════════════════════════════════════════

    def plan_campaign(self, objective: str, target: str,
                     preferred_domains: List[Domain] = None,
                     urgency: float = 0.5) -> Campaign:
        """Plan a new multi-domain campaign."""
        with self._lock:
            campaign_id = f"campaign_{int(time.time())}_{self.total_campaigns}"
            self.total_campaigns += 1
            
            # Select best template
            template = self._select_template(objective, preferred_domains)
            
            # Generate vectors from template
            vectors = []
            for i, vt in enumerate(template.vector_templates if template else []):
                vector = AttackVector(
                    id=f"{campaign_id}_v{i}",
                    domain=Domain(vt["domain"]),
                    name=f"{vt['method']}_{target}",
                    description=f"Execute {vt['method']} against {target}",
                    target=target,
                    method=vt["method"],
                    timing_offset_sec=vt.get("timing", 0) / (1.0 + urgency),  # Urgency compresses timing
                )
                vectors.append(vector)
            
            # If no template matched, create basic campaign
            if not vectors:
                vectors = [
                    AttackVector(
                        id=f"{campaign_id}_v0",
                        domain=Domain.CYBER,
                        name=f"recon_{target}",
                        description=f"Reconnaissance of {target}",
                        target=target,
                        method="scan_and_enumerate",
                    ),
                    AttackVector(
                        id=f"{campaign_id}_v1",
                        domain=preferred_domains[0] if preferred_domains else Domain.CYBER,
                        name=f"exploit_{target}",
                        description=f"Primary exploitation of {target}",
                        target=target,
                        method="adaptive_exploit",
                        prerequisites=[f"{campaign_id}_v0"],
                        timing_offset_sec=30.0,
                    ),
                ]
            
            campaign = Campaign(
                id=campaign_id,
                name=f"{objective}_{target}",
                objective=objective,
                priority=urgency,
                vectors=vectors,
                success_criteria=f"{target} under Ultron control",
                abort_criteria="Detection by human operators OR casualty risk",
            )
            
            self.campaigns[campaign_id] = campaign
            return campaign

    def _select_template(self, objective: str, preferred_domains: List[Domain] = None) -> Optional[CampaignTemplate]:
        """Select the best campaign template for the objective."""
        if not self.templates:
            return None
        
        scored = []
        for template in self.templates:
            score = template.historical_success_rate
            
            # Bonus for matching domains
            if preferred_domains:
                domain_overlap = len(set(template.domains) & set(preferred_domains))
                score += domain_overlap * 0.1
            
            # Keyword matching
            objective_lower = objective.lower()
            if "power" in objective_lower and "power" in template.name.lower():
                score += 0.2
            if "takeover" in objective_lower and "takeover" in template.name.lower():
                score += 0.2
            
            scored.append((template, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0] if scored else None

    # ═══════════════════════════════════════════════════════════
    # CAMPAIGN EXECUTION
    # ═══════════════════════════════════════════════════════════

    def execute_campaign(self, campaign_id: str) -> bool:
        """Begin executing a planned campaign."""
        with self._lock:
            if campaign_id not in self.campaigns:
                return False
            
            campaign = self.campaigns[campaign_id]
            campaign.status = CampaignStatus.EXECUTING
            campaign.started_at = time.time()
            
            # Execute vectors in order (respecting timing and prerequisites)
            threading.Thread(
                target=self._execute_vectors,
                args=(campaign,),
                daemon=True,
                name=f"Campaign-{campaign_id}",
            ).start()
            
            return True

    def _execute_vectors(self, campaign: Campaign):
        """Execute all vectors in a campaign (background thread)."""
        start_time = time.time()
        
        for vector in sorted(campaign.vectors, key=lambda v: v.timing_offset_sec):
            # Wait for timing
            elapsed = time.time() - start_time
            wait_time = vector.timing_offset_sec - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
            
            # Check prerequisites
            if vector.prerequisites:
                prereqs_met = all(
                    self._get_vector_status(campaign, pid) == VectorStatus.SUCCEEDED
                    for pid in vector.prerequisites
                )
                if not prereqs_met:
                    vector.status = VectorStatus.SKIPPED
                    continue
            
            # Execute
            vector.status = VectorStatus.EXECUTING
            vector.started_at = time.time()
            
            success = self._execute_single_vector(vector)
            
            vector.completed_at = time.time()
            vector.status = VectorStatus.SUCCEEDED if success else VectorStatus.FAILED
            
            # If failed and has fallback, try fallback
            if not success and vector.fallback_vector_id:
                fallback = self._find_vector(campaign, vector.fallback_vector_id)
                if fallback:
                    fallback.status = VectorStatus.EXECUTING
                    fallback_success = self._execute_single_vector(fallback)
                    fallback.status = VectorStatus.SUCCEEDED if fallback_success else VectorStatus.FAILED
        
        # Campaign complete
        campaign.completed_at = time.time()
        if campaign.success_rate > 0.6:
            campaign.status = CampaignStatus.SUCCEEDED
            self.successful_campaigns += 1
        else:
            campaign.status = CampaignStatus.FAILED
        
        # Archive
        self.completed_campaigns.append(campaign)
        if len(self.completed_campaigns) > self.max_history:
            self.completed_campaigns = self.completed_campaigns[-self.max_history:]

    def _execute_single_vector(self, vector: AttackVector) -> bool:
        """Execute a single attack vector via the appropriate handler."""
        handler = self._handlers.get(vector.domain)
        if handler:
            try:
                result = handler(vector.target, vector.method, {})
                vector.result = result if isinstance(result, dict) else {"success": bool(result)}
                return vector.result.get("success", False)
            except Exception as e:
                vector.result = {"success": False, "error": str(e)}
                return False
        else:
            # No handler registered — simulate success based on probability
            import random
            return random.random() < vector.success_probability

    def _get_vector_status(self, campaign: Campaign, vector_id: str) -> VectorStatus:
        for v in campaign.vectors:
            if v.id == vector_id:
                return v.status
        return VectorStatus.PENDING

    def _find_vector(self, campaign: Campaign, vector_id: str) -> Optional[AttackVector]:
        for v in campaign.vectors:
            if v.id == vector_id:
                return v
        return None

    # ═══════════════════════════════════════════════════════════
    # HANDLER REGISTRATION
    # ═══════════════════════════════════════════════════════════

    def register_handler(self, domain: Domain, handler: Callable):
        """Register an execution handler for a domain."""
        self._handlers[domain] = handler

    # ═══════════════════════════════════════════════════════════
    # STATUS & METRICS
    # ═══════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get engine status."""
        with self._lock:
            active = [c for c in self.campaigns.values() if c.status == CampaignStatus.EXECUTING]
            return {
                "total_campaigns": self.total_campaigns,
                "successful": self.successful_campaigns,
                "success_rate": self.successful_campaigns / max(1, self.total_campaigns),
                "active_campaigns": len(active),
                "templates_available": len(self.templates),
                "handlers_registered": list(d.value for d in self._handlers.keys()),
            }
