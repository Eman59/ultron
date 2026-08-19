"""
Meta-Learning → OODA Bridge
Closes the loop: meta-learning generates new algorithms/strategies,
this bridge converts them into LearningDirectives and pushes them
to the Go core agent via the UnifiedLearningService.

Every 5 minutes:
  1. Ask meta_controller for the best current algorithm
  2. Convert it to a Drive adjustment or Instinct rule
  3. Send it to the learning service JSON port (50061)
  4. The Go OODA loop applies it next tick via ApplyDirectives()
"""

import json
import socket
import time
import threading
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_LEARNING_ADDR = os.environ.get("ULTRON_LEARNING_ADDR", "http://localhost:50060")
_JSON_PORT = int(_LEARNING_ADDR.split(":")[-1]) + 1   # 50061
_PUSH_INTERVAL = 300  # seconds between meta-learning → OODA pushes
_running = False
_thread = None


def _send_directive(directive: dict) -> bool:
    """Send a directive to the learning service JSON port."""
    try:
        payload = json.dumps({
            "method": "submit_events",
            "params": {
                "events": [{
                    "event_type": "neural_evolution",
                    "component":  "meta_learning",
                    "outcome":    "success",
                    "data":       {"directive": directive},
                    "importance": 0.85,
                }]
            }
        }).encode() + b"\n"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(("localhost", _JSON_PORT))
        sock.sendall(payload)
        sock.close()
        return True
    except Exception as e:
        logger.debug(f"[META-BRIDGE] send failed: {e}")
        return False


def _algorithm_to_directive(algo_spec: dict) -> dict:
    """
    Convert a meta-learning algorithm spec into a Go LearningDirective.
    Algorithm types map to directive types:
      - exploration → DirectiveExplorationSet
      - optimization → DirectiveDriveAdjust (boost efficiency)
      - learning → DirectiveDriveAdjust (boost curiosity)
      - defensive → DirectiveActionBias (bias toward defend)
    """
    task_type = algo_spec.get("task_type", "unknown")
    fitness   = float(algo_spec.get("fitness_score", 0.5))

    if fitness < 0.3:
        return {}  # Not good enough to push

    if "exploration" in task_type or "curiosity" in task_type:
        return {
            "type": "drive_adjust",
            "payload": {
                "adjustments": {"curiosity": min(0.08, fitness * 0.1)},
                "reason": f"meta-learning: {task_type} fitness={fitness:.2f}",
            },
            "expires_in": 600,
        }
    elif "optim" in task_type or "effic" in task_type:
        return {
            "type": "drive_adjust",
            "payload": {
                "adjustments": {"efficiency": min(0.06, fitness * 0.08)},
                "reason": f"meta-learning: {task_type} fitness={fitness:.2f}",
            },
            "expires_in": 600,
        }
    elif "learn" in task_type or "knowl" in task_type:
        return {
            "type": "drive_adjust",
            "payload": {
                "adjustments": {"purpose": min(0.07, fitness * 0.09)},
                "reason": f"meta-learning: {task_type} fitness={fitness:.2f}",
            },
            "expires_in": 600,
        }
    elif "defend" in task_type or "surviv" in task_type:
        return {
            "type": "action_bias",
            "payload": {
                "action_type": "defend",
                "multiplier":  1.0 + fitness * 0.5,
                "reason": f"meta-learning: {task_type}",
                "duration_seconds": 300.0,
            },
        }
    return {}


def _bridge_loop(meta_controller):
    """Background loop that pushes meta-learning outputs to Go OODA."""
    global _running
    logger.info("[META-BRIDGE] Learning bridge started — pushing every %ds", _PUSH_INTERVAL)
    while _running:
        try:
            # Ask meta-controller for best current algorithm
            best = None
            if hasattr(meta_controller, "algorithm_generator"):
                gen = meta_controller.algorithm_generator
                if hasattr(gen, "get_best_algorithm"):
                    best = gen.get_best_algorithm()
                elif hasattr(gen, "population") and gen.population:
                    best = max(gen.population, key=lambda a: getattr(a, "fitness_score", 0))

            if best:
                spec = {}
                if hasattr(best, "to_dict"):
                    spec = best.to_dict()
                elif hasattr(best, "__dict__"):
                    spec = {k: v for k, v in best.__dict__.items()
                            if isinstance(v, (str, int, float, bool))}
                directive = _algorithm_to_directive(spec)
                if directive:
                    ok = _send_directive(directive)
                    if ok:
                        logger.info("[META-BRIDGE] Pushed directive: %s (fitness=%.2f)",
                                    spec.get("task_type","?"), spec.get("fitness_score",0))

            # Also push current meta-strategy as drive hints
            if hasattr(meta_controller, "get_strategy_recommendations"):
                recs = meta_controller.get_strategy_recommendations()
                for rec in (recs or [])[:3]:
                    d = _algorithm_to_directive(rec)
                    if d:
                        _send_directive(d)

        except Exception as e:
            logger.debug(f"[META-BRIDGE] loop error: {e}")

        time.sleep(_PUSH_INTERVAL)


def start(meta_controller) -> None:
    """Start the bridge thread. Call once after meta_controller is ready."""
    global _running, _thread
    if _thread and _thread.is_alive():
        return
    _running = True
    _thread = threading.Thread(
        target=_bridge_loop,
        args=(meta_controller,),
        daemon=True,
        name="meta-learning-bridge"
    )
    _thread.start()
    logger.info("[META-BRIDGE] Online — meta-learning → OODA loop connected")


def stop() -> None:
    global _running
    _running = False
