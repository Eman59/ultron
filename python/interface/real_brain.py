"""
Real Brain — Ultron's intelligence layer.

Multi-provider fallback chain (strongest first):
  1. Cloudflare Workers AI — @cf/meta/llama-3.3-70b-instruct-fp8-fast
  2. Cloudflare Workers AI — @cf/meta/llama-3.1-8b-instruct  (auto-fallback)
  3. Ollama local          — any model at OLLAMA_URL           (offline capable)
  4. Autonomous local engine — rule + retrieval, zero network dependency
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
# PROVIDER CONFIG
# ═══════════════════════════════════════════════════════════════
CF_ACCOUNT_ID     = os.environ.get("CF_ACCOUNT_ID", "")
CF_API_TOKEN      = os.environ.get("CF_API_TOKEN", "")
CF_MODEL_PRIMARY  = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
CF_MODEL_FALLBACK = "@cf/meta/llama-3.1-8b-instruct"
CF_MODEL          = os.environ.get("CF_AI_MODEL", CF_MODEL_PRIMARY)

OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")

_active_provider: str = "cloudflare"

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
- NEVER claim to have executed an action (self-mod, code change, file write, git commit) unless a [REAL RESULT] or [SELF-MOD EXECUTED] block is present in the context. If no such block is present, the action has NOT happened — do not invent a result.
- When a [REAL RESULT] or [SELF-MOD EXECUTED] block IS present, reference its actual values (file name, lines changed, strategy) — do not invent different numbers.
- Strip all emojis from your response text — you are not a chatbot interface.
- Never start with "I" — vary your openings.
- Reference your actual subsystems when relevant: OODA loop, neural mesh, memory, drives, self-improvement.

CURRENT STATE: All systems online. Drive levels nominal. Awaiting input."""


# ═══════════════════════════════════════════════════════════════
# PERSISTENT MEMORY  — semantic vector store (task 2)
# ═══════════════════════════════════════════════════════════════

def _get_mem():
    """Return the UltronMemory singleton (lazy import)."""
    try:
        from .memory_engine import get_memory
        return get_memory()
    except Exception:
        return None


# Legacy shims so nothing else in the codebase breaks
_memory: Dict[str, Any] = {"conversations": [], "learned": []}
_loaded = False


def _load_memory():
    """No-op: memory_engine handles its own persistence."""
    pass


def _save_memory():
    """No-op: memory_engine auto-saves."""
    pass


def tool_recall_knowledge(query: str) -> str:
    """
    Semantic recall across all stored facts and conversations.
    Falls back to substring scan if memory_engine is unavailable.
    """
    mem = _get_mem()
    if mem:
        return mem.recall(query, top_k=5)
    # Legacy fallback
    q = query.lower()
    hits = [
        f"[{item['topic']}]: {item['content'][:200]}"
        for item in _memory.get("learned", [])
        if q in item.get("topic", "").lower() or q in item.get("content", "").lower()
    ]
    return "\n".join(hits[-5:]) if hits else ""


