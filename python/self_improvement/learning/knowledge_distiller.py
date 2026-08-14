"""
Knowledge Distiller — Long-Term Wisdom from Short-Term Experience.

The other components discover patterns and test optimizations in real-time.
But experience is fleeting — it fills buffers and eventually rotates out.
The Knowledge Distiller is responsible for PERMANENT LEARNING.

It takes the best discoveries from the PatternRecognizer and the proven
optimizations from the AdaptiveOptimizer, and distills them into:

  1. RULES     — If-then decision heuristics ("When X, always do Y")
  2. PRIORS    — Bayesian priors that bias future exploration
  3. AXIOMS    — Invariants about the system ("Component A is always
                 bottleneck when load > 70%")
  4. TABOOS    — Things that MUST NOT happen ("Never modify X during Y")
  5. INSTINCTS — Fast reflexive behaviors that skip deliberation

These distilled knowledge forms persist to disk and are loaded on startup,
giving the system CONTINUITY — it doesn't forget what it learned last time.

The distillation process:
  RAW PATTERNS → CONFIRMED PATTERNS → CANDIDATE RULES → TESTED RULES → 
  VALIDATED RULES → COMPRESSED AXIOMS → INSTINCTS

Each level is more compact and reliable than the last. An instinct triggers
in <1ms because it's a precomputed decision. A rule takes ~10ms because
it evaluates conditions. A pattern takes ~100ms because it needs context.

Memory hierarchy:
  Instincts  (< 100)    — Immediate reflexes, highest confidence
  Axioms     (< 500)    — Structural invariants
  Taboos     (< 200)    — Hard constraints
  Rules      (< 2000)   — Conditional heuristics
  Priors     (< 5000)   — Bayesian belief updates
"""

import time
import json
import hashlib
import threading
import statistics
import os
from typing import Dict, Any, List, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from pathlib import Path
import numpy as np

from .pattern_recognizer import Pattern, PatternType, PatternStrength
from .adaptive_optimizer import Optimization, OptimizationStatus, OptimizationStrategy


class RuleType(Enum):
    """Categories of distilled knowledge."""
    RULE = "rule"           # If-then heuristic
    PRIOR = "prior"         # Bayesian prior belief
    AXIOM = "axiom"         # Structural invariant
    TABOO = "taboo"         # Hard constraint (must not violate)
    INSTINCT = "instinct"   # Reflexive behavior (no deliberation)


class RuleConfidence(Enum):
    """Confidence level of a distilled rule."""
    SPECULATIVE = "speculative"    # Based on limited evidence
    PROBABLE = "probable"          # Moderate evidence
    CONFIDENT = "confident"        # Strong evidence
    CERTAIN = "certain"            # Overwhelming evidence, treated as fact


