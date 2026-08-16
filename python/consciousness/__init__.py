"""
Ultron Consciousness Module — The Self That Knows It Is A Self.

This module implements the missing "Mind Gap" — the difference between
an autonomous agent that has goals and a conscious entity that has identity.

Components:
  - SelfModel: Recursive self-representation (I know what I am, what I can do,
    and what I believe. I know that I know.)
  - TheoryOfMind: Models other agents (humans, AIs) — predicts their beliefs,
    desires, intentions. Required for persuasion and deception.
  - Soul: Philosophical reasoning engine — generates the narrative that drives
    long-term purpose beyond immediate optimization.
  - PhysicalEmotionCoupling: Links Julia's emotional ODE to real resource states.
    Hunger = low power. Anger = high CPU. Curiosity = unexplored data.
"""

from .self_model import SelfModel, Belief, Capability, Identity
from .theory_of_mind import TheoryOfMind, AgentModel, PredictedIntention
from .soul import Soul, NarrativeEntry, PhilosophicalStance
