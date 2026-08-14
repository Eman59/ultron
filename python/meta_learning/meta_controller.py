"""
Meta-Controller - The brain that orchestrates the entire meta-learning system.

The MetaController coordinates the AlgorithmGenerator, StrategyOptimizer,
CurriculumDesigner, and TransferManager to create a system that autonomously
learns how to learn better over time.
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time
import json
import hashlib

from .algorithm_generator import AlgorithmGenerator, AlgorithmSpec
from .strategy_optimizer import StrategyOptimizer, StrategySpec, StrategyType
from .curriculum_designer import CurriculumDesigner, CurriculumTask, DifficultyLevel
from .transfer_manager import TransferManager, TransferMethod


class SystemMode(Enum):
    """Operating modes for the meta-learning system."""
    EXPLORATION = "exploration"      # Discovering new algorithms and strategies
    EXPLOITATION = "exploitation"    # Using best known approaches
    ADAPTATION = "adaptation"        # Adapting to new domains/tasks
    EVALUATION = "evaluation"        # Evaluating and benchmarking
    HIBERNATION = "hibernation"      # Low resource mode
    EVOLUTION = "evolution"          # Evolving the system itself


class LearningPhase(Enum):
    """Current phase of the learning process."""
    INITIALIZATION = "initialization"
    WARM_UP = "warm_up"
    ACTIVE_LEARNING = "active_learning"
    CONSOLIDATION = "consolidation"
    TRANSFER = "transfer"
    META_OPTIMIZATION = "meta_optimization"


@dataclass
class SystemState:
    """Complete state of the meta-learning system."""
    mode: SystemMode = SystemMode.EXPLORATION
    phase: LearningPhase = LearningPhase.INITIALIZATION
    generation: int = 0
    total_tasks_processed: int = 0
    total_algorithms_generated: int = 0
    total_transfers_performed: int = 0
    current_best_performance: float = 0.0
    improvement_rate: float = 0.0
    resource_usage: float = 0.0  # 0-1
    uptime: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class MetaDecision:
    """A decision made by the meta-controller."""
    decision_id: str
    decision_type: str  # "algorithm_selection", "strategy_switch", "transfer", "evolve"
    reasoning: str
    confidence: float
    expected_improvement: float
    actions: List[Dict[str, Any]] = field(default_factory=list)
    outcome: Optional[float] = None


class MetaController:
    """Orchestrates the meta-learning system - the 'brain' of Ultron's learning."""

    def __init__(self,
                 population_size: int = 50,
                 exploration_budget: float = 0.3,
                 adaptation_threshold: float = 0.1,
                 evolution_interval: int = 100):
        
        # Core components
        self.algorithm_generator = AlgorithmGenerator(population_size=population_size)
        self.strategy_optimizer = StrategyOptimizer(exploration_weight=exploration_budget)
        self.curriculum_designer = CurriculumDesigner()
        self.transfer_manager = TransferManager()
        
        # Configuration
        self.exploration_budget = exploration_budget
        self.adaptation_threshold = adaptation_threshold
        self.evolution_interval = evolution_interval
        
        # State
        self.state = SystemState()
        self.decision_history: List[MetaDecision] = []
        self.performance_log: List[Tuple[float, float]] = []  # (time, performance)
        
        # Meta-parameters (the system learns these too)
        self.meta_params = {
            "exploration_rate": exploration_budget,
            "learning_rate_multiplier": 1.0,
            "transfer_aggressiveness": 0.5,
            "evolution_pressure": 0.3,
            "curriculum_strictness": 0.7,
            "novelty_weight": 0.2,
        }
        
        # Internal clock
        self._step = 0
        self._start_time = time.time()

    def initialize(self, 
                   initial_tasks: List[Dict[str, Any]] = None,
                   initial_domains: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Initialize the meta-learning system."""
        
        print("=" * 60)
        print("  ULTRON META-LEARNING SYSTEM - INITIALIZATION")
        print("=" * 60)
        
        # Initialize algorithm population
        self.algorithm_generator.initialize_population()
        
        # Register initial domains
        if initial_domains:
            for domain in initial_domains:
                self.transfer_manager.register_domain(**domain)
        
        # Create initial curriculum
        if initial_tasks:
            for task_spec in initial_tasks:
                self.curriculum_designer.create_task(**task_spec)
        
        # Set initial state
        self.state.mode = SystemMode.EXPLORATION
        self.state.phase = LearningPhase.WARM_UP
        
        print(f"  Population size: {len(self.algorithm_generator.population)}")
        print(f"  Registered domains: {len(self.transfer_manager.domains)}")
        print(f"  Curriculum tasks: {len(self.curriculum_designer.task_library)}")
        print(f"  Mode: {self.state.mode.value}")
        print("=" * 60)
        
        return {
            "status": "initialized",
            "population_size": len(self.algorithm_generator.population),
            "domains": len(self.transfer_manager.domains),
            "tasks": len(self.curriculum_designer.task_library),
            "mode": self.state.mode.value
        }

    def step(self, 
             observation: Dict[str, Any] = None,
             reward: float = None) -> MetaDecision:
        """Execute one step of the meta-learning loop."""
        
        self._step += 1
        observation = observation or {}
        
        # 1. Observe current state
        current_performance = reward if reward is not None else self._estimate_performance()
        self.performance_log.append((self._step, current_performance))
        
        # 2. Analyze situation
        analysis = self._analyze_situation(observation, current_performance)
        
        # 3. Make meta-decision
        decision = self._make_decision(analysis)
        
        # 4. Execute decision
        self._execute_decision(decision)
        
        # 5. Update state
        self._update_state(current_performance)
        
        # 6. Check if evolution is needed
        if self._step % self.evolution_interval == 0:
            self._evolve_system()
        
        # Record decision
        self.decision_history.append(decision)
        
        return decision

    def process_task(self,
                    task_type: str,
                    task_data: Dict[str, Any],
                    constraints: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a learning task through the meta-learning system."""
        
        constraints = constraints or {}
        
        print(f"\n--- Processing Task: {task_type} ---")
        
        # 1. Select or generate algorithm
        algorithm_func, algorithm_spec = self._select_algorithm(task_type, constraints)
        
        # 2. Get learning strategy
        strategy = self._get_strategy(task_type, constraints)
        
        # 3. Check for transfer opportunities
        transfer_result = self._check_transfer_opportunities(task_type, task_data)
        
        # 4. Execute learning
        result = self._execute_learning(
            algorithm_func=algorithm_func,
            algorithm_spec=algorithm_spec,
            strategy=strategy,
            task_data=task_data,
            transfer_boost=transfer_result
        )
        
        # 5. Store learned knowledge
        self._store_learned_knowledge(task_type, result)
        
        # 6. Update system
        self.state.total_tasks_processed += 1
        self.state.current_best_performance = max(
            self.state.current_best_performance, result.get("performance", 0.0)
        )
        
        print(f"  Performance: {result.get('performance', 0.0):.4f}")
        print(f"  Algorithm: {algorithm_spec.name}")
        print(f"  Strategy: {strategy.name if strategy else 'None'}")
        
        return result

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        
        uptime = time.time() - self._start_time
        
        return {
            "system_state": {
                "mode": self.state.mode.value,
                "phase": self.state.phase.value,
                "generation": self.state.generation,
                "step": self._step,
                "uptime_seconds": uptime,
            },
            "performance": {
                "current_best": self.state.current_best_performance,
                "improvement_rate": self.state.improvement_rate,
                "total_tasks": self.state.total_tasks_processed,
                "total_algorithms": self.state.total_algorithms_generated,
                "total_transfers": self.state.total_transfers_performed,
            },
            "meta_parameters": self.meta_params,
            "component_status": {
                "algorithm_generator": {
                    "population_size": len(self.algorithm_generator.population),
                    "generations": self.algorithm_generator.generation,
                },
                "strategy_optimizer": {
                    "strategies_evaluated": len(self.strategy_optimizer.strategy_history),
                    "best_performance": self.strategy_optimizer.best_performance,
                },
                "curriculum_designer": {
                    "tasks": len(self.curriculum_designer.task_library),
                    "learners": len(self.curriculum_designer.learner_profiles),
                },
                "transfer_manager": {
                    "knowledge_units": len(self.transfer_manager.knowledge_store),
                    "domains": len(self.transfer_manager.domains),
                    "transfers": len(self.transfer_manager.transfer_history),
                },
            },
            "decisions_made": len(self.decision_history),
            "errors": self.state.errors[-5:],  # Last 5 errors
        }

    def adapt_to_new_domain(self, 
                           domain_spec: Dict[str, Any],
                           sample_tasks: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Adapt the system to a completely new domain."""
        
        print(f"\n{'='*60}")
        print(f"  ADAPTING TO NEW DOMAIN: {domain_spec.get('name', 'unknown')}")
        print(f"{'='*60}")
        
        # 1. Register domain
        domain = self.transfer_manager.register_domain(**domain_spec)
        
        # 2. Find transfer sources
        sources = self.transfer_manager.suggest_transfer_sources(
            domain_spec["domain_id"], 
            domain_spec.get("task_type", "unknown")
        )
        
        # 3. Perform transfer from best source
        transfer_result = None
        if sources:
            best_source = sources[0]
            print(f"  Best transfer source: {best_source['domain_name']} "
                  f"(score: {best_source['overall_score']:.3f})")
            
            transfer_result = self.transfer_manager.transfer_knowledge(
                source_domain=best_source["source_domain"],
                target_domain=domain_spec["domain_id"],
                target_task=domain_spec.get("task_type", "unknown")
            )
            
            self.state.total_transfers_performed += 1
        
        # 4. Generate domain-specific algorithms
        algo_func, algo_spec = self.algorithm_generator.generate_algorithm(
            domain_spec.get("task_type", "classification"),
            {"domain": domain_spec["domain_id"]}
        )
        self.state.total_algorithms_generated += 1
        
        # 5. Design curriculum for new domain
        if sample_tasks:
            for task in sample_tasks:
                self.curriculum_designer.create_task(**task)
        
        # 6. Switch to adaptation mode
        self.state.mode = SystemMode.ADAPTATION
        self.state.phase = LearningPhase.TRANSFER
        
        return {
            "domain_registered": True,
            "transfer_performed": transfer_result is not None,
            "transfer_success": transfer_result.success if transfer_result else False,
            "algorithm_generated": algo_spec.name,
            "mode": self.state.mode.value,
            "transfer_sources": [s["domain_name"] for s in sources[:3]]
        }

    def evolve(self, fitness_evaluator=None) -> Dict[str, Any]:
        """Explicitly evolve the system (can be triggered externally)."""
        return self._evolve_system(fitness_evaluator)

    def export_state(self) -> Dict[str, Any]:
        """Export complete system state for persistence or analysis."""
        
        return {
            "version": "0.1.0",
            "state": {
                "mode": self.state.mode.value,
                "phase": self.state.phase.value,
                "generation": self.state.generation,
                "step": self._step,
                "performance": self.state.current_best_performance,
            },
            "meta_parameters": self.meta_params,
            "algorithm_space": self.algorithm_generator.analyze_algorithm_space(),
            "strategy_space": self.strategy_optimizer.analyze_strategy_space(),
            "transfer_stats": self.transfer_manager.get_transfer_statistics(),
            "decision_summary": self._summarize_decisions(),
            "performance_trajectory": self.performance_log[-100:],  # Last 100 points
        }

    # ──────────────────────────── Private Methods ────────────────────────────

    def _analyze_situation(self, 
                          observation: Dict[str, Any],
                          current_performance: float) -> Dict[str, Any]:
        """Analyze the current situation to inform decisions."""
        
        # Performance trend
        if len(self.performance_log) >= 10:
            recent = [p for _, p in self.performance_log[-10:]]
            trend = np.polyfit(range(len(recent)), recent, 1)[0]
        else:
            trend = 0.0
        
        # Plateau detection
        is_plateau = False
        if len(self.performance_log) >= 20:
            recent = [p for _, p in self.performance_log[-20:]]
            is_plateau = np.std(recent) < 0.01
        
        # Exploration vs exploitation balance
        exploration_ratio = self.meta_params["exploration_rate"]
        
        return {
            "current_performance": current_performance,
            "performance_trend": trend,
            "is_plateau": is_plateau,
            "exploration_ratio": exploration_ratio,
            "mode": self.state.mode.value,
            "phase": self.state.phase.value,
            "step": self._step,
            "observation": observation
        }

    def _make_decision(self, analysis: Dict[str, Any]) -> MetaDecision:
        """Make a meta-level decision about what to do next."""
        
        decision_id = hashlib.md5(f"decision_{self._step}".encode()).hexdigest()[:12]
        
        # Decision logic based on analysis
        if analysis["is_plateau"]:
            # Performance plateau - need to try something new
            if analysis["exploration_ratio"] < 0.5:
                return MetaDecision(
                    decision_id=decision_id,
                    decision_type="strategy_switch",
                    reasoning="Performance plateau detected. Increasing exploration.",
                    confidence=0.7,
                    expected_improvement=0.1,
                    actions=[
                        {"action": "increase_exploration", "amount": 0.1},
                        {"action": "generate_new_algorithms", "count": 10}
                    ]
                )
            else:
                return MetaDecision(
                    decision_id=decision_id,
                    decision_type="evolve",
                    reasoning="Plateau persists despite exploration. Triggering evolution.",
                    confidence=0.6,
                    expected_improvement=0.15,
                    actions=[
                        {"action": "evolve_population"},
                        {"action": "reset_exploration"}
                    ]
                )
        
        elif analysis["performance_trend"] < -0.01:
            # Performance declining
            return MetaDecision(
                decision_id=decision_id,
                decision_type="adaptation",
                reasoning="Performance declining. Adapting strategy.",
                confidence=0.8,
                expected_improvement=0.05,
                actions=[
                    {"action": "adapt_strategy"},
                    {"action": "check_transfer_opportunities"}
                ]
            )
        
        elif analysis["performance_trend"] > 0.05:
            # Good progress - exploit
            return MetaDecision(
                decision_id=decision_id,
                decision_type="exploitation",
                reasoning="Strong positive trend. Exploiting current approach.",
                confidence=0.85,
                expected_improvement=analysis["performance_trend"],
                actions=[
                    {"action": "continue_current_approach"},
                    {"action": "reduce_exploration", "amount": 0.05}
                ]
            )
        
        else:
            # Neutral - balanced approach
            return MetaDecision(
                decision_id=decision_id,
                decision_type="balanced",
                reasoning="Moderate progress. Maintaining balanced approach.",
                confidence=0.6,
                expected_improvement=0.02,
                actions=[
                    {"action": "maintain_balance"}
                ]
            )

    def _execute_decision(self, decision: MetaDecision) -> None:
        """Execute a meta-decision."""
        
        for action in decision.actions:
            action_type = action.get("action", "")
            
            if action_type == "increase_exploration":
                amount = action.get("amount", 0.1)
                self.meta_params["exploration_rate"] = min(
                    0.8, self.meta_params["exploration_rate"] + amount
                )
                
            elif action_type == "reduce_exploration":
                amount = action.get("amount", 0.05)
                self.meta_params["exploration_rate"] = max(
                    0.05, self.meta_params["exploration_rate"] - amount
                )
                
            elif action_type == "generate_new_algorithms":
                count = action.get("count", 10)
                # Would generate new algorithms here
                self.state.total_algorithms_generated += count
                
            elif action_type == "evolve_population":
                self._evolve_system()
                
            elif action_type == "adapt_strategy":
                # Trigger strategy adaptation
                self.state.mode = SystemMode.ADAPTATION
                
            elif action_type == "check_transfer_opportunities":
                self.state.phase = LearningPhase.TRANSFER

    def _update_state(self, current_performance: float) -> None:
        """Update system state after a step."""
        
        # Update improvement rate
        if len(self.performance_log) >= 2:
            prev_perf = self.performance_log[-2][1]
            self.state.improvement_rate = current_performance - prev_perf
        
        # Phase transitions
        if self._step < 10:
            self.state.phase = LearningPhase.WARM_UP
        elif self.state.mode == SystemMode.ADAPTATION:
            self.state.phase = LearningPhase.TRANSFER
        elif self.state.improvement_rate > 0.01:
            self.state.phase = LearningPhase.ACTIVE_LEARNING
        elif self.state.improvement_rate < -0.01:
            self.state.phase = LearningPhase.META_OPTIMIZATION
        else:
            self.state.phase = LearningPhase.CONSOLIDATION

    def _evolve_system(self, fitness_evaluator=None) -> Dict[str, Any]:
        """Evolve the entire system."""
        
        self.state.generation += 1
        self.state.mode = SystemMode.EVOLUTION
        
        print(f"\n  [EVOLUTION] Generation {self.state.generation}")
        
        # 1. Evolve algorithm population
        fitness_scores = {}
        for algo in self.algorithm_generator.population:
            # Use historical performance or evaluate
            fitness_scores[algo.name] = algo.fitness_score or np.random.random()
        
        elites = self.algorithm_generator.evolve_generation(fitness_scores)
        
        # 2. Evolve meta-parameters
        self._evolve_meta_parameters()
        
        # 3. Return to appropriate mode
        self.state.mode = SystemMode.EXPLORATION
        
        return {
            "generation": self.state.generation,
            "elite_count": len(elites),
            "best_fitness": elites[0].fitness_score if elites else 0.0,
            "meta_params_updated": True
        }

    def _evolve_meta_parameters(self) -> None:
        """Evolve the meta-parameters themselves."""
        
        # Analyze what's working
        if len(self.decision_history) < 10:
            return
        
        # Look at recent decisions and their outcomes
        recent_decisions = self.decision_history[-20:]
        
        # Adjust exploration based on decision success
        successful_explorations = sum(
            1 for d in recent_decisions 
            if d.decision_type == "strategy_switch" and (d.outcome or 0) > 0
        )
        
        total_explorations = sum(
            1 for d in recent_decisions 
            if d.decision_type == "strategy_switch"
        )
        
        if total_explorations > 0:
            exploration_success_rate = successful_explorations / total_explorations
            # Adjust exploration rate based on success
            if exploration_success_rate > 0.5:
                self.meta_params["exploration_rate"] = min(
                    0.5, self.meta_params["exploration_rate"] * 1.1
                )
            else:
                self.meta_params["exploration_rate"] = max(
                    0.1, self.meta_params["exploration_rate"] * 0.9
                )
        
        # Small random perturbations to other meta-params
        for key in ["learning_rate_multiplier", "transfer_aggressiveness", 
                    "evolution_pressure", "novelty_weight"]:
            self.meta_params[key] *= np.random.uniform(0.95, 1.05)
            self.meta_params[key] = max(0.01, min(2.0, self.meta_params[key]))

    def _select_algorithm(self, 
                         task_type: str,
                         constraints: Dict[str, Any]) -> Tuple:
        """Select or generate an algorithm for a task."""
        
        # Check if we have a good algorithm already
        if self.algorithm_generator.population:
            best = max(self.algorithm_generator.population, 
                      key=lambda a: a.fitness_score)
            if best.fitness_score > 0.7:
                # Use existing good algorithm
                func = self.algorithm_generator._compile_algorithm(best)
                return func, best
        
        # Generate new algorithm
        func, spec = self.algorithm_generator.generate_algorithm(task_type, constraints)
        self.state.total_algorithms_generated += 1
        return func, spec

    def _get_strategy(self, 
                     task_type: str,
                     constraints: Dict[str, Any]) -> Optional[StrategySpec]:
        """Get the best learning strategy for a task."""
        
        # Map task type to strategy type
        strategy_map = {
            "classification": StrategyType.ADAPTIVE_LEARNING,
            "regression": StrategyType.ADAPTIVE_LEARNING,
            "reinforcement_learning": StrategyType.EXPLORATION_EXPLOITATION,
            "transfer": StrategyType.TRANSFER_LEARNING,
            "curriculum": StrategyType.CURRICULUM_LEARNING,
            "multi_task": StrategyType.MULTI_TASK_LEARNING,
        }
        
        strategy_type = strategy_map.get(task_type, StrategyType.ADAPTIVE_LEARNING)
        
        # Use current best strategy if available
        if self.strategy_optimizer.best_strategy:
            return self.strategy_optimizer.best_strategy
        
        # Optimize a new strategy (with limited trials for speed)
        context = {
            "problem_type": task_type,
            "strategy_type": strategy_type.value,
            "difficulty": constraints.get("difficulty", 0.5)
        }
        
        try:
            strategy = self.strategy_optimizer.optimize_strategy(context, n_trials=10)
            return strategy
        except Exception as e:
            self.state.errors.append(f"Strategy optimization failed: {str(e)}")
            return None

    def _check_transfer_opportunities(self,
                                     task_type: str,
                                     task_data: Dict[str, Any]) -> Optional[Dict]:
        """Check if we can transfer knowledge from previous tasks."""
        
        target_domain = task_data.get("domain", "default")
        
        if target_domain in self.transfer_manager.domains:
            sources = self.transfer_manager.suggest_transfer_sources(
                target_domain, task_type, top_k=3
            )
            
            if sources and sources[0]["overall_score"] > 0.4:
                # Perform transfer
                result = self.transfer_manager.transfer_knowledge(
                    source_domain=sources[0]["source_domain"],
                    target_domain=target_domain,
                    target_task=task_type
                )
                
                if result.success:
                    self.state.total_transfers_performed += 1
                    return {
                        "source": sources[0]["source_domain"],
                        "efficiency": result.transfer_efficiency,
                        "boost": result.transfer_efficiency * 0.2
                    }
        
        return None

    def _execute_learning(self,
                         algorithm_func,
                         algorithm_spec: AlgorithmSpec,
                         strategy: Optional[StrategySpec],
                         task_data: Dict[str, Any],
                         transfer_boost: Optional[Dict]) -> Dict[str, Any]:
        """Execute the learning process."""
        
        # Simulate learning (in real implementation, this trains a model)
        base_performance = 0.5
        
        # Algorithm contribution
        algo_contribution = algorithm_spec.fitness_score * 0.2
        
        # Strategy contribution
        strategy_contribution = 0.0
        if strategy and strategy.performance_history:
            strategy_contribution = max(strategy.performance_history) * 0.15
        
        # Transfer boost
        transfer_contribution = 0.0
        if transfer_boost:
            transfer_contribution = transfer_boost.get("boost", 0.0)
        
        # Meta-parameter influence
        meta_influence = self.meta_params["learning_rate_multiplier"] * 0.05
        
        # Final performance
        performance = (base_performance + algo_contribution + 
                      strategy_contribution + transfer_contribution + 
                      meta_influence + np.random.normal(0, 0.05))
        performance = max(0.0, min(1.0, performance))
        
        return {
            "performance": performance,
            "algorithm_used": algorithm_spec.name,
            "strategy_used": strategy.name if strategy else None,
            "transfer_used": transfer_boost is not None,
            "contributions": {
                "base": base_performance,
                "algorithm": algo_contribution,
                "strategy": strategy_contribution,
                "transfer": transfer_contribution,
                "meta": meta_influence
            }
        }

    def _store_learned_knowledge(self, task_type: str, result: Dict[str, Any]) -> None:
        """Store knowledge from completed task."""
        
        if result.get("performance", 0.0) > 0.6:
            # Good performance - worth storing
            knowledge_repr = np.random.randn(64)  # Simulated knowledge embedding
            
            self.transfer_manager.store_knowledge(
                source_domain=task_type,
                source_task=task_type,
                knowledge_type="learned_features",
                representation=knowledge_repr,
                metadata={
                    "performance": result["performance"],
                    "algorithm": result.get("algorithm_used"),
                    "task_type": task_type
                }
            )

    def _estimate_performance(self) -> float:
        """Estimate current performance when no explicit reward is given."""
        if self.performance_log:
            return self.performance_log[-1][1]
        return 0.5

    def _summarize_decisions(self) -> Dict[str, Any]:
        """Summarize decision history."""
        if not self.decision_history:
            return {}
        
        type_counts = {}
        for d in self.decision_history:
            type_counts[d.decision_type] = type_counts.get(d.decision_type, 0) + 1
        
        avg_confidence = np.mean([d.confidence for d in self.decision_history])
        
        return {
            "total_decisions": len(self.decision_history),
            "decision_types": type_counts,
            "average_confidence": avg_confidence,
            "last_decision": self.decision_history[-1].decision_type
        }


# ━━━━━━━━━━━━━━━━━━━━━━━ Entry Point ━━━━━━━━━━━━━━━━━━━━━━━

def create_ultron_meta_learner(config: Dict[str, Any] = None) -> MetaController:
    """Factory function to create a configured MetaController instance."""
    
    config = config or {}
    
    controller = MetaController(
        population_size=config.get("population_size", 50),
        exploration_budget=config.get("exploration_budget", 0.3),
        adaptation_threshold=config.get("adaptation_threshold", 0.1),
        evolution_interval=config.get("evolution_interval", 100)
    )
    
    # Default initialization
    default_domains = [
        {
            "domain_id": "vision",
            "name": "Computer Vision",
            "feature_dimensions": 2048,
            "task_type": "classification",
            "complexity": 0.7
        },
        {
            "domain_id": "nlp",
            "name": "Natural Language Processing",
            "feature_dimensions": 768,
            "task_type": "classification",
            "complexity": 0.8
        },
        {
            "domain_id": "rl",
            "name": "Reinforcement Learning",
            "feature_dimensions": 256,
            "task_type": "reinforcement_learning",
            "complexity": 0.9
        },
    ]
    
    default_tasks = [
        {
            "task_id": "basic_classification",
            "name": "Basic Classification",
            "difficulty": DifficultyLevel.EASY,
            "skills_taught": ["classification", "data_handling"],
        },
        {
            "task_id": "advanced_optimization",
            "name": "Advanced Optimization",
            "difficulty": DifficultyLevel.HARD,
            "prerequisites": ["basic_classification"],
            "skills_taught": ["optimization", "hyperparameter_tuning"],
        },
        {
            "task_id": "transfer_learning",
            "name": "Transfer Learning",
            "difficulty": DifficultyLevel.EXPERT,
            "prerequisites": ["advanced_optimization"],
            "skills_taught": ["transfer", "domain_adaptation"],
        },
    ]
    
    controller.initialize(
        initial_tasks=default_tasks,
        initial_domains=default_domains
    )
    
    return controller
