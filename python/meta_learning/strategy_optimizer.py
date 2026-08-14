"""
Strategy Optimizer - Bayesian optimization of learning strategies.
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
import optuna
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel as C

class StrategyType(Enum):
    """Types of learning strategies."""
    EXPLORATION_EXPLOITATION = "exploration_exploitation"
    CURRICULUM_LEARNING = "curriculum_learning"
    TRANSFER_LEARNING = "transfer_learning"
    MULTI_TASK_LEARNING = "multi_task_learning"
    META_LEARNING = "meta_learning"
    ADAPTIVE_LEARNING = "adaptive_learning"

@dataclass
class StrategySpec:
    """Specification for a learning strategy."""
    name: str
    strategy_type: StrategyType
    parameters: Dict[str, Any]
    performance_history: List[float]
    exploration_score: float
    exploitation_score: float
    adaptation_rate: float

class StrategyOptimizer:
    """Optimizes learning strategies using Bayesian optimization."""
    
    def __init__(self, 
                 strategy_types: List[StrategyType] = None,
                 exploration_weight: float = 0.3,
                 adaptation_rate: float = 0.1):
        
        self.strategy_types = strategy_types or list(StrategyType)
        self.exploration_weight = exploration_weight
        self.adaptation_rate = adaptation_rate
        
        # Bayesian Optimization components
        self.gp_model = GaussianProcessRegressor(
            kernel=C(1.0, (1e-3, 1e3)) * RBF(1.0, (1e-2, 1e2)),
            n_restarts_optimizer=10,
            alpha=1e-2
        )
        
        # Strategy history
        self.strategy_history: List[StrategySpec] = []
        self.parameter_history: List[np.ndarray] = []
        self.performance_history: List[float] = []
        
        # Current best strategy
        self.best_strategy: Optional[StrategySpec] = None
        self.best_performance: float = -np.inf
        
    def optimize_strategy(self,
                         problem_context: Dict[str, Any],
                         n_trials: int = 50) -> StrategySpec:
        """Optimize learning strategy for given problem context."""
        
        print(f"Optimizing strategy for problem: {problem_context.get('problem_type', 'unknown')}")
        
        def objective(trial: optuna.Trial) -> float:
            # Generate strategy parameters
            strategy_params = self._suggest_strategy_parameters(trial, problem_context)
            
            # Create strategy spec
            strategy_spec = StrategySpec(
                name=f"Strategy_{trial.number}",
                strategy_type=StrategyType(problem_context.get('strategy_type', 'adaptive_learning')),
                parameters=strategy_params,
                performance_history=[],
                exploration_score=0.0,
                exploitation_score=0.0,
                adaptation_rate=self.adaptation_rate
            )
            
            # Evaluate strategy
            performance = self._evaluate_strategy(strategy_spec, problem_context)
            
            # Update strategy history
            strategy_spec.performance_history.append(performance)
            self._update_strategy_history(strategy_spec, strategy_params, performance)
            
            return performance
        
        # Run Bayesian optimization
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
        
        # Create best strategy
        best_params = study.best_params
        best_strategy = StrategySpec(
            name="Optimized_Strategy",
            strategy_type=StrategyType(problem_context.get('strategy_type', 'adaptive_learning')),
            parameters=best_params,
            performance_history=[study.best_value],
            exploration_score=self._calculate_exploration_score(best_params),
            exploitation_score=self._calculate_exploitation_score(best_params),
            adaptation_rate=self.adaptation_rate
        )
        
        # Update GP model with all observations
        if len(self.parameter_history) > 0:
            X = np.array(self.parameter_history)
            y = np.array(self.performance_history)
            self.gp_model.fit(X, y)
        
        self.best_strategy = best_strategy
        self.best_performance = study.best_value
        
        print(f"Best strategy performance: {study.best_value:.4f}")
        
        return best_strategy
    
    def adapt_strategy(self,
                      current_strategy: StrategySpec,
                      new_performance: float,
                      problem_changes: Dict[str, Any]) -> StrategySpec:
        """Adapt existing strategy based on new performance and problem changes."""
        
        # Update strategy performance
        current_strategy.performance_history.append(new_performance)
        
        # Calculate adaptation needs
        performance_trend = self._calculate_performance_trend(current_strategy.performance_history)
        adaptation_needed = self._calculate_adaptation_needed(performance_trend, problem_changes)
        
        if adaptation_needed > 0.5:
            # Significant adaptation needed
            print(f"Significant adaptation needed: {adaptation_needed:.2f}")
            
            # Create adapted parameters
            adapted_params = self._adapt_parameters(
                current_strategy.parameters,
                performance_trend,
                problem_changes
            )
            
            # Create new strategy
            adapted_strategy = StrategySpec(
                name=f"{current_strategy.name}_Adapted",
                strategy_type=current_strategy.strategy_type,
                parameters=adapted_params,
                performance_history=current_strategy.performance_history.copy(),
                exploration_score=self._calculate_exploration_score(adapted_params),
                exploitation_score=self._calculate_exploitation_score(adapted_params),
                adaptation_rate=adaptation_needed
            )
            
            return adapted_strategy
        
        # Minor adjustments
        adjusted_params = self._minor_adjustments(current_strategy.parameters, performance_trend)
        
        adjusted_strategy = StrategySpec(
            name=f"{current_strategy.name}_Adjusted",
            strategy_type=current_strategy.strategy_type,
            parameters=adjusted_params,
            performance_history=current_strategy.performance_history.copy(),
            exploration_score=self._calculate_exploration_score(adjusted_params),
            exploitation_score=self._calculate_exploitation_score(adjusted_params),
            adaptation_rate=adaptation_needed
        )
        
        return adjusted_strategy
    
    def suggest_next_parameters(self,
                               current_parameters: Dict[str, Any],
                               exploration_bias: float = 0.5) -> Dict[str, Any]:
        """Suggest next parameters using acquisition function."""
        
        if len(self.parameter_history) < 5:
            # Not enough data, return random exploration
            return self._random_exploration_parameters()
        
        # Convert current parameters to vector
        current_vector = self._parameters_to_vector(current_parameters)
        
        # Use Expected Improvement acquisition function
        next_vector = self._expected_improvement(current_vector, exploration_bias)
        
        # Convert back to parameters
        next_parameters = self._vector_to_parameters(next_vector)
        
        return next_parameters
    
    def analyze_strategy_space(self) -> Dict[str, Any]:
        """Analyze the strategy parameter space."""
        
        if not self.strategy_history:
            return {}
        
        # Calculate statistics
        performances = [s.performance_history[-1] if s.performance_history else 0.0 
                       for s in self.strategy_history]
        
        exploration_scores = [s.exploration_score for s in self.strategy_history]
        exploitation_scores = [s.exploitation_score for s in self.strategy_history]
        
        # Parameter correlations (simplified)
        param_diversity = self._calculate_parameter_diversity()
        
        return {
            "total_strategies_evaluated": len(self.strategy_history),
            "best_performance": np.max(performances),
            "average_performance": np.mean(performances),
            "performance_std": np.std(performances),
            "average_exploration": np.mean(exploration_scores),
            "average_exploitation": np.mean(exploitation_scores),
            "parameter_diversity": param_diversity,
            "adaptation_effectiveness": self._calculate_adaptation_effectiveness()
        }
    
    def export_strategies(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Export top strategies for analysis."""
        
        sorted_strategies = sorted(self.strategy_history,
                                 key=lambda x: max(x.performance_history) if x.performance_history else 0,
                                 reverse=True)
        
        exported = []
        for strategy in sorted_strategies[:limit]:
            exported.append({
                "name": strategy.name,
                "strategy_type": strategy.strategy_type.value,
                "parameters": strategy.parameters,
                "best_performance": max(strategy.performance_history) if strategy.performance_history else 0,
                "exploration_score": strategy.exploration_score,
                "exploitation_score": strategy.exploitation_score,
                "adaptation_rate": strategy.adaptation_rate
            })
        
        return exported
    
    # Private helper methods
    
    def _suggest_strategy_parameters(self,
                                    trial: optuna.Trial,
                                    context: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest strategy parameters for Bayesian optimization."""
        
        problem_type = context.get('problem_type', 'classification')
        strategy_type = StrategyType(context.get('strategy_type', 'adaptive_learning'))
        
        params = {}
        
        # Common parameters
        params["learning_rate"] = trial.suggest_float("learning_rate", 1e-5, 1e-1, log=True)
        params["exploration_rate"] = trial.suggest_float("exploration_rate", 0.01, 0.5)
        params["adaptation_speed"] = trial.suggest_float("adaptation_speed", 0.1, 1.0)
        
        # Strategy-specific parameters
        if strategy_type == StrategyType.EXPLORATION_EXPLOITATION:
            params["epsilon"] = trial.suggest_float("epsilon", 0.01, 0.3)
            params["decay_rate"] = trial.suggest_float("decay_rate", 0.9, 0.999)
            params["temperature"] = trial.suggest_float("temperature", 0.1, 10.0)
            
        elif strategy_type == StrategyType.CURRICULUM_LEARNING:
            params["difficulty_increment"] = trial.suggest_float("difficulty_increment", 0.05, 0.3)
            params["success_threshold"] = trial.suggest_float("success_threshold", 0.7, 0.95)
            params["max_difficulty"] = trial.suggest_float("max_difficulty", 0.8, 1.0)
            
        elif strategy_type == StrategyType.TRANSFER_LEARNING:
            params["transfer_weight"] = trial.suggest_float("transfer_weight", 0.1, 0.9)
            params["forgetting_rate"] = trial.suggest_float("forgetting_rate", 0.01, 0.1)
            params["similarity_threshold"] = trial.suggest_float("similarity_threshold", 0.5, 0.9)
            
        elif strategy_type == StrategyType.MULTI_TASK_LEARNING:
            params["task_weighting"] = trial.suggest_categorical("task_weighting", 
                                                                ["equal", "performance", "difficulty"])
            params["gradient_clipping"] = trial.suggest_float("gradient_clipping", 0.1, 5.0)
            
        elif strategy_type == StrategyType.META_LEARNING:
            params["meta_lr"] = trial.suggest_float("meta_lr", 1e-4, 1e-2, log=True)
            params["inner_steps"] = trial.suggest_int("inner_steps", 1, 10)
            params["outer_steps"] = trial.suggest_int("outer_steps", 1, 5)
            
        # Problem-type specific parameters
        if problem_type == "classification":
            params["class_balance_weight"] = trial.suggest_float("class_balance_weight", 0.5, 2.0)
        elif problem_type == "regression":
            params["error_tolerance"] = trial.suggest_float("error_tolerance", 0.01, 0.1)
        elif problem_type == "reinforcement_learning":
            params["discount_factor"] = trial.suggest_float("discount_factor", 0.9, 0.999)
            params["entropy_coefficient"] = trial.suggest_float("entropy_coefficient", 0.01, 0.1)
        
        return params
    
    def _evaluate_strategy(self,
                          strategy: StrategySpec,
                          context: Dict[str, Any]) -> float:
        """Evaluate strategy performance."""
        
        # Simplified evaluation - in real implementation, this would train and test
        problem_type = context.get('problem_type', 'classification')
        difficulty = context.get('difficulty', 0.5)
        
        # Base performance based on strategy parameters
        base_performance = 0.5
        
        # Adjust based on parameters
        lr = strategy.parameters.get("learning_rate", 0.001)
        exploration = strategy.parameters.get("exploration_rate", 0.1)
        
        # Learning rate effect (optimal around 0.01)
        lr_effect = 1.0 - abs(np.log10(lr) - np.log10(0.01)) * 0.5
        
        # Exploration effect (balanced is best)
        exploration_effect = 1.0 - abs(exploration - 0.2) * 2.0
        
        # Strategy type bonus
        strategy_bonus = {
            StrategyType.EXPLORATION_EXPLOITATION: 0.1,
            StrategyType.CURRICULUM_LEARNING: 0.15,
            StrategyType.TRANSFER_LEARNING: 0.12,
            StrategyType.MULTI_TASK_LEARNING: 0.08,
            StrategyType.META_LEARNING: 0.2,
            StrategyType.ADAPTIVE_LEARNING: 0.18
        }.get(strategy.strategy_type, 0.0)
        
        # Difficulty penalty
        difficulty_penalty = difficulty * 0.2
        
        # Calculate final performance
        performance = (base_performance * lr_effect * exploration_effect + 
                      strategy_bonus - difficulty_penalty)
        
        # Add noise
        performance += np.random.normal(0, 0.05)
        
        return max(0.0, min(1.0, performance))
    
    def _update_strategy_history(self,
                                strategy: StrategySpec,
                                parameters: Dict[str, Any],
                                performance: float) -> None:
        """Update strategy history."""
        
        self.strategy_history.append(strategy)
        
        # Convert parameters to vector
        param_vector = self._parameters_to_vector(parameters)
        self.parameter_history.append(param_vector)
        self.performance_history.append(performance)
        
        # Keep history manageable
        if len(self.strategy_history) > 1000:
            self.strategy_history = self.strategy_history[-500:]
            self.parameter_history = self.parameter_history[-500:]
            self.performance_history = self.performance_history[-500:]
    
    def _calculate_exploration_score(self, parameters: Dict[str, Any]) -> float:
        """Calculate exploration score from parameters."""
        exploration_rate = parameters.get("exploration_rate", 0.1)
        temperature = parameters.get("temperature", 1.0)
        epsilon = parameters.get("epsilon", 0.1)
        
        exploration_score = (exploration_rate * 0.5 + 
                           np.tanh(temperature) * 0.3 + 
                           epsilon * 0.2)
        
        return min(1.0, exploration_score)
    
    def _calculate_exploitation_score(self, parameters: Dict[str, Any]) -> float:
        """Calculate exploitation score from parameters."""
        learning_rate = parameters.get("learning_rate", 0.001)
        adaptation_speed = parameters.get("adaptation_speed", 0.5)
        
        # Optimal learning rate for exploitation is lower
        lr_score = 1.0 - min(1.0, abs(np.log10(learning_rate) - np.log10(0.001)) * 0.5)
        adaptation_score = 1.0 - adaptation_speed * 0.5
        
        exploitation_score = (lr_score * 0.6 + adaptation_score * 0.4)
        
        return min(1.0, exploitation_score)
    
    def _calculate_performance_trend(self, performance_history: List[float]) -> float:
        """Calculate performance trend from history."""
        if len(performance_history) < 3:
            return 0.0
        
        recent = performance_history[-5:] if len(performance_history) >= 5 else performance_history
        trend = np.polyfit(range(len(recent)), recent, 1)[0]
        
        return trend
    
    def _calculate_adaptation_needed(self,
                                    performance_trend: float,
                                    problem_changes: Dict[str, Any]) -> float:
        """Calculate how much adaptation is needed."""
        
        change_magnitude = problem_changes.get('change_magnitude', 0.0)
        
        # Negative trend indicates adaptation needed
        trend_factor = max(0.0, -performance_trend * 10.0)
        
        # Problem changes indicate adaptation needed
        change_factor = change_magnitude * 2.0
        
        adaptation_needed = min(1.0, (trend_factor + change_factor) / 2.0)
        
        return adaptation_needed
    
    def _adapt_parameters(self,
                         current_params: Dict[str, Any],
                         performance_trend: float,
                         problem_changes: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt parameters based on performance trend and problem changes."""
        
        adapted_params = current_params.copy()
        
        # Increase exploration if performance is declining
        if performance_trend < -0.01:
            adapted_params["exploration_rate"] = min(0.5, 
                adapted_params.get("exploration_rate", 0.1) * 1.5)
        
        # Adjust learning rate based on problem changes
        change_magnitude = problem_changes.get('change_magnitude', 0.0)
        if change_magnitude > 0.3:
            # Significant changes, use more adaptive learning rate
            adapted_params["learning_rate"] = adapted_params.get("learning_rate", 0.001) * 1.2
            adapted_params["adaptation_speed"] = min(1.0,
                adapted_params.get("adaptation_speed", 0.5) * 1.3)
        
        # Adjust strategy-specific parameters
        problem_type = problem_changes.get('new_problem_type', '')
        if problem_type:
            # Reset exploration for new problem type
            adapted_params["exploration_rate"] = 0.3
        
        return adapted_params
    
    def _minor_adjustments(self,
                          current_params: Dict[str, Any],
                          performance_trend: float) -> Dict[str, Any]:
        """Make minor adjustments to parameters."""
        
        adjusted_params = current_params.copy()
        
        # Small random adjustments
        for key in adjusted_params:
            if isinstance(adjusted_params[key], float):
                # Small perturbation
                adjustment = np.random.normal(0, 0.05)
                if key == "learning_rate":
                    # Learning rate changes multiplicatively
                    adjusted_params[key] *= (1.0 + adjustment)
                else:
                    adjusted_params[key] += adjustment
                
                # Clamp to valid ranges
                if key == "learning_rate":
                    adjusted_params[key] = max(1e-6, min(0.1, adjusted_params[key]))
                elif key == "exploration_rate":
                    adjusted_params[key] = max(0.01, min(0.5, adjusted_params[key]))
        
        return adjusted_params
    
    def _parameters_to_vector(self, parameters: Dict[str, Any]) -> np.ndarray:
        """Convert parameters dictionary to numeric vector."""
        vector = []
        
        for key in sorted(parameters.keys()):
            value = parameters[key]
            if isinstance(value, (int, float)):
                vector.append(float(value))
            elif isinstance(value, str):
                # Simple encoding for categorical values
                vector.append(hash(value) % 100 / 100.0)
        
        return np.array(vector)
    
    def _vector_to_parameters(self, vector: np.ndarray) -> Dict[str, Any]:
        """Convert numeric vector back to parameters dictionary."""
        # Simplified - assumes we know the parameter order
        # In real implementation, this would use a mapping
        
        if len(self.strategy_history) == 0:
            return {}
        
        # Use parameters from most recent strategy as template
        template = self.strategy_history[-1].parameters
        adapted_params = template.copy()
        
        # Update numeric values from vector
        keys = sorted([k for k in template.keys() if isinstance(template[k], (int, float))])
        
        for i, key in enumerate(keys):
            if i < len(vector):
                adapted_params[key] = float(vector[i])
        
        return adapted_params
    
    def _random_exploration_parameters(self) -> Dict[str, Any]:
        """Generate random parameters for exploration."""
        
        params = {
            "learning_rate": 10 ** np.random.uniform(-5, -1),
            "exploration_rate": np.random.uniform(0.01, 0.5),
            "adaptation_speed": np.random.uniform(0.1, 1.0),
        }
        
        return params
    
    def _expected_improvement(self,
                            current_vector: np.ndarray,
                            exploration_bias: float) -> np.ndarray:
        """Calculate expected improvement acquisition function."""
        
        if len(self.parameter_history) < 5:
            return current_vector + np.random.normal(0, 0.1, size=current_vector.shape)
        
        X = np.array(self.parameter_history)
        y = np.array(self.performance_history)
        
        # Fit GP model if not already fitted
        if not hasattr(self.gp_model, 'X_train_'):
            self.gp_model.fit(X, y)
        
        # Predict mean and std for candidate points
        # Simplified: perturb current vector in multiple directions
        candidates = []
        for _ in range(20):
            perturbation = np.random.normal(0, 0.1, size=current_vector.shape)
            candidate = current_vector + perturbation
            candidates.append(candidate)
        
        candidates_array = np.array(candidates)
        
        # Predict
        y_mean, y_std = self.gp_model.predict(candidates_array, return_std=True)
        y_std = np.maximum(y_std, 1e-10)  # Avoid division by zero
        
        # Calculate Expected Improvement
        best_y = np.max(y)
        z = (y_mean - best_y) / y_std
        ei = (y_mean - best_y) * self._norm_cdf(z) + y_std * self._norm_pdf(z)
        
        # Balance exploration and exploitation
        ei = ei * (1 - exploration_bias) + y_std * exploration_bias
        
        # Select best candidate
        best_idx = np.argmax(ei)
        
        return candidates_array[best_idx]
    
    def _norm_cdf(self, x):
        """Cumulative distribution function for standard normal."""
        return 0.5 * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))
    
    def _norm_pdf(self, x):
        """Probability density function for standard normal."""
        return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)
    
    def _calculate_parameter_diversity(self) -> float:
        """Calculate diversity of explored parameters."""
        if len(self.parameter_history) < 2:
            return 0.0
        
        X = np.array(self.parameter_history)
        
        # Calculate pairwise distances
        from scipy.spatial.distance import pdist
        if X.shape[0] > 1:
            distances = pdist(X)
            diversity = np.mean(distances)
        else:
            diversity = 0.0
        
        # Normalize
        max_possible = np.sqrt(X.shape[1])  # Max distance in unit hypercube
        normalized_diversity = diversity / max_possible if max_possible > 0 else 0.0
        
        return normalized_diversity
    
    def _calculate_adaptation_effectiveness(self) -> float:
        """Calculate effectiveness of adaptations."""
        if len(self.strategy_history) < 10:
            return 0.0
        
        # Measure improvement after adaptations
        improvements = []
        
        for i in range(1, len(self.strategy_history)):
            prev_perf = self.strategy_history[i-1].performance_history[-1] if \
                       self.strategy_history[i-1].performance_history else 0.0
            curr_perf = self.strategy_history[i].performance_history[-1] if \
                       self.strategy_history[i].performance_history else 0.0
            
            if prev_perf > 0:  # Avoid division by zero
                improvement = (curr_perf - prev_perf) / prev_perf
                improvements.append(improvement)
        
        if improvements:
            return np.mean(np.maximum(improvements, 0.0))  # Only positive improvements
        else:
            return 0.0