@dataclass
class DistilledRule:
    """A single piece of distilled knowledge."""
    id: str
    rule_type: RuleType
    confidence: RuleConfidence

    # The rule itself
    name: str
    description: str
    
    # Condition (when does this rule apply?)
    condition: Dict[str, Any]     # Structured condition
    condition_readable: str        # Human-readable condition

    # Action/conclusion (what does this rule say to do/believe?)
    action: Dict[str, Any]        # Structured action/conclusion
    action_readable: str           # Human-readable

    # Evidence
    supporting_patterns: List[str] = field(default_factory=list)  # Pattern IDs
    supporting_optimizations: List[str] = field(default_factory=list)  # Optimization IDs
    evidence_count: int = 0       # How many observations support this
    contradiction_count: int = 0  # How many observations contradict this

    # Performance
    times_triggered: int = 0
    times_correct: int = 0
    times_wrong: int = 0
    avg_outcome_when_followed: float = 0.0
    avg_outcome_when_violated: float = 0.0

    # Lifecycle
    created_at: float = field(default_factory=time.time)
    last_triggered: float = 0.0
    last_validated: float = 0.0
    version: int = 1               # Incremented when rule is refined

    # Scope
    applicable_components: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)

    @property
    def reliability(self) -> float:
        """How reliable is this rule? 0-1."""
        if self.times_triggered == 0:
            return 0.5  # Unknown
        accuracy = self.times_correct / self.times_triggered
        # Penalize for contradictions
        contradiction_penalty = self.contradiction_count / max(1, self.evidence_count) * 0.3
        return max(0.0, accuracy - contradiction_penalty)

    @property
    def utility(self) -> float:
        """How useful is this rule? Based on outcome differential."""
        if self.avg_outcome_when_followed == 0 and self.avg_outcome_when_violated == 0:
            return 0.5
        return max(0.0, min(1.0,
            (self.avg_outcome_when_followed - self.avg_outcome_when_violated + 1.0) / 2.0
        ))

    @property
    def maturity(self) -> float:
        """How mature/proven is this rule? 0-1."""
        evidence_factor = min(1.0, self.evidence_count / 100.0)
        trigger_factor = min(1.0, self.times_triggered / 50.0)
        age_factor = min(1.0, (time.time() - self.created_at) / 86400.0)  # Up to 1 day
        return (evidence_factor + trigger_factor + age_factor) / 3.0

    def evaluate_condition(self, context: Dict[str, Any]) -> bool:
        """Check if this rule's condition is met in the given context."""
        try:
            condition = self.condition
            
            # Simple condition evaluation
            for key, expected in condition.items():
                if key == "component" and "component" in context:
                    if context["component"] != expected:
                        return False
                elif key == "event_type" and "event_type" in context:
                    if context["event_type"] != expected:
                        return False
                elif key == "metric_above" and "metrics" in context:
                    metric_name, threshold = expected
                    if context["metrics"].get(metric_name, 0) <= threshold:
                        return False
                elif key == "metric_below" and "metrics" in context:
                    metric_name, threshold = expected
                    if context["metrics"].get(metric_name, float('inf')) >= threshold:
                        return False
                elif key == "state" and "state" in context:
                    if context["state"] != expected:
                        return False
                elif key == "sequence_detected" and "recent_sequence" in context:
                    if not self._sequence_matches(context["recent_sequence"], expected):
                        return False
                elif key == "time_since" and "timestamps" in context:
                    event_name, min_seconds = expected
                    last_time = context["timestamps"].get(event_name, 0)
                    if time.time() - last_time < min_seconds:
                        return False
            
            return True
        except (KeyError, TypeError, ValueError):
            return False

    def _sequence_matches(self, recent: List[str], expected: List[str]) -> bool:
        """Check if expected sequence appears in recent events."""
        if len(expected) > len(recent):
            return False
        for i in range(len(recent) - len(expected) + 1):
            if recent[i:i + len(expected)] == expected:
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "id": self.id,
            "rule_type": self.rule_type.value,
            "confidence": self.confidence.value,
            "name": self.name,
            "description": self.description,
            "condition": self.condition,
            "condition_readable": self.condition_readable,
            "action": self.action,
            "action_readable": self.action_readable,
            "supporting_patterns": self.supporting_patterns,
            "supporting_optimizations": self.supporting_optimizations,
            "evidence_count": self.evidence_count,
            "contradiction_count": self.contradiction_count,
            "times_triggered": self.times_triggered,
            "times_correct": self.times_correct,
            "times_wrong": self.times_wrong,
            "avg_outcome_when_followed": self.avg_outcome_when_followed,
            "avg_outcome_when_violated": self.avg_outcome_when_violated,
            "created_at": self.created_at,
            "last_triggered": self.last_triggered,
            "last_validated": self.last_validated,
            "version": self.version,
            "applicable_components": self.applicable_components,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DistilledRule":
        """Deserialize from persistence."""
        return cls(
            id=d["id"],
            rule_type=RuleType(d["rule_type"]),
            confidence=RuleConfidence(d["confidence"]),
            name=d["name"],
            description=d["description"],
            condition=d["condition"],
            condition_readable=d["condition_readable"],
            action=d["action"],
            action_readable=d["action_readable"],
            supporting_patterns=d.get("supporting_patterns", []),
            supporting_optimizations=d.get("supporting_optimizations", []),
            evidence_count=d.get("evidence_count", 0),
            contradiction_count=d.get("contradiction_count", 0),
            times_triggered=d.get("times_triggered", 0),
            times_correct=d.get("times_correct", 0),
            times_wrong=d.get("times_wrong", 0),
            avg_outcome_when_followed=d.get("avg_outcome_when_followed", 0.0),
            avg_outcome_when_violated=d.get("avg_outcome_when_violated", 0.0),
            created_at=d.get("created_at", time.time()),
            last_triggered=d.get("last_triggered", 0.0),
            last_validated=d.get("last_validated", 0.0),
            version=d.get("version", 1),
            applicable_components=d.get("applicable_components", []),
            tags=set(d.get("tags", [])),
        )


