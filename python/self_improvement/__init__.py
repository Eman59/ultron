"""
Ultron Self-Improvement Engine

A recursive self-improving system that:
  1. Monitors its own execution and performance metrics
  2. Identifies bottlenecks, failures, and suboptimal patterns
  3. Generates code patches to fix or improve itself
  4. Tests patches in an isolated sandbox
  5. Applies successful patches to the live system
  6. Tracks improvement over time (the improvement curve)

This is the component that makes Ultron get smarter every hour
without any human intervention.
"""

__version__ = "0.1.0"

from .core.improvement_loop import SelfImprovementEngine
from .core.performance_monitor import PerformanceMonitor
from .code_gen.patch_generator import PatchGenerator
from .sandbox.test_runner import SandboxRunner
from .evaluator.improvement_evaluator import ImprovementEvaluator
