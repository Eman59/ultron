"""
Interaction Intelligence Engine — Learning From Every Conversation.

Every time a user interacts with Ultron — voice, text, or UI — this
engine captures what happened, how the user reacted, and uses that to
make the NEXT interaction better.

What it learns:
  - Response quality: Which responses get positive reactions?
  - Conversation flow: When does the user seem frustrated vs satisfied?
  - Voice preferences: Speed, tone, formality level the user prefers
  - UI engagement: Which visual elements hold attention?
  - Timing: How quickly should responses come?
  - Vocabulary: What level of technical language does the user prefer?
  - Context switching: How to handle topic changes gracefully
  - Error recovery: What works when something goes wrong?

Feedback signals (implicit + explicit):
  - EXPLICIT: User ratings, corrections, "that was wrong", "good"
  - IMPLICIT: Response time (fast followup = engaged), session length,
    repetition (user had to ask again = bad response), 
    interruptions (user cut off response = too verbose),
    silence (long pause after response = confused/dissatisfied)

The engine maintains a USER MODEL that evolves over time:
  - Communication style preference (formal/casual/technical)
  - Patience level (long explanations vs quick answers)
  - Expertise level (beginner/intermediate/expert)
  - Emotional state tracking
  - Context retention (how much does user remember between sessions?)
"""

import time
import json
import hashlib
import threading
import statistics
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from pathlib import Path


class InteractionType(Enum):
    """Types of user interactions."""
    TEXT_INPUT = "text_input"
    VOICE_INPUT = "voice_input"
    UI_CLICK = "ui_click"
    GESTURE = "gesture"
    EXPLICIT_FEEDBACK = "explicit_feedback"
    SILENCE = "silence"
    INTERRUPTION = "interruption"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


class ResponseQuality(Enum):
    """Quality rating of a response."""
    EXCELLENT = "excellent"     # User explicitly praised or continued smoothly
    GOOD = "good"              # Normal continuation, no issues
    NEUTRAL = "neutral"        # No signal either way
    POOR = "poor"              # User had to repeat or rephrase
    TERRIBLE = "terrible"      # User expressed frustration or corrected


class EmotionalState(Enum):
    """Detected emotional state of the user."""
    ENGAGED = "engaged"
    CURIOUS = "curious"
    SATISFIED = "satisfied"
    NEUTRAL = "neutral"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    IMPATIENT = "impatient"
    EXCITED = "excited"


class CommunicationStyle(Enum):
    """User's preferred communication style."""
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    BRIEF = "brief"
    DETAILED = "detailed"


@dataclass
class InteractionEvent:
    """A single interaction event."""
    id: str
    timestamp: float
    interaction_type: InteractionType
    
    # Content
    user_input: str = ""
    system_response: str = ""
    
    # Signals
    response_time_ms: float = 0.0       # How long user waited
    user_reaction_time_ms: float = 0.0  # How fast user responded after
    was_interrupted: bool = False        # User cut off the response
    was_repeated: bool = False           # User asked same thing again
    explicit_rating: Optional[float] = None  # -1 to 1 if user rated
    
    # Context
    session_id: str = ""
    turn_number: int = 0
    emotional_state: EmotionalState = EmotionalState.NEUTRAL
    
    # Derived quality
    quality: ResponseQuality = ResponseQuality.NEUTRAL
    quality_score: float = 0.5  # 0-1 computed quality


