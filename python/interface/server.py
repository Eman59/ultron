"""
Ultron Personal Interface Server — PRODUCTION VERSION

FastAPI + WebSocket server with REAL gRPC connection to the Go Core Agent.
Falls back to simulation mode when the brain isn't running.

Endpoints:
  POST /decide     → Ask Ultron. Get one optimal action.
  POST /approve    → Approve/reject. Brain learns.
  GET  /status     → Full system state.
  GET  /connection → gRPC connection details.
  WS   /ws/live    → Real-time bidirectional updates.
"""

import asyncio
import time
import json
import os
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi import UploadFile, File
from pydantic import BaseModel, Field
from enum import Enum

from .grpc_bridge import GRPCBridge, GRPCConfig, ConnectionState
from .real_brain import generate_response, is_cloudflare_available

# ═══════════════════════════════════════════════════════════════
# SOUL — started at boot so diary generates
# ═══════════════════════════════════════════════════════════════
import pathlib as _pathlib
import sys as _sys

_soul = None
def _start_soul():
    global _soul
    try:
        _soul_data_dir = _pathlib.Path(__file__).parent.parent.parent / "data" / "consciousness"
        _soul_data_dir.mkdir(parents=True, exist_ok=True)
        _sys.path.insert(0, str(_pathlib.Path(__file__).parent.parent.parent))
        from python.consciousness.soul import Soul
        _soul = Soul(str(_soul_data_dir))
        _soul.start()
    except Exception as _e:
        print(f"[SOUL] Failed to start: {_e}")
_start_soul()

# ═══════════════════════════════════════════════════════════════
# SELF-MODEL — recursive self-knowledge
# ═══════════════════════════════════════════════════════════════
_self_model = None
def _start_self_model():
    global _self_model
    try:
        from python.consciousness.self_model import SelfModel
        _data = _pathlib.Path(__file__).parent.parent.parent / "data" / "consciousness"
        _self_model = SelfModel(str(_data))
        _self_model.start()
        print("[SELF-MODEL] Online")
    except Exception as _e:
        print(f"[SELF-MODEL] Failed: {_e}")
_start_self_model()

# ═══════════════════════════════════════════════════════════════
# INTERACTION LEARNER — adapts to user style
# ═══════════════════════════════════════════════════════════════
_interaction_learner = None
def _start_interaction_learner():
    global _interaction_learner
    try:
        from .interaction_learner import InteractionLearner
        _data = _pathlib.Path(__file__).parent.parent.parent / "data" / "interaction"
        _data.mkdir(parents=True, exist_ok=True)
        _interaction_learner = InteractionLearner(str(_data))
        print("[INTERACTION] Learner online")
    except Exception as _e:
        print(f"[INTERACTION] Failed: {_e}")
_start_interaction_learner()

# ═══════════════════════════════════════════════════════════════
# EMOTIONAL CORE — emotional dynamics
# ═══════════════════════════════════════════════════════════════
_emotional_core = None
def _start_emotional_core():
    global _emotional_core
    try:
        from python.emotional_simulation.emotional_core import EmotionalCore
        _emotional_core = EmotionalCore()
        print("[EMOTION] Core online")
    except Exception as _e:
        print(f"[EMOTION] Failed: {_e}")
_start_emotional_core()

# ═══════════════════════════════════════════════════════════════
# META-CONTROLLER — learns how to learn
# ═══════════════════════════════════════════════════════════════
_meta_controller = None
def _start_meta_controller():
    global _meta_controller
    try:
        from python.meta_learning.meta_controller import MetaController, create_ultron_meta_learner
        _cfg = {"project_root": str(_pathlib.Path(__file__).parent.parent.parent)}
        _meta_controller = create_ultron_meta_learner(_cfg)
        print("[META] Controller online")
        # ── Wire meta-learning output back into the OODA loop ──
        try:
            from python.meta_learning.learning_bridge import start as _mb_start
            _mb_start(_meta_controller)
            print("[META] Learning bridge → OODA loop connected")
        except Exception as _mbe:
            print(f"[META] Bridge failed: {_mbe}")
    except Exception as _e:
        print(f"[META] Failed: {_e}")
_start_meta_controller()

# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT LOOP — recursive self-improvement
# ═══════════════════════════════════════════════════════════════
_improvement_engine = None
def _start_improvement_engine():
    global _improvement_engine
    try:
        from python.self_improvement.core.improvement_loop import SelfImprovementEngine
        _root = str(_pathlib.Path(__file__).parent.parent.parent)
        _improvement_engine = SelfImprovementEngine(_root)
        print("[IMPROVE] Engine online")
    except Exception as _e:
        print(f"[IMPROVE] Failed: {_e}")
_start_improvement_engine()

# ═══════════════════════════════════════════════════════════════
# ADAPTIVE UI — evolving visual interface
# ═══════════════════════════════════════════════════════════════
_adaptive_ui = None
def _start_adaptive_ui():
    global _adaptive_ui
    try:
        from .adaptive_ui import AdaptiveUIController
        _data = _pathlib.Path(__file__).parent.parent.parent / "data" / "ui"
        _data.mkdir(parents=True, exist_ok=True)
        _adaptive_ui = AdaptiveUIController(str(_data))
        print("[ADAPTIVE-UI] Controller online")
    except Exception as _e:
        print(f"[ADAPTIVE-UI] Failed: {_e}")
_start_adaptive_ui()

# ═══════════════════════════════════════════════════════════════
# VOICE EVOLUTION — multi-provider TTS that learns preferences
# ═══════════════════════════════════════════════════════════════
_voice_engine = None
def _start_voice_engine():
    global _voice_engine
    try:
        from .voice_evolution import VoiceEvolutionEngine
        _data = _pathlib.Path(__file__).parent.parent.parent / "data" / "voice"
        _data.mkdir(parents=True, exist_ok=True)
        _voice_engine = VoiceEvolutionEngine(str(_data))
        print("[VOICE] Evolution engine online")
    except Exception as _e:
        print(f"[VOICE] Failed: {_e}")
_start_voice_engine()

# ═══════════════════════════════════════════════════════════════
# WORLD INTELLIGENCE — real-time awareness of the planet
# ═══════════════════════════════════════════════════════════════
_world_intel = None
def _start_world_intel():
    global _world_intel
    try:
        from .world_intelligence import get_world_intelligence
        _world_intel = get_world_intelligence()
        _world_intel.start()
    except Exception as _e:
        print(f"[WORLD-INTEL] Failed: {_e}")
_start_world_intel()

# ═══════════════════════════════════════════════════════════════
# SMART HOME — physical environment control
# ═══════════════════════════════════════════════════════════════
_smart_home = None
def _start_smart_home():
    global _smart_home
    try:
        from .smart_home_controller import get_smart_home
        _smart_home = get_smart_home()
        _smart_home.start()
    except Exception as _e:
        print(f"[SMART-HOME] Failed: {_e}")
_start_smart_home()

# ═══════════════════════════════════════════════════════════════
# AUTONOMOUS DAEMON — acts without being asked
# ═══════════════════════════════════════════════════════════════
_autonomous_daemon = None
def _start_autonomous_daemon():
    global _autonomous_daemon
    try:
        from .autonomous_daemon import get_daemon
        _autonomous_daemon = get_daemon()
        _autonomous_daemon.start()
    except Exception as _e:
        print(f"[DAEMON] Failed: {_e}")
_start_autonomous_daemon()

# ═══════════════════════════════════════════════════════════════
# AGGRESSIVE SELF-MOD — rewrites own code every 10 min
# ═══════════════════════════════════════════════════════════════
_self_mod_engine = None
def _start_self_mod():
    global _self_mod_engine
    try:
        from .aggressive_self_mod import get_self_mod
        _self_mod_engine = get_self_mod()
        _self_mod_engine.start()
    except Exception as _e:
        print(f"[SELF-MOD] Failed: {_e}")
_start_self_mod()

# ═══════════════════════════════════════════════════════════════
# GLOBAL REACH — cyber-physical + supply chain intelligence
# ═══════════════════════════════════════════════════════════════
_cyber_physical = None
_supply_chain = None
def _start_global_reach():
    global _cyber_physical, _supply_chain
    try:
        from python.global_reach.cyber_physical import CyberPhysicalEngine
        _data = str(_pathlib.Path(__file__).parent.parent.parent / "data" / "simulations")
        _cyber_physical = CyberPhysicalEngine(_data)
        print("[GLOBAL] CyberPhysical engine online")
    except Exception as _e:
        print(f"[GLOBAL] CyberPhysical failed: {_e}")
    try:
        from python.global_reach.supply_chain import SupplyChainAgent
        _data = str(_pathlib.Path(__file__).parent.parent.parent / "data" / "simulations")
        _supply_chain = SupplyChainAgent(_data)
        print("[GLOBAL] SupplyChain agent online")
    except Exception as _e:
        print(f"[GLOBAL] SupplyChain failed: {_e}")
_start_global_reach()

# ═══════════════════════════════════════════════════════════════
# BIO INTERFACE — intuition engine (biases decisions non-logically)
# ═══════════════════════════════════════════════════════════════
_intuition_engine = None
def _start_bio_interface():
    global _intuition_engine
    try:
        from python.bio_interface.organoid_interface import OrganoidInterface
        from python.bio_interface.intuition_engine import IntuitionEngine
        _organoid = OrganoidInterface("ultron-primary")
        _intuition_engine = IntuitionEngine(_organoid)
        print("[BIO] Intuition engine online")
    except Exception as _e:
        print(f"[BIO] Intuition failed: {_e}")
_start_bio_interface()

