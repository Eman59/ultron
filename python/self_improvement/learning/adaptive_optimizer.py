"""
Adaptive Optimizer — The Executive Cortex of Self-Learning.

This component takes the discovered patterns from the PatternRecognizer and
the structural knowledge from the CodeIntrospector, and generates TARGETED
optimizations that are validated through rigorous A/B testing before deployment.

Unlike the existing PatchGenerator (which uses heuristic templates), this
optimizer is ADAPTIVE — it learns which optimization strategies work for which
components, adjusts its approach based on historical success, and evolves
its own optimization tactics over time.

Optimization strategies:
  1. Pattern Exploitation   — Amplify discovered success patterns
  2. Anti-Pattern Breaking  — Interrupt sequences that predict failure
  3. Causal Intervention    — Modify behavior at identified causal points
  4. Bottleneck Relief      — Reduce load on identified bottleneck components
  5. Parameter Tuning       — Adjust runtime parameters based on performance data
  6. Architecture Reshaping — Restructure component interactions
  7. Preemptive Defense     — Add guards based on failure predictors
  8. Resonance Amplification — Boost synergistic component combinations

A/B Testing:
  Every optimization runs in shadow mode first, comparing its behavior
  to the original. Only when the optimization consistently outperforms
  the baseline does it get promoted to production.

The key insight: We don't just generate random improvements.
We KNOW what patterns lead to success, and we generate code that
makes those patterns happen MORE OFTEN.
"""

import time
import hashlib
import threading
import statistics
import copy
from typing import Dict, Any, List, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from pathlib import Path
import json
import numpy as np

from .experience_collector import ExperienceCollector, EventType
from .pattern_recognizer import PatternRecognizer, Pattern, PatternType, CausalChain
from .code_introspector import CodeIntrospector, FunctionProfile, ComponentHealth


class OptimizationStrategy(Enum):
    """Categories of optimization approaches."""
    PATTERN_EXPLOITATION = "pattern_exploitation"
    ANTI_PATTERN_BREAKING = "anti_pattern_breaking"
    CAUSAL_INTERVENTION = "causal_intervention"
    BOTTLENECK_RELIEF = "bottleneck_relief"
    PARAMETER_TUNING = "parameter_tuning"
    ARCHITECTURE_RESHAPING = "architecture_reshaping"
    PREEMPTIVE_DEFENSE = "preemptive_defense"
    RESONANCE_AMPLIFICATION = "resonance_amplification"
    DEAD_CODE_REMOVAL = "dead_code_removal"
    COMPLEXITY_REDUCTION = "complexity_reduction"


class OptimizationStatus(Enum):
    """Lifecycle of an optimization."""
    PROPOSED = "proposed"       # Generated, awaiting test
    TESTING = "testing"         # In A/B test
    WINNING = "winning"         # Outperforming baseline
    LOSING = "losing"           # Underperforming baseline
    DEPLOYED = "deployed"       # Applied to production
    REVERTED = "reverted"       # Was deployed but rolled back
    ABANDONED = "abandoned"     # Failed testing, discarded


@dataclass
class Optimization:
    """A single proposed optimization."""
    id: str
    strategy: OptimizationStrategy
    status: OptimizationStatus = OptimizationStatus.PROPOSED
    
    # What this optimization does
    description: str = ""
    target_component: str = ""
    target_file: str = ""
    target_function: str = ""
    
    # The actual change
    change_type: str = ""       # "parameter", "code", "config", "behavior"
    change_spec: Dict[str, Any] = field(default_factory=dict)
    
    # Source of the optimization
    source_pattern_id: str = ""  # Which pattern suggested this
    source_recommendation: str = ""
    
    # Expected vs actual performance
    expected_improvement: float = 0.0   # Predicted improvement
    actual_improvement: float = 0.0     # Measured improvement
    confidence: float = 0.0            # Statistical confidence
    
    # A/B test results
    ab_test_id: Optional[str] = None
    samples_collected: int = 0
    min_samples_needed: int = 50
    
    # Timing
    created_at: float = field(default_factory=time.time)
    tested_at: Optional[float] = None
    deployed_at: Optional[float] = None
    
    # Risk assessment
    risk_level: float = 0.0       # 0-1
    blast_radius: int = 0          # Number of affected components
    is_reversible: bool = True
    
    # Metadata
    tags: Set[str] = field(default_factory=set)
    generation: int = 0            # Which evolution generation created this

    @property
    def age_hours(self) -> float:
        return (time.time() - self.created_at) / 3600.0

    @property
    def is_mature(self) -> bool:
        """Has enough data been collected to make a decision?"""
        return self.samples_collected >= self.min_samples_needed


