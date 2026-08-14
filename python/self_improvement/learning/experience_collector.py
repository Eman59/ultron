"""
Experience Collector — The Sensory Cortex of Self-Learning.

This system captures EVERYTHING that happens across all Ultron components
and organizes it into a queryable execution trace database.

What it captures:
  - Every decision made by the autonomy loop (Go core agent)
  - Every neural mesh activation pattern (Rust)
  - Every meta-learning algorithm evaluation (Python)
  - Every patch generated and its outcome (Self-Improvement)
  - Resource usage over time
  - Error cascades and recovery sequences
  - Timing of every operation at microsecond granularity

The traces are stored in a ring buffer (bounded memory) with important
traces promoted to long-term storage based on information content.

This is NOT a log. This is structured experiential memory that can be
queried causally: "What led to this outcome?" "What always precedes this failure?"
"""

import time
import threading
import hashlib
import json
import os
import statistics
from typing import Dict, Any, List, Optional, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from pathlib import Path
import numpy as np


class TraceLevel(Enum):
    """Granularity of trace capture."""
    CRITICAL = "critical"     # Errors, regressions, breakthroughs
    DECISION = "decision"     # Every decision point
    EXECUTION = "execution"   # Every function execution
    MICRO = "micro"           # Instruction-level (expensive, used selectively)


class EventType(Enum):
    """Categories of events in the execution trace."""
    # Core Agent Events
    DECISION_MADE = "decision_made"
    ACTION_EXECUTED = "action_executed"
    ACTION_OUTCOME = "action_outcome"
    DRIVE_CHANGE = "drive_change"
    STATE_TRANSITION = "state_transition"
    GOAL_CREATED = "goal_created"
    GOAL_COMPLETED = "goal_completed"
    GOAL_FAILED = "goal_failed"

    # Neural Events
    NEURAL_ACTIVATION = "neural_activation"
    PLASTICITY_UPDATE = "plasticity_update"
    NEURAL_EVOLUTION = "neural_evolution"
    ARCHITECTURE_CHANGE = "architecture_change"

    # Meta-Learning Events
    ALGORITHM_GENERATED = "algorithm_generated"
    ALGORITHM_EVALUATED = "algorithm_evaluated"
    STRATEGY_SWITCH = "strategy_switch"
    TRANSFER_PERFORMED = "transfer_performed"

    # Self-Improvement Events
    PATCH_GENERATED = "patch_generated"
    PATCH_TESTED = "patch_tested"
    PATCH_APPLIED = "patch_applied"
    PATCH_REVERTED = "patch_reverted"
    PERFORMANCE_MEASURED = "performance_measured"

    # System Events
    RESOURCE_SPIKE = "resource_spike"
    ERROR_OCCURRED = "error_occurred"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    COMPONENT_RESTART = "component_restart"

    # Learning Events
    PATTERN_DISCOVERED = "pattern_discovered"
    RULE_DISTILLED = "rule_distilled"
    OPTIMIZATION_APPLIED = "optimization_applied"
    KNOWLEDGE_TRANSFERRED = "knowledge_transferred"


@dataclass
class TraceEvent:
    """A single event in the execution trace."""
    id: str
    timestamp: float
    event_type: EventType
    component: str                    # Which subsystem generated this
    data: Dict[str, Any]              # Event-specific payload
    duration_us: Optional[int] = None # Duration in microseconds (if applicable)
    causality: List[str] = field(default_factory=list)  # IDs of events that caused this
    outcome: Optional[float] = None   # Utility/reward signal (-1 to 1)
    context_vector: Optional[List[float]] = None  # Embedding of the context
    tags: Set[str] = field(default_factory=set)
    importance: float = 0.5           # 0-1, determines if promoted to long-term

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "component": self.component,
            "data": self.data,
            "duration_us": self.duration_us,
            "causality": self.causality,
            "outcome": self.outcome,
            "tags": list(self.tags),
            "importance": self.importance,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TraceEvent":
        return cls(
            id=d["id"],
            timestamp=d["timestamp"],
            event_type=EventType(d["event_type"]),
            component=d["component"],
            data=d["data"],
            duration_us=d.get("duration_us"),
            causality=d.get("causality", []),
            outcome=d.get("outcome"),
            tags=set(d.get("tags", [])),
            importance=d.get("importance", 0.5),
        )


