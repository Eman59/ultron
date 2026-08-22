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
            "dead_code": self.dead_code_found
        }

class Bootstrap:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.experience_collector = ExperienceCollector()
        self.pattern_recognizer = PatternRecognizer()
        self.code_introspector = CodeIntrospector()
        self.knowledge_distiller = KnowledgeDistiller()
        self.adaptive_optimizer = AdaptiveOptimizer()
        self.codebase_agent = CodebaseAgent()

    def run_full_bootstrap(self):
        report = BootstrapReport()
        report.started_at = time.time()
        
        # SCANNING the existing codebase to generate structural events
        self.scan_codebase(report)
        
        # PROFILING every component to create baseline performance data
        self.profile_components(report)
        
        # SIMULATING decision traces from the autonomy loop's design
        self.simulate_decision_traces(report)
        
        # SEEDING the pattern recognizer with known architectural patterns
        self.seed_pattern_recognizer(report)
        
        # PRE-LOADING knowledge rules from the codebase conventions
        self.pre_load_knowledge_rules(report)
        
        # RUNNING the code introspector to build the dependency graph
        self.run_code_introspector(report)
        
        # BENCHMARKING component interactions to establish baselines
        self.benchmark_components(report)
        
        # GENERATING synthetic A/B test data to warm up the optimizer
        self.generate_synthetic_ab_test_data(report)
        
        report.completed_at = time.time()
        return report

    def scan_codebase(self, report: BootstrapReport):
        files_scanned = 0
        lines_scanned = 0
        hotspots_found = 0
        dead_code_found = 0
        
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r") as f:
                        lines = f.readlines()
                        lines_scanned += len(lines)
                        for line in lines:
                            # Check for hotspots and dead code
                            if "TODO" in line or "FIXME" in line:
                                hotspots_found += 1
                            if "pass" in line or "None" in line:
                                dead_code_found += 1
                    files_scanned += 1
        
        report.total_lines_scanned = lines_scanned
        report.hotspots_found = hotspots_found
        report.dead_code_found = dead_code_found
        report.files_profiled = files_scanned

    def profile_components(self, report: BootstrapReport):
        components_profiled = 0
        for component in self.codebase_agent.get_components():
            # Profile the component
            self.code_introspector.profile_component(component)
            components_profiled += 1
        
        report.components_benchmarked = components_profiled

    def simulate_decision_traces(self, report: BootstrapReport):
        decision_traces = 0
        for component in self.codebase_agent.get_components():
            # Simulate decision traces for the component
            decision_traces += self.adaptive_optimizer.simulate_decision_traces(component)
        
        report.traces_created = decision_traces

    def seed_pattern_recognizer(self, report: BootstrapReport):
        patterns_seeded = 0
        for pattern in self.knowledge_distiller.get_known_patterns():
            # Seed the pattern recognizer with the known pattern
            self.pattern_recognizer.seed_pattern(pattern)
            patterns_seeded += 1
        
        report.patterns_seeded = patterns_seeded

    def pre_load_knowledge_rules(self, report: BootstrapReport):
        rules_pre_loaded = 0
        for rule in self.knowledge_distiller.get_knowledge_rules():
            # Pre-load the knowledge rule
            self.experience_collector.pre_load_knowledge_rule(rule)
            rules_pre_loaded += 1
        
        report.rules_pre_loaded = rules_pre_loaded

    def run_code_introspector(self, report: BootstrapReport):
        self.code_introspector.run()

    def benchmark_components(self, report: BootstrapReport):
        components_benchmarked = 0
        for component in self.codebase_agent.get_components():
            # Benchmark the component
            self.code_introspector.benchmark_component(component)
            components_benchmarked += 1
        
        report.components_benchmarked = components_benchmarked

    def generate_synthetic_ab_test_data(self, report: BootstrapReport):
        synthetic_data = 0
        for component in self.codebase_agent.get_components():
            # Generate synthetic A/B test data for the component
            synthetic_data += self.adaptive_optimizer.generate_synthetic_ab_test_data(component)
        
        report.events_seeded = synthetic_data