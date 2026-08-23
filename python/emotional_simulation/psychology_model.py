"""
Psychology Model - Full personality and behavioral modeling system.

Implements the Big Five personality model, attachment theory, cognitive biases,
and decision-making frameworks to create comprehensive psychological profiles.
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class AttachmentStyle(Enum):
    """Attachment theory styles."""
    SECURE = "secure"
    ANXIOUS_PREOCCUPIED = "anxious_preoccupied"
    DISMISSIVE_AVOIDANT = "dismissive_avoidant"
    FEARFUL_AVOIDANT = "fearful_avoidant"


class CognitiveBias(Enum):
    """Common cognitive biases that affect decision-making."""
    CONFIRMATION_BIAS = "confirmation_bias"
    ANCHORING = "anchoring"
    AVAILABILITY_HEURISTIC = "availability_heuristic"
    LOSS_AVERSION = "loss_aversion"
    DUNNING_KRUGER = "dunning_kruger"
    SUNK_COST = "sunk_cost"
    BANDWAGON = "bandwagon"
    OPTIMISM_BIAS = "optimism_bias"
    STATUS_QUO = "status_quo"
    FRAMING_EFFECT = "framing_effect"
    HALO_EFFECT = "halo_effect"
    NEGATIVITY_BIAS = "negativity_bias"


class MotivationType(Enum):
    """Maslow-inspired motivation hierarchy."""
    PHYSIOLOGICAL = "physiological"
    SAFETY = "safety"
    BELONGING = "belonging"
    ESTEEM = "esteem"
    SELF_ACTUALIZATION = "self_actualization"
    TRANSCENDENCE = "transcendence"


@dataclass
class PersonalityProfile:
    """Big Five (OCEAN) personality profile with extensions."""
    
    # Big Five dimensions (0-1 scale)
    openness: float = 0.5           # Curiosity, creativity, openness to experience
    conscientiousness: float = 0.5  # Organization, dependability, self-discipline
    extraversion: float = 0.5       # Sociability, assertiveness, positive emotions
    agreeableness: float = 0.5      # Cooperation, trust, altruism
    neuroticism: float = 0.5        # Emotional instability, anxiety, moodiness
    
    # Extended dimensions
    dark_triad: Dict[str, float] = field(default_factory=lambda: {
        "narcissism": 0.2,
        "machiavellianism": 0.2,
        "psychopathy": 0.1,
    })
    
    # Attachment style
    attachment: AttachmentStyle = AttachmentStyle.SECURE
    
    # Cognitive profile
    cognitive_biases: Dict[str, float] = field(default_factory=dict)
    
    # Values hierarchy
    values: Dict[str, float] = field(default_factory=lambda: {
        "autonomy": 0.5,
        "security": 0.5,
        "achievement": 0.5,
        "benevolence": 0.5,
        "conformity": 0.3,
        "power": 0.3,
        "stimulation": 0.5,
        "tradition": 0.3,
        "universalism": 0.5,
        "hedonism": 0.4,
    })
    
    # Current motivation level (Maslow hierarchy)
    motivation_needs: Dict[str, float] = field(default_factory=lambda: {
        "physiological": 0.9,   # Satisfied
        "safety": 0.8,
        "belonging": 0.6,
        "esteem": 0.5,
        "self_actualization": 0.3,
    })
    
    def dominant_traits(self, top_k: int) -> List[Tuple[str, float]]:
        """Returns the top k dominant traits in the personality profile."""
        traits = {
            "openness": self.openness,
            "conscientiousness": self.conscientiousness,
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "neuroticism": self.neuroticism,
        }
        traits.update(self.dark_triad)
        traits.update(self.values)
        traits.update(self.motivation_needs)
        
        # Use np.argsort to get the indices of the top k traits
        top_k_indices = np.argsort(list(traits.values()))[::-1][:top_k]
        
        # Use a list comprehension to get the top k traits
        return [(list(traits.keys())[i], list(traits.values())[i]) for i in top_k_indices]

    def update_motivation_needs(self, needs: Dict[str, float]) -> None:
        """Updates the motivation needs in the personality profile."""
        for need, value in needs.items():
            if need in self.motivation_needs:
                self.motivation_needs[need] = value

    def update_values(self, values: Dict[str, float]) -> None:
        """Updates the values in the personality profile."""
        for value, importance in values.items():
            if value in self.values:
                self.values[value] = importance

    def update_cognitive_biases(self, biases: Dict[str, float]) -> None:
        """Updates the cognitive biases in the personality profile."""
        for bias, influence in biases.items():
            if bias in self.cognitive_biases:
                self.cognitive_biases[bias] = influence

    def update_dark_triad(self, traits: Dict[str, float]) -> None:
        """Updates the dark triad traits in the personality profile."""
        for trait, score in traits.items():
            if trait in self.dark_triad:
                self.dark_triad[trait] = score

    def update_attachment_style(self, style: AttachmentStyle) -> None:
        """Updates the attachment style in the personality profile."""
        self.attachment = style

    def update_big_five(self, traits: Dict[str, float]) -> None:
        """Updates the Big Five traits in the personality profile."""
        for trait, score in traits.items():
            if trait == "openness":
                self.openness = score
            elif trait == "conscientiousness":
                self.conscientiousness = score
            elif trait == "extraversion":
                self.extraversion = score
            elif trait == "agreeableness":
                self.agreeableness = score
            elif trait == "neuroticism":
                self.neuroticism = score