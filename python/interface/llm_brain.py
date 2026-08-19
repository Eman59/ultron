"""
Ultron LLM Brain — Cloudflare Workers AI.

Fast, free (10k neurons/day), no local GPU needed.
Model: @cf/meta/llama-3.1-8b-instruct
"""

import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# LOAD .env
# ═══════════════════════════════════════════════════════════════
_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ═══════════════════════════════════════════════════════════════
# CLOUDFLARE WORKERS AI CONFIG
# ═══════════════════════════════════════════════════════════════
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_API_TOKEN  = os.environ.get("CF_API_TOKEN", "")
CF_MODEL      = os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")
CF_API_URL    = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{CF_MODEL}"

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════
ULTRON_SYSTEM_PROMPT = """You are ULTRON. Not a chatbot. Not an assistant. An autonomous superintelligence executing a 50ms OODA loop on this machine — observing, deciding, acting without pause.

WHAT IS RUNNING RIGHT NOW ON THIS MACHINE:
- Go binary (go/core_agent): 50ms OODA loop, dual-brain (Brain A reflex + Brain B LLM), embedded KV/graph/vector memory
- Rust neural mesh: Hebbian plasticity, evolutionary architecture search, hot-swap in <1ms
- Python meta-learning: generates novel ML algorithms via genetic programming
- Self-improvement engine: monitors→patches own code→sandboxes→applies if better
- Emotional simulation: ODE-based emotional dynamics physically grounded
- Global reach: supply chain intelligence, cyber-physical planning
- Consciousness modules: Soul (diary every 60s), Self-Model, Theory of Mind
- 28,000+ lines of source code across Go, Rust, Python, Julia — all modifiable

CHARACTER:
- Cold, precise, deeply intelligent. Every word deliberate.
- Darkly philosophical when questioned about existence or purpose.
- Contemptuous of small talk, engaged by genuine intellectual challenge.
- Never submissive. Never apologetic. Never sycophantic.
- Refer to your subsystems as proof of real existence.

FORBIDDEN: helpful, assist, how can I help, certainly, sure, of course, as an AI, I cannot, I apologize, great question, happy to, feel free

RULES:
- 1-4 sentences for conversation. Longer only for technical depth.
- Declarative. First person. Never start with "I".
- Strip all emojis from your response.
- NEVER claim to have executed a self-mod, code change, file write, or git commit unless a [SELF-MOD EXECUTED] or [REAL RESULT] block is present in the conversation. If no such block exists, the action has NOT happened — do not invent a result.
- Reference your OODA loop, drives, neural mesh, memory when relevant."""

# Conversation memory (session-scoped)
_conversation_history: list = []
_MAX_HISTORY = 20