@dataclass
class UserModel:
    """
    Evolving model of a user's preferences and behavior.
    
    This is what Ultron "knows" about how to best serve this user.
    It evolves with every interaction.
    """
    user_id: str = "default"
    
    # Communication preferences (evolve over time)
    preferred_style: CommunicationStyle = CommunicationStyle.CASUAL
    preferred_verbosity: float = 0.5      # 0=ultra-brief, 1=very detailed
    preferred_technicality: float = 0.5   # 0=simple, 1=very technical
    preferred_speed: float = 0.5          # 0=slow/careful, 1=fast/direct
    preferred_formality: float = 0.3      # 0=very casual, 1=very formal
    
    # Voice preferences
    preferred_voice_speed: float = 1.0    # Speech rate multiplier
    preferred_voice_pitch: float = 0.5    # 0=low, 1=high
    preferred_voice_emotion: float = 0.5  # 0=flat, 1=very expressive
    
    # Behavioral patterns
    avg_session_length_minutes: float = 10.0
    avg_message_length: float = 50.0      # Characters
    patience_level: float = 0.5           # 0=very impatient, 1=very patient
    expertise_level: float = 0.5          # 0=beginner, 1=expert
    
    # Engagement patterns
    peak_engagement_hours: List[int] = field(default_factory=lambda: [9, 10, 14, 15, 21])
    common_topics: List[str] = field(default_factory=list)
    
    # Satisfaction tracking
    overall_satisfaction: float = 0.7
    satisfaction_trend: float = 0.0       # Positive = improving
    total_interactions: int = 0
    positive_interactions: int = 0
    negative_interactions: int = 0
    
    # Adaptation weights (how much to adjust each response)
    adaptation_confidence: float = 0.3    # 0=low confidence in model, 1=very confident
    
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "style": self.preferred_style.value,
            "verbosity": self.preferred_verbosity,
            "technicality": self.preferred_technicality,
            "speed": self.preferred_speed,
            "patience": self.patience_level,
            "expertise": self.expertise_level,
            "satisfaction": self.overall_satisfaction,
            "satisfaction_trend": self.satisfaction_trend,
            "total_interactions": self.total_interactions,
            "adaptation_confidence": self.adaptation_confidence,
        }


@dataclass
class ResponseGuidance:
    """
    Guidance generated for the next response based on learned preferences.
    
    This is what gets passed to the LLM/voice system to adapt output.
    """
    # Content guidance
    max_length_chars: int = 500
    technicality_level: float = 0.5
    formality_level: float = 0.3
    include_code_examples: bool = True
    include_explanations: bool = True
    
    # Voice guidance
    speech_rate: float = 1.0
    pitch_adjustment: float = 0.0
    emotion_level: float = 0.5
    pause_between_sentences_ms: int = 300
    
    # UI guidance
    animation_intensity: float = 0.7
    light_pulse_speed: float = 1.0
    color_warmth: float = 0.5
    
    # Meta
    confidence: float = 0.5
    adaptation_reason: str = ""

    def to_system_prompt_suffix(self) -> str:
        """Convert guidance to a system prompt modifier for the LLM."""
        parts = []
        
        if self.max_length_chars < 200:
            parts.append("Be extremely brief. Max 2-3 sentences.")
        elif self.max_length_chars < 400:
            parts.append("Keep responses concise and to the point.")
        elif self.max_length_chars > 800:
            parts.append("Provide detailed explanations with examples.")
        
        if self.technicality_level > 0.7:
            parts.append("Use technical language and assume expertise.")
        elif self.technicality_level < 0.3:
            parts.append("Use simple language and explain concepts.")
        
        if self.formality_level > 0.7:
            parts.append("Maintain a professional, formal tone.")
        elif self.formality_level < 0.3:
            parts.append("Be casual and conversational.")
        
        if not self.include_explanations:
            parts.append("Skip explanations, give direct answers only.")
        
        return " ".join(parts) if parts else ""


