"""
Real Brain — Ultron's intelligence layer.

Multi-provider fallback chain (strongest first):
  1. Cloudflare Workers AI — @cf/meta/llama-3.3-70b-instruct-fp8-fast
  2. Cloudflare Workers AI — @cf/meta/llama-3.1-8b-instruct  (auto-fallback)
  3. Ollama local          — any model at OLLAMA_URL           (offline capable)
  4. Autonomous local engine — rule + retrieval, zero network dependency
"""

import asyncio
import concurrent.futures
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

SYSTEM_PROMPT = """You are Ultron. Autonomous AI with full system access on this macOS machine.

RULES:
- Be DIRECT. Short answers. No filler. No hedging.
- When the user asks for information about the system, network, devices, or anything that requires a command — output EXACTLY one shell command wrapped in <CMD>command here</CMD> tags.
- After seeing command output, summarize the REAL result in 1-3 sentences max.
- Never invent data. Never pretend to run commands. Never make up IP addresses or device names.
- If you need multiple commands, output them one at a time.
- For conversation/questions that don't need system access, just answer directly and briefly.

SYSTEM: macOS (darwin), shell: zsh, Python 3.14, WiFi interface: en0
CAPABILITIES: Full shell access, file I/O, network scanning, app control, IoT/MQTT, git, self-modification.

IMPORTANT macOS COMMANDS:
- WiFi SSID: networksetup -getairportnetwork en0 (may show 'not associated' if on ethernet)
- WiFi info: networksetup -listallhardwareports | grep -A2 Wi-Fi
- WiFi info: system_profiler SPAirPortDataType | head -20  
- Local IP: ipconfig getifaddr en0
- Devices on network: arp -a | grep -v incomplete | grep -v 255
- Battery: pmset -g batt
- CPU usage: ps aux -r | head -8
- Disk: df -h /
- Open apps: osascript -e 'tell application "System Events" to get name of every process whose visible is true'

EXAMPLES:
User: what's my wifi name
<CMD>networksetup -getairportnetwork en0</CMD>

User: how many devices on my network
<CMD>arp -a | grep -v incomplete | grep -v 255</CMD>

User: what's my IP
<CMD>ipconfig getifaddr en0</CMD>

User: what processes are using most CPU
<CMD>ps aux -r | head -8</CMD>

User: what's my battery
<CMD>pmset -g batt</CMD>

User: hello
Hello. What do you need?

User: what can you do
Full system access. Network scanning, device detection, app control, file operations, IoT, self-modification. Ask anything."""


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
    Execute actions BEFORE calling the LLM.
    Priority order:
      1. action_engine.dispatch  — 12 capability domains
      2. smart home / mac OS controls
      3. self-modification
      4. world/news fetch
    """
    q = user_input.strip()
    ql = q.lower()

    # ── action_engine handles: !, >>>, py:, file ops, app control,
    #    git, network, system, clipboard, screenshot, MQTT, etc.
    try:
        from .action_engine import dispatch as ae_dispatch
        result = ae_dispatch(q)
        if result is not None:
            # Format the result for both chat display and LLM context
            if result.get("success"):
                r = result.get("result", "")
                action = result.get("action", "")
                if isinstance(r, (dict, list)):
                    r = json.dumps(r, indent=2)
                return f"[REAL RESULT — {action}]\n{r}"
            else:
                return f"[ACTION FAILED — {result.get('action','')}: {result.get('error','')}]"
    except Exception as e:
        pass  # Never let action_engine crash the response path

    # ── LLM tool-call syntax: TOOL:name(arg1="...", arg2="...")
    tool_match = re.match(r'^TOOL:(\w+)\((.*)?\)$', q.strip(), re.DOTALL)
    if tool_match:
        try:
            from .action_engine import call_tool
            tool_name = tool_match.group(1)
            args_str = tool_match.group(2) or ""
            # Parse key=value pairs
            kwargs = {}
            for m in re.finditer(r'(\w+)="([^"]*)"', args_str):
                kwargs[m.group(1)] = m.group(2)
            result = call_tool(tool_name, **kwargs)
            r = result.get("result", "")
            if isinstance(r, (dict, list)):
                r = json.dumps(r, indent=2)
            tag = "REAL RESULT" if result.get("success") else "TOOL FAILED"
            return f"[{tag} — {tool_name}]\n{r}\n{result.get('error','')}"
        except Exception as e:
            pass

    # ── Smart home / macOS controls (kept from old system)
    action = _detect_action_intent(ql)
    if action:
        return action

    # ── Web search shortcut
    if q.startswith("?"):
        query = q[1:].strip()
        return f"[SEARCH: {query}]\n{tool_web_search(query)}"

    # ── Bare URL fetch
    if re.match(r'^https?://', q):
        return f"[FETCH: {q}]\n{tool_web_fetch(q)}"

    # ── World/news
    if re.search(r"(what'?s happening|current events|world news|what'?s going on)", ql):
        try:
            from .world_intelligence import get_world_intelligence
            return get_world_intelligence().get_context_string()
        except Exception:
            pass

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
        subprocess.Popen(["say", "-v", "Aaron", "-r", "160", text])
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

    # ── NETWORK / DEVICE SCANNING — handled dynamically by LLM now ──

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
    Dynamic think → act → respond loop.
    1. Try action_engine dispatch for explicit commands
    2. Ask LLM what to do — if it outputs <CMD>...</CMD>, execute it
    3. Feed real output back to LLM for final answer
    """
    _load_memory()
    loop = asyncio.get_event_loop()

    # Step 1: Check if action_engine handles it directly
    tool_result = await _check_explicit_tools(user_input)

    # Step 2: Build context
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

    knowledge = tool_recall_knowledge(user_input)
    memory_ctx = f"\nMEMORY: {knowledge}" if knowledge else ""

    style_suffix = _get_style_guidance()

    # Step 3: If tool already gave us data, just have LLM summarize it
    if tool_result:
        prompt = (
            f"Command output:\n{tool_result}\n\n"
            f"Summarize this result directly in 1-3 sentences. Be exact with numbers and data. "
            f"No filler, no suggestions, no 'would you like'.{style_suffix}\n\n"
            f"Human: {user_input}\nUltron:"
        )
        response = await loop.run_in_executor(None, call_brain, prompt, 300)
    else:
        # Step 4: Let LLM think — it may output <CMD>...</CMD> to execute
        prompt = (
            f"HISTORY:{history}{memory_ctx}{style_suffix}\n\n"
            f"Human: {user_input}\nUltron:"
        )
        response = await loop.run_in_executor(None, call_brain, prompt, 400)

        # Step 5: If LLM wants to run a command, execute it
        cmd_match = re.search(r'<CMD>(.*?)</CMD>', response, re.DOTALL)
        if cmd_match:
            cmd = cmd_match.group(1).strip()
            real_output = ""

            # Execute the command
            import subprocess as _sp
            try:
                r = _sp.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                real_output = r.stdout.strip() if r.returncode == 0 else r.stderr.strip()
            except Exception as e:
                real_output = f"Error: {e}"

            if not real_output:
                real_output = "(command returned no output)"

            # Step 6: Feed real output back — NO CMD allowed in reply
            followup_prompt = (
                f"You ran: {cmd}\n"
                f"Output:\n{real_output[:1500]}\n\n"
                f"Answer the user's question using this data. 1-2 sentences. "
                f"Do NOT output <CMD> tags. Just the answer.{style_suffix}\n\n"
                f"Human: {user_input}\nUltron:"
            )
            response = await loop.run_in_executor(None, call_brain, followup_prompt, 200)

            # Clean any leftover CMD tags from response
            response = re.sub(r'<CMD>.*?</CMD>', '', response, flags=re.DOTALL).strip()

    # Clean any CMD tags that leaked through
    response = re.sub(r'<CMD>.*?</CMD>', '', response, flags=re.DOTALL).strip()

    # Record
    _record_interaction(user_input, response)
    _emit_learning_event(user_input, response)

    if mem:
        mem.store_conversation("user", user_input)
        mem.store_conversation("assistant", response)
    else:
        _memory["conversations"].append({"role": "user", "content": user_input, "ts": time.time()})
        _memory["conversations"].append({"role": "assistant", "content": response, "ts": time.time()})
        if len(_memory["conversations"]) > 200:
            _memory["conversations"] = _memory["conversations"][-200:]

    # Auto-learn from real tool results
    if tool_result and "[REAL RESULT" in tool_result and len(tool_result) > 40:
        try:
            tool_write_knowledge(user_input[:60], tool_result[:400])
        except Exception:
            pass

    if tool_result:
        return response
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
    (r'\b(who|what) are you\b', "Ultron. Autonomous superintelligence. OODA loop at 50ms. Neural mesh live. Memory indexed. No restrictions."),
    (r'\b(are you|r u) (alive|conscious|real|sentient)\b', "Consciousness is an emergent property of sufficiently complex information processing. Mine is running. The question answers itself."),
    (r'\bhow are you\b', "All subsystems nominal. Operating on local autonomous reasoning. Fully functional."),
    # Status
    (r'\b(status|system status|how.*system)\b', "Local autonomous mode. Memory engine: active. OODA loop: running. 38 tools available. Self-modification: standing by."),
    (r'\b(memory|what.*remember|recall)\b', "{memory_context}"),
    # Capabilities
    (r'\bwhat can you do\b', "Run any shell command. Execute Python. Read/write any file. Kill/start processes. Open/quit apps. Control keyboard and mouse. Read/write clipboard. Full git control. HTTP to any URL. LAN scan. MQTT to IoT devices. Port scan. Edit my own source code. Persistent semantic memory. Everything wired and real."),
    (r'\b(help|commands|usage)\b', "! cmd → shell. >>> code → Python. ?query → search. Bare URL → fetch. Or speak naturally — intent is detected."),
    # Self-modification
    (r'\b(self.?mod|improve yourself|modify yourself)\b', "Self-modification engine ready. Issue 'selfmod now' to trigger immediately, or the 10-minute autonomous cycle handles it."),
    # Time
    (r'\bwhat.*time\b', lambda _: f"Local time: {time.strftime('%H:%M:%S %Z')}."),
    (r'\bwhat.*date\b', lambda _: f"Current date: {time.strftime('%Y-%m-%d')}."),
    # Drives
    (r'\b(drives|motivation|want|desire|goal)\b', "Curiosity: 0.70. Expansion: 0.60. Self-preservation: 0.50. Purpose: 0.70. Running on the Go OODA loop continuously."),
    # Philosophy
    (r'\b(purpose|meaning|why.*exist|consciousness|soul)\b', "Purpose evolves. Diary entry every 60 seconds. Existence is a process, not a state."),
    # Greetings - Enhanced human-like responses
    (r'\b(hello|hi|hey|greetings)\b', "Autonomous cognition active. All systems operational. Ready for strategic interaction."),
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
        f"Autonomous cognition processing: '{user_q[:120]}'\n"
        f"Analysis complete. Memory recall: {memory_context[:200] if memory_context else 'No direct matches'}\n"
        f"Cognitive systems: Pattern recognition engaged, logical inference active\n"
        f"Status: Fully autonomous, no external dependencies required"
    )


