"""
Ultron Benchmark Tracker
========================
Measures Ultron's decision quality over time and writes a persistent
curve to data/benchmark.json so you can watch improvement happen.

Metrics tracked every N seconds:
  - decision_quality  : weighted avg utility of last 100 decisions
  - patch_success_rate: % of self-modification patches that improved things
  - experience_count  : total experiences stored (proxy for learning depth)
  - pattern_count     : distinct patterns learned
  - action_diversity  : Shannon entropy of action types chosen
  - llm_confidence    : mean confidence of recent LLM patches
  - improvement_delta : quality score change vs previous window

All written to data/benchmark.json as an append-only time-series.
A simple ASCII chart is printed to stdout every interval.
"""

import os
import sys
import json
import time
import math
import signal
import threading
import socket
import datetime
from pathlib import Path
from collections import deque, Counter
from typing import List, Dict, Any, Optional


# ── Config ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT   = Path(os.environ.get("ULTRON_PROJECT_ROOT", "."))
BENCHMARK_FILE = PROJECT_ROOT / "data" / "benchmark.json"
SAMPLE_INTERVAL = int(os.environ.get("ULTRON_BENCHMARK_INTERVAL", "30"))  # seconds
MAX_HISTORY     = 10_000   # max data points kept in file
LEARNING_ADDR   = os.environ.get("ULTRON_LEARNING_ADDR", "localhost:50060")

# Strip http:// scheme if present
LEARNING_ADDR = LEARNING_ADDR.replace("https://", "").replace("http://", "")


# ── Data point ─────────────────────────────────────────────────────────────────
def _empty_point() -> dict:
    return {
        "ts":               0.0,
        "timestamp":        "",
        "decision_quality": 0.0,
        "patch_success_rate": 0.0,
        "patches_total":    0,
        "patches_applied":  0,
        "experience_count": 0,
        "pattern_count":    0,
        "action_diversity": 0.0,
        "llm_confidence":   0.0,
        "improvement_delta": 0.0,
        "source":           "benchmark_tracker",
    }


# ── Learning service query ─────────────────────────────────────────────────────
def _query_learning_service(method: str, params: dict = None, timeout: float = 4.0) -> Optional[dict]:
    """Send one JSON request to the learning service TCP socket."""
    try:
        host, port_str = LEARNING_ADDR.rsplit(":", 1)
        port = int(port_str)
        payload = json.dumps({"method": method, "params": params or {}}).encode() + b"\n"
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(payload)
            sock.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        return json.loads(b"".join(chunks).decode())
    except Exception:
        return None


# ── Experiential learning data ─────────────────────────────────────────────────
def _load_exp_learning_data() -> dict:
    """Read experiential learning stats from the data directory."""
    exp_dir = PROJECT_ROOT / "data" / "experiential_learning"
    result = {"experience_count": 0, "pattern_count": 0, "action_diversity": 0.0}

    # Try patterns.json
    patterns_file = exp_dir / "patterns.json"
    if patterns_file.exists():
        try:
            with open(patterns_file) as f:
                patterns = json.load(f)
            result["pattern_count"] = len(patterns) if isinstance(patterns, (list, dict)) else 0
        except Exception:
            pass

    # Try experiences.json
    exp_file = exp_dir / "experiences.json"
    if exp_file.exists():
        try:
            with open(exp_file) as f:
                exps = json.load(f)
            if isinstance(exps, list):
                result["experience_count"] = len(exps)
                # Action diversity = Shannon entropy of action_type distribution
                action_counts = Counter(e.get("action_type", "unknown") for e in exps[-1000:])
                total = sum(action_counts.values())
                if total > 0:
                    entropy = -sum((c / total) * math.log2(c / total) for c in action_counts.values() if c > 0)
                    result["action_diversity"] = round(entropy, 3)
        except Exception:
            pass

    return result


# ── Self-modification stats ────────────────────────────────────────────────────
def _load_selfmod_stats() -> dict:
    """Read self-modification history for patch success rate."""
    result = {"patches_total": 0, "patches_applied": 0, "patch_success_rate": 0.0, "llm_confidence": 0.0}

    mod_file = PROJECT_ROOT / "data" / "evolution" / "modification_history.json"
    if not mod_file.exists():
        # fallback: check selfmod log
        mod_file = PROJECT_ROOT / "data" / "mutations" / "mutations.json"

    if mod_file.exists():
        try:
            with open(mod_file) as f:
                records = json.load(f)
            if isinstance(records, list):
                result["patches_total"] = len(records)
                successes = [r for r in records if r.get("success", False)]
                result["patches_applied"] = len(successes)
                if records:
                    result["patch_success_rate"] = round(len(successes) / len(records), 3)
                # Mean confidence of last 20 patches
                recent = records[-20:]
                confs = [r.get("confidence", 0.0) for r in recent if "confidence" in r]
                if confs:
                    result["llm_confidence"] = round(sum(confs) / len(confs), 3)
        except Exception:
            pass

    return result


# ── Decision quality from learning service ─────────────────────────────────────
def _get_decision_quality() -> float:
    """Query learning service for recent decision utility score."""
    resp = _query_learning_service("get_status")
    if not resp:
        return 0.0
    try:
        # Navigate the status dict for utility metrics
        core = resp.get("core_agent", {})
        util = core.get("avg_utility", core.get("mean_utility", 0.0))
        if util:
            return round(float(util), 4)
        # Fallback: check evolution controller
        evo = resp.get("evolution", {})
        return round(float(evo.get("generation_fitness", 0.0)), 4)
    except Exception:
        return 0.0


