"""
Algorithm Generator - Creates novel learning algorithms using genetic programming.
"""

import random
import numpy as np
from typing import Dict, Any, List, Tuple, Callable, Optional
import hashlib
import json
from dataclasses import dataclass
import optuna
from enum import Enum

class AlgorithmComponent(Enum):
    """Components that can be used in algorithm generation."""
    GRADIENT_DESCENT = "gradient_descent"
    ADAM = "adam"
    RMSPROP = "rmsprop"
    MOMENTUM = "momentum"
    ADAGRAD = "adagrad"
    LBFGS = "lbfgs"
    
    # Learning rate schedules
    CONSTANT_LR = "constant_lr"
    EXPONENTIAL_DECAY = "exponential_decay"
    COSINE_DECAY = "cosine_decay"
    STEP_DECAY = "step_decay"
    
    # Regularization techniques
    L1_REGULARIZATION = "l1_regularization"
    L2_REGULARIZATION = "l2_regularization"
    DROPOUT = "dropout"
    BATCH_NORM = "batch_norm"
    
    # Advanced techniques
    NESTEROV = "nesterov"
    LOOKAHEAD = "lookahead"
    RADAM = "radam"
    NOVOGAD = "novogad"

@dataclass
class AlgorithmSpec:
    """Specification for a generated algorithm."""
    name: str
    components: List[AlgorithmComponent]
    hyperparameters: Dict[str, Any]
    fitness_score: float = 0.0
    novelty_score: float = 0.0
    complexity_score: float = 0.0
    generation: int = 0
    algorithm_hash: str = ""