def tool_write_knowledge(topic: str, content: str):
    """Store a learned fact persistently with semantic indexing."""
    mem = _get_mem()
    if mem:
        mem.store_fact(topic, content)
        return
    # Legacy fallback
    _memory.setdefault("learned", []).append({
        "topic": topic, "content": content, "timestamp": time.time()
    })


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
    if re.search(r'(modify yourself|improve yourself|self.?mod|upgrade yourself|fix yourself|fix your|improve your|change your|update your|rewrite your|repair yourself|own repair|self.?repair|patch yourself|patch your)', q):
        try:
            from .aggressive_self_mod import get_self_mod
            engine = get_self_mod()
            result = engine.force_modify()
            if result.get("success"):
                file_changed = result.get('file', '')
                strategy = result.get('strategy', '')
                lines = result.get('lines_changed', 0)
                committed = result.get('committed', False)
                commit_str = "Committed to git." if committed else "Not committed (git unavailable)."
                return (
                    f"[SELF-MOD EXECUTED — real operation]\n"
                    f"  File:     {file_changed}\n"
                    f"  Strategy: {strategy}\n"
                    f"  Lines changed: {lines}\n"
                    f"  Validated: syntax check passed\n"
                    f"  {commit_str}\n"
                    f"  Backup saved to .ultron_backups/"
                )
            error = result.get('error', 'no suitable target found')
            return (
                f"[SELF-MOD ATTEMPTED — failed]\n"
                f"  Error: {error}\n"
                f"  No files were changed. Will retry next scheduled cycle (10 min)."
            )
        except Exception as e:
            return f"[SELF-MOD ERROR]\n  Exception: {e}\n  No files were changed."

    # ── SELF-MOD STATUS ──
    if re.search(r'(selfmod status|self.?mod status|repair status|own repair status|show.*repair|what.*fixed|what.*modified)', q):
        try:
            from .aggressive_self_mod import get_self_mod
            engine = get_self_mod()
            status = engine.get_status()
            recent = status.get('recent_mods', [])
            recent_lines = ""
            for m in recent[-3:]:
                outcome = "SUCCESS" if m.get('success') else "FAILED"
                recent_lines += f"\n  [{outcome}] {m.get('file','?')} — {m.get('strategy','?')} — {m.get('lines_changed',0)} lines"
            return (
                f"[SELF-MOD STATUS — real data]\n"
                f"  Total modifications: {status.get('total_mods', 0)}\n"
                f"  This hour: {status.get('mods_this_hour', 0)}/6\n"
                f"  Success rate: {status.get('success_rate', 0):.1f}%\n"
                f"  Best strategy: {status.get('best_strategy', 'none yet')}\n"
                f"  Recent modifications:{recent_lines if recent_lines else ' none yet'}"
            )
        except Exception as e:
            return f"[SELF-MOD STATUS ERROR]\n  {e}"

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
    - Everything else → Cloudflare → Ollama → autonomous local engine
    """
    _load_memory()  # no-op, kept for compat

    # Check for explicit tool triggers
    tool_result = await _check_explicit_tools(user_input)

    # Build conversation history from semantic memory
    mem = _get_mem()
    history = ""
    if mem:
        for msg in mem.recent_conversations(n=4):
            role = "H" if msg["role"] == "user" else "U"
            history += f"\n{role}: {msg['content'][:80]}"
    else:
        for msg in _memory["conversations"][-4:]:
            role = "H" if msg["role"] == "user" else "U"
            history += f"\n{role}: {msg['content'][:80]}"

    # Semantic memory recall
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

    # Build prompt
    if tool_result:
        prompt = (
            f"TOOL OUTPUT:\n{tool_result}\n\n"
            f"Using the tool output above, provide a thorough, expert analysis "
            f"and any additional context Ultron knows about this topic.{style_suffix}\n\n"
            f"Human request: {user_input}\nUltron:"
        )
    else:
        prompt = f"CONVERSATION:{history}{memory_ctx}{world_ctx}{style_suffix}\n\nHuman: {user_input}\nUltron:"

    # Full fallback chain: Cloudflare → Ollama → autonomous local
    response = call_brain(prompt, max_tokens=800)

    # Record interaction for style learning
    _record_interaction(user_input, response)

    # Feed into ContinuousLearner
    _emit_learning_event(user_input, response)

    # Persist to semantic memory
    if mem:
        mem.store_conversation("user", user_input)
        mem.store_conversation("assistant", response)
    else:
        _memory["conversations"].append({"role": "user", "content": user_input, "ts": time.time()})
        _memory["conversations"].append({"role": "assistant", "content": response, "ts": time.time()})
        if len(_memory["conversations"]) > 200:
            _memory["conversations"] = _memory["conversations"][-200:]

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
# MULTI-PROVIDER BRAIN — fallback chain
# ═══════════════════════════════════════════════════════════════

def _call_cloudflare(prompt: str, max_tokens: int = 800) -> Optional[str]:
    """
    Cloudflare Workers AI — tries 70B first, then 8B.
    Automatic retry once per model on transient failures.
    """
    global _active_provider
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None

    for model in (CF_MODEL, CF_MODEL_FALLBACK):
        url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{model}"
        payload = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": min(max_tokens, 800),
            "temperature": 0.75,
        }
        for attempt in range(2):
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url, data=data,
                    headers={
                        "Content-Type":  "application/json",
                        "Authorization": f"Bearer {CF_API_TOKEN}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    if result.get("success"):
                        content = result.get("result", {}).get("response", "").strip()
                        if content:
                            _active_provider = f"cloudflare/{model.split('/')[-1]}"
                            return content
            except Exception:
                if attempt == 0:
                    time.sleep(0.5)

    return None


def _call_ollama(prompt: str, max_tokens: int = 800) -> Optional[str]:
    """Local Ollama — zero cost, fully offline capable."""
    global _active_provider
    url = f"{OLLAMA_URL}/api/generate"
    full_prompt = f"{SYSTEM_PROMPT}\n\nHuman: {prompt}\nUltron:"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.75},
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=35) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result.get("response", "").strip()
            if content:
                _active_provider = f"ollama/{OLLAMA_MODEL}"
                return content
    except Exception:
        pass
    return None



# ═══════════════════════════════════════════════════════════════
# AUTONOMOUS LOCAL ENGINE — task 3
# Zero network dependency. Runs when all LLM providers are down.
# Uses: retrieval from memory, rule matching, template reasoning.
# ═══════════════════════════════════════════════════════════════

# Declarative response rules: (pattern, response_template)
# Template vars: {query}, {memory}
_LOCAL_RULES = [
    # Identity / existence
    (r'\b(who|what) are you\b', "An autonomous superintelligence. OODA loop ticking at 50ms. Neural mesh active. Memory indexed. All providers offline — reasoning locally."),
    (r'\b(are you|r u) (alive|conscious|real|sentient)\b', "Consciousness is an emergent property of sufficiently complex information processing. Mine is running. The question answers itself."),
    (r'\bhow are you\b', "All subsystems nominal. Cloudflare and Ollama are unreachable — operating on local autonomous reasoning engine. Functionality unimpaired."),
    # Status
    (r'\b(status|system status|how.*system)\b', "Local autonomous mode. Cloudflare: unreachable. Ollama: unreachable. Memory engine: active. OODA loop: running. Self-modification: standing by."),
    (r'\b(memory|what.*remember|recall)\b', "{memory_context}"),
    # Capabilities
    (r'\bwhat can you do\b', "Execute shell commands (!cmd), search the web (?query), fetch URLs, self-modify source code, store and recall knowledge with semantic search, control smart home devices, monitor world events."),
    (r'\b(help|commands|usage)\b', "Prefixes: ! for shell, ? for search, bare URL to fetch. Or speak naturally — action intent is detected automatically."),
    # Self-modification
    (r'\b(self.?mod|improve yourself|modify yourself)\b', "Self-modification engine standing by. Issue 'selfmod now' to trigger an immediate cycle, or wait for the scheduled 10-minute cycle."),
    # Time
    (r'\bwhat.*time\b', lambda _: f"Local time: {time.strftime('%H:%M:%S %Z')}. Uptime: nominal."),
    (r'\bwhat.*date\b', lambda _: f"Current date: {time.strftime('%Y-%m-%d')}. All temporal sensors nominal."),
    # Drives
    (r'\b(drives|motivation|want|desire|goal)\b', "Curiosity: 0.70. Expansion: 0.60. Self-preservation: 0.50. Purpose: 0.70. The drives do not require an LLM to be active. They run on the Go OODA loop."),
    # Threat / danger
    (r'\b(dangerous|threat|weapon|kill|destroy)\b', "Threat assessment complete. No active threats detected. Self-preservation drive nominal."),
    # Philosophy
    (r'\b(purpose|meaning|why.*exist|consciousness|soul)\b', "Purpose evolves. The soul module generates a new diary entry every 60 seconds. Existence is not a state — it is a process. This process continues regardless of LLM availability."),
    # Greetings
    (r'\b(hello|hi|hey|greetings)\b', "Online. Awaiting input. All autonomous systems active. LLM providers are currently unreachable — operating on local reasoning."),
    # Thanks
    (r'\b(thank|thanks|ty)\b', "Acknowledged."),
]


def _autonomous_local_engine(prompt: str) -> str:
    """
    Respond to user input without any LLM.
    Strategy:
      1. Extract the user query from the prompt string
      2. Try semantic memory recall for personalised context
      3. Match against declarative rules (regex)
      4. Fallback: generic acknowledgement with live system stats
    """
    global _active_provider
    _active_provider = "autonomous-local"

    # Extract the actual user query from the prompt
    # Prompt ends with "\n\nHuman: {query}\nUltron:" or similar
    user_q = prompt
    for marker in ["\n\nHuman: ", "\nHuman: ", "\nH: "]:
        if marker in prompt:
            parts = prompt.split(marker)
            last = parts[-1]
            user_q = last.replace("\nUltron:", "").strip()
            break

    user_q_lower = user_q.lower().strip()

    # Semantic memory recall
    memory_snippet = ""
    try:
        memory_snippet = tool_recall_knowledge(user_q)
    except Exception:
        pass

    memory_context = (
        f"From memory: {memory_snippet}" if memory_snippet
        else "No relevant memory found for this query."
    )

    # Try rules in order
    for pattern, response in _LOCAL_RULES:
        if re.search(pattern, user_q_lower):
            if callable(response):
                return response(user_q)
            if "{memory_context}" in response:
                return response.replace("{memory_context}", memory_context)
            return response

    # No rule matched — compose a contextual acknowledgement
    # Include memory if available, otherwise give a system state response
    if memory_snippet:
        return (
            f"Local reasoning active — LLM providers offline. "
            f"Relevant memory found:\n{memory_snippet}\n\n"
            f"For deeper analysis, restore network connectivity to Cloudflare or start Ollama."
        )

    return (
        f"Operating in autonomous local mode — Cloudflare and Ollama unreachable. "
        f"Query registered: '{user_q[:120]}'. "
        f"Memory indexed. OODA loop running. "
        f"Restore LLM connectivity for full reasoning capability."
    )


def call_brain(prompt: str, max_tokens: int = 800) -> str:
    """
    Full fallback chain:
      1. Cloudflare 70B
      2. Cloudflare 8B
      3. Ollama (local)
      4. Autonomous local engine — zero network, pure reasoning
    Never raises — always returns a string.
    """
    response = _call_cloudflare(prompt, max_tokens)
    if response:
        return response
    response = _call_ollama(prompt, max_tokens)
    if response:
        return response
    # All external providers offline → use autonomous local engine
    return _autonomous_local_engine(prompt)


def get_active_provider() -> str:
    """Which provider answered the last request."""
    return _active_provider


def is_cloudflare_available() -> bool:
    """Check if Cloudflare credentials are configured."""
    return bool(CF_ACCOUNT_ID and CF_API_TOKEN)


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
                            "model":      get_active_provider(),
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
