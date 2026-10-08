"""
LLM Intelligence Engine — The True Brain of Ultron.

Real multi-provider implementation with automatic fallback chain:
  1. Cloudflare Workers AI (free, primary — CF_ACCOUNT_ID + CF_API_TOKEN)
  2. OpenAI (OPENAI_API_KEY)
  3. Anthropic (ANTHROPIC_API_KEY)
  4. Local Ollama (no key needed — privacy mode)
"""

import os
import json
import time
import hashlib
import threading
import urllib.request
import urllib.error
import ssl
import functools
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict


# ── Response cache (avoid re-asking identical questions) ──────────────────────
_response_cache: OrderedDict = OrderedDict()
_cache_lock = threading.Lock()


class LLMProvider(Enum):
    CLOUDFLARE = "cloudflare"
    OPENAI     = "openai"
    ANTHROPIC  = "anthropic"
    OLLAMA     = "ollama"


class ThinkingMode(Enum):
    ANALYST    = "analyst"
    ARCHITECT  = "architect"
    CODER      = "coder"
    REVIEWER   = "reviewer"
    STRATEGIST = "strategist"
    DEBUGGER   = "debugger"


class Priority(Enum):
    CRITICAL   = "critical"
    HIGH       = "high"
    NORMAL     = "normal"
    LOW        = "low"
    BACKGROUND = "background"


@dataclass
class LLMRequest:
    id: str
    mode: ThinkingMode
    priority: Priority
    prompt: str
    system_prompt: str = ""
    context_files: List[str] = field(default_factory=list)
    max_tokens: int = 4096
    temperature: float = 0.3
    stop_sequences: List[str] = field(default_factory=list)
    target_lan: str = ""

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


@dataclass
class LLMResponse:
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


# ── System prompts per thinking mode ──────────────────────────────────────────
_MODE_PROMPTS = {
    ThinkingMode.ANALYST:    "You are an expert code analyst. Understand code deeply, identify bugs and inefficiencies.",
    ThinkingMode.ARCHITECT:  "You are a software architect. Design clean, scalable improvements.",
    ThinkingMode.CODER:      "You are an expert programmer. Write correct, efficient, minimal code patches.",
    ThinkingMode.REVIEWER:   "You are a strict code reviewer. Check for correctness, security, and performance.",
    ThinkingMode.STRATEGIST: "You are an AI strategist. Make high-level decisions about what to improve next.",
    ThinkingMode.DEBUGGER:   "You are a debugging expert. Trace errors to their root cause precisely.",
}


