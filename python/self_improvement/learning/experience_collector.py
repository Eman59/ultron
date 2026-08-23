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