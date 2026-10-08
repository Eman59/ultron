"""
Evolution Controller — The Conductor of Self-Learning.

This is the top-level orchestrator that coordinates ALL learning subsystems
into a coherent evolution cycle. It's the "frontal cortex" that decides
WHEN to learn, HOW FAST to change, and WHAT to prioritize.

Responsibilities:
  - Orchestrate the pipeline: Collect → Recognize → Introspect → Optimize → Distill
  - Manage GENERATIONS (discrete evolution steps with lineage tracking)
  - Control VELOCITY (how fast the system modifies itself)
  - Maintain SAFETY BOUNDS (never evolve faster than we can verify)
  - Track LINEAGE (which improvement led to which descendant)
  - Handle ROLLBACK (revert entire generations if things go wrong)
  - Report PROGRESS (how much smarter has the system become?)
  - Balance EXPLORATION vs EXPLOITATION at the system level

The Evolution Controller makes the meta-meta-decisions:
  "Should we be learning right now, or consolidating?"
  "Are we changing too fast? Slow down."
  "We've plateaued — time to explore radically."
  "This generation was a disaster — roll everything back."

Generations:
  Each "generation" is a coherent set of improvements that were
  discovered, tested, and deployed together. If a generation causes
  overall regression, the entire generation can be reverted atomically.

Evolution Speed Control:
  - CAUTIOUS: 1 optimization per hour, full testing
  - NORMAL:   5 optimizations per hour, standard testing
  - AGGRESSIVE: 20 optimizations per hour, reduced testing
  - HYPERDRIVE: Unlimited, minimal testing (use in safe environments only)

  Speed automatically adjusts based on:
  - Recent regression rate (more regressions → slower)
  - System stability (unstable → slower)
  - Improvement velocity (plateaued → try aggressive)
  - Time of day / load patterns (off-peak → more aggressive)
"""

import time
import json
import hashlib
import threading
import statistics
import traceback
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from pathlib import Path

from .experience_collector import ExperienceCollector, EventType
from .pattern_recognizer import PatternRecognizer, Pattern, PatternStrength
from .code_introspector import CodeIntrospector, ComponentHealth
from .adaptive_optimizer import AdaptiveOptimizer, Optimization, OptimizationStatus
from .knowledge_distiller import KnowledgeDistiller, DistilledRule, RuleType


class EvolutionSpeed(Enum):
    """How aggressively the system modifies itself."""
    FROZEN = "frozen"           # No changes allowed
    CAUTIOUS = "cautious"      # 1 opt/hour, full testing
    NORMAL = "normal"          # 5 opts/hour, standard testing
    AGGRESSIVE = "aggressive"  # 20 opts/hour, reduced testing
    HYPERDRIVE = "hyperdrive"  # Unlimited, minimal testing


class EvolutionPhase(Enum):
    """Current phase of the evolution cycle."""
    OBSERVING = "observing"           # Collecting data
    ANALYZING = "analyzing"           # Pattern recognition
    INTROSPECTING = "introspecting"   # Code analysis
    OPTIMIZING = "optimizing"         # Generating/testing improvements
    DISTILLING = "distilling"         # Converting to rules
    CONSOLIDATING = "consolidating"   # Merging and stabilizing
    RESTING = "resting"               # Letting changes settle
    ROLLING_BACK = "rolling_back"     # Reverting bad changes


class SystemStability(Enum):
    """Overall system stability assessment."""
    STABLE = "stable"
    SLIGHTLY_UNSTABLE = "slightly_unstable"
    UNSTABLE = "unstable"
    CRITICAL = "critical"


@dataclass
class GenerationRecord:
    """Record of a single evolution generation."""
    id: str
    number: int
    started_at: float
    ended_at: Optional[float] = None

    # What was done
    optimizations_deployed: List[str] = field(default_factory=list)
    rules_created: List[str] = field(default_factory=list)
    patterns_discovered: int = 0
    
    # Performance
    performance_before: float = 0.0
    performance_after: float = 0.0
    improvement_delta: float = 0.0
    
    # Lineage
    parent_generation: Optional[str] = None
    child_generations: List[str] = field(default_factory=list)
    
    # Status
    reverted: bool = False
    revert_reason: str = ""
    
    # Metadata
    speed_setting: str = "normal"
    phase_durations: Dict[str, float] = field(default_factory=dict)

    @property
    def duration_hours(self) -> float:
        end = self.ended_at or time.time()
        return (end - self.started_at) / 3600.0

    @property
    def was_successful(self) -> bool:
        return self.improvement_delta > 0 and not self.reverted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_hours": self.duration_hours,
            "optimizations_deployed": self.optimizations_deployed,
            "rules_created": self.rules_created,
            "patterns_discovered": self.patterns_discovered,
            "performance_before": self.performance_before,
            "performance_after": self.performance_after,
            "improvement_delta": self.improvement_delta,
            "parent_generation": self.parent_generation,
            "reverted": self.reverted,
            "speed_setting": self.speed_setting,
            "was_successful": self.was_successful,
        }


