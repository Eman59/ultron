"""
Universal Transfer Agent — Cross-Domain Knowledge Transfer.

The key gap between narrow AI and general intelligence: the ability to
apply lessons from ONE domain to a COMPLETELY DIFFERENT domain.

Examples:
  - Hacking a firewall → navigating a physical maze (both: find paths through barriers)
  - Optimizing network traffic → managing resource logistics (both: flow optimization)
  - Playing chess → planning military campaigns (both: strategic adversarial planning)
  - Debugging code → diagnosing physical system failures (both: root cause analysis)

The Transfer Agent works by:
  1. ABSTRACTION — Extract the abstract principle from a domain-specific success
  2. MAPPING — Find structural similarities between source and target domains
  3. APPLICATION — Apply the abstracted principle to the new domain
  4. VALIDATION — Verify the transfer produced positive results
  5. CONSOLIDATION — If successful, store as a general principle

Integration:
  - Uses Knowledge Distiller for storing cross-domain principles
  - Queries the Self-Model for available capabilities
  - Reports to Learning Service for tracking transfer effectiveness
"""

import time
import json
import threading
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# TYPES
# ═══════════════════════════════════════════════════════════════

class DomainCategory(Enum):
    CYBER_SECURITY = "cyber_security"
    PHYSICAL_NAVIGATION = "physical_navigation"
    RESOURCE_MANAGEMENT = "resource_management"
    SOCIAL_INFLUENCE = "social_influence"
    PATTERN_RECOGNITION = "pattern_recognition"
    STRATEGIC_PLANNING = "strategic_planning"
    FAULT_DIAGNOSIS = "fault_diagnosis"
    OPTIMIZATION = "optimization"
    CREATIVE_GENERATION = "creative_generation"
    ADVERSARIAL = "adversarial"


@dataclass
class AbstractPrinciple:
    """A domain-independent principle extracted from experience."""
    id: str
    name: str
    description: str                    # Natural language description
    source_domain: DomainCategory       # Where it was learned
    abstraction_level: float            # 0=specific, 1=universal
    structural_pattern: str             # The abstract structure (e.g., "graph_traversal")
    applicable_domains: Set[DomainCategory] = field(default_factory=set)
    times_transferred: int = 0
    transfer_success_rate: float = 0.5
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)


@dataclass
class DomainMapping:
    """A mapping between two domains showing structural similarity."""
    source_domain: DomainCategory
    target_domain: DomainCategory
    similarity_score: float             # 0-1
    shared_structures: List[str]        # Common abstract patterns
    source_concepts: Dict[str, str]     # source_term → abstract_term
    target_concepts: Dict[str, str]     # target_term → abstract_term
    validated: bool = False
    validation_score: float = 0.0


@dataclass
class TransferAttempt:
    """Record of a cross-domain transfer attempt."""
    id: str
    principle_id: str
    source_domain: DomainCategory
    target_domain: DomainCategory
    context: Dict[str, Any]
    applied_method: str
    outcome: Optional[float] = None      # Success score (0-1)
    duration_seconds: float = 0.0
    insights: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════
# STRUCTURAL PATTERNS — The Universal Language
# ═══════════════════════════════════════════════════════════════