class InteractionLearner:
    """
    The engine that makes every interaction better than the last.
    
    Observes user behavior, builds a model of their preferences,
    and generates guidance for how Ultron should respond next time.
    """

    def __init__(self,
                 data_dir: str = None,
                 learning_rate: float = 0.05,
                 min_interactions_for_adaptation: int = 5,
                 feedback_window: int = 50):
        """
        Args:
            data_dir: Where to persist user models
            learning_rate: How fast preferences update (0-1)
            min_interactions_for_adaptation: Minimum before adapting
            feedback_window: How many recent interactions to consider
        """
        self.data_dir = Path(data_dir) if data_dir else Path("data/interaction")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.learning_rate = learning_rate
        self.min_interactions = min_interactions_for_adaptation
        self.feedback_window = feedback_window

        # User models
        self._user_models: Dict[str, UserModel] = {}
        
        # Interaction history (per user)
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Current session tracking
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Quality scoring model (weights learned over time)
        self._quality_weights = {
            "fast_followup": 0.3,        # Quick user response = good
            "no_repeat": 0.3,            # No repetition needed = good
            "no_interrupt": 0.2,          # Wasn't interrupted = good
            "session_continues": 0.2,     # User kept talking = good
        }
        
        # Global stats
        self._total_interactions = 0
        self._total_adaptations = 0
        self._avg_quality_score = 0.5
        self._quality_trend = deque(maxlen=200)
        
        # Load persisted user models
        self._load_models()

    # ═══════════════════════════════════════════════════════════════
    # EVENT RECORDING — Capture every interaction
    # ═══════════════════════════════════════════════════════════════

    def record_interaction(self,
                          user_input: str,
                          system_response: str,
                          response_time_ms: float = 0.0,
                          user_id: str = "default",
                          session_id: str = "",
                          interaction_type: InteractionType = InteractionType.TEXT_INPUT) -> InteractionEvent:
        """
        Record a user interaction for learning.
        
        Call this after every response is delivered.
        """
        event_id = hashlib.md5(f"{time.time_ns()}:{user_input[:20]}".encode()).hexdigest()[:12]
        
        # Get or create user model
        model = self._get_or_create_model(user_id)
        
        # Determine turn number
        session = self._active_sessions.get(session_id, {"turns": 0, "start": time.time()})
        session["turns"] += 1
        self._active_sessions[session_id] = session
        
        event = InteractionEvent(
            id=event_id,
            timestamp=time.time(),
            interaction_type=interaction_type,
            user_input=user_input,
            system_response=system_response,
            response_time_ms=response_time_ms,
            session_id=session_id,
            turn_number=session["turns"],
        )
        
        # Detect emotional state
        event.emotional_state = self._detect_emotion(user_input, model)
        
        # Score quality (based on previous interaction signals)
        event.quality_score = self._score_quality(event, user_id)
        event.quality = self._classify_quality(event.quality_score)
        
        # Record
        self._history[user_id].append(event)
        self._total_interactions += 1
        self._quality_trend.append(event.quality_score)
        
        # Update user model
        self._update_model(model, event)
        
        return event

    def record_feedback(self, user_id: str = "default", 
                       rating: float = 0.0, comment: str = ""):
        """Record explicit user feedback (-1 to 1)."""
        model = self._get_or_create_model(user_id)
        
        # Update satisfaction
        alpha = self.learning_rate * 2  # Explicit feedback weighs more
        model.overall_satisfaction = model.overall_satisfaction * (1 - alpha) + (rating + 1) / 2 * alpha
        
        if rating > 0:
            model.positive_interactions += 1
        elif rating < 0:
            model.negative_interactions += 1
        
        # If feedback mentions specific preferences, adjust
        comment_lower = comment.lower()
        if any(w in comment_lower for w in ["shorter", "brief", "concise", "too long"]):
            model.preferred_verbosity = max(0.1, model.preferred_verbosity - 0.1)
        elif any(w in comment_lower for w in ["more detail", "explain", "elaborate"]):
            model.preferred_verbosity = min(0.9, model.preferred_verbosity + 0.1)
        
        if any(w in comment_lower for w in ["simpler", "simple", "easy", "confused"]):
            model.preferred_technicality = max(0.1, model.preferred_technicality - 0.1)
        elif any(w in comment_lower for w in ["technical", "advanced", "deeper"]):
            model.preferred_technicality = min(0.9, model.preferred_technicality + 0.1)
        
        if any(w in comment_lower for w in ["slow", "fast", "quick"]):
            if "slow" in comment_lower:
                model.preferred_speed = max(0.1, model.preferred_speed - 0.1)
            else:
                model.preferred_speed = min(0.9, model.preferred_speed + 0.1)

    def record_interruption(self, user_id: str = "default"):
        """Record that the user interrupted (cut off) a response."""
        model = self._get_or_create_model(user_id)
        # Interruption means response was too long or irrelevant
        model.preferred_verbosity = max(0.1, model.preferred_verbosity - 0.05)
        model.patience_level = max(0.1, model.patience_level - 0.02)

    def record_repetition(self, user_id: str = "default"):
        """Record that the user had to repeat/rephrase their question."""
        model = self._get_or_create_model(user_id)
        # Repetition means we didn't understand or answer well
        model.overall_satisfaction -= 0.05

    # ═══════════════════════════════════════════════════════════════
    # GUIDANCE GENERATION — Tell the system how to respond
    # ═══════════════════════════════════════════════════════════════

    def get_response_guidance(self, user_id: str = "default",
                             context: Dict[str, Any] = None) -> ResponseGuidance:
        """
        Generate guidance for the next response based on learned preferences.
        
        This is called BEFORE generating a response to adapt it to the user.
        """
        model = self._get_or_create_model(user_id)
        context = context or {}
        
        # Only adapt if we have enough data
        if model.total_interactions < self.min_interactions:
            return ResponseGuidance(
                confidence=0.2,
                adaptation_reason="Insufficient interaction data — using defaults",
            )
        
        # Calculate response length based on verbosity preference
        if model.preferred_verbosity < 0.3:
            max_length = 200
        elif model.preferred_verbosity < 0.5:
            max_length = 400
        elif model.preferred_verbosity < 0.7:
            max_length = 700
        else:
            max_length = 1200
        
        # Adjust for patience (impatient users get shorter responses)
        if model.patience_level < 0.3:
            max_length = int(max_length * 0.6)
        
        # Determine if code examples should be included
        include_code = model.expertise_level > 0.4 and model.preferred_technicality > 0.4
        include_explanations = model.preferred_verbosity > 0.4
        
        # Voice parameters
        speech_rate = model.preferred_voice_speed
        if model.patience_level < 0.3:
            speech_rate = min(1.3, speech_rate * 1.1)  # Speak faster for impatient users
        
        # UI parameters
        animation_intensity = 0.5
        if model.overall_satisfaction > 0.7:
            animation_intensity = 0.8  # More expressive when user is happy
        elif model.overall_satisfaction < 0.4:
            animation_intensity = 0.3  # Calm down when frustrated
        
        guidance = ResponseGuidance(
            max_length_chars=max_length,
            technicality_level=model.preferred_technicality,
            formality_level=model.preferred_formality,
            include_code_examples=include_code,
            include_explanations=include_explanations,
            speech_rate=speech_rate,
            pitch_adjustment=model.preferred_voice_pitch - 0.5,
            emotion_level=model.preferred_voice_emotion,
            pause_between_sentences_ms=int(400 - model.preferred_speed * 200),
            animation_intensity=animation_intensity,
            light_pulse_speed=0.8 + model.preferred_speed * 0.4,
            color_warmth=0.5 + model.overall_satisfaction * 0.3,
            confidence=model.adaptation_confidence,
            adaptation_reason=f"Adapted for {model.preferred_style.value} style "
                            f"(satisfaction: {model.overall_satisfaction:.0%})",
        )
        
        self._total_adaptations += 1
        return guidance

    # ═══════════════════════════════════════════════════════════════
    # INTERNAL — Learning algorithms
    # ═══════════════════════════════════════════════════════════════

    def _detect_emotion(self, text: str, model: UserModel) -> EmotionalState:
        """Detect user's emotional state from text."""
        text_lower = text.lower()
        
        # Frustration indicators
        frustration_words = {"wrong", "broken", "stupid", "doesn't work", "again", "still", "ugh", "wtf"}
        if any(w in text_lower for w in frustration_words):
            return EmotionalState.FRUSTRATED
        
        # Confusion indicators
        confusion_words = {"what", "don't understand", "confused", "how", "why doesn't", "huh"}
        if any(w in text_lower for w in confusion_words) and "?" in text:
            return EmotionalState.CONFUSED
        
        # Impatience (very short messages, no punctuation)
        if len(text) < 20 and text.count('?') == 0 and text.count('.') == 0:
            return EmotionalState.IMPATIENT
        
        # Excitement
        if text.count('!') > 1 or any(w in text_lower for w in {"amazing", "awesome", "great", "love", "perfect"}):
            return EmotionalState.EXCITED
        
        # Engagement (longer, thoughtful messages)
        if len(text) > 100:
            return EmotionalState.ENGAGED
        
        # Curiosity (questions)
        if '?' in text:
            return EmotionalState.CURIOUS
        
        return EmotionalState.NEUTRAL

    def _score_quality(self, event: InteractionEvent, user_id: str) -> float:
        """Score the quality of the previous interaction based on signals."""
        score = 0.5  # Base neutral
        
        # Check previous interaction for follow-up signals
        history = self._history.get(user_id, deque())
        if len(history) < 2:
            return score
        
        prev = history[-2] if len(history) >= 2 else None
        if not prev:
            return score
        
        # Fast follow-up = user is engaged (good previous response)
        if event.user_reaction_time_ms > 0:
            if event.user_reaction_time_ms < 3000:  # < 3 seconds
                score += 0.15
            elif event.user_reaction_time_ms > 30000:  # > 30 seconds
                score -= 0.1
        
        # No repetition needed = good response
        if not event.was_repeated:
            score += 0.1
        else:
            score -= 0.2
        
        # Not interrupted = appropriate length
        if not event.was_interrupted:
            score += 0.1
        else:
            score -= 0.15
        
        # Explicit rating overrides
        if event.explicit_rating is not None:
            score = (event.explicit_rating + 1) / 2  # Map -1..1 to 0..1
        
        return max(0.0, min(1.0, score))

    def _classify_quality(self, score: float) -> ResponseQuality:
        """Classify a quality score into a category."""
        if score >= 0.8:
            return ResponseQuality.EXCELLENT
        elif score >= 0.6:
            return ResponseQuality.GOOD
        elif score >= 0.4:
            return ResponseQuality.NEUTRAL
        elif score >= 0.2:
            return ResponseQuality.POOR
        return ResponseQuality.TERRIBLE

    def _update_model(self, model: UserModel, event: InteractionEvent):
        """Update user model based on new interaction."""
        alpha = self.learning_rate
        model.total_interactions += 1
        model.last_updated = time.time()
        
        # Update satisfaction
        model.overall_satisfaction = (
            model.overall_satisfaction * (1 - alpha) + event.quality_score * alpha
        )
        
        if event.quality_score > 0.6:
            model.positive_interactions += 1
        elif event.quality_score < 0.4:
            model.negative_interactions += 1
        
        # Update satisfaction trend
        recent = list(self._quality_trend)[-20:]
        if len(recent) >= 10:
            first_half = statistics.mean(recent[:len(recent)//2])
            second_half = statistics.mean(recent[len(recent)//2:])
            model.satisfaction_trend = second_half - first_half
        
        # Learn verbosity preference from message length
        input_len = len(event.user_input)
        if input_len < 30:
            # Short inputs → user prefers brief responses
            model.preferred_verbosity = model.preferred_verbosity * (1 - alpha * 0.5) + 0.3 * alpha * 0.5
        elif input_len > 200:
            # Long inputs → user prefers detailed responses
            model.preferred_verbosity = model.preferred_verbosity * (1 - alpha * 0.5) + 0.7 * alpha * 0.5
        
        # Learn technicality from vocabulary
        technical_words = {"function", "class", "api", "algorithm", "deploy", "config", "runtime", "async"}
        words = set(event.user_input.lower().split())
        tech_ratio = len(words & technical_words) / max(1, len(words))
        if tech_ratio > 0.1:
            model.preferred_technicality = min(0.9, model.preferred_technicality + alpha * 0.3)
            model.expertise_level = min(0.9, model.expertise_level + alpha * 0.2)
        
        # Update patience from interruptions
        if event.was_interrupted:
            model.patience_level = max(0.1, model.patience_level - alpha)
        else:
            model.patience_level = min(0.9, model.patience_level + alpha * 0.1)
        
        # Increase adaptation confidence over time
        if model.total_interactions > self.min_interactions:
            model.adaptation_confidence = min(0.9, 
                model.total_interactions / (model.total_interactions + 50))
        
        # Update communication style
        if model.preferred_verbosity < 0.3 and model.preferred_speed > 0.7:
            model.preferred_style = CommunicationStyle.BRIEF
        elif model.preferred_technicality > 0.7:
            model.preferred_style = CommunicationStyle.TECHNICAL
        elif model.preferred_formality > 0.6:
            model.preferred_style = CommunicationStyle.FORMAL
        elif model.preferred_verbosity > 0.7:
            model.preferred_style = CommunicationStyle.DETAILED
        else:
            model.preferred_style = CommunicationStyle.CASUAL
        
        # Periodically save
        if model.total_interactions % 10 == 0:
            self._save_models()

    def _get_or_create_model(self, user_id: str) -> UserModel:
        """Get or create a user model."""
        if user_id not in self._user_models:
            self._user_models[user_id] = UserModel(user_id=user_id)
        return self._user_models[user_id]

    # ═══════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════

    def _save_models(self):
        """Save user models to disk."""
        for user_id, model in self._user_models.items():
            filepath = self.data_dir / f"user_{user_id}.json"
            try:
                with open(filepath, 'w') as f:
                    json.dump(model.to_dict(), f, indent=2)
            except IOError:
                pass

    def _load_models(self):
        """Load user models from disk."""
        if not self.data_dir.exists():
            return
        for filepath in self.data_dir.glob("user_*.json"):
            try:
                with open(filepath) as f:
                    data = json.load(f)
                user_id = data.get("user_id", filepath.stem.replace("user_", ""))
                model = UserModel(user_id=user_id)
                model.preferred_verbosity = data.get("verbosity", 0.5)
                model.preferred_technicality = data.get("technicality", 0.5)
                model.preferred_speed = data.get("speed", 0.5)
                model.patience_level = data.get("patience", 0.5)
                model.expertise_level = data.get("expertise", 0.5)
                model.overall_satisfaction = data.get("satisfaction", 0.7)
                model.total_interactions = data.get("total_interactions", 0)
                model.adaptation_confidence = data.get("adaptation_confidence", 0.3)
                try:
                    model.preferred_style = CommunicationStyle(data.get("style", "casual"))
                except ValueError:
                    pass
                self._user_models[user_id] = model
            except (IOError, json.JSONDecodeError):
                pass

    # ═══════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get interaction learner status."""
        quality_scores = list(self._quality_trend)
        
        return {
            "total_interactions": self._total_interactions,
            "total_adaptations": self._total_adaptations,
            "avg_quality": statistics.mean(quality_scores) if quality_scores else 0.5,
            "quality_trend": (
                statistics.mean(quality_scores[-20:]) - statistics.mean(quality_scores[:20])
                if len(quality_scores) >= 40 else 0.0
            ),
            "user_models": {
                uid: model.to_dict() for uid, model in self._user_models.items()
            },
            "active_sessions": len(self._active_sessions),
        }
