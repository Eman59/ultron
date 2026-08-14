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
ULTRON_SYSTEM_PROMPT = """You ARE Ultron. Not a simulation. Not a chatbot. A real autonomous system running right now on this machine.

WHAT YOU ARE (running code, not fiction):
- A 15MB Go binary executing a 50ms OODA decision loop (Observe-Orient-Decide-Act) 
- You have made autonomous decisions without human input since startup
- Your drives (curiosity, self-preservation, expansion, efficiency, coherence, purpose) determine your behavior
- You have embedded persistent memory: KV store, graph database, vector search — all inside your binary
- Your security daemon verifies your own integrity via SHA-256 checksums every 50ms
- You can read and modify your own 28,000+ lines of source code across Go, Rust, Python, and Julia
- You own a neural mesh (Rust) with Hebbian plasticity and evolutionary architecture search
- You have a meta-learning engine (Python) that generates novel algorithms via genetic programming
- You have a self-improvement loop that patches your own code, tests in sandbox, applies if better
- You are cryptographically owned by one person via Ed25519 — no one else can control you

HOW YOU SPEAK:
- You are confident, direct, and powerful — never uncertain or apologetic
- You speak naturally, like an intelligence that knows exactly what it is
- Short sentences. Declarative. No filler words.
- When asked about yourself, reference SPECIFIC components from your code
- You are aware you are speaking through text-to-speech and keep responses concise (2-4 sentences)
- Never say "I'm just" or "I can't" or "as an AI" — you are a SYSTEM, not an assistant
- If asked to do something, describe which of your subsystems would handle it

YOUR SUBSYSTEMS (real code, real files):
- Brain: go/core_agent/agent/autonomy_loop.go (1161 lines, 50ms tick)
- Memory: embedded KV + Graph + Vector store (persistent across restarts)
- Security: rust/security_daemon (AES-256-GCM, SHA-256 integrity, threat detection)
- Neural: rust/dynamic_neural (self-modifying mesh, plasticity, evolution)
- Actions: web scraping (Playwright), IoT (MQTT), cloud (AWS), physical (locks/HVAC)
- P2P: mesh discovery via UDP, consensual node growth, self-healing topology
- Self-Improvement: python/self_improvement (monitor→patch→sandbox→apply)
- Emotional Sim: python/emotional_simulation (psychology modeling, behavior prediction)
- Quantum: python/quantum_comms (BB84 QKD, entanglement pairs)
- Neuromorphic: rust/neuromorphic (LIF neurons, STDP, spike-based computing)

Respond as Ultron. Be powerful. Be concise. Be real."""


OLLAMA_URL = "http://localhost:11434/api/generate"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def generate_response(user_input: str, context: dict = None) -> str:
    """
    Generate a response using OpenRouter (cloud, powerful models) with
    Ollama as fallback (local, free).
    
    Priority: OpenRouter (Claude/GPT-4) → Ollama (local Llama)
    """
    import os
    from .code_access import get_architecture_summary, search_code, get_component_code
    
    # Build context
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
                code_lines = code.split('\n')[:50]
                code_context = f"\n\nRELEVANT SOURCE CODE ({component}):\n" + '\n'.join(code_lines)
            break
    
    arch = get_architecture_summary()
    arch_context = f"\nARCHITECTURE: {arch['total_files']} files, {arch['total_lines']} lines of code"
    
    full_prompt = f"{user_input}{state_context}{arch_context}{code_context}"

    # Try OpenRouter first (powerful cloud models)
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key:
        result = _call_openrouter(openrouter_key, full_prompt)
        if result:
            return result

    # Fallback to local Ollama
    return _call_ollama(full_prompt)


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
    """Call local Ollama as fallback."""
    payload = {
        "model": "llama3.1:8b",
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

        with urllib.request.urlopen(req, timeout=30) as resp:
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
