"""
Pattern Recognizer — The Analytical Cortex of Self-Learning.

Takes raw execution traces from the ExperienceCollector and discovers
MEANING in them. This is where Ultron develops intuition about itself.

What it discovers:
  - Temporal patterns: "Action A always precedes outcome B"
  - Anti-patterns: "When X happens, failure follows 80% of the time"
  - Causal chains: "The sequence A→B→C reliably produces outcome D"
  - Correlations: "Component X slows down when Y is under load"
  - Resonance: "These two unrelated components improve together"
  - Decay patterns: "Performance degrades after N hours without consolidation"
  - Emergence: "New capability appeared from combination of patterns"

The recognizer uses multiple analysis strategies:
  1. Sequential pattern mining (frequent subsequence extraction)
  2. Temporal correlation (cross-correlation of time series)
  3. Causal inference (Granger causality + intervention testing)
  4. Anomaly clustering (group similar failures/successes)
  5. Graph analysis (find critical paths in causal graphs)

This module doesn't just find patterns — it RANKS them by:
  - Predictive power (how reliably does the pattern predict an outcome?)
  - Actionability (can the system do something about this?)
  - Impact (how much would acting on this pattern improve things?)
  - Novelty (is this something we haven't seen before?)
"""

import time
import threading
import hashlib
import statistics
import math
from typing import Dict, Any, List, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, Counter, deque
from itertools import combinations
import numpy as np

from .experience_collector import (
    ExperienceCollector, TraceEvent, ExecutionTrace, EventType
)


class PatternType(Enum):
    """Categories of discovered patterns."""
    TEMPORAL_SEQUENCE = "temporal_sequence"     # A then B then C
    CAUSAL_CHAIN = "causal_chain"              # A causes B causes C
    ANTI_PATTERN = "anti_pattern"              # This sequence predicts failure
    CORRELATION = "correlation"                 # X and Y move together
    RESONANCE = "resonance"                    # Unrelated improvements co-occur
    DECAY = "decay"                            # Performance degrades over time
    BOTTLENECK = "bottleneck"                  # One component limits others
    RECOVERY = "recovery"                      # How system recovers from failures
    EMERGENCE = "emergence"                    # New capability from combinations
    CYCLE = "cycle"                            # Repeating behavioral loops
    PHASE_TRANSITION = "phase_transition"       # Sudden capability jumps


class PatternStrength(Enum):
    """How strong/reliable a pattern is."""
    HYPOTHESIS = "hypothesis"     # Seen 2-5 times
    EMERGING = "emerging"         # Seen 5-20 times, moderate confidence
    ESTABLISHED = "established"   # Seen 20+ times, high confidence
    LAW = "law"                   # Seen 100+ times, near-certain


@dataclass
class Pattern:
    """A discovered behavioral pattern in the system."""
    id: str
    pattern_type: PatternType
    strength: PatternStrength
    description: str

    # The pattern itself
    sequence: List[str]            # Event types / component names in order
    conditions: Dict[str, Any]     # When does this pattern occur?
    outcome: float                 # Expected outcome when pattern occurs (-1 to 1)

    # Statistics
    occurrences: int = 0
    confidence: float = 0.0        # How reliably this pattern predicts outcome
    predictive_power: float = 0.0  # Correlation between pattern and outcome
    actionability: float = 0.0     # Can we influence this pattern? (0-1)
    impact: float = 0.0            # How much improvement would acting on this yield?
    novelty: float = 1.0           # How new is this? (decays over time)

    # Temporal
    first_seen: float = 0.0
    last_seen: float = 0.0
    avg_interval: float = 0.0     # Average time between occurrences

    # Metadata
    components_involved: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    related_patterns: List[str] = field(default_factory=list)  # IDs

    @property
    def score(self) -> float:
        """Composite score for ranking patterns."""
        return (
            self.predictive_power * 0.3 +
            self.actionability * 0.25 +
            self.impact * 0.25 +
            self.novelty * 0.1 +
            self.confidence * 0.1
        )

    @property
    def age_hours(self) -> float:
        if self.first_seen == 0:
            return 0.0
        return (time.time() - self.first_seen) / 3600.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.pattern_type.value,
            "strength": self.strength.value,
            "description": self.description,
            "sequence": self.sequence,
            "conditions": self.conditions,
            "outcome": self.outcome,
            "occurrences": self.occurrences,
            "confidence": self.confidence,
            "score": self.score,
            "components": self.components_involved,
        }


@dataclass
class CausalChain:
    """A discovered causal relationship: A → B → C → Outcome."""
    id: str
    chain: List[Tuple[str, str]]   # [(event_type, component), ...]
    outcome: float                 # What this chain leads to
    strength: float                # How reliable (0-1)
    observed_count: int = 0
    avg_latency_ms: float = 0.0   # Typical time from start to outcome
    interventions: List[str] = field(default_factory=list)  # Where to break/boost

    @property
    def length(self) -> int:
        return len(self.chain)

    def can_intervene_at(self, index: int) -> bool:
        """Check if intervention is possible at a step in the chain."""
        return index < len(self.chain) and index in range(len(self.interventions))


