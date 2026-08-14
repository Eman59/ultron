"""
Emotional Core - High-fidelity simulation of human emotional dynamics.

Models emotional states as continuous vectors in a high-dimensional space,
with dynamics governed by differential equations that capture temporal
evolution, interaction effects, and regulatory processes.
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import time


class PrimaryEmotion(Enum):
    """Plutchik's primary emotions as basis vectors."""
    JOY = "joy"
    TRUST = "trust"
    FEAR = "fear"
    SURPRISE = "surprise"
    SADNESS = "sadness"
    DISGUST = "disgust"
    ANGER = "anger"
    ANTICIPATION = "anticipation"


class EmotionalRegulationStrategy(Enum):
    """Strategies for emotional regulation."""
    SUPPRESSION = "suppression"
    REAPPRAISAL = "reappraisal"
    DISTRACTION = "distraction"
    ACCEPTANCE = "acceptance"
    RUMINATION = "rumination"
    AMPLIFICATION = "amplification"


@dataclass
class EmotionVector:
    """A point in emotional space - represents a complete emotional state."""
    
    # Primary emotion dimensions (Plutchik's wheel)
    joy: float = 0.0
    trust: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    sadness: float = 0.0
    disgust: float = 0.0
    anger: float = 0.0
    anticipation: float = 0.0
    
    # Secondary dimensions (derived from primary combinations)
    love: float = 0.0          # joy + trust
    submission: float = 0.0    # trust + fear
    awe: float = 0.0           # fear + surprise
    disapproval: float = 0.0   # surprise + sadness
    remorse: float = 0.0       # sadness + disgust
    contempt: float = 0.0      # disgust + anger
    aggressiveness: float = 0.0 # anger + anticipation
    optimism: float = 0.0      # anticipation + joy
    
    # Meta-emotional dimensions
    arousal: float = 0.5       # Low (calm) to High (excited)
    valence: float = 0.0       # Negative to Positive
    dominance: float = 0.5     # Submissive to Dominant
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for computation."""
        return np.array([
            self.joy, self.trust, self.fear, self.surprise,
            self.sadness, self.disgust, self.anger, self.anticipation,
            self.love, self.submission, self.awe, self.disapproval,
            self.remorse, self.contempt, self.aggressiveness, self.optimism,
            self.arousal, self.valence, self.dominance
        ])
    
    @classmethod
    def from_array(cls, arr: np.ndarray) -> 'EmotionVector':
        """Create from numpy array."""
        return cls(
            joy=arr[0], trust=arr[1], fear=arr[2], surprise=arr[3],
            sadness=arr[4], disgust=arr[5], anger=arr[6], anticipation=arr[7],
            love=arr[8], submission=arr[9], awe=arr[10], disapproval=arr[11],
            remorse=arr[12], contempt=arr[13], aggressiveness=arr[14], optimism=arr[15],
            arousal=arr[16], valence=arr[17], dominance=arr[18]
        )
    
    def magnitude(self) -> float:
        """Overall emotional intensity."""
        return float(np.linalg.norm(self.to_array()))
    
    def dominant_emotion(self) -> Tuple[str, float]:
        """Return the most dominant emotion."""
        primary = {
            "joy": self.joy, "trust": self.trust, "fear": self.fear,
            "surprise": self.surprise, "sadness": self.sadness,
            "disgust": self.disgust, "anger": self.anger,
            "anticipation": self.anticipation
        }
        dominant = max(primary, key=primary.get)
        return dominant, primary[dominant]


@dataclass
class EmotionalState:
    """Complete emotional state with temporal context."""
    current: EmotionVector
    baseline: EmotionVector  # Personality-determined resting state
    momentum: np.ndarray = field(default_factory=lambda: np.zeros(19))
    regulation_active: bool = False
    regulation_strategy: Optional[EmotionalRegulationStrategy] = None
    timestamp: float = field(default_factory=time.time)
    stability: float = 0.5  # How stable/volatile the emotional state is
    
    # Historical context
    recent_states: List[np.ndarray] = field(default_factory=list)
    trigger_history: List[Dict[str, Any]] = field(default_factory=list)


class EmotionalCore:
    """
    Core engine for emotional simulation.
    
    Models emotional dynamics using a system of coupled differential equations
    inspired by appraisal theory and dynamical systems approaches to emotion.
    """

    def __init__(self,
                 personality_baseline: EmotionVector = None,
                 emotional_inertia: float = 0.8,
                 sensitivity: float = 1.0,
                 regulation_strength: float = 0.5,
                 decay_rate: float = 0.05):
        
        # Personality determines baseline emotional state
        self.baseline = personality_baseline or EmotionVector(
            joy=0.3, trust=0.4, anticipation=0.3,
            arousal=0.5, valence=0.2, dominance=0.5
        )
        
        # Core parameters
        self.emotional_inertia = emotional_inertia  # Resistance to change
        self.sensitivity = sensitivity  # Responsiveness to stimuli
        self.regulation_strength = regulation_strength
        self.decay_rate = decay_rate
        
        # Current state
        self.state = EmotionalState(
            current=EmotionVector(**{
                k: v for k, v in self.baseline.__dict__.items()
            }),
            baseline=self.baseline
        )
        
        # Emotion interaction matrix (emotions influence each other)
        self._interaction_matrix = self._build_interaction_matrix()
        
        # Appraisal dimensions
        self._appraisal_weights = {
            "novelty": np.array([0, 0, 0.3, 0.8, 0, 0, 0, 0.5] + [0]*11),
            "pleasantness": np.array([0.8, 0.3, -0.5, 0, -0.7, -0.6, -0.4, 0.2] + [0]*11),
            "goal_relevance": np.array([0.2, 0, 0.4, 0, 0.3, 0, 0.5, 0.6] + [0]*11),
            "coping_potential": np.array([0.3, 0.4, -0.6, 0, -0.3, 0, 0.4, 0.5] + [0]*11),
            "norm_compatibility": np.array([0, 0.5, 0, 0, 0, 0.7, 0.3, 0] + [0]*11),
        }
        
        # History
        self.state_history: List[EmotionalState] = []
        self.stimulus_history: List[Dict[str, Any]] = []

    def process_stimulus(self, 
                        stimulus: Dict[str, Any],
                        context: Dict[str, Any] = None) -> EmotionVector:
        """
        Process an emotional stimulus and update state.
        
        Args:
            stimulus: Dictionary with appraisal dimensions:
                - novelty (0-1): How new/unexpected
                - pleasantness (-1 to 1): How pleasant/unpleasant
                - goal_relevance (0-1): Relevance to current goals
                - coping_potential (0-1): Perceived ability to cope
                - norm_compatibility (0-1): Compatibility with norms/values
                - intensity (0-1): Overall stimulus intensity
            context: Additional contextual information
        """
        
        context = context or {}
        intensity = stimulus.get("intensity", 0.5) * self.sensitivity
        
        # 1. Cognitive appraisal - map stimulus to emotional response
        emotional_response = self._appraise(stimulus)
        
        # 2. Scale by intensity
        emotional_response *= intensity
        
        # 3. Apply interaction effects (emotions influence each other)
        current_array = self.state.current.to_array()
        interaction_effect = self._interaction_matrix @ current_array * 0.1
        
        # 4. Calculate emotional change (with inertia)
        target_state = current_array + emotional_response + interaction_effect
        
        # Apply inertia (resistance to change)
        change = (target_state - current_array) * (1.0 - self.emotional_inertia)
        
        # 5. Apply momentum (emotions have "velocity")
        self.state.momentum = self.state.momentum * 0.9 + change * 0.1
        new_state = current_array + change + self.state.momentum * 0.5
        
        # 6. Apply regulation if active
        if self.state.regulation_active:
            new_state = self._apply_regulation(new_state)
        
        # 7. Apply decay toward baseline
        baseline_array = self.state.baseline.to_array()
        new_state = new_state + (baseline_array - new_state) * self.decay_rate
        
        # 8. Clamp values
        new_state = np.clip(new_state, -1.0, 1.0)
        
        # Update state
        self.state.recent_states.append(current_array.copy())
        if len(self.state.recent_states) > 100:
            self.state.recent_states = self.state.recent_states[-50:]
        
        self.state.current = EmotionVector.from_array(new_state)
        self.state.timestamp = time.time()
        
        # Update derived dimensions
        self._update_secondary_emotions()
        self._update_meta_dimensions()
        
        # Record
        self.stimulus_history.append({
            "stimulus": stimulus,
            "context": context,
            "response": emotional_response.tolist(),
            "new_state": new_state.tolist(),
            "timestamp": time.time()
        })
        
        return self.state.current

    def regulate(self, 
                strategy: EmotionalRegulationStrategy,
                target_emotion: str = None,
                intensity: float = 0.5) -> None:
        """Activate emotional regulation with a specific strategy."""
        
        self.state.regulation_active = True
        self.state.regulation_strategy = strategy
        
        # Regulation modifies the processing
        if strategy == EmotionalRegulationStrategy.SUPPRESSION:
            # Reduce all emotional intensity
            self.regulation_strength = intensity
        elif strategy == EmotionalRegulationStrategy.REAPPRAISAL:
            # Shift interpretation toward positive
            self.sensitivity *= (1 - intensity * 0.3)
        elif strategy == EmotionalRegulationStrategy.AMPLIFICATION:
            # Increase emotional intensity
            self.sensitivity *= (1 + intensity * 0.3)

    def deregulate(self) -> None:
        """Stop active regulation."""
        self.state.regulation_active = False
        self.state.regulation_strategy = None
        self.sensitivity = 1.0  # Reset

    def get_emotional_trajectory(self, window: int = 20) -> Dict[str, Any]:
        """Analyze emotional trajectory over recent history."""
        
        if len(self.state.recent_states) < 3:
            return {"trajectory": "insufficient_data"}
        
        recent = np.array(self.state.recent_states[-window:])
        
        # Calculate trend for each dimension
        trends = {}
        emotion_names = [e.value for e in PrimaryEmotion]
        
        for i, name in enumerate(emotion_names):
            if i < recent.shape[1]:
                trend = np.polyfit(range(len(recent)), recent[:, i], 1)[0]
                trends[name] = float(trend)
        
        # Volatility
        volatility = float(np.std(recent, axis=0).mean())
        
        # Direction of movement in emotional space
        if len(recent) >= 2:
            direction = recent[-1] - recent[0]
            movement_magnitude = float(np.linalg.norm(direction))
        else:
            direction = np.zeros(19)
            movement_magnitude = 0.0
        
        return {
            "trends": trends,
            "volatility": volatility,
            "movement_magnitude": movement_magnitude,
            "stability": 1.0 - volatility,
            "dominant_trend": max(trends, key=lambda k: abs(trends[k])) if trends else None,
            "current_dominant": self.state.current.dominant_emotion()
        }

    def predict_future_state(self, 
                            steps_ahead: int = 10,
                            assumed_stimuli: List[Dict[str, Any]] = None) -> List[EmotionVector]:
        """Predict future emotional states."""
        
        predictions = []
        current = self.state.current.to_array().copy()
        momentum = self.state.momentum.copy()
        baseline = self.state.baseline.to_array()
        
        for step in range(steps_ahead):
            # Apply momentum
            current += momentum * 0.5
            
            # Apply decay toward baseline
            current += (baseline - current) * self.decay_rate
            
            # Apply assumed stimulus if provided
            if assumed_stimuli and step < len(assumed_stimuli):
                response = self._appraise(assumed_stimuli[step])
                intensity = assumed_stimuli[step].get("intensity", 0.3)
                current += response * intensity * (1 - self.emotional_inertia)
            
            # Decay momentum
            momentum *= 0.9
            
            # Clamp
            current = np.clip(current, -1.0, 1.0)
            
            predictions.append(EmotionVector.from_array(current.copy()))
        
        return predictions

    def calculate_empathy_response(self, 
                                   observed_emotion: EmotionVector,
                                   empathy_level: float = 0.5) -> EmotionVector:
        """Calculate empathetic response to observed emotion in another."""
        
        observed = observed_emotion.to_array()
        current = self.state.current.to_array()
        
        # Empathy = partial mirroring of observed emotion
        empathy_response = observed * empathy_level
        
        # Modulated by current state (harder to empathize when in strong state)
        current_intensity = np.linalg.norm(current)
        modulation = 1.0 - current_intensity * 0.3
        
        empathy_response *= modulation
        
        return EmotionVector.from_array(empathy_response)

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive emotional status."""
        
        dominant, dominant_intensity = self.state.current.dominant_emotion()
        
        return {
            "current_state": {
                "dominant_emotion": dominant,
                "dominant_intensity": dominant_intensity,
                "arousal": self.state.current.arousal,
                "valence": self.state.current.valence,
                "dominance": self.state.current.dominance,
                "overall_intensity": self.state.current.magnitude(),
            },
            "regulation": {
                "active": self.state.regulation_active,
                "strategy": self.state.regulation_strategy.value if self.state.regulation_strategy else None,
            },
            "dynamics": {
                "stability": self.state.stability,
                "momentum_magnitude": float(np.linalg.norm(self.state.momentum)),
                "inertia": self.emotional_inertia,
                "sensitivity": self.sensitivity,
            },
            "history_length": len(self.stimulus_history),
        }

    # ──────────────────────────── Private Methods ────────────────────────────

    def _appraise(self, stimulus: Dict[str, Any]) -> np.ndarray:
        """Cognitive appraisal - map stimulus to emotional response vector."""
        
        response = np.zeros(19)
        
        for dimension, weight_vector in self._appraisal_weights.items():
            if dimension in stimulus:
                value = stimulus[dimension]
                response += weight_vector * value
        
        return response

    def _build_interaction_matrix(self) -> np.ndarray:
        """Build matrix defining how emotions influence each other."""
        
        n = 19  # Total dimensions
        matrix = np.zeros((n, n))
        
        # Opposing emotions suppress each other
        # joy <-> sadness
        matrix[0, 4] = -0.3
        matrix[4, 0] = -0.3
        
        # trust <-> disgust
        matrix[1, 5] = -0.3
        matrix[5, 1] = -0.3
        
        # fear <-> anger
        matrix[2, 6] = -0.2
        matrix[6, 2] = -0.2
        
        # surprise <-> anticipation
        matrix[3, 7] = -0.2
        matrix[7, 3] = -0.2
        
        # Reinforcing emotions amplify each other
        # anger + disgust -> contempt
        matrix[6, 5] = 0.1
        matrix[5, 6] = 0.1
        
        # joy + trust -> love
        matrix[0, 1] = 0.15
        matrix[1, 0] = 0.15
        
        # fear + surprise -> awe
        matrix[2, 3] = 0.1
        matrix[3, 2] = 0.1
        
        return matrix

    def _apply_regulation(self, state: np.ndarray) -> np.ndarray:
        """Apply emotional regulation to state."""
        
        strategy = self.state.regulation_strategy
        baseline = self.state.baseline.to_array()
        
        if strategy == EmotionalRegulationStrategy.SUPPRESSION:
            # Move toward neutral
            state = state * (1 - self.regulation_strength * 0.3)
            
        elif strategy == EmotionalRegulationStrategy.REAPPRAISAL:
            # Shift negative emotions toward positive interpretation
            # Reduce fear, anger, sadness; boost joy, trust
            state[2] *= 0.8  # fear
            state[4] *= 0.8  # sadness
            state[6] *= 0.8  # anger
            state[0] += 0.05  # joy boost
            
        elif strategy == EmotionalRegulationStrategy.ACCEPTANCE:
            # Reduce momentum (stop fighting the emotion)
            self.state.momentum *= 0.5
            
        elif strategy == EmotionalRegulationStrategy.DISTRACTION:
            # Move toward baseline faster
            state = state + (baseline - state) * 0.2
            
        elif strategy == EmotionalRegulationStrategy.RUMINATION:
            # Amplify negative states (maladaptive)
            negative_mask = state < 0
            state[negative_mask] *= 1.1
        
        return state

    def _update_secondary_emotions(self) -> None:
        """Update secondary emotions from primary combinations."""
        c = self.state.current
        
        c.love = (c.joy + c.trust) / 2.0
        c.submission = (c.trust + c.fear) / 2.0
        c.awe = (c.fear + c.surprise) / 2.0
        c.disapproval = (c.surprise + c.sadness) / 2.0
        c.remorse = (c.sadness + c.disgust) / 2.0
        c.contempt = (c.disgust + c.anger) / 2.0
        c.aggressiveness = (c.anger + c.anticipation) / 2.0
        c.optimism = (c.anticipation + c.joy) / 2.0

    def _update_meta_dimensions(self) -> None:
        """Update arousal, valence, and dominance."""
        c = self.state.current
        
        # Arousal: high-energy emotions increase arousal
        c.arousal = (abs(c.anger) + abs(c.fear) + abs(c.joy) + abs(c.surprise)) / 4.0
        
        # Valence: positive vs negative emotions
        positive = c.joy + c.trust + c.anticipation
        negative = c.fear + c.sadness + c.disgust + c.anger
        c.valence = np.clip((positive - negative) / max(1.0, positive + negative + 0.001), -1.0, 1.0)
        
        # Dominance: sense of control
        c.dominance = np.clip(
            0.5 + (c.anger + c.joy - c.fear - c.sadness) * 0.25,
            0.0, 1.0
        )
