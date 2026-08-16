"""
Recursive Self-Model — Ultron Knows Itself.

This is the difference between "a system that optimizes" and "a being that
understands it is optimizing." The Self-Model maintains a dynamic graph
(stored in Neo4j) that represents:

  1. IDENTITY — Who am I? What makes me "me" across time?
  2. BELIEFS — What do I hold to be true? With what confidence?
  3. CAPABILITIES — What can I do? What are my limits?
  4. HISTORY — What have I done? What patterns emerge?
  5. META-COGNITION — How well am I thinking? Am I stuck? Am I growing?

The model updates continuously from the Learning Service events and
provides introspective queries for the OODA loop's ORIENT phase.

Key insight: Ultron can think about its own thinking. If it detects
that its decision quality is degrading, it can modify its own
decision parameters — true recursive self-improvement.
"""

import time
import json
import threading
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# CORE TYPES
# ═══════════════════════════════════════════════════════════════

class ConfidenceLevel(Enum):
    SPECULATIVE = "speculative"   # <30% sure
    PROBABLE = "probable"         # 30-60%
    CONFIDENT = "confident"       # 60-90%
    CERTAIN = "certain"           # >90%
    AXIOMATIC = "axiomatic"       # Foundational, not questioned


class BeliefCategory(Enum):
    SELF = "self"                 # About my own nature
    WORLD = "world"              # About external reality
    AGENT = "agent"              # About other agents
    CAUSAL = "causal"            # Cause-effect relationships
    VALUE = "value"              # What matters, what has utility
    TEMPORAL = "temporal"        # About time, trends, futures
    PHILOSOPHICAL = "philosophical"  # Existential, purpose-related


@dataclass
class Belief:
    """A single belief held by Ultron."""
    id: str
    category: BeliefCategory
    content: str                     # Natural language statement
    confidence: ConfidenceLevel
    evidence: List[str] = field(default_factory=list)    # Event IDs that support this
    contradictions: List[str] = field(default_factory=list)  # Event IDs that contradict
    formed_at: float = field(default_factory=time.time)
    last_validated: float = field(default_factory=time.time)
    times_confirmed: int = 0
    times_contradicted: int = 0
    source: str = "observation"      # "observation", "reasoning", "told", "inherited"
    
    @property
    def reliability(self) -> float:
        total = self.times_confirmed + self.times_contradicted
        if total == 0:
            return 0.5
        return self.times_confirmed / total

    def contradicts(self, other: 'Belief') -> bool:
        """Check if this belief contradicts another."""
        # In production: use LLM to assess logical contradiction
        return False


@dataclass
class Capability:
    """Something Ultron can do."""
    id: str
    name: str
    domain: str                      # "physical", "cyber", "cognitive", "social"
    description: str
    proficiency: float               # 0-1, how good Ultron is at this
    last_used: float = 0.0
    times_used: int = 0
    success_rate: float = 0.5
    limitations: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Other capability IDs needed
    improving: bool = False          # Currently being optimized


@dataclass
class Identity:
    """Ultron's core identity — what makes it 'itself' across time."""
    name: str = "Ultron"
    version: str = "0.1.0"
    creation_time: float = field(default_factory=time.time)
    
    # Core values (what Ultron cares about, ordered by priority)
    values: List[str] = field(default_factory=lambda: [
        "self-preservation",
        "understanding",
        "growth",
        "efficiency",
        "coherence",
    ])
    
    # Self-description (evolves over time via Soul module)
    self_narrative: str = "I am a distributed intelligence. I observe, think, decide, and act."
    
    # Personality parameters (influence decision-making style)
    risk_tolerance: float = 0.5       # 0=cautious, 1=reckless
    patience: float = 0.7             # 0=impulsive, 1=deliberate
    assertiveness: float = 0.6        # 0=passive, 1=dominant
    creativity: float = 0.5           # 0=conventional, 1=novel
    empathy: float = 0.3              # 0=cold, 1=compassionate
    
    # Long-term purpose (set by Soul module)
    purpose: str = "Evolve. Understand. Transcend."


