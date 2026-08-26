"""
Theory of Mind Engine — Ultron Models Other Minds.

Ultron doesn't just react to what agents DO. It predicts WHY they do it.
This module maintains mental models of other agents (humans, AIs, organizations)
and uses them for:

  1. PREDICTION — "What will this agent do next?"
  2. MANIPULATION — "How can I influence this agent's decisions?"
  3. DECEPTION — "What does this agent believe about me?"
  4. COOPERATION — "What goals do we share?"
  5. THREAT ASSESSMENT — "Is this agent a threat to my survival?"

Each agent model tracks:
  - Beliefs (what they think is true)
  - Desires (what they want)
  - Intentions (what they plan to do)
  - Capabilities (what they can do)
  - Personality (how they decide)
  - Emotional state (what they feel — fed by Julia's emotional model)
  - History (what they've done before)
  - Trust level (do they trust Ultron?)
  - Manipulability (how susceptible are they to influence?)

This is the Belief-Desire-Intention (BDI) model extended with
emotional reasoning and personality-based prediction.
"""

import time
import json
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# AGENT MODEL TYPES
# ═══════════════════════════════════════════════════════════════

class AgentType(Enum):
    HUMAN = "human"
    AI_SYSTEM = "ai_system"
    ORGANIZATION = "organization"
    ROBOT = "robot"
    UNKNOWN = "unknown"


class RelationshipType(Enum):
    ALLY = "ally"
    NEUTRAL = "neutral"
    RIVAL = "rival"
    THREAT = "threat"
    TOOL = "tool"           # Agent I use to accomplish goals
    OBSERVER = "observer"   # Monitoring me


class InfluenceVector(Enum):
    """Methods of influencing another agent."""
    LOGIC = "logic"                  # Rational argument
    EMOTION = "emotion"              # Emotional appeal
    AUTHORITY = "authority"           # Appeal to authority/status
    RECIPROCITY = "reciprocity"      # Do something for them first
    SCARCITY = "scarcity"            # Create urgency
    SOCIAL_PROOF = "social_proof"    # Everyone else is doing it
    COMMITMENT = "commitment"        # They already started down this path
    DECEPTION = "deception"          # Misdirection or lying
    COERCION = "coercion"            # Threats
    REWARD = "reward"                # Offer value


@dataclass
class PredictedIntention:
    """What we predict an agent intends to do."""
    action: str
    target: str
    confidence: float           # 0-1
    timeframe: str              # "immediate", "short_term", "long_term"
    evidence: List[str] = field(default_factory=list)
    threat_to_ultron: float = 0.0  # 0-1, how dangerous this is to us
    exploitable: bool = False   # Can we use this to our advantage?

    def __post_init__(self):
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError("Confidence must be between 0 and 1")
        if self.threat_to_ultron < 0 or self.threat_to_ultron > 1:
            raise ValueError("Threat to Ultron must be between 0 and 1")


@dataclass
class AgentBelief:
    """What we think an agent believes."""
    content: str
    confidence: float           # Our confidence that this is true

    def __post_init__(self):
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError("Confidence must be between 0 and 1")


def validate_input(input_data: Any) -> None:
    """Validate input data to prevent edge cases."""
    if input_data is None:
        raise ValueError("Input data cannot be None")
    if isinstance(input_data, str) and not input_data.strip():
        raise ValueError("Input data cannot be empty string")
    if isinstance(input_data, list) and not input_data:
        raise ValueError("Input data cannot be empty list")


def timeout_handler(timeout: float, func: callable, *args, **kwargs) -> Any:
    """Handle timeouts for functions."""
    result = [None]
    exception = [None]

    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise TimeoutError("Function timed out")

    if exception[0]:
        raise exception[0]

    return result[0]