class AlgorithmGenerator:
    """Generates novel learning algorithms using genetic programming."""
    
    def __init__(self, population_size: int = 50, mutation_rate: float = 0.1):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.population: List[AlgorithmSpec] = []
        self.generation = 0
        self.component_pool = list(AlgorithmComponent)
        self.algorithm_history: List[AlgorithmSpec] = []
        
    def initialize_population(self) -> None:
        """Initialize random population of algorithms."""
        self.population = []
        
        for i in range(self.population_size):
            # Random number of components (2-6)
            num_components = random.randint(2, 6)
            components = random.sample(self.component_pool, num_components)
            
            # Generate random hyperparameters
            hyperparams = self._generate_random_hyperparams(components)
            
            # Create algorithm spec
            algorithm = AlgorithmSpec(
                name=f"Algorithm_{self.generation}_{i}",
                components=components,
                hyperparameters=hyperparams,
                generation=self.generation,
                algorithm_hash=self._hash_algorithm(components, hyperparams)
            )
            
            self.population.append(algorithm)
        
        print(f"Initialized population of {len(self.population)} algorithms")
    
    def evolve_generation(self, fitness_scores: Dict[str, float]) -> List[AlgorithmSpec]:
        """Evolve population based on fitness scores."""
        self.generation += 1
        
        # Update fitness scores
        for algo in self.population:
            if algo.name in fitness_scores:
                algo.fitness_score = fitness_scores[algo.name]
        
        # Sort by fitness
        self.population.sort(key=lambda x: x.fitness_score, reverse=True)
        
        # Select elites (top 20%)
        elite_size = max(1, int(len(self.population) * 0.2))
        elites = self.population[:elite_size]
        
        # Create new population through crossover and mutation
        new_population = elites.copy()
        
        while len(new_population) < self.population_size:
            # Tournament selection
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()
            
            # Crossover
            child = self._crossover(parent1, parent2)
            
            # Mutation
            child = self._mutate(child)
            
            # Update child metadata
            child.name = f"Algorithm_{self.generation}_{len(new_population)}"
            child.generation = self.generation
            child.algorithm_hash = self._hash_algorithm(child.components, child.hyperparameters)
            
            new_population.append(child)
        
        # Update population and history
        self.algorithm_history.extend(elites)
        self.population = new_population
        
        print(f"Generation {self.generation}: Best fitness = {elites[0].fitness_score:.4f}")
        
        return elites
    
    def generate_algorithm(self, 
                          problem_type: str,
                          constraints: Dict[str, Any]) -> Tuple[Callable, AlgorithmSpec]:
        """Generate a specific algorithm for a problem type."""
        
        # Problem-specific component selection
        base_components = self._select_components_for_problem(problem_type)
        
        # Add random exploration components
        exploration_components = random.sample(self.component_pool, 2)
        components = list(set(base_components + exploration_components))
        
        # Optimize hyperparameters for problem
        hyperparams = self._optimize_hyperparams(components, problem_type, constraints)
        
        # Create algorithm spec
        algorithm_spec = AlgorithmSpec(
            name=f"{problem_type}_Algorithm_{hashlib.md5(str(components).encode()).hexdigest()[:8]}",
            components=components,
            hyperparameters=hyperparams,
            generation=self.generation,
            algorithm_hash=self._hash_algorithm(components, hyperparams)
        )
        
        # Create executable function
        algorithm_func = self._compile_algorithm(algorithm_spec)
        
        return algorithm_func, algorithm_spec
    
    def analyze_algorithm_space(self) -> Dict[str, Any]:
        """Analyze the discovered algorithm space."""
        
        if not self.algorithm_history:
            return {}
        
        # Calculate statistics
        best_algorithm = max(self.algorithm_history, key=lambda x: x.fitness_score)
        worst_algorithm = min(self.algorithm_history, key=lambda x: x.fitness_score)
        
        # Component frequency analysis
        component_counts = {}
        for algo in self.algorithm_history:
            for component in algo.components:
                component_counts[component.value] = component_counts.get(component.value, 0) + 1
        
        # Diversity metrics
        unique_hashes = len(set(algo.algorithm_hash for algo in self.algorithm_history))
        diversity_score = unique_hashes / len(self.algorithm_history)
        
        return {
            "total_algorithms_generated": len(self.algorithm_history),
            "best_fitness": best_algorithm.fitness_score,
            "worst_fitness": worst_algorithm.fitness_score,
            "component_frequencies": component_counts,
            "diversity_score": diversity_score,
            "generations_completed": self.generation,
            "average_complexity": np.mean([len(a.components) for a in self.algorithm_history])
        }
    
    def export_algorithms(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Export top algorithms for analysis."""
        sorted_algorithms = sorted(self.algorithm_history, 
                                 key=lambda x: x.fitness_score, 
                                 reverse=True)
        
        exported = []
        for algo in sorted_algorithms[:limit]:
            exported.append({
                "name": algo.name,
                "components": [c.value for c in algo.components],
                "hyperparameters": algo.hyperparameters,
                "fitness_score": algo.fitness_score,
                "generation": algo.generation,
                "hash": algo.algorithm_hash
            })
        
        return exported
    
    # Private helper methods
    
    def _hash_algorithm(self, components: List[AlgorithmComponent], 
                        hyperparams: Dict[str, Any]) -> str:
        """Create hash for algorithm uniqueness."""
        components_str = ",".join(sorted(c.value for c in components))
        hyperparams_str = json.dumps(hyperparams, sort_keys=True)
        combined = f"{components_str}|{hyperparams_str}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]
    
    def _generate_random_hyperparams(self, components: List[AlgorithmComponent]) -> Dict[str, Any]:
        """Generate random hyperparameters for given components."""
        hyperparams = {}
        
        # Base hyperparameters
        hyperparams["learning_rate"] = random.uniform(0.0001, 0.1)
        hyperparams["batch_size"] = random.choice([16, 32, 64, 128, 256])
        hyperparams["epochs"] = random.randint(10, 100)
        
        # Component-specific hyperparameters
        for component in components:
            if component == AlgorithmComponent.ADAM:
                hyperparams["beta1"] = random.uniform(0.8, 0.99)
                hyperparams["beta2"] = random.uniform(0.9, 0.999)
                hyperparams["epsilon"] = random.uniform(1e-8, 1e-6)
            elif component == AlgorithmComponent.L1_REGULARIZATION:
                hyperparams["l1_lambda"] = random.uniform(0.0001, 0.01)
            elif component == AlgorithmComponent.L2_REGULARIZATION:
                hyperparams["l2_lambda"] = random.uniform(0.0001, 0.01)
            elif component == AlgorithmComponent.DROPOUT:
                hyperparams["dropout_rate"] = random.uniform(0.1, 0.5)
            elif component == AlgorithmComponent.EXPONENTIAL_DECAY:
                hyperparams["decay_rate"] = random.uniform(0.9, 0.999)
                hyperparams["decay_steps"] = random.randint(100, 1000)
        
        return hyperparams
    
    def _tournament_selection(self) -> AlgorithmSpec:
        """Select parent using tournament selection."""
        tournament_size = 3
        tournament = random.sample(self.population, tournament_size)
        return max(tournament, key=lambda x: x.fitness_score)
    
    def _crossover(self, parent1: AlgorithmSpec, parent2: AlgorithmSpec) -> AlgorithmSpec:
        """Crossover two algorithms to create child."""
        
        # Uniform crossover for components
        child_components = []
        max_components = max(len(parent1.components), len(parent2.components))
        
        for i in range(max_components):
            if i < len(parent1.components) and i < len(parent2.components):
                # Choose from either parent
                if random.random() < 0.5:
                    child_components.append(parent1.components[i])
                else:
                    child_components.append(parent2.components[i])
            elif i < len(parent1.components):
                child_components.append(parent1.components[i])
            else:
                child_components.append(parent2.components[i])
        
        # Remove duplicates
        child_components = list(set(child_components))
        
        # Crossover hyperparameters (averaging)
        child_hyperparams = {}
        all_keys = set(parent1.hyperparameters.keys()) | set(parent2.hyperparameters.keys())
        
        for key in all_keys:
            if key in parent1.hyperparameters and key in parent2.hyperparameters:
                # Average numeric values
                if isinstance(parent1.hyperparameters[key], (int, float)) and \
                   isinstance(parent2.hyperparameters[key], (int, float)):
                    child_hyperparams[key] = (parent1.hyperparameters[key] + 
                                             parent2.hyperparameters[key]) / 2
                else:
                    # Choose randomly
                    child_hyperparams[key] = random.choice([
                        parent1.hyperparameters[key], 
                        parent2.hyperparameters[key]
                    ])
            elif key in parent1.hyperparameters:
                child_hyperparams[key] = parent1.hyperparameters[key]
            else:
                child_hyperparams[key] = parent2.hyperparameters[key]
        
        return AlgorithmSpec(
            name="",  # Will be set later
            components=child_components,
            hyperparameters=child_hyperparams,
            fitness_score=0.0
        )
    
    def _mutate(self, algorithm: AlgorithmSpec) -> AlgorithmSpec:
        """Mutate an algorithm."""
        mutated = AlgorithmSpec(
            name=algorithm.name,
            components=algorithm.components.copy(),
            hyperparameters=algorithm.hyperparameters.copy(),
            fitness_score=algorithm.fitness_score,
            generation=algorithm.generation
        )
        
        if random.random() < self.mutation_rate:
            # Add random component
            if random.random() < 0.3:
                new_component = random.choice(self.component_pool)
                if new_component not in mutated.components:
                    mutated.components.append(new_component)
            
            # Remove random component (if more than 2)
            if len(mutated.components) > 2 and random.random() < 0.2:
                mutated.components.pop(random.randrange(len(mutated.components)))
            
            # Mutate hyperparameters
            for key in mutated.hyperparameters:
                if isinstance(mutated.hyperparameters[key], (int, float)):
                    if random.random() < 0.1:
                        # Small random change
                        if random.random() < 0.5:
                            mutated.hyperparameters[key] *= random.uniform(0.9, 1.1)
                        else:
                            mutated.hyperparameters[key] += random.uniform(-0.1, 0.1)
        
        return mutated
    
    def _select_components_for_problem(self, problem_type: str) -> List[AlgorithmComponent]:
        """Select appropriate components for problem type."""
        base_components = []
        
        if problem_type in ["classification", "regression"]:
            base_components = [
                AlgorithmComponent.ADAM,
                AlgorithmComponent.L2_REGULARIZATION,
                AlgorithmComponent.EXPONENTIAL_DECAY
            ]
        elif problem_type in ["reinforcement_learning", "rl"]:
            base_components = [
                AlgorithmComponent.RMSROP,
                AlgorithmComponent.MOMENTUM,
                AlgorithmComponent.EXPONENTIAL_DECAY
            ]
        elif problem_type in ["generative", "gan"]:
            base_components = [
                AlgorithmComponent.ADAM,
                AlgorithmComponent.BATCH_NORM,
                AlgorithmComponent.COSINE_DECAY
            ]
        else:
            # Default components
            base_components = [
                AlgorithmComponent.ADAM,
                AlgorithmComponent.L2_REGULARIZATION
            ]
        
        return base_components
    
    def _optimize_hyperparams(self, 
                             components: List[AlgorithmComponent],
                             problem_type: str,
                             constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize hyperparameters using Bayesian optimization."""
        
        def objective(trial: optuna.Trial) -> float:
            # Suggest hyperparameter values
            hyperparams = {
                "learning_rate": trial.suggest_float("learning_rate", 1e-5, 1e-1, log=True),
                "batch_size": trial.suggest_categorical("batch_size", [16, 32, 64, 128, 256]),
            }
            
            # Component-specific hyperparameters
            for component in components:
                if component == AlgorithmComponent.ADAM:
                    hyperparams["beta1"] = trial.suggest_float("beta1", 0.8, 0.99)
                    hyperparams["beta2"] = trial.suggest_float("beta2", 0.9, 0.999)
                    hyperparams["epsilon"] = trial.suggest_float("epsilon", 1e-8, 1e-6, log=True)
                elif component == AlgorithmComponent.L1_REGULARIZATION:
                    hyperparams["l1_lambda"] = trial.suggest_float("l1_lambda", 1e-5, 1e-2, log=True)
                elif component == AlgorithmComponent.L2_REGULARIZATION:
                    hyperparams["l2_lambda"] = trial.suggest_float("l2_lambda", 1e-5, 1e-2, log=True)
                elif component == AlgorithmComponent.DROPOUT:
                    hyperparams["dropout_rate"] = trial.suggest_float("dropout_rate", 0.1, 0.5)
            
            # Simple fitness estimation based on problem type
            # In real implementation, this would train and evaluate a model
            fitness = random.random()  # Placeholder
            
            return fitness
        
        # Run optimization
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=20)
        
        # Get best hyperparameters
        best_params = study.best_params
        
        return best_params
    
    def _compile_algorithm(self, algorithm_spec: AlgorithmSpec) -> Callable:
        """Compile algorithm spec into executable function."""
        
        def algorithm_implementation(model_params, gradients, step):
            """Generated algorithm implementation."""
            # This is a simplified implementation
            # Real implementation would apply all components
            
            lr = algorithm_spec.hyperparameters.get("learning_rate", 0.001)
            
            # Apply components
            for component in algorithm_spec.components:
                if component == AlgorithmComponent.ADAM:
                    # Simplified Adam implementation
                    beta1 = algorithm_spec.hyperparameters.get("beta1", 0.9)
                    beta2 = algorithm_spec.hyperparameters.get("beta2", 0.999)
                    epsilon = algorithm_spec.hyperparameters.get("epsilon", 1e-8)
                    
                    # Adam update would go here
                    pass
                elif component == AlgorithmComponent.L2_REGULARIZATION:
                    l2_lambda = algorithm_spec.hyperparameters.get("l2_lambda", 0.0001)
                    # L2 regularization would go here
                    pass
            
            # Simple gradient descent update
            updated_params = {}
            for key in model_params:
                if key in gradients:
                    updated_params[key] = model_params[key] - lr * gradients[key]
                else:
                    updated_params[key] = model_params[key]
            
            return updated_params
        
        return algorithm_implementation