@dataclass
class ExecutionTrace:
    """A sequence of causally-linked events forming a coherent episode."""
    trace_id: str
    start_time: float
    end_time: Optional[float] = None
    events: List[TraceEvent] = field(default_factory=list)
    total_outcome: float = 0.0        # Aggregate outcome of the trace
    root_cause: Optional[str] = None  # ID of the originating event
    component_chain: List[str] = field(default_factory=list)  # Order of components involved
    tags: Set[str] = field(default_factory=set)

    @property
    def duration(self) -> float:
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def event_count(self) -> int:
        return len(self.events)

    def add_event(self, event: TraceEvent):
        self.events.append(event)
        if event.component not in self.component_chain:
            self.component_chain.append(event.component)
        if event.outcome is not None:
            self.total_outcome += event.outcome

    def finalize(self, outcome: float = None):
        """Close the trace."""
        self.end_time = time.time()
        if outcome is not None:
            self.total_outcome = outcome


@dataclass
class ComponentStats:
    """Real-time statistics for a single component."""
    component: str
    total_events: int = 0
    total_successes: int = 0
    total_failures: int = 0
    avg_duration_us: float = 0.0
    p99_duration_us: float = 0.0
    avg_outcome: float = 0.0
    recent_durations: deque = field(default_factory=lambda: deque(maxlen=1000))
    recent_outcomes: deque = field(default_factory=lambda: deque(maxlen=1000))
    error_rate_history: deque = field(default_factory=lambda: deque(maxlen=100))
    last_event_time: float = 0.0

    def record(self, event: TraceEvent):
        self.total_events += 1
        self.last_event_time = event.timestamp

        if event.duration_us is not None:
            self.recent_durations.append(event.duration_us)
            if self.recent_durations:
                self.avg_duration_us = statistics.mean(self.recent_durations)
                self.p99_duration_us = (
                    sorted(self.recent_durations)[int(len(self.recent_durations) * 0.99)]
                    if len(self.recent_durations) > 10 else self.avg_duration_us
                )

        if event.outcome is not None:
            self.recent_outcomes.append(event.outcome)
            self.avg_outcome = statistics.mean(self.recent_outcomes)
            if event.outcome > 0:
                self.total_successes += 1
            elif event.outcome < 0:
                self.total_failures += 1