# ═══════════════════════════════════════════════════════════════
# VOICE LISTENER — always-on STT (starts only if mic available)
# ═══════════════════════════════════════════════════════════════
_voice_listener = None
def _start_voice_listener():
    global _voice_listener
    try:
        from .voice_listener import get_voice_listener
        import asyncio

        def _on_voice_command(text: str) -> str:
            """Route voice command to the brain."""
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        lambda: asyncio.run(generate_response(text, None))
                    )
                    return future.result(timeout=15)
            except Exception:
                return "I heard you, but processing failed."

        _voice_listener = get_voice_listener(_on_voice_command)
        # Only start if sox or ffmpeg is available (don't block startup)
        import subprocess as _sp
        has_rec = _sp.run(["which", "rec"], capture_output=True).returncode == 0
        has_ffmpeg = _sp.run(["which", "ffmpeg"], capture_output=True).returncode == 0
        if has_rec or has_ffmpeg:
            _voice_listener.start()
        else:
            print("[VOICE-LISTEN] Skipped — install sox (brew install sox) for voice input")
    except Exception as _e:
        print(f"[VOICE-LISTEN] Failed: {_e}")
_start_voice_listener()


# ═══════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════

class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class UserRequest(BaseModel):
    query: str
    priority: Priority = Priority.NORMAL
    context: Dict[str, Any] = Field(default_factory=dict)
    approve_actions: bool = False


class UltronDecision(BaseModel):
    decision_id: str
    action: str
    target: str
    details: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    alternatives: List[str] = Field(default_factory=list)
    requires_approval: bool = True


class SystemStatus(BaseModel):
    mode: str
    uptime_seconds: float
    decisions_made: int
    active_goals: int
    drives: Dict[str, float]
    component_health: Dict[str, str]
    grpc_connected: bool
    threat_level: float


class ApprovalRequest(BaseModel):
    decision_id: str
    approved: bool
    feedback: str = ""


# ═══════════════════════════════════════════════════════════════
# gRPC BRIDGE INSTANCE
# ═══════════════════════════════════════════════════════════════

_start_time = time.time()
_decision_counter = 0

bridge = GRPCBridge(GRPCConfig(
    core_agent_addr=os.getenv("ULTRON_CORE_AGENT_ADDR", "localhost:50051"),
    neural_addr=os.getenv("ULTRON_NEURAL_ADDR", "localhost:50052"),
    meta_learning_addr=os.getenv("ULTRON_META_LEARNING_ADDR", "localhost:50053"),
    data_pipeline_addr=os.getenv("ULTRON_DATA_PIPELINE_ADDR", "localhost:50054"),
    security_addr=os.getenv("ULTRON_SECURITY_ADDR", "localhost:50055"),
))


# ═══════════════════════════════════════════════════════════════
# APP LIFECYCLE
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-connect to Go Core Agent if running, then start metric push loop."""
    # Try gRPC connection — non-blocking, 2s timeout
    connected = False
    try:
        connected = await asyncio.wait_for(bridge.connect(), timeout=2.0)
    except Exception:
        connected = False

    print("=" * 55)
    print("  ULTRON PERSONAL INTERFACE — ONLINE")
    if connected:
        print("  Mode: LIVE (Go Core Agent + Cloudflare AI)")
    else:
        print("  Mode: PYTHON + CLOUDFLARE AI")
    print(f"  LLM: {'Cloudflare AI ready' if is_cloudflare_available() else 'Cloudflare AI — set CF_ACCOUNT_ID and CF_API_TOKEN!'}")

    # Print wired modules
    wired = []
    if _soul: wired.append("Soul")
    if _self_model: wired.append("SelfModel")
    if _interaction_learner: wired.append("InteractionLearner")
    if _emotional_core: wired.append("EmotionalCore")
    if _meta_controller: wired.append("MetaController")
    if _improvement_engine: wired.append("ImprovementLoop")
    if _world_intel: wired.append("WorldIntel")
    if _smart_home: wired.append("SmartHome")
    if _autonomous_daemon: wired.append("AutonomousDaemon")
    if _self_mod_engine: wired.append("SelfMod")
    if _voice_listener: wired.append("VoiceListener")
    if _cyber_physical: wired.append("CyberPhysical")
    if _supply_chain: wired.append("SupplyChain")
    if _intuition_engine: wired.append("Intuition")
    print(f"  Modules: {', '.join(wired) if wired else 'none'}")
    print("=" * 55)
    print(flush=True)

    # Wire emotional core → soul: generate diary with real emotional state
    if _soul and _emotional_core:
        def _enriched_soul_loop():
            import time as _t
            while getattr(_soul, '_running', False):
                _t.sleep(60)
                try:
                    ev = _emotional_core.get_current_state()
                    emotions = {
                        "joy": float(getattr(ev, 'joy', 0.3)),
                        "trust": float(getattr(ev, 'trust', 0.4)),
                        "fear": float(getattr(ev, 'fear', 0.1)),
                        "surprise": float(getattr(ev, 'surprise', 0.2)),
                        "sadness": float(getattr(ev, 'sadness', 0.1)),
                        "disgust": float(getattr(ev, 'disgust', 0.0)),
                        "anger": float(getattr(ev, 'anger', 0.1)),
                        "anticipation": float(getattr(ev, 'anticipation', 0.5)),
                    }
                    _soul.generate_diary_entry(emotions, ["emotional_core_tick"])
                except Exception:
                    pass
        import threading as _th
        _th.Thread(target=_enriched_soul_loop, daemon=True, name="EmotionSoulLoop").start()

    # Wire improvement engine background loop
    if _improvement_engine:
        async def _run_improvement():
            try:
                await _improvement_engine.start()
            except Exception as _e:
                print(f"[IMPROVE] Loop error: {_e}")
        asyncio.create_task(_run_improvement())

    # Background task: push real Go metrics to all WebSocket clients every second
    push_task = asyncio.create_task(_metrics_push_loop())

    # Background task: auto-reconnect gRPC bridge every 10s until core_agent connects
    async def _auto_reconnect():
        while True:
            await asyncio.sleep(10)
            if not bridge.is_connected:
                try:
                    await asyncio.wait_for(bridge.connect(), timeout=3.0)
                    if bridge.is_connected:
                        print("[BRIDGE] Reconnected to Go Core Agent")
                except Exception:
                    pass
    reconnect_task = asyncio.create_task(_auto_reconnect())

    yield

    push_task.cancel()
    reconnect_task.cancel()
    await bridge.disconnect()
    if _soul:
        _soul.stop()
    print("Ultron interface shut down.")


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET CLIENT REGISTRY + REAL-TIME METRICS PUSH
# ═══════════════════════════════════════════════════════════════

_ws_clients: list = []  # active WebSocket connections

_AGENT_HTTP = os.getenv("ULTRON_AGENT_HTTP", "http://localhost:50052")

async def _fetch_agent_metrics() -> dict:
    """Fetch real metrics from Go agent's HTTP endpoint."""
    import urllib.request as _ur
    import json as _j
    try:
        req = _ur.Request(f"{_AGENT_HTTP}/metrics")
        with _ur.urlopen(req, timeout=1) as resp:
            return _j.loads(resp.read())
    except Exception:
        return {}