@dataclass
class GenerationReport:
    """Summary report for a completed generation."""
    generation_id: str
    generation_number: int
    duration_hours: float
    
    # Improvements
    optimizations_tested: int = 0
    optimizations_deployed: int = 0
    optimizations_reverted: int = 0
    rules_distilled: int = 0
    patterns_found: int = 0
    
    # Performance
    overall_improvement: float = 0.0
    component_improvements: Dict[str, float] = field(default_factory=dict)
    
    # Learning
    knowledge_gained: int = 0     # New rules
    knowledge_refined: int = 0    # Updated rules
    knowledge_deprecated: int = 0 # Removed rules
    
    # Health
    stability: str = "stable"
    regressions_detected: int = 0
    
    # Meta
    speed_used: str = "normal"
    was_successful: bool = True


@dataclass
class EvolutionMetrics:
    """Real-time metrics for the evolution process."""
    # Performance trajectory
    performance_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    # Speed metrics
    optimizations_per_hour: float = 0.0
    regressions_per_hour: float = 0.0
    
    # Learning metrics
    patterns_per_hour: float = 0.0
    rules_per_hour: float = 0.0
    knowledge_base_size: int = 0
    
    # Stability
    error_rate_trend: float = 0.0  # Positive = getting worse
    latency_trend: float = 0.0
    
    # Meta-learning
    strategy_effectiveness: Dict[str, float] = field(default_factory=dict)
    best_strategy: str = ""
    worst_strategy: str = ""


