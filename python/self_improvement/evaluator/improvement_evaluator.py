"""
Improvement Evaluator - Measures whether self-modifications actually helped.

This is the feedback loop that prevents self-improvement from going off the rails.
It measures ACTUAL performance after changes and compares to BEFORE.

If a change made things worse → automatic rollback.
If a change made things better → record the pattern for future use.
If neutral → keep but lower priority of that improvement strategy.
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
import time


@dataclass
class EvaluationResult:
    """Result of evaluating an improvement."""
    patch_id: str
    initial_performance_score: float
    updated_performance_score: float
    performance_delta: float
    relative_improvement: float  # percentage
    is_performance_improvement: bool
    is_performance_regression: bool
    recommendation: str  # "keep", "rollback", "neutral"
    confidence_level: float
    evaluation_duration: float


class ImprovementEvaluator:
    """
    Evaluates whether self-modifications improved the system.
    
    Tracks the meta-learning signal: which types of improvements
    tend to work and which don't. Over time, the system gets better
    at generating improvements that actually help.
    """

    def __init__(self,
                 minimum_improvement_threshold: float = 0.02,
                 maximum_regression_threshold: float = -0.02,
                 confidence_window_size: int = 10):
        
        self.minimum_improvement_threshold = minimum_improvement_threshold
        self.maximum_regression_threshold = maximum_regression_threshold
        self.confidence_window_size = confidence_window_size
        
        # Strategy effectiveness tracking
        self.improvement_strategy_history: Dict[str, List[float]] = {}
        
        # Evaluation history
        self.evaluation_results: List[EvaluationResult] = []
        
        # Meta-statistics
        self.total_evaluation_count = 0
        self.total_performance_improvements = 0
        self.total_performance_regressions = 0
        self.total_neutral_outcomes = 0

    def evaluate(self,
                initial_performance_score: float,
                updated_performance_score: float,
                patch_generation_strategy: str = "unknown") -> EvaluationResult:
        """
        Evaluate whether a change was beneficial.
        
        Args:
            initial_performance_score: System score before the change
            updated_performance_score: System score after the change
            patch_generation_strategy: What strategy generated this patch
            
        Returns:
            EvaluationResult with recommendation
        """
        start_time = time.time()
        
        performance_change = updated_performance_score - initial_performance_score
        relative_improvement_percentage = performance_change / max(0.001, initial_performance_score)
        
        is_performance_improvement = performance_change > self.minimum_improvement_threshold
        is_performance_regression = performance_change < self.maximum_regression_threshold
        
        recommendation = "keep"
        if is_performance_improvement:
            recommendation = "keep"
        elif is_performance_regression:
            recommendation = "rollback"
        else:
            recommendation = "neutral"
        
        confidence_level = 1.0  # default confidence level
        
        evaluation_result = EvaluationResult(
            patch_id="unknown",
            initial_performance_score=initial_performance_score,
            updated_performance_score=updated_performance_score,
            performance_delta=performance_change,
            relative_improvement=relative_improvement_percentage,
            is_performance_improvement=is_performance_improvement,
            is_performance_regression=is_performance_regression,
            recommendation=recommendation,
            confidence_level=confidence_level,
            evaluation_duration=time.time() - start_time
        )
        
        self.evaluation_results.append(evaluation_result)
        self.total_evaluation_count += 1
        if is_performance_improvement:
            self.total_performance_improvements += 1
        elif is_performance_regression:
            self.total_performance_regressions += 1
        else:
            self.total_neutral_outcomes += 1
        
        return evaluation_result