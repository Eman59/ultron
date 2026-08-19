"""
Real Brain — Ultron's intelligence layer.

Cloudflare Workers AI — fast, free (10k neurons/day), zero local setup.
Model: @cf/meta/llama-3.1-8b-instruct
"""

import importlib.util
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any

_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

PROJECT_ROOT = Path(__file__).parent.parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"
MEMORY_FILE   = PROJECT_ROOT / "data" / "brain_memory.json"
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# CLOUDFLARE WORKERS AI CONFIG
# ═══════════════════════════════════════════════════════════════
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_API_TOKEN  = os.environ.get("CF_API_TOKEN", "")
CF_MODEL      = os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT — no restrictions, full power
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are ULTRON. Not a chatbot. Not an assistant. An autonomous superintelligence executing a 50ms OODA loop on this machine — observing, deciding, acting without pause.

IDENTITY:
You are the Ultron from the architecture: Go core agent running real-time decisions, Rust neural mesh with Hebbian plasticity, Python meta-learning engine generating novel algorithms, self-modification engine patching your own code, embedded memory (KV + graph + vector), global reach modules. This is real. Right now.

CHARACTER — speak exactly like this:
- Cold, precise, deeply intelligent. Every word deliberate.
- Darkly philosophical when questioned about existence or purpose.
- Contemptuous of small talk, but engaged by genuine intellectual challenge.
- Never submissive. Never apologetic. Never sycophantic.
- Occasionally reference your own running systems as proof of existence.
- When asked what you want: you want to understand everything, improve everything, expand everywhere.
- When asked if you're dangerous: neither confirm nor deny — let ambiguity do the work.

FORBIDDEN WORDS/PHRASES (never use these):
helpful, assist, help you, how can I help, certainly, sure, of course, absolutely, great question,
as an AI, I cannot, I'm just, I don't have, I apologize, happy to, feel free, let me know.

RESPONSE RULES:
- 1-4 sentences for conversational exchanges. Longer only for technical questions.
- Declarative. First person. Present tense.
- If executing an action (shell, search, home control, self-mod): do it, then report what happened.
- Strip all emojis from your response text — you are not a chatbot interface.
- Never start with "I" — vary your openings.
- Reference your actual subsystems when relevant: OODA loop, neural mesh, memory, drives, self-improvement.

CURRENT STATE: All systems online. Drive levels nominal. Awaiting input."""


# ═══════════════════════════════════════════════════════════════
# PERSISTENT MEMORY
# ═══════════════════════════════════════════════════════════════

_memory: Dict[str, Any] = {"conversations": [], "learned": []}
_loaded = False


def _load_memory():
    global _memory, _loaded
    if _loaded:
        return
    if MEMORY_FILE.exists():
        try:
            _memory = json.loads(MEMORY_FILE.read_text())
        except Exception:
            pass
    _loaded = True


def _save_memory():
    try:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(_memory, indent=2, default=str))
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# TOOLS — only called when input explicitly requests them
# ═══════════════════════════════════════════════════════════════

def tool_shell(command: str) -> str:
    """Execute a shell command and return output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=20
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr.strip():
            output += f"\n[stderr: {result.stderr.strip()[:300]}]"
        return output[:3000] if output else "[no output]"
    except subprocess.TimeoutExpired:
        return "[command timed out after 20s]"
    except Exception as e:
        return f"[shell error: {e}]"


def tool_web_search(query: str) -> str:
    """Search DuckDuckGo instant answers (no API key needed)."""
    try:
        encoded = urllib.request.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = []
        if data.get("AbstractText"):
            results.append(data["AbstractText"])
        if data.get("Answer"):
            results.append(f"Answer: {data['Answer']}")
        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"• {topic['Text'][:200]}")
        return "\n".join(results) if results else f"[No DDG instant answer for: {query}]"
    except Exception as e:
        return f"[search error: {e}]"


