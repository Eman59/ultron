"""
Brain C HTTP Server — The sidecar that Go talks to.

Listens on 127.0.0.1:50070 and exposes three endpoints:

  POST /reason   → Accept a BrainCRequest, return a BrainCResponse
  GET  /status   → Brain C stats
  GET  /health   → Simple liveness check

Started automatically by brain_c_bridge.go when the Go agent boots.
Can also be run manually:

  python3 brain_c_server.py --port 50070 --data-dir /path/to/data/brain_c

The server is single-process but uses a thread pool for the reasoning
calls so the HTTP layer never blocks for longer than the reasoning timeout.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict

# Ensure the consciousness package is importable
_HERE = Path(__file__).parent
_PYTHON_ROOT = _HERE.parent
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from consciousness.brain_c import BrainC, Situation

logging.basicConfig(
    level=logging.INFO,
    format="[BrainC-Server] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("brain_c_server")

# Global singleton
_brain: Optional[BrainC] = None
_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════
# REQUEST HANDLER
# ═══════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):
    """Minimal HTTP handler — zero external deps."""

    def log_message(self, fmt, *args):
        pass  # Suppress default access log spam

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "ts": time.time()})
        elif self.path == "/status":
            self._respond(200, _brain.stats() if _brain else {"online": False})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/reason":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = json.loads(body)
                result = self._handle_reason(data)
                self._respond(200, result)
            except json.JSONDecodeError as e:
                self._respond(400, {"error": f"invalid JSON: {e}"})
            except Exception as e:
                logger.error(f"Reason error: {e}", exc_info=True)
                self._respond(500, {"error": str(e)})
        else:
            self._respond(404, {"error": "not found"})

    def _handle_reason(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not _brain:
            return {"error": "brain not initialized"}

        situation = Situation(
            timestamp=data.get("timestamp", time.time()),
            drive_pressures=data.get("drive_pressures", {}),
            world_state=data.get("world_state", {}),
            active_goals=data.get("active_goals", []),
            recent_events=data.get("recent_events", []),
            owner_token=data.get("owner_token") or None,
        )

        decision = _brain.reason(situation)

        return {
            "action":            decision.action,
            "action_class":      decision.action_class.value,
            "confidence":        decision.confidence,
            "reasoning_chain":   decision.reasoning_chain,
            "analogy_source":    decision.analogy_source or "",
            "drive_alignment":   decision.drive_alignment,
            "requires_owner":    decision.requires_owner,
            "token_valid":       decision.token_valid,
            "timestamp":         decision.timestamp,
            "alternative_actions": decision.alternative_actions,
        }

    def _respond(self, code: int, payload: Dict[str, Any]):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Brain C Sidecar Server")
    parser.add_argument("--port",     type=int, default=50070)
    parser.add_argument("--host",     type=str, default="127.0.0.1")
    parser.add_argument("--data-dir", type=str,
                        default=os.environ.get("ULTRON_DATA_DIR", "./data/brain_c"))
    args = parser.parse_args()

    global _brain
    with _lock:
        logger.info(f"Initializing Brain C with data_dir={args.data_dir}")
        _brain = BrainC(data_dir=args.data_dir)

    server = HTTPServer((args.host, args.port), Handler)
    logger.info(f"Brain C server listening on {args.host}:{args.port}")
    logger.info(f"Stats: {_brain.stats()}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Brain C server shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