# ── Sample one benchmark point ─────────────────────────────────────────────────
def sample(prev_quality: float = 0.0) -> dict:
    point = _empty_point()
    now = time.time()
    point["ts"]        = now
    point["timestamp"] = datetime.datetime.utcfromtimestamp(now).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Decision quality
    dq = _get_decision_quality()
    point["decision_quality"]   = dq
    point["improvement_delta"]  = round(dq - prev_quality, 4)

    # Experiential learning
    exp = _load_exp_learning_data()
    point["experience_count"] = exp["experience_count"]
    point["pattern_count"]    = exp["pattern_count"]
    point["action_diversity"] = exp["action_diversity"]

    # Self-modification
    sm = _load_selfmod_stats()
    point["patches_total"]      = sm["patches_total"]
    point["patches_applied"]    = sm["patches_applied"]
    point["patch_success_rate"] = sm["patch_success_rate"]
    point["llm_confidence"]     = sm["llm_confidence"]

    return point


# ── Persistence ────────────────────────────────────────────────────────────────
def load_history() -> List[dict]:
    if BENCHMARK_FILE.exists():
        try:
            with open(BENCHMARK_FILE) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def save_history(history: List[dict]) -> None:
    BENCHMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Keep only last MAX_HISTORY points
    trimmed = history[-MAX_HISTORY:]
    with open(BENCHMARK_FILE, "w") as f:
        json.dump(trimmed, f, indent=2)


# ── ASCII chart ────────────────────────────────────────────────────────────────
def _ascii_chart(history: List[dict], field: str = "decision_quality", width: int = 60, height: int = 10) -> str:
    values = [p.get(field, 0.0) for p in history[-width:]]
    if not values:
        return "  (no data yet)"

    vmin = min(values)
    vmax = max(values)
    span = vmax - vmin if vmax != vmin else 1.0

    rows = []
    for row in range(height, 0, -1):
        threshold = vmin + (row / height) * span
        line = ""
        for v in values:
            line += "█" if v >= threshold else " "
        label = f"{vmin + (row / height) * span:.3f} │"
        rows.append(f"  {label}{line}")

    rows.append("  " + " " * (len(f"{vmax:.3f} │")) + "─" * len(values))
    return "\n".join(rows)


def _print_status(history: List[dict], point: dict) -> None:
    latest = point
    prev   = history[-2] if len(history) >= 2 else _empty_point()

    delta_sym = "▲" if latest["improvement_delta"] > 0 else ("▼" if latest["improvement_delta"] < 0 else "─")
    delta_col = "\033[92m" if latest["improvement_delta"] > 0 else ("\033[91m" if latest["improvement_delta"] < 0 else "\033[93m")
    reset = "\033[0m"

    print(f"\n{'═'*64}")
    print(f"  ULTRON BENCHMARK  {latest['timestamp']}")
    print(f"{'─'*64}")
    print(f"  Decision Quality : {latest['decision_quality']:.4f}  "
          f"{delta_col}{delta_sym} {latest['improvement_delta']:+.4f}{reset}")
    print(f"  Patch Success    : {latest['patch_success_rate']*100:.1f}%  "
          f"({latest['patches_applied']}/{latest['patches_total']} applied)")
    print(f"  LLM Confidence   : {latest['llm_confidence']:.3f}")
    print(f"  Experiences      : {latest['experience_count']:,}")
    print(f"  Patterns Learned : {latest['pattern_count']:,}")
    print(f"  Action Diversity : {latest['action_diversity']:.3f} bits")
    print(f"{'─'*64}")
    print("  Decision Quality (last 60 samples):")
    print(_ascii_chart(history, "decision_quality"))
    print(f"{'═'*64}")
    sys.stdout.flush()


# ── Main tracker loop ──────────────────────────────────────────────────────────
class BenchmarkTracker:
    """
    Background benchmark tracker. Call start() to begin sampling.
    Call stop() to halt cleanly.
    """

    def __init__(self, interval: int = SAMPLE_INTERVAL):
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._history: List[dict] = load_history()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True, name="benchmark-tracker")
        self._thread.start()
        print(f"[Benchmark] Tracker started — sampling every {self.interval}s → {BENCHMARK_FILE}")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        save_history(self._history)
        print("[Benchmark] Tracker stopped.")

    def get_latest(self) -> Optional[dict]:
        return self._history[-1] if self._history else None

    def get_history(self, n: int = 100) -> List[dict]:
        return self._history[-n:]

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            prev_q = self._history[-1]["decision_quality"] if self._history else 0.0
            try:
                point = sample(prev_q)
                self._history.append(point)
                save_history(self._history)
                _print_status(self._history, point)
            except Exception as e:
                print(f"[Benchmark] Sample error: {e}")
            self._stop_event.wait(timeout=self.interval)


# ── CLI entry-point ────────────────────────────────────────────────────────────
def main() -> None:
    tracker = BenchmarkTracker()

    def _shutdown(sig, frame):
        print("\n[Benchmark] Shutting down…")
        tracker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    tracker.start()

    # Keep main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