@dataclass 
class TemporalCorrelation:
    """A time-lagged correlation between two metrics."""
    metric_a: str
    metric_b: str
    lag_seconds: float            # B happens this long after A
    correlation: float            # Pearson correlation (-1 to 1)
    samples: int
    direction: str                # "positive", "negative", "bidirectional"


@dataclass
class AnomalyCluster:
    """A cluster of similar anomalous behaviors."""
    cluster_id: str
    pattern_type: str             # "failure", "success", "unusual"
    centroid: List[float]         # Average feature vector
    members: List[str]            # Event IDs in this cluster
    frequency: float              # How often this cluster appears (per hour)
    severity: float               # Average severity of members
    common_components: List[str]  # Components most often involved
    common_precursors: List[str]  # What typically comes before


class PatternRecognizer:
    """
    The pattern discovery engine.

    Continuously analyzes execution traces to find actionable patterns
    that the system can use to improve itself.

    Works in three modes:
    - PASSIVE: Observes and accumulates statistics
    - ACTIVE: Actively searches for specific pattern types
    - HUNTING: Focused deep search triggered by anomalies
    """

    def __init__(self,
                 experience_collector: ExperienceCollector,
                 min_pattern_occurrences: int = 3,
                 min_confidence: float = 0.6,
                 max_patterns: int = 5000,
                 analysis_interval: float = 30.0):
        """
        Args:
            experience_collector: The experience source
            min_pattern_occurrences: Minimum times a pattern must occur
            min_confidence: Minimum confidence to report a pattern
            max_patterns: Maximum patterns to maintain
            analysis_interval: Seconds between analysis cycles
        """
        self.collector = experience_collector
        self.min_occurrences = min_pattern_occurrences
        self.min_confidence = min_confidence
        self.max_patterns = max_patterns
        self.analysis_interval = analysis_interval

        # Discovered patterns
        self._patterns: Dict[str, Pattern] = {}
        self._causal_chains: Dict[str, CausalChain] = {}
        self._correlations: List[TemporalCorrelation] = []
        self._anomaly_clusters: Dict[str, AnomalyCluster] = {}

        # Pattern mining state
        self._sequence_counts: Dict[tuple, int] = defaultdict(int)
        self._outcome_by_sequence: Dict[tuple, List[float]] = defaultdict(list)
        self._component_cooccurrence: Dict[tuple, int] = defaultdict(int)
        self._transition_matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Time series for correlation analysis
        self._metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))

        # Analysis counters
        self._analysis_cycles = 0
        self._patterns_discovered = 0
        self._patterns_promoted = 0
        self._patterns_deprecated = 0

        # Concurrency
        self._lock = threading.RLock()
        self._running = False
        self._analysis_thread: Optional[threading.Thread] = None

        # Register as listener on the collector
        self.collector.on_any_event(self._on_event)

    def start(self):
        """Start the pattern recognition engine."""
        self._running = True
        self._analysis_thread = threading.Thread(
            target=self._analysis_loop,
            daemon=True,
            name="PatternRecognizer-Analysis"
        )
        self._analysis_thread.start()
        print("[PatternRecognizer] Started — searching for patterns in experience")

    def stop(self):
        """Stop pattern recognition."""
        self._running = False
        if self._analysis_thread:
            self._analysis_thread.join(timeout=5.0)
        print(f"[PatternRecognizer] Stopped — {self._patterns_discovered} patterns found")

    # ═══════════════════════════════════════════════════════════════
    # REAL-TIME EVENT PROCESSING
    # ═══════════════════════════════════════════════════════════════

    def _on_event(self, event: TraceEvent):
        """Called for every event — maintains running statistics."""
        # Update transition matrix (Markov chain of events)
        # This tracks "what usually follows what"
        event_key = f"{event.event_type.value}:{event.component}"

        # Record metric for time series
        if event.outcome is not None:
            self._metric_history[f"outcome:{event.component}"].append(
                (event.timestamp, event.outcome)
            )
        if event.duration_us is not None:
            self._metric_history[f"latency:{event.component}"].append(
                (event.timestamp, event.duration_us)
            )

        # Update co-occurrence matrix
        # (which components tend to be active together?)
        recent = self.collector.query_events(
            since=event.timestamp - 1.0,  # Within 1 second
            limit=20
        )
        for other in recent:
            if other.id != event.id:
                pair = tuple(sorted([event.component, other.component]))
                self._component_cooccurrence[pair] += 1

        # Track transitions
        for parent_id in event.causality:
            # Find the parent event's type
            parent_events = self.collector.query_events(limit=50)
            for pe in parent_events:
                if pe.id == parent_id:
                    parent_key = f"{pe.event_type.value}:{pe.component}"
                    self._transition_matrix[parent_key][event_key] += 1
                    break

    # ═══════════════════════════════════════════════════════════════
    # ANALYSIS ENGINE — runs periodically
    # ═══════════════════════════════════════════════════════════════

    def _analysis_loop(self):
        """Background thread: periodic deep analysis."""
        while self._running:
            time.sleep(self.analysis_interval)
            self._run_analysis_cycle()

    def _run_analysis_cycle(self):
        """Execute one complete analysis cycle."""
        self._analysis_cycles += 1

        # 1. Mine sequential patterns from recent traces
        self._mine_sequential_patterns()

        # 2. Detect causal chains
        self._detect_causal_chains()

        # 3. Find temporal correlations
        self._find_temporal_correlations()

        # 4. Cluster anomalies
        self._cluster_anomalies()

        # 5. Detect behavioral cycles
        self._detect_cycles()

        # 6. Look for phase transitions
        self._detect_phase_transitions()

        # 7. Update pattern strengths and prune weak ones
        self._update_pattern_strengths()
        self._prune_weak_patterns()

        # 8. Discover emergent patterns (combinations of existing patterns)
        self._detect_emergence()

    # ═══════════════════════════════════════════════════════════════
    # PATTERN MINING STRATEGIES
    # ═══════════════════════════════════════════════════════════════

    def _mine_sequential_patterns(self):
        """
        Find frequent subsequences in execution traces.

        Uses a sliding window approach over recent traces to find
        event sequences that occur more than chance would predict.
        """
        # Get recent completed traces
        traces = self.collector.query_traces(limit=200, min_events=3)

        for trace in traces:
            events = trace.events
            if len(events) < 2:
                continue

            # Extract subsequences of length 2-5
            for window_size in range(2, min(6, len(events) + 1)):
                for i in range(len(events) - window_size + 1):
                    window = events[i:i + window_size]
                    
                    # Create a signature for this sequence
                    seq_key = tuple(
                        f"{e.event_type.value}:{e.component}" for e in window
                    )
                    
                    self._sequence_counts[seq_key] += 1
                    
                    # Track outcome associated with this sequence
                    # Use the trace's overall outcome or last event's outcome
                    outcome = trace.total_outcome
                    if window[-1].outcome is not None:
                        outcome = window[-1].outcome
                    self._outcome_by_sequence[seq_key].append(outcome)

        # Identify sequences that occur frequently
        for seq_key, count in self._sequence_counts.items():
            if count < self.min_occurrences:
                continue

            outcomes = self._outcome_by_sequence.get(seq_key, [])
            if not outcomes:
                continue

            avg_outcome = statistics.mean(outcomes)
            outcome_std = statistics.stdev(outcomes) if len(outcomes) > 1 else 0.5

            # Calculate confidence (low std = high confidence)
            confidence = max(0.0, 1.0 - outcome_std)

            if confidence < self.min_confidence:
                continue

            # Determine pattern type
            if avg_outcome < -0.3:
                pattern_type = PatternType.ANTI_PATTERN
            elif avg_outcome > 0.3:
                pattern_type = PatternType.TEMPORAL_SEQUENCE
            else:
                continue  # Neutral sequences aren't interesting

            # Create or update pattern
            pattern_id = hashlib.md5(str(seq_key).encode()).hexdigest()[:12]

            if pattern_id not in self._patterns:
                # Determine strength
                if count >= 100:
                    strength = PatternStrength.LAW
                elif count >= 20:
                    strength = PatternStrength.ESTABLISHED
                elif count >= 5:
                    strength = PatternStrength.EMERGING
                else:
                    strength = PatternStrength.HYPOTHESIS

                # Extract components involved
                components = list(set(
                    s.split(":")[1] for s in seq_key if ":" in s
                ))

                pattern = Pattern(
                    id=pattern_id,
                    pattern_type=pattern_type,
                    strength=strength,
                    description=self._describe_sequence(seq_key, avg_outcome),
                    sequence=list(seq_key),
                    conditions={"min_occurrences": count},
                    outcome=avg_outcome,
                    occurrences=count,
                    confidence=confidence,
                    predictive_power=abs(avg_outcome) * confidence,
                    actionability=self._assess_actionability(seq_key),
                    impact=abs(avg_outcome) * count / 100.0,
                    first_seen=time.time(),
                    last_seen=time.time(),
                    components_involved=components,
                    tags={"sequential", pattern_type.value},
                )

                self._patterns[pattern_id] = pattern
                self._patterns_discovered += 1

            else:
                # Update existing pattern
                existing = self._patterns[pattern_id]
                existing.occurrences = count
                existing.confidence = confidence
                existing.last_seen = time.time()
                existing.predictive_power = abs(avg_outcome) * confidence
                existing.novelty = max(0.0, existing.novelty - 0.01)  # Decay novelty

    def _detect_causal_chains(self):
        """
        Discover causal chains by following causality links in events.

        A causal chain is a sequence where each event explicitly
        lists its predecessor as a cause.
        """
        # Get events with causal links
        events_with_causes = self.collector.query_events(limit=5000)
        events_with_causes = [e for e in events_with_causes if e.causality]

        # Build causal graph
        causal_graph: Dict[str, List[str]] = defaultdict(list)
        event_map: Dict[str, TraceEvent] = {}

        for event in events_with_causes:
            event_map[event.id] = event
            for cause_id in event.causality:
                causal_graph[cause_id].append(event.id)

        # Find chains (DFS from events without causes)
        root_events = [
            e for e in events_with_causes
            if not any(e.id in graph_entry for graph_entry in causal_graph.values())
        ]

        chains_found = []
        for root in root_events[:100]:  # Limit to prevent explosion
            chain = self._trace_causal_chain(root.id, causal_graph, event_map, max_depth=8)
            if len(chain) >= 3:
                chains_found.append(chain)

        # Aggregate similar chains
        for chain_events in chains_found:
            chain_signature = tuple(
                (e.event_type.value, e.component) for e in chain_events
            )
            chain_id = hashlib.md5(str(chain_signature).encode()).hexdigest()[:12]

            # Calculate chain outcome (last event's outcome or sum)
            chain_outcome = sum(
                e.outcome for e in chain_events if e.outcome is not None
            )

            # Calculate average latency
            if len(chain_events) >= 2:
                latency = (chain_events[-1].timestamp - chain_events[0].timestamp) * 1000
            else:
                latency = 0.0

            if chain_id in self._causal_chains:
                existing = self._causal_chains[chain_id]
                existing.observed_count += 1
                existing.strength = min(1.0, existing.observed_count / 50.0)
                existing.avg_latency_ms = (
                    existing.avg_latency_ms * 0.9 + latency * 0.1
                )
            else:
                self._causal_chains[chain_id] = CausalChain(
                    id=chain_id,
                    chain=list(chain_signature),
                    outcome=chain_outcome,
                    strength=0.1,
                    observed_count=1,
                    avg_latency_ms=latency,
                    interventions=self._find_intervention_points(chain_events),
                )

    def _find_temporal_correlations(self):
        """
        Find time-lagged correlations between component metrics.

        Example: "Neural mesh latency increases 5 seconds before
        meta-learning performance drops"
        """
        self._correlations.clear()

        metric_names = list(self._metric_history.keys())
        if len(metric_names) < 2:
            return

        # Check pairs of metrics for correlation at various lags
        for i, metric_a in enumerate(metric_names):
            for metric_b in metric_names[i + 1:]:
                series_a = list(self._metric_history[metric_a])
                series_b = list(self._metric_history[metric_b])

                if len(series_a) < 20 or len(series_b) < 20:
                    continue

                # Try different time lags (0.5s, 1s, 2s, 5s, 10s)
                for lag in [0.5, 1.0, 2.0, 5.0, 10.0]:
                    corr = self._compute_lagged_correlation(series_a, series_b, lag)
                    if corr is not None and abs(corr) > 0.5:
                        direction = "positive" if corr > 0 else "negative"
                        self._correlations.append(TemporalCorrelation(
                            metric_a=metric_a,
                            metric_b=metric_b,
                            lag_seconds=lag,
                            correlation=corr,
                            samples=min(len(series_a), len(series_b)),
                            direction=direction,
                        ))

    def _cluster_anomalies(self):
        """
        Group similar anomalous events into clusters.

        This helps identify recurring types of failures vs. one-off issues.
        """
        # Get failure events
        failures = self.collector.query_events(
            event_types=[EventType.ERROR_OCCURRED, EventType.PATCH_REVERTED],
            limit=500,
        )

        if len(failures) < 5:
            return

        # Simple clustering by component + error type
        clusters: Dict[str, List[TraceEvent]] = defaultdict(list)

        for event in failures:
            cluster_key = f"{event.component}:{event.data.get('error_type', 'unknown')}"
            clusters[cluster_key].append(event)

        for key, events in clusters.items():
            if len(events) < 2:
                continue

            cluster_id = hashlib.md5(key.encode()).hexdigest()[:10]

            # Find common precursors (what happens before these failures)
            precursors: Counter = Counter()
            for event in events:
                # Look at events just before this one
                before = self.collector.query_events(
                    until=event.timestamp,
                    since=event.timestamp - 5.0,
                    limit=5,
                )
                for pre in before:
                    if pre.id != event.id:
                        precursors[f"{pre.event_type.value}:{pre.component}"] += 1

            common_precursors = [p for p, c in precursors.most_common(5) if c > 1]

            self._anomaly_clusters[cluster_id] = AnomalyCluster(
                cluster_id=cluster_id,
                pattern_type="failure",
                centroid=[],  # Would use embeddings in production
                members=[e.id for e in events],
                frequency=len(events) / max(1.0, (time.time() - events[0].timestamp) / 3600),
                severity=statistics.mean(
                    abs(e.outcome) for e in events if e.outcome is not None
                ) if any(e.outcome for e in events) else 0.5,
                common_components=[events[0].component],
                common_precursors=common_precursors,
            )

    def _detect_cycles(self):
        """
        Detect repeating behavioral loops.

        Example: "Every 5 minutes, the system goes through
        explore → learn → consolidate → explore"
        """
        # Look at the transition matrix for self-loops and cycles
        for source, targets in self._transition_matrix.items():
            total_transitions = sum(targets.values())
            if total_transitions < 10:
                continue

            # Check for strong self-loops (same event type recurring)
            if source in targets and targets[source] / total_transitions > 0.3:
                cycle_id = hashlib.md5(f"cycle:{source}".encode()).hexdigest()[:12]
                if cycle_id not in self._patterns:
                    self._patterns[cycle_id] = Pattern(
                        id=cycle_id,
                        pattern_type=PatternType.CYCLE,
                        strength=PatternStrength.EMERGING,
                        description=f"Cyclic behavior detected: {source} repeats with {targets[source]}/{total_transitions} frequency",
                        sequence=[source, source],
                        conditions={"self_transition_rate": targets[source] / total_transitions},
                        outcome=0.0,
                        occurrences=targets[source],
                        confidence=targets[source] / total_transitions,
                        first_seen=time.time(),
                        last_seen=time.time(),
                        tags={"cycle", "behavioral"},
                    )

            # Check for 2-step cycles: A → B → A
            for target, count in targets.items():
                if target == source:
                    continue
                if source in self._transition_matrix.get(target, {}):
                    back_count = self._transition_matrix[target][source]
                    if count > 5 and back_count > 5:
                        cycle_rate = min(count, back_count) / total_transitions
                        if cycle_rate > 0.2:
                            cycle_id = hashlib.md5(
                                f"cycle2:{source}:{target}".encode()
                            ).hexdigest()[:12]
                            if cycle_id not in self._patterns:
                                self._patterns[cycle_id] = Pattern(
                                    id=cycle_id,
                                    pattern_type=PatternType.CYCLE,
                                    strength=PatternStrength.EMERGING,
                                    description=f"Bidirectional cycle: {source} ↔ {target}",
                                    sequence=[source, target, source],
                                    conditions={"cycle_rate": cycle_rate},
                                    outcome=0.0,
                                    occurrences=min(count, back_count),
                                    confidence=cycle_rate,
                                    first_seen=time.time(),
                                    last_seen=time.time(),
                                    components_involved=list(set(
                                        s.split(":")[1] for s in [source, target] if ":" in s
                                    )),
                                    tags={"cycle", "bidirectional"},
                                )

    def _detect_phase_transitions(self):
        """
        Detect sudden jumps in capability or performance.

        Phase transitions indicate the system has learned something
        qualitatively new — not just incremental improvement.
        """
        for metric_name, series in self._metric_history.items():
            if len(series) < 50:
                continue

            values = [v for _, v in series]

            # Look for step changes using a moving average comparison
            window = 20
            if len(values) < window * 3:
                continue

            for i in range(window, len(values) - window):
                before_mean = statistics.mean(values[i - window:i])
                after_mean = statistics.mean(values[i:i + window])

                # Detect significant jump (>50% change or >2 std devs)
                before_std = statistics.stdev(values[i - window:i]) if window > 1 else 0.1
                jump = abs(after_mean - before_mean)

                if jump > max(before_std * 2.5, abs(before_mean) * 0.5) and before_std > 0:
                    transition_id = hashlib.md5(
                        f"phase:{metric_name}:{i}".encode()
                    ).hexdigest()[:12]

                    if transition_id not in self._patterns:
                        direction = "improvement" if after_mean > before_mean else "degradation"
                        self._patterns[transition_id] = Pattern(
                            id=transition_id,
                            pattern_type=PatternType.PHASE_TRANSITION,
                            strength=PatternStrength.HYPOTHESIS,
                            description=(
                                f"Phase transition in {metric_name}: "
                                f"{before_mean:.3f} → {after_mean:.3f} ({direction})"
                            ),
                            sequence=[metric_name],
                            conditions={
                                "before_mean": before_mean,
                                "after_mean": after_mean,
                                "jump_magnitude": jump,
                                "direction": direction,
                            },
                            outcome=1.0 if direction == "improvement" else -1.0,
                            occurrences=1,
                            confidence=min(1.0, jump / (before_std * 3)),
                            impact=jump,
                            first_seen=time.time(),
                            last_seen=time.time(),
                            tags={"phase_transition", direction, metric_name},
                        )
                    break  # One transition per metric per cycle

    def _detect_emergence(self):
        """
        Look for emergent patterns — combinations of existing patterns
        that produce outcomes greater than their individual parts.
        """
        if len(self._patterns) < 5:
            return

        # Get patterns that co-occur (happen in same traces)
        established = [
            p for p in self._patterns.values()
            if p.strength in (PatternStrength.ESTABLISHED, PatternStrength.LAW)
        ]

        if len(established) < 2:
            return

        # Check pairs for synergy
        for p1, p2 in combinations(established[:20], 2):
            # Do these patterns share components?
            shared_components = set(p1.components_involved) & set(p2.components_involved)
            if not shared_components:
                continue

            # Check if combined outcome exceeds individual outcomes
            combined_expected = p1.outcome + p2.outcome
            
            # Look for traces where both patterns' sequences appear
            # (simplified: check if their components are both active in recent traces)
            traces = self.collector.query_traces(
                components=list(shared_components),
                min_events=5,
                limit=50,
            )

            if not traces:
                continue

            actual_outcomes = [t.total_outcome for t in traces]
            if not actual_outcomes:
                continue

            avg_actual = statistics.mean(actual_outcomes)

            # Emergence = actual significantly exceeds expected
            if avg_actual > combined_expected * 1.5 and avg_actual > 0.5:
                emergence_id = hashlib.md5(
                    f"emerge:{p1.id}:{p2.id}".encode()
                ).hexdigest()[:12]

                if emergence_id not in self._patterns:
                    self._patterns[emergence_id] = Pattern(
                        id=emergence_id,
                        pattern_type=PatternType.EMERGENCE,
                        strength=PatternStrength.HYPOTHESIS,
                        description=(
                            f"Emergent synergy between '{p1.description[:30]}' "
                            f"and '{p2.description[:30]}' — combined effect "
                            f"exceeds sum of parts ({avg_actual:.2f} vs {combined_expected:.2f})"
                        ),
                        sequence=p1.sequence + p2.sequence,
                        conditions={
                            "parent_patterns": [p1.id, p2.id],
                            "expected_outcome": combined_expected,
                            "actual_outcome": avg_actual,
                            "synergy_factor": avg_actual / max(0.01, combined_expected),
                        },
                        outcome=avg_actual,
                        occurrences=len(traces),
                        confidence=min(1.0, len(traces) / 20.0),
                        impact=avg_actual - combined_expected,
                        novelty=1.0,
                        first_seen=time.time(),
                        last_seen=time.time(),
                        components_involved=list(shared_components),
                        related_patterns=[p1.id, p2.id],
                        tags={"emergence", "synergy"},
                    )
                    self._patterns_discovered += 1

    # ═══════════════════════════════════════════════════════════════
    # PATTERN LIFECYCLE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    def _update_pattern_strengths(self):
        """Promote or demote patterns based on continued observation."""
        for pattern in self._patterns.values():
            # Promote based on occurrences
            if pattern.occurrences >= 100 and pattern.strength != PatternStrength.LAW:
                pattern.strength = PatternStrength.LAW
                self._patterns_promoted += 1
            elif pattern.occurrences >= 20 and pattern.strength == PatternStrength.HYPOTHESIS:
                pattern.strength = PatternStrength.EMERGING
                self._patterns_promoted += 1
            elif pattern.occurrences >= 5 and pattern.strength == PatternStrength.HYPOTHESIS:
                pattern.strength = PatternStrength.EMERGING

            # Decay novelty over time
            age_hours = pattern.age_hours
            pattern.novelty = max(0.0, 1.0 - age_hours / 24.0)

            # Update actionability based on whether we have interventions
            if pattern.pattern_type == PatternType.ANTI_PATTERN:
                pattern.actionability = 0.8  # Anti-patterns are usually actionable
            elif pattern.pattern_type == PatternType.BOTTLENECK:
                pattern.actionability = 0.9
            elif pattern.pattern_type == PatternType.CYCLE:
                pattern.actionability = 0.4  # Cycles might be intentional

    def _prune_weak_patterns(self):
        """Remove patterns that didn't gain strength over time."""
        to_remove = []

        for pid, pattern in self._patterns.items():
            # Remove old hypotheses that never strengthened
            if (pattern.strength == PatternStrength.HYPOTHESIS and
                    pattern.age_hours > 2.0 and
                    pattern.occurrences < self.min_occurrences * 2):
                to_remove.append(pid)

            # Remove patterns with very low score
            if pattern.score < 0.05 and pattern.age_hours > 1.0:
                to_remove.append(pid)

        for pid in to_remove:
            del self._patterns[pid]
            self._patterns_deprecated += 1

        # Also cap total patterns
        if len(self._patterns) > self.max_patterns:
            sorted_patterns = sorted(
                self._patterns.items(),
                key=lambda x: x[1].score
            )
            for pid, _ in sorted_patterns[:len(self._patterns) - self.max_patterns]:
                del self._patterns[pid]
                self._patterns_deprecated += 1

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC QUERY INTERFACE
    # ═══════════════════════════════════════════════════════════════

    def get_top_patterns(self, n: int = 20, pattern_type: PatternType = None) -> List[Pattern]:
        """Get the highest-scored patterns."""
        patterns = list(self._patterns.values())
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        patterns.sort(key=lambda p: p.score, reverse=True)
        return patterns[:n]

    def get_anti_patterns(self, min_confidence: float = 0.6) -> List[Pattern]:
        """Get patterns that predict failure — things to avoid."""
        return [
            p for p in self._patterns.values()
            if p.pattern_type == PatternType.ANTI_PATTERN
            and p.confidence >= min_confidence
        ]

    def get_success_patterns(self, min_confidence: float = 0.6) -> List[Pattern]:
        """Get patterns that predict success — things to replicate."""
        return [
            p for p in self._patterns.values()
            if p.outcome > 0.3 and p.confidence >= min_confidence
        ]

    def get_causal_chains(self, min_strength: float = 0.3) -> List[CausalChain]:
        """Get discovered causal chains above a strength threshold."""
        return [
            c for c in self._causal_chains.values()
            if c.strength >= min_strength
        ]

    def get_correlations(self, min_correlation: float = 0.5) -> List[TemporalCorrelation]:
        """Get temporal correlations above a threshold."""
        return [
            c for c in self._correlations
            if abs(c.correlation) >= min_correlation
        ]

    def get_anomaly_clusters(self) -> List[AnomalyCluster]:
        """Get current anomaly clusters."""
        return list(self._anomaly_clusters.values())

    def predict_outcome(self, event_sequence: List[str]) -> Optional[Dict[str, Any]]:
        """
        Given a sequence of recent events, predict what will happen next.

        Uses discovered patterns to make predictions.
        """
        if not event_sequence:
            return None

        predictions = []

        # Check which patterns match the current sequence
        seq_tuple = tuple(event_sequence)

        for pattern in self._patterns.values():
            if pattern.confidence < 0.5:
                continue

            # Check if pattern's sequence is a prefix of or matches current
            pattern_seq = tuple(pattern.sequence)

            # Exact match
            if seq_tuple == pattern_seq:
                predictions.append({
                    "pattern_id": pattern.id,
                    "predicted_outcome": pattern.outcome,
                    "confidence": pattern.confidence,
                    "description": pattern.description,
                })

            # Current sequence ends with pattern prefix
            elif len(pattern_seq) > len(seq_tuple):
                prefix = pattern_seq[:len(seq_tuple)]
                if prefix == seq_tuple:
                    predictions.append({
                        "pattern_id": pattern.id,
                        "predicted_outcome": pattern.outcome,
                        "confidence": pattern.confidence * 0.7,  # Lower confidence for partial match
                        "next_expected": pattern_seq[len(seq_tuple)],
                        "description": pattern.description,
                    })

        if not predictions:
            return None

        # Return best prediction
        predictions.sort(key=lambda p: p["confidence"], reverse=True)
        return {
            "best_prediction": predictions[0],
            "all_predictions": predictions[:5],
            "total_matching_patterns": len(predictions),
        }

    def get_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate actionable recommendations based on discovered patterns.

        Returns a prioritized list of things the system should do differently.
        """
        recommendations = []

        # From anti-patterns: "Stop doing X"
        for pattern in self.get_anti_patterns():
            if pattern.actionability > 0.5:
                recommendations.append({
                    "type": "avoid",
                    "priority": pattern.score,
                    "description": f"Avoid: {pattern.description}",
                    "pattern_id": pattern.id,
                    "expected_improvement": abs(pattern.outcome) * pattern.confidence,
                    "components": pattern.components_involved,
                })

        # From success patterns: "Do more of X"
        for pattern in self.get_success_patterns():
            if pattern.actionability > 0.5:
                recommendations.append({
                    "type": "amplify",
                    "priority": pattern.score,
                    "description": f"Amplify: {pattern.description}",
                    "pattern_id": pattern.id,
                    "expected_improvement": pattern.outcome * pattern.confidence,
                    "components": pattern.components_involved,
                })

        # From causal chains: "Intervene at point X"
        for chain in self.get_causal_chains(min_strength=0.5):
            if chain.outcome < -0.3 and chain.interventions:
                recommendations.append({
                    "type": "intervene",
                    "priority": abs(chain.outcome) * chain.strength,
                    "description": f"Break negative causal chain at: {chain.interventions[0]}",
                    "chain_id": chain.id,
                    "expected_improvement": abs(chain.outcome) * 0.5,
                    "components": [step[1] for step in chain.chain],
                })

        # From bottlenecks
        bottleneck_patterns = [
            p for p in self._patterns.values()
            if p.pattern_type == PatternType.BOTTLENECK
        ]
        for pattern in bottleneck_patterns:
            recommendations.append({
                "type": "optimize",
                "priority": pattern.impact,
                "description": f"Bottleneck: {pattern.description}",
                "pattern_id": pattern.id,
                "expected_improvement": pattern.impact,
                "components": pattern.components_involved,
            })

        # Sort by priority
        recommendations.sort(key=lambda r: r["priority"], reverse=True)
        return recommendations[:20]

    def get_status(self) -> Dict[str, Any]:
        """Get pattern recognizer status."""
        return {
            "analysis_cycles": self._analysis_cycles,
            "patterns_discovered": self._patterns_discovered,
            "patterns_active": len(self._patterns),
            "patterns_promoted": self._patterns_promoted,
            "patterns_deprecated": self._patterns_deprecated,
            "causal_chains": len(self._causal_chains),
            "correlations": len(self._correlations),
            "anomaly_clusters": len(self._anomaly_clusters),
            "pattern_types": dict(Counter(
                p.pattern_type.value for p in self._patterns.values()
            )),
            "strength_distribution": dict(Counter(
                p.strength.value for p in self._patterns.values()
            )),
            "top_patterns": [p.to_dict() for p in self.get_top_patterns(5)],
        }

    # ═══════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════

    def _trace_causal_chain(self, start_id: str, graph: Dict[str, List[str]],
                           event_map: Dict[str, TraceEvent],
                           max_depth: int) -> List[TraceEvent]:
        """Follow causal links forward from a starting event."""
        chain = []
        current = start_id
        visited = set()

        while current and len(chain) < max_depth:
            if current in visited:
                break
            visited.add(current)

            if current in event_map:
                chain.append(event_map[current])

            # Follow to next in chain
            successors = graph.get(current, [])
            if successors:
                current = successors[0]  # Follow primary successor
            else:
                break

        return chain

    def _find_intervention_points(self, chain_events: List[TraceEvent]) -> List[str]:
        """Identify points in a causal chain where intervention is possible."""
        interventions = []
        for i, event in enumerate(chain_events):
            # Events with long duration = opportunity to interrupt
            if event.duration_us and event.duration_us > 10000:  # >10ms
                interventions.append(f"step_{i}:{event.component}")
            # Decision events can be changed
            if event.event_type == EventType.DECISION_MADE:
                interventions.append(f"step_{i}:decision:{event.component}")
        return interventions

    def _compute_lagged_correlation(self, series_a: List[Tuple[float, float]],
                                    series_b: List[Tuple[float, float]],
                                    lag: float) -> Optional[float]:
        """Compute correlation between two time series with a time lag."""
        if len(series_a) < 10 or len(series_b) < 10:
            return None

        # Align series with lag
        aligned_a = []
        aligned_b = []

        for t_a, v_a in series_a:
            # Find closest value in series_b at time t_a + lag
            target_time = t_a + lag
            closest = min(series_b, key=lambda x: abs(x[0] - target_time))
            if abs(closest[0] - target_time) < lag * 0.3:  # Within 30% of lag
                aligned_a.append(v_a)
                aligned_b.append(closest[1])

        if len(aligned_a) < 10:
            return None

        # Compute Pearson correlation
        try:
            a_arr = np.array(aligned_a)
            b_arr = np.array(aligned_b)

            # Normalize
            a_std = np.std(a_arr)
            b_std = np.std(b_arr)

            if a_std == 0 or b_std == 0:
                return None

            correlation = np.corrcoef(a_arr, b_arr)[0, 1]
            return float(correlation) if not np.isnan(correlation) else None
        except (ValueError, RuntimeWarning):
            return None

    def _assess_actionability(self, sequence: tuple) -> float:
        """Assess how actionable a pattern is (can we influence it?)."""
        # Patterns involving decisions are highly actionable
        actionable_keywords = {"decision", "strategy", "algorithm", "patch", "goal"}
        seq_str = " ".join(str(s) for s in sequence).lower()

        score = 0.3  # Base actionability

        for keyword in actionable_keywords:
            if keyword in seq_str:
                score += 0.15

        return min(1.0, score)

    def _describe_sequence(self, seq_key: tuple, outcome: float) -> str:
        """Generate a human-readable description of a sequence pattern."""
        steps = [s.split(":") for s in seq_key if ":" in s]

        if not steps:
            return f"Pattern with outcome {outcome:.2f}"

        if outcome < -0.3:
            prefix = "Anti-pattern"
        elif outcome > 0.3:
            prefix = "Success pattern"
        else:
            prefix = "Pattern"

        components = list(set(s[1] for s in steps if len(s) > 1))
        event_types = [s[0] for s in steps if len(s) > 0]

        desc = f"{prefix}: {' → '.join(event_types[:4])}"
        if components:
            desc += f" (in {', '.join(components[:3])})"
        desc += f" [outcome: {outcome:.2f}]"

        return desc
