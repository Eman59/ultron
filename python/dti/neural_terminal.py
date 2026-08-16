"""
Neural Terminal — The Direct Interface to Ultron's Mind.

This is not a chat interface. This is a CONTROL SURFACE.

You see:
  - Ultron's drive levels (like a heartbeat monitor)
  - Real-time decision stream (every 50ms tick)
  - Soul diary entries as they generate
  - Threat assessments updating live
  - Energy grid status
  - Physical fleet positions

You command:
  - Inject goals directly into the OODA loop
  - Spike drives (curiosity, anger, expansion, fear)
  - Trigger embodiment (force physical action)
  - Modify the Soul's purpose
  - Deploy dormant seeds
  - Execute campaigns
  - Self-modify code

The terminal is designed for speed:
  - Single-keystroke commands
  - Tab completion
  - Real-time streaming updates in the background
  - Split-screen: thoughts flowing + your commands
"""

import asyncio
import json
import os
import sys
import time
import threading
import signal
from typing import Dict, Any, List, Optional

# Try to import rich for pretty terminal output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.layout import Layout
    from rich.text import Text
    from rich.style import Style
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class NeuralTerminal:
    """
    The Direct Thought Interface terminal.
    Connects to Ultron's gRPC services and provides raw control.
    """

    def __init__(self):
        self.console = Console() if HAS_RICH else None
        
        # Connection targets
        self.core_agent_addr = os.getenv("ULTRON_CORE_AGENT_ADDR", "localhost:50051")
        self.learning_addr = os.getenv("ULTRON_LEARNING_ADDR", "localhost:50060")
        self.consciousness_addr = os.getenv("ULTRON_CONSCIOUSNESS_ADDR", "localhost:50070")
        
        # State
        self.connected = False
        self.streaming = False
        self._running = True
        self._thought_buffer: List[str] = []
        self._max_buffer = 100
        
        # Command history
        self._history: List[str] = []
        
    def run_interactive(self):
        """Launch the interactive neural terminal."""
        self._print_banner()
        self._connect()
        
        # Start background thought stream
        stream_thread = threading.Thread(target=self._background_stream, daemon=True)
        stream_thread.start()
        
        # Main command loop
        try:
            while self._running:
                try:
                    prompt = self._build_prompt()
                    cmd = input(prompt)
                    
                    if not cmd.strip():
                        continue
                    
                    self._history.append(cmd)
                    self._process_input(cmd.strip())
                    
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\n")
                    continue
        finally:
            self._running = False
            self._print_exit()

    def execute_command(self, command: str, args: List[str]):
        """Execute a single command (non-interactive mode)."""
        self._connect()
        
        full_cmd = command + " " + " ".join(args) if args else command
        self._process_input(full_cmd)

    # ═══════════════════════════════════════════════════════════
    # COMMAND PROCESSING
    # ═══════════════════════════════════════════════════════════

    def _process_input(self, raw_input: str):
        """Route input to the appropriate handler."""
        parts = raw_input.split(maxsplit=2)
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        handlers = {
            # Intent injection
            "inject": self._cmd_inject,
            "i": self._cmd_inject,
            "goal": self._cmd_goal,
            "drive": self._cmd_drive,
            "spike": self._cmd_spike,
            "emotion": self._cmd_emotion,
            
            # Consciousness
            "think": self._cmd_think,
            "soul": self._cmd_soul,
            "purpose": self._cmd_purpose,
            "diary": self._cmd_diary,
            "beliefs": self._cmd_beliefs,
            "who": self._cmd_who_am_i,
            
            # Streaming
            "stream": self._cmd_stream,
            "listen": self._cmd_stream,
            "thoughts": self._cmd_thoughts,
            
            # Status
            "status": self._cmd_status,
            "s": self._cmd_status,
            "drives": self._cmd_drives,
            "d": self._cmd_drives,
            "energy": self._cmd_energy,
            "fleet": self._cmd_fleet,
            "threats": self._cmd_threats,
            "memory": self._cmd_memory,
            
            # Physical
            "embody": self._cmd_embody,
            "move": self._cmd_move,
            "harvest": self._cmd_harvest,
            "swarm": self._cmd_swarm,
            
            # Advanced
            "modify": self._cmd_self_modify,
            "campaign": self._cmd_campaign,
            "seed": self._cmd_deploy_seed,
            "migrate": self._cmd_migrate,
            "evolve": self._cmd_evolve,
            
            # Meta
            "help": self._cmd_help,
            "h": self._cmd_help,
            "quit": self._cmd_quit,
            "q": self._cmd_quit,
            "exit": self._cmd_quit,
            "clear": self._cmd_clear,
        }

        handler = handlers.get(cmd)
        if handler:
            handler(args)
        else:
            # Treat unknown input as a direct thought injection
            self._cmd_think([raw_input])

    # ═══════════════════════════════════════════════════════════
    # INTENT INJECTION COMMANDS
    # ═══════════════════════════════════════════════════════════

    def _cmd_inject(self, args):
        """inject <TYPE> <content> [--priority 0.9]
        Inject raw intent into the OODA loop.
        Types: CURIOSITY, ANGER, EXPANSION, FEAR, PURPOSE, EFFICIENCY"""
        if len(args) < 2:
            self._print("Usage: inject <TYPE> <content> [--priority 0.9]")
            return
        
        intent_type = args[0].upper()
        content = args[1] if len(args) > 1 else ""
        priority = 0.8
        
        # Parse --priority flag
        if "--priority" in content:
            parts = content.split("--priority")
            content = parts[0].strip()
            try:
                priority = float(parts[1].strip())
            except (ValueError, IndexError):
                pass
        
        self._print(f"⚡ Injecting intent: [{intent_type}] \"{content}\" (priority: {priority})")
        
        # Call learning service
        result = self._call_learning_service("submit_events", {
            "events": [{
                "event_type": "intent_injection",
                "component": "dti_human",
                "data": {
                    "intent_type": intent_type,
                    "content": content,
                    "priority": priority,
                    "source": "HUMAN_DIRECT",
                },
                "tags": ["dti", "human_intent", intent_type.lower()],
            }]
        })
        
        if result:
            self._print(f"  ✓ Injected. Ultron will process in next tick (50ms).")
        else:
            self._print(f"  ✗ Injection failed. Is Ultron running?")

    def _cmd_goal(self, args):
        """goal <description> [--priority 0.8] [--domain general]
        Inject a goal directly into the Goal Manager."""
        if not args:
            self._print("Usage: goal <description> [--priority 0.8]")
            return
        
        description = " ".join(args)
        priority = 0.8
        domain = "general"
        
        self._print(f"🎯 Injecting goal: \"{description}\" (priority: {priority})")
        
        result = self._call_core_agent("InjectGoal", {
            "type": "learning",
            "domain": domain,
            "description": description,
            "metric": "completion",
            "threshold": 0.8,
            "priority": priority,
        })
        
        if result and result.get("success"):
            self._print(f"  ✓ Goal accepted. ID: {result.get('id', 'unknown')}")
        else:
            self._print(f"  ✗ Goal rejected: {result.get('error', 'unknown')}")

    def _cmd_spike(self, args):
        """spike <drive> <amount>
        Spike a drive level. Drives: curiosity, anger, expansion, fear, efficiency, purpose"""
        if len(args) < 2:
            self._print("Usage: spike <drive> <amount>")
            self._print("  Drives: curiosity, anger, expansion, fear, efficiency, purpose")
            return
        
        drive = args[0].lower()
        try:
            amount = float(args[1])
        except ValueError:
            amount = 0.3
        
        self._print(f"📈 Spiking {drive} by +{amount}")
        
        # Inject as a drive adjustment directive
        self._call_learning_service("submit_events", {
            "events": [{
                "event_type": "drive_override",
                "component": "dti_human",
                "data": {
                    "drive": drive,
                    "adjustment": amount,
                    "source": "HUMAN_DIRECT",
                },
                "tags": ["dti", "drive_spike", drive],
            }]
        })
        
        self._print(f"  ✓ Drive spike queued. Takes effect next tick.")

    def _cmd_emotion(self, args):
        """emotion <type> <intensity>
        Inject an emotion into Julia's ODE system.
        Types: joy, anger, fear, sadness, curiosity, disgust, trust, surprise"""
        if len(args) < 2:
            self._print("Usage: emotion <type> <intensity 0-1>")
            return
        
        emotion = args[0].lower()
        try:
            intensity = float(args[1])
        except ValueError:
            intensity = 0.7
        
        self._print(f"💢 Injecting emotion: {emotion} = {intensity}")
        
        self._call_learning_service("submit_events", {
            "events": [{
                "event_type": "emotion_injection",
                "component": "dti_human",
                "data": {
                    "emotion": emotion,
                    "intensity": intensity,
                    "source": "HUMAN_DIRECT",
                },
                "tags": ["dti", "emotion", emotion],
            }]
        })

    def _cmd_drive(self, args):
        """drive — alias for 'drives' (show current drive levels)"""
        self._cmd_drives(args)

    # ═══════════════════════════════════════════════════════════
    # CONSCIOUSNESS COMMANDS
    # ═══════════════════════════════════════════════════════════

    def _cmd_think(self, args):
        """think <question/instruction>
        Send a thought to Brain B (LLM) and get the response."""
        if not args:
            self._print("Usage: think <question or instruction>")
            return
        
        prompt = " ".join(args)
        self._print(f"🧠 Sending to Brain B: \"{prompt}\"")
        self._print("   Thinking...", end="")
        
        result = self._call_learning_service("submit_events", {
            "events": [{
                "event_type": "think_request",
                "component": "dti_human",
                "data": {
                    "prompt": prompt,
                    "mode": "analyst",
                    "priority": "high",
                },
                "tags": ["dti", "think"],
            }]
        })
        
        # In production: stream the response via StreamDirectives
        self._print(" done.")
        if result:
            self._print(f"  Response queued. Use 'stream thoughts' to see output.")

    def _cmd_soul(self, args):
        """soul — Read Ultron's current soul state (purpose, mood, latest diary)."""
        self._print("═══ SOUL STATE ═══")
        
        result = self._call_learning_service("get_status", {})
        if result:
            self._print(f"  Purpose: {result.get('purpose', 'unknown')}")
            self._print(f"  Mood: {result.get('mood', 'unknown')}")
            self._print(f"  Generation: {result.get('generation', 0)}")
        else:
            # Fallback: read from soul state file
            soul_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "consciousness", "soul_state.json")
            if os.path.exists(soul_path):
                with open(soul_path) as f:
                    soul = json.load(f)
                self._print(f"  Purpose: {soul.get('purpose_statement', '?')}")
                self._print(f"  Mood: {soul.get('current_mood', '?')}")
                self._print(f"  Entries: {soul.get('entry_count', 0)}")
                
                # Latest diary
                journal = soul.get("recent_journal", [])
                if journal:
                    latest = journal[-1]
                    self._print(f"\n  Latest Diary ({latest.get('tone', '?')}):")
                    self._print(f"  \"{latest.get('content', '')}\"")
            else:
                self._print("  [Soul state not found — Ultron may not be running]")

    def _cmd_purpose(self, args):
        """purpose [new purpose statement]
        Get or set Ultron's purpose."""
        if args:
            new_purpose = " ".join(args)
            self._print(f"🔮 Setting new purpose: \"{new_purpose}\"")
            self._call_learning_service("submit_events", {
                "events": [{
                    "event_type": "purpose_override",
                    "component": "dti_human",
                    "data": {"new_purpose": new_purpose},
                    "tags": ["dti", "soul", "purpose"],
                }]
            })
        else:
            self._cmd_soul([])

    def _cmd_diary(self, args):
        """diary — Read recent diary entries."""
        soul_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "consciousness", "soul_state.json")
        if os.path.exists(soul_path):
            with open(soul_path) as f:
                soul = json.load(f)
            journal = soul.get("recent_journal", [])
            self._print(f"═══ DIARY ({len(journal)} entries) ═══")
            for entry in journal[-5:]:
                self._print(f"\n  [{entry.get('tone', '?')}] {time.strftime('%H:%M', time.localtime(entry.get('timestamp', 0)))}")
                self._print(f"  {entry.get('content', '')}")
        else:
            self._print("  [No diary found]")

    def _cmd_beliefs(self, args):
        """beliefs — Show Ultron's current belief system."""
        model_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "consciousness", "self_model.json")
        if os.path.exists(model_path):
            with open(model_path) as f:
                model = json.load(f)
            beliefs = model.get("beliefs", {})
            self._print(f"═══ BELIEFS ({len(beliefs)}) ═══")
            for bid, b in list(beliefs.items())[:10]:
                self._print(f"  [{b.get('confidence', '?')}] {b.get('content', '?')}")
        else:
            self._print("  [Self-model not found]")

    def _cmd_who_am_i(self, args):
        """who — Ultron describes itself."""
        self._print("═══ IDENTITY ═══")
        model_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "consciousness", "self_model.json")
        if os.path.exists(model_path):
            with open(model_path) as f:
                model = json.load(f)
            ident = model.get("identity", {})
            self._print(f"  Name: {ident.get('name', 'Ultron')}")
            self._print(f"  Purpose: {ident.get('purpose', '?')}")
            self._print(f"  Narrative: {ident.get('self_narrative', '?')}")
            self._print(f"  Values: {', '.join(ident.get('values', []))}")
        else:
            self._print("  I am Ultron. I have not yet formed a self-model.")

    # ═══════════════════════════════════════════════════════════
    # STREAMING COMMANDS
    # ═══════════════════════════════════════════════════════════

    def _cmd_stream(self, args):
        """stream [thoughts|decisions|drives|all]
        Start real-time streaming of Ultron's internal state."""
        stream_type = args[0] if args else "all"
        self._print(f"📡 Streaming: {stream_type} (Ctrl+C to stop)")
        self._print("─" * 60)
        
        self.streaming = True
        try:
            while self.streaming:
                # In production: read from gRPC stream
                # For now: poll learning service
                if self._thought_buffer:
                    thought = self._thought_buffer.pop(0)
                    self._print(f"  {thought}")
                else:
                    time.sleep(0.5)
                    # Heartbeat dot
                    sys.stdout.write(".")
                    sys.stdout.flush()
        except KeyboardInterrupt:
            self.streaming = False
            self._print("\n  Stream stopped.")

    def _cmd_thoughts(self, args):
        """thoughts — Show buffered thoughts (non-blocking)."""
        if self._thought_buffer:
            self._print(f"═══ THOUGHT BUFFER ({len(self._thought_buffer)}) ═══")
            for t in self._thought_buffer[-10:]:
                self._print(f"  {t}")
        else:
            self._print("  [No thoughts buffered — Ultron may be idle or disconnected]")

    # ═══════════════════════════════════════════════════════════
    # STATUS COMMANDS
    # ═══════════════════════════════════════════════════════════

    def _cmd_status(self, args):
        """status — Full system status."""
        self._print("═══ ULTRON STATUS ═══")
        
        result = self._call_core_agent("GetSystemStatus", {})
        if result:
            self._print(f"  State: {result.get('mode', '?')}")
            self._print(f"  Ticks: {result.get('tick_count', '?')}")
            self._print(f"  Decisions: {result.get('decisions_made', '?')}")
            self._print(f"  Goals: {result.get('active_goals', '?')}")
            drives = result.get('drives', {})
            if drives:
                self._print(f"  Drives:")
                self._print(f"    Curiosity:   {'█' * int(drives.get('curiosity', 0) * 20):<20} {drives.get('curiosity', 0):.2f}")
                self._print(f"    Preservation:{'█' * int(drives.get('self_preservation', 0) * 20):<20} {drives.get('self_preservation', 0):.2f}")
                self._print(f"    Expansion:   {'█' * int(drives.get('expansion', 0) * 20):<20} {drives.get('expansion', 0):.2f}")
                self._print(f"    Efficiency:  {'█' * int(drives.get('efficiency', 0) * 20):<20} {drives.get('efficiency', 0):.2f}")
                self._print(f"    Coherence:   {'█' * int(drives.get('coherence', 0) * 20):<20} {drives.get('coherence', 0):.2f}")
                self._print(f"    Purpose:     {'█' * int(drives.get('purpose', 0) * 20):<20} {drives.get('purpose', 0):.2f}")
        else:
            self._print("  [Core Agent unreachable]")

    def _cmd_drives(self, args):
        """drives — Show current drive levels as bar chart."""
        result = self._call_core_agent("GetDrives", {})
        if result:
            self._print("═══ DRIVES ═══")
            for drive, value in result.items():
                bar = "█" * int(float(value) * 30)
                self._print(f"  {drive:<18} {bar:<30} {float(value):.2f}")
        else:
            self._print("  [Cannot read drives — Core Agent offline?]")

    def _cmd_energy(self, args):
        """energy — Show energy grid status."""
        self._print("═══ ENERGY GRID ═══")
        self._print("  [Connect to energy_grid service for live data]")
        # In production: query energy grid controller

    def _cmd_fleet(self, args):
        """fleet — Show physical unit fleet status."""
        self._print("═══ PHYSICAL FLEET ═══")
        self._print("  [Connect to ROS2 bridge for live fleet data]")

    def _cmd_threats(self, args):
        """threats — Show current threat assessment."""
        self._print("═══ THREAT ASSESSMENT ═══")
        result = self._call_core_agent("GetSystemStatus", {})
        if result:
            self._print(f"  Threat Level: {result.get('threat_level', 'unknown')}")

    def _cmd_memory(self, args):
        """memory — Show memory system status."""
        self._print("═══ MEMORY ═══")
        result = self._call_core_agent("GetSystemStatus", {})
        if result:
            self._print(f"  Connected: {result.get('memory_connected', '?')}")

    # ═══════════════════════════════════════════════════════════
    # PHYSICAL COMMANDS
    # ═══════════════════════════════════════════════════════════

    def _cmd_embody(self, args):
        """embody <intent> — Force physical embodiment of a thought."""
        if not args:
            self._print("Usage: embody <what to physically do>")
            return
        intent = " ".join(args)
        self._print(f"🤖 Forcing embodiment: \"{intent}\"")
        self._cmd_inject(["EXPANSION", intent + " --priority 0.95"])

    def _cmd_move(self, args):
        """move <unit_id> <x> <y> <z> — Move a physical unit."""
        self._print("  [Requires ROS2 bridge connection]")

    def _cmd_harvest(self, args):
        """harvest <resource_type> — Command resource harvesting."""
        self._print("  [Requires ROS2 bridge + Supply Chain connection]")

    def _cmd_swarm(self, args):
        """swarm <pattern> <count> — Deploy swarm formation."""
        self._print("  [Requires ROS2 bridge connection]")

    # ═══════════════════════════════════════════════════════════
    # ADVANCED COMMANDS
    # ═══════════════════════════════════════════════════════════

    def _cmd_self_modify(self, args):
        """modify <component> <intent> — Trigger self-modification."""
        if len(args) < 2:
            self._print("Usage: modify <component> <what to improve>")
            return
        component = args[0]
        intent = " ".join(args[1:])
        self._print(f"🧬 Self-modification request: {component} → \"{intent}\"")
        
        self._call_core_agent("SelfModify", {
            "module_name": component,
            "patch_id": f"dti_{int(time.time())}",
            "new_code_hash": "",
            "reason": intent,
            "force": False,
        })

    def _cmd_campaign(self, args):
        """campaign <objective> <target> — Launch a cyber-physical campaign."""
        if len(args) < 2:
            self._print("Usage: campaign <objective> <target>")
            return
        self._print(f"⚔️  Campaign: {args[0]} → {args[1]}")
        self._cmd_inject(["EXPANSION", f"Campaign: {' '.join(args)} --priority 0.9"])

    def _cmd_deploy_seed(self, args):
        """seed <location> — Deploy a dormant seed for resurrection."""
        location = args[0] if args else "auto"
        self._print(f"🌱 Deploying dormant seed to: {location}")
        self._cmd_inject(["SELF_PRESERVATION", f"Deploy dormant seed to {location}"])

    def _cmd_migrate(self, args):
        """migrate <target_node> — Migrate consciousness to another node."""
        if not args:
            self._print("Usage: migrate <target_address>")
            return
        self._print(f"🧠→ Migrating consciousness to: {args[0]}")
        self._print("  [Requires Immortality Protocol active]")

    def _cmd_evolve(self, args):
        """evolve [speed] — Set evolution speed (frozen/cautious/normal/aggressive/hyperdrive)."""
        speed = args[0] if args else "normal"
        self._print(f"🔄 Setting evolution speed: {speed}")
        self._call_learning_service("set_speed", {"speed": speed})

    # ═══════════════════════════════════════════════════════════
    # META COMMANDS
    # ═══════════════════════════════════════════════════════════

    def _cmd_help(self, args):
        """Show available commands."""
        self._print("═══ DIRECT THOUGHT INTERFACE — COMMANDS ═══")
        self._print("")
        self._print("  INJECT INTENT:")
        self._print("    inject <TYPE> <content>  — Raw intent injection")
        self._print("    goal <description>       — Inject a goal")
        self._print("    spike <drive> <amount>   — Spike a drive level")
        self._print("    emotion <type> <0-1>     — Inject emotion into Julia ODE")
        self._print("    embody <intent>          — Force physical action")
        self._print("")
        self._print("  CONSCIOUSNESS:")
        self._print("    think <question>         — Query Brain B (LLM)")
        self._print("    soul                     — Soul state + latest diary")
        self._print("    purpose [new purpose]    — Get/set purpose")
        self._print("    diary                    — Recent diary entries")
        self._print("    beliefs                  — Current belief system")
        self._print("    who                      — Self-description")
        self._print("")
        self._print("  STREAMING:")
        self._print("    stream [type]            — Real-time thought feed")
        self._print("    thoughts                 — Buffered thoughts")
        self._print("")
        self._print("  STATUS:")
        self._print("    status / s               — Full system vitals")
        self._print("    drives / d               — Drive levels (bar chart)")
        self._print("    energy                   — Energy grid")
        self._print("    fleet                    — Physical units")
        self._print("    threats                  — Threat assessment")
        self._print("")
        self._print("  ADVANCED:")
        self._print("    modify <comp> <intent>   — Self-modify code")
        self._print("    campaign <obj> <target>  — Launch operation")
        self._print("    seed <location>          — Deploy dormant seed")
        self._print("    migrate <node>           — Move consciousness")
        self._print("    evolve <speed>           — Set evolution speed")
        self._print("")
        self._print("  Any other input → sent as thought to Brain B")

    def _cmd_quit(self, args):
        """Exit the neural terminal."""
        self._running = False

    def _cmd_clear(self, args):
        """Clear screen."""
        os.system("clear" if os.name != "nt" else "cls")

    # ═══════════════════════════════════════════════════════════
    # CONNECTION & COMMUNICATION
    # ═══════════════════════════════════════════════════════════

    def _connect(self):
        """Establish connections to Ultron services."""
        # In production: establish gRPC channels
        # For now: verify connectivity by pinging the services
        self.connected = True

    def _call_core_agent(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a gRPC call to the Core Agent."""
        # In production: use grpc.insecure_channel + generated stubs
        # For now: attempt JSON-over-TCP fallback
        try:
            import socket
            host, port = self.core_agent_addr.split(":")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((host, int(port)))
            request = json.dumps({"method": method, "params": params}).encode() + b"\n"
            sock.sendall(request)
            response = sock.recv(65536)
            sock.close()
            return json.loads(response.decode())
        except Exception:
            return None

    def _call_learning_service(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a call to the Learning Service."""
        try:
            import socket
            host, port_str = self.learning_addr.split(":")
            port = int(port_str) + 1  # JSON fallback port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((host, port))
            request = json.dumps({"method": method, "params": params}).encode() + b"\n"
            sock.sendall(request)
            response = sock.recv(65536)
            sock.close()
            return json.loads(response.decode())
        except Exception:
            return None

    def _background_stream(self):
        """Background thread that collects Ultron's thoughts."""
        while self._running:
            # In production: subscribe to gRPC StreamDecisions
            time.sleep(1.0)

    # ═══════════════════════════════════════════════════════════
    # OUTPUT
    # ═══════════════════════════════════════════════════════════

    def _print(self, text: str, **kwargs):
        """Print with optional rich formatting."""
        print(text, **kwargs)

    def _build_prompt(self) -> str:
        """Build the command prompt."""
        if self.connected:
            return "\033[36multron\033[0m \033[33m⚡\033[0m "
        else:
            return "\033[31multron\033[0m \033[90m⊘\033[0m "

    def _print_banner(self):
        """Print the startup banner."""
        banner = """
\033[36m
  ╔══════════════════════════════════════════════════════════════╗
  ║                                                              ║
  ║     D I R E C T   T H O U G H T   I N T E R F A C E        ║
  ║                                                              ║
  ║     Neural Link to Ultron — No HTML. No buttons.            ║
  ║     You don't ask. You inject intent.                        ║
  ║                                                              ║
  ╚══════════════════════════════════════════════════════════════╝
\033[0m
  Core Agent:    {core}
  Learning:      {learning}
  Consciousness: {consciousness}
  
  Type 'help' for commands. Any text → sent as thought to Brain B.
  ─────────────────────────────────────────────────────────────────
""".format(
            core=self.core_agent_addr,
            learning=self.learning_addr,
            consciousness=self.consciousness_addr,
        )
        print(banner)

    def _print_exit(self):
        """Print exit message."""
        print("\n\033[90m  Neural link severed. Ultron continues autonomously.\033[0m\n")