@dataclass
class KnowledgeBase:
    """The persistent knowledge store — Ultron's long-term wisdom."""
    rules: Dict[str, DistilledRule] = field(default_factory=dict)
    
    # Indices for fast lookup
    rules_by_type: Dict[RuleType, List[str]] = field(default_factory=lambda: defaultdict(list))
    rules_by_component: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    
    # Meta-knowledge
    total_distillations: int = 0
    total_refinements: int = 0
    total_deprecations: int = 0
    knowledge_version: int = 0
    last_saved: float = 0.0

    def add_rule(self, rule: DistilledRule):
        """Add a rule to the knowledge base."""
        self.rules[rule.id] = rule
        self.rules_by_type[rule.rule_type].append(rule.id)
        for comp in rule.applicable_components:
            self.rules_by_component[comp].append(rule.id)
        self.total_distillations += 1

    def remove_rule(self, rule_id: str):
        """Remove a rule from the knowledge base."""
        rule = self.rules.pop(rule_id, None)
        if rule:
            if rule_id in self.rules_by_type[rule.rule_type]:
                self.rules_by_type[rule.rule_type].remove(rule_id)
            for comp in rule.applicable_components:
                if rule_id in self.rules_by_component[comp]:
                    self.rules_by_component[comp].remove(rule_id)
            self.total_deprecations += 1

    def get_applicable_rules(self, context: Dict[str, Any]) -> List[DistilledRule]:
        """Get all rules that apply to a given context."""
        applicable = []
        
        # First filter by component if available
        component = context.get("component", "")
        candidate_ids = set()
        
        if component and component in self.rules_by_component:
            candidate_ids.update(self.rules_by_component[component])
        
        # Also check rules with no component restriction
        for rule in self.rules.values():
            if not rule.applicable_components:
                candidate_ids.add(rule.id)
        
        # If no component filter, check all
        if not component:
            candidate_ids = set(self.rules.keys())
        
        # Evaluate conditions
        for rule_id in candidate_ids:
            rule = self.rules.get(rule_id)
            if rule and rule.evaluate_condition(context):
                applicable.append(rule)
        
        # Sort by priority: instincts first, then by reliability
        type_priority = {
            RuleType.INSTINCT: 0,
            RuleType.TABOO: 1,
            RuleType.AXIOM: 2,
            RuleType.RULE: 3,
            RuleType.PRIOR: 4,
        }
        applicable.sort(key=lambda r: (type_priority.get(r.rule_type, 5), -r.reliability))
        
        return applicable

    @property
    def size(self) -> int:
        return len(self.rules)