class ExperienceCollector:
    """
    The central nervous system for experience capture.

    Ingests events from all Ultron subsystems, organizes them into
    causal traces, computes real-time statistics, and maintains both
    short-term (ring buffer) and long-term (persistent) trace storage.

    Thread-safe. Lock-free where possible using append-only structures.
    """

    def __init__(self,
                 max_buffer_size: int = 100_000,
                 max_traces: int = 10_000,
                 long_term_path: Optional[str] = None,
                 importance_threshold: float = 0.7,
                 auto_trace_timeout: float = 30.0):
        """
        Args:
            max_buffer_size: Maximum events in the short-term ring buffer
            max_traces: Maximum active traces before eviction
            long_term_path: Directory for persistent trace storage
            importance_threshold: Events above this are promoted to long-term
            auto_trace_timeout: Seconds before an open trace is auto-closed
        """
        # Short-term event buffer (ring buffer)
        self._event_buffer: deque = deque(maxlen=max_buffer_size)

        # Active traces being built
        self._active_traces: Dict[str, ExecutionTrace] = {}
        self._max_traces = max_traces

        # Completed traces (ring buffer)
        self._completed_traces: deque = deque(maxlen=max_traces)

        # Long-term storage
        self._long_term_path = Path(long_term_path) if long_term_path else None
        if self._long_term_path:
            self._long_term_path.mkdir(parents=True, exist_ok=True)

        # Component statistics (real-time)
        self._component_stats: Dict[str, ComponentStats] = {}

        # Configuration
        self._importance_threshold = importance_threshold
        self._auto_trace_timeout = auto_trace_timeout

        # Event listeners (for real-time processing)
        self._listeners: Dict[EventType, List[Callable]] = defaultdict(list)

        # Correlation tracking: event_id → trace_ids
        self._event_to_traces: Dict[str, List[str]] = defaultdict(list)

        # Metrics
        self._total_events_collected = 0
        self._total_traces_completed = 0
        self._events_promoted_to_long_term = 0

        # Concurrency
        self._lock = threading.RLock()
        self._running = False

        # Background maintenance
        self._maintenance_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the experience collector."""
        self._running = True
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            daemon=True,
            name="ExperienceCollector-Maintenance"
        )
        self._maintenance_thread.start()
        print("[ExperienceCollector] Started — capturing all experience")

    def stop(self):
        """Stop the collector and flush to disk."""
        self._running = False
        if self._maintenance_thread:
            self._maintenance_thread.join(timeout=5.0)
        self._flush_long_term()
        print(f"[ExperienceCollector] Stopped — {self._total_events_collected} events captured")

    # ═══════════════════════════════════════════════════════════════
    # EVENT INGESTION
    # ═══════════════════════════════════════════════════════════════

    def record_event(self,
                     event_type: EventType,
                     component: str,
                     data: Dict[str, Any],
                     duration_us: Optional[int] = None,
                     caused_by: Optional[List[str]] = None,
                     outcome: Optional[float] = None,
                     trace_id: Optional[str] = None,
                     tags: Optional[Set[str]] = None,
                     context_vector: Optional[List[float]] = None) -> str:
        """
        Record a single event from any component.

        Args:
            event_type: Category of the event
            component: Which subsystem (e.g., "core_agent", "neural_mesh", "meta_learning")
            data: Event-specific payload
            duration_us: How long the operation took (microseconds)
            caused_by: List of event IDs that caused this event
            outcome: Reward/utility signal (-1 to 1)
            trace_id: If part of an existing trace, link to it
            tags: Additional categorization tags
            context_vector: Embedding of the execution context

        Returns:
            Event ID for causal linking
        """
        event_id = self._generate_id(event_type, component)

        event = TraceEvent(
            id=event_id,
            timestamp=time.time(),
            event_type=event_type,
            component=component,
            data=data,
            duration_us=duration_us,
            causality=caused_by or [],
            outcome=outcome,
            context_vector=context_vector,
            tags=tags or set(),
            importance=self._calculate_importance(event_type, outcome, data),
        )

        # Add to buffer
        self._event_buffer.append(event)
        self._total_events_collected += 1

        # Update component stats
        self._update_stats(event)

        # Link to trace if specified
        if trace_id and trace_id in self._active_traces:
            self._active_traces[trace_id].add_event(event)
            self._event_to_traces[event_id].append(trace_id)

        # Auto-create trace from causal chain
        elif caused_by:
            self._auto_trace(event)

        # Promote high-importance events
        if event.importance >= self._importance_threshold:
            self._promote_to_long_term(event)

        # Notify listeners
        self._notify_listeners(event)

        return event_id

    def record_decision(self,
                        decision_id: str,
                        action_type: str,
                        target: str,
                        confidence: float,
                        reasoning: List[str],
                        alternatives_considered: int,
                        context: Dict[str, Any] = None) -> str:
        """Convenience: record a decision from the core agent."""
        return self.record_event(
            event_type=EventType.DECISION_MADE,
            component="core_agent",
            data={
                "decision_id": decision_id,
                "action_type": action_type,
                "target": target,
                "confidence": confidence,
                "reasoning": reasoning,
                "alternatives": alternatives_considered,
                "context": context or {},
            },
            tags={"decision", action_type},
        )

    def record_action_outcome(self,
                              decision_id: str,
                              success: bool,
                              utility: float,
                              duration_us: int,
                              side_effects: List[str] = None) -> str:
        """Convenience: record the outcome of an action."""
        return self.record_event(
            event_type=EventType.ACTION_OUTCOME,
            component="core_agent",
            data={
                "decision_id": decision_id,
                "success": success,
                "side_effects": side_effects or [],
            },
            duration_us=duration_us,
            outcome=utility if success else -abs(utility),
            caused_by=[decision_id],
            tags={"outcome", "success" if success else "failure"},
        )

    def record_neural_activation(self,
                                  mesh_id: str,
                                  neurons_fired: int,
                                  total_neurons: int,
                                  activation_pattern: List[float],
                                  plasticity_delta: float) -> str:
        """Convenience: record neural mesh activation."""
        return self.record_event(
            event_type=EventType.NEURAL_ACTIVATION,
            component="neural_mesh",
            data={
                "mesh_id": mesh_id,
                "neurons_fired": neurons_fired,
                "total_neurons": total_neurons,
                "fire_rate": neurons_fired / max(1, total_neurons),
                "plasticity_delta": plasticity_delta,
            },
            context_vector=activation_pattern[:64],  # Truncate for storage
            tags={"neural", "activation"},
        )

    def record_error(self,
                     component: str,
                     error_type: str,
                     message: str,
                     stack_trace: str = "",
                     severity: float = 0.5) -> str:
        """Convenience: record an error."""
        return self.record_event(
            event_type=EventType.ERROR_OCCURRED,
            component=component,
            data={
                "error_type": error_type,
                "message": message,
                "stack_trace": stack_trace,
                "severity": severity,
            },
            outcome=-severity,
            tags={"error", error_type, component},
        )

    # ═══════════════════════════════════════════════════════════════
    # TRACE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    def begin_trace(self, description: str = "", tags: Set[str] = None) -> str:
        """Start a new execution trace. Returns trace_id."""
        trace_id = hashlib.md5(
            f"trace:{time.time()}:{description}".encode()
        ).hexdigest()[:16]

        trace = ExecutionTrace(
            trace_id=trace_id,
            start_time=time.time(),
            tags=tags or set(),
        )

        with self._lock:
            # Evict oldest trace if at capacity
            if len(self._active_traces) >= self._max_traces:
                oldest_id = min(
                    self._active_traces,
                    key=lambda t: self._active_traces[t].start_time
                )
                self._finalize_trace(oldest_id)

            self._active_traces[trace_id] = trace

        return trace_id

    def end_trace(self, trace_id: str, outcome: float = None):
        """Close an active trace."""
        self._finalize_trace(trace_id, outcome)

    def get_trace(self, trace_id: str) -> Optional[ExecutionTrace]:
        """Retrieve a trace by ID."""
        if trace_id in self._active_traces:
            return self._active_traces[trace_id]
        for trace in self._completed_traces:
            if trace.trace_id == trace_id:
                return trace
        return None

    # ═══════════════════════════════════════════════════════════════
    # QUERY INTERFACE — for Pattern Recognizer and other consumers
    # ═══════════════════════════════════════════════════════════════

    def query_events(self,
                     event_types: Optional[List[EventType]] = None,
                     components: Optional[List[str]] = None,
                     min_outcome: Optional[float] = None,
                     max_outcome: Optional[float] = None,
                     since: Optional[float] = None,
                     until: Optional[float] = None,
                     tags: Optional[Set[str]] = None,
                     limit: int = 1000) -> List[TraceEvent]:
        """Query events with flexible filters."""
        results = []

        for event in reversed(self._event_buffer):
            if len(results) >= limit:
                break

            # Apply filters
            if event_types and event.event_type not in event_types:
                continue
            if components and event.component not in components:
                continue
            if min_outcome is not None and (event.outcome is None or event.outcome < min_outcome):
                continue
            if max_outcome is not None and (event.outcome is None or event.outcome > max_outcome):
                continue
            if since and event.timestamp < since:
                continue
            if until and event.timestamp > until:
                continue
            if tags and not tags.issubset(event.tags):
                continue

            results.append(event)

        return results

    def query_traces(self,
                     min_outcome: Optional[float] = None,
                     max_outcome: Optional[float] = None,
                     components: Optional[List[str]] = None,
                     min_events: int = 0,
                     tags: Optional[Set[str]] = None,
                     limit: int = 100) -> List[ExecutionTrace]:
        """Query completed traces."""
        results = []

        for trace in reversed(self._completed_traces):
            if len(results) >= limit:
                break

            if min_outcome is not None and trace.total_outcome < min_outcome:
                continue
            if max_outcome is not None and trace.total_outcome > max_outcome:
                continue
            if components:
                if not any(c in trace.component_chain for c in components):
                    continue
            if min_events > 0 and trace.event_count < min_events:
                continue
            if tags and not tags.issubset(trace.tags):
                continue

            results.append(trace)

        return results

    def get_causal_chain(self, event_id: str, max_depth: int = 10) -> List[TraceEvent]:
        """Walk backwards through causality to find root cause."""
        chain = []
        visited = set()
        queue = [event_id]

        while queue and len(chain) < max_depth:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            # Find event in buffer
            for event in self._event_buffer:
                if event.id == current_id:
                    chain.append(event)
                    queue.extend(event.causality)
                    break

        return chain

    def get_component_stats(self, component: str = None) -> Dict[str, Any]:
        """Get real-time stats for one or all components."""
        if component:
            stats = self._component_stats.get(component)
            if not stats:
                return {}
            return {
                "component": stats.component,
                "total_events": stats.total_events,
                "success_rate": stats.total_successes / max(1, stats.total_events),
                "failure_rate": stats.total_failures / max(1, stats.total_events),
                "avg_duration_us": stats.avg_duration_us,
                "p99_duration_us": stats.p99_duration_us,
                "avg_outcome": stats.avg_outcome,
            }

        return {
            name: {
                "total_events": s.total_events,
                "success_rate": s.total_successes / max(1, s.total_events),
                "avg_duration_us": s.avg_duration_us,
                "avg_outcome": s.avg_outcome,
            }
            for name, s in self._component_stats.items()
        }

    def get_failure_sequences(self, window_seconds: float = 300.0) -> List[List[TraceEvent]]:
        """Find sequences of events that ended in failure (for pattern analysis)."""
        cutoff = time.time() - window_seconds
        failures = []

        for trace in self._completed_traces:
            if trace.total_outcome < -0.3 and trace.start_time > cutoff:
                failures.append(trace.events)

        return failures

    def get_success_sequences(self, window_seconds: float = 300.0) -> List[List[TraceEvent]]:
        """Find sequences that led to high-value outcomes."""
        cutoff = time.time() - window_seconds
        successes = []

        for trace in self._completed_traces:
            if trace.total_outcome > 0.5 and trace.start_time > cutoff:
                successes.append(trace.events)

        return successes

    # ═══════════════════════════════════════════════════════════════
    # LISTENER SYSTEM — for real-time reaction
    # ═══════════════════════════════════════════════════════════════

    def on_event(self, event_type: EventType, callback: Callable[[TraceEvent], None]):
        """Register a listener for a specific event type."""
        self._listeners[event_type].append(callback)

    def on_any_event(self, callback: Callable[[TraceEvent], None]):
        """Register a listener for all events."""
        for event_type in EventType:
            self._listeners[event_type].append(callback)

    # ═══════════════════════════════════════════════════════════════
    # AGGREGATE METRICS — for the system to understand itself
    # ═══════════════════════════════════════════════════════════════

    def get_system_health(self) -> Dict[str, Any]:
        """Overall system health derived from experience data."""
        recent_events = list(self._event_buffer)[-1000:]

        if not recent_events:
            return {"status": "no_data", "health": 0.5}

        outcomes = [e.outcome for e in recent_events if e.outcome is not None]
        errors = [e for e in recent_events if e.event_type == EventType.ERROR_OCCURRED]
        decisions = [e for e in recent_events if e.event_type == EventType.DECISION_MADE]

        avg_outcome = statistics.mean(outcomes) if outcomes else 0.0
        error_rate = len(errors) / max(1, len(recent_events))
        decision_quality = statistics.mean(
            [e.data.get("confidence", 0.5) for e in decisions]
        ) if decisions else 0.5

        health = (
            (avg_outcome + 1.0) / 2.0 * 0.4 +  # Normalized outcome (0-1)
            (1.0 - error_rate) * 0.3 +            # Error rate inverted
            decision_quality * 0.3                 # Decision confidence
        )

        return {
            "status": "healthy" if health > 0.6 else "degraded" if health > 0.3 else "critical",
            "health": health,
            "avg_outcome": avg_outcome,
            "error_rate": error_rate,
            "decision_quality": decision_quality,
            "events_per_second": self._calculate_event_rate(),
            "active_traces": len(self._active_traces),
            "total_events": self._total_events_collected,
            "total_traces": self._total_traces_completed,
            "components_active": len(self._component_stats),
        }

    def get_learning_signal(self) -> Dict[str, Any]:
        """
        Extract the learning signal — what should the system pay attention to?

        Returns areas of opportunity and concern for the Pattern Recognizer.
        """
        signal = {
            "opportunities": [],
            "concerns": [],
            "trending_up": [],
            "trending_down": [],
        }

        for name, stats in self._component_stats.items():
            if stats.total_events < 10:
                continue

            # Declining performance
            if len(stats.recent_outcomes) > 20:
                recent = list(stats.recent_outcomes)
                first_half = statistics.mean(recent[:len(recent)//2])
                second_half = statistics.mean(recent[len(recent)//2:])

                if second_half < first_half - 0.1:
                    signal["trending_down"].append({
                        "component": name,
                        "delta": second_half - first_half,
                        "current_avg": second_half,
                    })
                elif second_half > first_half + 0.1:
                    signal["trending_up"].append({
                        "component": name,
                        "delta": second_half - first_half,
                        "current_avg": second_half,
                    })

            # High failure rate
            error_rate = stats.total_failures / max(1, stats.total_events)
            if error_rate > 0.2:
                signal["concerns"].append({
                    "component": name,
                    "issue": "high_error_rate",
                    "rate": error_rate,
                })

            # Latency spikes
            if stats.p99_duration_us > stats.avg_duration_us * 5 and stats.avg_duration_us > 0:
                signal["concerns"].append({
                    "component": name,
                    "issue": "latency_spikes",
                    "p99": stats.p99_duration_us,
                    "avg": stats.avg_duration_us,
                })

            # Underutilized (rarely fires but succeeds when it does)
            success_rate = stats.total_successes / max(1, stats.total_events)
            if success_rate > 0.8 and stats.avg_outcome > 0.5:
                signal["opportunities"].append({
                    "component": name,
                    "reason": "high_success_underutilized",
                    "success_rate": success_rate,
                    "avg_outcome": stats.avg_outcome,
                })

        return signal

    # ═══════════════════════════════════════════════════════════════
    # PRIVATE METHODS
    # ═══════════════════════════════════════════════════════════════

    def _generate_id(self, event_type: EventType, component: str) -> str:
        """Generate a unique, compact event ID."""
        raw = f"{event_type.value}:{component}:{time.time_ns()}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _calculate_importance(self, event_type: EventType, outcome: Optional[float],
                             data: Dict[str, Any]) -> float:
        """Calculate how important an event is for long-term storage."""
        importance = 0.3  # Base

        # High-impact event types
        if event_type in (EventType.PATCH_APPLIED, EventType.PATCH_REVERTED,
                         EventType.NEURAL_EVOLUTION, EventType.ARCHITECTURE_CHANGE):
            importance += 0.3

        if event_type in (EventType.GOAL_COMPLETED, EventType.GOAL_FAILED):
            importance += 0.2

        if event_type == EventType.ERROR_OCCURRED:
            importance += data.get("severity", 0.3) * 0.4

        # Extreme outcomes are noteworthy
        if outcome is not None:
            if abs(outcome) > 0.7:
                importance += 0.3
            elif abs(outcome) > 0.4:
                importance += 0.1

        # First occurrence of a new pattern
        if data.get("is_novel", False):
            importance += 0.2

        return min(1.0, importance)

    def _update_stats(self, event: TraceEvent):
        """Update real-time component statistics."""
        if event.component not in self._component_stats:
            self._component_stats[event.component] = ComponentStats(
                component=event.component
            )
        self._component_stats[event.component].record(event)

    def _auto_trace(self, event: TraceEvent):
        """Automatically create/extend traces from causal links."""
        # Check if any causal parent is in an active trace
        for parent_id in event.causality:
            if parent_id in self._event_to_traces:
                for trace_id in self._event_to_traces[parent_id]:
                    if trace_id in self._active_traces:
                        self._active_traces[trace_id].add_event(event)
                        self._event_to_traces[event.id].append(trace_id)
                        return

        # No existing trace found — start a new one if the event is important enough
        if event.importance > 0.5:
            trace_id = self.begin_trace(
                description=f"auto:{event.event_type.value}",
                tags=event.tags,
            )
            self._active_traces[trace_id].add_event(event)
            self._event_to_traces[event.id].append(trace_id)

    def _finalize_trace(self, trace_id: str, outcome: float = None):
        """Move a trace from active to completed."""
        with self._lock:
            trace = self._active_traces.pop(trace_id, None)
            if trace:
                trace.finalize(outcome)
                self._completed_traces.append(trace)
                self._total_traces_completed += 1

    def _promote_to_long_term(self, event: TraceEvent):
        """Save important events to persistent storage."""
        if not self._long_term_path:
            return

        self._events_promoted_to_long_term += 1

        # Write to date-partitioned file
        date_str = time.strftime("%Y-%m-%d")
        filepath = self._long_term_path / f"events_{date_str}.jsonl"

        try:
            with open(filepath, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except IOError:
            pass  # Don't let storage failures break collection

    def _flush_long_term(self):
        """Flush remaining important events on shutdown."""
        if not self._long_term_path:
            return

        important = [
            e for e in self._event_buffer
            if e.importance >= self._importance_threshold
        ]

        if important:
            date_str = time.strftime("%Y-%m-%d")
            filepath = self._long_term_path / f"events_{date_str}_flush.jsonl"
            try:
                with open(filepath, "a") as f:
                    for event in important:
                        f.write(json.dumps(event.to_dict()) + "\n")
            except IOError:
                pass

    def _notify_listeners(self, event: TraceEvent):
        """Notify registered listeners of a new event."""
        for callback in self._listeners.get(event.event_type, []):
            try:
                callback(event)
            except Exception:
                pass  # Listeners should not break collection

    def _calculate_event_rate(self) -> float:
        """Events per second over last 60 seconds."""
        cutoff = time.time() - 60.0
        recent = sum(1 for e in self._event_buffer if e.timestamp > cutoff)
        return recent / 60.0

    def _maintenance_loop(self):
        """Background thread: cleanup stale traces, compact storage."""
        while self._running:
            time.sleep(10.0)

            now = time.time()

            # Close stale traces
            stale_ids = [
                tid for tid, trace in self._active_traces.items()
                if now - trace.start_time > self._auto_trace_timeout
            ]
            for tid in stale_ids:
                self._finalize_trace(tid)

            # Prune event-to-trace mapping (remove entries for completed traces)
            active_trace_ids = set(self._active_traces.keys())
            stale_mappings = [
                eid for eid, tids in self._event_to_traces.items()
                if not any(t in active_trace_ids for t in tids)
            ]
            for eid in stale_mappings[:1000]:  # Batch cleanup
                del self._event_to_traces[eid]
