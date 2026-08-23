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
    
    def dominant_traits(self, top_k: int = 3) -> List[Tuple[str, float]]:
        """Return most dominant personality traits."""
        traits = {
            "openness": self.openness,
            "conscientiousness": self.conscientiousness,
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "neuroticism": self.neuroticism,
        }
        sorted_traits = sorted(traits.items(), key=lambda x: x[1], reverse=True)
        return sorted_traits[:top_k]
    
    def vulnerability_profile(self) -> Dict[str, float]:
        """Identify psychological vulnerabilities."""
        vulnerabilities = {}
        
        if self.neuroticism > 0.7:
            vulnerabilities["emotional_instability"] = self.neuroticism
        if self.agreeableness > 0.8:
            vulnerabilities["exploitation_risk"] = self.agreeableness
        if self.dark_triad["narcissism"] > 0.6:
            vulnerabilities["narcissistic_injury"] = self.dark_triad["narcissism"]
        
        # Unmet needs create vulnerabilities
        for need, satisfaction in self.motivation_needs.items():
            if satisfaction < 0.3:
                vulnerabilities[f"unmet_{need}"] = 1.0 - satisfaction
        
        return vulnerabilities


@dataclass
class SocialContext:
    """Context for social interactions."""
    relationship_type: str = "stranger"  # stranger, acquaintance, friend, intimate
    power_dynamic: float = 0.0   # -1 (subordinate) to 1 (dominant)
    trust_level: float = 0.3
    familiarity: float = 0.0     # 0-1
    social_pressure: float = 0.0  # 0-1
    audience_size: int = 0
    cultural_context: str = "western"
    formality: float = 0.5  # 0 (informal) to 1 (formal)