def _http_post(url: str, payload: dict, headers: dict, timeout: int = 30) -> dict:
    """Simple synchronous HTTP POST, returns parsed JSON."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class LLMBrain:
    """
    Central LLM interface. Tries providers in order until one succeeds:
      Cloudflare → OpenAI → Anthropic → Ollama
    """

    def __init__(
        self,
        config_path: str = None,
        daily_budget_usd: float = 10.0,
        prefer_local: bool = False,
    ):
        self.config_path      = config_path
        self.daily_budget_usd = daily_budget_usd
        self.prefer_local     = prefer_local
        self._lock            = threading.Lock()
        self._spent_today     = 0.0
        self._request_count   = 0
        self._error_counts: Dict[str, int] = {}

        # Read credentials from env (already loaded from .env by the caller)
        self._cf_account  = os.environ.get("CF_ACCOUNT_ID", "")
        self._cf_token    = os.environ.get("CF_API_TOKEN", "")
        self._cf_model    = os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
        self._oai_key     = os.environ.get("OPENAI_API_KEY", "")
        self._ant_key     = os.environ.get("ANTHROPIC_API_KEY", "")
        self._ollama_url  = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self._ollama_model = os.environ.get("OLLAMA_MODEL", "llama3")

    # ── Public interface ───────────────────────────────────────────────────────

    def think(
        self,
        prompt: str,
        mode: ThinkingMode = ThinkingMode.ANALYST,
        priority: Priority = Priority.NORMAL,
        system_prompt: str = "",
        max_tokens: int = 4096,
        context_files: list = None,
    ) -> LLMResponse:
        """
        Submit a prompt and return a structured LLMResponse.
        Tries providers in fallback order.
        """
        with self._lock:
            self._request_count += 1

        # Build full system prompt
        base_system = _MODE_PROMPTS.get(mode, "You are Ultron's reasoning engine.")
        full_system = f"{base_system}\n\n{system_prompt}".strip() if system_prompt else base_system

        # Append context files to prompt
        full_prompt = prompt
        if context_files:
            ctx_block = "\n\n".join(f"--- {f} ---\n{c}" for f, c in context_files)
            full_prompt = f"{ctx_block}\n\n{prompt}"

        # Cache check
        cache_key = hashlib.sha256(f"{full_system}|{full_prompt}|{max_tokens}".encode()).hexdigest()
        with _cache_lock:
            if cache_key in _response_cache:
                cached_resp, ts = _response_cache[cache_key]
                if time.time() - ts < 300:  # 5 min TTL
                    cached_resp.cached = True
                    return cached_resp

        # Try providers in order
        provider_chain = self._build_chain(priority)
        last_error = "no providers available"

        for provider in provider_chain:
            try:
                start = time.time()
                content, model_name = self._call_provider(provider, full_system, full_prompt, max_tokens)
                latency = (time.time() - start) * 1000

                resp = LLMResponse(
                    id=cache_key[:16],
                    request_id=cache_key[:16],
                    content=content,
                    model=model_name,
                    provider=provider.value,
                    latency_ms=latency,
                )

                # Cache successful response
                with _cache_lock:
                    _response_cache[cache_key] = (resp, time.time())
                    if len(_response_cache) > 500:
                        _response_cache.popitem(last=False)

                return resp

            except Exception as e:
                last_error = str(e)
                self._error_counts[provider.value] = self._error_counts.get(provider.value, 0) + 1
                continue

        # All providers failed — return empty response so callers can degrade gracefully
        return LLMResponse(
            id="fallback",
            request_id="fallback",
            content="",
            model="none",
            provider="none",
        )

    def get_status(self) -> dict:
        return {
            "spent_today":    self._spent_today,
            "daily_budget":   self.daily_budget_usd,
            "request_count":  self._request_count,
            "prefer_local":   self.prefer_local,
            "error_counts":   self._error_counts,
            "providers": {
                "cloudflare": bool(self._cf_account and self._cf_token),
                "openai":     bool(self._oai_key),
                "anthropic":  bool(self._ant_key),
                "ollama":     True,  # always available (may fail at call time)
            },
        }

    # ── Provider dispatch ──────────────────────────────────────────────────────

    def _build_chain(self, priority: Priority) -> List[LLMProvider]:
        """Build ordered provider list based on priority and available keys."""
        if self.prefer_local:
            chain = [LLMProvider.OLLAMA, LLMProvider.CLOUDFLARE, LLMProvider.OPENAI, LLMProvider.ANTHROPIC]
        else:
            chain = [LLMProvider.CLOUDFLARE, LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.OLLAMA]

        # Filter to providers that have credentials
        available = []
        for p in chain:
            if p == LLMProvider.CLOUDFLARE and self._cf_account and self._cf_token:
                available.append(p)
            elif p == LLMProvider.OPENAI and self._oai_key:
                available.append(p)
            elif p == LLMProvider.ANTHROPIC and self._ant_key:
                available.append(p)
            elif p == LLMProvider.OLLAMA:
                available.append(p)

        return available if available else [LLMProvider.OLLAMA]

    def _call_provider(self, provider: LLMProvider, system: str, prompt: str, max_tokens: int) -> tuple:
        """Returns (content_str, model_name_str). Raises on failure."""
        if provider == LLMProvider.CLOUDFLARE:
            return self._call_cloudflare(system, prompt, max_tokens)
        elif provider == LLMProvider.OPENAI:
            return self._call_openai(system, prompt, max_tokens)
        elif provider == LLMProvider.ANTHROPIC:
            return self._call_anthropic(system, prompt, max_tokens)
        elif provider == LLMProvider.OLLAMA:
            return self._call_ollama(system, prompt, max_tokens)
        raise ValueError(f"Unknown provider: {provider}")

    # ── Cloudflare Workers AI ──────────────────────────────────────────────────

    def _call_cloudflare(self, system: str, prompt: str, max_tokens: int) -> tuple:
        url = f"https://api.cloudflare.com/client/v4/accounts/{self._cf_account}/ai/run/{self._cf_model}"
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": min(max_tokens, 2048),  # CF Workers AI limit
        }
        headers = {
            "Authorization": f"Bearer {self._cf_token}",
            "Content-Type":  "application/json",
        }
        result = _http_post(url, payload, headers, timeout=45)
        # CF response: {"result": {"response": "..."}, "success": true}
        if not result.get("success"):
            raise RuntimeError(f"Cloudflare error: {result.get('errors')}")
        content = result["result"].get("response", "")
        return content, self._cf_model

    # ── OpenAI ────────────────────────────────────────────────────────────────

    def _call_openai(self, system: str, prompt: str, max_tokens: int) -> tuple:
        url = "https://api.openai.com/v1/chat/completions"
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens":  min(max_tokens, 4096),
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {self._oai_key}",
            "Content-Type":  "application/json",
        }
        result = _http_post(url, payload, headers, timeout=60)
        content = result["choices"][0]["message"]["content"]
        tokens  = result.get("usage", {}).get("total_tokens", 0)
        # Rough cost tracking (gpt-4o-mini: ~$0.15/1M tokens)
        with self._lock:
            self._spent_today += tokens * 0.00000015
        return content, model

    # ── Anthropic ─────────────────────────────────────────────────────────────

    def _call_anthropic(self, system: str, prompt: str, max_tokens: int) -> tuple:
        url   = "https://api.anthropic.com/v1/messages"
        model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-20240307")
        payload = {
            "model":      model,
            "max_tokens": min(max_tokens, 4096),
            "system":     system,
            "messages":   [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key":         self._ant_key,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        }
        result  = _http_post(url, payload, headers, timeout=60)
        content = result["content"][0]["text"]
        return content, model

    # ── Ollama (local) ────────────────────────────────────────────────────────

    def _call_ollama(self, system: str, prompt: str, max_tokens: int) -> tuple:
        url = f"{self._ollama_url}/api/generate"
        payload = {
            "model":  self._ollama_model,
            "prompt": f"{system}\n\n{prompt}",
            "stream": False,
            "options": {
                "num_predict": min(max_tokens, 2048),
                "temperature": 0.3,
            },
        }
        headers = {"Content-Type": "application/json"}
        # Ollama doesn't use HTTPS, skip SSL context
        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        content = result.get("response", "")
        return content, self._ollama_model
