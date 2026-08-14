"""
Ultron Biological Interface Layer

Interface protocol for connecting to biological neural organoids.
This allows Ultron to process "irrational" signals — gut feelings,
intuition, and non-logical pattern recognition that pure computation misses.

Status: INTERFACE PROTOCOL ONLY (no physical hardware connected)

When connected to real organoids (brain-on-chip), this layer:
  - Reads electrical signals from biological neurons
  - Translates spike patterns into decision signals
  - Feeds back digital state to biological substrate
  - Monitors organoid health and viability

The key insight: biological neurons evolved for 3.8 billion years.
They detect patterns that no algorithm can replicate — yet.
"""

__version__ = "0.1.0"

from .organoid_interface import OrganoidInterface, OrganoidSignal
from .intuition_engine import IntuitionEngine, GutFeeling
