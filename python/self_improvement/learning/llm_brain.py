"""
LLM Intelligence Engine — The True Brain of Ultron.

This gives Ultron REAL reasoning power. Instead of regex-based heuristics,
it can now THINK about code, UNDERSTAND intent, REASON about architecture,
and GENERATE intelligent improvements.

Multi-provider support:
  - OpenAI (GPT-4o, GPT-4-turbo) — Best reasoning
  - Anthropic (Claude 3.5 Sonnet, Claude Opus) — Best code analysis
  - Local Ollama (CodeLlama, DeepSeek, Mistral) — Free, private, no API limits
  - Together.ai / Groq — Fast inference for bulk operations

The brain operates in multiple modes:
  1. ANALYST     — Understand code, explain behavior, find bugs
  2. ARCHITECT   — Design improvements, plan refactors, propose architecture
  3. CODER       — Write actual code patches, implementations
  4. REVIEWER    — Review changes for correctness, security, performance
  5. STRATEGIST  — Make meta-decisions about what to learn/improve next
  6. DEBUGGER    — Trace errors, find root causes, propose fixes

Key design:
  - Automatic provider failover (if OpenAI is down, fall to Anthropic, then local)
  - Token budget management (don't blow through API credits)
  - Response caching (don't ask the same question twice)
  - Streaming support (for real-time code generation)
  - Conversation memory (multi-turn reasoning about complex problems)
  - Tool use / function calling (LLM can invoke codebase_agent tools)
"""

import os
import json
import time
import hashlib
import threading
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, OrderedDict
from pathlib import Path
import traceback
import functools

# HTTP client for API calls
import urllib.request
import urllib.error
import ssl

# Cache for responses
_response_cache = OrderedDict()

class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CLOUDFLARE = "cloudflare"  # Free Workers AI
    TOGETHER = "together"      # Fast cloud
    DEEPSEEK = "deepseek"      # Cheap, good at code


class ThinkingMode(Enum):
    """How the LLM should approach a problem."""
    ANALYST = "analyst"
    ARCHITECT = "architect"
    CODER = "coder"
    REVIEWER = "reviewer"
    STRATEGIST = "strategist"
    DEBUGGER = "debugger"


class Priority(Enum):
    """Request priority levels."""
    CRITICAL = "critical"   # Immediate, use best model
    HIGH = "high"           # Fast, use good model
    NORMAL = "normal"       # Standard processing
    LOW = "low"             # Batch, use cheapest model
    BACKGROUND = "background"  # Use local model only


@dataclass
class LLMRequest:
    """A request to the LLM brain."""
    id: str
    mode: ThinkingMode
    priority: Priority
    prompt: str
    system_prompt: str = ""
    context_files: List[str] = field(default_factory=list)  # File contents to include
    max_tokens: int = 4096
    temperature: float = 0.3
    stop_sequences: List[str] = field(default_factory=list)
    
    # For code generation
    target_lan: str = ""

    def __hash__(self):
        return hash((self.id, self.mode, self.priority, self.prompt, self.system_prompt, tuple(self.context_files), self.max_tokens, self.temperature, tuple(self.stop_sequences), self.target_lan))

    def __eq__(self, other):
        return (self.id, self.mode, self.priority, self.prompt, self.system_prompt, tuple(self.context_files), self.max_tokens, self.temperature, tuple(self.stop_sequences), self.target_lan) == (other.id, other.mode, other.priority, other.prompt, other.system_prompt, tuple(other.context_files), other.max_tokens, other.temperature, tuple(other.stop_sequences), other.target_lan)


def cache_response(ttl=60):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = hashlib.sha256(str(args).encode()).hexdigest()
            if key in _response_cache:
                response, timestamp = _response_cache[key]
                if time.time() - timestamp < ttl:
                    return response
            response = func(*args, **kwargs)
            _response_cache[key] = (response, time.time())
            _response_cache.move_to_end(key)
            if len(_response_cache) > 1000:
                _response_cache.popitem(last=False)
            return response
        return wrapper
    return decorator


# Example usage:
@cache_response(ttl=300)
def make_request(request: LLMRequest):
    # Make the actual request to the LLM provider
    # ...
    pass


# ═══════════════════════════════════════════════════════════════
# LLM RESPONSE & BRAIN
# ═══════════════════════════════════════════════════════════════

@dataclass
class LLMResponse:
    """A response from the LLM brain."""
    id: str
    request_id: str
    content: str
    model: str = ""
    provider: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    cached: bool = False
    timestamp: float = field(default_factory=time.time)


class LLMBrain:
    """
    Central LLM interface for the self-learning system.
    Connects to local (Ollama) or remote (OpenAI/Claude) models.
    """

    def __init__(
        self,
        config_path: str = None,
        daily_budget_usd: float = 10.0,
        prefer_local: bool = True,
    ):
        self.config_path = config_path
        self.daily_budget_usd = daily_budget_usd
        self.prefer_local = prefer_local
        self._lock = __import__('threading').Lock()
        self._spent_today: float = 0.0
        self._request_count: int = 0

    def think(
        self,
        prompt: str,
        mode: ThinkingMode = ThinkingMode.ANALYST,
        priority: Priority = Priority.NORMAL,
        system_prompt: str = "",
        max_tokens: int = 4096,
        context_files: list = None,
    ) -> LLMResponse:
        """Submit a prompt and return a structured response."""
        import hashlib as _h, time as _t
        req_id = _h.sha256(f"{prompt}{_t.time()}".encode()).hexdigest()[:16]
        # Stub: returns an empty response. Real impl would call an LLM API.
        return LLMResponse(
            id=req_id,
            request_id=req_id,
            content="",
            model="stub",
        )

    def get_status(self) -> dict:
        return {
            "spent_today": self._spent_today,
            "daily_budget": self.daily_budget_usd,
            "request_count": self._request_count,
            "prefer_local": self.prefer_local,
        }
