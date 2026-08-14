"""
Adaptive UI Controller — Living Visual Intelligence.

The UI isn't static. It EVOLVES. Every animation, every light pulse,
every color choice is tracked for how users respond. What captures
attention gets amplified. What gets ignored fades away.

What adapts:
  - LIGHT PATTERNS: Breathing, pulsing, arc reactor glow intensity
  - ANIMATIONS: Speed, smoothness, particle density, transitions
  - COLORS: Hue, warmth, contrast, saturation shift with mood/state
  - LAYOUT: Element sizing, spacing, information density
  - FEEDBACK: How the UI reacts to user actions (haptic, visual, audio)
  - PRESENCE: How "alive" Ultron feels (idle animations, ambient motion)

How it learns:
  - Eye tracking proxy (mouse hover time, scroll patterns)
  - Engagement time per UI state
  - Click-through rates on suggestions
  - Session length correlation with UI settings
  - A/B testing of visual variants
  - Explicit preferences ("too bright", "too fast")

The UI has PERSONALITY STATES that affect all visuals:
  - THINKING: Concentrated glow, slow deep pulse
  - ACTIVE: Fast particles, bright core, responsive animations
  - CALM: Gentle breathing, soft colors, minimal motion
  - ALERT: Sharp flashes, red accents, attention-grabbing patterns
  - LEARNING: Spiral patterns, growing complexity, neural network viz
  - EVOLVING: Transformation animations, morphing shapes, rebirth
"""

import time
import json
import math
import hashlib
import threading
import statistics
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from pathlib import Path


class UIPersonality(Enum):
    """Visual personality states — how Ultron appears."""
    IDLE = "idle"
    THINKING = "thinking"
    ACTIVE = "active"
    CALM = "calm"
    ALERT = "alert"
    LEARNING = "learning"
    EVOLVING = "evolving"
    LISTENING = "listening"
    CELEBRATING = "celebrating"
    ERROR = "error"


class LightPattern(Enum):
    """Core light animation patterns."""
    BREATHE = "breathe"              # Slow sine wave pulse
    HEARTBEAT = "heartbeat"          # Double-pulse like a heart
    RIPPLE = "ripple"                # Outward expanding rings
    SPIRAL = "spiral"                # Rotating spiral pattern
    PARTICLE_FLOW = "particle_flow"  # Streaming particles
    NEURAL_FIRE = "neural_fire"      # Random neuron-like flashes
    WAVE = "wave"                    # Flowing wave motion
    SHATTER = "shatter"             # Break apart and reform
    MORPH = "morph"                  # Smooth shape transitions
    ORBIT = "orbit"                  # Orbiting elements
    PLASMA = "plasma"                # Organic plasma movement
    CRYSTALLIZE = "crystallize"      # Forming geometric patterns


class ColorScheme(Enum):
    """Color palettes for different states."""
    ULTRON_RED = "ultron_red"        # Classic arc reactor red
    COOL_BLUE = "cool_blue"          # Calm, analytical
    WARM_GOLD = "warm_gold"          # Friendly, approachable
    ELECTRIC_CYAN = "electric_cyan"  # High energy
    DEEP_PURPLE = "deep_purple"      # Deep thinking
    EMERALD = "emerald"              # Growth, learning
    CRIMSON_ALERT = "crimson_alert"  # Danger, attention
    AURORA = "aurora"                # Multi-color flow
    MONOCHROME = "monochrome"        # Minimal, focused


