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
    event_type: EventType
    event_level: TraceLevel
    timestamp: float
    event_data: Dict[str, Any]
    related_events: List['TraceEvent'] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# EXPERIENCE COLLECTOR
# ═══════════════════════════════════════════════════════════════

class ExperienceCollector:
    """
    Collects and stores learning experiences for the self-improvement loop.

    Accepts events from all Ultron components and exposes them for
    pattern recognition and knowledge distillation.
    """

    def __init__(
        self,
        data_dir: str = ".ultron/experiences",
        max_buffer_size: int = 200_000,
        max_traces: int = 20_000,
        long_term_path: str = None,
        importance_threshold: float = 0.7,
        auto_trace_timeout: float = 30.0,
    ):
        import os
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        if long_term_path:
            os.makedirs(long_term_path, exist_ok=True)

        self.max_buffer_size = max_buffer_size
        self.max_traces = max_traces
        self.long_term_path = long_term_path
        self.importance_threshold = importance_threshold
        self.auto_trace_timeout = auto_trace_timeout

        # Ring buffer for recent events
        self._events: deque = deque(maxlen=max_buffer_size)
        self._traces: deque = deque(maxlen=max_traces)
        self._lock = threading.Lock()

        # Simple stats
        self._error_count: int = 0
        self._total_received: int = 0

    # ── Core ingestion ──────────────────────────────────────────

    def record_event(
        self,
        event_type: EventType,
        component: str,
        data: Dict[str, Any],
        duration_us: Optional[int] = None,
        caused_by: Optional[List[str]] = None,
        outcome: Optional[float] = None,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """Record a single structured event from any component."""
        event = {
            "event_type": event_type.value if hasattr(event_type, "value") else str(event_type),
            "component": component,
            "data": data,
            "timestamp": time.time(),
            "duration_us": duration_us,
            "caused_by": caused_by or [],
            "outcome": outcome,
            "tags": list(tags) if tags else [],
        }
        with self._lock:
            self._events.append(event)
            self._total_received += 1
            if event_type == EventType.ERROR_OCCURRED:
                self._error_count += 1

    def collect(
        self,
        event_type: str,
        data: Dict[str, Any],
        outcome: float = 0.0,
    ) -> None:
        """Convenience wrapper — accepts string event_type."""
        entry = {
            "event_type": event_type,
            "data": data,
            "outcome": outcome,
            "timestamp": time.time(),
        }
        with self._lock:
            self._events.append(entry)
            self._total_received += 1
        for cb in getattr(self, '_event_callbacks', []):
            try: cb(entry)
            except Exception: pass

    def collect_from_decisions(self, decision: Dict[str, Any]) -> None:
        self.collect("decision", decision, decision.get("outcome", 0.0))

    def collect_from_code_analysis(self, analysis: Dict[str, Any]) -> None:
        self.collect("code_analysis", analysis)

    # ── Retrieval ───────────────────────────────────────────────


    def on_any_event(self, callback) -> None:
        """Register a callback triggered on every new experience."""
        self._event_callbacks = getattr(self, '_event_callbacks', [])
        self._event_callbacks.append(callback)

    def get_recent(self, n: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._events)
            return events[-n:]

    def get_events_by_type(
        self, event_type: EventType, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        with self._lock:
            target = event_type.value if hasattr(event_type, "value") else str(event_type)
            return [e for e in self._events if e.get("event_type") == target][-limit:]

    def get_events_by_component(
        self, component: str, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        with self._lock:
            return [e for e in self._events if e.get("component") == component][-limit:]

    # ── Health & Signal ─────────────────────────────────────────

    def get_system_health(self) -> Dict[str, Any]:
        """Return a dict of basic health metrics."""
        with self._lock:
            total = self._total_received or 1
            error_rate = self._error_count / total
            return {
                "total_events": self._total_received,
                "buffer_size": len(self._events),
                "error_count": self._error_count,
                "error_rate": error_rate,
                "status": "healthy" if error_rate < 0.1 else "degraded",
            }

    def get_learning_signal(self) -> Dict[str, Any]:
        """Return a summary learning signal for directive generation."""
        with self._lock:
            events = list(self._events)

        outcomes = [e["outcome"] for e in events if e.get("outcome") is not None]
        if outcomes:
            avg_outcome = sum(outcomes) / len(outcomes)
            recent = outcomes[-50:]
            trend = (sum(recent) / len(recent)) - avg_outcome if recent else 0.0
        else:
            avg_outcome = 0.0
            trend = 0.0

        return {
            "avg_outcome": avg_outcome,
            "outcome_trend": trend,
            "total_samples": len(outcomes),
            "signal_strength": min(1.0, len(outcomes) / 1000),
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total": self._total_received,
                "buffered": len(self._events),
                "data_dir": self.data_dir,
            }

    def start(self) -> None:
        """No background threads required at this level."""
        pass

    def stop(self) -> None:
        pass


@dataclass
class ExecutionTrace:
    """A complete execution trace spanning multiple related events."""
    trace_id: str
    start_time: float
    end_time: float
    events: List[TraceEvent] = field(default_factory=list)
    outcome: Optional[float] = None
    component: str = "unknown"
    tags: List[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000.0

    @property
    def event_count(self) -> int:
        return len(self.events)


    def collect_experience(self, experience: Dict[str, Any]) -> None:
        """Collect a structured experience record."""
        self.collect(
            event_type=experience.get("event_type", "experience"),
            data=experience,
            outcome=float(experience.get("outcome", 0.0)),
        )


# ── Patch collect_experience onto ExperienceCollector (appended post-class) ──
def _ec_collect_experience(self, experience: Dict[str, Any]) -> None:
    """Collect a structured experience record."""
    self.collect(
        event_type=experience.get("event_type", "experience"),
        data=experience,
        outcome=float(experience.get("outcome", 0.0)),
    )

ExperienceCollector.collect_experience = _ec_collect_experience
