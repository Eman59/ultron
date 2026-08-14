"""
Data Pipeline Bootstrap — Kickstarting the Learning Flywheel.

The self-learning system needs DATA to learn from. But when it first starts,
the experience collector is empty — no patterns, no traces, no knowledge.

This bootstrap module solves the cold-start problem by:

  1. SCANNING the existing codebase to generate structural events
  2. PROFILING every component to create baseline performance data
  3. SIMULATING decision traces from the autonomy loop's design
  4. SEEDING the pattern recognizer with known architectural patterns
  5. PRE-LOADING knowledge rules from the codebase conventions
  6. RUNNING the code introspector to build the dependency graph
  7. BENCHMARKING component interactions to establish baselines
  8. GENERATING synthetic A/B test data to warm up the optimizer

After bootstrap, the system has enough "experience" to start finding
real patterns and making real improvements — the flywheel begins spinning.

Usage:
    from self_improvement.learning.bootstrap import Bootstrap
    bootstrap = Bootstrap(project_root="/path/to/ultron")
    bootstrap.run_full_bootstrap()
"""

import os
import time
import json
import hashlib
import random
import ast
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

from .experience_collector import ExperienceCollector, EventType
from .pattern_recognizer import PatternRecognizer, PatternType, PatternStrength
from .code_introspector import CodeIntrospector
from .knowledge_distiller import KnowledgeDistiller, DistilledRule, RuleType, RuleConfidence
from .adaptive_optimizer import AdaptiveOptimizer
from .codebase_agent import CodebaseAgent


@dataclass
class BootstrapReport:
    """Report of what the bootstrap accomplished."""
    started_at: float = 0.0
    completed_at: float = 0.0
    
    # What was generated
    events_seeded: int = 0
    traces_created: int = 0
    patterns_seeded: int = 0
    rules_pre_loaded: int = 0
    files_profiled: int = 0
    functions_analyzed: int = 0
    components_benchmarked: int = 0
    
    # Quality
    codebase_health_score: float = 0.0
    total_lines_scanned: int = 0
    hotspots_found: int = 0
    dead_code_found: int = 0
    
    @property
    def duration_seconds(self) -> float:
        return self.completed_at - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration_seconds": self.duration_seconds,
            "events_seeded": self.events_seeded,
            "traces_created": self.traces_created,
            "patterns_seeded": self.patterns_seeded,
            "rules_pre_loaded": self.rules_pre_loaded,
            "files_profiled": self.files_profiled,
            "functions_analyzed": self.functions_analyzed,
            "codebase_health": self.codebase_health_score,
            "total_lines": self.total_lines_scanned,
            "hotspots": self.hotspots_found,
            "dead_code": self.dead_code_found,
        }


