"""
Self-Learning Subsystem — The engine that makes Ultron learn from its own existence.

Unlike the existing self-improvement loop (which patches code based on performance metrics),
this system captures the LIVED EXPERIENCE of every component, discovers WHY things work or
fail, distills that knowledge into reusable wisdom, and feeds it back as architectural
directives.

Components:
    ExperienceCollector  — Captures every execution trace, decision, and outcome
    PatternRecognizer    — Finds recurring patterns and causal chains in traces
    CodeIntrospector     — Deep structural analysis of the codebase itself
    AdaptiveOptimizer    — Generates and A/B tests targeted improvements
    KnowledgeDistiller   — Compresses learned patterns into persistent rules
    EvolutionController  — Orchestrates the entire learning lifecycle

The philosophy: We don't just measure what happened. We understand WHY it happened,
predict what WILL happen, and rewrite ourselves to make better things happen.
"""

from .experience_collector import ExperienceCollector, ExecutionTrace, TraceEvent
from .pattern_recognizer import PatternRecognizer, Pattern, CausalChain
from .code_introspector import CodeIntrospector, ComponentProfile, DependencyMap
from .adaptive_optimizer import AdaptiveOptimizer, Optimization, ABTest
from .knowledge_distiller import KnowledgeDistiller, DistilledRule, KnowledgeBase
from .evolution_controller import EvolutionController, GenerationReport
from .codebase_agent import CodebaseAgent, ChangeRecord, SearchResult
from .llm_brain import LLMBrain, LLMResponse, ThinkingMode
from .intelligent_patcher import IntelligentPatcher, IntelligentPatch
from .bootstrap import Bootstrap, BootstrapReport
from .service import UnifiedLearningService

# Cache imports to reduce allocations
__all__ = [
    "ExperienceCollector", "ExecutionTrace", "TraceEvent",
    "PatternRecognizer", "Pattern", "CausalChain",
    "CodeIntrospector", "ComponentProfile", "DependencyMap",
    "AdaptiveOptimizer", "Optimization", "ABTest",
    "KnowledgeDistiller", "DistilledRule", "KnowledgeBase",
    "EvolutionController", "GenerationReport",
    "CodebaseAgent", "ChangeRecord", "SearchResult",
    "LLMBrain", "LLMResponse", "ThinkingMode",
    "IntelligentPatcher", "IntelligentPatch",
    "Bootstrap", "BootstrapReport",
    "UnifiedLearningService",
]