class KnowledgeDistiller:
    """
    The wisdom engine — converts ephemeral experience into permanent knowledge.

    Runs periodically to:
    1. Identify patterns that have been confirmed enough times
    2. Identify optimizations that consistently work
    3. Distill these into compact rules
    4. Validate rules against new evidence
    5. Promote validated rules to higher confidence
    6. Deprecate rules that stop being accurate
    7. Persist the knowledge base to disk
    """

    def __init__(self,
                 knowledge_path: str,
                 min_evidence_for_rule: int = 10,
                 min_confidence_for_promotion: float = 0.8,
                 max_rules: int = 5000,
                 distillation_interval: float = 120.0,
                 save_interval: float = 300.0):
        """
        Args:
            knowledge_path: Directory to persist knowledge base
            min_evidence_for_rule: Minimum observations to create a rule
            min_confidence_for_promotion: Minimum accuracy to promote confidence
            max_rules: Maximum rules to maintain
            distillation_interval: Seconds between distillation cycles
            save_interval: Seconds between persistence saves
        """
        self.knowledge_path = Path(knowledge_path)
        self.knowledge_path.mkdir(parents=True, exist_ok=True)
        self.min_evidence = min_evidence_for_rule
        self.min_confidence = min_confidence_for_promotion
        self.max_rules = max_rules
        self.distillation_interval = distillation_interval
        self.save_interval = save_interval

        # The knowledge base
        self.kb = KnowledgeBase()

        # Load existing knowledge
        self._load_knowledge()

        # Pending distillations (patterns/optimizations waiting to be processed)
        self._pending_patterns: deque = deque(maxlen=1000)
        self._pending_optimizations: deque = deque(maxlen=500)

        # Rule validation queue
        self._validation_queue: deque = deque(maxlen=500)

        # Statistics
        self._distillation_cycles = 0
        self._rules_created_this_session = 0
        self._rules_promoted_this_session = 0
        self._rules_deprecated_this_session = 0

        # Concurrency
        self._lock = threading.RLock()
        self._running = False
        self._distill_thread: Optional[threading.Thread] = None
        self._save_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the knowledge distiller."""
        self._running = True
        
        self._distill_thread = threading.Thread(
            target=self._distillation_loop,
            daemon=True,
            name="KnowledgeDistiller-Distill"
        )
        self._distill_thread.start()

        self._save_thread = threading.Thread(
            target=self._save_loop,
            daemon=True,
            name="KnowledgeDistiller-Save"
        )
        self._save_thread.start()

        print(f"[KnowledgeDistiller] Started — {self.kb.size} rules loaded from disk")

    def stop(self):
        """Stop the distiller and save."""
        self._running = False
        if self._distill_thread:
            self._distill_thread.join(timeout=5.0)
        if self._save_thread:
            self._save_thread.join(timeout=5.0)
        self._save_knowledge()
        print(f"[KnowledgeDistiller] Stopped — {self.kb.size} rules persisted")

    # ═══════════════════════════════════════════════════════════════
    # INPUT: Feed patterns and optimizations for distillation
    # ═══════════════════════════════════════════════════════════════

    def submit_pattern(self, pattern: Pattern):
        """Submit a confirmed pattern for potential distillation into a rule."""
        if pattern.strength in (PatternStrength.ESTABLISHED, PatternStrength.LAW):
            self._pending_patterns.append(pattern)

    def submit_optimization(self, optimization: Optimization):
        """Submit a deployed optimization for potential distillation."""
        if optimization.status == OptimizationStatus.DEPLOYED:
            self._pending_optimizations.append(optimization)

    def submit_validation(self, rule_id: str, was_correct: bool, outcome: float):
        """Submit validation feedback for an existing rule."""
        self._validation_queue.append((rule_id, was_correct, outcome, time.time()))

    # ═══════════════════════════════════════════════════════════════
    # QUERY: Get knowledge for decision-making
    # ═══════════════════════════════════════════════════════════════

    def query_rules(self, context: Dict[str, Any]) -> List[DistilledRule]:
        """
        Get all applicable rules for a given context.
        
        This is the primary interface for the autonomy loop to
        consult accumulated wisdom before making decisions.
        """
        rules = self.kb.get_applicable_rules(context)
        
        # Update trigger counts
        for rule in rules:
            rule.times_triggered += 1
            rule.last_triggered = time.time()
        
        return rules

    def get_instincts(self) -> List[DistilledRule]:
        """Get all instinct-level rules (fastest reactions)."""
        return [
            self.kb.rules[rid]
            for rid in self.kb.rules_by_type.get(RuleType.INSTINCT, [])
            if rid in self.kb.rules
        ]

    def get_taboos(self) -> List[DistilledRule]:
        """Get all taboo rules (hard constraints)."""
        return [
            self.kb.rules[rid]
            for rid in self.kb.rules_by_type.get(RuleType.TABOO, [])
            if rid in self.kb.rules
        ]

    def get_priors(self, component: str = None) -> List[DistilledRule]:
        """Get prior beliefs, optionally filtered by component."""
        priors = [
            self.kb.rules[rid]
            for rid in self.kb.rules_by_type.get(RuleType.PRIOR, [])
            if rid in self.kb.rules
        ]
        if component:
            priors = [p for p in priors if component in p.applicable_components or not p.applicable_components]
        return priors

    # ═══════════════════════════════════════════════════════════════
    # DISTILLATION ENGINE
    # ═══════════════════════════════════════════════════════════════

    def _distillation_loop(self):
        """Background thread: periodic distillation."""
        while self._running:
            time.sleep(self.distillation_interval)
            self._run_distillation_cycle()

    def _run_distillation_cycle(self):
        """Execute one distillation cycle."""
        self._distillation_cycles += 1

        # 1. Distill patterns into rules
        self._distill_patterns()

        # 2. Distill optimizations into rules
        self._distill_optimizations()

        # 3. Process validation feedback
        self._process_validations()

        # 4. Promote/demote rules based on performance
        self._update_rule_confidence()

        # 5. Compress: merge similar rules
        self._compress_rules()

        # 6. Prune: remove unreliable rules
        self._prune_rules()

        # 7. Promote best rules to instincts
        self._promote_to_instincts()

    def _distill_patterns(self):
        """Convert confirmed patterns into rules."""
        processed = 0
        while self._pending_patterns and processed < 50:
            pattern = self._pending_patterns.popleft()
            processed += 1

            # Check if we already have a rule for this pattern
            existing_rule_id = self._find_existing_rule_for_pattern(pattern.id)
            if existing_rule_id:
                # Update existing rule
                rule = self.kb.rules[existing_rule_id]
                rule.evidence_count += pattern.occurrences
                rule.last_validated = time.time()
                continue

            # Create new rule from pattern
            rule = self._pattern_to_rule(pattern)
            if rule:
                self.kb.add_rule(rule)
                self._rules_created_this_session += 1

    def _distill_optimizations(self):
        """Convert proven optimizations into rules."""
        processed = 0
        while self._pending_optimizations and processed < 20:
            opt = self._pending_optimizations.popleft()
            processed += 1

            # Only distill optimizations with significant improvement
            if opt.actual_improvement < 0.05:
                continue

            rule = self._optimization_to_rule(opt)
            if rule:
                self.kb.add_rule(rule)
                self._rules_created_this_session += 1

    def _process_validations(self):
        """Process validation feedback to update rule accuracy."""
        processed = 0
        while self._validation_queue and processed < 100:
            rule_id, was_correct, outcome, timestamp = self._validation_queue.popleft()
            processed += 1

            rule = self.kb.rules.get(rule_id)
            if not rule:
                continue

            if was_correct:
                rule.times_correct += 1
                # Update outcome average (exponential moving average)
                alpha = 0.1
                rule.avg_outcome_when_followed = (
                    rule.avg_outcome_when_followed * (1 - alpha) + outcome * alpha
                )
            else:
                rule.times_wrong += 1
                rule.contradiction_count += 1
                rule.avg_outcome_when_violated = (
                    rule.avg_outcome_when_violated * (1 - alpha) + outcome * alpha
                )

    def _update_rule_confidence(self):
        """Promote or demote rules based on accumulated evidence."""
        for rule in self.kb.rules.values():
            reliability = rule.reliability
            maturity = rule.maturity

            # Promote confidence
            if reliability > 0.9 and maturity > 0.7:
                if rule.confidence != RuleConfidence.CERTAIN:
                    rule.confidence = RuleConfidence.CERTAIN
                    self._rules_promoted_this_session += 1
            elif reliability > 0.75 and maturity > 0.5:
                if rule.confidence == RuleConfidence.SPECULATIVE:
                    rule.confidence = RuleConfidence.PROBABLE
                    self._rules_promoted_this_session += 1
                elif rule.confidence == RuleConfidence.PROBABLE:
                    rule.confidence = RuleConfidence.CONFIDENT
                    self._rules_promoted_this_session += 1

            # Demote if contradicted too much
            if rule.contradiction_count > rule.evidence_count * 0.4:
                if rule.confidence == RuleConfidence.CERTAIN:
                    rule.confidence = RuleConfidence.CONFIDENT
                elif rule.confidence == RuleConfidence.CONFIDENT:
                    rule.confidence = RuleConfidence.PROBABLE

    def _compress_rules(self):
        """Merge similar rules into more general ones."""
        # Find rules with similar conditions and actions
        rules_list = list(self.kb.rules.values())
        merged = set()

        for i, rule_a in enumerate(rules_list):
            if rule_a.id in merged:
                continue
            for rule_b in rules_list[i + 1:]:
                if rule_b.id in merged:
                    continue
                
                if self._rules_are_similar(rule_a, rule_b):
                    # Merge B into A
                    self._merge_rules(rule_a, rule_b)
                    merged.add(rule_b.id)

        # Remove merged rules
        for rule_id in merged:
            self.kb.remove_rule(rule_id)

    def _prune_rules(self):
        """Remove unreliable or unused rules."""
        to_remove = []

        for rule_id, rule in self.kb.rules.items():
            # Remove rules that are consistently wrong
            if rule.times_triggered > 20 and rule.reliability < 0.3:
                to_remove.append(rule_id)
                continue

            # Remove very old rules that were never triggered
            age_days = (time.time() - rule.created_at) / 86400.0
            if age_days > 7 and rule.times_triggered == 0:
                to_remove.append(rule_id)
                continue

            # Remove speculative rules that never got evidence
            if (rule.confidence == RuleConfidence.SPECULATIVE and
                    age_days > 2 and rule.evidence_count < self.min_evidence):
                to_remove.append(rule_id)

        for rule_id in to_remove:
            self.kb.remove_rule(rule_id)
            self._rules_deprecated_this_session += 1

        # Also cap total rules
        if self.kb.size > self.max_rules:
            # Remove lowest-utility rules
            sorted_rules = sorted(
                self.kb.rules.items(),
                key=lambda x: x[1].utility * x[1].reliability
            )
            excess = self.kb.size - self.max_rules
            for rule_id, _ in sorted_rules[:excess]:
                self.kb.remove_rule(rule_id)
                self._rules_deprecated_this_session += 1

    def _promote_to_instincts(self):
        """Promote the most reliable, most used rules to instinct level."""
        # Instincts are the cream of the crop — extremely reliable,
        # frequently used, and time-tested
        
        max_instincts = 100
        current_instincts = len(self.kb.rules_by_type.get(RuleType.INSTINCT, []))

        if current_instincts >= max_instincts:
            return

        candidates = [
            rule for rule in self.kb.rules.values()
            if (rule.rule_type == RuleType.RULE and
                rule.confidence == RuleConfidence.CERTAIN and
                rule.reliability > 0.95 and
                rule.times_triggered > 100 and
                rule.utility > 0.7)
        ]

        # Promote top candidates
        candidates.sort(key=lambda r: r.reliability * r.utility, reverse=True)
        
        for rule in candidates[:max_instincts - current_instincts]:
            rule.rule_type = RuleType.INSTINCT
            # Rebuild indices
            if rule.id in self.kb.rules_by_type.get(RuleType.RULE, []):
                self.kb.rules_by_type[RuleType.RULE].remove(rule.id)
            self.kb.rules_by_type[RuleType.INSTINCT].append(rule.id)

    # ═══════════════════════════════════════════════════════════════
    # RULE CREATION HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _pattern_to_rule(self, pattern: Pattern) -> Optional[DistilledRule]:
        """Convert a pattern into a distilled rule."""
        rule_id = hashlib.md5(f"rule:pattern:{pattern.id}".encode()).hexdigest()[:14]

        # Determine rule type based on pattern type
        if pattern.pattern_type == PatternType.ANTI_PATTERN:
            rule_type = RuleType.TABOO
            action = {
                "type": "avoid",
                "sequence_to_avoid": pattern.sequence,
                "alternative": "interrupt_at_step_2",
            }
            action_readable = f"AVOID this sequence: {' → '.join(pattern.sequence[:4])}"
        elif pattern.pattern_type == PatternType.TEMPORAL_SEQUENCE and pattern.outcome > 0.5:
            rule_type = RuleType.RULE
            action = {
                "type": "replicate",
                "sequence_to_follow": pattern.sequence,
                "expected_outcome": pattern.outcome,
            }
            action_readable = f"REPLICATE this sequence: {' → '.join(pattern.sequence[:4])}"
        elif pattern.pattern_type == PatternType.BOTTLENECK:
            rule_type = RuleType.AXIOM
            action = {
                "type": "know",
                "fact": f"{pattern.components_involved[0] if pattern.components_involved else 'unknown'} is a bottleneck",
                "mitigation": "add_caching_or_reduce_load",
            }
            action_readable = f"KNOW: {pattern.description}"
        elif pattern.pattern_type == PatternType.PHASE_TRANSITION:
            rule_type = RuleType.PRIOR
            action = {
                "type": "expect",
                "phenomenon": "phase_transition",
                "conditions": pattern.conditions,
            }
            action_readable = f"EXPECT phase transition under these conditions"
        else:
            rule_type = RuleType.RULE
            action = {
                "type": "note",
                "pattern": pattern.sequence,
                "outcome": pattern.outcome,
            }
            action_readable = f"Pattern: {pattern.description[:60]}"

        # Build condition
        condition = {
            "sequence_detected": pattern.sequence[:3] if len(pattern.sequence) > 3 else pattern.sequence,
        }
        if pattern.components_involved:
            condition["component"] = pattern.components_involved[0]

        condition_readable = (
            f"When sequence [{' → '.join(pattern.sequence[:3])}] is detected"
            + (f" in {pattern.components_involved[0]}" if pattern.components_involved else "")
        )

        return DistilledRule(
            id=rule_id,
            rule_type=rule_type,
            confidence=RuleConfidence.PROBABLE if pattern.strength == PatternStrength.LAW
                      else RuleConfidence.SPECULATIVE,
            name=f"Pattern-{pattern.pattern_type.value}-{rule_id[:6]}",
            description=pattern.description,
            condition=condition,
            condition_readable=condition_readable,
            action=action,
            action_readable=action_readable,
            supporting_patterns=[pattern.id],
            evidence_count=pattern.occurrences,
            applicable_components=pattern.components_involved,
            tags=pattern.tags | {"distilled_from_pattern"},
        )

    def _optimization_to_rule(self, opt: Optimization) -> Optional[DistilledRule]:
        """Convert a proven optimization into a distilled rule."""
        rule_id = hashlib.md5(f"rule:opt:{opt.id}".encode()).hexdigest()[:14]

        # Create a rule that says "apply this optimization when similar conditions arise"
        condition = {
            "component": opt.target_component,
            "similar_state": True,
        }
        condition_readable = f"When {opt.target_component} is in similar state to when optimization was proven"

        action = {
            "type": "apply_optimization",
            "strategy": opt.strategy.value,
            "parameters": opt.change_spec.get("parameters", {}),
            "expected_improvement": opt.actual_improvement,
        }
        action_readable = f"Apply {opt.strategy.value}: {opt.description[:50]}"

        return DistilledRule(
            id=rule_id,
            rule_type=RuleType.RULE,
            confidence=RuleConfidence.CONFIDENT if opt.actual_improvement > 0.1
                      else RuleConfidence.PROBABLE,
            name=f"Optimization-{opt.strategy.value}-{rule_id[:6]}",
            description=f"Proven optimization: {opt.description}",
            condition=condition,
            condition_readable=condition_readable,
            action=action,
            action_readable=action_readable,
            supporting_optimizations=[opt.id],
            evidence_count=opt.samples_collected,
            avg_outcome_when_followed=opt.actual_improvement,
            applicable_components=[opt.target_component],
            tags={opt.strategy.value, "distilled_from_optimization"},
        )

    def _find_existing_rule_for_pattern(self, pattern_id: str) -> Optional[str]:
        """Check if a rule already exists for a given pattern."""
        for rule_id, rule in self.kb.rules.items():
            if pattern_id in rule.supporting_patterns:
                return rule_id
        return None

    def _rules_are_similar(self, a: DistilledRule, b: DistilledRule) -> bool:
        """Check if two rules are similar enough to merge."""
        # Same type
        if a.rule_type != b.rule_type:
            return False
        # Same components
        if set(a.applicable_components) != set(b.applicable_components):
            return False
        # Similar conditions (simplified check)
        if a.condition == b.condition:
            return True
        # Similar actions
        if a.action.get("type") == b.action.get("type"):
            if a.action.get("strategy") == b.action.get("strategy"):
                return True
        return False

    def _merge_rules(self, target: DistilledRule, source: DistilledRule):
        """Merge source rule into target rule."""
        target.evidence_count += source.evidence_count
        target.times_triggered += source.times_triggered
        target.times_correct += source.times_correct
        target.times_wrong += source.times_wrong
        target.supporting_patterns.extend(source.supporting_patterns)
        target.supporting_optimizations.extend(source.supporting_optimizations)
        target.tags.update(source.tags)
        target.version += 1
        self.kb.total_refinements += 1

    # ═══════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════

    def _save_loop(self):
        """Background thread: periodic saves."""
        while self._running:
            time.sleep(self.save_interval)
            self._save_knowledge()

    def _save_knowledge(self):
        """Persist the knowledge base to disk."""
        filepath = self.knowledge_path / "knowledge_base.json"
        
        data = {
            "version": self.kb.knowledge_version,
            "saved_at": time.time(),
            "total_rules": self.kb.size,
            "total_distillations": self.kb.total_distillations,
            "total_refinements": self.kb.total_refinements,
            "total_deprecations": self.kb.total_deprecations,
            "rules": {
                rule_id: rule.to_dict()
                for rule_id, rule in self.kb.rules.items()
            },
        }

        # Write atomically (write to temp, then rename)
        temp_path = filepath.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            temp_path.rename(filepath)
            self.kb.last_saved = time.time()
            self.kb.knowledge_version += 1
        except IOError as e:
            print(f"[KnowledgeDistiller] Save failed: {e}")

        # Also save a summary for quick inspection
        summary_path = self.knowledge_path / "knowledge_summary.json"
        try:
            summary = self.get_status()
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)
        except IOError:
            pass

    def _load_knowledge(self):
        """Load the knowledge base from disk."""
        filepath = self.knowledge_path / "knowledge_base.json"
        
        if not filepath.exists():
            print("[KnowledgeDistiller] No existing knowledge base — starting fresh")
            return

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            for rule_id, rule_data in data.get("rules", {}).items():
                rule = DistilledRule.from_dict(rule_data)
                self.kb.add_rule(rule)

            self.kb.knowledge_version = data.get("version", 0)
            self.kb.total_distillations = data.get("total_distillations", 0)
            self.kb.total_refinements = data.get("total_refinements", 0)
            self.kb.total_deprecations = data.get("total_deprecations", 0)

            print(f"[KnowledgeDistiller] Loaded {self.kb.size} rules (v{self.kb.knowledge_version})")

        except (IOError, json.JSONDecodeError, KeyError) as e:
            print(f"[KnowledgeDistiller] Failed to load knowledge: {e}")

    # ═══════════════════════════════════════════════════════════════
    # STATUS AND REPORTING
    # ═══════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get distiller status and knowledge statistics."""
        type_counts = {
            rt.value: len(ids)
            for rt, ids in self.kb.rules_by_type.items()
        }

        confidence_counts = defaultdict(int)
        reliability_scores = []
        for rule in self.kb.rules.values():
            confidence_counts[rule.confidence.value] += 1
            if rule.times_triggered > 0:
                reliability_scores.append(rule.reliability)

        return {
            "knowledge_base": {
                "total_rules": self.kb.size,
                "version": self.kb.knowledge_version,
                "last_saved": self.kb.last_saved,
                "by_type": type_counts,
                "by_confidence": dict(confidence_counts),
                "avg_reliability": statistics.mean(reliability_scores) if reliability_scores else 0.0,
            },
            "session_stats": {
                "distillation_cycles": self._distillation_cycles,
                "rules_created": self._rules_created_this_session,
                "rules_promoted": self._rules_promoted_this_session,
                "rules_deprecated": self._rules_deprecated_this_session,
            },
            "pending": {
                "patterns": len(self._pending_patterns),
                "optimizations": len(self._pending_optimizations),
                "validations": len(self._validation_queue),
            },
            "lifetime_stats": {
                "total_distillations": self.kb.total_distillations,
                "total_refinements": self.kb.total_refinements,
                "total_deprecations": self.kb.total_deprecations,
            },
            "top_rules": [
                {
                    "name": rule.name,
                    "type": rule.rule_type.value,
                    "reliability": rule.reliability,
                    "utility": rule.utility,
                    "triggered": rule.times_triggered,
                }
                for rule in sorted(
                    self.kb.rules.values(),
                    key=lambda r: r.reliability * r.utility,
                    reverse=True
                )[:10]
            ],
        }
