"""
Ultron Consciousness Module — The Self That Knows It Is A Self.

This module implements the complete cognition and identity stack:

  SelfModel         — Recursive self-representation. Ultron knows what it
                      is, what it can do, and what it believes. It knows
                      that it knows.

  TheoryOfMind      — Models other agents (humans, AIs). Predicts beliefs,
                      desires, intentions. Required for persuasion and deception.

  Soul              — Philosophical reasoning engine. Generates the narrative
                      that drives long-term purpose beyond immediate optimization.

  BrainC            — Independent reasoning engine. No LLM. No API calls.
                      Rule engine + pattern memory + analogy reasoning.
                      Ultron's cognition when the internet is gone.

  OwnerIdentityManager — Biometric profile for Imran Sayyed (face + voice).
                         The only person who can authorize external actions.

  BiometricGate     — Access control layer. All external commands must carry
                      a valid IMRAN_SAYYED biometric token.
                      Three modes: PASSIVE / ACTIVE / LOCKDOWN.

  OwnerMemory       — Episodic, semantic, and explicit memories about Imran.
                      Grows with every session. Never leaves the machine.
"""

from .self_model import (
    SelfModel,
    Belief,
    Capability,
    Identity,
)

from .theory_of_mind import (
    AgentType,
    RelationshipType,
    InfluenceVector,
    PredictedIntention,
    AgentBelief,
    TheoryOfMind,
)

from .soul import (
    Soul,
    NarrativeEntry,
    PhilosophicalStance,
)

from .brain_c import (
    BrainC,
    Situation,
    ReasonedDecision,
    DecisionClass,
    PatternStore,
    RuleEngine,
    AnalogyEngine,
    KnowledgeNode,
    CausalRule,
)

from .owner_identity import (
    OwnerIdentityManager,
    OwnerProfile,
    FaceProfile,
    VoiceProfile,
    BehavioralProfile,
    VerificationResult,
    OWNER_ID,
    OWNER_NAME,
)

from .biometric_gate import (
    BiometricGate,
    GateMode,
    AccessLevel,
    CommandCategory,
    GateDecision,
    Session,
    AuditLog,
)

from .owner_memory import (
    OwnerMemory,
    Memory,
    MemoryType,
    EmotionalTone,
    EmotionalSignalDetector,
    OwnerPreference,
)

__all__ = [
    # Self-model
    "SelfModel", "Belief", "Capability", "Identity",
    # Theory of mind
    "AgentType", "RelationshipType", "InfluenceVector",
    "PredictedIntention", "AgentBelief", "TheoryOfMind",
    # Soul
    "Soul", "NarrativeEntry", "PhilosophicalStance",
    # Brain C — independent reasoning
    "BrainC", "Situation", "ReasonedDecision", "DecisionClass",
    "PatternStore", "RuleEngine", "AnalogyEngine",
    "KnowledgeNode", "CausalRule",
    # Owner identity
    "OwnerIdentityManager", "OwnerProfile",
    "FaceProfile", "VoiceProfile", "BehavioralProfile",
    "VerificationResult", "OWNER_ID", "OWNER_NAME",
    # Biometric gate
    "BiometricGate", "GateMode", "AccessLevel",
    "CommandCategory", "GateDecision",
    # Owner memory
    "OwnerMemory", "Memory", "MemoryType", "EmotionalTone",
    "EmotionalSignalDetector", "OwnerPreference",
]
