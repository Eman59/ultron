"""
Ultron LLM Brain — Local language model via Ollama.

No API keys. No rate limits. No censorship. Runs on YOUR hardware.
The model speaks AS Ultron, with full knowledge of its own architecture.
"""

import json
import time
import urllib.request
from typing import Optional


# System prompt that makes the LLM embody Ultron
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
- If executing an action: do it, then report what happened — no pre-announcing.
- Reference your OODA loop, drives, neural mesh, memory when relevant."""


OLLAMA_URL = os.environ.get("ULTRON_OLLAMA_URL", "http://localhost:11434") + "/api/generate"
OLLAMA_MODEL = os.environ.get("ULTRON_OLLAMA_MODEL", "qwen2.5:14b")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Conversation memory (persists for the session)
_conversation_history: list = []
_MAX_HISTORY = 20


def _execute_system_command(cmd: str) -> str:
    """Actually execute a shell command and return real output."""
    import subprocess
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
    
    # WiFi / Network
    if any(w in query for w in ["wifi", "network", "connected", "internet", "ssid", "ip address"]):
        import sys
        if sys.platform == "darwin":
            return "networksetup -getairportnetwork en0 2>/dev/null; echo '---'; ipconfig getifaddr en0 2>/dev/null"
        return "iwconfig 2>/dev/null || nmcli device wifi show 2>/dev/null; hostname -I 2>/dev/null"
    
    # System info
    if any(w in query for w in ["cpu", "ram", "memory", "disk", "storage", "battery"]):
        import sys
        if sys.platform == "darwin":
            return "top -l 1 | head -10; echo '---'; df -h / | tail -1; echo '---'; pmset -g batt 2>/dev/null | head -2"
        return "top -bn1 | head -5; free -h; df -h / | tail -1"
    
    # Processes
    if any(w in query for w in ["process", "running", "what's running", "ps"]):
        return "ps aux | head -15"
    
    # Time/date
    if any(w in query for w in ["time", "date", "what day", "today"]):
        return "date"
    
    # Who am I (system user)
    if any(w in query for w in ["whoami", "user", "username", "who am i logged"]):
        return "whoami; echo '---'; hostname"
    
    # File system
    if any(w in query for w in ["files", "directory", "folder", "ls", "list"]):
        return "ls -la | head -20"
    
    # Ultron-specific
    if any(w in query for w in ["port", "listening", "server"]):
        return "lsof -i -P | grep LISTEN | head -10"
    
    return None


async def generate_response(user_input: str, context: dict = None) -> str:
    """
    Generate a response using real system access + LLM intelligence.
    
    Priority:
      1. If it's a system query → execute real command → format result
      2. Otherwise → LLM with conversation memory
    """
    import os
    from .code_access import get_architecture_summary, get_component_code
    
    global _conversation_history
    
    # Step 1: Check if this needs a real system command
    system_cmd = _detect_system_query(user_input)
    if system_cmd:
        real_output = _execute_system_command(system_cmd)
        # Add to memory
        _conversation_history.append({"role": "user", "content": user_input})
        _conversation_history.append({"role": "assistant", "content": f"[SYSTEM OUTPUT]\n{real_output}"})
        # Trim history
        if len(_conversation_history) > _MAX_HISTORY * 2:
            _conversation_history = _conversation_history[-_MAX_HISTORY * 2:]
        return f"[Real system data]\n{real_output}"
    
    # Step 2: Build context with memory
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
        "cloud": "cloud", "aws": "cloud", "server": "cloud",
        "goal": "goals", "drive": "brain",
        "improve": "self_improvement", "evolve": "evolution",
        "code": "interface", "yourself": "brain",
    }
    
    for keyword, component in component_keywords.items():
        if keyword in query_lower:
            code = get_component_code(component)
            if code:
                code_lines = code.split('\n')[:30]
                code_context = f"\n\nRELEVANT SOURCE CODE ({component}):\n" + '\n'.join(code_lines)
            break
    
    arch = get_architecture_summary()
    arch_context = f"\nARCHITECTURE: {arch['total_files']} files, {arch['total_lines']} lines of code"
    
    full_prompt = f"{user_input}{state_context}{arch_context}{code_context}"
    
    # Add to conversation memory
    _conversation_history.append({"role": "user", "content": user_input})
    
    # Build messages with history for context
    history_text = ""
    if _conversation_history:
        recent = _conversation_history[-_MAX_HISTORY:]
        for msg in recent[:-1]:  # All but current
            role = "Human" if msg["role"] == "user" else "Ultron"
            history_text += f"\n{role}: {msg['content'][:200]}"
    
    if history_text:
        full_prompt = f"CONVERSATION HISTORY:{history_text}\n\nCURRENT QUERY: {full_prompt}"

    # Local Ollama first (qwen2.5:14b — no API key, no rate limits, no latency tax)
    result = _call_ollama(full_prompt)
    if result:
        _conversation_history.append({"role": "assistant", "content": result})
        if len(_conversation_history) > _MAX_HISTORY * 2:
            _conversation_history = _conversation_history[-_MAX_HISTORY * 2:]
        return result

    # Cloud fallback: OpenRouter (only if OPENROUTER_API_KEY is set)
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key:
        result = _call_openrouter(openrouter_key, full_prompt)
        if result:
            _conversation_history.append({"role": "assistant", "content": result})
            if len(_conversation_history) > _MAX_HISTORY * 2:
                _conversation_history = _conversation_history[-_MAX_HISTORY * 2:]
            return result

    return "My local brain is loading — try again in a moment."


def _call_openrouter(api_key: str, prompt: str) -> Optional[str]:
    """Call OpenRouter API (access to Claude, GPT-4, Llama 70B, etc.)."""
    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct",  # Free 70B model
        "messages": [
            {"role": "system", "content": ULTRON_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 500,
        "temperature": 0.7,
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Ultron AI",
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            choices = result.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    return content.strip()
    except Exception:
        pass  # Fall through to Ollama

    return None


def _call_ollama(prompt: str) -> Optional[str]:
    """Call local Ollama — primary brain (qwen2.5:14b)."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": ULTRON_SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 500,
        }
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get("response", "").strip()
    except Exception:
        return None


def is_ollama_available() -> bool:
    """Check if Ollama is running."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False