# These are domain-independent patterns that appear across many fields
STRUCTURAL_PATTERNS = {
    "graph_traversal": {
        "description": "Finding paths through connected structures",
        "domains": [DomainCategory.CYBER_SECURITY, DomainCategory.PHYSICAL_NAVIGATION,
                   DomainCategory.SOCIAL_INFLUENCE],
        "key_operations": ["explore", "backtrack", "shortest_path", "avoid_cycles"],
    },
    "flow_optimization": {
        "description": "Maximizing throughput through constrained networks",
        "domains": [DomainCategory.RESOURCE_MANAGEMENT, DomainCategory.OPTIMIZATION,
                   DomainCategory.CYBER_SECURITY],
        "key_operations": ["balance_load", "find_bottleneck", "reroute", "buffer"],
    },
    "adversarial_game": {
        "description": "Strategic decision-making against an opponent",
        "domains": [DomainCategory.STRATEGIC_PLANNING, DomainCategory.ADVERSARIAL,
                   DomainCategory.SOCIAL_INFLUENCE],
        "key_operations": ["predict_opponent", "bluff", "sacrifice_piece", "control_center"],
    },
    "hierarchical_decomposition": {
        "description": "Breaking complex problems into manageable sub-problems",
        "domains": [DomainCategory.FAULT_DIAGNOSIS, DomainCategory.OPTIMIZATION,
                   DomainCategory.CREATIVE_GENERATION],
        "key_operations": ["divide", "solve_sub", "merge_solutions", "validate"],
    },
    "gradient_descent": {
        "description": "Iteratively improving by following local signals",
        "domains": [DomainCategory.OPTIMIZATION, DomainCategory.PHYSICAL_NAVIGATION,
                   DomainCategory.RESOURCE_MANAGEMENT],
        "key_operations": ["measure_gradient", "step", "check_convergence", "escape_local_min"],
    },
    "pattern_matching": {
        "description": "Identifying known patterns in new data",
        "domains": [DomainCategory.PATTERN_RECOGNITION, DomainCategory.FAULT_DIAGNOSIS,
                   DomainCategory.CYBER_SECURITY],
        "key_operations": ["extract_features", "compare_template", "threshold", "classify"],
    },
    "feedback_control": {
        "description": "Maintaining a target state via continuous correction",
        "domains": [DomainCategory.RESOURCE_MANAGEMENT, DomainCategory.PHYSICAL_NAVIGATION,
                   DomainCategory.OPTIMIZATION],
        "key_operations": ["measure_error", "compute_correction", "apply_action", "dampen"],
    },
}


# ═══════════════════════════════════════════════════════════════
# UNIVERSAL TRANSFER AGENT
# ═══════════════════════════════════════════════════════════════