class Bootstrap:
    """
    Bootstraps the self-learning system from cold start.
    
    Generates enough initial data for the learning pipeline to
    begin discovering real patterns and making real improvements.
    """

    def __init__(self,
                 project_root: str,
                 collector: ExperienceCollector = None,
                 introspector: CodeIntrospector = None,
                 distiller: KnowledgeDistiller = None,
                 codebase: CodebaseAgent = None):
        """
        Args:
            project_root: Root of the Ultron project
            collector: Experience collector (created if not provided)
            introspector: Code introspector (created if not provided)
            distiller: Knowledge distiller (created if not provided)
            codebase: Codebase agent (created if not provided)
        """
        self.project_root = Path(project_root)

        # Use provided subsystems or create temporary ones
        self.collector = collector or ExperienceCollector(
            max_buffer_size=100_000,
            long_term_path=str(self.project_root / "data" / "knowledge" / "traces"),
        )
        self.introspector = introspector or CodeIntrospector(
            project_root=str(self.project_root),
        )
        self.distiller = distiller or KnowledgeDistiller(
            knowledge_path=str(self.project_root / "data" / "knowledge"),
        )
        self.codebase = codebase or CodebaseAgent(project_root=str(self.project_root))

        self._report = BootstrapReport()

    def run_full_bootstrap(self) -> BootstrapReport:
        """
        Run the complete bootstrap sequence.
        
        This is the main entry point. Call once when the system first starts
        or after a full reset.
        """
        self._report.started_at = time.time()

        print("=" * 70)
        print("  ULTRON SELF-LEARNING BOOTSTRAP")
        print("=" * 70)

        # Phase 1: Scan and profile the codebase
        print("\n  [1/7] Scanning codebase structure...")
        self._phase_scan_codebase()

        # Phase 2: Generate structural events
        print("  [2/7] Generating structural events...")
        self._phase_generate_structural_events()

        # Phase 3: Simulate autonomy loop traces
        print("  [3/7] Simulating decision traces...")
        self._phase_simulate_traces()

        # Phase 4: Seed known patterns
        print("  [4/7] Seeding architectural patterns...")
        self._phase_seed_patterns()

        # Phase 5: Pre-load knowledge rules
        print("  [5/7] Pre-loading knowledge rules...")
        self._phase_preload_rules()

        # Phase 6: Profile component interactions
        print("  [6/7] Profiling component interactions...")
        self._phase_profile_interactions()

        # Phase 7: Generate baseline metrics
        print("  [7/7] Generating baseline metrics...")
        self._phase_generate_baselines()

        self._report.completed_at = time.time()

        print(f"\n  Bootstrap complete in {self._report.duration_seconds:.1f}s")
        print(f"  Events seeded: {self._report.events_seeded}")
        print(f"  Patterns seeded: {self._report.patterns_seeded}")
        print(f"  Rules loaded: {self._report.rules_pre_loaded}")
        print(f"  Files profiled: {self._report.files_profiled}")
        print(f"  Codebase health: {self._report.codebase_health_score:.2f}")
        print("=" * 70)

        # Save the report
        self._save_report()

        return self._report

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1: Scan codebase
    # ═══════════════════════════════════════════════════════════════

    def _phase_scan_codebase(self):
        """Run the code introspector for full codebase analysis."""
        scan_result = self.introspector.full_scan()
        
        self._report.files_profiled = scan_result.get("total_profiled", 0)
        
        overview = self.introspector.get_system_overview()
        self._report.total_lines_scanned = overview.get("total_lines", 0)
        self._report.functions_analyzed = overview.get("total_functions", 0)
        self._report.codebase_health_score = overview.get("overall_health", 0.5)
        self._report.hotspots_found = len(self.introspector.get_hotspots(50))
        self._report.dead_code_found = len(self.introspector.get_dead_code())

        print(f"    {self._report.files_profiled} files, "
              f"{self._report.total_lines_scanned} lines, "
              f"{self._report.functions_analyzed} functions")

    # ═══════════════════════════════════════════════════════════════
    # PHASE 2: Generate structural events
    # ═══════════════════════════════════════════════════════════════

    def _phase_generate_structural_events(self):
        """Create events representing the existing codebase structure."""
        count = 0

        # Event for each component's existence and health
        for name, profile in self.introspector.get_component_profiles().items():
            self.collector.record_event(
                event_type=EventType.PERFORMANCE_MEASURED,
                component=name,
                data={
                    "type": "component_profile",
                    "total_files": profile.total_files,
                    "total_lines": profile.total_lines,
                    "total_functions": profile.total_functions,
                    "avg_complexity": profile.avg_complexity,
                    "max_complexity": profile.max_complexity,
                    "health_score": profile.health_score,
                    "health": profile.health.value,
                    "dead_code_pct": profile.dead_code_percentage,
                    "tech_debt_hours": profile.technical_debt_hours,
                },
                outcome=profile.health_score,
                tags={"bootstrap", "structure", "component"},
            )
            count += 1

        # Event for each complexity hotspot
        for func in self.introspector.get_hotspots(30):
            self.collector.record_event(
                event_type=EventType.PERFORMANCE_MEASURED,
                component=func.file_path.split('/')[0] if '/' in func.file_path else "root",
                data={
                    "type": "complexity_hotspot",
                    "function": func.name,
                    "file": func.file_path,
                    "cyclomatic_complexity": func.cyclomatic_complexity,
                    "cognitive_complexity": func.cognitive_complexity,
                    "nesting_depth": func.nesting_depth,
                    "line_count": func.line_count,
                    "health_score": func.health_score,
                },
                outcome=func.health_score - 1.0,  # Negative for hotspots
                tags={"bootstrap", "hotspot", "complexity"},
            )
            count += 1

        # Event for dependency graph characteristics
        dep_map = self.introspector.get_dependency_map()
        if dep_map.circular_dependencies:
            self.collector.record_event(
                event_type=EventType.ERROR_OCCURRED,
                component="architecture",
                data={
                    "type": "circular_dependencies",
                    "count": len(dep_map.circular_dependencies),
                    "cycles": [str(c[:3]) for c in dep_map.circular_dependencies[:5]],
                },
                outcome=-0.3,
                tags={"bootstrap", "architecture", "circular_dep"},
            )
            count += 1

        if dep_map.bottleneck_nodes:
            self.collector.record_event(
                event_type=EventType.PERFORMANCE_MEASURED,
                component="architecture",
                data={
                    "type": "bottleneck_nodes",
                    "nodes": dep_map.bottleneck_nodes[:10],
                    "count": len(dep_map.bottleneck_nodes),
                },
                outcome=-0.2,
                tags={"bootstrap", "architecture", "bottleneck"},
            )
            count += 1

        self._report.events_seeded += count

    # ═══════════════════════════════════════════════════════════════
    # PHASE 3: Simulate decision traces
    # ═══════════════════════════════════════════════════════════════

    def _phase_simulate_traces(self):
        """
        Generate synthetic execution traces that represent typical
        autonomy loop behavior based on the architecture design.
        """
        traces_created = 0

        # Simulate various typical scenarios
        scenarios = [
            self._simulate_learn_cycle,
            self._simulate_explore_cycle,
            self._simulate_defend_cycle,
            self._simulate_consolidate_cycle,
            self._simulate_error_recovery,
            self._simulate_optimization_cycle,
            self._simulate_goal_completion,
        ]

        for scenario_fn in scenarios:
            for _ in range(5):  # 5 instances of each scenario
                trace_id = self.collector.begin_trace(
                    description=f"bootstrap:{scenario_fn.__name__}",
                    tags={"bootstrap", "simulated"},
                )
                event_count = scenario_fn(trace_id)
                
                # End with a plausible outcome
                outcome = random.uniform(0.2, 0.9)
                self.collector.end_trace(trace_id, outcome=outcome)
                traces_created += 1
                self._report.events_seeded += event_count

        self._report.traces_created = traces_created

    def _simulate_learn_cycle(self, trace_id: str) -> int:
        """Simulate: Observe → Learn → Consolidate."""
        events = 0

        # Decision to learn
        self.collector.record_event(
            event_type=EventType.DECISION_MADE,
            component="core_agent",
            data={"action_type": "Learn", "confidence": 0.75, "target": "new_domain",
                  "reasoning": ["curiosity high", "learning potential detected"]},
            trace_id=trace_id,
            tags={"decision", "learn"},
        )
        events += 1

        # Execute learning
        self.collector.record_event(
            event_type=EventType.ACTION_OUTCOME,
            component="core_agent",
            data={"action_type": "Learn", "success": True, "utility": 0.6},
            duration_us=random.randint(10000, 50000),
            outcome=0.6,
            trace_id=trace_id,
            tags={"outcome", "learn"},
        )
        events += 1

        # Consolidate
        self.collector.record_event(
            event_type=EventType.ACTION_OUTCOME,
            component="core_agent",
            data={"action_type": "Consolidate", "success": True, "utility": 0.3},
            duration_us=random.randint(5000, 20000),
            outcome=0.3,
            trace_id=trace_id,
            tags={"outcome", "consolidate"},
        )
        events += 1

        return events

    def _simulate_explore_cycle(self, trace_id: str) -> int:
        """Simulate: High curiosity → Explore → Discover."""
        events = 0

        self.collector.record_event(
            event_type=EventType.DRIVE_CHANGE,
            component="core_agent",
            data={"curiosity": 0.85, "trigger": "stagnation"},
            trace_id=trace_id,
            tags={"drives", "curiosity"},
        )
        events += 1

        self.collector.record_event(
            event_type=EventType.DECISION_MADE,
            component="core_agent",
            data={"action_type": "Explore", "confidence": 0.65, "target": "unknown_space"},
            trace_id=trace_id,
            tags={"decision", "explore"},
        )
        events += 1

        success = random.random() > 0.3
        self.collector.record_event(
            event_type=EventType.ACTION_OUTCOME,
            component="core_agent",
            data={"action_type": "Explore", "success": success,
                  "utility": 0.7 if success else 0.1},
            duration_us=random.randint(20000, 100000),
            outcome=0.7 if success else -0.1,
            trace_id=trace_id,
            tags={"outcome", "explore"},
        )
        events += 1

        return events

    def _simulate_defend_cycle(self, trace_id: str) -> int:
        """Simulate: Threat detected → Defend → Recover."""
        events = 0

        self.collector.record_event(
            event_type=EventType.STATE_TRANSITION,
            component="core_agent",
            data={"from": "Observing", "to": "Surviving", "reason": "threat_detected"},
            trace_id=trace_id,
            tags={"state", "threat"},
        )
        events += 1

        self.collector.record_event(
            event_type=EventType.DECISION_MADE,
            component="core_agent",
            data={"action_type": "Defend", "confidence": 0.9, "target": "perimeter"},
            trace_id=trace_id,
            tags={"decision", "defend"},
        )
        events += 1

        self.collector.record_event(
            event_type=EventType.ACTION_OUTCOME,
            component="core_agent",
            data={"action_type": "Defend", "success": True, "utility": 0.8},
            duration_us=random.randint(5000, 15000),
            outcome=0.8,
            trace_id=trace_id,
            tags={"outcome", "defend"},
        )
        events += 1

        return events

    def _simulate_consolidate_cycle(self, trace_id: str) -> int:
        """Simulate: Low resources → Consolidate → Recover."""
        events = 0

        self.collector.record_event(
            event_type=EventType.PERFORMANCE_MEASURED,
            component="core_agent",
            data={"cpu_available": 0.2, "memory_available": 0.3, "trigger": "resource_low"},
            outcome=-0.3,
            trace_id=trace_id,
            tags={"resources", "low"},
        )
        events += 1

        self.collector.record_event(
            event_type=EventType.DECISION_MADE,
            component="core_agent",
            data={"action_type": "Consolidate", "confidence": 0.8},
            trace_id=trace_id,
            tags={"decision", "consolidate"},
        )
        events += 1

        self.collector.record_event(
            event_type=EventType.ACTION_OUTCOME,
            component="core_agent",
            data={"action_type": "Consolidate", "success": True, "utility": 0.5,
                  "resources_freed": 0.3},
            duration_us=random.randint(30000, 80000),
            outcome=0.5,
            trace_id=trace_id,
            tags={"outcome", "consolidate"},
        )
        events += 1

        return events

    def _simulate_error_recovery(self, trace_id: str) -> int:
        """Simulate: Error → Diagnosis → Recovery."""
        events = 0

        self.collector.record_event(
            event_type=EventType.ERROR_OCCURRED,
            component=random.choice(["meta_learning", "neural_mesh", "data_pipeline"]),
            data={"error_type": "timeout", "message": "Operation timed out",
                  "severity": 0.4},
            outcome=-0.4,
            trace_id=trace_id,
            tags={"error", "timeout"},
        )
        events += 1

        self.collector.record_event(
            event_type=EventType.RECOVERY_STARTED,
            component="core_agent",
            data={"recovery_type": "retry_with_backoff"},
            trace_id=trace_id,
            tags={"recovery"},
        )
        events += 1

        self.collector.record_event(
            event_type=EventType.RECOVERY_COMPLETED,
            component="core_agent",
            data={"success": True, "attempts": 2},
            outcome=0.3,
            trace_id=trace_id,
            tags={"recovery", "success"},
        )
        events += 1

        return events

    def _simulate_optimization_cycle(self, trace_id: str) -> int:
        """Simulate: Bottleneck found → Optimize → Measure."""
        events = 0

        self.collector.record_event(
            event_type=EventType.PATTERN_DISCOVERED,
            component="pattern_recognizer",
            data={"pattern_type": "bottleneck", "component": "meta_learning",
                  "description": "Strategy optimizer taking >100ms"},
            trace_id=trace_id,
            tags={"pattern", "bottleneck"},
        )
        events += 1

        self.collector.record_event(
            event_type=EventType.OPTIMIZATION_APPLIED,
            component="adaptive_optimizer",
            data={"strategy": "parameter_tuning", "target": "meta_learning",
                  "change": "increased cache_size from 256 to 512"},
            outcome=0.2,
            trace_id=trace_id,
            tags={"optimization", "parameter"},
        )
        events += 1

        return events

    def _simulate_goal_completion(self, trace_id: str) -> int:
        """Simulate: Goal created → Progress → Completion."""
        events = 0

        goal_id = f"goal_{random.randint(1000, 9999)}"
        self.collector.record_event(
            event_type=EventType.GOAL_CREATED,
            component="core_agent",
            data={"goal_id": goal_id, "goal_type": "learning",
                  "description": "Learn new optimization strategy"},
            trace_id=trace_id,
            tags={"goal", "created"},
        )
        events += 1

        self.collector.record_event(
            event_type=EventType.GOAL_COMPLETED,
            component="core_agent",
            data={"goal_id": goal_id, "progress": 1.0, "utility": 0.7},
            outcome=0.7,
            trace_id=trace_id,
            tags={"goal", "completed"},
        )
        events += 1

        return events

    # ═══════════════════════════════════════════════════════════════
    # PHASE 4: Seed known patterns
    # ═══════════════════════════════════════════════════════════════

    def _phase_seed_patterns(self):
        """Pre-load known architectural patterns as discovered patterns."""
        count = 0

        # These are patterns we KNOW exist based on the architecture
        known_patterns = [
            {
                "type": "temporal_sequence",
                "description": "OODA loop: Observe → Orient → Decide → Act reliably produces good outcomes",
                "sequence": ["state_transition:core_agent", "decision_made:core_agent", "action_outcome:core_agent"],
                "outcome": 0.6,
                "components": ["core_agent"],
            },
            {
                "type": "correlation",
                "description": "High curiosity drive correlates with successful exploration outcomes",
                "sequence": ["drive_change:core_agent", "decision_made:core_agent"],
                "outcome": 0.5,
                "components": ["core_agent"],
            },
            {
                "type": "anti_pattern",
                "description": "Exploring when resources are low leads to failures",
                "sequence": ["performance_measured:core_agent", "decision_made:core_agent", "error_occurred:core_agent"],
                "outcome": -0.4,
                "components": ["core_agent"],
            },
            {
                "type": "bottleneck",
                "description": "Meta-learning strategy optimization is the latency bottleneck",
                "sequence": ["algorithm_evaluated:meta_learning"],
                "outcome": -0.2,
                "components": ["meta_learning"],
            },
            {
                "type": "recovery",
                "description": "Retry-with-backoff successfully recovers from transient errors",
                "sequence": ["error_occurred:*", "recovery_started:core_agent", "recovery_completed:core_agent"],
                "outcome": 0.5,
                "components": ["core_agent"],
            },
            {
                "type": "resonance",
                "description": "Neural evolution and meta-learning improve together when synchronized",
                "sequence": ["neural_evolution:neural_mesh", "algorithm_generated:meta_learning"],
                "outcome": 0.7,
                "components": ["neural_mesh", "meta_learning"],
            },
        ]

        for p in known_patterns:
            # Record as a discovered pattern event
            self.collector.record_event(
                event_type=EventType.PATTERN_DISCOVERED,
                component="bootstrap",
                data={
                    "pattern_type": p["type"],
                    "description": p["description"],
                    "sequence": p["sequence"],
                    "outcome": p["outcome"],
                    "components": p["components"],
                    "is_seeded": True,
                    "confidence": 0.7,
                },
                outcome=abs(p["outcome"]),
                tags={"bootstrap", "seeded_pattern", p["type"]},
            )
            count += 1

        self._report.patterns_seeded = count

    # ═══════════════════════════════════════════════════════════════
    # PHASE 5: Pre-load knowledge rules
    # ═══════════════════════════════════════════════════════════════

    def _phase_preload_rules(self):
        """Load foundational rules derived from the architecture design."""
        rules = [
            # INSTINCTS (fastest reactions)
            DistilledRule(
                id="rule_instinct_defend",
                rule_type=RuleType.INSTINCT,
                confidence=RuleConfidence.CERTAIN,
                name="Immediate Defense on High Threat",
                description="When threat level exceeds 0.8, immediately switch to defense mode",
                condition={"metric_above": ["threat_level", 0.8]},
                condition_readable="When threat_level > 0.8",
                action={"type": "immediate_action", "action": "Defend", "priority": 10},
                action_readable="IMMEDIATELY switch to Defend mode",
                evidence_count=100,  # Architectural invariant
                times_triggered=0,
                times_correct=0,
                applicable_components=["core_agent"],
                tags={"instinct", "defense", "architectural"},
            ),
            DistilledRule(
                id="rule_instinct_resource",
                rule_type=RuleType.INSTINCT,
                confidence=RuleConfidence.CERTAIN,
                name="Rest When Resources Critical",
                description="When CPU or memory below 10%, reduce activity immediately",
                condition={"metric_below": ["resources", 0.1]},
                condition_readable="When resources < 10%",
                action={"type": "immediate_action", "action": "Rest", "priority": 9},
                action_readable="IMMEDIATELY reduce activity (Rest mode)",
                evidence_count=100,
                applicable_components=["core_agent"],
                tags={"instinct", "resources", "architectural"},
            ),

            # TABOOS (things that must never happen)
            DistilledRule(
                id="rule_taboo_explore_low_resources",
                rule_type=RuleType.TABOO,
                confidence=RuleConfidence.CONFIDENT,
                name="Never Explore When Resources Low",
                description="Exploring when resources < 30% reliably causes failures",
                condition={"metric_below": ["resources", 0.3], "event_type": "Explore"},
                condition_readable="When trying to Explore with resources < 30%",
                action={"type": "block", "reason": "Resources too low for exploration"},
                action_readable="BLOCK exploration action — will cause failure",
                evidence_count=50,
                applicable_components=["core_agent"],
                tags={"taboo", "resources", "exploration"},
            ),
            DistilledRule(
                id="rule_taboo_evolve_unstable",
                rule_type=RuleType.TABOO,
                confidence=RuleConfidence.CONFIDENT,
                name="Never Self-Modify When Unstable",
                description="Self-modification during instability compounds problems",
                condition={"state": "unstable", "event_type": "Evolve"},
                condition_readable="When system is unstable and trying to self-modify",
                action={"type": "block", "reason": "System unstable — stabilize first"},
                action_readable="BLOCK self-modification until stability restored",
                evidence_count=30,
                applicable_components=["core_agent", "evolution_controller"],
                tags={"taboo", "stability", "evolution"},
            ),

            # AXIOMS (structural invariants)
            DistilledRule(
                id="rule_axiom_ooda",
                rule_type=RuleType.AXIOM,
                confidence=RuleConfidence.CERTAIN,
                name="OODA Loop is Sacred",
                description="The Observe-Orient-Decide-Act cycle must always complete in order",
                condition={},
                condition_readable="Always true",
                action={"type": "know", "fact": "OODA cycle must complete in order: observe→orient→decide→act"},
                action_readable="KNOW: OODA cycle is invariant — never skip steps",
                evidence_count=1000,
                applicable_components=["core_agent"],
                tags={"axiom", "ooda", "architectural"},
            ),
            DistilledRule(
                id="rule_axiom_memory_persist",
                rule_type=RuleType.AXIOM,
                confidence=RuleConfidence.CERTAIN,
                name="Memory Must Persist",
                description="Drive state and learned knowledge must survive restarts",
                condition={},
                condition_readable="Always true",
                action={"type": "know", "fact": "All drive states and knowledge must be persisted before shutdown"},
                action_readable="KNOW: Always persist state before shutdown",
                evidence_count=1000,
                applicable_components=["core_agent", "knowledge_distiller"],
                tags={"axiom", "memory", "persistence"},
            ),

            # RULES (conditional heuristics)
            DistilledRule(
                id="rule_curiosity_stagnation",
                rule_type=RuleType.RULE,
                confidence=RuleConfidence.CONFIDENT,
                name="Increase Curiosity on Stagnation",
                description="When progress stalls, increasing curiosity drive helps",
                condition={"metric_above": ["stagnation_time", 300]},
                condition_readable="When no goal progress for 5+ minutes",
                action={"type": "drive_adjust", "curiosity": 0.1, "direction": "increase"},
                action_readable="Increase curiosity drive by 0.1",
                evidence_count=25,
                avg_outcome_when_followed=0.4,
                avg_outcome_when_violated=-0.1,
                applicable_components=["core_agent"],
                tags={"rule", "curiosity", "stagnation"},
            ),
            DistilledRule(
                id="rule_consolidate_after_learn",
                rule_type=RuleType.RULE,
                confidence=RuleConfidence.CONFIDENT,
                name="Consolidate After Learning Burst",
                description="After 5+ consecutive learn actions, consolidate to integrate knowledge",
                condition={"sequence_detected": ["Learn", "Learn", "Learn", "Learn", "Learn"]},
                condition_readable="After 5 consecutive Learn actions",
                action={"type": "suggest_action", "action": "Consolidate"},
                action_readable="Switch to Consolidate to integrate what was learned",
                evidence_count=20,
                avg_outcome_when_followed=0.5,
                applicable_components=["core_agent"],
                tags={"rule", "consolidation", "learning"},
            ),
            DistilledRule(
                id="rule_parallel_neural_meta",
                rule_type=RuleType.RULE,
                confidence=RuleConfidence.PROBABLE,
                name="Run Neural and Meta-Learning in Parallel",
                description="Neural evolution and meta-learning produce better results when run together",
                condition={"component": "evolution_controller"},
                condition_readable="When scheduling learning subsystems",
                action={"type": "suggest", "suggestion": "Run neural_mesh and meta_learning simultaneously"},
                action_readable="Run neural evolution and meta-learning in parallel for synergy",
                evidence_count=15,
                avg_outcome_when_followed=0.6,
                applicable_components=["evolution_controller"],
                tags={"rule", "parallelism", "synergy"},
            ),

            # PRIORS (beliefs about the system)
            DistilledRule(
                id="rule_prior_llm_accuracy",
                rule_type=RuleType.PRIOR,
                confidence=RuleConfidence.PROBABLE,
                name="LLM Code Generation Accuracy",
                description="LLM-generated patches succeed ~70% of the time after self-review",
                condition={"component": "intelligent_patcher"},
                condition_readable="When evaluating LLM patch likelihood",
                action={"type": "prior_belief", "success_probability": 0.7},
                action_readable="EXPECT 70% success rate for LLM-generated patches",
                evidence_count=10,
                applicable_components=["intelligent_patcher", "adaptive_optimizer"],
                tags={"prior", "llm", "prediction"},
            ),
            DistilledRule(
                id="rule_prior_evolution_speed",
                rule_type=RuleType.PRIOR,
                confidence=RuleConfidence.PROBABLE,
                name="Safe Evolution Speed",
                description="Normal speed (5 opts/hour) balances improvement vs stability",
                condition={"component": "evolution_controller"},
                condition_readable="When deciding evolution speed",
                action={"type": "prior_belief", "recommended_speed": "normal",
                        "max_safe_speed": "aggressive"},
                action_readable="EXPECT normal speed to be optimal for most conditions",
                evidence_count=10,
                applicable_components=["evolution_controller"],
                tags={"prior", "evolution", "speed"},
            ),
        ]

        for rule in rules:
            self.distiller.kb.add_rule(rule)
            self._report.rules_pre_loaded += 1

    # ═══════════════════════════════════════════════════════════════
    # PHASE 6: Profile component interactions
    # ═══════════════════════════════════════════════════════════════

    def _phase_profile_interactions(self):
        """Generate events representing how components interact."""
        count = 0

        # Simulate the main communication patterns
        interactions = [
            ("core_agent", "neural_mesh", "gRPC", 5),      # Frequent
            ("core_agent", "meta_learning", "gRPC", 3),    # Regular
            ("core_agent", "memory", "embedded", 20),       # Very frequent
            ("meta_learning", "neural_mesh", "event", 2),  # Occasional
            ("self_improvement", "meta_learning", "internal", 1),
            ("evolution_controller", "adaptive_optimizer", "internal", 2),
            ("experience_collector", "pattern_recognizer", "internal", 5),
        ]

        for source, target, protocol, frequency in interactions:
            for _ in range(frequency):
                latency = random.randint(100, 5000)  # Microseconds
                success = random.random() > 0.05  # 95% success rate

                self.collector.record_event(
                    event_type=EventType.ACTION_OUTCOME,
                    component=source,
                    data={
                        "type": "component_interaction",
                        "source": source,
                        "target": target,
                        "protocol": protocol,
                        "success": success,
                    },
                    duration_us=latency,
                    outcome=0.5 if success else -0.2,
                    tags={"bootstrap", "interaction", protocol},
                )
                count += 1

        self._report.events_seeded += count
        self._report.components_benchmarked = len(set(
            s for s, _, _, _ in interactions
        ))

    # ═══════════════════════════════════════════════════════════════
    # PHASE 7: Generate baseline metrics
    # ═══════════════════════════════════════════════════════════════

    def _phase_generate_baselines(self):
        """Generate baseline performance metrics for all components."""
        count = 0

        components = [
            ("core_agent", 0.7, 500),       # (name, health, avg_latency_us)
            ("neural_mesh", 0.6, 2000),
            ("meta_learning", 0.65, 5000),
            ("memory", 0.8, 200),
            ("pattern_recognizer", 0.7, 1000),
            ("adaptive_optimizer", 0.6, 3000),
            ("knowledge_distiller", 0.75, 500),
            ("code_introspector", 0.7, 10000),
        ]

        for component, base_health, avg_latency in components:
            # Generate 20 baseline measurements per component
            for i in range(20):
                health = base_health + random.uniform(-0.1, 0.1)
                latency = avg_latency + random.randint(-avg_latency // 3, avg_latency // 3)

                self.collector.record_event(
                    event_type=EventType.PERFORMANCE_MEASURED,
                    component=component,
                    data={
                        "type": "baseline_metric",
                        "health": health,
                        "latency_us": max(10, latency),
                        "error_rate": random.uniform(0.0, 0.1),
                        "throughput": random.uniform(10, 100),
                    },
                    duration_us=max(10, latency),
                    outcome=health,
                    tags={"bootstrap", "baseline", "metric"},
                )
                count += 1

        self._report.events_seeded += count

    # ═══════════════════════════════════════════════════════════════
    # SAVE
    # ═══════════════════════════════════════════════════════════════

    def _save_report(self):
        """Save the bootstrap report to disk."""
        report_path = self.project_root / "data" / "knowledge" / "bootstrap_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(report_path, 'w') as f:
                json.dump(self._report.to_dict(), f, indent=2)
        except IOError:
            pass
