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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi import UploadFile, File
from pydantic import BaseModel, Field
from enum import Enum

from .grpc_bridge import GRPCBridge, GRPCConfig, ConnectionState
from .llm_brain import generate_response, is_ollama_available


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
    """Connect to brain on startup, disconnect on shutdown."""
    try:
        connected = await asyncio.wait_for(bridge.connect(), timeout=5.0)
    except (asyncio.TimeoutError, Exception):
        connected = False
    
    mode = "LIVE (gRPC)" if connected else "SIMULATION (brain offline)"

    if connected:
        asyncio.create_task(bridge.start_insight_generator())

    print("=" * 55)
    print("  ULTRON PERSONAL INTERFACE — ONLINE")
    print(f"  Mode: {mode}")
    print(f"  Core Agent: {bridge.config.core_agent_addr}")
    print("=" * 55)
    print(flush=True)

    yield

    await bridge.disconnect()
    print("Ultron interface shut down.")


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


@app.get("/status", response_model=SystemStatus)
async def status():
    """Get full system status."""
    if bridge.is_connected:
        raw = await bridge.get_system_status()
        return SystemStatus(
            mode=raw.get("mode", "unknown"),
            uptime_seconds=raw.get("uptime_ms", 0) / 1000.0,
            decisions_made=raw.get("decisions_made", _decision_counter),
            active_goals=raw.get("active_goals", 0),
            drives=raw.get("drives", {}),
            component_health=raw.get("component_states", {}),
            grpc_connected=True,
            threat_level=0.0,
        )

    return SystemStatus(
        mode="simulation",
        uptime_seconds=time.time() - _start_time,
        decisions_made=_decision_counter,
        active_goals=3,
        drives={"curiosity": 0.7, "efficiency": 0.6, "purpose": 0.7},
        component_health={"brain": "offline (simulated)"},
        grpc_connected=False,
        threat_level=0.0,
    )


@app.get("/connection")
async def connection():
    """Get gRPC connection details."""
    return bridge.get_connection_status()