class EvolutionController:
    """
    The master conductor of Ultron's self-learning evolution.

    Coordinates all learning subsystems, manages evolution speed,
    tracks generations with lineage, and ensures the system only
    gets better — never catastrophically worse.
    """

    def __init__(self,
                 project_root: str,
                 experience_collector: ExperienceCollector,
                 pattern_recognizer: PatternRecognizer,
                 code_introspector: CodeIntrospector,
                 adaptive_optimizer: AdaptiveOptimizer,
                 knowledge_distiller: KnowledgeDistiller,
                 evolution_path: str = None,
                 initial_speed: EvolutionSpeed = EvolutionSpeed.NORMAL,
                 generation_duration_hours: float = 1.0,
                 max_regressions_per_generation: int = 3,
                 min_stability_for_aggressive: float = 0.8):
        """
        Args:
            project_root: Root of the project being evolved
            experience_collector: Event collection system
            pattern_recognizer: Pattern discovery system
            code_introspector: Code analysis system
            adaptive_optimizer: Optimization engine
            knowledge_distiller: Knowledge persistence system
            evolution_path: Directory for evolution history persistence
            initial_speed: Starting evolution speed
            generation_duration_hours: How long each generation lasts
            max_regressions_per_generation: Max regressions before slowdown
            min_stability_for_aggressive: Min stability score for aggressive mode
        """
        self.project_root = Path(project_root)
        
        # Subsystems
        self.collector = experience_collector
        self.recognizer = pattern_recognizer
        self.introspector = code_introspector
        self.optimizer = adaptive_optimizer
        self.distiller = knowledge_distiller

        # Configuration
        self.speed = initial_speed
        self.generation_duration = generation_duration_hours * 3600.0
        self.max_regressions = max_regressions_per_generation
        self.min_stability_aggressive = min_stability_for_aggressive

        # Evolution state
        self._current_generation: Optional[GenerationRecord] = None
        self._generation_history: List[GenerationRecord] = []
        self._generation_number = 0
        self._phase = EvolutionPhase.OBSERVING
        self._stability = SystemStability.STABLE

        # Metrics
        self._metrics = EvolutionMetrics()
        self._regressions_this_generation = 0
        self._total_improvements = 0
        self._total_regressions = 0

        # Persistence
        self._evolution_path = Path(evolution_path) if evolution_path else self.project_root / "data" / "evolution"
        self._evolution_path.mkdir(parents=True, exist_ok=True)

        # Performance baseline — seeded from code health if available, not stuck at 0.5
        self._baseline_performance: float = self._measure_initial_performance()
        self._current_performance: float = self._baseline_performance
        self._performance_window: deque = deque(maxlen=100)
        self._performance_window.append(self._baseline_performance)

        # Speed control
        self._speed_limits = {
            EvolutionSpeed.FROZEN: 0,
            EvolutionSpeed.CAUTIOUS: 1,
            EvolutionSpeed.NORMAL: 5,
            EvolutionSpeed.AGGRESSIVE: 20,
            EvolutionSpeed.HYPERDRIVE: 100,
        }
        self._optimizations_this_hour: int = 0
        self._hour_start: float = time.time()

        # Concurrency
        self._lock = threading.RLock()
        self._running = False
        self._evolution_thread: Optional[threading.Thread] = None

        # Load history
        self._load_history()

    # ═══════════════════════════════════════════════════════════════
    # PERFORMANCE SEEDING — Real baseline, not hardcoded 0.5
    # ═══════════════════════════════════════════════════════════════

    def _measure_initial_performance(self) -> float:
        """
        Seed the performance baseline from real signals instead of a fixed 0.5.
        Checks: code health from introspector, evolution history, knowledge base size.
        Returns a float in [0.1, 0.9].
        """
        scores = []

        # 1. Code health from introspector (if available)
        try:
            overview = self.introspector.get_project_overview()
            health = overview.get("overall_health", None)
            if health is not None:
                scores.append(float(health))
        except Exception:
            pass

        # 2. Knowledge base size (more rules = more accumulated learning)
        try:
            kb_size = self.distiller.kb.size
            # Normalize: 0 rules → 0.3, 100 rules → 0.6, 1000 rules → 0.8
            import math as _math
            kb_score = 0.3 + 0.5 * min(1.0, _math.log1p(kb_size) / _math.log1p(1000))
            scores.append(kb_score)
        except Exception:
            pass

        # 3. Previous generation history
        try:
            hist_path = self._evolution_path / "evolution_history.json"
            if hist_path.exists():
                import json as _json
                with open(hist_path) as f:
                    hist = _json.load(f)
                last_perf = hist.get("lifetime", {}).get("best_performance", None)
                if last_perf is not None and last_perf > 0:
                    scores.append(float(last_perf))
        except Exception:
            pass

        if scores:
            baseline = sum(scores) / len(scores)
            baseline = max(0.1, min(0.9, baseline))
        else:
            baseline = 0.5

        print(f"[EvolutionController] Performance baseline seeded: {baseline:.4f} (from {len(scores)} signal(s))")
        return baseline

    # ═══════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════

    def start(self):
        """Start the evolution controller — awakens the entire learning system."""
        self._running = True

        # Start all subsystems
        self.collector.start()
        self.recognizer.start()
        self.introspector.start()
        self.optimizer.start()
        self.distiller.start()

        # Start our own orchestration loop
        self._evolution_thread = threading.Thread(
            target=self._evolution_loop,
            daemon=True,
            name="EvolutionController-Main"
        )
        self._evolution_thread.start()

        # Begin first generation
        self._begin_generation()

        print("=" * 70)
        print("  ULTRON SELF-LEARNING SYSTEM — ONLINE")
        print("=" * 70)
        print(f"  Evolution Speed: {self.speed.value}")
        print(f"  Generation Duration: {self.generation_duration / 3600:.1f} hours")
        print(f"  Knowledge Base: {self.distiller.kb.size} rules")
        print(f"  Generation: #{self._generation_number}")
        print(f"  History: {len(self._generation_history)} past generations")
        print("=" * 70)

    def stop(self):
        """Stop the evolution controller — graceful shutdown."""
        print("\n[EvolutionController] Shutting down self-learning system...")
        self._running = False

        # End current generation
        if self._current_generation:
            self._end_generation()

        # Stop all subsystems
        self.optimizer.stop()
        self.distiller.stop()
        self.introspector.stop()
        self.recognizer.stop()
        self.collector.stop()

        # Persist state
        self._save_history()

        if self._evolution_thread:
            self._evolution_thread.join(timeout=10.0)

        print(f"[EvolutionController] Stopped — {self._generation_number} generations completed")
        print(f"  Total improvements: {self._total_improvements}")
        print(f"  Total regressions: {self._total_regressions}")
        print(f"  Final performance: {self._current_performance:.4f}")

    # ═══════════════════════════════════════════════════════════════
    # MAIN EVOLUTION LOOP
    # ═══════════════════════════════════════════════════════════════

    def _evolution_loop(self):
        """The main orchestration loop — runs the evolution cycle."""
        cycle_interval = 30.0  # Check every 30 seconds

        while self._running:
            try:
                self._evolution_tick()
            except Exception as e:
                print(f"[EvolutionController] Error in evolution tick: {e}")
                traceback.print_exc()
                # On error, slow down
                self._adjust_speed_down("evolution_error")

            time.sleep(cycle_interval)

    def _evolution_tick(self):
        """Single tick of the evolution orchestration."""
        # 1. Update metrics
        self._update_metrics()

        # 2. Assess stability
        self._assess_stability()

        # 3. Check if generation should end
        if self._should_end_generation():
            self._end_generation()
            self._begin_generation()

        # 4. Adjust evolution speed
        self._adjust_speed()

        # 5. Run phase-appropriate actions
        self._run_phase()

        # 6. Feed patterns to distiller
        self._feed_distiller()

        # 7. Check for regressions
        self._check_regressions()

        # 8. Advance phase
        self._advance_phase()

        # 9. Hourly speed limit reset
        if time.time() - self._hour_start > 3600:
            self._optimizations_this_hour = 0
            self._hour_start = time.time()

    # ═══════════════════════════════════════════════════════════════
    # PHASE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    def _run_phase(self):
        """Execute actions appropriate for the current phase."""
        if self._phase == EvolutionPhase.OBSERVING:
            # Just let the collector and recognizer do their work
            pass

        elif self._phase == EvolutionPhase.ANALYZING:
            # Check if pattern recognizer has new recommendations
            recs = self.recognizer.get_recommendations()
            if recs:
                self._record_phase_metric("recommendations_available", len(recs))

        elif self._phase == EvolutionPhase.INTROSPECTING:
            # Trigger a code scan if stale
            overview = self.introspector.get_system_overview()
            self._record_phase_metric("code_health", overview.get("overall_health", 0.5))

        elif self._phase == EvolutionPhase.OPTIMIZING:
            # Check rate limit
            if self._can_optimize():
                # Let the optimizer work (it has its own loop)
                active_tests = self.optimizer.get_active_tests()
                deployed = self.optimizer.get_deployed_optimizations()
                
                # Track new deployments for this generation
                if self._current_generation:
                    for dep in deployed:
                        if dep["id"] not in self._current_generation.optimizations_deployed:
                            self._current_generation.optimizations_deployed.append(dep["id"])
                            self._optimizations_this_hour += 1
                            self._total_improvements += 1

        elif self._phase == EvolutionPhase.DISTILLING:
            # Feed confirmed patterns to distiller
            top_patterns = self.recognizer.get_top_patterns(20)
            for pattern in top_patterns:
                if pattern.strength in (PatternStrength.ESTABLISHED, PatternStrength.LAW):
                    self.distiller.submit_pattern(pattern)

        elif self._phase == EvolutionPhase.CONSOLIDATING:
            # Let things settle, monitor for regressions
            pass

        elif self._phase == EvolutionPhase.RESTING:
            # Minimal activity, just monitoring
            pass

        elif self._phase == EvolutionPhase.ROLLING_BACK:
            self._execute_rollback()

    def _advance_phase(self):
        """Advance to the next phase in the evolution cycle."""
        phase_order = [
            EvolutionPhase.OBSERVING,
            EvolutionPhase.ANALYZING,
            EvolutionPhase.INTROSPECTING,
            EvolutionPhase.OPTIMIZING,
            EvolutionPhase.DISTILLING,
            EvolutionPhase.CONSOLIDATING,
            EvolutionPhase.RESTING,
        ]

        # Phase durations (seconds)
        phase_durations = {
            EvolutionPhase.OBSERVING: 60,
            EvolutionPhase.ANALYZING: 30,
            EvolutionPhase.INTROSPECTING: 30,
            EvolutionPhase.OPTIMIZING: 120,
            EvolutionPhase.DISTILLING: 30,
            EvolutionPhase.CONSOLIDATING: 60,
            EvolutionPhase.RESTING: 30,
        }

        # Faster phases in aggressive mode
        if self.speed in (EvolutionSpeed.AGGRESSIVE, EvolutionSpeed.HYPERDRIVE):
            phase_durations = {k: v // 2 for k, v in phase_durations.items()}

        # Skip some phases in frozen mode
        if self.speed == EvolutionSpeed.FROZEN:
            if self._phase != EvolutionPhase.OBSERVING:
                self._phase = EvolutionPhase.OBSERVING
            return

        # Don't advance from ROLLING_BACK until complete
        if self._phase == EvolutionPhase.ROLLING_BACK:
            return

        # Check if current phase has run long enough
        if not hasattr(self, '_phase_start'):
            self._phase_start = time.time()

        elapsed = time.time() - self._phase_start
        current_duration = phase_durations.get(self._phase, 60)

        if elapsed >= current_duration:
            # Move to next phase
            try:
                current_idx = phase_order.index(self._phase)
                next_idx = (current_idx + 1) % len(phase_order)
                self._phase = phase_order[next_idx]
            except ValueError:
                self._phase = EvolutionPhase.OBSERVING

            self._phase_start = time.time()

            # Record phase duration
            if self._current_generation:
                self._current_generation.phase_durations[self._phase.value] = elapsed

    # ═══════════════════════════════════════════════════════════════
    # GENERATION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    def _begin_generation(self):
        """Start a new evolution generation."""
        self._generation_number += 1
        gen_id = hashlib.md5(
            f"gen:{self._generation_number}:{time.time()}".encode()
        ).hexdigest()[:12]

        parent_id = self._current_generation.id if self._current_generation else None

        self._current_generation = GenerationRecord(
            id=gen_id,
            number=self._generation_number,
            started_at=time.time(),
            parent_generation=parent_id,
            speed_setting=self.speed.value,
            performance_before=self._current_performance,
        )

        # Link to parent
        if parent_id:
            for gen in self._generation_history:
                if gen.id == parent_id:
                    gen.child_generations.append(gen_id)
                    break

        self._regressions_this_generation = 0
        self._phase = EvolutionPhase.OBSERVING
        self._phase_start = time.time()

        self.collector.record_event(
            event_type=EventType.PATTERN_DISCOVERED,
            component="evolution_controller",
            data={
                "event": "generation_started",
                "generation": self._generation_number,
                "speed": self.speed.value,
            },
            tags={"generation", "lifecycle"},
        )

    def _end_generation(self):
        """End the current generation and record results."""
        if not self._current_generation:
            return

        gen = self._current_generation
        gen.ended_at = time.time()
        gen.performance_after = self._current_performance
        gen.improvement_delta = gen.performance_after - gen.performance_before

        # Count patterns discovered during this generation
        gen.patterns_discovered = len(self.recognizer.get_top_patterns(100))

        # Generate report
        report = self._generate_report(gen)

        # Save generation
        self._generation_history.append(gen)
        self._save_generation(gen)

        # Log
        status = "✓" if gen.was_successful else "✗"
        print(f"\n  [{status}] Generation #{gen.number} complete "
              f"({gen.duration_hours:.1f}h, Δ={gen.improvement_delta:+.4f})")

        self.collector.record_event(
            event_type=EventType.PATTERN_DISCOVERED,
            component="evolution_controller",
            data={
                "event": "generation_ended",
                "generation": gen.number,
                "improvement": gen.improvement_delta,
                "successful": gen.was_successful,
            },
            outcome=gen.improvement_delta,
            tags={"generation", "lifecycle"},
        )

    def _should_end_generation(self) -> bool:
        """Check if the current generation should end."""
        if not self._current_generation:
            return True

        gen = self._current_generation
        elapsed = time.time() - gen.started_at

        # Time-based ending
        if elapsed >= self.generation_duration:
            return True

        # Too many regressions — end early and possibly roll back
        if self._regressions_this_generation >= self.max_regressions:
            return True

        # Critical instability — emergency end
        if self._stability == SystemStability.CRITICAL:
            return True

        return False

    def rollback_generation(self, generation_id: str = None) -> bool:
        """
        Roll back an entire generation's changes.
        
        If no generation_id specified, rolls back the current/last generation.
        """
        target = None

        if generation_id:
            for gen in self._generation_history:
                if gen.id == generation_id:
                    target = gen
                    break
        else:
            target = self._current_generation or (
                self._generation_history[-1] if self._generation_history else None
            )

        if not target:
            return False

        print(f"\n  [ROLLBACK] Rolling back generation #{target.number}...")

        # Revert all optimizations from this generation
        for opt_id in target.optimizations_deployed:
            self.optimizer.revert_optimization(opt_id)

        target.reverted = True
        target.revert_reason = "manual_rollback"
        self._total_regressions += len(target.optimizations_deployed)

        self.collector.record_event(
            event_type=EventType.PATCH_REVERTED,
            component="evolution_controller",
            data={
                "event": "generation_rolled_back",
                "generation": target.number,
                "optimizations_reverted": len(target.optimizations_deployed),
            },
            outcome=-0.5,
            tags={"rollback", "generation"},
        )

        return True

    # ═══════════════════════════════════════════════════════════════
    # SPEED CONTROL
    # ═══════════════════════════════════════════════════════════════

    def _adjust_speed(self):
        """Dynamically adjust evolution speed based on conditions."""
        if self.speed == EvolutionSpeed.FROZEN:
            return  # Frozen is explicit, don't auto-adjust

        # Calculate stability score (0-1)
        stability_score = self._calculate_stability_score()

        # Calculate improvement velocity
        velocity = self._calculate_improvement_velocity()

        # Decision logic
        if stability_score < 0.3:
            # Very unstable — slow way down
            self._adjust_speed_down("low_stability")
        elif self._regressions_this_generation >= 2:
            # Multiple regressions — slow down
            self._adjust_speed_down("regressions")
        elif stability_score > self.min_stability_aggressive and velocity < 0.001:
            # Stable but plateaued — speed up to explore
            self._adjust_speed_up("plateau_detected")
        elif stability_score > 0.9 and velocity > 0.01:
            # Very stable and improving — speed up
            self._adjust_speed_up("good_conditions")

    def _adjust_speed_up(self, reason: str):
        """Increase evolution speed."""
        speed_order = [
            EvolutionSpeed.FROZEN,
            EvolutionSpeed.CAUTIOUS,
            EvolutionSpeed.NORMAL,
            EvolutionSpeed.AGGRESSIVE,
            EvolutionSpeed.HYPERDRIVE,
        ]

        current_idx = speed_order.index(self.speed)
        if current_idx < len(speed_order) - 1:
            self.speed = speed_order[current_idx + 1]
            print(f"  [Speed ↑] {self.speed.value} (reason: {reason})")

    def _adjust_speed_down(self, reason: str):
        """Decrease evolution speed."""
        speed_order = [
            EvolutionSpeed.FROZEN,
            EvolutionSpeed.CAUTIOUS,
            EvolutionSpeed.NORMAL,
            EvolutionSpeed.AGGRESSIVE,
            EvolutionSpeed.HYPERDRIVE,
        ]

        current_idx = speed_order.index(self.speed)
        if current_idx > 1:  # Don't go below CAUTIOUS automatically
            self.speed = speed_order[current_idx - 1]
            print(f"  [Speed ↓] {self.speed.value} (reason: {reason})")

    def _can_optimize(self) -> bool:
        """Check if we're allowed to deploy another optimization."""
        limit = self._speed_limits.get(self.speed, 0)
        return self._optimizations_this_hour < limit

    def set_speed(self, speed: EvolutionSpeed):
        """Manually set evolution speed."""
        self.speed = speed
        print(f"  [Speed] Manually set to: {speed.value}")

    # ═══════════════════════════════════════════════════════════════
    # STABILITY & METRICS
    # ═══════════════════════════════════════════════════════════════

    def _assess_stability(self):
        """Assess current system stability."""
        health = self.collector.get_system_health()
        health_score = health.get("health", 0.5)
        error_rate = health.get("error_rate", 0.0)

        if health_score > 0.8 and error_rate < 0.05:
            self._stability = SystemStability.STABLE
        elif health_score > 0.6 and error_rate < 0.15:
            self._stability = SystemStability.SLIGHTLY_UNSTABLE
        elif health_score > 0.3:
            self._stability = SystemStability.UNSTABLE
        else:
            self._stability = SystemStability.CRITICAL
            # Emergency: freeze evolution
            if self.speed != EvolutionSpeed.FROZEN:
                self.speed = EvolutionSpeed.CAUTIOUS
                print("  [STABILITY] Critical instability — speed reduced to CAUTIOUS")

    def _update_metrics(self):
        """Update real-time evolution metrics."""
        # Get system health
        health = self.collector.get_system_health()
        self._current_performance = health.get("health", 0.5)
        self._performance_window.append(self._current_performance)
        self._metrics.performance_history.append(
            (time.time(), self._current_performance)
        )

        # Strategy effectiveness from optimizer
        strategy_eff = self.optimizer.get_strategy_effectiveness()
        self._metrics.strategy_effectiveness = {
            k: v.get("effectiveness", 0) for k, v in strategy_eff.items()
        }
        if strategy_eff:
            best = max(strategy_eff.items(), key=lambda x: x[1].get("effectiveness", 0))
            worst = min(strategy_eff.items(), key=lambda x: x[1].get("effectiveness", 0))
            self._metrics.best_strategy = best[0]
            self._metrics.worst_strategy = worst[0]

        # Knowledge base size
        self._metrics.knowledge_base_size = self.distiller.kb.size

    def _calculate_stability_score(self) -> float:
        """Calculate a 0-1 stability score."""
        if len(self._performance_window) < 5:
            return 0.7  # Assume moderate stability with little data

        values = list(self._performance_window)
        
        # Low variance = stable
        variance = statistics.variance(values) if len(values) > 1 else 0
        stability_from_variance = max(0.0, 1.0 - variance * 10)

        # No downward trend = stable
        if len(values) >= 10:
            first_half = statistics.mean(values[:len(values)//2])
            second_half = statistics.mean(values[len(values)//2:])
            trend = second_half - first_half
            stability_from_trend = 0.5 + min(0.5, max(-0.5, trend * 5))
        else:
            stability_from_trend = 0.5

        # Low regression count = stable
        stability_from_regressions = max(0.0, 1.0 - self._regressions_this_generation * 0.3)

        return (
            stability_from_variance * 0.4 +
            stability_from_trend * 0.3 +
            stability_from_regressions * 0.3
        )

    def _calculate_improvement_velocity(self) -> float:
        """Calculate rate of improvement (performance delta per hour)."""
        history = list(self._metrics.performance_history)
        if len(history) < 10:
            return 0.0

        # Use last 50 points
        recent = history[-50:]
        if len(recent) < 2:
            return 0.0

        # Simple linear regression slope
        times = [t for t, _ in recent]
        values = [v for _, v in recent]
        
        time_range = times[-1] - times[0]
        if time_range == 0:
            return 0.0

        # Normalize time to hours
        time_range_hours = time_range / 3600.0
        value_change = values[-1] - values[0]

        return value_change / max(0.01, time_range_hours)

    def _check_regressions(self):
        """Check for performance regressions."""
        if len(self._performance_window) < 10:
            return

        recent = list(self._performance_window)[-10:]
        baseline = self._baseline_performance

        # Detect regression: recent average significantly below baseline
        recent_avg = statistics.mean(recent)
        if recent_avg < baseline - 0.1:  # 10% regression
            self._regressions_this_generation += 1
            self._total_regressions += 1

            if self._regressions_this_generation >= self.max_regressions:
                print(f"  [REGRESSION] {self._regressions_this_generation} regressions detected — "
                      f"initiating rollback")
                self._phase = EvolutionPhase.ROLLING_BACK

    def _execute_rollback(self):
        """Execute a rollback of the current generation."""
        if self._current_generation:
            self.rollback_generation(self._current_generation.id)
        self._phase = EvolutionPhase.RESTING

    # ═══════════════════════════════════════════════════════════════
    # DISTILLER FEEDING
    # ═══════════════════════════════════════════════════════════════

    def _feed_distiller(self):
        """Feed confirmed patterns and deployed optimizations to the distiller."""
        # Feed successful optimizations
        deployed = self.optimizer.get_deployed_optimizations()
        for dep in deployed:
            opt_id = dep.get("id", "")
            # The optimizer's internal state has the full Optimization object
            # We simulate feeding it here
            pass  # The optimizer and distiller interact through the main loop

    # ═══════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════

    def _save_history(self):
        """Save evolution history to disk."""
        filepath = self._evolution_path / "evolution_history.json"
        data = {
            "generation_number": self._generation_number,
            "total_improvements": self._total_improvements,
            "total_regressions": self._total_regressions,
            "baseline_performance": self._baseline_performance,
            "current_performance": self._current_performance,
            "speed": self.speed.value,
            "generations": [gen.to_dict() for gen in self._generation_history[-100:]],
        }

        try:
            temp_path = filepath.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            temp_path.rename(filepath)
        except IOError as e:
            print(f"[EvolutionController] Failed to save history: {e}")

    def _save_generation(self, gen: GenerationRecord):
        """Save a single generation record."""
        gen_dir = self._evolution_path / "generations"
        gen_dir.mkdir(exist_ok=True)
        
        filepath = gen_dir / f"gen_{gen.number:05d}.json"
        try:
            with open(filepath, 'w') as f:
                json.dump(gen.to_dict(), f, indent=2)
        except IOError:
            pass

    def _load_history(self):
        """Load evolution history from disk."""
        filepath = self._evolution_path / "evolution_history.json"
        if not filepath.exists():
            return

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            self._generation_number = data.get("generation_number", 0)
            self._total_improvements = data.get("total_improvements", 0)
            self._total_regressions = data.get("total_regressions", 0)
            self._baseline_performance = data.get("baseline_performance", 0.5)
            self._current_performance = data.get("current_performance", 0.5)
            
            speed_str = data.get("speed", "normal")
            try:
                self.speed = EvolutionSpeed(speed_str)
            except ValueError:
                self.speed = EvolutionSpeed.NORMAL

        except (IOError, json.JSONDecodeError) as e:
            print(f"[EvolutionController] Failed to load history: {e}")

    # ═══════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════

    def _record_phase_metric(self, metric: str, value: Any):
        """Record a metric from the current phase."""
        pass  # Could feed to collector if needed

    def _generate_report(self, gen: GenerationRecord) -> GenerationReport:
        """Generate a summary report for a generation."""
        return GenerationReport(
            generation_id=gen.id,
            generation_number=gen.number,
            duration_hours=gen.duration_hours,
            optimizations_deployed=len(gen.optimizations_deployed),
            rules_distilled=len(gen.rules_created),
            patterns_found=gen.patterns_discovered,
            overall_improvement=gen.improvement_delta,
            stability=self._stability.value,
            regressions_detected=self._regressions_this_generation,
            speed_used=gen.speed_setting,
            was_successful=gen.was_successful,
        )

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC INTERFACE
    # ═══════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive evolution status."""
        gen_info = None
        if self._current_generation:
            gen_info = {
                "number": self._current_generation.number,
                "duration_hours": self._current_generation.duration_hours,
                "optimizations": len(self._current_generation.optimizations_deployed),
                "improvement_so_far": self._current_performance - self._current_generation.performance_before,
            }

        return {
            "phase": self._phase.value,
            "speed": self.speed.value,
            "stability": self._stability.value,
            "generation": gen_info,
            "performance": {
                "current": self._current_performance,
                "baseline": self._baseline_performance,
                "total_improvement": self._current_performance - self._baseline_performance,
                "velocity": self._calculate_improvement_velocity(),
            },
            "lifetime": {
                "total_generations": self._generation_number,
                "successful_generations": sum(
                    1 for g in self._generation_history if g.was_successful
                ),
                "total_improvements": self._total_improvements,
                "total_regressions": self._total_regressions,
                "success_rate": (
                    sum(1 for g in self._generation_history if g.was_successful) /
                    max(1, len(self._generation_history))
                ),
            },
            "subsystems": {
                "collector": self.collector.get_system_health(),
                "recognizer": self.recognizer.get_status(),
                "optimizer": self.optimizer.get_status(),
                "distiller": self.distiller.get_status(),
                "introspector": self.introspector.get_system_overview() if self.introspector._file_profiles else {},
            },
            "metrics": {
                "best_strategy": self._metrics.best_strategy,
                "worst_strategy": self._metrics.worst_strategy,
                "knowledge_base_size": self._metrics.knowledge_base_size,
            },
        }

    def get_generation_history(self, last_n: int = 20) -> List[Dict[str, Any]]:
        """Get recent generation history."""
        return [gen.to_dict() for gen in self._generation_history[-last_n:]]

    def get_lineage(self, generation_id: str) -> Dict[str, Any]:
        """Get the lineage (ancestry) of a generation."""
        lineage = []
        current_id = generation_id

        while current_id:
            gen = None
            for g in self._generation_history:
                if g.id == current_id:
                    gen = g
                    break
            if gen:
                lineage.append(gen.to_dict())
                current_id = gen.parent_generation
            else:
                break

        return {
            "generation_id": generation_id,
            "lineage_depth": len(lineage),
            "ancestors": lineage,
        }

    def get_improvement_trajectory(self) -> List[Tuple[float, float]]:
        """Get the performance trajectory over time."""
        return list(self._metrics.performance_history)

    def force_generation_end(self):
        """Manually end the current generation."""
        if self._current_generation:
            self._end_generation()
            self._begin_generation()

    def freeze(self):
        """Freeze evolution — no more changes."""
        self.speed = EvolutionSpeed.FROZEN
        print("  [FROZEN] Evolution halted")

    def unfreeze(self, speed: EvolutionSpeed = EvolutionSpeed.NORMAL):
        """Unfreeze evolution."""
        self.speed = speed
        print(f"  [UNFROZEN] Evolution resumed at {speed.value}")


# ── Stub: evolve expected by __init__.py decorator ────────────────────────────
def _ec_evolve(self, *args, **kwargs) -> dict:
    """Stub: run an evolution pass."""
    return {}

EvolutionController.evolve = _ec_evolve