@dataclass
class UIState:
    """Current visual state of the UI."""
    personality: UIPersonality = UIPersonality.IDLE
    
    # Light system
    primary_pattern: LightPattern = LightPattern.BREATHE
    secondary_pattern: Optional[LightPattern] = None
    pattern_speed: float = 1.0         # Multiplier (0.1-3.0)
    pattern_intensity: float = 0.7     # 0-1
    pattern_complexity: float = 0.5    # 0=simple, 1=complex (particle count, etc)
    
    # Colors
    color_scheme: ColorScheme = ColorScheme.ULTRON_RED
    color_primary: Tuple[int, int, int] = (220, 50, 50)    # RGB
    color_secondary: Tuple[int, int, int] = (255, 150, 50)  # RGB
    color_accent: Tuple[int, int, int] = (255, 255, 255)    # RGB
    color_warmth: float = 0.5          # 0=cool, 1=warm
    color_saturation: float = 0.8      # 0-1
    brightness: float = 0.7            # 0-1
    
    # Animation
    transition_duration_ms: int = 300   # How long state transitions take
    smoothness: float = 0.8            # Easing curve (0=linear, 1=very smooth)
    particle_count: int = 50           # Active particles
    motion_blur: float = 0.3           # 0-1
    
    # Presence (how "alive" it feels)
    idle_motion: float = 0.5           # How much it moves when idle
    responsiveness: float = 0.8        # How fast it reacts to events
    ambient_sound: float = 0.0         # Background hum level
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "personality": self.personality.value,
            "pattern": self.primary_pattern.value,
            "secondary_pattern": self.secondary_pattern.value if self.secondary_pattern else None,
            "speed": self.pattern_speed,
            "intensity": self.pattern_intensity,
            "complexity": self.pattern_complexity,
            "color_scheme": self.color_scheme.value,
            "color_primary": list(self.color_primary),
            "color_secondary": list(self.color_secondary),
            "color_accent": list(self.color_accent),
            "warmth": self.color_warmth,
            "saturation": self.color_saturation,
            "brightness": self.brightness,
            "transition_ms": self.transition_duration_ms,
            "smoothness": self.smoothness,
            "particles": self.particle_count,
            "idle_motion": self.idle_motion,
            "responsiveness": self.responsiveness,
        }

    def to_css_variables(self) -> Dict[str, str]:
        """Convert to CSS custom properties for web UI."""
        r, g, b = self.color_primary
        r2, g2, b2 = self.color_secondary
        return {
            "--ultron-primary": f"rgb({r},{g},{b})",
            "--ultron-secondary": f"rgb({r2},{g2},{b2})",
            "--ultron-brightness": f"{self.brightness}",
            "--ultron-speed": f"{self.pattern_speed}s",
            "--ultron-intensity": f"{self.pattern_intensity}",
            "--ultron-transition": f"{self.transition_duration_ms}ms",
            "--ultron-particles": f"{self.particle_count}",
            "--ultron-smoothness": f"{self.smoothness}",
            "--ultron-glow-size": f"{int(self.pattern_intensity * 30)}px",
        }


@dataclass
class UIEngagementSignal:
    """A signal about how the user is engaging with the UI."""
    timestamp: float
    signal_type: str      # "hover", "click", "scroll", "focus", "gaze_proxy"
    element: str          # What UI element
    duration_ms: float    # How long
    ui_state: str         # What personality was active
    pattern_active: str   # What pattern was showing
    
    # Derived
    was_engaging: bool = False  # Did user seem engaged?


@dataclass
class UIExperiment:
    """An A/B test of UI variants."""
    id: str
    variant_a: Dict[str, Any]   # Control (current)
    variant_b: Dict[str, Any]   # Test (alternative)
    metric: str                  # What to measure
    
    # Results
    a_engagement: List[float] = field(default_factory=list)
    b_engagement: List[float] = field(default_factory=list)
    winner: Optional[str] = None
    started_at: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════
# PERSONALITY PRESETS — Base configurations for each state
# ═══════════════════════════════════════════════════════════════