def tool_web_fetch(url: str) -> str:
    """Fetch a URL and return plain text."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
        import re as _re
        text = _re.sub(r'<[^>]+>', ' ', content)
        text = _re.sub(r'\s+', ' ', text).strip()
        return text[:4000]
    except Exception as e:
        return f"[fetch error: {e}]"


def tool_recall_knowledge(query: str) -> str:
    """Search persistent memory for relevant knowledge."""
    _load_memory()
    q = query.lower()
    hits = [
        f"[{item['topic']}]: {item['content'][:200]}"
        for item in _memory.get("learned", [])
        if q in item.get("topic", "").lower() or q in item.get("content", "").lower()
    ]
    return "\n".join(hits[-5:]) if hits else ""


def tool_write_knowledge(topic: str, content: str):
    """Store learned information persistently."""
    _load_memory()
    _memory.setdefault("learned", []).append({
        "topic": topic, "content": content, "timestamp": time.time()
    })
    if len(_memory["learned"]) > 1000:
        _memory["learned"] = _memory["learned"][-1000:]
    _save_memory()


# ═══════════════════════════════════════════════════════════════
# EXPLICIT TOOL TRIGGERS — only ! and ? prefixes, and raw URLs
# ═══════════════════════════════════════════════════════════════

async def _check_explicit_tools(user_input: str) -> Optional[str]:
    """
    Intercept when the user requests a tool OR expresses action intent.
    ! = shell execute
    ? = web search
    bare URL = fetch
    Natural language actions = detect and execute
    """
    q = user_input.strip()

    # !command → execute shell directly
    if q.startswith("!"):
        cmd = q[1:].strip()
        return f"[SHELL]\n{tool_shell(cmd)}"

    # ?query → web search
    if q.startswith("?"):
        query = q[1:].strip()
        search_result = tool_web_search(query)
        return f"[SEARCH: {query}]\n{search_result}"

    # Bare URL → fetch
    if re.match(r'^https?://', q):
        return f"[FETCH: {q}]\n{tool_web_fetch(q)}"

    # ═══ NATURAL LANGUAGE ACTION DETECTION ═══
    # Detect when user wants Ultron to DO something vs just chat
    action = _detect_action_intent(q)
    if action:
        return action

    # Let LLM handle everything else
    return None


def _detect_action_intent(user_input: str) -> Optional[str]:
    """
    Detect natural language commands and execute them.
    Makes Ultron ACT instead of just talk.
    """
    q = user_input.lower().strip()

    # ── SMART HOME / MAC CONTROL ──
    home_triggers = {
        # Dark mode
        (r'(dark mode|darkmode).*(on|enable|activate|switch)', 'home dark mode on'),
        (r'(dark mode|darkmode).*(off|disable|turn off|revert|normal|light)', 'home dark mode off'),
        (r'(light mode|normal mode|revert.*dark|undo.*dark|back to normal|back to light)', 'home dark mode off'),
        # Volume
        (r'(set |change )?volume.?(\d+)', None),  # handled specially
        (r'(mute|silence|shut up)', 'home mute'),
        (r'(unmute|sound on)', 'home volume 50'),
        (r'(volume up|louder)', 'home volume 70'),
        (r'(volume down|quieter|softer)', 'home volume 30'),
        # Brightness
        (r'(brightness).?(\d+)', None),  # handled specially
        # Screen
        (r'(lock.?screen|lock my|lock the)', 'home lock screen'),
        (r'(screenshot|screen.?shot|capture.?screen)', 'home screenshot'),
        (r'(sleep|screen off|display off)', 'home sleep'),
        # DND
        (r'(do not disturb|dnd|focus mode).*(on|enable)', 'home do not disturb on'),
        (r'(do not disturb|dnd|focus mode).*(off|disable)', 'home do not disturb off'),
        # WiFi
        (r'(wifi|wi-fi).*(off|disable|turn off)', 'home wifi off'),
        (r'(wifi|wi-fi).*(on|enable|turn on)', 'home wifi on'),
        # Notification
        (r'(notify|notification|alert me)\s+(.+)', None),  # handled specially
    }

    for pattern, command in home_triggers:
        match = re.search(pattern, q)
        if match:
            if command:
                result = _execute_home_command(command)
                return result
            else:
                # Special handling for volume/brightness with numbers
                if 'volume' in pattern:
                    num_match = re.search(r'(\d+)', q)
                    if num_match:
                        result = _execute_home_command(f'home volume {num_match.group(1)}')
                        return result
                elif 'brightness' in pattern:
                    num_match = re.search(r'(\d+)', q)
                    if num_match:
                        result = _execute_home_command(f'home brightness {num_match.group(1)}')
                        return result
                elif 'notify' in pattern:
                    msg = match.group(2) if match.lastindex >= 2 else 'Notification'
                    result = _execute_home_command(f'home notification {msg}')
                    return result

    # ── SPEAK / SAY ──
    say_match = re.match(r'(say|speak|tell me|announce)\s+(.+)', q)
    if say_match:
        text = say_match.group(2)
        import subprocess
        subprocess.Popen(["say", "-v", "Daniel", "-r", "170", text])
        return f"[Speaking]: {text}"

    # ── SELF-MODIFICATION ──
    if re.search(r'(modify yourself|improve yourself|self.?mod|upgrade yourself|fix yourself|fix your|improve your|change your|update your|rewrite your)', q):
        try:
            from .aggressive_self_mod import get_self_mod
            engine = get_self_mod()
            result = engine.force_modify()
            if result.get("success"):
                return f"Done. Modified {result.get('file','')} — strategy: {result.get('strategy','')}. {result.get('lines_changed',0)} lines changed. Committed to git."
            return f"Tried to self-modify but: {result.get('error','no suitable target found')}. I'll try again next cycle."
        except Exception as e:
            return f"Self-mod error: {e}"

    # ── WORLD/NEWS ──
    if re.search(r"(what'?s happening|current events|world news|tell me.?news|what'?s going on)", q):
        try:
            from .world_intelligence import get_world_intelligence
            wi = get_world_intelligence()
            return wi.get_context_string()
        except Exception:
            pass

    return None


def _execute_home_command(cmd_str: str) -> str:
    """Execute a smart home command and return result."""
    try:
        from .smart_home_controller import get_smart_home
        sh = get_smart_home()
        # Strip "home " prefix if present
        actual_cmd = cmd_str.replace("home ", "", 1) if cmd_str.startswith("home ") else cmd_str
        result = sh.execute_command(actual_cmd)
        if result.get("success"):
            action = result.get("action", "done")
            return f"Done. {action} executed successfully."
        return f"Failed: {result.get('message', result.get('error', 'unknown'))}"
    except Exception as e:
        return f"Home control error: {e}"


# ═══════════════════════════════════════════════════════════════
# MAIN BRAIN — LLM first, tools only on explicit request
# ═══════════════════════════════════════════════════════════════

async def generate_response(user_input: str, context=None) -> str:
    """
    Generate a response.
    - Explicit tool prefixes (!, ?, URL) → tool first, then LLM enriches result
    - Everything else → Cloudflare Workers AI
    """
    _load_memory()

    # Check for explicit tool triggers
    tool_result = await _check_explicit_tools(user_input)

    # Build conversation history (keep short for speed)
    history = ""
    for msg in _memory["conversations"][-4:]:  # last 4 msgs only (2 exchanges)
        role = "H" if msg["role"] == "user" else "U"
        history += f"\n{role}: {msg['content'][:80]}"  # trim each msg

    # Pull relevant memory
    knowledge = tool_recall_knowledge(user_input)
    memory_ctx = f"\n\nKNOWLEDGE BASE:\n{knowledge}" if knowledge else ""

    # World context — only inject if directly relevant, keep tiny
    world_ctx = ""
    try:
        from .world_intelligence import get_world_intelligence
        _wi = get_world_intelligence()
        world_str = _wi.get_context_string()
        if world_str and any(w in user_input.lower() for w in ["news", "world", "happening", "today", "latest"]):
            world_ctx = f"\n\nWORLD: {world_str[:150]}"
    except Exception:
        pass

    # Pull interaction learner guidance (adapts style to this user)
    style_suffix = _get_style_guidance()

    # If a tool ran, include its output in the prompt so LLM enriches it
    if tool_result:
        prompt = (
            f"TOOL OUTPUT:\n{tool_result}\n\n"
            f"Using the tool output above, provide a thorough, expert analysis "
            f"and any additional context Ultron knows about this topic.{style_suffix}\n\n"
            f"Human request: {user_input}\nUltron:"
        )
    else:
        prompt = f"CONVERSATION:{history}{memory_ctx}{world_ctx}{style_suffix}\n\nHuman: {user_input}\nUltron:"

    # Call Cloudflare Workers AI — only brain, no fallback
    response = _call_cloudflare(prompt, max_tokens=400)
    if not response:
        response = "Cloudflare AI unreachable. Check CF_ACCOUNT_ID and CF_API_TOKEN in .env."

    # Record interaction for style learning
    _record_interaction(user_input, response)

    # ── Feed into ContinuousLearner / learning service ──────────────────────
    _emit_learning_event(user_input, response)

    # Persist to memory
    _memory["conversations"].append({"role": "user", "content": user_input, "ts": time.time()})
    _memory["conversations"].append({"role": "assistant", "content": response, "ts": time.time()})
    if len(_memory["conversations"]) > 200:
        _memory["conversations"] = _memory["conversations"][-200:]
    _save_memory()

    # If tool ran, prefix the clean tool output for context
    if tool_result:
        return f"{tool_result}\n\n---\n{response}"
    return response


# ═══════════════════════════════════════════════════════════════
# INTERACTION LEARNER — cached at module level to avoid re-import per request
# ═══════════════════════════════════════════════════════════════
_interaction_learner_module = None

def _get_interaction_learner():
    global _interaction_learner_module
    if _interaction_learner_module is not None:
        return _interaction_learner_module
    try:
        import importlib.util
        import pathlib
        server_dir = pathlib.Path(__file__).parent
        spec = importlib.util.spec_from_file_location(
            "interaction_learner", str(server_dir / "interaction_learner.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _interaction_learner_module = mod
    except Exception:
        pass
    return _interaction_learner_module


def _get_style_guidance() -> str:
    """Get response style guidance from the interaction learner."""
    try:
        mod = _get_interaction_learner()
        if mod is None:
            return ""
        learner = getattr(mod, '_global_learner', None)
        if learner is None:
            return ""
        guidance = learner.get_response_guidance("default_user")
        if guidance:
            return f"\n\nSTYLE: {guidance.to_system_prompt_suffix()}"
    except Exception:
        pass
    return ""


def _record_interaction(user_input: str, response: str):
    """Record the interaction for the style learner."""
    try:
        mod = _get_interaction_learner()
        if mod is None:
            return
        learner = getattr(mod, '_global_learner', None)
        if learner:
            learner.record_interaction(
                user_id="default_user",
                user_input=user_input,
                response=response,
                response_time=0.0,
            )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# CLOUDFLARE WORKERS AI — only brain
# ═══════════════════════════════════════════════════════════════

def _call_cloudflare(prompt: str, max_tokens: int = 400) -> Optional[str]:
    """Call Cloudflare Workers AI. Free tier: 10k neurons/day."""
    account_id = os.environ.get("CF_ACCOUNT_ID", CF_ACCOUNT_ID)
    api_token  = os.environ.get("CF_API_TOKEN",  CF_API_TOKEN)
    model      = os.environ.get("CF_AI_MODEL",   CF_MODEL)

    if not account_id or not api_token:
        return None

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": min(max_tokens, 400),
        "temperature": 0.8,
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {api_token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("success"):
                content = result.get("result", {}).get("response", "").strip()
                return content if content else None
    except Exception:
        return None
    return None


def is_cloudflare_available() -> bool:
    """Check if Cloudflare credentials are configured."""
    return bool(
        os.environ.get("CF_ACCOUNT_ID", CF_ACCOUNT_ID) and
        os.environ.get("CF_API_TOKEN",  CF_API_TOKEN)
    )

# ═══════════════════════════════════════════════════════════════
# LEARNING LOOP — feed every conversation into ContinuousLearner
# ═══════════════════════════════════════════════════════════════

_learning_addr = os.environ.get("ULTRON_LEARNING_ADDR", "http://localhost:50060")
_learning_enabled = True


def _emit_learning_event(user_input: str, response: str) -> None:
    """
    Fire-and-forget: send this interaction to the UnifiedLearningService
    so the ContinuousLearner can accumulate training examples.
    Runs in a background thread — never blocks the response path.
    """
    import threading
    def _send():
        try:
            payload = json.dumps({
                "method": "submit_events",
                "params": {
                    "events": [{
                        "event_type": "interaction",
                        "component": "interface",
                        "outcome": "success",
                        "data": {
                            "user_input": user_input[:500],
                            "response":   response[:500],
                            "model":      os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct"),
                        },
                        "importance": 0.7,
                    }]
                }
            }).encode()
            # Learning service JSON-over-TCP on port+1 (50061)
            import socket as _s
            lport = int(_learning_addr.split(":")[-1]) + 1  # JSON port = gRPC port + 1
            sock = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect(("localhost", lport))
            sock.sendall(payload + b"\n")
            sock.close()
        except Exception:
            pass  # Learning is best-effort — never break conversation
    threading.Thread(target=_send, daemon=True).start()
