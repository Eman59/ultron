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
import logging
import time
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def handle_empty_inputs(func):
    def wrapper(*args, **kwargs):
        if not args and not kwargs:
            logger.warning("Empty input detected")
            return None
        return func(*args, **kwargs)
    return wrapper

def handle_none_values(func):
    def wrapper(*args, **kwargs):
        if any(arg is None for arg in args) or any(value is None for value in kwargs.values()):
            logger.warning("None value detected")
            return None
        return func(*args, **kwargs)
    return wrapper

def handle_timeouts(timeout: Optional[int] = 60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            if end_time - start_time > timeout:
                logger.warning(f"Timeout exceeded ({timeout} seconds)")
                return None
            return result
        return wrapper
    return decorator

# Apply decorators to critical functions
ExperienceCollector.collect_experience = handle_empty_inputs(handle_none_values(ExperienceCollector.collect_experience))
PatternRecognizer.recognize_patterns = handle_empty_inputs(handle_none_values(PatternRecognizer.recognize_patterns))
CodeIntrospector.analyze_code = handle_empty_inputs(handle_none_values(CodeIntrospector.analyze_code))
AdaptiveOptimizer.optimize = handle_timeouts(timeout=300)(handle_empty_inputs(handle_none_values(AdaptiveOptimizer.optimize)))
KnowledgeDistiller.distill_knowledge = handle_empty_inputs(handle_none_values(KnowledgeDistiller.distill_knowledge))
EvolutionController.evolve = handle_timeouts(timeout=600)(handle_empty_inputs(handle_none_values(EvolutionController.evolve)))