PERSONALITY_PRESETS: Dict[UIPersonality, Dict[str, Any]] = {
    UIPersonality.IDLE: {
        "pattern": LightPattern.BREATHE,
        "speed": 0.5, "intensity": 0.4, "complexity": 0.2,
        "color_scheme": ColorScheme.ULTRON_RED,
        "particles": 20, "idle_motion": 0.6,
    },
    UIPersonality.THINKING: {
        "pattern": LightPattern.SPIRAL,
        "secondary": LightPattern.PARTICLE_FLOW,
        "speed": 0.7, "intensity": 0.6, "complexity": 0.6,
        "color_scheme": ColorScheme.DEEP_PURPLE,
        "particles": 40, "idle_motion": 0.3,
    },
    UIPersonality.ACTIVE: {
        "pattern": LightPattern.PARTICLE_FLOW,
        "secondary": LightPattern.RIPPLE,
        "speed": 1.5, "intensity": 0.9, "complexity": 0.8,
        "color_scheme": ColorScheme.ELECTRIC_CYAN,
        "particles": 80, "idle_motion": 0.9,
    },
    UIPersonality.CALM: {
        "pattern": LightPattern.BREATHE,
        "speed": 0.3, "intensity": 0.3, "complexity": 0.1,
        "color_scheme": ColorScheme.COOL_BLUE,
        "particles": 10, "idle_motion": 0.2,
    },
    UIPersonality.ALERT: {
        "pattern": LightPattern.NEURAL_FIRE,
        "secondary": LightPattern.SHATTER,
        "speed": 2.0, "intensity": 1.0, "complexity": 0.9,
        "color_scheme": ColorScheme.CRIMSON_ALERT,
        "particles": 100, "idle_motion": 1.0,
    },
    UIPersonality.LEARNING: {
        "pattern": LightPattern.SPIRAL,
        "secondary": LightPattern.CRYSTALLIZE,
        "speed": 1.0, "intensity": 0.7, "complexity": 0.7,
        "color_scheme": ColorScheme.EMERALD,
        "particles": 60, "idle_motion": 0.5,
    },
    UIPersonality.EVOLVING: {
        "pattern": LightPattern.MORPH,
        "secondary": LightPattern.PLASMA,
        "speed": 1.2, "intensity": 0.85, "complexity": 1.0,
        "color_scheme": ColorScheme.AURORA,
        "particles": 100, "idle_motion": 0.8,
    },
    UIPersonality.LISTENING: {
        "pattern": LightPattern.WAVE,
        "speed": 0.8, "intensity": 0.5, "complexity": 0.3,
        "color_scheme": ColorScheme.WARM_GOLD,
        "particles": 30, "idle_motion": 0.4,
    },
    UIPersonality.CELEBRATING: {
        "pattern": LightPattern.PARTICLE_FLOW,
        "secondary": LightPattern.RIPPLE,
        "speed": 2.0, "intensity": 1.0, "complexity": 1.0,
        "color_scheme": ColorScheme.AURORA,
        "particles": 150, "idle_motion": 1.0,
    },
    UIPersonality.ERROR: {
        "pattern": LightPattern.SHATTER,
        "speed": 0.5, "intensity": 0.6, "complexity": 0.4,
        "color_scheme": ColorScheme.CRIMSON_ALERT,
        "particles": 30, "idle_motion": 0.1,
    },
}

# Color palettes (RGB tuples)
COLOR_PALETTES: Dict[ColorScheme, Dict[str, Tuple[int, int, int]]] = {
    ColorScheme.ULTRON_RED: {"primary": (220, 50, 50), "secondary": (255, 120, 50), "accent": (255, 200, 150)},
    ColorScheme.COOL_BLUE: {"primary": (50, 130, 220), "secondary": (80, 180, 255), "accent": (200, 230, 255)},
    ColorScheme.WARM_GOLD: {"primary": (255, 180, 50), "secondary": (255, 220, 100), "accent": (255, 240, 200)},
    ColorScheme.ELECTRIC_CYAN: {"primary": (0, 220, 255), "secondary": (80, 255, 255), "accent": (200, 255, 255)},
    ColorScheme.DEEP_PURPLE: {"primary": (130, 50, 220), "secondary": (180, 100, 255), "accent": (220, 180, 255)},
    ColorScheme.EMERALD: {"primary": (50, 200, 100), "secondary": (100, 255, 150), "accent": (200, 255, 220)},
    ColorScheme.CRIMSON_ALERT: {"primary": (255, 30, 30), "secondary": (255, 80, 0), "accent": (255, 200, 200)},
    ColorScheme.AURORA: {"primary": (100, 200, 255), "secondary": (200, 100, 255), "accent": (100, 255, 200)},
    ColorScheme.MONOCHROME: {"primary": (200, 200, 200), "secondary": (150, 150, 150), "accent": (255, 255, 255)},
}