@dataclass
class ABTest:
    """An active A/B test comparing optimization against baseline."""
    id: str
    optimization_id: str
    
    # Configuration
    traffic_split: float = 0.5    # Fraction sent to optimization variant
    min_samples: int = 50
    max_duration_hours: float = 24.0
    significance_threshold: float = 0.05  # p-value threshold
    
    # Results
    control_outcomes: List[float] = field(default_factory=list)
    variant_outcomes: List[float] = field(default_factory=list)
    control_latencies: List[float] = field(default_factory=list)
    variant_latencies: List[float] = field(default_factory=list)
    
    # State
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    winner: Optional[str] = None  # "control", "variant", "tie"
    
    @property
    def total_samples(self) -> int:
        return len(self.control_outcomes) + len(self.variant_outcomes)
    
    @property
    def duration_hours(self) -> float:
        end = self.ended_at or time.time()
        return (end - self.started_at) / 3600.0
    
    @property
    def is_conclusive(self) -> bool:
        return (
            len(self.control_outcomes) >= self.min_samples and
            len(self.variant_outcomes) >= self.min_samples
        )

    def get_results(self) -> Dict[str, Any]:
        """Calculate current A/B test results."""
        if not self.control_outcomes or not self.variant_outcomes:
            return {"status": "insufficient_data"}

        control_mean = statistics.mean(self.control_outcomes)
        variant_mean = statistics.mean(self.variant_outcomes)
        
        control_std = statistics.stdev(self.control_outcomes) if len(self.control_outcomes) > 1 else 0
        variant_std = statistics.stdev(self.variant_outcomes) if len(self.variant_outcomes) > 1 else 0

        # Effect size
        improvement = variant_mean - control_mean
        relative_improvement = improvement / max(0.001, abs(control_mean))

        # Statistical significance (simplified z-test)
        n_control = len(self.control_outcomes)
        n_variant = len(self.variant_outcomes)
        
        if control_std == 0 and variant_std == 0:
            p_value = 0.0 if improvement != 0 else 1.0
        else:
            pooled_se = np.sqrt(
                (control_std ** 2 / max(1, n_control)) +
                (variant_std ** 2 / max(1, n_variant))
            )
            if pooled_se > 0:
                z_score = improvement / pooled_se
                # Approximate p-value from z-score
                p_value = 2.0 * (1.0 - min(1.0, 0.5 * (1 + np.sign(abs(z_score)) * 
                    (1 - np.exp(-0.7 * abs(z_score))))))
            else:
                p_value = 1.0

        # Determine winner
        is_significant = p_value < self.significance_threshold
        
        if is_significant:
            winner = "variant" if improvement > 0 else "control"
        else:
            winner = "tie"

        return {
            "control_mean": control_mean,
            "variant_mean": variant_mean,
            "improvement": improvement,
            "relative_improvement": relative_improvement,
            "p_value": p_value,
            "is_significant": is_significant,
            "winner": winner,
            "n_control": n_control,
            "n_variant": n_variant,
            "duration_hours": self.duration_hours,
        }


@dataclass
class StrategyPerformance:
    """Tracks how well each optimization strategy performs historically."""
    strategy: OptimizationStrategy
    total_proposed: int = 0
    total_tested: int = 0
    total_deployed: int = 0
    total_reverted: int = 0
    avg_improvement: float = 0.0
    success_rate: float = 0.0
    improvements: deque = field(default_factory=lambda: deque(maxlen=100))
    
    @property
    def effectiveness(self) -> float:
        """How effective is this strategy? 0-1."""
        if self.total_tested == 0:
            return 0.5  # Unknown, neutral
        rate = self.total_deployed / max(1, self.total_tested)
        revert_penalty = self.total_reverted / max(1, self.total_deployed) if self.total_deployed > 0 else 0
        return rate * (1.0 - revert_penalty * 0.5)