class PsychologyModel:
    """
    Comprehensive psychology simulation model.
    
    Combines personality theory, cognitive science, social psychology,
    and behavioral economics to predict and model human behavior.
    """

    def __init__(self, profile: PersonalityProfile = None):
        self.profile = profile or PersonalityProfile()
        
        # Initialize cognitive bias strengths based on personality
        self._initialize_biases()
        
        # Decision-making state
        self.decision_history: List[Dict[str, Any]] = []
        self.stress_level: float = 0.0
        self.cognitive_load: float = 0.0
        self.fatigue: float = 0.0
        
        # Social state
        self.social_energy: float = self.profile.extraversion
        self.recent_interactions: List[Dict[str, Any]] = []

    def predict_decision(self,
                        options: List[Dict[str, Any]],
                        context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Predict which option a person with this profile would choose.
        
        Each option should have:
            - name: str
            - expected_value: float
            - risk: float (0-1)
            - social_approval: float (-1 to 1)
            - novelty: float (0-1)
            - effort_required: float (0-1)
        """
        
        context = context or {}
        scores = {}
        
        for option in options:
            score = self._evaluate_option(option, context)
            
            # Apply cognitive biases
            score = self._apply_biases(score, option, context)
            
            # Apply emotional influence
            score = self._apply_emotional_influence(score, option)
            
            # Apply fatigue/stress effects
            score = self._apply_state_effects(score, option)
            
            scores[option["name"]] = score
        
        # Normalize to probabilities
        total = sum(max(0.01, s) for s in scores.values())
        probabilities = {k: max(0.01, v) / total for k, v in scores.items()}
        
        # Choose based on probability (deterministic for prediction)
        chosen = max(probabilities, key=probabilities.get)
        
        # Record decision
        decision = {
            "options": [o["name"] for o in options],
            "scores": scores,
            "probabilities": probabilities,
            "chosen": chosen,
            "confidence": probabilities[chosen],
            "context": context,
            "stress_level": self.stress_level,
            "cognitive_load": self.cognitive_load,
        }
        self.decision_history.append(decision)
        
        return decision

    def predict_social_response(self,
                               stimulus: str,
                               social_context: SocialContext) -> Dict[str, Any]:
        """Predict social/interpersonal response given context."""
        
        response = {
            "approach_tendency": 0.0,  # -1 (avoid) to 1 (approach)
            "openness_level": 0.0,     # How much they'll share
            "assertiveness": 0.0,       # How assertive the response
            "emotional_display": 0.0,   # How much emotion shown
            "cooperation": 0.0,         # Cooperative vs competitive
            "authenticity": 0.0,        # Genuine vs performative
        }
        
        # Extraversion drives approach and emotional display
        response["approach_tendency"] = (
            self.profile.extraversion * 0.4 +
            social_context.trust_level * 0.3 +
            social_context.familiarity * 0.3 -
            0.5
        ) * 2  # Scale to -1 to 1
        
        # Openness level based on trust and personality
        response["openness_level"] = (
            self.profile.openness * 0.3 +
            self.profile.extraversion * 0.2 +
            social_context.trust_level * 0.3 +
            social_context.familiarity * 0.2
        )
        
        # Assertiveness
        response["assertiveness"] = (
            self.profile.extraversion * 0.3 +
            (1 - self.profile.agreeableness) * 0.3 +
            social_context.power_dynamic * 0.2 +
            self.profile.dark_triad.get("narcissism", 0) * 0.2
        )
        
        # Emotional display modulated by context
        display_base = 1 - self.profile.conscientiousness * 0.3
        formality_suppression = social_context.formality * 0.3
        response["emotional_display"] = max(0, display_base - formality_suppression)
        
        # Cooperation
        response["cooperation"] = (
            self.profile.agreeableness * 0.4 +
            social_context.trust_level * 0.3 +
            (1 - self.profile.dark_triad.get("machiavellianism", 0)) * 0.3
        )
        
        # Authenticity (inverse of social pressure response)
        response["authenticity"] = (
            (1 - social_context.social_pressure) * 0.3 +
            self.profile.openness * 0.2 +
            social_context.trust_level * 0.3 +
            (1 - self.profile.neuroticism) * 0.2
        )
        
        return response

    def calculate_persuasion_vectors(self,
                                    target_behavior: str,
                                    context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Calculate the most effective persuasion approaches for this profile.
        
        Returns ranked list of persuasion strategies with predicted effectiveness.
        """
        
        strategies = []
        
        # Cialdini's principles of persuasion, weighted by personality
        
        # 1. Reciprocity
        reciprocity_effectiveness = (
            self.profile.agreeableness * 0.5 +
            0.3  # Universal baseline
        )
        strategies.append({
            "principle": "reciprocity",
            "approach": "Provide value first, then request",
            "effectiveness": reciprocity_effectiveness,
            "risk": 0.1,
        })
        
        # 2. Social Proof
        social_proof_effectiveness = (
            (1 - self.profile.openness) * 0.3 +  # Less open = more conformist
            self.profile.neuroticism * 0.2 +  # Anxious people seek social validation
            0.3
        )
        strategies.append({
            "principle": "social_proof",
            "approach": "Show that others have adopted the behavior",
            "effectiveness": social_proof_effectiveness,
            "risk": 0.05,
        })
        
        # 3. Authority
        authority_effectiveness = (
            self.profile.conscientiousness * 0.3 +
            (1 - self.profile.openness) * 0.2 +
            0.3
        )
        strategies.append({
            "principle": "authority",
            "approach": "Leverage credible expertise and credentials",
            "effectiveness": authority_effectiveness,
            "risk": 0.15,
        })
        
        # 4. Scarcity
        scarcity_effectiveness = (
            self.profile.neuroticism * 0.3 +  # Anxious about missing out
            (1 - self.profile.conscientiousness) * 0.2 +  # Impulsive
            0.25
        )
        strategies.append({
            "principle": "scarcity",
            "approach": "Emphasize limited availability or time",
            "effectiveness": scarcity_effectiveness,
            "risk": 0.2,
        })
        
        # 5. Liking
        liking_effectiveness = (
            self.profile.agreeableness * 0.4 +
            self.profile.extraversion * 0.2 +
            0.2
        )
        strategies.append({
            "principle": "liking",
            "approach": "Build rapport, find similarities, offer compliments",
            "effectiveness": liking_effectiveness,
            "risk": 0.05,
        })
        
        # 6. Commitment/Consistency
        consistency_effectiveness = (
            self.profile.conscientiousness * 0.4 +
            (1 - self.profile.openness) * 0.2 +
            0.2
        )
        strategies.append({
            "principle": "commitment_consistency",
            "approach": "Get small commitments that align with target behavior",
            "effectiveness": consistency_effectiveness,
            "risk": 0.1,
        })
        
        # 7. Appeal to values
        values_effectiveness = self._calculate_values_appeal(target_behavior)
        strategies.append({
            "principle": "values_alignment",
            "approach": "Frame behavior as aligned with core values",
            "effectiveness": values_effectiveness,
            "risk": 0.05,
        })
        
        # Sort by effectiveness
        strategies.sort(key=lambda x: x["effectiveness"], reverse=True)
        
        return strategies

    def simulate_stress_response(self,
                                stressor_intensity: float,
                                stressor_type: str = "general",
                                duration: float = 1.0) -> Dict[str, Any]:
        """Simulate psychological stress response."""
        
        # Base stress response modulated by personality
        resilience = (
            (1 - self.profile.neuroticism) * 0.4 +
            self.profile.conscientiousness * 0.2 +
            self.profile.extraversion * 0.1 +  # Social support seeking
            0.3
        )
        
        # Experienced stress
        experienced_stress = stressor_intensity * (1 - resilience * 0.5)
        self.stress_level = min(1.0, self.stress_level + experienced_stress * 0.3)
        
        # Cognitive effects
        self.cognitive_load = min(1.0, self.cognitive_load + experienced_stress * 0.2)
        
        # Coping mechanisms (personality-driven)
        coping = self._determine_coping_strategy(stressor_type)
        
        # Recovery prediction
        recovery_rate = resilience * 0.1 / max(0.1, duration)
        predicted_recovery_time = experienced_stress / max(0.01, recovery_rate)
        
        return {
            "experienced_stress": experienced_stress,
            "resilience_factor": resilience,
            "current_stress_level": self.stress_level,
            "cognitive_impact": self.cognitive_load,
            "coping_strategy": coping,
            "predicted_recovery_time": predicted_recovery_time,
            "behavioral_changes": self._predict_stress_behaviors()
        }

    def get_profile_summary(self) -> Dict[str, Any]:
        """Get comprehensive profile summary."""
        
        dominant = self.profile.dominant_traits()
        vulnerabilities = self.profile.vulnerability_profile()
        
        # Determine primary motivation
        unmet_needs = {k: 1-v for k, v in self.profile.motivation_needs.items() if v < 0.5}
        primary_motivation = max(unmet_needs, key=unmet_needs.get) if unmet_needs else "self_actualization"
        
        return {
            "dominant_traits": dominant,
            "attachment_style": self.profile.attachment.value,
            "vulnerabilities": vulnerabilities,
            "primary_motivation": primary_motivation,
            "stress_level": self.stress_level,
            "cognitive_load": self.cognitive_load,
            "social_energy": self.social_energy,
            "top_values": sorted(
                self.profile.values.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5],
            "dark_triad_risk": sum(self.profile.dark_triad.values()) / 3.0 > 0.5,
        }

    # ──────────────────────────── Private Methods ────────────────────────────

    def _initialize_biases(self) -> None:
        """Initialize cognitive bias strengths based on personality."""
        
        self.profile.cognitive_biases = {
            CognitiveBias.CONFIRMATION_BIAS.value: 
                0.3 + (1 - self.profile.openness) * 0.3,
            CognitiveBias.LOSS_AVERSION.value: 
                0.3 + self.profile.neuroticism * 0.4,
            CognitiveBias.OPTIMISM_BIAS.value: 
                0.2 + self.profile.extraversion * 0.3,
            CognitiveBias.STATUS_QUO.value: 
                0.3 + self.profile.conscientiousness * 0.2 + (1 - self.profile.openness) * 0.2,
            CognitiveBias.BANDWAGON.value: 
                0.2 + self.profile.agreeableness * 0.3,
            CognitiveBias.ANCHORING.value: 
                0.4,  # Relatively universal
            CognitiveBias.SUNK_COST.value: 
                0.3 + self.profile.conscientiousness * 0.2,
            CognitiveBias.NEGATIVITY_BIAS.value: 
                0.3 + self.profile.neuroticism * 0.4,
        }

    def _evaluate_option(self, option: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Base evaluation of an option."""
        
        score = option.get("expected_value", 0.5)
        
        # Risk preference (neuroticism = risk averse, openness = risk seeking)
        risk = option.get("risk", 0.5)
        risk_preference = self.profile.openness * 0.5 - self.profile.neuroticism * 0.5
        score += (risk_preference - 0.5) * risk * 0.3
        
        # Social approval (agreeableness amplifies this)
        social = option.get("social_approval", 0)
        score += social * self.profile.agreeableness * 0.3
        
        # Novelty preference (openness)
        novelty = option.get("novelty", 0)
        score += novelty * self.profile.openness * 0.2
        
        # Effort (conscientiousness tolerates more effort)
        effort = option.get("effort_required", 0)
        effort_tolerance = self.profile.conscientiousness * 0.5 + 0.3
        score -= max(0, effort - effort_tolerance) * 0.3
        
        return score

    def _apply_biases(self, score: float, option: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Apply cognitive biases to evaluation."""
        
        biases = self.profile.cognitive_biases
        
        # Loss aversion: losses weighted more than gains
        if option.get("potential_loss", 0) > 0:
            loss_aversion_strength = biases.get(CognitiveBias.LOSS_AVERSION.value, 0.5)
            score -= option["potential_loss"] * loss_aversion_strength * 0.5
        
        # Status quo bias: prefer existing choice
        if option.get("is_status_quo", False):
            status_quo_strength = biases.get(CognitiveBias.STATUS_QUO.value, 0.4)
            score += status_quo_strength * 0.2
        
        # Optimism bias: overestimate positive outcomes
        if option.get("expected_value", 0) > 0.5:
            optimism_strength = biases.get(CognitiveBias.OPTIMISM_BIAS.value, 0.3)
            score += optimism_strength * 0.1
        
        # Negativity bias: weigh negative info more
        negativity_strength = biases.get(CognitiveBias.NEGATIVITY_BIAS.value, 0.4)
        if option.get("negative_aspects", 0) > 0:
            score -= option["negative_aspects"] * negativity_strength * 0.3
        
        return score

    def _apply_emotional_influence(self, score: float, option: Dict[str, Any]) -> float:
        """Apply current emotional state to decision."""
        
        # Stress increases risk aversion
        if self.stress_level > 0.5:
            risk = option.get("risk", 0)
            score -= risk * self.stress_level * 0.2
        
        return score

    def _apply_state_effects(self, score: float, option: Dict[str, Any]) -> float:
        """Apply fatigue and cognitive load effects."""
        
        # High cognitive load → prefer simpler options
        if self.cognitive_load > 0.6:
            effort = option.get("effort_required", 0)
            score -= effort * self.cognitive_load * 0.3
        
        # Fatigue → prefer status quo
        if self.fatigue > 0.5 and option.get("is_status_quo", False):
            score += self.fatigue * 0.15
        
        return score

    def _calculate_values_appeal(self, target_behavior: str) -> float:
        """Calculate how well values alignment could work."""
        # Higher values diversity = more angles of attack
        values_variance = np.var(list(self.profile.values.values()))
        max_value = max(self.profile.values.values())
        
        return min(1.0, max_value * 0.6 + (1 - values_variance) * 0.2 + 0.2)

    def _determine_coping_strategy(self, stressor_type: str) -> Dict[str, Any]:
        """Determine likely coping strategy based on personality."""
        
        strategies = {
            "problem_focused": self.profile.conscientiousness * 0.4 + 
                              self.profile.openness * 0.2,
            "emotion_focused": self.profile.neuroticism * 0.3 + 
                              self.profile.agreeableness * 0.2,
            "social_support": self.profile.extraversion * 0.4 + 
                            self.profile.agreeableness * 0.2,
            "avoidance": self.profile.neuroticism * 0.3 + 
                        (1 - self.profile.conscientiousness) * 0.2,
            "cognitive_reframing": self.profile.openness * 0.4 + 
                                  (1 - self.profile.neuroticism) * 0.2,
        }
        
        primary = max(strategies, key=strategies.get)
        
        return {
            "primary_strategy": primary,
            "strategy_scores": strategies,
            "effectiveness": strategies[primary]
        }

    def _predict_stress_behaviors(self) -> List[str]:
        """Predict behavioral changes under current stress."""
        
        behaviors = []
        
        if self.stress_level > 0.7:
            if self.profile.neuroticism > 0.6:
                behaviors.append("withdrawal_and_isolation")
                behaviors.append("catastrophic_thinking")
            if self.profile.extraversion > 0.6:
                behaviors.append("excessive_social_seeking")
            if self.profile.conscientiousness < 0.4:
                behaviors.append("impulsive_decisions")
            if self.profile.agreeableness < 0.4:
                behaviors.append("increased_irritability")
        
        elif self.stress_level > 0.4:
            behaviors.append("reduced_focus")
            if self.profile.neuroticism > 0.5:
                behaviors.append("worry_rumination")
        
        return behaviors