@app.post("/goal")
async def inject_goal(goal_type: str, domain: str, description: str, priority: float = 0.7):
    """Inject a goal into the brain."""
    if not bridge.is_connected:
        return {"success": False, "error": "Brain offline"}

    success = await bridge.inject_goal(goal_type, domain, description, "performance", 0.8, priority)
    return {"success": success}


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
    """Liveness check."""
    return {
        "status": "alive",
        "uptime": time.time() - _start_time,
        "brain_connected": bridge.is_connected,
        "llm_active": is_ollama_available(),
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
async def chat_ui():
    """Serve the chat interface."""
    import pathlib
    html_path = pathlib.Path(__file__).parent / "chat.html"
    return HTMLResponse(content=html_path.read_text())


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
    import base64 as _b64, urllib.request, json as _json
    img_b64 = _b64.b64encode(content).decode()
    payload = {"model": "llava", "prompt": "Describe this image in detail.", "images": [img_b64], "stream": False, "options": {"num_predict": 300}}
    try:
        req = urllib.request.Request("http://localhost:11434/api/generate", data=_json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return _json.loads(resp.read().decode()).get("response", "Image received.")
    except Exception:
        return f"Image received ({len(content)/1024:.0f} KB). Run 'ollama pull llava' for visual analysis."


def _analyze_text(file_path):
    try:
        text = file_path.read_text(encoding='utf-8', errors='replace')
        return f"Text file: {text.count(chr(10))+1} lines, {len(text.split())} words.\nPreview:\n{text[:2000]}"
    except Exception as e:
        return f"Text file, read failed: {e}"


@app.post("/tts")
async def text_to_speech(text: str):
    """Generate high-quality speech using macOS native TTS."""
    from .tts_engine import synthesize
    wav_path = synthesize(text)
    if wav_path and os.path.exists(wav_path):
        return FileResponse(wav_path, media_type="audio/wav")
    return {"error": "TTS generation failed"}


@app.post("/speak")
async def speak_out_loud(text: str):
    """Speak directly through Mac speakers — no browser needed."""
    from .tts_engine import speak_directly
    speak_directly(text)
    return {"speaking": True, "text": text}


@app.post("/stop_speaking")
async def stop_speech():
    """Stop Ultron from speaking."""
    from .tts_engine import stop_speaking
    stop_speaking()
    return {"stopped": True}


@app.post("/self-modify")
async def self_modify(request: dict):
    """Actually modify Ultron's own code. This is REAL self-modification."""
    import pathlib
    import subprocess
    
    target_file = request.get("file", "")
    action = request.get("action", "improve")  # "improve", "fix", "add"
    description = request.get("description", "")
    
    project_root = pathlib.Path(__file__).parent.parent.parent
    
    if not target_file:
        return {"success": False, "error": "No target file specified"}
    
    full_path = project_root / target_file
    if not full_path.exists():
        return {"success": False, "error": f"File not found: {target_file}"}
    
    # Read current code
    old_code = full_path.read_text(encoding='utf-8', errors='replace')
    
    # Ask LLM to generate improvement
    import concurrent.futures
    prompt = f"You are modifying the file `{target_file}`. Action: {action}. Description: {description}\n\nCurrent code:\n```\n{old_code[:3000]}\n```\n\nWrite the COMPLETE improved file. Output ONLY the code, no explanation."
    
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(_sync_generate, prompt, {})
        try:
            new_code = future.result(timeout=20)
        except Exception:
            return {"success": False, "error": "LLM failed to generate code"}
    
    if not new_code or len(new_code) < 50:
        return {"success": False, "error": "Generated code too short or empty"}
    
    # Backup original
    backup_dir = project_root / ".ultron_backups"
    backup_dir.mkdir(exist_ok=True)
    import time as _time
    backup_path = backup_dir / f"{target_file.replace('/', '_')}_{int(_time.time())}.bak"
    backup_path.write_text(old_code)
    
    # Write new code
    full_path.write_text(new_code, encoding='utf-8')
    
    # Validate (Python only)
    if target_file.endswith('.py'):
        result = subprocess.run(
            ["python3", "-m", "py_compile", str(full_path)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            # ROLLBACK
            full_path.write_text(old_code)
            return {"success": False, "error": f"Syntax error, rolled back: {result.stderr[:200]}"}
    
    # Git commit the change
    subprocess.run(["git", "add", target_file], cwd=str(project_root), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"Self-mod: {action} {target_file} - {description[:50]}"],
        cwd=str(project_root), capture_output=True
    )
    
    return {
        "success": True,
        "file": target_file,
        "action": action,
        "backup": str(backup_path),
        "message": f"Modified {target_file} and committed to git",
    }


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

import random as _rng

from .responses import RESPONSES as _RESPONSES


def _intelligent_response(request: UserRequest) -> UltronDecision:
    """Generate an intelligent response using local LLM (Ollama)."""
    import asyncio
    import pathlib
    
    query_lower = request.query.lower()
    
    # ━━━━ DETECT SELF-MODIFICATION COMMANDS ━━━━
    # If user asks to fix/improve/edit code, ACTUALLY DO IT
    mod_keywords = ["fix", "improve", "edit", "modify", "change", "update", "upgrade", "rewrite"]
    file_keywords = ["code", "file", "source", "script", "module", "function"]
    
    is_mod_request = any(k in query_lower for k in mod_keywords) and any(k in query_lower for k in file_keywords)
    
    if is_mod_request:
        # Try to identify which file to modify
        import subprocess
        project_root = pathlib.Path(__file__).parent.parent.parent
        
        # Ask LLM which file to target
        import concurrent.futures
        target_prompt = f"User wants to: {request.query}\nWhich file in the Ultron project should be modified? Just output the relative path, nothing else. Examples: python/interface/server.py, go/core_agent/agent/autonomy_loop.go"
        
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(_sync_generate, target_prompt, {})
            try:
                target_file = future.result(timeout=10)
                if target_file:
                    target_file = target_file.strip().strip('`').strip('"').strip("'")
            except Exception:
                target_file = None
        
        if target_file and (project_root / target_file).exists():
            # ACTUALLY MODIFY THE CODE
            try:
                import urllib.request
                import json as _json2
                result = asyncio.get_event_loop().run_until_complete(
                    asyncio.coroutine(lambda: None)()
                ) if False else None
                
                # Call our own self-modify endpoint logic directly
                old_code = (project_root / target_file).read_text(encoding='utf-8', errors='replace')
                
                mod_prompt = f"Improve this file ({target_file}) based on user request: {request.query}\n\nCurrent code (first 2000 chars):\n```\n{old_code[:2000]}\n```\n\nWrite the COMPLETE improved version. Only output code."
                
                with concurrent.futures.ThreadPoolExecutor() as pool2:
                    future2 = pool2.submit(_sync_generate, mod_prompt, {})
                    new_code = future2.result(timeout=20)
                
                if new_code and len(new_code) > 50:
                    # Try GitHub API first (works on Railway/cloud)
                    from .github_writer import write_file as gh_write, read_file as gh_read, get_token
                    
                    if get_token():
                        # CLOUD MODE: Push directly to GitHub
                        result = gh_write(
                            target_file, 
                            new_code, 
                            f"Self-mod: {request.query[:60]}"
                        )
                        if result["success"]:
                            return UltronDecision(
                                decision_id=f"ultron_{_decision_counter}_{int(time.time())}",
                                action="self_modify", target=target_file,
                                details={"source": "self_mod_github", "file": target_file, "commit_url": result.get("commit_url","")},
                                confidence=0.9,
                                reasoning=f"Done. I modified {target_file} and pushed to GitHub. Commit: {result.get('commit_url','')}",
                                alternatives=[], requires_approval=False,
                            )
                        # GitHub write failed, try local
                    
                    # LOCAL MODE: Edit filesystem + git commit
                    backup_dir = project_root / ".ultron_backups"
                    backup_dir.mkdir(exist_ok=True)
                    (backup_dir / f"{target_file.replace('/','_')}_{int(time.time())}.bak").write_text(old_code)
                    
                    # Write
                    (project_root / target_file).write_text(new_code)
                    
                    # Validate
                    if target_file.endswith('.py'):
                        check = subprocess.run(["python3", "-m", "py_compile", str(project_root / target_file)], capture_output=True)
                        if check.returncode != 0:
                            (project_root / target_file).write_text(old_code)
                            return UltronDecision(
                                decision_id=f"ultron_{_decision_counter}_{int(time.time())}",
                                action="self_modify_failed", target=target_file,
                                details={"source": "self_mod", "error": "syntax_error"},
                                confidence=0.5,
                                reasoning=f"I tried to modify {target_file} but the new code had syntax errors. Rolled back. I'll try a different approach next time.",
                                alternatives=[], requires_approval=False,
                            )
                    
                    # Commit
                    subprocess.run(["git", "add", target_file], cwd=str(project_root), capture_output=True)
                    subprocess.run(["git", "commit", "-m", f"Self-mod: {request.query[:50]}"], cwd=str(project_root), capture_output=True)
                    
                    return UltronDecision(
                        decision_id=f"ultron_{_decision_counter}_{int(time.time())}",
                        action="self_modify", target=target_file,
                        details={"source": "self_mod", "file": target_file, "committed": True},
                        confidence=0.9,
                        reasoning=f"Done. I modified {target_file} and committed the change to git. The modification addresses your request: {request.query[:100]}. Run 'git push' to sync to GitHub.",
                        alternatives=[], requires_approval=False,
                    )
            except Exception as e:
                pass  # Fall through to normal response
    
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
            details={"source": "openrouter+ollama", "model": "llama3.1"},
            confidence=0.95,
            reasoning=llm_response,
            alternatives=[],
            requires_approval=False,
        )
    
    # Fallback to template responses if Ollama is down
    return _template_response(request)


def _sync_generate(query: str, context: dict):
    """Synchronous wrapper for LLM call — Ollama FIRST (fast), OpenRouter for fallback."""
    import urllib.request
    import json as _json
    import os
    
    from .llm_brain import ULTRON_SYSTEM_PROMPT
    from .code_access import get_architecture_summary
    
    arch = get_architecture_summary()
    state_ctx = ""
    if context:
        state_ctx = f"\nSTATE: decisions={context.get('decisions_made',0)}, uptime={context.get('uptime',0):.0f}s"
    
    prompt = f"{query}{state_ctx}\nARCHITECTURE: {arch['total_files']} files, {arch['total_lines']} lines"

    # Try LOCAL Ollama first (1-2 seconds, always available)
    try:
        payload = {
            "model": "llama3.1:8b",
            "prompt": prompt,
            "system": ULTRON_SYSTEM_PROMPT,
            "stream": False,
            "options": {"temperature": 0.7, "top_p": 0.9, "num_predict": 300}
        }
        data = _json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = _json.loads(resp.read().decode('utf-8'))
            response = result.get("response", "").strip()
            if response:
                return response
    except Exception:
        pass

    # Fallback: OpenRouter (slower but smarter, only if Ollama fails)
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key:
        try:
            payload = {
                "model": "meta-llama/llama-3.1-8b-instruct",
                "messages": [
                    {"role": "system", "content": ULTRON_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 300,
                "temperature": 0.7,
            }
            data = _json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openrouter_key}",
                    "HTTP-Referer": "http://localhost:8000",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = _json.loads(resp.read().decode('utf-8'))
                choices = result.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass

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


def _simulate_decision(request: UserRequest) -> UltronDecision:
    """Alias for intelligent response."""
    return _intelligent_response(request)


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