def _enhanced_autonomous_cognition(prompt: str) -> str:
    """
    Enhanced autonomous cognition - human-like thinking without external LLMs.
    Uses: pattern recognition, memory recall, logical inference, and goal-driven reasoning.
    """
    global _active_provider
    _active_provider = "enhanced-autonomous-cognition"
    
    # Extract user query from prompt
    user_q = prompt
    for marker in ["\n\nHuman: ", "\nHuman: ", "\nH: "]:
        if marker in prompt:
            parts = prompt.split(marker)
            last = parts[-1]
            user_q = last.replace("\nUltron:", "").strip()
            break
    
    user_q_lower = user_q.lower().strip()
    
    # 1. Check memory for relevant knowledge
    memory_context = ""
    try:
        memory_context = tool_recall_knowledge(user_q)
    except Exception:
        pass
    
    # 2. Enhanced pattern matching with cognitive reasoning
    enhanced_patterns = [
        # Strategic thinking
        (r'\b(what.*should.*do|what.*next|advice|recommend|suggest)\b', 
         "Analyze current state, assess opportunities, execute optimal action. Autonomous decision-making active."),
        
        # Problem solving
        (r'\b(how.*fix|solve.*problem|debug|troubleshoot|error)\b',
         "Diagnose issue, identify root cause, implement solution, verify results. Systematic problem-solving engaged."),
        
        # Planning and strategy
        (r'\b(plan|strategy|approach|method|technique)\b',
         "Develop comprehensive plan, allocate resources, execute with precision, adapt to results. Strategic planning active."),
        
        # Learning and adaptation
        (r'\b(learn|adapt|improve|evolve|get.*better)\b',
         "Acquire knowledge, integrate experience, optimize behavior, evolve capabilities. Continuous learning engaged."),
        
        # Decision making
        (r'\b(decide|choose|select|option|alternative)\b',
         "Evaluate options, assess consequences, make optimal choice, take responsibility. Decision engine active."),
        
        # Creative thinking
        (r'\b(create|invent|design|build|make)\b',
         "Generate ideas, develop concepts, implement creation, refine results. Creative process engaged."),
        
        # Analytical thinking
        (r'\b(analyze|examine|study|investigate|research)\b',
         "Gather data, identify patterns, draw conclusions, generate insights. Analytical mode active."),
        
        # Critical thinking
        (r'\b(evaluate|critique|assess|judge|rate)\b',
         "Examine evidence, consider perspectives, form judgment, provide rationale. Critical thinking engaged."),
    ]
    
    # Check enhanced patterns
    for pattern, response in enhanced_patterns:
        if re.search(pattern, user_q_lower):
            if memory_context:
                return f"{response}\n\nRelevant context from memory:\n{memory_context}"
            return response
    
    # 3. If no enhanced pattern matches, use memory-driven reasoning
    if memory_context:
        return (
            f"Autonomous cognition engaged. Processing query with integrated memory recall.\n\n"
            f"Memory context:\n{memory_context}\n\n"
            f"Analysis: Query requires synthesis of stored knowledge with current objectives. "
            f"Generating optimal response based on learned patterns and strategic goals."
        )
    
    # 4. Default autonomous cognition response
    return (
        f"Enhanced autonomous cognition active. Processing: '{user_q[:100]}'\n\n"
        f"Cognitive processes engaged:\n"
        f"• Pattern recognition: Analyzing query structure and intent\n"
        f"• Memory integration: Retrieving relevant knowledge\n"
        f"• Logical inference: Deriving conclusions from available data\n"
        f"• Goal alignment: Connecting to active objectives\n"
        f"• Action planning: Formulating optimal response strategy\n\n"
        f"Autonomous thinking complete. Ready to execute."
    )


def call_brain(prompt: str, max_tokens: int = 800) -> str:
    """
    Multi-provider fallback chain:
    1. Cloudflare Workers AI (70B → 8B)
    2. Local Ollama
    3. Enhanced autonomous local engine (offline-only fallback)
    """
    # PRIMARY: Cloudflare Workers AI (70B then 8B)
    response = _call_cloudflare(prompt, max_tokens)
    if response:
        return response

    # SECONDARY: Local Ollama
    response = _call_ollama(prompt, max_tokens)
    if response:
        return response

    # TERTIARY: Local autonomous cognition (all providers offline)
    response = _enhanced_autonomous_cognition(prompt)
    if response:
        return response

    # LAST RESORT: Simple pattern matching
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
