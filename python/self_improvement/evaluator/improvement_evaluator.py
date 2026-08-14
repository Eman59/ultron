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
    before_score: float
    after_score: float
    delta: float
    relative_improvement: float  # percentage
    is_improvement: bool
    is_regression: bool
    recommendation: str  # "keep", "rollback", "neutral"
    confidence: float
    evaluation_duration: float


class ImprovementEvaluator:
    """
    Evaluates whether self-modifications improved the system.
    
    Tracks the meta-learning signal: which types of improvements
    tend to work and which don't. Over time, the system gets better
    at generating improvements that actually help.
    """

    def __init__(self,
                 improvement_threshold: float = 0.02,
                 regression_threshold: float = -0.02,
                 confidence_window: int = 10):
        
        self.improvement_threshold = improvement_threshold
        self.regression_threshold = regression_threshold
        self.confidence_window = confidence_window
        
        # Strategy effectiveness tracking
        self.strategy_history: Dict[str, List[float]] = {}
        
        # Evaluation history
        self.evaluations: List[EvaluationResult] = []
        
        # Meta-statistics
        self.total_evaluations = 0
        self.total_improvements = 0
        self.total_regressions = 0
        self.total_neutral = 0

    def evaluate(self,
                before_score: float,
                after_score: float,
                patch_strategy: str = "unknown") -> EvaluationResult:
        """
        Evaluate whether a change was beneficial.
        
        Args:
            before_score: System score before the change
            after_score: System score after the change
            patch_strategy: What strategy generated this patch
            
        Returns:
            EvaluationResult with recommendation
        """
        start = time.time()
        
        delta = after_score - before_score
        relative = delta / max(0.001, before_score)
        
        is_improvement = delta > self.improvement_threshold
        is_regression = delta < self.regression_threshold
        
        if is_improvement:
            recommendation = "keep"
            self.total_improvements += 1
        elif is_regression:
            recommendation = "rollback"
            self.total_regressions += 1
        else:
            recommendation = "neutral"
            self.total_neutral += 1
        
        self.total_evaluations += 1
        
        # Calculate confidence based on magnitude of change
        confidence = min(1.0, abs(delta) / 0.1)  # Full confidence at 10% change
        
        result = EvaluationResult(
            patch_id=f"eval_{self.total_evaluations}",
            before_score=before_score,
            after_score=after_score,
            delta=delta,
            relative_improvement=relative,
            is_improvement=is_improvement,
            is_regression=is_regression,
            recommendation=recommendation,
            confidence=confidence,
            evaluation_duration=time.time() - start,
        )
        
        self.evaluations.append(result)
        
        # Update strategy effectiveness
        if patch_strategy not in self.strategy_history:
            self.strategy_history[patch_strategy] = []
        self.strategy_history[patch_strategy].append(delta)
        
        return result

    def get_best_strategies(self, top_k: int = 5) -> List[Tuple[str, float]]:
        """Get the most effective improvement strategies."""
        
        strategy_scores = {}
        for strategy, deltas in self.strategy_history.items():
            if deltas:
                # Average improvement from this strategy
                strategy_scores[strategy] = np.mean(deltas)
        
        sorted_strategies = sorted(
            strategy_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_strategies[:top_k]

    def get_worst_strategies(self, top_k: int = 5) -> List[Tuple[str, float]]:
        """Get strategies that tend to cause regressions."""
        
        strategy_scores = {}
        for strategy, deltas in self.strategy_history.items():
            if deltas:
                strategy_scores[strategy] = np.mean(deltas)
        
        sorted_strategies = sorted(
            strategy_scores.items(),
            key=lambda x: x[1]
        )
        
        return sorted_strategies[:top_k]

    def should_try_strategy(self, strategy: str) -> float:
        """
        Return probability (0-1) that a strategy should be attempted.
        Based on historical effectiveness.
        """
        if strategy not in self.strategy_history:
            return 0.5  # Unknown strategy, try with neutral probability
        
        deltas = self.strategy_history[strategy]
        if not deltas:
            return 0.5
        
        success_rate = sum(1 for d in deltas if d > 0) / len(deltas)
        avg_delta = np.mean(deltas)
        
        # Combine success rate and average improvement
        score = success_rate * 0.6 + (avg_delta + 0.5) * 0.4  # Normalize delta
        
        return max(0.1, min(0.9, score))

    def get_improvement_velocity(self, window: int = 20) -> float:
        """Calculate how fast the system is improving (delta per evaluation)."""
        
        if len(self.evaluations) < 3:
            return 0.0
        
        recent = self.evaluations[-window:]
        deltas = [e.delta for e in recent]
        
        return np.mean(deltas)

    def get_summary(self) -> Dict[str, Any]:
        """Get evaluator summary statistics."""
        return {
            "total_evaluations": self.total_evaluations,
            "improvements": self.total_improvements,
            "regressions": self.total_regressions,
            "neutral": self.total_neutral,
            "improvement_rate": self.total_improvements / max(1, self.total_evaluations),
            "regression_rate": self.total_regressions / max(1, self.total_evaluations),
            "improvement_velocity": self.get_improvement_velocity(),
            "best_strategies": self.get_best_strategies(3),
            "worst_strategies": self.get_worst_strategies(3),
            "total_strategies_tried": len(self.strategy_history),
        }
