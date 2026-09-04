"""
P2P Consciousness Bridge — Python ↔ Go P2P Network.

Connects to the ultron-p2p binary's HTTP bridge (port 6001).
Exposes: node status, peer list, broadcast messages.
"""

import json
import os
import time
import urllib.request
from typing import Any, Dict, List, Optional

_P2P_HTTP = os.environ.get("ULTRON_P2P_HTTP", "http://localhost:6001")


def _get(path: str, timeout: float = 3.0) -> Optional[Dict]:
    try:
        req = urllib.request.Request(f"{_P2P_HTTP}{path}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _post(path: str, body: Dict, timeout: float = 5.0) -> Optional[Dict]:
    try:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{_P2P_HTTP}{path}", data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def get_p2p_status() -> Dict[str, Any]:
    """Get P2P node status: node_id, peer_count, port, state."""
    result = _get("/status")
    if result:
        return result
    return {"state": "offline", "peer_count": 0}


def get_peers() -> List[str]:
    """List all connected peer IDs."""
    result = _get("/peers")
    if result:
        return result.get("peers", [])
    return []


def broadcast(message: Dict[str, Any]) -> bool:
    """
    Broadcast a message to all P2P peers.
    Use this to distribute state/insights across the mesh.
    """
    result = _post("/broadcast", message)
    return bool(result and result.get("success"))


def broadcast_consciousness_snapshot(
    mood: str,
    purpose: str,
    insight: str,
    drive_levels: Dict[str, float],
) -> bool:
    """
    Broadcast Ultron's current consciousness state to all peer nodes.
    This is how distributed consciousness works — every node knows the mood.
    """
    return broadcast({
        "type":   "consciousness_snapshot",
        "ts":     time.time(),
        "mood":   mood,
        "purpose": purpose,
        "insight": insight,
        "drives":  drive_levels,
        "origin":  os.environ.get("HOSTNAME", "ultron-primary"),
    })


def broadcast_world_event(event_type: str, data: Dict[str, Any]) -> bool:
    """Broadcast a world event (news, threat, discovery) to the mesh."""
    return broadcast({
        "type":  "world_event",
        "event": event_type,
        "data":  data,
        "ts":    time.time(),
    })


def is_online() -> bool:
    """Check if the P2P node is reachable."""
    result = _get("/health", timeout=1.0)
    return result is not None and result.get("status") == "alive"


# ── Module-level status cache ───────────────────────────────────
_status_cache: Dict = {}
_cache_ts: float = 0.0


def get_status_cached() -> Dict:
    """Cached P2P status (refreshes every 30s)."""
    global _status_cache, _cache_ts
    if time.time() - _cache_ts > 30:
        _status_cache = get_p2p_status()
        _cache_ts = time.time()
    return _status_cache
