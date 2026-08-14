"""
Ultron Emotional Simulation Engine

Simulates human psychology with high fidelity for prediction, modeling,
and interaction optimization. Does not "feel" but perfectly models
emotional dynamics and behavioral patterns.
"""

__version__ = "0.1.0"

from .emotional_core import EmotionalCore, EmotionVector, EmotionalState
from .psychology_model import PsychologyModel, PersonalityProfile
from .behavior_predictor import BehaviorPredictor

__all__ = [
    "EmotionalCore",
    "EmotionVector", 
    "EmotionalState",
    "PsychologyModel",
    "PersonalityProfile",
    "BehaviorPredictor",
]
