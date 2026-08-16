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
        self._latency_samples[component].append(latency_ms)
        # Keep bounded
        if len(self._latency_samples[component]) > 1000:
            self._latency_samples[component] = self._latency_samples[component][-500:]

    def record_success(self, component: str):
        """Record a successful operation."""
        self._call_counters[component] += 1
        self._throughput_counters[component] += 1

    def record_error(self, component: str, error: str):
        """Record an error."""
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
        
        elapsed = time.time() - self._last_reset
        if elapsed < 0.001:
            elapsed = 1.0
        
        snapshot = PerformanceSnapshot()
        
        # Calculate latencies (p50)
        for component, samples in self._latency_samples.items():
            if samples:
                snapshot.latencies[component] = statistics.median(samples)
        
        # Calculate throughputs (ops/sec)
        for component, count in self._throughput_counters.items():
            snapshot.throughputs[component] = count / elapsed
        
        # Calculate error rates
        for component in set(list(self._error_counters.keys()) + list(self._call_counters.keys())):
            calls = self._call_counters.get(component, 0)
            errors = self._error_counters.get(component, 0)
            if calls > 0:
                snapshot.error_rates[component] = errors / calls
            else:
                snapshot.error_rates[component] = 0.0
        
        # Calculate component scores (0-1, higher is better)
        all_components = set(snapshot.latencies.keys()) | set(snapshot.error_rates.keys()) | set(snapshot.throughputs.keys())
        for component in all_components:
            
            # Score based on: low latency + low error rate + high throughput
            latency_score = max(0, 1.0 - snapshot.latencies.get(component, 50.0) / 500.0)
            error_score = 1.0 - snapshot.error_rates.get(component, 0.0)
            throughput_score = min(1.0, snapshot.throughputs.get(component, 0.0) / 100.0)
            
            snapshot.component_scores[component] = (
                latency_score * 0.3 +
                error_score * 0.5 +
                throughput_score * 0.2
            )
        
        # Overall score
        if snapshot.component_scores:
            snapshot.overall_score = statistics.mean(snapshot.component_scores.values())
        
        # Resource efficiency (simplified)
        snapshot.resource_efficiency = self._estimate_efficiency()
        
        # Detect failure patterns
        snapshot.failure_patterns = self._detect_failure_patterns()
        
        # Memory usage
        try:
            import psutil
            process = psutil.Process(os.getpid())
            snapshot.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            snapshot.cpu_utilization = process.cpu_percent()
        except ImportError:
            snapshot.memory_usage_mb = 0.0
            snapshot.cpu_utilization = 0.0
        
        # Store in history
        self._history.append(snapshot)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history // 2:]
        
        return snapshot

    def get_trend(self, component: str, window: int = 20) -> float:
        """Get performance trend for a component (positive = improving)."""
        if len(self._history) < 3:
            return 0.0
        
        recent = self._history[-window:]
        scores = [s.component_scores.get(component, 0.5) for s in recent]
        
        if len(scores) < 2:
            return 0.0
        
        # Simple linear trend
        return (scores[-1] - scores[0]) / len(scores)

    def get_worst_components(self, n: int = 5) -> List[Tuple[str, float]]:
        """Get the N worst-performing components."""
        if not self._history:
            return []
        
        latest = self._history[-1]
        sorted_components = sorted(
            latest.component_scores.items(),
            key=lambda x: x[1]
        )
        return sorted_components[:n]

    def reset_counters(self):
        """Reset counters for a new measurement window."""
        self._throughput_counters.clear()
        self._error_counters.clear()
        self._call_counters.clear()
        self._last_reset = time.time()

    def _estimate_efficiency(self) -> float:
        """Estimate overall resource efficiency."""
        total_ops = sum(self._throughput_counters.values())
        total_errors = sum(self._error_counters.values())
        
        if total_ops == 0:
            return 0.5
        
        # Efficiency = useful work / total work
        return max(0, (total_ops - total_errors) / total_ops)

    def _detect_failure_patterns(self) -> List[Dict[str, Any]]:
        """Detect recurring failure patterns."""
        if not self._error_log:
            return []
        
        # Group errors by component + error message
        patterns: Dict[str, Dict[str, Any]] = {}
        
        recent_errors = [e for e in self._error_log if time.time() - e["timestamp"] < 300]
        
        for error in recent_errors:
            key = f"{error['component']}:{error['error'][:50]}"
            if key not in patterns:
                patterns[key] = {
                    "component": error["component"],
                    "error": error["error"][:100],
                    "count": 0,
                    "first_seen": error["timestamp"],
                    "last_seen": error["timestamp"],
                }
            patterns[key]["count"] += 1
            patterns[key]["last_seen"] = error["timestamp"]
        
        # Return patterns with count > 2
        return [p for p in patterns.values() if p["count"] > 2]
