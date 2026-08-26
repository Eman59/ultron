"""
Performance Monitor - Ultron watches itself.

Continuously tracks execution metrics, identifies degradation patterns,
and provides the data that drives self-improvement decisions.
"""

import time
import os
import sys
import traceback
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import statistics


@dataclass
class PerformanceSnapshot:
    """A point-in-time capture of system performance."""
    timestamp: float = field(default_factory=time.time)
    overall_score: float = 0.5
    component_scores: Dict[str, float] = field(default_factory=dict)
    latencies: Dict[str, float] = field(default_factory=dict)  # ms
    throughputs: Dict[str, float] = field(default_factory=dict)  # ops/sec
    error_rates: Dict[str, float] = field(default_factory=dict)
    resource_efficiency: float = 0.5
    failure_patterns: List[Dict[str, Any]] = field(default_factory=list)
    memory_usage_mb: float = 0.0
    cpu_utilization: float = 0.0


class PerformanceMonitor:
    """
    Watches all system components and reports performance metrics.
    
    This is the "self-awareness" component — Ultron's ability to know
    how well it's performing and where it's failing.
    """

    def __init__(self):
        # Metric accumulators
        self._latency_samples: Dict[str, List[float]] = defaultdict(list)
        self._throughput_counters: Dict[str, int] = defaultdict(int)
        self._error_counters: Dict[str, int] = defaultdict(int)
        self._call_counters: Dict[str, int] = defaultdict(int)
        self._last_reset: float = time.time()
        
        # Error tracking for pattern detection
        self._error_log: List[Dict[str, Any]] = []
        
        # Historical snapshots
        self._history: List[PerformanceSnapshot] = []
        self._max_history = 1000

    def record_latency(self, component: str, latency_ms: float):
        """Record a latency measurement for a component."""
        if component is None or latency_ms is None:
            return
        if not isinstance(component, str) or not isinstance(latency_ms, (int, float)):
            raise TypeError("Invalid input type")
        self._latency_samples[component].append(latency_ms)
        # Keep bounded
        if len(self._latency_samples[component]) > 1000:
            self._latency_samples[component] = self._latency_samples[component][-500:]

    def record_success(self, component: str):
        """Record a successful operation."""
        if component is None:
            return
        if not isinstance(component, str):
            raise TypeError("Invalid input type")
        self._call_counters[component] += 1
        self._throughput_counters[component] += 1

    def record_error(self, component: str, error: str):
        """Record an error."""
        if component is None or error is None:
            return
        if not isinstance(component, str) or not isinstance(error, str):
            raise TypeError("Invalid input type")
        self._error_counters[component] += 1
        self._call_counters[component] += 1
        self._error_log.append({
            "component": component,
            "error": error,
            "timestamp": time.time(),
        })
        if len(self._error_log) > 5000:
            self._error_log = self._error_log[-2500:]

    def take_snapshot(self) -> PerformanceSnapshot:
        """Take a complete performance snapshot."""
        try:
            elapsed = time.time() - self._last_reset
            if elapsed < 0.001:  # Avoid division by zero
                return PerformanceSnapshot()
            snapshot = PerformanceSnapshot()
            for component, latency_samples in self._latency_samples.items():
                if latency_samples:
                    snapshot.latencies[component] = statistics.mean(latency_samples)
            for component, throughput_counter in self._throughput_counters.items():
                if throughput_counter > 0:
                    snapshot.throughputs[component] = throughput_counter / elapsed
            for component, error_counter in self._error_counters.items():
                if self._call_counters[component] > 0:
                    snapshot.error_rates[component] = error_counter / self._call_counters[component]
            self._history.append(snapshot)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            return snapshot
        except Exception as e:
            print(f"Error taking snapshot: {e}", file=sys.stderr)
            return PerformanceSnapshot()

    def get_history(self) -> List[PerformanceSnapshot]:
        """Get the historical performance snapshots."""
        return self._history

    def reset(self):
        """Reset the performance monitor."""
        self._latency_samples = defaultdict(list)
        self._throughput_counters = defaultdict(int)
        self._error_counters = defaultdict(int)
        self._call_counters = defaultdict(int)
        self._last_reset = time.time()
        self._error_log = []
        self._history = []