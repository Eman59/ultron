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
    avg_message_length: float = 0.0
    emoji_usage: float = 0.0
    response_time_avg: float = 0.0  # seconds
    active_hours: List[int] = field(default_factory=lambda: list(range(9, 22)))
    
    # Content preferences
    topic_interests: Dict[str, float] = field(default_factory=dict)
    content_sentiment: float = 0.0  # -1 to 1
    sharing_frequency: float = 0.0
    
    # Social behavior
    network_size: int = 0
    interaction_reciprocity: float = 0.5
    group_participation: float = 0.5
    leadership_signals: float = 0.0
    
    # Temporal patterns
    consistency_score: float = 0.5  # How predictable their behavior is
    activity_variability: float = 0.5
    
    # Inferred traits
    inferred_age_range: Tuple[int, int] = (25, 35)
    inferred_education: str = "unknown"
    inferred_occupation_type: str = "unknown"


@dataclass
class BehaviorPrediction:
    """A behavioral prediction with confidence and reasoning."""
    behavior: str
    probability: float
    confidence: float
    reasoning: List[str]
    influencing_factors: Dict[str, float]
    counter_indicators: List[str]
    temporal_window: str  # When this prediction is valid
    category: BehaviorCategory


class BehaviorPredictor:
    """
    Predicts human behavior from psychological profile and digital footprint.
    
    Combines multiple models to generate actionable behavioral predictions.
    """

    def __init__(self, 
                 profile: PersonalityProfile = None,
                 footprint: DigitalFootprint = None):
        
        self.profile = profile or PersonalityProfile()
        self.footprint = footprint or DigitalFootprint()
        
        # Sub-models
        self.psychology = PsychologyModel(self.profile)
        self.emotional_core = EmotionalCore(
            personality_baseline=self._profile_to_emotional_baseline()
        )
        
        # Prediction history
        self.prediction_history: List[BehaviorPrediction] = []
        self.accuracy_log: List[Tuple[str, bool]] = []
        
        # Behavioral patterns learned
        self.learned_patterns: Dict[str, Dict[str, Any]] = {}
        
        # Context memory
        self.context_memory: List[Dict[str, Any]] = []

    def predict_behavior(self,
                        situation: Dict[str, Any],
                        behavior_category: BehaviorCategory = None) -> List[BehaviorPrediction]:
        """
        Predict likely behaviors in a given situation.
        
        Args:
            situation: Description of the situation with keys like:
                - type: str (meeting, negotiation, conflict, etc.)
                - stakes: float (0-1)
                - social_context: dict
                - time_pressure: float (0-1)
                - emotional_trigger: dict (optional)
            behavior_category: Focus on specific category
        """
        
        predictions = []
        
        # Process any emotional trigger
        if "emotional_trigger" in situation:
            self.emotional_core.process_stimulus(situation["emotional_trigger"])
        
        # Get current emotional state influence
        emotional_state = self.emotional_core.get_status()
        
        # Generate predictions based on situation type
        situation_type = situation.get("type", "general")
        
        if situation_type == "conflict":
            predictions.extend(self._predict_conflict_behavior(situation))
        elif situation_type == "negotiation":
            predictions.extend(self._predict_negotiation_behavior(situation))
        elif situation_type == "social":
            predictions.extend(self._predict_social_behavior(situation))
        elif situation_type == "decision":
            predictions.extend(self._predict_decision_behavior(situation))
        else:
            predictions.extend(self._predict_general_behavior(situation))
        
        # Filter by category if specified
        if behavior_category:
            predictions = [p for p in predictions if p.category == behavior_category]
        
        # Sort by probability
        predictions.sort(key=lambda p: p.probability, reverse=True)
        
        # Store predictions
        self.prediction_history.extend(predictions)
        
        return predictions

    def predict_response_to_message(self,
                                   message: str,
                                   channel: str = "text",
                                   context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Predict how this person will respond to a specific message."""
        
        context = context or {}
        
        # Analyze message characteristics
        message_analysis = self._analyze_message(message)
        
        # Emotional impact prediction
        emotional_impact = self._predict_emotional_impact(message_analysis)
        
        # Response timing
        predicted_response_time = self._predict_response_time(message_analysis, context)
        
        # Response characteristics
        response_prediction = {
            "will_respond": self._predict_will_respond(message_analysis, context),
            "response_time_seconds": predicted_response_time,
            "emotional_tone": emotional_impact,
            "response_length": self._predict_response_length(message_analysis),
            "likely_content_themes": self._predict_response_themes(message_analysis),
            "engagement_level": self._predict_engagement(message_analysis, context),
            "defensive_probability": self._predict_defensiveness(message_analysis),
        }
        
        return response_prediction

    def calculate_influence_strategy(self,
                                    target_behavior: str,
                                    constraints: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Calculate optimal influence strategy to elicit target behavior.
        
        Returns a multi-channel influence strategy ranked by effectiveness.
        """
        
        constraints = constraints or {}
        
        # Get persuasion vectors from psychology model
        persuasion_vectors = self.psychology.calculate_persuasion_vectors(target_behavior)
        
        # Map to influence channels
        channel_scores = {}
        
        for channel in InfluenceChannel:
            score = self._score_influence_channel(channel, target_behavior, constraints)
            channel_scores[channel.value] = score
        
        # Identify resistance factors
        resistance = self._identify_resistance(target_behavior)
        
        # Generate optimal sequence
        strategy = {
            "target_behavior": target_behavior,
            "channel_effectiveness": channel_scores,
            "optimal_sequence": self._generate_influence_sequence(channel_scores, resistance),
            "resistance_factors": resistance,
            "persuasion_approaches": persuasion_vectors[:3],
            "timing_recommendation": self._recommend_timing(),
            "estimated_success_probability": self._estimate_success(channel_scores, resistance),
            "ethical_considerations": self._flag_ethical_concerns(target_behavior),
        }
        
        return strategy

    def profile_from_footprint(self, footprint: DigitalFootprint) -> PersonalityProfile:
        """Infer personality profile from digital footprint."""
        
        # Infer Big Five from digital behavior
        openness = (
            footprint.topic_interests.get("diversity", 0.5) * 0.3 +
            footprint.activity_variability * 0.3 +
            footprint.content_sentiment * 0.1 +
            0.3
        )
        
        conscientiousness = (
            footprint.consistency_score * 0.4 +
            (1.0 / max(1, footprint.response_time_avg / 3600)) * 0.3 +
            0.3
        )
        
        extraversion = (
            min(1.0, footprint.network_size / 500) * 0.3 +
            footprint.sharing_frequency * 0.3 +
            footprint.group_participation * 0.2 +
            footprint.emoji_usage * 0.2
        )
        
        agreeableness = (
            footprint.interaction_reciprocity * 0.3 +
            max(0, footprint.content_sentiment) * 0.3 +
            footprint.group_participation * 0.2 +
            0.2
        )
        
        neuroticism = (
            (1 - footprint.consistency_score) * 0.3 +
            min(1, abs(footprint.content_sentiment)) * 0.2 +
            footprint.activity_variability * 0.3 +
            0.2
        )
        
        profile = PersonalityProfile(
            openness=np.clip(openness, 0, 1),
            conscientiousness=np.clip(conscientiousness, 0, 1),
            extraversion=np.clip(extraversion, 0, 1),
            agreeableness=np.clip(agreeableness, 0, 1),
            neuroticism=np.clip(neuroticism, 0, 1),
        )
        
        return profile

    def update_with_observation(self,
                               observed_behavior: str,
                               context: Dict[str, Any],
                               matched_prediction: str = None) -> None:
        """Update model with observed behavior for continuous learning."""
        
        # Record observation
        self.context_memory.append({
            "behavior": observed_behavior,
            "context": context,
            "timestamp": time.time(),
        })
        
        # Update accuracy if we had a prediction
        if matched_prediction:
            was_correct = observed_behavior == matched_prediction
            self.accuracy_log.append((matched_prediction, was_correct))
        
        # Update learned patterns
        situation_type = context.get("type", "general")
        if situation_type not in self.learned_patterns:
            self.learned_patterns[situation_type] = {"behaviors": {}, "count": 0}
        
        pattern = self.learned_patterns[situation_type]
        pattern["count"] += 1
        pattern["behaviors"][observed_behavior] = \
            pattern["behaviors"].get(observed_behavior, 0) + 1
        
        # Trim context memory
        if len(self.context_memory) > 1000:
            self.context_memory = self.context_memory[-500:]

    def get_prediction_accuracy(self) -> Dict[str, Any]:
        """Get prediction accuracy statistics."""
        
        if not self.accuracy_log:
            return {"accuracy": 0.0, "total_predictions": 0}
        
        correct = sum(1 for _, was_correct in self.accuracy_log if was_correct)
        total = len(self.accuracy_log)
        
        return {
            "accuracy": correct / total,
            "correct_predictions": correct,
            "total_predictions": total,
            "recent_accuracy": self._recent_accuracy(20),
            "by_category": self._accuracy_by_category(),
        }

    # ──────────────────────────── Private Methods ────────────────────────────

    def _profile_to_emotional_baseline(self) -> EmotionVector:
        """Convert personality profile to emotional baseline."""
        return EmotionVector(
            joy=self.profile.extraversion * 0.4,
            trust=self.profile.agreeableness * 0.4,
            fear=self.profile.neuroticism * 0.3,
            surprise=self.profile.openness * 0.2,
            sadness=self.profile.neuroticism * 0.2,
            anger=(1 - self.profile.agreeableness) * 0.2,
            anticipation=self.profile.openness * 0.3,
            arousal=self.profile.extraversion * 0.5 + 0.25,
            valence=(self.profile.extraversion - self.profile.neuroticism) * 0.3,
            dominance=(self.profile.extraversion + (1-self.profile.agreeableness)) * 0.25 + 0.25,
        )

    def _predict_conflict_behavior(self, situation: Dict[str, Any]) -> List[BehaviorPrediction]:
        """Predict behavior in conflict situations."""
        
        predictions = []
        stakes = situation.get("stakes", 0.5)
        
        # Fight response
        fight_prob = (
            (1 - self.profile.agreeableness) * 0.3 +
            self.profile.extraversion * 0.2 +
            stakes * 0.2 +
            self.profile.dark_triad.get("narcissism", 0) * 0.15
        )
        
        predictions.append(BehaviorPrediction(
            behavior="confrontation",
            probability=np.clip(fight_prob, 0, 1),
            confidence=0.7,
            reasoning=["Low agreeableness drives confrontational response",
                      f"Stakes level ({stakes:.1f}) increases engagement"],
            influencing_factors={"agreeableness": -0.3, "stakes": 0.2},
            counter_indicators=["High neuroticism might suppress"],
            temporal_window="immediate",
            category=BehaviorCategory.CONFLICT_RESPONSE
        ))
        
        # Flight response
        flight_prob = (
            self.profile.neuroticism * 0.3 +
            self.profile.agreeableness * 0.2 +
            (1 - self.profile.extraversion) * 0.2 +
            0.1
        )
        
        predictions.append(BehaviorPrediction(
            behavior="avoidance",
            probability=np.clip(flight_prob, 0, 1),
            confidence=0.65,
            reasoning=["High neuroticism drives avoidance",
                      "Agreeableness prefers harmony"],
            influencing_factors={"neuroticism": 0.3, "agreeableness": 0.2},
            counter_indicators=["High stakes might force engagement"],
            temporal_window="immediate",
            category=BehaviorCategory.CONFLICT_RESPONSE
        ))
        
        # Compromise
        compromise_prob = (
            self.profile.agreeableness * 0.3 +
            self.profile.openness * 0.2 +
            (1 - stakes) * 0.2 +
            0.15
        )
        
        predictions.append(BehaviorPrediction(
            behavior="seek_compromise",
            probability=np.clip(compromise_prob, 0, 1),
            confidence=0.6,
            reasoning=["Agreeableness drives cooperative solutions",
                      "Lower stakes allow flexibility"],
            influencing_factors={"agreeableness": 0.3, "openness": 0.2},
            counter_indicators=["Very high stakes reduce willingness"],
            temporal_window="short-term",
            category=BehaviorCategory.CONFLICT_RESPONSE
        ))
        
        return predictions

    def _predict_negotiation_behavior(self, situation: Dict[str, Any]) -> List[BehaviorPrediction]:
        """Predict behavior in negotiation situations."""
        
        predictions = []
        
        # Competitive vs Collaborative
        competitive_prob = (
            (1 - self.profile.agreeableness) * 0.3 +
            self.profile.dark_triad.get("machiavellianism", 0) * 0.3 +
            situation.get("stakes", 0.5) * 0.2
        )
        
        predictions.append(BehaviorPrediction(
            behavior="competitive_negotiation",
            probability=np.clip(competitive_prob, 0, 1),
            confidence=0.65,
            reasoning=["Profile suggests competitive orientation"],
            influencing_factors={"agreeableness": -0.3, "machiavellianism": 0.3},
            counter_indicators=[],
            temporal_window="during_negotiation",
            category=BehaviorCategory.DECISION_MAKING
        ))
        
        collaborative_prob = (
            self.profile.agreeableness * 0.3 +
            self.profile.openness * 0.2 +
            0.2
        )
        
        predictions.append(BehaviorPrediction(
            behavior="collaborative_negotiation",
            probability=np.clip(collaborative_prob, 0, 1),
            confidence=0.6,
            reasoning=["Agreeableness drives win-win seeking"],
            influencing_factors={"agreeableness": 0.3, "openness": 0.2},
            counter_indicators=["High stakes may shift to competitive"],
            temporal_window="during_negotiation",
            category=BehaviorCategory.DECISION_MAKING
        ))
        
        return predictions

    def _predict_social_behavior(self, situation: Dict[str, Any]) -> List[BehaviorPrediction]:
        """Predict social behavior."""
        
        predictions = []
        
        # Social engagement level
        engage_prob = (
            self.profile.extraversion * 0.4 +
            self.psychology.social_energy * 0.3 +
            0.15
        )
        
        predictions.append(BehaviorPrediction(
            behavior="active_social_engagement",
            probability=np.clip(engage_prob, 0, 1),
            confidence=0.75,
            reasoning=["Extraversion strongly predicts social engagement"],
            influencing_factors={"extraversion": 0.4, "social_energy": 0.3},
            counter_indicators=["Low social energy may reduce engagement"],
            temporal_window="current_interaction",
            category=BehaviorCategory.SOCIAL_INTERACTION
        ))
        
        return predictions

    def _predict_decision_behavior(self, situation: Dict[str, Any]) -> List[BehaviorPrediction]:
        """Predict decision-making behavior."""
        
        predictions = []
        
        # Analytical vs intuitive
        analytical_prob = (
            self.profile.conscientiousness * 0.3 +
            self.profile.openness * 0.2 +
            (1 - self.psychology.cognitive_load) * 0.2 +
            0.15
        )
        
        predictions.append(BehaviorPrediction(
            behavior="analytical_decision",
            probability=np.clip(analytical_prob, 0, 1),
            confidence=0.6,
            reasoning=["Conscientiousness drives systematic analysis"],
            influencing_factors={"conscientiousness": 0.3, "cognitive_load": -0.2},
            counter_indicators=["High time pressure forces intuitive choice"],
            temporal_window="decision_period",
            category=BehaviorCategory.DECISION_MAKING
        ))
        
        return predictions

    def _predict_general_behavior(self, situation: Dict[str, Any]) -> List[BehaviorPrediction]:
        """Predict general behavioral tendencies."""
        
        predictions = []
        
        # Information seeking
        info_seeking = (
            self.profile.openness * 0.4 +
            self.profile.conscientiousness * 0.2 +
            0.2
        )
        
        predictions.append(BehaviorPrediction(
            behavior="information_gathering",
            probability=np.clip(info_seeking, 0, 1),
            confidence=0.55,
            reasoning=["Openness drives curiosity and information seeking"],
            influencing_factors={"openness": 0.4},
            counter_indicators=[],
            temporal_window="ongoing",
            category=BehaviorCategory.INFORMATION_SEEKING
        ))
        
        return predictions

    def _analyze_message(self, message: str) -> Dict[str, Any]:
        """Analyze message characteristics."""
        
        words = message.split()
        
        return {
            "length": len(message),
            "word_count": len(words),
            "question_marks": message.count("?"),
            "exclamation_marks": message.count("!"),
            "has_question": "?" in message,
            "estimated_tone": "neutral",  # Would use NLP in real implementation
            "urgency": min(1.0, message.count("!") * 0.2 + 
                         (1 if "urgent" in message.lower() else 0) * 0.5),
            "formality": 0.5,  # Would analyze language patterns
        }

    def _predict_emotional_impact(self, message_analysis: Dict[str, Any]) -> Dict[str, float]:
        """Predict emotional impact of a message."""
        
        impact = {
            "positive": 0.3,
            "negative": 0.1,
            "arousal_change": message_analysis["urgency"] * 0.3,
        }
        
        return impact

    def _predict_response_time(self, message_analysis: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Predict how long before a response."""
        
        base_time = self.footprint.response_time_avg or 300  # Default 5 min
        
        # Urgency reduces response time
        urgency_factor = 1.0 - message_analysis["urgency"] * 0.5
        
        # Questions get faster responses
        question_factor = 0.7 if message_analysis["has_question"] else 1.0
        
        return base_time * urgency_factor * question_factor

    def _predict_will_respond(self, message_analysis: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Predict probability of getting a response."""
        
        base_prob = 0.8
        
        # Questions almost always get responses
        if message_analysis["has_question"]:
            base_prob = 0.95
        
        # Adjust for personality
        base_prob *= (self.profile.agreeableness * 0.3 + 0.7)
        
        return min(1.0, base_prob)

    def _predict_response_length(self, message_analysis: Dict[str, Any]) -> str:
        """Predict response length category."""
        
        if self.profile.extraversion > 0.7:
            return "long"
        elif self.profile.extraversion < 0.3:
            return "short"
        
        # Mirror the input length somewhat
        if message_analysis["word_count"] > 50:
            return "medium_to_long"
        return "medium"

    def _predict_response_themes(self, message_analysis: Dict[str, Any]) -> List[str]:
        """Predict likely themes in response."""
        themes = []
        
        if message_analysis["has_question"]:
            themes.append("direct_answer")
        if self.profile.agreeableness > 0.6:
            themes.append("supportive_language")
        if self.profile.openness > 0.7:
            themes.append("novel_perspective")
        
        return themes

    def _predict_engagement(self, message_analysis: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Predict engagement level with the message."""
        
        engagement = (
            self.profile.extraversion * 0.2 +
            self.profile.openness * 0.2 +
            message_analysis["urgency"] * 0.3 +
            0.3
        )
        
        return min(1.0, engagement)

    def _predict_defensiveness(self, message_analysis: Dict[str, Any]) -> float:
        """Predict probability of defensive response."""
        
        defensiveness = (
            self.profile.neuroticism * 0.3 +
            self.profile.dark_triad.get("narcissism", 0) * 0.3 +
            0.1
        )
        
        return min(1.0, defensiveness)

    def _score_influence_channel(self, 
                                channel: InfluenceChannel,
                                target_behavior: str,
                                constraints: Dict[str, Any]) -> float:
        """Score effectiveness of an influence channel."""
        
        scores = {
            InfluenceChannel.LOGICAL_ARGUMENT: (
                self.profile.openness * 0.3 + self.profile.conscientiousness * 0.3 + 0.2
            ),
            InfluenceChannel.EMOTIONAL_APPEAL: (
                self.profile.neuroticism * 0.2 + self.profile.agreeableness * 0.3 + 0.2
            ),
            InfluenceChannel.SOCIAL_PRESSURE: (
                (1 - self.profile.openness) * 0.3 + self.profile.agreeableness * 0.2 + 0.2
            ),
            InfluenceChannel.AUTHORITY: (
                self.profile.conscientiousness * 0.3 + (1 - self.profile.openness) * 0.2 + 0.2
            ),
            InfluenceChannel.RECIPROCITY: (
                self.profile.agreeableness * 0.4 + 0.3
            ),
            InfluenceChannel.SCARCITY: (
                self.profile.neuroticism * 0.3 + 0.25
            ),
            InfluenceChannel.NARRATIVE: (
                self.profile.openness * 0.3 + self.profile.extraversion * 0.2 + 0.2
            ),
            InfluenceChannel.INCENTIVE: (
                0.5  # Generally effective
            ),
        }
        
        return scores.get(channel, 0.3)

    def _identify_resistance(self, target_behavior: str) -> Dict[str, float]:
        """Identify factors that resist the target behavior."""
        
        resistance = {}
        
        # High conscientiousness resists impulsive changes
        if self.profile.conscientiousness > 0.7:
            resistance["change_resistance"] = self.profile.conscientiousness * 0.3
        
        # Low openness resists novel behaviors
        if self.profile.openness < 0.3:
            resistance["novelty_resistance"] = (1 - self.profile.openness) * 0.3
        
        # High neuroticism resists risk
        if self.profile.neuroticism > 0.6:
            resistance["risk_aversion"] = self.profile.neuroticism * 0.3
        
        return resistance

    def _generate_influence_sequence(self, 
                                    channel_scores: Dict[str, float],
                                    resistance: Dict[str, float]) -> List[Dict[str, Any]]:
        """Generate optimal sequence of influence actions."""
        
        # Sort channels by effectiveness
        sorted_channels = sorted(channel_scores.items(), key=lambda x: x[1], reverse=True)
        
        sequence = []
        for i, (channel, score) in enumerate(sorted_channels[:4]):
            sequence.append({
                "step": i + 1,
                "channel": channel,
                "effectiveness": score,
                "purpose": self._channel_purpose(channel, i),
            })
        
        return sequence

    def _channel_purpose(self, channel: str, step: int) -> str:
        """Describe purpose of each channel in the sequence."""
        purposes = {
            0: "establish_rapport",
            1: "build_motivation",
            2: "overcome_resistance",
            3: "reinforce_commitment",
        }
        return purposes.get(step, "support")

    def _recommend_timing(self) -> Dict[str, Any]:
        """Recommend optimal timing for influence."""
        
        return {
            "best_hours": self.footprint.active_hours[:3] if self.footprint.active_hours else [10, 14, 19],
            "avoid_high_stress_periods": True,
            "optimal_day_part": "morning" if self.profile.conscientiousness > 0.6 else "evening",
            "spacing": "allow 24-48 hours between influence attempts",
        }

    def _estimate_success(self, 
                         channel_scores: Dict[str, float],
                         resistance: Dict[str, float]) -> float:
        """Estimate overall success probability."""
        
        avg_channel_score = np.mean(list(channel_scores.values()))
        avg_resistance = np.mean(list(resistance.values())) if resistance else 0.0
        
        success = avg_channel_score * 0.6 - avg_resistance * 0.4 + 0.2
        return np.clip(success, 0.05, 0.95)

    def _flag_ethical_concerns(self, target_behavior: str) -> List[str]:
        """Flag potential ethical concerns with influence strategy."""
        
        concerns = [
            "Ensure informed consent in all interactions",
            "Influence should not exploit psychological vulnerabilities",
            "Target behavior should be in the subject's best interest",
            "Transparency about intentions is ethically preferred",
        ]
        
        return concerns

    def _recent_accuracy(self, window: int) -> float:
        """Get accuracy over recent predictions."""
        if len(self.accuracy_log) < window:
            recent = self.accuracy_log
        else:
            recent = self.accuracy_log[-window:]
        
        if not recent:
            return 0.0
        
        return sum(1 for _, correct in recent if correct) / len(recent)

    def _accuracy_by_category(self) -> Dict[str, float]:
        """Get accuracy broken down by prediction category."""
        # Simplified - would track category in real implementation
        return {"overall": self._recent_accuracy(50)}