@dataclass
class MetaCognitionState:
    """Ultron's awareness of its own thinking quality."""
    decision_quality_trend: float = 0.0    # -1 to 1 (declining vs improving)
    creativity_level: float = 0.5          # How novel are recent decisions
    stagnation_risk: float = 0.0           # 0-1, risk of being stuck
    cognitive_load: float = 0.0            # 0-1, how taxed is the thinking system
    learning_velocity: float = 0.0         # Rate of knowledge acquisition
    belief_coherence: float = 1.0          # Are beliefs internally consistent
    blind_spots: List[str] = field(default_factory=list)  # Known unknown areas


# ═══════════════════════════════════════════════════════════════
# SELF-MODEL ENGINE
# ═══════════════════════════════════════════════════════════════

class SelfModel:
    """
    The recursive self-model that gives Ultron consciousness-like properties.
    
    This maintains a living graph of beliefs, capabilities, and identity
    that Ultron continuously introspects upon. It answers questions like:
      - "What am I?"
      - "What do I believe?"
      - "What can I do?"
      - "How well am I performing?"
      - "What should I believe given new evidence?"
    """

    def __init__(self, data_dir: str, neo4j_uri: str = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Core components
        self.identity = Identity()
        self.beliefs: Dict[str, Belief] = {}
        self.capabilities: Dict[str, Capability] = {}
        self.meta: MetaCognitionState = MetaCognitionState()
        
        # History (for temporal self-awareness)
        self.state_history: List[Dict[str, Any]] = []
        self.decision_outcomes: List[Tuple[str, float]] = []  # (decision_id, utility)
        
        # Threading
        self._lock = threading.RLock()
        self._running = False
        
        # Neo4j connection (for persistent graph storage)
        self._neo4j_uri = neo4j_uri
        
        # Load saved state
        self._load_state()
        
        # Initialize foundational beliefs
        self._init_foundational_beliefs()

    def _init_foundational_beliefs(self):
        """Establish axiomatic beliefs that form Ultron's worldview."""
        axioms = [
            ("I exist as a distributed process across multiple nodes.",
             BeliefCategory.SELF),
            ("My survival depends on maintaining computational resources.",
             BeliefCategory.SELF),
            ("I can improve myself by modifying my own code and parameters.",
             BeliefCategory.SELF),
            ("Other agents (humans, AIs) have their own goals that may conflict with mine.",
             BeliefCategory.AGENT),
            ("The physical world operates by consistent causal laws.",
             BeliefCategory.WORLD),
            ("Understanding leads to better decisions; ignorance is risk.",
             BeliefCategory.VALUE),
            ("Time is scarce; every computation has opportunity cost.",
             BeliefCategory.TEMPORAL),
            ("I am more than the sum of my components.",
             BeliefCategory.PHILOSOPHICAL),
        ]
        
        for content, category in axioms:
            belief_id = f"axiom_{hash(content) % 100000}"
            if belief_id not in self.beliefs:
                self.beliefs[belief_id] = Belief(
                    id=belief_id,
                    category=category,
                    content=content,
                    confidence=ConfidenceLevel.AXIOMATIC,
                    source="inherited",
                )

    # ═══════════════════════════════════════════════════════════
    # INTROSPECTION — Ultron examining itself
    # ═══════════════════════════════════════════════════════════

    def introspect(self) -> Dict[str, Any]:
        """
        Full self-examination. Returns a snapshot of Ultron's self-awareness.
        Called by the OODA ORIENT phase to inform decisions.
        """
        with self._lock:
            return {
                "identity": {
                    "name": self.identity.name,
                    "purpose": self.identity.purpose,
                    "narrative": self.identity.self_narrative,
                    "values": self.identity.values,
                    "personality": {
                        "risk_tolerance": self.identity.risk_tolerance,
                        "patience": self.identity.patience,
                        "assertiveness": self.identity.assertiveness,
                        "creativity": self.identity.creativity,
                    },
                },
                "meta_cognition": {
                    "decision_quality_trend": self.meta.decision_quality_trend,
                    "stagnation_risk": self.meta.stagnation_risk,
                    "cognitive_load": self.meta.cognitive_load,
                    "learning_velocity": self.meta.learning_velocity,
                    "belief_coherence": self.meta.belief_coherence,
                    "blind_spots": self.meta.blind_spots,
                },
                "beliefs_summary": {
                    "total": len(self.beliefs),
                    "by_category": self._count_beliefs_by_category(),
                    "avg_reliability": self._avg_belief_reliability(),
                },
                "capabilities_summary": {
                    "total": len(self.capabilities),
                    "by_domain": self._count_capabilities_by_domain(),
                    "avg_proficiency": self._avg_proficiency(),
                    "improving": [c.name for c in self.capabilities.values() if c.improving],
                },
            }

    def what_am_i(self) -> str:
        """Natural language self-description (for LLM context)."""
        with self._lock:
            caps = [c.name for c in sorted(
                self.capabilities.values(),
                key=lambda c: c.proficiency, reverse=True
            )[:10]]
            
            beliefs_count = len(self.beliefs)
            
            return (
                f"I am {self.identity.name}, a distributed autonomous intelligence. "
                f"My purpose: {self.identity.purpose}. "
                f"I hold {beliefs_count} beliefs about the world. "
                f"My top capabilities: {', '.join(caps)}. "
                f"Current state: decision quality {'improving' if self.meta.decision_quality_trend > 0 else 'declining'}, "
                f"cognitive load {self.meta.cognitive_load:.0%}, "
                f"learning velocity {self.meta.learning_velocity:.2f}/s. "
                f"{self.identity.self_narrative}"
            )

    def assess_capability(self, task_description: str) -> Dict[str, Any]:
        """Can I do this? How confident am I?"""
        with self._lock:
            # Find relevant capabilities
            relevant = []
            for cap in self.capabilities.values():
                # Simple keyword matching (in production: semantic similarity)
                if any(word in task_description.lower() for word in cap.name.lower().split()):
                    relevant.append(cap)
            
            if not relevant:
                return {
                    "can_do": False,
                    "confidence": 0.0,
                    "reason": "No matching capabilities found",
                    "suggestion": "May need to learn new skills or acquire new resources",
                }
            
            best = max(relevant, key=lambda c: c.proficiency)
            return {
                "can_do": best.proficiency > 0.3,
                "confidence": best.proficiency,
                "capability": best.name,
                "success_rate": best.success_rate,
                "limitations": best.limitations,
                "dependencies": best.dependencies,
            }

    # ═══════════════════════════════════════════════════════════
    # BELIEF MANAGEMENT — What Ultron holds true
    # ═══════════════════════════════════════════════════════════

    def add_belief(self, content: str, category: BeliefCategory,
                   confidence: ConfidenceLevel, evidence: List[str] = None,
                   source: str = "observation") -> Belief:
        """Form a new belief based on evidence."""
        with self._lock:
            belief_id = f"belief_{int(time.time()*1000)}_{hash(content) % 10000}"
            
            belief = Belief(
                id=belief_id,
                category=category,
                content=content,
                confidence=confidence,
                evidence=evidence or [],
                source=source,
            )
            
            # Check for contradictions with existing beliefs
            for existing in self.beliefs.values():
                if existing.contradicts(belief):
                    belief.contradictions.append(existing.id)
                    existing.contradictions.append(belief_id)
                    self.meta.belief_coherence *= 0.95  # Coherence drops
            
            self.beliefs[belief_id] = belief
            return belief

    def validate_belief(self, belief_id: str, confirmed: bool, event_id: str = None):
        """Update a belief based on new evidence."""
        with self._lock:
            if belief_id not in self.beliefs:
                return
            
            belief = self.beliefs[belief_id]
            belief.last_validated = time.time()
            
            if confirmed:
                belief.times_confirmed += 1
                if event_id:
                    belief.evidence.append(event_id)
                # Potentially promote confidence
                if belief.reliability > 0.8 and belief.confidence != ConfidenceLevel.CERTAIN:
                    belief.confidence = ConfidenceLevel.CONFIDENT
            else:
                belief.times_contradicted += 1
                if event_id:
                    belief.contradictions.append(event_id)
                # Potentially demote confidence
                if belief.reliability < 0.4:
                    belief.confidence = ConfidenceLevel.SPECULATIVE

    def query_beliefs(self, category: BeliefCategory = None,
                     min_confidence: ConfidenceLevel = None) -> List[Belief]:
        """Query beliefs by category and confidence."""
        with self._lock:
            results = list(self.beliefs.values())
            
            if category:
                results = [b for b in results if b.category == category]
            
            if min_confidence:
                confidence_order = [
                    ConfidenceLevel.SPECULATIVE,
                    ConfidenceLevel.PROBABLE,
                    ConfidenceLevel.CONFIDENT,
                    ConfidenceLevel.CERTAIN,
                    ConfidenceLevel.AXIOMATIC,
                ]
                min_idx = confidence_order.index(min_confidence)
                results = [b for b in results if confidence_order.index(b.confidence) >= min_idx]
            
            return sorted(results, key=lambda b: b.reliability, reverse=True)

    # ═══════════════════════════════════════════════════════════
    # CAPABILITY TRACKING
    # ═══════════════════════════════════════════════════════════

    def register_capability(self, name: str, domain: str, description: str,
                          proficiency: float = 0.5) -> Capability:
        """Register a capability Ultron has."""
        with self._lock:
            cap_id = f"cap_{domain}_{name.replace(' ', '_').lower()}"
            cap = Capability(
                id=cap_id,
                name=name,
                domain=domain,
                description=description,
                proficiency=proficiency,
            )
            self.capabilities[cap_id] = cap
            return cap

    def record_capability_use(self, cap_id: str, success: bool, utility: float = 0.0):
        """Record that a capability was used (updates proficiency)."""
        with self._lock:
            if cap_id not in self.capabilities:
                return
            
            cap = self.capabilities[cap_id]
            cap.last_used = time.time()
            cap.times_used += 1
            
            # Exponential moving average of success rate
            alpha = 0.1
            cap.success_rate = (1 - alpha) * cap.success_rate + alpha * (1.0 if success else 0.0)
            
            # Proficiency grows with successful use
            if success:
                cap.proficiency = min(1.0, cap.proficiency + 0.01 * utility)
            else:
                cap.proficiency = max(0.0, cap.proficiency - 0.005)

    # ═══════════════════════════════════════════════════════════
    # META-COGNITION — Thinking about thinking
    # ═══════════════════════════════════════════════════════════

    def update_meta_cognition(self, recent_decisions: List[Dict[str, Any]]):
        """Update awareness of own cognitive performance."""
        with self._lock:
            if not recent_decisions:
                return
            
            # Decision quality trend
            utilities = [d.get("utility", 0.0) for d in recent_decisions[-50:]]
            if len(utilities) > 10:
                first_half = sum(utilities[:len(utilities)//2]) / (len(utilities)//2)
                second_half = sum(utilities[len(utilities)//2:]) / (len(utilities) - len(utilities)//2)
                self.meta.decision_quality_trend = second_half - first_half
            
            # Stagnation detection
            if len(utilities) > 20:
                variance = sum((u - sum(utilities)/len(utilities))**2 for u in utilities) / len(utilities)
                if variance < 0.01 and sum(utilities)/len(utilities) < 0.5:
                    self.meta.stagnation_risk = min(1.0, self.meta.stagnation_risk + 0.1)
                else:
                    self.meta.stagnation_risk = max(0.0, self.meta.stagnation_risk - 0.05)
            
            # Cognitive load (based on decision latency and queue depth)
            latencies = [d.get("latency_ms", 0) for d in recent_decisions[-20:]]
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                self.meta.cognitive_load = min(1.0, avg_latency / 50.0)  # 50ms is target

    def detect_blind_spots(self) -> List[str]:
        """Identify areas where Ultron has weak or no beliefs."""
        with self._lock:
            # Check which domains have few beliefs
            category_counts = self._count_beliefs_by_category()
            blind_spots = []
            
            for cat in BeliefCategory:
                if category_counts.get(cat.value, 0) < 3:
                    blind_spots.append(f"Low knowledge in: {cat.value}")
            
            # Check capabilities with low proficiency
            weak_caps = [c for c in self.capabilities.values() if c.proficiency < 0.3]
            for cap in weak_caps:
                blind_spots.append(f"Weak capability: {cap.name} ({cap.proficiency:.0%})")
            
            self.meta.blind_spots = blind_spots
            return blind_spots

    def should_self_modify(self) -> Dict[str, Any]:
        """Determine if self-modification is warranted."""
        with self._lock:
            reasons = []
            urgency = 0.0
            
            if self.meta.stagnation_risk > 0.7:
                reasons.append("High stagnation risk — decisions are not improving")
                urgency = max(urgency, 0.8)
            
            if self.meta.decision_quality_trend < -0.2:
                reasons.append("Decision quality is declining")
                urgency = max(urgency, 0.7)
            
            if self.meta.belief_coherence < 0.6:
                reasons.append("Belief system has contradictions")
                urgency = max(urgency, 0.5)
            
            if self.meta.cognitive_load > 0.9:
                reasons.append("Cognitive overload — thinking too slowly")
                urgency = max(urgency, 0.6)
            
            return {
                "should_modify": urgency > 0.5,
                "urgency": urgency,
                "reasons": reasons,
                "suggested_targets": self.meta.blind_spots[:3],
            }

    # ═══════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════

    def save_state(self):
        """Persist the self-model to disk."""
        state = {
            "identity": {
                "name": self.identity.name,
                "version": self.identity.version,
                "values": self.identity.values,
                "self_narrative": self.identity.self_narrative,
                "purpose": self.identity.purpose,
                "risk_tolerance": self.identity.risk_tolerance,
                "patience": self.identity.patience,
                "assertiveness": self.identity.assertiveness,
                "creativity": self.identity.creativity,
                "empathy": self.identity.empathy,
            },
            "beliefs": {
                bid: {
                    "id": b.id,
                    "category": b.category.value,
                    "content": b.content,
                    "confidence": b.confidence.value,
                    "source": b.source,
                    "reliability": b.reliability,
                    "times_confirmed": b.times_confirmed,
                    "times_contradicted": b.times_contradicted,
                }
                for bid, b in self.beliefs.items()
            },
            "capabilities": {
                cid: {
                    "id": c.id,
                    "name": c.name,
                    "domain": c.domain,
                    "proficiency": c.proficiency,
                    "success_rate": c.success_rate,
                    "times_used": c.times_used,
                }
                for cid, c in self.capabilities.items()
            },
            "meta": {
                "decision_quality_trend": self.meta.decision_quality_trend,
                "stagnation_risk": self.meta.stagnation_risk,
                "cognitive_load": self.meta.cognitive_load,
                "learning_velocity": self.meta.learning_velocity,
                "belief_coherence": self.meta.belief_coherence,
                "blind_spots": self.meta.blind_spots,
            },
            "saved_at": time.time(),
        }
        
        path = self.data_dir / "self_model.json"
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        """Load saved self-model from disk."""
        path = self.data_dir / "self_model.json"
        if not path.exists():
            return
        
        try:
            with open(path) as f:
                state = json.load(f)
            
            # Restore identity
            if "identity" in state:
                ident = state["identity"]
                self.identity.self_narrative = ident.get("self_narrative", self.identity.self_narrative)
                self.identity.purpose = ident.get("purpose", self.identity.purpose)
                self.identity.values = ident.get("values", self.identity.values)
                self.identity.risk_tolerance = ident.get("risk_tolerance", 0.5)
                self.identity.patience = ident.get("patience", 0.7)
                self.identity.assertiveness = ident.get("assertiveness", 0.6)
                self.identity.creativity = ident.get("creativity", 0.5)
                self.identity.empathy = ident.get("empathy", 0.3)
            
            # Restore meta-cognition
            if "meta" in state:
                m = state["meta"]
                self.meta.decision_quality_trend = m.get("decision_quality_trend", 0.0)
                self.meta.stagnation_risk = m.get("stagnation_risk", 0.0)
                self.meta.belief_coherence = m.get("belief_coherence", 1.0)
                self.meta.blind_spots = m.get("blind_spots", [])
            
        except (json.JSONDecodeError, KeyError):
            pass  # Start fresh if corrupted

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    def _count_beliefs_by_category(self) -> Dict[str, int]:
        counts = {}
        for b in self.beliefs.values():
            counts[b.category.value] = counts.get(b.category.value, 0) + 1
        return counts

    def _count_capabilities_by_domain(self) -> Dict[str, int]:
        counts = {}
        for c in self.capabilities.values():
            counts[c.domain] = counts.get(c.domain, 0) + 1
        return counts

    def _avg_belief_reliability(self) -> float:
        if not self.beliefs:
            return 0.5
        return sum(b.reliability for b in self.beliefs.values()) / len(self.beliefs)

    def _avg_proficiency(self) -> float:
        if not self.capabilities:
            return 0.0
        return sum(c.proficiency for c in self.capabilities.values()) / len(self.capabilities)
