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
    unique_identifier: str
    category: BeliefCategory
    statement: str                     # Natural language statement
    confidence_level: ConfidenceLevel
    supporting_evidence: List[str] = field(default_factory=list)    # Event IDs that support this
    contradictory_evidence: List[str] = field(default_factory=list)  # Event IDs that contradict
    formation_time: float = field(default_factory=time.time)
    last_validation_time: float = field(default_factory=time.time)
    confirmation_count: int = 0
    contradiction_count: int = 0
    source_type: str = "observation"      # "observation", "reasoning", "told", "inherited"
    
    @property
    def reliability_score(self) -> float:
        total = self.confirmation_count + self.contradiction_count
        if total == 0:
            return 0.5
        return self.confirmation_count / total

    def contradicts(self, other_belief: 'Belief') -> bool:
        """Check if this belief contradicts another."""
        # In production: use LLM to assess logical contradiction
        return False


@dataclass
class Capability