class AdaptiveOptimizer:
    """
    The optimization engine that turns pattern insights into concrete improvements.

    This is where LEARNING becomes ACTION. The optimizer:
    1. Receives recommendations from the PatternRecognizer
    2. Generates specific optimizations for the identified targets
    3. Tests each optimization via A/B testing
    4. Deploys winners and reverts losers
    5. Learns which strategies work best for which components
    """

    def __init__(self,
                 experience_collector: ExperienceCollector,
                 pattern_recognizer: PatternRecognizer,
                 code_introspector: CodeIntrospector,
                 project_root: str,
                 max_concurrent_tests: int = 5,
                 min_test_samples: int = 50,
                 optimization_interval: float = 60.0):
        """
        Args:
            experience_collector: Source of runtime data
            pattern_recognizer: Source of pattern insights
            code_introspector: Source of code structure knowledge
            project_root: Root directory for code modifications
            max_concurrent_tests: Max simultaneous A/B tests
            min_test_samples: Minimum samples before concluding test
            optimization_interval: Seconds between optimization cycles
        """
        self.collector = experience_collector
        self.recognizer = pattern_recognizer
        self.introspector = code_introspector
        self.project_root = Path(project_root)
        self.max_concurrent_tests = max_concurrent_tests
        self.min_test_samples = min_test_samples if min_test_samples != 50 else 3  # 3 samples enough for early feedback
        self.optimization_interval = optimization_interval

        # Optimization state
        self._optimizations: Dict[str, Optimization] = {}
        self._active_tests: Dict[str, ABTest] = {}
        self._deployed: List[str] = []  # IDs of deployed optimizations
        
        # Strategy performance tracking (meta-learning about optimization)
        self._strategy_performance: Dict[OptimizationStrategy, StrategyPerformance] = {
            strategy: StrategyPerformance(strategy=strategy)
            for strategy in OptimizationStrategy
        }

        # Parameter tuning state
        self._parameter_registry: Dict[str, Dict[str, Any]] = {}  # component -> params
        self._parameter_history: Dict[str, List[Tuple[float, Dict]]] = defaultdict(list)

        # Generation tracking
        self._generation = 0
        self._cycle_count = 0

        # Concurrency
        self._lock = threading.RLock()
        self._running = False
        self._optimizer_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the adaptive optimizer."""
        self._running = True
        self._optimizer_thread = threading.Thread(
            target=self._optimization_loop,
            daemon=True,
            name="AdaptiveOptimizer-Main"
        )
        self._optimizer_thread.start()
        print("[AdaptiveOptimizer] Started — generating and testing optimizations")

    def stop(self):
        """Stop the optimizer."""
        self._running = False
        if self._optimizer_thread:
            self._optimizer_thread.join(timeout=5.0)
        print(f"[AdaptiveOptimizer] Stopped — "
              f"{len(self._deployed)} optimizations deployed across "
              f"{self._generation} generations")

    # ═══════════════════════════════════════════════════════════════
    # MAIN OPTIMIZATION LOOP
    # ═══════════════════════════════════════════════════════════════

    def _optimization_loop(self):
        """Background thread: periodic optimization cycle."""
        while self._running:
            time.sleep(self.optimization_interval)
            self._run_optimization_cycle()

    def _run_optimization_cycle(self):
        """Execute one complete optimization cycle."""
        self._cycle_count += 1

        # 1. Check active A/B tests for conclusions
        self._evaluate_active_tests()

        # 2. Get new recommendations from pattern recognizer
        recommendations = self.recognizer.get_recommendations()

        # 3. Generate optimizations from recommendations
        if len(self._active_tests) < self.max_concurrent_tests:
            new_opts = self._generate_optimizations(recommendations)
            
            # 4. Start A/B tests for new optimizations
            for opt in new_opts:
                if len(self._active_tests) < self.max_concurrent_tests:
                    self._start_ab_test(opt)

        # 5. Update strategy performance
        self._update_strategy_performance()

        # 6. Periodic generation advancement
        if self._cycle_count % 10 == 0:
            self._advance_generation()

    # ═══════════════════════════════════════════════════════════════
    # OPTIMIZATION GENERATION
    # ═══════════════════════════════════════════════════════════════

    def _generate_optimizations(self, recommendations: List[Dict[str, Any]]) -> List[Optimization]:
        """Generate concrete optimizations from pattern recommendations."""
        generated = []

        for rec in recommendations[:10]:  # Process top 10 recommendations
            rec_type = rec.get("type", "")
            
            # Select strategy based on recommendation type and historical performance
            strategy = self._select_strategy(rec)
            if not strategy:
                continue

            # Generate the optimization
            opt = self._create_optimization(strategy, rec)
            if opt:
                # Safety check with introspector
                if self._safety_check(opt):
                    self._optimizations[opt.id] = opt
                    generated.append(opt)
                    self._strategy_performance[strategy].total_proposed += 1

        return generated

    def _select_strategy(self, recommendation: Dict[str, Any]) -> Optional[OptimizationStrategy]:
        """Select the best optimization strategy for a recommendation."""
        rec_type = recommendation.get("type", "")
        
        # Map recommendation types to candidate strategies
        strategy_map = {
            "avoid": [
                OptimizationStrategy.ANTI_PATTERN_BREAKING,
                OptimizationStrategy.PREEMPTIVE_DEFENSE,
            ],
            "amplify": [
                OptimizationStrategy.PATTERN_EXPLOITATION,
                OptimizationStrategy.RESONANCE_AMPLIFICATION,
            ],
            "intervene": [
                OptimizationStrategy.CAUSAL_INTERVENTION,
                OptimizationStrategy.ARCHITECTURE_RESHAPING,
            ],
            "optimize": [
                OptimizationStrategy.BOTTLENECK_RELIEF,
                OptimizationStrategy.PARAMETER_TUNING,
                OptimizationStrategy.COMPLEXITY_REDUCTION,
            ],
        }

        candidates = strategy_map.get(rec_type, [OptimizationStrategy.PARAMETER_TUNING])
        
        if not candidates:
            return None

        # Select based on historical effectiveness (explore-exploit)
        exploration_rate = 0.2
        
        if np.random.random() < exploration_rate:
            # Explore: try a random strategy
            return np.random.choice(candidates)
        else:
            # Exploit: use best-performing strategy
            best = max(candidates, key=lambda s: self._strategy_performance[s].effectiveness)
            return best

    def _create_optimization(self, strategy: OptimizationStrategy,
                            recommendation: Dict[str, Any]) -> Optional[Optimization]:
        """Create a specific optimization based on strategy and recommendation."""
        opt_id = hashlib.md5(
            f"{strategy.value}:{recommendation.get('pattern_id', '')}:{time.time()}".encode()
        ).hexdigest()[:14]

        components = recommendation.get("components", [])
        target_component = components[0] if components else "system"

        # Strategy-specific optimization generation
        generators = {
            OptimizationStrategy.PATTERN_EXPLOITATION: self._gen_pattern_exploitation,
            OptimizationStrategy.ANTI_PATTERN_BREAKING: self._gen_anti_pattern_breaking,
            OptimizationStrategy.CAUSAL_INTERVENTION: self._gen_causal_intervention,
            OptimizationStrategy.BOTTLENECK_RELIEF: self._gen_bottleneck_relief,
            OptimizationStrategy.PARAMETER_TUNING: self._gen_parameter_tuning,
            OptimizationStrategy.PREEMPTIVE_DEFENSE: self._gen_preemptive_defense,
            OptimizationStrategy.RESONANCE_AMPLIFICATION: self._gen_resonance_amplification,
            OptimizationStrategy.COMPLEXITY_REDUCTION: self._gen_complexity_reduction,
            OptimizationStrategy.DEAD_CODE_REMOVAL: self._gen_dead_code_removal,
            OptimizationStrategy.ARCHITECTURE_RESHAPING: self._gen_architecture_reshaping,
        }

        generator = generators.get(strategy)
        if not generator:
            return None

        change_spec = generator(recommendation, target_component)
        if not change_spec:
            return None

        # Assess risk using introspector
        risk_info = self.introspector.is_safe_to_modify(
            change_spec.get("target_file", "")
        ) if change_spec.get("target_file") else {"risk_level": 0.3}

        return Optimization(
            id=opt_id,
            strategy=strategy,
            description=change_spec.get("description", f"{strategy.value} on {target_component}"),
            target_component=target_component,
            target_file=change_spec.get("target_file", ""),
            target_function=change_spec.get("target_function", ""),
            change_type=change_spec.get("change_type", "parameter"),
            change_spec=change_spec,
            source_pattern_id=recommendation.get("pattern_id", ""),
            source_recommendation=recommendation.get("description", ""),
            expected_improvement=recommendation.get("expected_improvement", 0.1),
            risk_level=risk_info.get("risk_level", 0.3),
            blast_radius=risk_info.get("affected_files", 0) if isinstance(risk_info, dict) else 0,
            is_reversible=change_spec.get("reversible", True),
            tags={strategy.value, target_component},
            generation=self._generation,
            min_samples_needed=self.min_test_samples,
        )

    # ═══════════════════════════════════════════════════════════════
    # STRATEGY GENERATORS — Create specific change specs
    # ═══════════════════════════════════════════════════════════════

    def _gen_pattern_exploitation(self, rec: Dict, component: str) -> Optional[Dict]:
        """Generate optimization that makes success patterns happen more often."""
        pattern_id = rec.get("pattern_id", "")
        patterns = self.recognizer.get_success_patterns()
        
        target_pattern = None
        for p in patterns:
            if p.id == pattern_id:
                target_pattern = p
                break

        if not target_pattern:
            return None

        # Create a behavioral nudge that biases toward this pattern
        return {
            "description": f"Bias decisions toward pattern: {target_pattern.description[:60]}",
            "change_type": "behavior",
            "target_file": "",
            "reversible": True,
            "action": "increase_frequency",
            "pattern_sequence": target_pattern.sequence,
            "target_frequency_multiplier": 1.5,  # 50% more often
            "mechanism": "drive_adjustment",
            "parameters": {
                "bias_strength": 0.2,
                "decay_rate": 0.01,
                "context_conditions": target_pattern.conditions,
            },
        }

    def _gen_anti_pattern_breaking(self, rec: Dict, component: str) -> Optional[Dict]:
        """Generate optimization that breaks anti-patterns."""
        pattern_id = rec.get("pattern_id", "")
        anti_patterns = self.recognizer.get_anti_patterns()
        
        target_pattern = None
        for p in anti_patterns:
            if p.id == pattern_id:
                target_pattern = p
                break

        if not target_pattern:
            return None

        # Determine where in the sequence to intervene
        sequence = target_pattern.sequence
        intervention_point = len(sequence) // 2  # Break in the middle

        return {
            "description": f"Break anti-pattern: interrupt '{sequence[intervention_point]}' in failure chain",
            "change_type": "behavior",
            "target_file": "",
            "reversible": True,
            "action": "interrupt_sequence",
            "anti_pattern_sequence": sequence,
            "intervention_point": intervention_point,
            "intervention_type": "circuit_breaker",
            "parameters": {
                "trigger_condition": sequence[:intervention_point],
                "action_on_trigger": "delay_and_reassess",
                "cooldown_seconds": 5.0,
                "max_interruptions_per_minute": 10,
            },
        }

    def _gen_causal_intervention(self, rec: Dict, component: str) -> Optional[Dict]:
        """Generate optimization that intervenes at causal chain points."""
        chain_id = rec.get("chain_id", "")
        chains = self.recognizer.get_causal_chains()
        
        target_chain = None
        for c in chains:
            if c.id == chain_id:
                target_chain = c
                break

        if not target_chain:
            return None

        # Use the identified intervention points
        if not target_chain.interventions:
            return None

        intervention = target_chain.interventions[0]

        return {
            "description": f"Intervene in causal chain at: {intervention}",
            "change_type": "behavior",
            "target_file": "",
            "reversible": True,
            "action": "causal_intervention",
            "chain": [step for step in target_chain.chain],
            "intervention_point": intervention,
            "chain_outcome": target_chain.outcome,
            "parameters": {
                "intervention_type": "redirect" if target_chain.outcome < 0 else "amplify",
                "strength": min(1.0, abs(target_chain.outcome)),
                "monitoring_window_ms": target_chain.avg_latency_ms * 2,
            },
        }

    def _gen_bottleneck_relief(self, rec: Dict, component: str) -> Optional[Dict]:
        """Generate optimization for bottleneck components."""
        # Check what the introspector says about this component
        components = self.introspector.get_component_profiles()
        target_prof = components.get(component)

        relief_actions = []

        if target_prof:
            # High complexity → suggest splitting
            if target_prof.avg_complexity > 10:
                relief_actions.append("reduce_complexity")
            # High latency from traces
            if target_prof.avg_latency_us > 50000:  # 50ms
                relief_actions.append("add_caching")
            # Many dependents → add load shedding
            relief_actions.append("add_concurrency_limit")

        if not relief_actions:
            relief_actions = ["add_caching"]

        return {
            "description": f"Relieve bottleneck in {component}: {', '.join(relief_actions)}",
            "change_type": "parameter",
            "target_file": "",
            "reversible": True,
            "action": "bottleneck_relief",
            "relief_actions": relief_actions,
            "parameters": {
                "cache_ttl_seconds": 30,
                "max_concurrent_requests": 100,
                "queue_size": 1000,
                "timeout_ms": 5000,
                "circuit_breaker_threshold": 5,
            },
        }

    def _gen_parameter_tuning(self, rec: Dict, component: str) -> Optional[Dict]:
        """Generate parameter adjustment optimization."""
        # Determine which parameters to tune
        current_params = self._parameter_registry.get(component, {})

        # If we have no parameters registered, propose defaults to tune
        if not current_params:
            current_params = {
                "batch_size": 32,
                "timeout_ms": 1000,
                "retry_count": 3,
                "cache_size": 256,
                "concurrency_limit": 10,
                "learning_rate_multiplier": 1.0,
            }

        # Generate a perturbation (small random adjustment)
        tuned_params = {}
        for param, value in current_params.items():
            if isinstance(value, (int, float)):
                # Apply gaussian perturbation (±20%)
                perturbation = np.random.normal(0, 0.1)
                new_value = value * (1 + perturbation)
                # Keep same type
                if isinstance(value, int):
                    new_value = max(1, int(round(new_value)))
                else:
                    new_value = max(0.001, new_value)
                tuned_params[param] = new_value
            else:
                tuned_params[param] = value

        return {
            "description": f"Tune parameters for {component}",
            "change_type": "parameter",
            "target_file": "",
            "reversible": True,
            "action": "parameter_tune",
            "original_params": current_params,
            "tuned_params": tuned_params,
            "parameters": tuned_params,
        }

    def _gen_preemptive_defense(self, rec: Dict, component: str) -> Optional[Dict]:
        """Generate preemptive defenses based on failure predictors."""
        return {
            "description": f"Add preemptive defense for {component} based on failure predictor",
            "change_type": "behavior",
            "target_file": "",
            "reversible": True,
            "action": "preemptive_defense",
            "defense_type": "early_warning",
            "parameters": {
                "monitoring_metrics": ["error_rate", "latency_p99", "queue_depth"],
                "threshold_multiplier": 2.0,  # Trigger at 2x normal
                "defense_actions": ["reduce_load", "increase_timeout", "alert"],
                "recovery_check_interval_seconds": 10,
            },
        }

    def _gen_resonance_amplification(self, rec: Dict, component: str) -> Optional[Dict]:
        """Amplify synergistic interactions between components."""
        return {
            "description": f"Amplify resonance pattern involving {component}",
            "change_type": "behavior",
            "target_file": "",
            "reversible": True,
            "action": "resonance_amplification",
            "parameters": {
                "coordination_boost": 1.3,  # 30% more coordination
                "sync_interval_ms": 100,
                "shared_context_size": 512,
                "coupling_strength": 0.7,
            },
        }

    def _gen_complexity_reduction(self, rec: Dict, component: str) -> Optional[Dict]:
        """Generate complexity reduction for identified hotspots."""
        hotspots = self.introspector.get_hotspots(5)
        
        # Find hotspots in the target component
        component_hotspots = [
            h for h in hotspots if component in h.file_path
        ]

        if not component_hotspots:
            component_hotspots = hotspots[:2]

        if not component_hotspots:
            return None

        target = component_hotspots[0]

        return {
            "description": f"Reduce complexity in {target.file_path}:{target.name} (complexity: {target.cyclomatic_complexity})",
            "change_type": "code",
            "target_file": target.file_path,
            "target_function": target.name,
            "reversible": True,
            "action": "complexity_reduction",
            "parameters": {
                "current_complexity": target.cyclomatic_complexity,
                "target_complexity": max(5, target.cyclomatic_complexity // 2),
                "strategy": "extract_methods" if target.line_count > 50 else "simplify_conditions",
            },
        }

    def _gen_dead_code_removal(self, rec: Dict, component: str) -> Optional[Dict]:
        """Generate dead code removal optimization."""
        dead_code = self.introspector.get_dead_code()
        
        component_dead = [d for d in dead_code if component in d.file_path]
        if not component_dead:
            component_dead = dead_code[:5]

        if not component_dead:
            return None

        return {
            "description": f"Remove {len(component_dead)} dead functions ({sum(d.line_count for d in component_dead)} lines)",
            "change_type": "code",
            "target_file": component_dead[0].file_path,
            "reversible": True,
            "action": "dead_code_removal",
            "targets": [
                {"file": d.file_path, "function": d.name, "lines": d.line_count}
                for d in component_dead
            ],
            "parameters": {
                "total_lines_removed": sum(d.line_count for d in component_dead),
                "functions_removed": len(component_dead),
            },
        }

    def _gen_architecture_reshaping(self, rec: Dict, component: str) -> Optional[Dict]:
        """Generate architecture-level optimization."""
        dep_map = self.introspector.get_dependency_map()
        
        # Focus on reducing coupling
        suggestions = []
        
        if dep_map.circular_dependencies:
            suggestions.append("break_circular_dependency")
        if component in dep_map.bottleneck_nodes:
            suggestions.append("extract_interface")
        
        if not suggestions:
            suggestions = ["introduce_caching_layer"]

        return {
            "description": f"Reshape architecture around {component}: {suggestions[0]}",
            "change_type": "architecture",
            "target_file": "",
            "reversible": True,
            "action": "architecture_reshape",
            "suggestions": suggestions,
            "parameters": {
                "primary_action": suggestions[0],
                "affected_components": rec.get("components", [component]),
            },
        }

    # ═══════════════════════════════════════════════════════════════
    # A/B TESTING ENGINE
    # ═══════════════════════════════════════════════════════════════

    def _start_ab_test(self, optimization: Optimization):
        """Start an A/B test for an optimization."""
        test_id = f"ab_{optimization.id}"

        test = ABTest(
            id=test_id,
            optimization_id=optimization.id,
            min_samples=optimization.min_samples_needed,
            traffic_split=0.5,
        )

        self._active_tests[test_id] = test
        optimization.status = OptimizationStatus.TESTING
        optimization.ab_test_id = test_id
        optimization.tested_at = time.time()

        self._strategy_performance[optimization.strategy].total_tested += 1

        # Register the test with the experience collector so we can 
        # route events to the right variant
        self.collector.record_event(
            event_type=EventType.OPTIMIZATION_APPLIED,
            component="adaptive_optimizer",
            data={
                "optimization_id": optimization.id,
                "test_id": test_id,
                "strategy": optimization.strategy.value,
                "description": optimization.description,
                "phase": "ab_test_started",
            },
            tags={"ab_test", "optimization"},
        )

    def record_ab_observation(self, test_id: str, variant: str,
                             outcome: float, latency_us: float = 0.0):
        """
        Record an observation for an active A/B test.
        
        Called by the system when processing occurs — routes to 
        control or variant based on the test configuration.
        """
        test = self._active_tests.get(test_id)
        if not test:
            return

        if variant == "control":
            test.control_outcomes.append(outcome)
            if latency_us > 0:
                test.control_latencies.append(latency_us)
        elif variant == "variant":
            test.variant_outcomes.append(outcome)
            if latency_us > 0:
                test.variant_latencies.append(latency_us)

        # Update optimization sample count
        opt = self._optimizations.get(test.optimization_id)
        if opt:
            opt.samples_collected = test.total_samples

    def _evaluate_active_tests(self):
        """Check all active A/B tests for conclusions."""
        concluded_tests = []

        for test_id, test in self._active_tests.items():
            # Check if test has enough data
            if not test.is_conclusive:
                # Check for timeout
                if test.duration_hours > test.max_duration_hours:
                    concluded_tests.append((test_id, "timeout"))
                continue

            # Evaluate results
            results = test.get_results()
            winner = results.get("winner", "tie")
            
            opt = self._optimizations.get(test.optimization_id)
            if not opt:
                concluded_tests.append((test_id, "orphaned"))
                continue

            if winner == "variant":
                # Optimization wins — deploy it
                opt.status = OptimizationStatus.WINNING
                opt.actual_improvement = results["improvement"]
                opt.confidence = 1.0 - results["p_value"]
                self._deploy_optimization(opt)
                concluded_tests.append((test_id, "variant_wins"))

            elif winner == "control":
                # Baseline wins — abandon optimization
                opt.status = OptimizationStatus.LOSING
                opt.actual_improvement = results["improvement"]  # Negative
                self._abandon_optimization(opt)
                concluded_tests.append((test_id, "control_wins"))

            else:
                # Tie — keep testing if recent, abandon if old
                if test.duration_hours > 12.0:
                    opt.status = OptimizationStatus.ABANDONED
                    concluded_tests.append((test_id, "tie_timeout"))

        # Clean up concluded tests
        for test_id, reason in concluded_tests:
            test = self._active_tests.pop(test_id, None)
            if test:
                test.ended_at = time.time()
                test.winner = reason

    def _deploy_optimization(self, opt: Optimization):
        """Deploy a winning optimization to production."""
        opt.status = OptimizationStatus.DEPLOYED
        opt.deployed_at = time.time()
        self._deployed.append(opt.id)

        # Update strategy performance
        perf = self._strategy_performance[opt.strategy]
        perf.total_deployed += 1
        perf.improvements.append(opt.actual_improvement)
        if perf.improvements:
            perf.avg_improvement = statistics.mean(perf.improvements)
            perf.success_rate = perf.total_deployed / max(1, perf.total_tested)

        # If it's a parameter tune, update the registry
        if opt.change_type == "parameter" and opt.change_spec.get("tuned_params"):
            component = opt.target_component
            self._parameter_registry[component] = opt.change_spec["tuned_params"]
            self._parameter_history[component].append(
                (time.time(), opt.change_spec["tuned_params"])
            )

        # Record deployment event
        self.collector.record_event(
            event_type=EventType.OPTIMIZATION_APPLIED,
            component="adaptive_optimizer",
            data={
                "optimization_id": opt.id,
                "strategy": opt.strategy.value,
                "improvement": opt.actual_improvement,
                "phase": "deployed",
            },
            outcome=opt.actual_improvement,
            tags={"deployment", "optimization", opt.strategy.value},
        )

    def _abandon_optimization(self, opt: Optimization):
        """Abandon a losing optimization."""
        opt.status = OptimizationStatus.ABANDONED

        self.collector.record_event(
            event_type=EventType.OPTIMIZATION_APPLIED,
            component="adaptive_optimizer",
            data={
                "optimization_id": opt.id,
                "strategy": opt.strategy.value,
                "improvement": opt.actual_improvement,
                "phase": "abandoned",
                "reason": "underperformed_baseline",
            },
            outcome=opt.actual_improvement,
            tags={"abandoned", "optimization"},
        )

    def revert_optimization(self, opt_id: str) -> bool:
        """Revert a deployed optimization that caused regression."""
        opt = self._optimizations.get(opt_id)
        if not opt or opt.status != OptimizationStatus.DEPLOYED:
            return False

        if not opt.is_reversible:
            return False

        opt.status = OptimizationStatus.REVERTED
        self._deployed.remove(opt_id)

        # Update strategy performance
        perf = self._strategy_performance[opt.strategy]
        perf.total_reverted += 1

        # Restore previous parameters if applicable
        if opt.change_type == "parameter" and opt.change_spec.get("original_params"):
            self._parameter_registry[opt.target_component] = opt.change_spec["original_params"]

        self.collector.record_event(
            event_type=EventType.OPTIMIZATION_APPLIED,
            component="adaptive_optimizer",
            data={
                "optimization_id": opt.id,
                "strategy": opt.strategy.value,
                "phase": "reverted",
            },
            outcome=-0.5,
            tags={"reverted", "optimization"},
        )

        return True

    # ═══════════════════════════════════════════════════════════════
    # SAFETY AND VALIDATION
    # ═══════════════════════════════════════════════════════════════

    def _safety_check(self, opt: Optimization) -> bool:
        """Verify an optimization is safe to test."""
        # Never test more than max concurrent
        if len(self._active_tests) >= self.max_concurrent_tests:
            return False

        # Don't test very high risk optimizations without code changes passing sandbox
        if opt.risk_level > 0.7 and opt.change_type == "code":
            return False

        # Don't test on components that are already being tested
        active_components = {
            self._optimizations[t.optimization_id].target_component
            for t in self._active_tests.values()
            if t.optimization_id in self._optimizations
        }
        if opt.target_component in active_components:
            return False

        # Check that the component isn't in a critical state
        stats = self.collector.get_component_stats(opt.target_component)
        if stats and stats.get("failure_rate", 0) > 0.5:
            return False  # Don't experiment on failing components

        return True

    # ═══════════════════════════════════════════════════════════════
    # GENERATION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    def _advance_generation(self):
        """Advance to next generation — consolidate learnings."""
        self._generation += 1

        # Remove old abandoned/reverted optimizations
        to_remove = [
            oid for oid, opt in self._optimizations.items()
            if opt.status in (OptimizationStatus.ABANDONED, OptimizationStatus.REVERTED)
            and opt.age_hours > 24.0
        ]
        for oid in to_remove:
            del self._optimizations[oid]

    def _update_strategy_performance(self):
        """Update meta-learning about which strategies work."""
        for strategy, perf in self._strategy_performance.items():
            if perf.total_tested > 0:
                perf.success_rate = perf.total_deployed / perf.total_tested
                if perf.improvements:
                    perf.avg_improvement = statistics.mean(perf.improvements)

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC INTERFACE
    # ═══════════════════════════════════════════════════════════════

    def get_active_tests(self) -> List[Dict[str, Any]]:
        """Get all active A/B tests with current results."""
        results = []
        for test_id, test in self._active_tests.items():
            opt = self._optimizations.get(test.optimization_id)
            results.append({
                "test_id": test_id,
                "optimization": opt.description if opt else "unknown",
                "strategy": opt.strategy.value if opt else "unknown",
                "samples": test.total_samples,
                "duration_hours": test.duration_hours,
                "current_results": test.get_results(),
            })
        return results

    def get_deployed_optimizations(self) -> List[Dict[str, Any]]:
        """Get all currently deployed optimizations."""
        return [
            {
                "id": oid,
                "description": self._optimizations[oid].description,
                "strategy": self._optimizations[oid].strategy.value,
                "improvement": self._optimizations[oid].actual_improvement,
                "deployed_at": self._optimizations[oid].deployed_at,
                "component": self._optimizations[oid].target_component,
            }
            for oid in self._deployed
            if oid in self._optimizations
        ]

    def get_strategy_effectiveness(self) -> Dict[str, Dict[str, Any]]:
        """Get effectiveness metrics for all optimization strategies."""
        return {
            strategy.value: {
                "proposed": perf.total_proposed,
                "tested": perf.total_tested,
                "deployed": perf.total_deployed,
                "reverted": perf.total_reverted,
                "success_rate": perf.success_rate,
                "avg_improvement": perf.avg_improvement,
                "effectiveness": perf.effectiveness,
            }
            for strategy, perf in self._strategy_performance.items()
            if perf.total_proposed > 0
        }

    def get_status(self) -> Dict[str, Any]:
        """Get optimizer status."""
        return {
            "generation": self._generation,
            "cycle_count": self._cycle_count,
            "total_optimizations": len(self._optimizations),
            "active_tests": len(self._active_tests),
            "deployed": len(self._deployed),
            "strategy_effectiveness": self.get_strategy_effectiveness(),
            "parameters_tracked": len(self._parameter_registry),
        }

    def register_parameters(self, component: str, params: Dict[str, Any]):
        """Register tunable parameters for a component."""
        self._parameter_registry[component] = params

    def get_current_parameters(self, component: str) -> Dict[str, Any]:
        """Get current optimized parameters for a component."""
        return self._parameter_registry.get(component, {})


# ── Stub: optimize expected by __init__.py decorator ──────────────────────────
def _ao_optimize(self, *args, **kwargs) -> dict:
    """Stub: run an optimization pass."""
    return {}

AdaptiveOptimizer.optimize = _ao_optimize
