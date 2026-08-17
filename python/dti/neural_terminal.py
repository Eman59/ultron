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
        self.console: Optional[Console] = Console() if HAS_RICH else None
        
        # Connection targets
        self.core_agent_addr: str = os.getenv("ULTRON_CORE_AGENT_ADDR", "localhost:50051")
        self.learning_addr: str = os.getenv("ULTRON_LEARNING_ADDR", "localhost:50060")
        self.consciousness_addr: str = os.getenv("ULTRON_CONSCIOUSNESS_ADDR", "localhost:50070")
        
        # State
        self.connected: bool = False
        self.streaming: bool = False
        self._running: bool = True
        self._thought_buffer: List[str] = []
        self._max_buffer: int = 100
        
        # Command history
        self._history: List[str] = []

    def run_interactive(self) -> None:
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
                    prompt: str = self._build_prompt()
                    cmd: str = input(prompt)
                    
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