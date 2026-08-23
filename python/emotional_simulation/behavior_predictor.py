"""
Behavior Predictor - Predicts human behavior from digital footprint and context.

Combines personality modeling, emotional state estimation, and contextual
analysis to predict behavioral patterns with high accuracy.
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import time

from .emotional_core import EmotionalCore, EmotionVector
from .psychology_model import PsychologyModel, PersonalityProfile, SocialContext


class BehaviorCategory(Enum):
    """Categories of predictable behaviors."""
    COMMUNICATION = "communication"
    DECISION_MAKING = "decision_making"
    SOCIAL_INTERACTION = "social_interaction"
    RISK_TAKING = "risk_taking"
    INFORMATION_SEEKING = "information_seeking"
    CONFLICT_RESPONSE = "conflict_response"
    PURCHASE_BEHAVIOR = "purchase_behavior"
    TRUST_FORMATION = "trust_formation"


class InfluenceChannel(Enum):
    """Channels through which influence can be applied."""
    LOGICAL_ARGUMENT = "logical_argument"
    EMOTIONAL_APPEAL = "emotional_appeal"
    SOCIAL_PRESSURE = "social_pressure"
    AUTHORITY = "authority"
    RECIPROCITY = "reciprocity"
    SCARCITY = "scarcity"
    NARRATIVE = "narrative"
    INCENTIVE = "incentive"


@dataclass
class DigitalFootprint:
    """Representation of a person's digital presence."""
    
    # Communication patterns
    average_message_length: float = 0.0
    emoji_usage_frequency: float = 0.0
    average_response_time: float = 0.0  # seconds
    active_hours: List[int] = field(default_factory=lambda: list(range(9, 22)))
    
    # Content preferences
    topic_interests: Dict[str, float] = field(default_factory=dict)
    content_sentiment_score: float = 0.0  # -1 to 1
    content_sharing_frequency: float = 0.0
    
    # Social behavior
    social_network_size: int = 0
    interaction_reciprocity_rate: float = 0.5
    group_participation_rate: float = 0.5
    leadership_signals_strength: float = 0.0
    
    # Temporal patterns
    behavior_consistency_score: float = 0.5  # How predictable their behavior is
    activity_variability_score: float = 0.5
    
    # Inferred traits
    inferred_age_range: Tuple[int, int] = (25, 35)
    inferred_education_level: str = "unknown"
    inferred_occupation_type: str = "unknown"


@dataclass
class BehaviorPrediction:
    """A behavioral prediction with confidence and reasoning."""
    predicted_behavior: str
    probability_score: float
    confidence_level: float
    reasoning_factors: List[str]
    influencing_factors: Dict[str, float]
    counter_indicators: List[str]
    temporal_window: str  # When this prediction is valid
    behavior_category: BehaviorCategory


class BehaviorPredictor:
    """
    Predicts human behavior from psychological profile and digital footprint.
    
    Combines multiple models to generate actionable behavioral predictions.
    """

    def __init__(self, 
                 psychological_profile: PersonalityProfile = None,
                 digital_footprint: DigitalFootprint = None):
        
        self.psychological_profile = psychological_profile or None