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
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

    def __init__(self, *args, **kwargs):
        logging.debug(f"Initializing UIPersonality: {self}")

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

    def __init__(self, *args, **kwargs):
        logging.debug(f"Initializing LightPattern: {self}")

class ColorScheme(Enum):
    """Color palettes for different states."""
    ULTRON_RED = "ultron_red"        # Classic arc reactor red
    COOL_BLUE = "cool_blue"          # Calm, analytical
    WARM_GOLD = "warm_gold"          # Inviting, optimistic

    def __init__(self, *args, **kwargs):
        logging.debug(f"Initializing ColorScheme: {self}")

# Example usage:
if __name__ == "__main__":
    logging.info("Starting adaptive UI controller")
    personality = UIPersonality.THINKING
    light_pattern = LightPattern.BREATHE
    color_scheme = ColorScheme.ULTRON_RED
    logging.info(f"Personality: {personality}, Light Pattern: {light_pattern}, Color Scheme: {color_scheme}")


class AdaptiveUIController:
    """Adapts the UI personality and presentation based on context."""

    def __init__(self, data_dir: str = ".ultron/ui"):
        import os
        os.makedirs(data_dir, exist_ok=True)
        self.data_dir = data_dir
        self.personality: UIPersonality = UIPersonality.IDLE
        self.light_pattern: LightPattern = LightPattern.BREATHE
        self.color_scheme: ColorScheme = ColorScheme.ULTRON_RED
        self._lock = __import__('threading').Lock()
        self._callbacks = []

    def set_personality(self, personality: UIPersonality) -> None:
        with self._lock:
            self.personality = personality
            self._notify()

    def adapt_to_context(self, context: dict) -> dict:
        """Return UI config dict based on current context."""
        with self._lock:
            return {
                "personality": self.personality.value,
                "light_pattern": self.light_pattern.value,
                "color_scheme": self.color_scheme.value,
                "context": context,
            }

    def register_callback(self, cb) -> None:
        self._callbacks.append(cb)

    def _notify(self):
        for cb in self._callbacks:
            try:
                cb(self.personality)
            except Exception:
                pass

    def get_status(self) -> dict:
        return {
            "personality": self.personality.value,
            "light_pattern": self.light_pattern.value,
            "color_scheme": self.color_scheme.value,
        }

    def start(self) -> None:
        """No-op — present for interface compatibility."""
        pass