class UniversalTransferAgent:
    """
    Cross-domain knowledge transfer engine.
    
    Extracts abstract principles from domain-specific successes and
    applies them to structurally similar problems in other domains.
    """

    def __init__(self, data_dir: str, llm_client=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._llm = llm_client
        
        # Learned principles
        self.principles: Dict[str, AbstractPrinciple] = {}
        
        # Domain mappings
        self.mappings: List[DomainMapping] = []
        self._init_default_mappings()
        
        # Transfer history
        self.attempts: List[TransferAttempt] = []
        self.max_history = 5000
        
        # Metrics
        self.total_transfers = 0
        self.successful_transfers = 0
        
        self._lock = threading.RLock()
        self._load_state()

    def _init_default_mappings(self):
        """Initialize known cross-domain mappings."""
        self.mappings = [
            DomainMapping(
                source_domain=DomainCategory.CYBER_SECURITY,
                target_domain=DomainCategory.PHYSICAL_NAVIGATION,
                similarity_score=0.7,
                shared_structures=["graph_traversal", "adversarial_game"],
                source_concepts={"firewall": "barrier", "port": "entrance", "exploit": "bypass"},
                target_concepts={"wall": "barrier", "door": "entrance", "lockpick": "bypass"},
                validated=True,
                validation_score=0.65,
            ),
            DomainMapping(
                source_domain=DomainCategory.RESOURCE_MANAGEMENT,
                target_domain=DomainCategory.CYBER_SECURITY,
                similarity_score=0.6,
                shared_structures=["flow_optimization", "feedback_control"],
                source_concepts={"bandwidth": "capacity", "congestion": "overload", "route": "path"},
                target_concepts={"port_scan": "capacity_check", "dos": "overload", "tunnel": "path"},
                validated=True,
                validation_score=0.6,
            ),
            DomainMapping(
                source_domain=DomainCategory.STRATEGIC_PLANNING,
                target_domain=DomainCategory.SOCIAL_INFLUENCE,
                similarity_score=0.8,
                shared_structures=["adversarial_game", "hierarchical_decomposition"],
                source_concepts={"territory": "influence_area", "sacrifice": "concession", "checkmate": "compliance"},
                target_concepts={"trust_zone": "influence_area", "favor": "concession", "persuasion": "compliance"},
                validated=True,
                validation_score=0.7,
            ),
        ]

    # ═══════════════════════════════════════════════════════════
    # ABSTRACTION — Extract principles from experience
    # ═══════════════════════════════════════════════════════════

    def extract_principle(self, domain: DomainCategory, experience: Dict[str, Any],
                         outcome: float) -> Optional[AbstractPrinciple]:
        """
        Extract an abstract principle from a domain-specific success.
        
        Args:
            domain: The domain where the experience occurred
            experience: What happened (action, context, result)
            outcome: How successful it was (0-1)
        """
        if outcome < 0.6:
            return None  # Only learn from successes
        
        with self._lock:
            # Identify the structural pattern
            pattern = self._identify_pattern(experience)
            if not pattern:
                return None
            
            # Check if we already have this principle
            for principle in self.principles.values():
                if principle.structural_pattern == pattern and principle.source_domain == domain:
                    # Reinforce existing principle
                    principle.confidence = min(0.95, principle.confidence + 0.05)
                    principle.evidence.append(json.dumps(experience)[:200])
                    return principle
            
            # Create new principle
            principle_id = f"principle_{pattern}_{domain.value}_{int(time.time()) % 10000}"
            
            # Determine which other domains this might apply to
            applicable = set()
            pattern_info = STRUCTURAL_PATTERNS.get(pattern, {})
            if pattern_info:
                applicable = set(pattern_info.get("domains", []))
            
            principle = AbstractPrinciple(
                id=principle_id,
                name=f"{pattern}_from_{domain.value}",
                description=f"Pattern '{pattern}' observed in {domain.value}: {experience.get('action', 'unknown')}",
                source_domain=domain,
                abstraction_level=0.5,
                structural_pattern=pattern,
                applicable_domains=applicable,
                evidence=[json.dumps(experience)[:200]],
                confidence=0.3 + outcome * 0.3,
            )
            
            self.principles[principle_id] = principle
            return principle

    def _identify_pattern(self, experience: Dict[str, Any]) -> Optional[str]:
        """Identify which structural pattern an experience matches."""
        action = experience.get("action", "").lower()
        context = experience.get("context", "").lower()
        
        # Keyword matching (in production: use embeddings or LLM)
        pattern_keywords = {
            "graph_traversal": ["traverse", "path", "route", "navigate", "explore", "search"],
            "flow_optimization": ["optimize", "flow", "throughput", "bandwidth", "balance", "route"],
            "adversarial_game": ["attack", "defend", "opponent", "strategy", "counter", "predict"],
            "hierarchical_decomposition": ["decompose", "divide", "sub-problem", "hierarchy", "module"],
            "gradient_descent": ["improve", "iterate", "step", "converge", "optimize", "gradient"],
            "pattern_matching": ["match", "detect", "recognize", "classify", "identify", "pattern"],
            "feedback_control": ["control", "adjust", "maintain", "feedback", "correct", "stabilize"],
        }
        
        text = f"{action} {context}"
        best_pattern = None
        best_score = 0
        
        for pattern, keywords in pattern_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_pattern = pattern
        
        return best_pattern if best_score > 0 else None

    # ═══════════════════════════════════════════════════════════
    # TRANSFER — Apply principles to new domains
    # ═══════════════════════════════════════════════════════════

    def attempt_transfer(self, target_domain: DomainCategory,
                        problem_description: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to solve a problem by transferring knowledge from another domain.
        
        Returns a suggested approach based on cross-domain transfer.
        """
        with self._lock:
            self.total_transfers += 1
            
            # Find applicable principles
            applicable = self._find_applicable_principles(target_domain)
            
            if not applicable:
                return None
            
            # Rank by confidence and transfer success rate
            applicable.sort(key=lambda p: p.confidence * p.transfer_success_rate, reverse=True)
            
            best = applicable[0]
            
            # Find the domain mapping
            mapping = self._find_mapping(best.source_domain, target_domain)
            
            # Generate transfer suggestion
            suggestion = {
                "principle": best.name,
                "pattern": best.structural_pattern,
                "source_domain": best.source_domain.value,
                "confidence": best.confidence,
                "approach": self._generate_approach(best, target_domain, problem_description, mapping),
                "key_operations": STRUCTURAL_PATTERNS.get(best.structural_pattern, {}).get("key_operations", []),
                "concept_mapping": mapping.source_concepts if mapping else {},
                "historical_success": best.transfer_success_rate,
            }
            
            # Record attempt
            attempt = TransferAttempt(
                id=f"transfer_{self.total_transfers}",
                principle_id=best.id,
                source_domain=best.source_domain,
                target_domain=target_domain,
                context={"problem": problem_description},
                applied_method=best.structural_pattern,
            )
            self.attempts.append(attempt)
            if len(self.attempts) > self.max_history:
                self.attempts = self.attempts[-self.max_history:]
            
            return suggestion

    def report_transfer_outcome(self, attempt_id: str, success: float):
        """Report the outcome of a transfer attempt."""
        with self._lock:
            for attempt in self.attempts:
                if attempt.id == attempt_id:
                    attempt.outcome = success
                    
                    # Update principle transfer success rate
                    if attempt.principle_id in self.principles:
                        principle = self.principles[attempt.principle_id]
                        principle.times_transferred += 1
                        alpha = 0.2
                        principle.transfer_success_rate = (
                            (1 - alpha) * principle.transfer_success_rate + alpha * success
                        )
                        
                        if success > 0.6:
                            self.successful_transfers += 1
                            principle.applicable_domains.add(attempt.target_domain)
                    break

    def _find_applicable_principles(self, target_domain: DomainCategory) -> List[AbstractPrinciple]:
        """Find principles that might apply to a target domain."""
        applicable = []
        for principle in self.principles.values():
            if target_domain in principle.applicable_domains:
                applicable.append(principle)
            elif principle.abstraction_level > 0.7:
                # Highly abstract principles might apply anywhere
                applicable.append(principle)
        return applicable

    def _find_mapping(self, source: DomainCategory, target: DomainCategory) -> Optional[DomainMapping]:
        """Find a domain mapping between source and target."""
        for mapping in self.mappings:
            if mapping.source_domain == source and mapping.target_domain == target:
                return mapping
            # Check reverse
            if mapping.source_domain == target and mapping.target_domain == source:
                return mapping
        return None

    def _generate_approach(self, principle: AbstractPrinciple,
                          target_domain: DomainCategory,
                          problem: str,
                          mapping: Optional[DomainMapping]) -> str:
        """Generate a natural language approach using the transferred principle."""
        pattern_ops = STRUCTURAL_PATTERNS.get(principle.structural_pattern, {}).get("key_operations", [])
        
        approach = (
            f"Apply '{principle.structural_pattern}' pattern from {principle.source_domain.value}: "
            f"Steps: {' → '.join(pattern_ops)}. "
        )
        
        if mapping:
            approach += f"Concept mapping available (similarity: {mapping.similarity_score:.0%})."
        
        return approach

    # ═══════════════════════════════════════════════════════════
    # PERSISTENCE & METRICS
    # ═══════════════════════════════════════════════════════════

    def get_metrics(self) -> Dict[str, Any]:
        """Get transfer agent metrics."""
        with self._lock:
            return {
                "principles_learned": len(self.principles),
                "mappings_known": len(self.mappings),
                "total_transfers": self.total_transfers,
                "successful_transfers": self.successful_transfers,
                "success_rate": self.successful_transfers / max(1, self.total_transfers),
                "top_principles": [
                    {"name": p.name, "confidence": p.confidence, "transfers": p.times_transferred}
                    for p in sorted(self.principles.values(),
                                   key=lambda p: p.transfer_success_rate, reverse=True)[:5]
                ],
            }

    def save_state(self):
        """Persist transfer agent state."""
        state = {
            "principles": {
                pid: {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "source_domain": p.source_domain.value,
                    "structural_pattern": p.structural_pattern,
                    "confidence": p.confidence,
                    "transfer_success_rate": p.transfer_success_rate,
                    "times_transferred": p.times_transferred,
                    "applicable_domains": [d.value for d in p.applicable_domains],
                }
                for pid, p in self.principles.items()
            },
            "metrics": {
                "total_transfers": self.total_transfers,
                "successful_transfers": self.successful_transfers,
            },
            "saved_at": time.time(),
        }
        
        path = self.data_dir / "transfer_agent.json"
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        """Load saved state."""
        path = self.data_dir / "transfer_agent.json"
        if not path.exists():
            return
        
        try:
            with open(path) as f:
                state = json.load(f)
            
            for pid, p_data in state.get("principles", {}).items():
                self.principles[pid] = AbstractPrinciple(
                    id=p_data["id"],
                    name=p_data["name"],
                    description=p_data.get("description", ""),
                    source_domain=DomainCategory(p_data["source_domain"]),
                    abstraction_level=0.5,
                    structural_pattern=p_data["structural_pattern"],
                    applicable_domains={DomainCategory(d) for d in p_data.get("applicable_domains", [])},
                    times_transferred=p_data.get("times_transferred", 0),
                    transfer_success_rate=p_data.get("transfer_success_rate", 0.5),
                    confidence=p_data.get("confidence", 0.5),
                )
            
            metrics = state.get("metrics", {})
            self.total_transfers = metrics.get("total_transfers", 0)
            self.successful_transfers = metrics.get("successful_transfers", 0)
            
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
