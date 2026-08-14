"""
Intuition Engine - Integrates biological signals into the decision process.

This is the bridge between the organoid's "gut feelings" and the
Core Agent's rational OODA loop. It provides a non-logical signal
that biases decisions in ways pure computation cannot replicate.

The Intuition Engine:
  - Does NOT override the rational decision system
  - Provides a weighted "nudge" that influences action selection
  - Is especially useful when rational analysis is inconclusive
  - Detects patterns humans would call "something feels wrong"
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time

from .organoid_interface import OrganoidInterface, OrganoidSignal


class IntuitionType(Enum):
    """Types of intuitive signals."""
    APPROACH = "approach"           # "This feels right, go for it"
    AVOID = "avoid"                 # "Something is wrong, back away"
    CURIOUS = "curious"             # "This is interesting, investigate"
    ALARM = "alarm"                 # "Danger! React now!"
    CALM = "calm"                   # "All is well, conserve energy"
    UNCERTAIN = "uncertain"         # "Can't read the situation"


@dataclass
class GutFeeling:
    """
    A processed intuition signal ready for the decision engine.
    
    This is what the Core Agent's autonomy loop receives from
    the biological layer — a pre-rational assessment.
    """
    feeling_id: str
    timestamp: float
    intuition_type: IntuitionType
    
    # Primary signal
    approach_avoid: float      # -1 (strong avoid) to 1 (strong approach)
    confidence: float          # 0-1, how strong the signal is
    urgency: float            # 0-1, how quickly to act on this
    
    # Contributing factors
    arousal_level: float      # 0-1, overall biological activation
    novelty_score: float      # 0-1, how novel the situation seems
    threat_signal: float      # 0-1, biological threat detection
    
    # Context
    context_hash: str = ""    # What context triggered this
    explanation: str = ""     # Best-guess interpretation
    
    # Integration parameters
    weight_in_decision: float = 0.15  # How much to influence the decision (0-1)
    override_rational: bool = False    # Only True in extreme danger


class IntuitionEngine:
    """
    Integrates biological intuition into Ultron's decision process.
    
    The engine maintains a running "intuitive state" that continuously
    processes organoid signals and provides real-time gut feelings
    to the autonomy loop.
    """

    def __init__(self, 
                 organoid: OrganoidInterface,
                 intuition_weight: float = 0.15,
                 alarm_threshold: float = 0.8):
        
        self.organoid = organoid
        self.base_weight = intuition_weight  # How much intuition influences decisions
        self.alarm_threshold = alarm_threshold
        
        # Current intuitive state (running average)
        self.current_state = {
            "approach_avoid": 0.0,
            "arousal": 0.3,
            "novelty": 0.0,
            "threat": 0.0,
        }
        
        # History of gut feelings
        self.feeling_history: List[GutFeeling] = []
        
        # Accuracy tracking (when we can verify intuition was right)
        self.predictions: List[Tuple[GutFeeling, Optional[bool]]] = []
        self.accuracy_score: float = 0.5  # Start neutral
        
        # Calibration
        self.sensitivity: float = 1.0  # Adjusted based on accuracy
        self.false_alarm_rate: float = 0.0

    def get_intuition(self, context: np.ndarray) -> GutFeeling:
        """
        Get the current gut feeling given a context vector.
        
        This is called by the Core Agent during the ORIENT phase
        of the OODA loop to get a biological read on the situation.
        
        Args:
            context: State vector from the autonomy loop (drives, world state)
            
        Returns:
            GutFeeling object to integrate into decision-making
        """
        # Get raw biological signal
        bio_signal = self.organoid.get_intuition_signal(context)
        
        if not bio_signal.get("available", False):
            return self._neutral_feeling()
        
        # Update running state with exponential smoothing
        alpha = 0.3  # Smoothing factor
        self.current_state["approach_avoid"] = (
            (1 - alpha) * self.current_state["approach_avoid"] +
            alpha * bio_signal.get("approach_tendency", 0.0)
        )
        self.current_state["arousal"] = (
            (1 - alpha) * self.current_state["arousal"] +
            alpha * bio_signal.get("arousal", 0.3)
        )
        self.current_state["novelty"] = (
            (1 - alpha) * self.current_state["novelty"] +
            alpha * bio_signal.get("novelty_detection", 0.0)
        )
        
        # Threat detection: high arousal + avoid tendency
        threat = max(0.0, 
            self.current_state["arousal"] * (1 - (self.current_state["approach_avoid"] + 1) / 2)
        )
        self.current_state["threat"] = (
            (1 - alpha) * self.current_state["threat"] +
            alpha * threat
        )
        
        # Classify the intuition
        intuition_type = self._classify_feeling()
        
        # Determine urgency
        urgency = self._calculate_urgency()
        
        # Calculate decision weight (higher when rational analysis is weak)
        weight = self._calculate_weight(context)
        
        # Create gut feeling
        feeling = GutFeeling(
            feeling_id=f"gut_{int(time.time()*1000)}",
            timestamp=time.time(),
            intuition_type=intuition_type,
            approach_avoid=self.current_state["approach_avoid"] * self.sensitivity,
            confidence=bio_signal.get("confidence", 0.5),
            urgency=urgency,
            arousal_level=self.current_state["arousal"],
            novelty_score=self.current_state["novelty"],
            threat_signal=self.current_state["threat"],
            context_hash=str(hash(context.tobytes()))[:8],
            explanation=self._generate_explanation(intuition_type),
            weight_in_decision=weight,
            override_rational=(intuition_type == IntuitionType.ALARM and urgency > 0.9),
        )
        
        # Record
        self.feeling_history.append(feeling)
        if len(self.feeling_history) > 10000:
            self.feeling_history = self.feeling_history[-5000:]
        
        return feeling

    def record_outcome(self, feeling_id: str, was_correct: bool):
        """
        Record whether an intuition was correct (for calibration).
        
        Over time, this adjusts the sensitivity and weight of
        biological signals based on their track record.
        """
        # Update accuracy
        self.accuracy_score = self.accuracy_score * 0.95 + (1.0 if was_correct else 0.0) * 0.05
        
        # Adjust sensitivity based on accuracy
        if self.accuracy_score > 0.6:
            self.sensitivity = min(2.0, self.sensitivity * 1.01)
        elif self.accuracy_score < 0.4:
            self.sensitivity = max(0.5, self.sensitivity * 0.99)

    def get_intuition_stats(self) -> Dict[str, Any]:
        """Get statistics about intuition performance."""
        
        if not self.feeling_history:
            return {"active": False}
        
        recent = self.feeling_history[-100:]
        
        type_distribution = {}
        for f in recent:
            t = f.intuition_type.value
            type_distribution[t] = type_distribution.get(t, 0) + 1
        
        return {
            "active": self.organoid.connected,
            "accuracy_score": self.accuracy_score,
            "sensitivity": self.sensitivity,
            "current_state": self.current_state,
            "base_weight": self.base_weight,
            "total_feelings": len(self.feeling_history),
            "type_distribution": type_distribution,
            "avg_confidence": np.mean([f.confidence for f in recent]),
            "avg_urgency": np.mean([f.urgency for f in recent]),
            "alarm_count": sum(1 for f in recent if f.intuition_type == IntuitionType.ALARM),
        }

    # ─────────────────────── Private Methods ───────────────────────

    def _classify_feeling(self) -> IntuitionType:
        """Classify the current state into an intuition type."""
        
        aa = self.current_state["approach_avoid"]
        arousal = self.current_state["arousal"]
        threat = self.current_state["threat"]
        novelty = self.current_state["novelty"]
        
        # Alarm: high threat + high arousal
        if threat > self.alarm_threshold and arousal > 0.7:
            return IntuitionType.ALARM
        
        # Avoid: negative approach + moderate arousal
        if aa < -0.3 and arousal > 0.3:
            return IntuitionType.AVOID
        
        # Curious: high novelty + positive approach
        if novelty > 0.5 and aa > 0.0:
            return IntuitionType.CURIOUS
        
        # Approach: positive approach + confidence
        if aa > 0.3:
            return IntuitionType.APPROACH
        
        # Calm: low arousal, neutral approach
        if arousal < 0.3 and abs(aa) < 0.2:
            return IntuitionType.CALM
        
        return IntuitionType.UNCERTAIN

    def _calculate_urgency(self) -> float:
        """Calculate how urgently the intuition should be acted upon."""
        
        threat = self.current_state["threat"]
        arousal = self.current_state["arousal"]
        novelty = self.current_state["novelty"]
        
        # Threats are urgent
        urgency = threat * 0.5
        
        # High arousal adds urgency
        urgency += arousal * 0.3
        
        # Novelty adds mild urgency (should investigate)
        urgency += novelty * 0.2
        
        return min(1.0, urgency)

    def _calculate_weight(self, context: np.ndarray) -> float:
        """
        Calculate how much weight this intuition should have in the decision.
        
        Intuition is weighted MORE when:
        - Rational analysis is inconclusive (context values near 0)
        - Historical accuracy is high
        - The signal is strong and confident
        """
        # Context ambiguity: lower values = more ambiguous = more weight on intuition
        context_clarity = np.mean(np.abs(context)) if len(context) > 0 else 0.5
        ambiguity_boost = max(0, 0.5 - context_clarity) * 0.3
        
        # Accuracy boost
        accuracy_boost = (self.accuracy_score - 0.5) * 0.2
        
        # Signal strength
        strength = abs(self.current_state["approach_avoid"]) * 0.1
        
        weight = self.base_weight + ambiguity_boost + accuracy_boost + strength
        
        return max(0.05, min(0.4, weight))  # Clamp between 5% and 40%

    def _generate_explanation(self, intuition_type: IntuitionType) -> str:
        """Generate a human-readable explanation of the intuition."""
        
        explanations = {
            IntuitionType.APPROACH: "Biological substrate shows positive activation pattern. Proceed.",
            IntuitionType.AVOID: "Inhibitory response detected. The organoid senses something wrong.",
            IntuitionType.CURIOUS: "Novel pattern detected in biological response. Worth investigating.",
            IntuitionType.ALARM: "STRONG biological alarm response. Immediate attention required.",
            IntuitionType.CALM: "Biological substrate at rest. No significant signals.",
            IntuitionType.UNCERTAIN: "Mixed signals from biological substrate. Low confidence.",
        }
        
        return explanations.get(intuition_type, "Unknown biological signal.")

    def _neutral_feeling(self) -> GutFeeling:
        """Return a neutral feeling when organoid is unavailable."""
        return GutFeeling(
            feeling_id=f"neutral_{int(time.time()*1000)}",
            timestamp=time.time(),
            intuition_type=IntuitionType.UNCERTAIN,
            approach_avoid=0.0,
            confidence=0.0,
            urgency=0.0,
            arousal_level=0.0,
            novelty_score=0.0,
            threat_signal=0.0,
            explanation="Biological substrate not connected.",
            weight_in_decision=0.0,
        )