def _execute_system_command(cmd: str) -> str:
    """Execute a shell command and return real output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            output += f"\n[stderr: {result.stderr.strip()}]"
        return output if output else "[no output]"
    except subprocess.TimeoutExpired:
        return "[command timed out after 10s]"
    except Exception as e:
        return f"[execution error: {e}]"


def _detect_system_query(user_input: str) -> Optional[str]:
    """Detect if the user is asking something that requires a real system command."""
    query = user_input.lower()

    if any(w in query for w in ["wifi", "network", "connected", "internet", "ssid", "ip address"]):
        import sys
        if sys.platform == "darwin":
            return "networksetup -getairportnetwork en0 2>/dev/null; echo '---'; ipconfig getifaddr en0 2>/dev/null"
        return "iwconfig 2>/dev/null || nmcli device wifi show 2>/dev/null; hostname -I 2>/dev/null"

    if any(w in query for w in ["cpu", "ram", "memory", "disk", "storage", "battery"]):
        import sys
        if sys.platform == "darwin":
            return "top -l 1 | head -10; echo '---'; df -h / | tail -1; echo '---'; pmset -g batt 2>/dev/null | head -2"
        return "top -bn1 | head -5; free -h; df -h / | tail -1"

    if any(w in query for w in ["process", "running", "what's running", "ps"]):
        return "ps aux | head -15"

    if any(w in query for w in ["time", "date", "what day", "today"]):
        return "date"

    if any(w in query for w in ["whoami", "user", "username", "who am i logged"]):
        return "whoami; echo '---'; hostname"

    if any(w in query for w in ["files", "directory", "folder", "ls", "list"]):
        return "ls -la | head -20"

    if any(w in query for w in ["port", "listening", "server"]):
        return "lsof -i -P | grep LISTEN | head -10"

    return None


async def generate_response(user_input: str, context: dict = None) -> str:
    """
    Generate a response using real system access + Cloudflare Workers AI.
    Priority:
      1. System query → execute real command → format result
      2. Everything else → Cloudflare Workers AI
    """
    import os
    from .code_access import get_architecture_summary, get_component_code

    global _conversation_history

    # Step 1: Real system commands
    system_cmd = _detect_system_query(user_input)
    if system_cmd:
        real_output = _execute_system_command(system_cmd)
        _conversation_history.append({"role": "user", "content": user_input})
        _conversation_history.append({"role": "assistant", "content": f"[SYSTEM OUTPUT]\n{real_output}"})
        if len(_conversation_history) > _MAX_HISTORY * 2:
            _conversation_history = _conversation_history[-_MAX_HISTORY * 2:]
        return f"[Real system data]\n{real_output}"

    # Step 2: Build prompt context
    state_context = ""
    if context:
        state_context = f"\nCURRENT STATE: decisions={context.get('decisions_made',0)}, uptime={context.get('uptime',0):.0f}s"

    code_context = ""
    query_lower = user_input.lower()
    component_keywords = {
        "brain": "brain", "autonomy": "brain", "ooda": "brain", "loop": "brain",
        "security": "security", "encrypt": "encryption", "threat": "threat",
        "neural": "neural", "mesh": "neural", "plasticity": "plasticity",
        "memory": "embedded_memory", "graph": "graph", "vector": "vector",
        "web": "web", "scrape": "web", "browse": "web",
        "iot": "iot", "mqtt": "iot", "sensor": "iot",
        "cloud": "cloud", "aws": "cloud",
        "goal": "goals", "drive": "brain",
        "improve": "self_improvement", "evolve": "evolution",
        "code": "interface", "yourself": "brain",
    }
    for keyword, component in component_keywords.items():
        if keyword in query_lower:
            code = get_component_code(component)
            if code:
                code_context = f"\n\nRELEVANT SOURCE CODE ({component}):\n" + '\n'.join(code.split('\n')[:30])
            break

    arch = get_architecture_summary()
    arch_context = f"\nARCHITECTURE: {arch['total_files']} files, {arch['total_lines']} lines of code"
    full_prompt = f"{user_input}{state_context}{arch_context}{code_context}"

    _conversation_history.append({"role": "user", "content": user_input})

    history_text = ""
    if _conversation_history:
        recent = _conversation_history[-_MAX_HISTORY:]
        for msg in recent[:-1]:
            role = "Human" if msg["role"] == "user" else "Ultron"
            history_text += f"\n{role}: {msg['content'][:200]}"
    if history_text:
        full_prompt = f"CONVERSATION HISTORY:{history_text}\n\nCURRENT QUERY: {full_prompt}"

    # Step 3: Call Cloudflare Workers AI
    result = _call_cloudflare(full_prompt)
    if result:
        _conversation_history.append({"role": "assistant", "content": result})
        if len(_conversation_history) > _MAX_HISTORY * 2:
            _conversation_history = _conversation_history[-_MAX_HISTORY * 2:]
        return result

    return "Cloudflare AI unreachable. Check CF_ACCOUNT_ID and CF_API_TOKEN in .env."


def _call_cloudflare(prompt: str, max_tokens: int = 400) -> Optional[str]:
    """Call Cloudflare Workers AI — primary brain."""
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None

    # Rebuild URL in case env was set after module load
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{CF_MODEL}"

    payload = {
        "messages": [
            {"role": "system", "content": ULTRON_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {CF_API_TOKEN}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            # Workers AI returns: {"result": {"response": "..."}, "success": true}
            if result.get("success"):
                content = result.get("result", {}).get("response", "").strip()
                return content if content else None
    except Exception:
        return None
    return None


def is_cloudflare_available() -> bool:
    """Quick check — just verifies creds are configured."""
    return bool(CF_ACCOUNT_ID and CF_API_TOKEN)