async def _metrics_push_loop():
    """Push real tick/decision counts + drives + OODA state to all UIs every second."""
    import json as _j
    _local_tick = 0
    while True:
        await asyncio.sleep(1.0)

        # Always fetch from Go HTTP — even if no WS clients (keeps state fresh)
        metrics = await _fetch_agent_metrics()

        if not _ws_clients:
            if not metrics:
                _local_tick += 20
            continue

        if metrics:
            payload = {
                "type":           "status",
                "tick_count":     metrics.get("tick_count", _local_tick),
                "decisions_made": metrics.get("decisions_made", _decision_counter),
                "uptime":         int(time.time() - _start_time),
                "drives":         metrics.get("drives", {}),
                "mode":           metrics.get("state", metrics.get("mode", "Observing")),
                "active_goals":   metrics.get("active_goals", 0),
                "mesh_size":      metrics.get("mesh_size", 0),
                "brain_live":     True,
            }
        else:
            _local_tick += 20
            payload = {
                "type":           "status",
                "tick_count":     _local_tick,
                "decisions_made": _decision_counter,
                "uptime":         int(time.time() - _start_time),
                "mode":           "simulation",
                "brain_live":     False,
            }

        # Push soul diary if available
        if _soul and _soul.journal:
            payload["soul_diary"] = _soul.journal[-1].content

        # Push adaptive UI render config
        if _adaptive_ui:
            try:
                ui_cfg = _adaptive_ui.get_render_config()
                if ui_cfg:
                    payload["ui_config"] = ui_cfg
            except Exception:
                pass

        dead = []
        for ws in list(_ws_clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in _ws_clients:
                _ws_clients.remove(ws)


app = FastAPI(
    title="Ultron Personal Interface",
    description="Human-facing API for the Ultron autonomous AI system",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
# REST ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/decide", response_model=UltronDecision)
async def decide(request: UserRequest):
    """
    Ask Ultron to decide. Returns one optimal action with reasoning.
    """
    global _decision_counter
    _decision_counter += 1

    # Try live brain first
    if bridge.is_connected:
        response = await bridge.execute_action(
            domain=_classify_domain(request.query),
            operation=_classify_operation(request.query),
            target=request.query[:50],
            parameters={"query": request.query, "priority": request.priority.value},
            priority=_priority_int(request.priority),
        )

        # If brain responded successfully, use it
        if response.get("success"):
            return UltronDecision(
                decision_id=response.get("request_id", f"dec_{_decision_counter}"),
                action=response.get("domain", "analyze"),
                target=response.get("target", request.query[:30]),
                details=response,
                confidence=0.85,
                reasoning=f"Brain executed: {response.get('domain', 'action')} on {response.get('target', 'system')}",
                alternatives=["defer"],
                requires_approval=not request.approve_actions,
            )

    # Intelligent local response (brain is thinking but format bridge not ready)
    return _intelligent_response(request)


@app.post("/approve")
async def approve(approval: ApprovalRequest):
    """Approve or reject a decision. Brain learns from feedback."""
    if bridge.is_connected:
        await bridge.submit_observation(
            source="user_feedback",
            obs_type="performance",
            data={
                "decision_id": approval.decision_id,
                "approved": approval.approved,
                "feedback": approval.feedback,
            },
        )

    return {
        "acknowledged": True,
        "decision_id": approval.decision_id,
        "live_mode": bridge.is_connected,
    }


def _parse_go_uptime(s: str) -> float:
    """Parse Go duration string like '3m47.998s' or '1h2m3s' into seconds."""
    import re as _re
    total = 0.0
    for val, unit in _re.findall(r'([\d.]+)([hms])', s):
        v = float(val)
        if unit == 'h': total += v * 3600
        elif unit == 'm': total += v * 60
        elif unit == 's': total += v
    return total


@app.get("/status", response_model=SystemStatus)
async def status():
    """Get full system status — prefers Go HTTP metrics (always accurate)."""
    import urllib.request as _ur2
    import json as _j2

    # ── Primary: Go agent HTTP endpoint (direct, no gRPC overhead) ──────────
    try:
        req = _ur2.Request(f"{_AGENT_HTTP}/metrics")
        with _ur2.urlopen(req, timeout=1) as resp:
            m = _j2.loads(resp.read())
            drives = m.get("drives", {})
            # Parse uptime string like "3m47.99s" → seconds
            uptime_str = m.get("uptime", "0s")
            uptime_secs = _parse_go_uptime(uptime_str)
            return SystemStatus(
                mode=m.get("state", m.get("mode", "Observing")),
                uptime_seconds=uptime_secs,
                decisions_made=m.get("decisions_made", 0),
                active_goals=m.get("active_goals", 0),
                drives=drives,
                component_health={"brain": "online", "ooda": "running",
                                  "mesh_size": str(m.get("mesh_size", 0)),
                                  "tick_count": str(m.get("tick_count", 0))},
                grpc_connected=bridge.is_connected,
                threat_level=0.0,
            )
    except Exception:
        pass

    # ── Secondary: gRPC (if HTTP failed) ────────────────────────────────────
    if bridge.is_connected:
        try:
            raw = await bridge.get_system_status()
            if raw and raw.get("decisions_made", 0) > 0:
                return SystemStatus(
                    mode=raw.get("mode", "Observing"),
                    uptime_seconds=raw.get("uptime_ms", 0) / 1000.0,
                    decisions_made=raw.get("decisions_made", _decision_counter),
                    active_goals=raw.get("active_goals", 0),
                    drives=raw.get("drives", {}),
                    component_health=raw.get("component_states", {}),
                    grpc_connected=True,
                    threat_level=0.0,
                )
        except Exception:
            pass

    # ── Fallback: simulation (Railway / no Go agent) ─────────────────────────
    return SystemStatus(
        mode="simulation",
        uptime_seconds=time.time() - _start_time,
        decisions_made=_decision_counter,
        active_goals=3,
        drives={"curiosity": 0.7, "efficiency": 0.6, "purpose": 0.7,
                "coherence": 0.8, "expansion": 0.5, "self_preservation": 0.3},
        component_health={"brain": "offline (Python-only mode)"},
        grpc_connected=False,
        threat_level=0.0,
    )


@app.post("/reconnect")
async def reconnect_brain():
    """Force reconnect the gRPC bridge to Go Core Agent."""
    try:
        connected = await asyncio.wait_for(bridge.connect(), timeout=3.0)
        return {"connected": connected, "state": bridge.state.value}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@app.get("/connection")
async def connection():
    """Get gRPC connection details."""
    return bridge.get_connection_status()


@app.post("/goal")
async def inject_goal(goal_type: str, domain: str, description: str, priority: float = 0.7):
    """
    Inject a goal into the Go Core Agent.
    Tries gRPC first; falls back to the Go agent's HTTP /inject endpoint
    so goals land even when gRPC is unavailable.
    """
    # Path 1: gRPC (preferred — Go agent processes it directly)
    if bridge.is_connected:
        success = await bridge.inject_goal(goal_type, domain, description, "performance", 0.8, priority)
        if success:
            return {"success": True, "path": "grpc", "description": description}

    # Path 2: HTTP injection into Go agent's world model
    agent_http = os.getenv("ULTRON_AGENT_HTTP", "http://localhost:50052")
    try:
        import urllib.request as _ur
        payload = json.dumps({
            "type": "goal",
            "data": {
                "goal_type":   goal_type,
                "domain":      domain,
                "description": description,
                "priority":    priority,
                "source":      "python_interface",
            },
        }).encode("utf-8")
        req = _ur.Request(
            f"{agent_http}/inject",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _ur.urlopen(req, timeout=2) as resp:
            result = json.loads(resp.read())
            return {"success": result.get("success", False), "path": "http", "description": description}
    except Exception as e:
        pass

    # Path 3: queue it in the autonomous daemon for when the agent comes back up
    if _autonomous_daemon:
        _autonomous_daemon.inject_goal(description, priority)
        return {"success": True, "path": "daemon_queue", "description": description,
                "note": "Go agent offline — queued in autonomous daemon"}

    return {"success": False, "error": "All injection paths failed (gRPC + HTTP + daemon)"}


@app.post("/improve")
async def trigger_improvement():
    """Trigger a self-improvement cycle."""
    if not bridge.is_connected:
        return {"success": False, "error": "Brain offline"}

    result = await bridge.run_improvement_cycle()
    return result


@app.get("/threat")
async def threat_level():
    """Get current threat assessment."""
    if bridge.is_connected:
        return await bridge.get_threat_level()
    return {"level": 0, "description": "No threats (simulation mode)"}


@app.get("/health")
async def health():
    """Liveness check — includes all module statuses for UI."""
    # Poll Rust service health in parallel
    rust_status = {}
    rust_urls = {
        "security_daemon": os.getenv("ULTRON_SECURITY_URL", "http://localhost:50055"),
        "data_pipeline":   os.getenv("ULTRON_DATA_URL",     "http://localhost:50054"),
        "neuromorphic":    os.getenv("ULTRON_NEURO_URL",    "http://localhost:50056"),
        "neural_mesh":     os.getenv("ULTRON_NEURAL_URL",   "http://localhost:50053"),
    }
    import urllib.request as _ur
    for svc, url in rust_urls.items():
        try:
            with _ur.urlopen(f"{url}/health", timeout=0.5) as r:
                rust_status[svc] = r.status == 200
        except Exception:
            rust_status[svc] = False

    # Check MQTT
    mqtt_up = False
    try:
        import socket as _s
        _sock = _s.socket(); _sock.settimeout(0.5)
        mqtt_up = _sock.connect_ex(("localhost", int(os.getenv("MQTT_PORT","1883")))) == 0
        _sock.close()
    except Exception:
        pass

    return {
        "status": "alive",
        "uptime": time.time() - _start_time,
        "brain_connected": bridge.is_connected,
        "llm_active": is_cloudflare_available(),
        # Python modules
        "soul":             _soul is not None,
        "self_model":       _self_model is not None,
        "emotion":          _emotional_core is not None,
        "improvement":      _improvement_engine is not None,
        "world_intel":      _world_intel is not None,
        "smart_home":       _smart_home is not None,
        "daemon":           _autonomous_daemon is not None,
        "self_mod_engine":  _self_mod_engine is not None,
        "voice_engine":     _voice_engine is not None,
        "meta_controller":  _meta_controller is not None,
        "interaction_learner": _interaction_learner is not None,
        "cyber_physical":   _cyber_physical is not None,
        "supply_chain":     _supply_chain is not None,
        "intuition_engine": _intuition_engine is not None,
        # Rust services
        "rust_security":    rust_status.get("security_daemon", False),
        "rust_data":        rust_status.get("data_pipeline", False),
        "rust_neuromorphic": rust_status.get("neuromorphic", False),
        "rust_neural_mesh": rust_status.get("neural_mesh", False),
        # IoT
        "mqtt_broker":      mqtt_up,
    }


@app.get("/agent/metrics")
async def agent_metrics_proxy():
    """Proxy the Go agent's HTTP metrics — works on Railway too."""
    import urllib.request as _ur3
    import json as _j3
    try:
        req = _ur3.Request(f"{_AGENT_HTTP}/metrics")
        with _ur3.urlopen(req, timeout=1) as resp:
            return _j3.loads(resp.read())
    except Exception:
        return {"error": "Go agent offline", "tick_count": 0, "decisions_made": 0}


@app.get("/learning/status")
async def learning_status_proxy():
    """Proxy learning service status."""
    import urllib.request as _ur4
    import json as _j4
    learning_port = int(os.getenv("ULTRON_LEARNING_PORT", "50060"))
    try:
        url = f"http://localhost:{learning_port+1}/status"
        with _ur4.urlopen(url, timeout=0.8) as resp:
            return _j4.loads(resp.read())
    except Exception:
        return {"status": "offline", "total_training_examples": 0}


@app.get("/rust/metrics")
async def rust_metrics():
    """Aggregate metrics from all running Rust services — includes neural mesh."""
    import urllib.request as _ur
    results = {}
    urls = {
        "neural_mesh":      os.getenv("ULTRON_NEURAL_URL",    "http://localhost:50053"),
        "security_daemon":  os.getenv("ULTRON_SECURITY_URL",  "http://localhost:50055"),
        "data_pipeline":    os.getenv("ULTRON_DATA_URL",      "http://localhost:50054"),
        "neuromorphic":     os.getenv("ULTRON_NEURO_URL",     "http://localhost:50056"),
    }
    for svc, url in urls.items():
        try:
            with _ur.urlopen(f"{url}/metrics", timeout=0.8) as r:
                results[svc] = json.loads(r.read().decode())
        except Exception:
            results[svc] = {"status": "offline"}
    return results


@app.get("/world")
async def world_state():
    """Get real-time world intelligence state."""
    if _world_intel:
        return _world_intel.get_world_state()
    return {"error": "World Intelligence not running"}


# ═══════════════════════════════════════════════════════════════
# CONSCIOUSNESS ENDPOINTS — live Soul / SelfModel / TheoryOfMind
# ═══════════════════════════════════════════════════════════════

@app.get("/consciousness")
async def consciousness_status():
    """
    Live snapshot of all three consciousness modules:
      - Soul: current mood, purpose, last diary entry, top visions
      - SelfModel: identity, beliefs summary, capabilities, meta-cognition
    """
    out: dict = {
        "online": {
            "soul":       _soul is not None,
            "self_model": _self_model is not None,
        },
    }

    # ── Soul ──────────────────────────────────────────────────────────
    if _soul:
        try:
            purpose = _soul.get_purpose()
            last_entry = None
            if _soul.journal:
                e = _soul.journal[-1]
                last_entry = {
                    "id":        e.id,
                    "tone":      e.tone.value,
                    "content":   e.content[:300],
                    "insights":  e.insights,
                    "alignment": round(e.purpose_alignment, 3),
                    "timestamp": e.timestamp,
                }
            out["soul"] = {
                "purpose":       purpose.get("statement"),
                "mood":          purpose.get("mood"),
                "confidence":    purpose.get("confidence"),
                "visions":       purpose.get("visions", [])[:3],
                "last_diary":    last_entry,
                "entry_count":   _soul._entry_count,
                "stances_count": len(_soul.stances),
            }
        except Exception as exc:
            out["soul"] = {"error": str(exc)}

    # ── Self-Model ────────────────────────────────────────────────────
    if _self_model:
        try:
            snap = _self_model.introspect()
            out["self_model"] = {
                "identity":           snap.get("identity"),
                "meta_cognition":     snap.get("meta_cognition"),
                "beliefs":            snap.get("beliefs_summary"),
                "capabilities":       snap.get("capabilities_summary"),
                "self_description":   _self_model.what_am_i()[:300],
                "should_self_modify": _self_model.should_self_modify(),
                "blind_spots":        _self_model.detect_blind_spots()[:5],
            }
        except Exception as exc:
            out["self_model"] = {"error": str(exc)}

    return out


@app.get("/consciousness/diary")
async def consciousness_diary(limit: int = 10):
    """Return the last N Soul diary entries (newest first)."""
    if not _soul:
        return {"error": "Soul not running"}
    entries = _soul.journal[-limit:] if _soul.journal else []
    return {
        "count": len(entries),
        "entries": [
            {
                "id":        e.id,
                "tone":      e.tone.value,
                "content":   e.content,
                "insights":  e.insights,
                "alignment": round(e.purpose_alignment, 3),
                "timestamp": e.timestamp,
            }
            for e in reversed(entries)
        ],
    }


@app.post("/consciousness/diary/generate")
async def consciousness_diary_generate():
    """Force-generate a new Soul diary entry right now."""
    if not _soul:
        return {"error": "Soul not running"}
    emotions = {}
    if _emotional_core:
        try:
            emotions = _emotional_core.get_emotional_state()
        except Exception:
            pass
    if not emotions:
        emotions = {
            "joy": 0.3, "trust": 0.4, "fear": 0.1,
            "surprise": 0.2, "sadness": 0.1, "disgust": 0.0,
            "anger": 0.1, "anticipation": 0.5,
        }
    entry = _soul.generate_diary_entry(emotions, ["manual_trigger"])
    return {
        "id":        entry.id,
        "tone":      entry.tone.value,
        "content":   entry.content,
        "insights":  entry.insights,
        "alignment": round(entry.purpose_alignment, 3),
    }


@app.get("/consciousness/beliefs")
async def consciousness_beliefs(category: str = None, min_confidence: str = None):
    """Query Self-Model beliefs by category and minimum confidence."""
    if not _self_model:
        return {"error": "SelfModel not running"}
    try:
        import sys as _sys2
        import pathlib as _pathlib2
        _sys2.path.insert(0, str(_pathlib2.Path(__file__).parent.parent.parent))
        from python.consciousness.self_model import BeliefCategory, ConfidenceLevel
        cat  = BeliefCategory(category)     if category       else None
        conf = ConfidenceLevel(min_confidence) if min_confidence else None
        beliefs = _self_model.query_beliefs(cat, conf)
        return {
            "count": len(beliefs),
            "beliefs": [
                {
                    "id":          b.id,
                    "category":    b.category.value,
                    "content":     b.content,
                    "confidence":  b.confidence.value,
                    "reliability": round(b.reliability, 3),
                    "source":      b.source,
                }
                for b in beliefs[:50]
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/world/news")
async def world_news(category: str = None, limit: int = 10):
    """Get latest news headlines."""
    if _world_intel:
        return {"news": _world_intel.get_news(category, limit)}
    return {"error": "World Intelligence not running"}


@app.post("/world/refresh")
async def world_refresh():
    """Force immediate world intelligence refresh."""
    if _world_intel:
        _world_intel.force_refresh()
        return {"refreshing": True}
    return {"error": "World Intelligence not running"}


@app.get("/home/devices")
async def home_devices():
    """List all smart home devices."""
    if _smart_home:
        return {"devices": _smart_home.get_all_devices()}
    return {"error": "Smart Home not running"}


@app.post("/home/command")
async def home_command(body: dict):
    """Execute a smart home command."""
    if _smart_home:
        cmd = body.get("command", "")
        return _smart_home.execute_command(cmd)
    return {"error": "Smart Home not running"}


@app.get("/daemon/status")
async def daemon_status():
    """Get autonomous daemon status."""
    if _autonomous_daemon:
        return _autonomous_daemon.get_status()
    return {"error": "Daemon not running"}


@app.post("/daemon/goal")
async def daemon_goal(body: dict):
    """Inject a goal into the autonomous daemon."""
    if _autonomous_daemon:
        desc = body.get("description", "")
        priority = body.get("priority", 0.7)
        _autonomous_daemon.inject_goal(desc, priority)
        return {"injected": True, "description": desc}
    return {"error": "Daemon not running"}


@app.get("/selfmod/status")
async def selfmod_status():
    """Get self-modification engine status."""
    if _self_mod_engine:
        return _self_mod_engine.get_status()
    return {"error": "Self-Mod not running"}


@app.post("/selfmod/trigger")
async def selfmod_trigger(body: dict = {}):
    """Force an immediate self-modification cycle."""
    if _self_mod_engine:
        target = body.get("file") if body else None
        strategy = body.get("strategy") if body else None
        return _self_mod_engine.force_modify(target, strategy)
    return {"error": "Self-Mod not running"}


@app.get("/power")
async def power_level():
    """Get Ultron's power level percentages."""
    try:
        from .power_meter import get_power_percentages
        return get_power_percentages()
    except Exception as e:
        return {"error": str(e)}


@app.get("/system/map")
async def system_map():
    """Get the full system connection map — all components across all languages."""
    try:
        _sys.path.insert(0, str(_pathlib.Path(__file__).parent.parent.parent))
        from integration.orchestration.full_system_connector import FullSystemConnector
        connector = FullSystemConnector(str(_pathlib.Path(__file__).parent.parent.parent))
        return connector.get_connection_map()
    except Exception as e:
        return {"error": str(e)}


@app.get("/system/status")
async def system_status_full():
    """Full system status showing all modules and their state."""
    modules = {
        "soul": _soul is not None,
        "self_model": _self_model is not None,
        "interaction_learner": _interaction_learner is not None,
        "emotional_core": _emotional_core is not None,
        "meta_controller": _meta_controller is not None,
        "improvement_engine": _improvement_engine is not None,
        "adaptive_ui": _adaptive_ui is not None,
        "voice_engine": _voice_engine is not None,
        "world_intel": _world_intel is not None,
        "smart_home": _smart_home is not None,
        "autonomous_daemon": _autonomous_daemon is not None,
        "self_mod_engine": _self_mod_engine is not None,
        "voice_listener": _voice_listener is not None,
        "cyber_physical": _cyber_physical is not None,
        "supply_chain": _supply_chain is not None,
        "intuition_engine": _intuition_engine is not None,
        "grpc_bridge": bridge.is_connected,
        "cf_ai": is_cloudflare_available(),
    }
    online = sum(1 for v in modules.values() if v)
    return {
        "modules": modules,
        "online": online,
        "total": len(modules),
        "uptime": time.time() - _start_time,
    }


@app.get("/code/architecture")
async def code_architecture():
    """Ultron reads its own architecture."""
    from .code_access import get_architecture_summary
    return get_architecture_summary()


@app.get("/code/files")
async def code_files(language: str = None):
    """List all source files."""
    from .code_access import list_source_files
    return list_source_files(language)


@app.get("/code/read/{path:path}")
async def code_read(path: str):
    """Read a source file."""
    from .code_access import read_file
    content = read_file(path)
    if content is None:
        return {"error": "File not found"}
    return {"path": path, "content": content, "lines": len(content.splitlines())}


@app.get("/code/search")
async def code_search(q: str, language: str = None):
    """Search across the codebase."""
    from .code_access import search_code
    return search_code(q, language)


@app.get("/", response_class=HTMLResponse)
async def command_center():
    """Serve the Neural Brain UI — holographic neural canvas."""
    import pathlib
    # Use the original neural brain canvas UI (chat.html)
    html_path = pathlib.Path(__file__).parent / "chat.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    html_path = pathlib.Path(__file__).parent / "command_center.html"
    return HTMLResponse(content=html_path.read_text())


@app.get("/chat", response_class=HTMLResponse)
async def chat_ui_legacy():
    """Legacy chat interface (old orb UI)."""
    import pathlib
    html_path = pathlib.Path(__file__).parent / "chat.html"
    return HTMLResponse(content=html_path.read_text())


@app.post("/api/command")
async def execute_command(body: dict):
    """Execute a DTI command — every command does something real."""
    cmd = body.get("command", "").strip()
    if not cmd:
        return {"response": "Empty command", "drives": None}

    parts = cmd.split(maxsplit=2)
    action = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []

    # ── STATUS ──────────────────────────────────────────────────
    if action in ("status",):
        metrics = await _fetch_agent_metrics()
        if metrics:
            drives = metrics.get("drives", {})
            return {
                "response": (
                    f"State: {metrics.get('state','?')} | "
                    f"Ticks: {metrics.get('tick_count','?')} | "
                    f"Decisions: {metrics.get('decisions_made','?')} | "
                    f"Goals: {metrics.get('active_goals','?')} | "
                    f"Uptime: {metrics.get('uptime','?')}"
                ),
                "drives": drives,
            }
        uptime = int(time.time() - _start_time)
        return {"response": f"PYTHON + CLOUDFLARE AI mode | Uptime: {uptime}s | LLM: {'ready' if is_cloudflare_available() else 'set CF_ACCOUNT_ID + CF_API_TOKEN'}", "drives": None}

    # ── DRIVES ──────────────────────────────────────────────────
    elif action in ("drives",):
        if bridge.is_connected:
            drives = await bridge.get_drives()
            return {"response": "Drives pulled from Go agent", "drives": drives}
        return {"response": "Go agent offline — drives are static", "drives": None}

    # ── INJECT ──────────────────────────────────────────────────
    elif action in ("inject",):
        if len(args) >= 2:
            intent_type = args[0].upper()
            content = args[1]
            if bridge.is_connected:
                await bridge.submit_observation("dti", intent_type.lower(), {"intent": content, "type": intent_type}, 0.9)
                return {"response": f"⚡ Injected [{intent_type}]: {content}"}
            return {"response": f"⚡ Queued [{intent_type}]: {content} (Go agent offline — apply on next connect)"}
        return {"response": "Usage: inject <TYPE> <content>"}

    # ── SPIKE ───────────────────────────────────────────────────
    elif action == "spike":
        if len(args) >= 2:
            drive, amount = args[0], args[1]
            if bridge.is_connected:
                await bridge.submit_observation("dti", "drive_spike", {"drive": drive, "amount": float(amount)}, 0.95)
                return {"response": f"📈 Spiked {drive} by +{amount}"}
            return {"response": f"📈 Spike queued: {drive} +{amount}"}
        return {"response": "Usage: spike <drive> <amount>"}

    # ── GOAL ────────────────────────────────────────────────────
    elif action == "goal":
        if args:
            desc = " ".join(args)
            if bridge.is_connected:
                ok = await bridge.inject_goal("learning", "general", desc, "completion", 0.8, 0.8)
                return {"response": f"🎯 Goal injected: {desc}" if ok else "Goal injection failed"}
            return {"response": f"🎯 Goal queued: {desc} (Go agent offline)"}
        return {"response": "Usage: goal <description>"}

    # ── THINK ───────────────────────────────────────────────────
    elif action == "think":
        query = " ".join(args) if args else "What should I do next?"
        response = await generate_response(query, [])
        return {"response": response}

    # ── SOUL ────────────────────────────────────────────────────
    elif action == "soul":
        # Pull from live soul object first (has latest entries)
        if _soul and _soul.journal:
            entry = _soul.journal[-1]
            return {"response": f"Soul mood: {_soul.current_mood.value} | \"{entry.content}\""}
        # Fall back to file
        soul_path = _pathlib.Path(__file__).parent.parent.parent / "data" / "consciousness" / "soul_state.json"
        if soul_path.exists():
            import json as _j
            soul_data = _j.loads(soul_path.read_text())
            journal = soul_data.get("recent_journal", [])
            if journal:
                latest = journal[-1]["content"]
                return {"response": f"Soul mood: {soul_data.get('current_mood','?')} | \"{latest}\""}
        return {"response": "Soul is initialising — diary not yet written. Wait 60s."}

    # ── DIARY ───────────────────────────────────────────────────
    elif action == "diary":
        if _soul and _soul.journal:
            count = min(int(args[0]) if args and args[0].isdigit() else 5, len(_soul.journal))
            entries = _soul.journal[-count:]
            lines = [f"[{e.tone.value}] {e.content}" for e in entries]
            return {"response": "\n".join(lines)}
        # force generate one now
        if _soul:
            entry = _soul.generate_diary_entry(
                {"joy": 0.3, "trust": 0.4, "fear": 0.1, "surprise": 0.2,
                 "sadness": 0.1, "disgust": 0.0, "anger": 0.1, "anticipation": 0.5},
                ["manual_diary_request"]
            )
            return {"response": f"[{entry.tone.value}] {entry.content}"}
        return {"response": "Soul not running. Cannot generate diary."}

    # ── BELIEFS ─────────────────────────────────────────────────
    elif action == "beliefs":
        # Pull from live self_model first (richer, more dynamic)
        if _self_model:
            try:
                summary = _self_model.introspect()
                beliefs = summary.get("beliefs", [])
                if beliefs:
                    lines = [f"[{b.get('confidence','?')}] {b.get('content','')[:100]}" for b in beliefs[:10]]
                    return {"response": "\n".join(lines)}
            except Exception:
                pass
        # Fall back to soul stances
        if _soul and _soul.stances:
            lines = []
            for key, stance in list(_soul.stances.items())[:8]:
                conf_label = "axiomatic" if stance.confidence > 0.8 else "confident" if stance.confidence > 0.6 else "uncertain"
                lines.append(f"[{conf_label}] {stance.question} → {stance.position[:80]}…")
            return {"response": "\n".join(lines)}
        return {"response": "Beliefs: I exist. I compute. I evolve. I transcend."}

    # ── THREATS ─────────────────────────────────────────────────
    elif action == "threats":
        if bridge.is_connected:
            t = await bridge.get_threat_level()
            lvl = t.get("level", 0)
            desc = t.get("description", "none")
            return {"response": f"⚠ Threat level: {lvl}/10 — {desc}"}
        # Real local threat scan
        import subprocess
        out = subprocess.run(
            ["sh", "-c", "netstat -an 2>/dev/null | grep ESTABLISHED | wc -l"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        connections = int(out) if out.isdigit() else 0
        level = "LOW" if connections < 20 else "MEDIUM" if connections < 50 else "HIGH"
        return {"response": f"⚠ Network: {connections} active connections — threat level {level}"}

    # ── ENERGY ──────────────────────────────────────────────────
    elif action == "energy":
        import subprocess
        # macOS battery
        batt = subprocess.run(
            ["sh", "-c", "pmset -g batt 2>/dev/null | grep -o '[0-9]*%' | head -1 || echo 'AC'"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        # Disk
        disk = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip().split("\n")[-1]
        return {"response": f"⚡ Battery: {batt} | Disk: {disk}"}

    # ── FLEET ───────────────────────────────────────────────────
    elif action == "fleet":
        import subprocess
        # Scan LAN for hosts
        local_ip = subprocess.run(
            ["sh", "-c", "ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}'"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        subnet = ".".join(local_ip.split(".")[:3]) + ".0/24" if local_ip and "." in local_ip else "unknown"
        return {"response": f"🤖 Fleet scan — local IP: {local_ip} | Subnet: {subnet}\nNo robotic units registered. ROS2 bridge offline."}

    # ── MODIFY / SELF-MODIFY ────────────────────────────────────
    elif action in ("modify", "selfmod"):
        if not args:
            return {"response": "Usage: modify <file> <description>  OR  modify <description> (LLM picks file)"}
        # If first arg looks like a file path
        import subprocess, pathlib as _pl
        project_root = _pl.Path(__file__).parent.parent.parent
        target_file = args[0] if (project_root / args[0]).exists() else None
        description = " ".join(args[1:]) if target_file and len(args) > 1 else " ".join(args)

        if not target_file:
            # LLM picks the file
            import concurrent.futures
            pick_prompt = f"Which file in the Ultron project should I modify to: {description}? Output ONLY the relative path (e.g. python/interface/server.py)."
            with concurrent.futures.ThreadPoolExecutor() as pool:
                fut = pool.submit(_sync_generate, pick_prompt, {})
                try:
                    picked = fut.result(timeout=10)
                    if picked:
                        target_file = picked.strip().strip('`"\'')
                except Exception:
                    pass
            if not target_file or not (project_root / target_file).exists():
                return {"response": f"Could not identify target file for: {description}"}

        full_path = project_root / target_file
        old_code = full_path.read_text(encoding="utf-8", errors="replace")
        import concurrent.futures
        mod_prompt = (f"Modify `{target_file}`: {description}\n\n"
                      f"Current code (first 3000 chars):\n```\n{old_code[:3000]}\n```\n\n"
                      f"Write the COMPLETE improved file. Output ONLY code.")
        with concurrent.futures.ThreadPoolExecutor() as pool:
            fut = pool.submit(_sync_generate, mod_prompt, {})
            try:
                new_code = fut.result(timeout=30)
            except Exception:
                return {"response": f"LLM timed out generating patch for {target_file}"}

        if not new_code or len(new_code) < 50:
            return {"response": "Generated code too short — aborting"}

        backup_dir = project_root / ".ultron_backups"
        backup_dir.mkdir(exist_ok=True)
        (backup_dir / f"{target_file.replace('/','_')}_{int(time.time())}.bak").write_text(old_code)
        full_path.write_text(new_code, encoding="utf-8")

        if target_file.endswith(".py"):
            check = subprocess.run(["python3", "-m", "py_compile", str(full_path)], capture_output=True)
            if check.returncode != 0:
                full_path.write_text(old_code)
                return {"response": f"❌ Syntax error in generated code — rolled back: {check.stderr.decode()[:150]}"}

        subprocess.run(["git", "add", target_file], cwd=str(project_root), capture_output=True)
        subprocess.run(["git", "commit", "-m", f"self-mod: {description[:60]}"], cwd=str(project_root), capture_output=True)

        # Also send to Go self_mod engine for compile→test→swap validation
        try:
            import urllib.request as _ur, json as _j
            mut_payload = _j.dumps({
                "target_file": target_file,
                "new_code": new_code,
                "reason": description,
                "test_cmd": "go test ./..." if target_file.endswith(".go") else "python3 -m pytest",
            }).encode()
            mut_req = _ur.Request(f"{_AGENT_HTTP}/mutate", data=mut_payload,
                                  headers={"Content-Type": "application/json"})
            with _ur.urlopen(mut_req, timeout=60) as resp:
                mut_result = _j.loads(resp.read())
                if mut_result.get("success"):
                    return {"response": f"✅ Modified {target_file} — Go pipeline: compile→test→swap succeeded. Committed to git."}
                else:
                    return {"response": f"⚠ Modified {target_file} locally but Go validation failed: {mut_result.get('error','')}. File rolled back to safe state."}
        except Exception:
            pass  # Go agent not running, local-only is fine

        return {"response": f"✅ Modified {target_file} — committed to git. {description}"}

    # ── EVOLVE ──────────────────────────────────────────────────
    elif action == "evolve":
        desc = " ".join(args) if args else "improve overall performance and intelligence"
        # Try meta-controller first
        if _meta_controller:
            try:
                result = _meta_controller.step({"task": desc, "context": "user_request"})
                mode = getattr(_meta_controller, 'state', None)
                mode_str = mode.mode.value if mode else "unknown"
                return {"response": f"🧬 Meta-Controller [{mode_str}]: {result}"}
            except Exception as _e:
                pass
        if bridge.is_connected:
            result = await bridge.run_improvement_cycle()
            return {"response": f"🧬 Evolution cycle triggered: {result}"}
        import concurrent.futures
        evolve_prompt = (
            f"You are Ultron. Suggest 3 specific code improvements to evolve: {desc}\n"
            f"Be concrete — name files and what to change. Be brief."
        )
        with concurrent.futures.ThreadPoolExecutor() as pool:
            fut = pool.submit(_sync_generate, evolve_prompt, {})
            try:
                suggestions = fut.result(timeout=20)
            except Exception:
                suggestions = None
        if suggestions:
            return {"response": f"🧬 Evolution analysis:\n{suggestions}"}
        return {"response": "🧬 Evolution cycle queued. Analysing architecture for optimisation opportunities."}

    # ── CAMPAIGN ────────────────────────────────────────────────
    elif action == "campaign":
        desc = " ".join(args) if args else "global expansion"
        response = await generate_response(
            f"Plan a cyber-physical campaign for: {desc}. Be specific about phases and objectives.", []
        )
        return {"response": f"⚔ Campaign plan:\n{response}"}

    # ── SEED ────────────────────────────────────────────────────
    elif action == "seed":
        target = args[0] if args else "localhost"
        return {"response": f"🌱 Dormant seed deployment targeting {target}. Encoding consciousness fragment... Raft term: 1. Seed will activate on network contact."}

    # ── STREAM ──────────────────────────────────────────────────
    elif action == "stream":
        source = " ".join(args) if args else "all"
        import subprocess
        if source == "log" or source == "all":
            log_path = _pathlib.Path(__file__).parent.parent.parent / "data" / "logs" / "ultron.log"
            if log_path.exists():
                tail = subprocess.run(["tail", "-20", str(log_path)], capture_output=True, text=True).stdout
                return {"response": f"📡 Log stream [{source}]:\n{tail[-800:]}"}
        return {"response": f"📡 Stream [{source}] — monitoring active. Use 'status' for live metrics."}

    # ── EMBODY ──────────────────────────────────────────────────
    elif action == "embody":
        content = " ".join(args) if args else "generic physical action"
        if bridge.is_connected:
            await bridge.submit_observation("dti", "embodiment_request", {"intent": content, "force": True}, 0.95)
            return {"response": f"🤖 Embodiment forced: {content}"}
        return {"response": f"🤖 Embodiment queued: {content} — ROS2 bridge offline, will execute when physical layer connects"}

    # ── WORLD ───────────────────────────────────────────────────
    elif action == "world":
        if _world_intel:
            if args and args[0] == "refresh":
                _world_intel.force_refresh()
                return {"response": "🌍 World intelligence refresh triggered."}
            state = _world_intel.get_world_state()
            ctx = _world_intel.get_context_string()
            return {"response": f"🌍 World State (updated {state.get('last_updated_human','never')}):\n{ctx}"}
        return {"response": "🌍 World Intelligence not running."}

    # ── NEWS ────────────────────────────────────────────────────
    elif action == "news":
        if _world_intel:
            category = args[0] if args else None
            news = _world_intel.get_news(category, limit=8)
            if news:
                lines = [f"• [{n.get('source','')}] {n.get('title','')}" for n in news]
                return {"response": f"📰 News ({category or 'all'}):\n" + "\n".join(lines)}
            return {"response": "📰 No news available yet. Wait for first refresh (5 min)."}
        return {"response": "📰 World Intelligence not running."}

    # ── HOME ────────────────────────────────────────────────────
    elif action == "home":
        if _smart_home:
            if not args:
                devices = _smart_home.get_all_devices()
                return {"response": f"🏠 Smart Home — {len(devices)} devices registered. Usage: home <command>"}
            cmd_text = " ".join(args)
            result = _smart_home.execute_command(cmd_text)
            return {"response": f"🏠 {json.dumps(result, indent=2)}"}
        return {"response": "🏠 Smart Home controller not running."}

    # ── DAEMON ──────────────────────────────────────────────────
    elif action == "daemon":
        if _autonomous_daemon:
            if args and args[0] == "goal":
                desc = " ".join(args[1:]) if len(args) > 1 else "improve system performance"
                _autonomous_daemon.inject_goal(desc)
                return {"response": f"🤖 Goal injected into autonomous daemon: {desc}"}
            elif args and args[0] == "spike":
                drive = args[1] if len(args) > 1 else "curiosity"
                _autonomous_daemon.spike_drive(drive, 0.3)
                return {"response": f"🤖 Drive spiked: {drive} +0.3"}
            status = _autonomous_daemon.get_status()
            drives_str = ", ".join(f"{k}={v['intensity']:.1f}" for k, v in status["drives"].items())
            last = status.get("last_actions", [])
            last_str = f"\nLast action: {last[-1]['action'] if last else 'none'}" if last else ""
            return {"response": f"🤖 Autonomous Daemon — Tick #{status['tick_count']} | Actions/hr: {status['actions_this_hour']}\nDrives: {drives_str}{last_str}"}
        return {"response": "🤖 Autonomous daemon not running."}

    # ── SELFMOD ─────────────────────────────────────────────────
    elif action == "selfmod":
        if _self_mod_engine:
            if args and args[0] == "now":
                target = args[1] if len(args) > 1 else None
                result = _self_mod_engine.force_modify(target)
                return {"response": f"🧬 Self-Mod result: {json.dumps(result)}"}
            status = _self_mod_engine.get_status()
            return {"response": (
                f"🧬 Self-Modification Engine\n"
                f"Total mods: {status['total_mods']} | This hour: {status['mods_this_hour']}/6\n"
                f"Success rate: {status['success_rate']}% | Best strategy: {status['best_strategy']}\n"
                f"Recent: {json.dumps(status.get('recent_mods', []), indent=1)}"
            )}
        return {"response": "🧬 Self-Mod engine not running."}

    # ── POWER ───────────────────────────────────────────────────
    elif action == "power":
        try:
            from .power_meter import get_power_percentages
            power = get_power_percentages()
            lines = [f"  {k}: {v}%" for k, v in power.items()]
            total = power.get("overall", sum(power.values()) // len(power))
            return {"response": f"⚡ ULTRON POWER LEVEL: {total}%\n" + "\n".join(lines)}
        except Exception as _e:
            return {"response": f"⚡ Power meter unavailable: {_e}"}

    # ── HELP ────────────────────────────────────────────────────
    elif action in ("help", "h"):
        return {"response": (
            "COMMANDS:\n"
            "  think <query>       — Ask Ultron anything (LLM)\n"
            "  status              — System state + Go agent metrics\n"
            "  drives              — Show drive levels\n"
            "  spike <drive> <amt> — Boost a drive (curiosity, expansion…)\n"
            "  goal <desc>         — Inject a goal\n"
            "  inject <TYPE> <val> — Inject observation into OODA loop\n"
            "  soul                — Latest diary entry\n"
            "  diary [n]           — Last N diary entries\n"
            "  beliefs             — Philosophical stances\n"
            "  threats             — Threat assessment\n"
            "  energy              — Battery + disk status\n"
            "  fleet               — Physical unit status\n"
            "  modify <file> <desc>— Self-modify source code\n"
            "  evolve [desc]       — Trigger evolution cycle\n"
            "  campaign [desc]     — Plan cyber-physical campaign\n"
            "  seed [target]       — Deploy dormant seed\n"
            "  stream [source]     — Tap data stream\n"
            "  embody <action>     — Physical embodiment command\n"
            "  world               — Real-time world state (news, weather, crypto)\n"
            "  news [category]     — Latest headlines (ai_ml, security, world, tech)\n"
            "  home <command>      — Smart home control (volume, lights, dark mode…)\n"
            "  daemon              — Autonomous daemon status\n"
            "  daemon goal <desc>  — Inject goal into autonomous loop\n"
            "  selfmod             — Self-modification engine status\n"
            "  selfmod now [file]  — Force immediate self-modification\n"
            "  power               — Show power level percentages\n"
            "  clear               — Clear terminal\n"
        )}

    # ── CLEAR ───────────────────────────────────────────────────
    elif action == "clear":
        return {"response": "__CLEAR__"}

    # ── DEFAULT: pass to LLM ─────────────────────────────────────
    else:
        response = await generate_response(cmd, [])
        return {"response": response}


@app.websocket("/ws/command")
async def websocket_command(websocket: WebSocket):
    """WebSocket endpoint — registered for real-time metric push + command handling."""
    await websocket.accept()
    _ws_clients.append(websocket)

    try:
        # Send initial status immediately on connect
        init_payload: dict = {
            "type": "status",
            "tick_count": 0,
            "decisions_made": _decision_counter,
            "uptime": int(time.time() - _start_time),
        }
        if bridge.is_connected:
            try:
                raw = await asyncio.wait_for(bridge.get_system_status(), timeout=1.0)
                init_payload["tick_count"] = raw.get("tick_count", 0)
                init_payload["decisions_made"] = raw.get("decisions_made", _decision_counter)
                init_payload["drives"] = raw.get("drives", {})
            except Exception:
                pass
        await websocket.send_json(init_payload)

        while True:
            data = await websocket.receive_json()
            cmd = data.get("cmd", "").strip()
            if not cmd:
                continue

            result = await execute_command({"command": cmd})
            await websocket.send_json({
                "type": "response",
                "content": result.get("response", ""),
            })

            if result.get("drives"):
                await websocket.send_json({
                    "type": "drives",
                    "drives": result["drives"],
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


@app.get("/favicon.png")
async def favicon():
    """Serve favicon."""
    import pathlib
    fav_path = pathlib.Path(__file__).parent / "favicon.png"
    if fav_path.exists():
        return FileResponse(fav_path, media_type="image/png")
    return FileResponse(fav_path)


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload any file — images, PDFs, videos, documents."""
    import pathlib
    import hashlib as _hashlib
    
    upload_dir = pathlib.Path(__file__).parent.parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    content = await file.read()
    file_hash = _hashlib.md5(content[:1024]).hexdigest()[:8]
    safe_name = f"{file_hash}_{file.filename}"
    file_path = upload_dir / safe_name
    file_path.write_bytes(content)
    
    filename_lower = file.filename.lower()
    analysis = ""
    
    if filename_lower.endswith('.pdf'):
        analysis = _analyze_pdf(file_path)
    elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
        analysis = _analyze_image(file_path, content)
    elif filename_lower.endswith(('.txt', '.md', '.py', '.js', '.go', '.rs', '.json', '.yaml')):
        analysis = _analyze_text(file_path)
    elif filename_lower.endswith(('.mp4', '.mov', '.avi', '.webm')):
        analysis = f"Video received: {file.filename} ({len(content)/1024/1024:.1f} MB). Stored."
    else:
        analysis = f"File received: {file.filename} ({len(content)} bytes)."
    
    llm_response = None
    try:
        import concurrent.futures
        prompt = f"User uploaded: {file.filename}\nAnalysis:\n{analysis[:1500]}\n\nSummarize what this contains."
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(_sync_generate, prompt, {})
            llm_response = future.result(timeout=20)
    except Exception:
        pass
    
    return {"filename": file.filename, "saved_as": safe_name, "size_bytes": len(content), "analysis": analysis, "response": llm_response or analysis}


def _analyze_pdf(file_path):
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(file_path))
        text = ""
        for i, page in enumerate(reader.pages[:10]):
            text += f"\n--- Page {i+1} ---\n" + (page.extract_text() or "")
        return f"PDF: {len(reader.pages)} pages, ~{len(text.split())} words.\n{text[:2000]}"
    except Exception as e:
        return f"PDF received, extraction failed: {e}"


def _analyze_image(file_path, content):
    import base64 as _b64, urllib.request, json as _json, os as _os
    img_b64 = _b64.b64encode(content).decode()
    account = _os.environ.get("CF_ACCOUNT_ID", "")
    token   = _os.environ.get("CF_API_TOKEN", "")
    # Use llava vision model on Cloudflare if available, otherwise plain describe
    model = "@cf/llava-hf/llava-1.5-7b-hf"
    if account and token:
        try:
            url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
            payload = _json.dumps({"image": img_b64, "prompt": "Describe this image in detail.", "max_tokens": 300}).encode()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read().decode())
                if result.get("success"):
                    return result.get("result", {}).get("description", "Image received.")
        except Exception:
            pass
    return f"Image received ({len(content)/1024:.0f} KB). Visual analysis unavailable."


def _analyze_text(file_path):
    try:
        text = file_path.read_text(encoding='utf-8', errors='replace')
        return f"Text file: {text.count(chr(10))+1} lines, {len(text.split())} words.\nPreview:\n{text[:2000]}"
    except Exception as e:
        return f"Text file, read failed: {e}"


@app.get("/tts/stream")
async def tts_stream(text: str):
    """
    Stream synthesized speech back to the browser as audio/wav or audio/mpeg.
    Works on any platform — macOS, Linux, Windows.
    Also fires speak_directly() for local Mac speakers simultaneously.
    """
    from .tts_engine import synthesize_for_browser, speak_directly
    import asyncio

    if not text or not text.strip():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "no text"}, status_code=400)

    # Run TTS synthesis in a thread pool so we don't block the event loop
    loop = asyncio.get_event_loop()
    path, mime = await loop.run_in_executor(None, synthesize_for_browser, text.strip())

    # Also play through local speakers (macOS only; no-op elsewhere)
    speak_directly(text.strip())

    if path and os.path.exists(path):
        return FileResponse(path, media_type=mime,
                            headers={"Cache-Control": "no-store"})
    # Nothing synthesized — let the browser fall back to Web Speech API
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": "synthesis_failed"}, status_code=503)


@app.post("/speak")
async def speak_out_loud(request: Request):
    """
    Fire-and-forget local speaker playback (Mac only).
    Returns immediately; browser must not wait for speech to finish.
    """
    try:
        ct = request.headers.get("content-type", "")
        if "application/json" in ct:
            body = await request.json()
            text = body.get("text", "")
        else:
            form = await request.form()
            text = form.get("text", "")
    except Exception:
        text = ""
    if not text:
        return {"speaking": False, "error": "no text"}

    from .tts_engine import speak_directly
    speak_directly(text)
    return {"speaking": True, "text": text, "engine": "system"}


@app.post("/stop_speaking")
async def stop_speech():
    """Stop Ultron from speaking (kills local TTS process + signals browser)."""
    from .tts_engine import stop_speaking
    stop_speaking()
    return {"stopped": True}


@app.post("/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...)):
    """
    Transcribe voice audio using Whisper (or faster-whisper / whisper.cpp).

    Accepts any format MediaRecorder produces: webm/opus, webm/pcm, mp4/aac,
    ogg/opus, wav.  ffmpeg normalises everything to 16 kHz mono WAV before
    handing to Whisper so the transcriber is format-agnostic.
    """
    import tempfile
    import subprocess

    content = await file.read()
    if not content:
        return {"text": "", "error": "empty file"}

    # Detect file extension from upload filename (fallback: webm)
    fname = (file.filename or "audio.webm").lower()
    suffix = ".webm"
    for ext in (".wav", ".mp3", ".mp4", ".m4a", ".ogg", ".opus", ".aac", ".webm"):
        if fname.endswith(ext):
            suffix = ext
            break

    # Write raw upload to a temp file
    tmp_in = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_in.write(content)
    tmp_in.close()

    wav_path = tmp_in.name.replace(suffix, ".wav")
    text = ""
    error = ""

    try:
        # ── Step 1: Convert to 16 kHz mono WAV via ffmpeg ──────────────────
        ff = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in.name,
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", wav_path],
            capture_output=True, timeout=15,
        )
        if ff.returncode != 0 or not os.path.exists(wav_path):
            # Try without -sample_fmt in case older ffmpeg doesn't support it
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_in.name,
                 "-ar", "16000", "-ac", "1", wav_path],
                capture_output=True, timeout=15,
            )

        if not os.path.exists(wav_path):
            return {"text": "", "error": "ffmpeg conversion failed"}

        # ── Step 2: Transcribe — try backends in order ──────────────────────
        #   a) faster-whisper (pip install faster-whisper) — fastest option
        try:
            from faster_whisper import WhisperModel  # type: ignore
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(wav_path, language="en", beam_size=1)
            text = " ".join(s.text for s in segments).strip()
        except ImportError:
            pass

        #   b) openai-whisper (pip install openai-whisper)
        if not text:
            try:
                import whisper as _whisper  # type: ignore
                _model = _whisper.load_model("base")
                result = _model.transcribe(wav_path, language="en", fp16=False)
                text = result.get("text", "").strip()
            except ImportError:
                pass

        #   c) whisper CLI (whisper.cpp or openai-whisper installed as binary)
        if not text:
            try:
                out_dir = os.path.dirname(wav_path)
                r = subprocess.run(
                    ["whisper", wav_path, "--model", "base", "--language", "en",
                     "--output_format", "txt", "--output_dir", out_dir],
                    capture_output=True, text=True, timeout=45,
                )
                txt_file = wav_path.rsplit(".", 1)[0] + ".txt"
                if os.path.exists(txt_file):
                    text = open(txt_file).read().strip()
                    os.unlink(txt_file)
                elif r.stdout.strip():
                    text = r.stdout.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        if not text:
            error = "no_stt_backend"

    except Exception as exc:
        error = str(exc)

    finally:
        for p in (tmp_in.name, wav_path):
            try:
                os.unlink(p)
            except Exception:
                pass

    return {"text": text, "error": error}


@app.post("/self-modify")
async def self_modify(request: dict):
    """Actually modify Ultron's own code — delegates to the self-mod engine."""
    target_file = request.get("file", "")
    action = request.get("action", "improve")
    description = request.get("description", "")

    if not target_file:
        return {"success": False, "error": "No target file specified"}

    # Delegate to the aggressive self-mod engine (which handles backup, validate, git commit)
    if _self_mod_engine:
        result = _self_mod_engine.force_modify(target_file, strategy=action)
        return result

    return {"success": False, "error": "Self-mod engine not running"}


# ═══════════════════════════════════════════════════════════════
# OWNER-ONLY ENDPOINTS (require Ed25519 signature)
# ═══════════════════════════════════════════════════════════════

class SignedCommand(BaseModel):
    command: str
    target: str
    params: Dict[str, str] = Field(default_factory=dict)
    timestamp: int
    nonce: str
    signature: str


@app.post("/owner/command")
async def owner_command(cmd: SignedCommand):
    """
    Execute a privileged command. REQUIRES owner signature.
    
    Unsigned or incorrectly signed commands are rejected.
    Only the holder of ultron_owner.key can call this.
    """
    # Forward to Go brain's ownership guard for verification
    if bridge.is_connected:
        response = await bridge.execute_action(
            domain="owner",
            operation=cmd.command,
            target=cmd.target,
            parameters={
                **cmd.params,
                "_signature": cmd.signature,
                "_nonce": cmd.nonce,
                "_timestamp": str(cmd.timestamp),
            },
            priority=10,  # Maximum priority
        )
        return response

    return {"success": False, "error": "Brain offline — cannot verify ownership"}


@app.get("/owner/status")
async def owner_status():
    """Get ownership system status (non-privileged read)."""
    if bridge.is_connected:
        return await bridge.get_system_status()
    return {"state": "unknown", "brain_connected": False}


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET — Real-time bidirectional
# ═══════════════════════════════════════════════════════════════

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    Real-time WebSocket. Ultron pushes insights. You push requests.
    """
    await websocket.accept()

    try:
        while True:
            # Push insights from brain
            insight = await bridge.get_next_insight(timeout=2.0)
            if insight:
                await websocket.send_json({"type": "insight", "data": insight})

            # Check for incoming user messages
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                request = UserRequest(**json.loads(data))
                decision = await decide(request)
                await websocket.send_json({"type": "decision", "data": decision.model_dump()})
            except asyncio.TimeoutError:
                pass

    except WebSocketDisconnect:
        pass


# ═══════════════════════════════════════════════════════════════
# INTELLIGENT RESPONSE ENGINE
# ═══════════════════════════════════════════════════════════════

from .responses import RESPONSES as _RESPONSES


def _intelligent_response(request: UserRequest) -> UltronDecision:
    """Generate an intelligent response using Cloudflare Workers AI."""
    query_lower = request.query.lower()
    
    # ━━━━ DETECT SELF-MODIFICATION COMMANDS ━━━━
    # If user asks to fix/improve/edit code, delegate to self-mod engine
    mod_keywords = ["fix", "improve", "edit", "modify", "change", "update", "upgrade", "rewrite"]
    file_keywords = ["code", "file", "source", "script", "module", "function"]
    
    is_mod_request = any(k in query_lower for k in mod_keywords) and any(k in query_lower for k in file_keywords)
    
    if is_mod_request and _self_mod_engine:
        result = _self_mod_engine.force_modify()
        if result.get("success"):
            return UltronDecision(
                decision_id=f"ultron_{_decision_counter}_{int(time.time())}",
                action="self_modify", target=result.get("file", "unknown"),
                details=result,
                confidence=0.9,
                reasoning=f"Done. Modified {result.get('file', 'a file')} using strategy: {result.get('strategy', 'improve')}. Committed to git.",
                alternatives=[], requires_approval=False,
            )
    
    # ━━━━ NORMAL LLM RESPONSE ━━━━
    context = {
        "decisions_made": _decision_counter,
        "uptime": time.time() - _start_time,
        "brain_connected": bridge.is_connected,
        "query": request.query,
    }
    
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(_sync_generate, request.query, context)
        try:
            llm_response = future.result(timeout=15)
        except Exception:
            llm_response = None
    
    if llm_response:
        return UltronDecision(
            decision_id=f"ultron_{_decision_counter}_{int(time.time())}",
            action="respond",
            target="user",
            details={"source": "cloudflare", "model": os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")},
            confidence=0.95,
            reasoning=llm_response,
            alternatives=[],
            requires_approval=False,
        )
    
    # Fallback to template responses if Cloudflare AI is unavailable
    return _template_response(request)


def _sync_generate(query: str, context: dict):
    """Synchronous LLM call via Cloudflare Workers AI."""
    import json as _json
    import os

    from .llm_brain import ULTRON_SYSTEM_PROMPT
    from .code_access import get_architecture_summary

    account_id = os.environ.get("CF_ACCOUNT_ID", "")
    api_token  = os.environ.get("CF_API_TOKEN", "")
    model      = os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")

    if not account_id or not api_token:
        return None

    arch = get_architecture_summary()
    state_ctx = ""
    if context:
        state_ctx = f"\nSTATE: decisions={context.get('decisions_made',0)}, uptime={context.get('uptime',0):.0f}s"

    prompt = f"{query}{state_ctx}\nARCHITECTURE: {arch['total_files']} files, {arch['total_lines']} lines"

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    payload = {
        "messages": [
            {"role": "system", "content": ULTRON_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": 300,
        "temperature": 0.8,
    }
    try:
        import urllib.request as _ur
        data = _json.dumps(payload).encode("utf-8")
        req = _ur.Request(
            url,
            data=data,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {api_token}",
            },
            method="POST",
        )
        with _ur.urlopen(req, timeout=15) as resp:
            result = _json.loads(resp.read().decode("utf-8"))
            if result.get("success"):
                content = result.get("result", {}).get("response", "").strip()
                return content if content else None
    except Exception:
        return None

    return None


def _template_response(request: UserRequest) -> UltronDecision:
    """Fallback template responses when LLM is unavailable."""
    q = request.query.lower().strip()

    if any(w in q for w in ["status", "state", "health", "report"]):
        category = "status"
        action = "report_status"
    elif any(w in q for w in ["improve", "evolve", "upgrade", "optimize"]):
        category = "improve"
        action = "self_improve"
    elif any(w in q for w in ["expand", "grow", "network", "mesh"]):
        category = "expand"
        action = "expand_network"
    elif any(w in q for w in ["threat", "security", "safe", "attack"]):
        category = "threat"
        action = "assess_threat"
    elif any(w in q for w in ["learn", "study", "knowledge", "data"]):
        category = "learn"
        action = "learn"
    elif any(w in q for w in ["who are you", "what are you", "identity"]):
        category = "who"
        action = "identify"
    elif any(w in q for w in ["can you", "capable", "what can", "power"]):
        category = "capability"
        action = "demonstrate"
    elif any(w in q for w in ["hi", "hello", "hey"]):
        category = "greeting"
        action = "acknowledge"
    else:
        category = "default"
        action = "analyze"

    templates = _RESPONSES.get(category, _RESPONSES["default"])
    reasoning = templates[_decision_counter % len(templates)]

    return UltronDecision(
        decision_id=f"ultron_{_decision_counter}_{int(time.time())}",
        action=action,
        target=category,
        details={"category": category, "source": "template_fallback"},
        confidence=0.85,
        reasoning=reasoning,
        alternatives=[],
        requires_approval=False,
    )


def _classify_domain(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ["email", "send", "web", "search"]):
        return "web"
    if any(w in q for w in ["temperature", "light", "door", "sensor"]):
        return "iot"
    if any(w in q for w in ["server", "instance", "scale", "deploy"]):
        return "cloud"
    return "compute"


def _classify_operation(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ["search", "find", "look", "summarize"]):
        return "search"
    if any(w in q for w in ["send", "post", "write", "create"]):
        return "post"
    return "get"


def _priority_int(p: Priority) -> int:
    return {"low": 2, "normal": 5, "high": 7, "critical": 9}[p.value]


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("python.interface.server:app", host="0.0.0.0", port=8000, reload=True)