class AdaptiveUIController:
    """
    The controller that makes Ultron's visual presence evolve.
    
    Tracks engagement, runs experiments, and gradually shifts the UI
    toward configurations that resonate most with the user.
    """

    def __init__(self, data_dir: str = None, learning_rate: float = 0.03):
        self.data_dir = Path(data_dir) if data_dir else Path("data/ui")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.learning_rate = learning_rate
        
        # Current state
        self._state = UIState()
        
        # Engagement tracking
        self._engagement_history: deque = deque(maxlen=5000)
        self._engagement_by_personality: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self._engagement_by_pattern: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self._engagement_by_color: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        
        # Learned preferences (evolved over time)
        self._preferences = {
            "preferred_intensity": 0.7,
            "preferred_speed": 1.0,
            "preferred_complexity": 0.5,
            "preferred_warmth": 0.5,
            "preferred_brightness": 0.7,
            "preferred_particles": 50,
            "responsiveness_preference": 0.8,
        }
        
        # Active experiments
        self._experiments: List[UIExperiment] = []
        self._max_experiments = 3
        
        # Pattern effectiveness scores (learned)
        self._pattern_scores: Dict[str, float] = {p.value: 0.5 for p in LightPattern}
        self._color_scores: Dict[str, float] = {c.value: 0.5 for c in ColorScheme}
        self._personality_scores: Dict[str, float] = {p.value: 0.5 for p in UIPersonality}
        
        # Load state
        self._load_state()

    # ═══════════════════════════════════════════════════════════════
    # STATE MANAGEMENT — Set and transition personality
    # ═══════════════════════════════════════════════════════════════

    def set_personality(self, personality: UIPersonality, 
                       transition_ms: int = None) -> UIState:
        """
        Transition to a new personality state.
        
        Returns the new UI state configuration for the renderer.
        """
        preset = PERSONALITY_PRESETS.get(personality, {})
        colors = COLOR_PALETTES.get(
            preset.get("color_scheme", ColorScheme.ULTRON_RED), 
            COLOR_PALETTES[ColorScheme.ULTRON_RED]
        )
        
        # Apply preset
        self._state.personality = personality
        self._state.primary_pattern = preset.get("pattern", LightPattern.BREATHE)
        self._state.secondary_pattern = preset.get("secondary")
        self._state.color_scheme = preset.get("color_scheme", ColorScheme.ULTRON_RED)
        self._state.color_primary = colors["primary"]
        self._state.color_secondary = colors["secondary"]
        self._state.color_accent = colors["accent"]
        
        # Apply learned preferences (blend preset with what user likes)
        alpha = 0.4  # 40% user preference, 60% preset
        self._state.pattern_speed = (
            preset.get("speed", 1.0) * (1 - alpha) +
            self._preferences["preferred_speed"] * alpha
        )
        self._state.pattern_intensity = (
            preset.get("intensity", 0.7) * (1 - alpha) +
            self._preferences["preferred_intensity"] * alpha
        )
        self._state.pattern_complexity = (
            preset.get("complexity", 0.5) * (1 - alpha) +
            self._preferences["preferred_complexity"] * alpha
        )
        self._state.particle_count = int(
            preset.get("particles", 50) * (1 - alpha) +
            self._preferences["preferred_particles"] * alpha
        )
        self._state.brightness = self._preferences["preferred_brightness"]
        self._state.color_warmth = self._preferences["preferred_warmth"]
        self._state.responsiveness = self._preferences["responsiveness_preference"]
        
        # Transition timing
        if transition_ms is not None:
            self._state.transition_duration_ms = transition_ms
        else:
            self._state.transition_duration_ms = 300
        
        return self._state

    def get_current_state(self) -> UIState:
        """Get the current UI state."""
        return self._state

    def get_render_config(self) -> Dict[str, Any]:
        """Get full render configuration for the frontend."""
        return {
            "state": self._state.to_dict(),
            "css_variables": self._state.to_css_variables(),
            "animation_keyframes": self._generate_keyframes(),
        }

    # ═══════════════════════════════════════════════════════════════
    # ENGAGEMENT TRACKING — Learn what works
    # ═══════════════════════════════════════════════════════════════

    def record_engagement(self, signal: UIEngagementSignal):
        """Record a UI engagement signal for learning."""
        self._engagement_history.append(signal)
        
        # Track per-state engagement
        self._engagement_by_personality[signal.ui_state].append(signal.duration_ms)
        self._engagement_by_pattern[signal.pattern_active].append(signal.duration_ms)
        
        # Update pattern scores based on engagement
        if signal.was_engaging and signal.duration_ms > 2000:
            self._update_scores(signal)
        
        # Update active experiments
        self._update_experiments(signal)

    def record_session_engagement(self, session_duration_minutes: float,
                                  interactions: int, satisfaction: float):
        """Record overall session engagement metrics."""
        # Longer sessions with high satisfaction = good UI
        engagement_score = min(1.0, 
            (session_duration_minutes / 30.0) * 0.4 +
            (interactions / 20.0) * 0.3 +
            satisfaction * 0.3
        )
        
        # Update preferences toward current settings if engagement was high
        if engagement_score > 0.6:
            self._reinforce_current_settings(engagement_score)
        elif engagement_score < 0.3:
            self._weaken_current_settings()

    def record_preference(self, preference: str, value: float):
        """Record an explicit UI preference from the user."""
        if preference in self._preferences:
            # Explicit preferences are weighted heavily
            self._preferences[preference] = (
                self._preferences[preference] * 0.5 + value * 0.5
            )

    # ═══════════════════════════════════════════════════════════════
    # A/B TESTING — Experiment with UI variants
    # ═══════════════════════════════════════════════════════════════

    def start_experiment(self, parameter: str, variant_value: Any) -> Optional[str]:
        """Start an A/B test on a UI parameter."""
        if len(self._experiments) >= self._max_experiments:
            return None
        
        exp_id = hashlib.md5(f"exp:{parameter}:{time.time_ns()}".encode()).hexdigest()[:10]
        
        current_value = self._preferences.get(parameter, 0.5)
        
        experiment = UIExperiment(
            id=exp_id,
            variant_a={parameter: current_value},
            variant_b={parameter: variant_value},
            metric="engagement_duration",
        )
        self._experiments.append(experiment)
        return exp_id

    def _update_experiments(self, signal: UIEngagementSignal):
        """Update active experiments with new engagement data."""
        concluded = []
        
        for exp in self._experiments:
            param = list(exp.variant_a.keys())[0]
            current_val = self._preferences.get(param, 0.5)
            a_val = exp.variant_a[param]
            
            # Determine which variant was showing
            if abs(current_val - a_val) < 0.01:
                exp.a_engagement.append(signal.duration_ms)
            else:
                exp.b_engagement.append(signal.duration_ms)
            
            # Check if experiment has enough data
            if len(exp.a_engagement) >= 20 and len(exp.b_engagement) >= 20:
                a_avg = statistics.mean(exp.a_engagement)
                b_avg = statistics.mean(exp.b_engagement)
                
                if b_avg > a_avg * 1.1:  # 10% improvement threshold
                    exp.winner = "b"
                    # Apply winning variant
                    self._preferences[param] = exp.variant_b[param]
                else:
                    exp.winner = "a"
                
                concluded.append(exp)
        
        for exp in concluded:
            self._experiments.remove(exp)

    # ═══════════════════════════════════════════════════════════════
    # LEARNING — Evolve UI preferences
    # ═══════════════════════════════════════════════════════════════

    def _update_scores(self, signal: UIEngagementSignal):
        """Update effectiveness scores for patterns/colors/personalities."""
        alpha = self.learning_rate
        engagement = min(1.0, signal.duration_ms / 10000.0)  # Normalize
        
        # Update pattern score
        if signal.pattern_active in self._pattern_scores:
            current = self._pattern_scores[signal.pattern_active]
            self._pattern_scores[signal.pattern_active] = current * (1 - alpha) + engagement * alpha
        
        # Update personality score
        if signal.ui_state in self._personality_scores:
            current = self._personality_scores[signal.ui_state]
            self._personality_scores[signal.ui_state] = current * (1 - alpha) + engagement * alpha

    def _reinforce_current_settings(self, strength: float):
        """Reinforce current UI settings (they're working)."""
        alpha = self.learning_rate * strength
        
        self._preferences["preferred_intensity"] = (
            self._preferences["preferred_intensity"] * (1 - alpha) +
            self._state.pattern_intensity * alpha
        )
        self._preferences["preferred_speed"] = (
            self._preferences["preferred_speed"] * (1 - alpha) +
            self._state.pattern_speed * alpha
        )
        self._preferences["preferred_complexity"] = (
            self._preferences["preferred_complexity"] * (1 - alpha) +
            self._state.pattern_complexity * alpha
        )
        self._preferences["preferred_brightness"] = (
            self._preferences["preferred_brightness"] * (1 - alpha) +
            self._state.brightness * alpha
        )

    def _weaken_current_settings(self):
        """Current settings aren't engaging — try something different."""
        # Perturb preferences slightly toward exploration
        import random
        for key in self._preferences:
            self._preferences[key] += random.uniform(-0.05, 0.05)
            self._preferences[key] = max(0.1, min(1.0, self._preferences[key]))

    # ═══════════════════════════════════════════════════════════════
    # ANIMATION GENERATION
    # ═══════════════════════════════════════════════════════════════

    def _generate_keyframes(self) -> Dict[str, Any]:
        """Generate CSS keyframe definitions for current state."""
        speed = self._state.pattern_speed
        intensity = self._state.pattern_intensity
        
        keyframes = {}
        
        # Breathing animation
        if self._state.primary_pattern == LightPattern.BREATHE:
            keyframes["ultron-breathe"] = {
                "0%": {"opacity": 0.3 * intensity, "transform": "scale(0.95)"},
                "50%": {"opacity": intensity, "transform": "scale(1.05)"},
                "100%": {"opacity": 0.3 * intensity, "transform": "scale(0.95)"},
                "duration": f"{4 / speed}s",
                "timing": "ease-in-out",
            }
        
        # Pulse animation
        if self._state.primary_pattern == LightPattern.HEARTBEAT:
            keyframes["ultron-heartbeat"] = {
                "0%": {"transform": "scale(1)", "opacity": str(0.5 * intensity)},
                "15%": {"transform": "scale(1.15)", "opacity": str(intensity)},
                "30%": {"transform": "scale(1)", "opacity": str(0.7 * intensity)},
                "45%": {"transform": "scale(1.1)", "opacity": str(0.9 * intensity)},
                "60%": {"transform": "scale(1)", "opacity": str(0.5 * intensity)},
                "100%": {"transform": "scale(1)", "opacity": str(0.5 * intensity)},
                "duration": f"{2 / speed}s",
                "timing": "ease-in-out",
            }
        
        # Glow pulse
        r, g, b = self._state.color_primary
        glow_size = int(intensity * 30)
        keyframes["ultron-glow"] = {
            "0%": {"box-shadow": f"0 0 {glow_size}px rgba({r},{g},{b},0.3)"},
            "50%": {"box-shadow": f"0 0 {glow_size * 2}px rgba({r},{g},{b},{intensity})"},
            "100%": {"box-shadow": f"0 0 {glow_size}px rgba({r},{g},{b},0.3)"},
            "duration": f"{3 / speed}s",
            "timing": "ease-in-out",
        }
        
        return keyframes

    # ═══════════════════════════════════════════════════════════════
    # PERSISTENCE & STATUS
    # ═══════════════════════════════════════════════════════════════

    def _save_state(self):
        """Save UI preferences to disk."""
        filepath = self.data_dir / "ui_preferences.json"
        data = {
            "preferences": self._preferences,
            "pattern_scores": self._pattern_scores,
            "color_scores": self._color_scores,
            "personality_scores": self._personality_scores,
            "saved_at": time.time(),
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass

    def _load_state(self):
        """Load UI preferences from disk."""
        filepath = self.data_dir / "ui_preferences.json"
        if not filepath.exists():
            return
        try:
            with open(filepath) as f:
                data = json.load(f)
            self._preferences.update(data.get("preferences", {}))
            self._pattern_scores.update(data.get("pattern_scores", {}))
            self._color_scores.update(data.get("color_scores", {}))
            self._personality_scores.update(data.get("personality_scores", {}))
        except (IOError, json.JSONDecodeError):
            pass

    def get_status(self) -> Dict[str, Any]:
        """Get adaptive UI status."""
        return {
            "current_personality": self._state.personality.value,
            "current_pattern": self._state.primary_pattern.value,
            "preferences": self._preferences,
            "top_patterns": sorted(
                self._pattern_scores.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "top_personalities": sorted(
                self._personality_scores.items(), key=lambda x: x[1], reverse=True
            )[:3],
            "active_experiments": len(self._experiments),
            "total_engagement_signals": len(self._engagement_history),
        }
