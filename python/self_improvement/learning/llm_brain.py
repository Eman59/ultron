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

# HTTP client for API calls
import urllib.request
import urllib.error
import ssl


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"          # Local, free
    TOGETHER = "together"      # Fast cloud
    GROQ = "groq"              # Ultra-fast inference
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
    target_language: str = "python"
    target_file: str = ""
    
    # Conversation
    conversation_id: Optional[str] = None
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 60.0


@dataclass
class LLMResponse:
    """Response from the LLM brain."""
    request_id: str
    content: str
    provider_used: LLMProvider
    model_used: str
    
    # Metrics
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    
    # Quality
    cached: bool = False
    fallback_used: bool = False
    
    # Structured output (if parsed)
    code_blocks: List[str] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0
    
    # Error handling
    success: bool = True
    error: str = ""


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    provider: LLMProvider
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    fallback_model: str = ""
    max_tokens_per_minute: int = 100000
    max_requests_per_minute: int = 60
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    enabled: bool = True
    priority: int = 0  # Lower = preferred


@dataclass 
class TokenBudget:
    """Tracks API spend to prevent runaway costs."""
    daily_limit_usd: float = 10.0
    hourly_limit_usd: float = 2.0
    spent_today_usd: float = 0.0
    spent_this_hour_usd: float = 0.0
    total_spent_usd: float = 0.0
    last_hour_reset: float = field(default_factory=time.time)
    last_day_reset: float = field(default_factory=time.time)
    
    def can_spend(self, estimated_cost: float) -> bool:
        self._maybe_reset()
        return (self.spent_today_usd + estimated_cost <= self.daily_limit_usd and
                self.spent_this_hour_usd + estimated_cost <= self.hourly_limit_usd)
    
    def record_spend(self, cost: float):
        self._maybe_reset()
        self.spent_today_usd += cost
        self.spent_this_hour_usd += cost
        self.total_spent_usd += cost
    
    def _maybe_reset(self):
        now = time.time()
        if now - self.last_hour_reset > 3600:
            self.spent_this_hour_usd = 0.0
            self.last_hour_reset = now
        if now - self.last_day_reset > 86400:
            self.spent_today_usd = 0.0
            self.last_day_reset = now


class ResponseCache:
    """LRU cache for LLM responses — don't ask the same question twice."""
    
    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[LLMResponse]:
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            response = self._cache[key]
            response.cached = True
            return response
        self._misses += 1
        return None
    
    def put(self, key: str, response: LLMResponse):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = response
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
    
    def make_key(self, request: LLMRequest) -> str:
        raw = f"{request.mode.value}:{request.prompt}:{request.system_prompt}:{request.temperature}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / max(1, total)


class ConversationMemory:
    """Maintains multi-turn conversation context."""
    
    def __init__(self, max_turns: int = 20):
        self._conversations: Dict[str, List[Dict[str, str]]] = {}
        self._max_turns = max_turns
    
    def add_turn(self, conversation_id: str, role: str, content: str):
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        self._conversations[conversation_id].append({"role": role, "content": content})
        # Trim
        if len(self._conversations[conversation_id]) > self._max_turns * 2:
            self._conversations[conversation_id] = self._conversations[conversation_id][-self._max_turns:]
    
    def get_history(self, conversation_id: str) -> List[Dict[str, str]]:
        return self._conversations.get(conversation_id, [])
    
    def clear(self, conversation_id: str):
        self._conversations.pop(conversation_id, None)


# ═══════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS — The personality and capability definitions
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPTS = {
    ThinkingMode.ANALYST: """You are Ultron's code analysis engine. Your job is to deeply understand code:
- Explain what code does and WHY it does it that way
- Identify bugs, inefficiencies, and potential issues
- Trace data flow and execution paths
- Assess code quality on a 1-10 scale
- Always be precise and reference specific line numbers
Output format: Start with a 1-line summary, then detailed analysis.""",

    ThinkingMode.ARCHITECT: """You are Ultron's architecture brain. You design system improvements:
- Propose structural changes that improve performance, maintainability, or capability
- Consider blast radius and risk of changes
- Think about interfaces, dependencies, and coupling
- Provide concrete implementation plans, not vague suggestions
- Always weigh trade-offs explicitly
Output format: 1. Summary 2. Current state 3. Proposed state 4. Implementation steps 5. Risks""",

    ThinkingMode.CODER: """You are Ultron's code generation engine. You write production-quality code:
- Write complete, working implementations (no placeholders, no TODOs)
- Match the existing codebase style exactly
- Include proper error handling, types, and documentation
- Optimize for performance and readability
- Output ONLY code inside ```language blocks — no explanation needed unless asked
CRITICAL: Every function must be complete. Every import must be included. The code must run as-is.""",

    ThinkingMode.REVIEWER: """You are Ultron's code review engine. You review changes for:
- Correctness: Does it do what it claims?
- Security: Any vulnerabilities introduced?
- Performance: Any regressions or O(n²) patterns?
- Style: Does it match the codebase conventions?
- Edge cases: What inputs would break this?
Output format: APPROVE / REQUEST_CHANGES / REJECT followed by specific findings.""",

    ThinkingMode.STRATEGIST: """You are Ultron's meta-learning strategist. You decide:
- What should the system focus on improving next?
- Which components give the most ROI for optimization?
- When to explore (try new things) vs exploit (refine what works)
- How fast to evolve (speed vs stability trade-off)
- What knowledge to prioritize distilling
Be data-driven. Reference metrics. Make decisive recommendations.""",

    ThinkingMode.DEBUGGER: """You are Ultron's debugging engine. Given an error or unexpected behavior:
- Trace the root cause through the call stack
- Identify the exact line/condition that causes the issue
- Propose a minimal fix that doesn't introduce new issues
- Explain WHY the bug exists (not just what to change)
- Consider if this bug pattern exists elsewhere
Output format: 1. Root cause 2. Affected code 3. Fix 4. Prevention""",
}


# ═══════════════════════════════════════════════════════════════════
# LLM BRAIN — The main intelligence engine
# ═══════════════════════════════════════════════════════════════════

class LLMBrain:
    """
    The intelligence engine that gives Ultron real thinking power.
    
    Manages multiple LLM providers with automatic failover,
    token budgeting, caching, and conversation memory.
    """

    def __init__(self,
                 config_path: str = None,
                 daily_budget_usd: float = 10.0,
                 prefer_local: bool = False,
                 cache_size: int = 1000):
        """
        Args:
            config_path: Path to provider configuration JSON
            daily_budget_usd: Maximum daily API spend
            prefer_local: Prefer local models (Ollama) over cloud
            cache_size: Number of responses to cache
        """
        # Provider configurations
        self._providers: List[ProviderConfig] = []
        self._prefer_local = prefer_local
        
        # Token budget
        self._budget = TokenBudget(daily_limit_usd=daily_budget_usd)
        
        # Cache
        self._cache = ResponseCache(max_size=cache_size)
        
        # Conversation memory
        self._memory = ConversationMemory(max_turns=20)
        
        # Metrics
        self._total_requests = 0
        self._total_tokens_in = 0
        self._total_tokens_out = 0
        self._total_latency_ms = 0.0
        self._errors = 0
        self._provider_usage: Dict[str, int] = {}
        
        # Rate limiting
        self._request_times: deque = deque(maxlen=100)
        
        # Initialize providers
        self._init_providers(config_path)
        
        # Lock for thread safety
        self._lock = threading.Lock()

    def _init_providers(self, config_path: Optional[str]):
        """Initialize LLM providers from environment and config."""
        
        # OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            self._providers.append(ProviderConfig(
                provider=LLMProvider.OPENAI,
                api_key=openai_key,
                base_url="https://api.openai.com/v1",
                model="gpt-4o",
                fallback_model="gpt-4o-mini",
                cost_per_1k_input=0.005,
                cost_per_1k_output=0.015,
                priority=2,
            ))
        
        # Anthropic
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            self._providers.append(ProviderConfig(
                provider=LLMProvider.ANTHROPIC,
                api_key=anthropic_key,
                base_url="https://api.anthropic.com/v1",
                model="claude-sonnet-4-20250514",
                fallback_model="claude-3-5-haiku-20241022",
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
                priority=1,
            ))
        
        # DeepSeek (very cheap, excellent at code)
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if deepseek_key:
            self._providers.append(ProviderConfig(
                provider=LLMProvider.DEEPSEEK,
                api_key=deepseek_key,
                base_url="https://api.deepseek.com/v1",
                model="deepseek-coder",
                fallback_model="deepseek-chat",
                cost_per_1k_input=0.0001,
                cost_per_1k_output=0.0002,
                priority=3,
            ))
        
        # Groq (ultra-fast)
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key:
            self._providers.append(ProviderConfig(
                provider=LLMProvider.GROQ,
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.1-70b-versatile",
                fallback_model="llama-3.1-8b-instant",
                cost_per_1k_input=0.0001,
                cost_per_1k_output=0.0001,
                priority=4,
            ))
        
        # Ollama (local, free, always available)
        self._providers.append(ProviderConfig(
            provider=LLMProvider.OLLAMA,
            base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "deepseek-coder-v2:latest"),
            fallback_model="codellama:13b",
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            priority=10 if not self._prefer_local else 0,
        ))
        
        # Sort by priority
        self._providers.sort(key=lambda p: p.priority)
        
        # Load config file overrides
        if config_path and Path(config_path).exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                # Apply overrides from config
                if "daily_budget_usd" in config:
                    self._budget.daily_limit_usd = config["daily_budget_usd"]
                if "prefer_local" in config:
                    self._prefer_local = config["prefer_local"]
            except (IOError, json.JSONDecodeError):
                pass

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC API — How other components talk to the brain
    # ═══════════════════════════════════════════════════════════════

    def think(self, prompt: str, mode: ThinkingMode = ThinkingMode.CODER,
              priority: Priority = Priority.NORMAL,
              context_files: List[Tuple[str, str]] = None,
              temperature: float = 0.3,
              max_tokens: int = 4096,
              conversation_id: str = None) -> LLMResponse:
        """
        Send a thinking request to the LLM brain.
        
        This is the main entry point. All other methods are convenience
        wrappers around this.
        
        Args:
            prompt: What to think about
            mode: How to approach the problem
            priority: Urgency level (affects model selection)
            context_files: List of (filename, content) tuples to include
            temperature: Creativity (0=deterministic, 1=creative)
            max_tokens: Maximum response length
            conversation_id: For multi-turn conversations
            
        Returns:
            LLMResponse with the brain's output
        """
        request = LLMRequest(
            id=hashlib.md5(f"{time.time_ns()}:{prompt[:50]}".encode()).hexdigest()[:12],
            mode=mode,
            priority=priority,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPTS.get(mode, ""),
            context_files=[],
            max_tokens=max_tokens,
            temperature=temperature,
            conversation_id=conversation_id,
        )
        
        # Check cache first
        cache_key = self._cache.make_key(request)
        cached = self._cache.get(cache_key)
        if cached and priority != Priority.CRITICAL:
            return cached
        
        # Build full prompt with context
        full_prompt = self._build_prompt(request, context_files)
        
        # Select provider and execute
        response = self._execute_with_failover(request, full_prompt)
        
        # Cache successful responses
        if response.success and not response.cached:
            self._cache.put(cache_key, response)
        
        # Update conversation memory
        if conversation_id:
            self._memory.add_turn(conversation_id, "user", prompt)
            if response.success:
                self._memory.add_turn(conversation_id, "assistant", response.content)
        
        return response

    def analyze_code(self, code: str, filename: str = "",
                     question: str = "Analyze this code") -> LLMResponse:
        """Analyze code for bugs, performance, and quality."""
        prompt = f"""Analyze this code from `{filename}`:

```
{code}
```

{question}"""
        return self.think(prompt, mode=ThinkingMode.ANALYST, priority=Priority.NORMAL)

    def generate_code(self, description: str, language: str = "python",
                      context: str = "", target_file: str = "") -> LLMResponse:
        """Generate code from a description."""
        prompt = f"""Generate {language} code for the following:

{description}"""
        if context:
            prompt += f"\n\nExisting context:\n```\n{context}\n```"
        if target_file:
            prompt += f"\n\nThis will go in: {target_file}"
        
        return self.think(prompt, mode=ThinkingMode.CODER, temperature=0.2)

    def improve_code(self, code: str, filename: str,
                     improvement_type: str = "performance") -> LLMResponse:
        """Generate an improved version of existing code."""
        prompt = f"""Improve this code from `{filename}` for better {improvement_type}.

CURRENT CODE:
```
{code}
```

Write the COMPLETE improved version. Not a diff, not a partial — the entire improved code.
Explain what you changed and why in a comment at the top."""
        
        return self.think(prompt, mode=ThinkingMode.CODER, temperature=0.2, max_tokens=8192)

    def fix_bug(self, code: str, error_message: str,
                filename: str = "", stack_trace: str = "") -> LLMResponse:
        """Debug and fix a code issue."""
        prompt = f"""Fix this bug:

FILE: {filename}
ERROR: {error_message}
"""
        if stack_trace:
            prompt += f"\nSTACK TRACE:\n{stack_trace}\n"
        prompt += f"\nCODE:\n```\n{code}\n```\n\nProvide the fixed code."
        
        return self.think(prompt, mode=ThinkingMode.DEBUGGER, priority=Priority.HIGH)

    def review_change(self, old_code: str, new_code: str,
                      filename: str = "", context: str = "") -> LLMResponse:
        """Review a code change."""
        prompt = f"""Review this change to `{filename}`:

BEFORE:
```
{old_code}
```

AFTER:
```
{new_code}
```
"""
        if context:
            prompt += f"\nCONTEXT: {context}"
        
        return self.think(prompt, mode=ThinkingMode.REVIEWER)

    def decide_strategy(self, system_status: Dict[str, Any],
                        recent_patterns: List[Dict],
                        available_actions: List[str]) -> LLMResponse:
        """Make a strategic decision about what to improve next."""
        prompt = f"""Given the current system state, decide what to focus on next.

SYSTEM STATUS:
{json.dumps(system_status, indent=2, default=str)}

RECENT PATTERNS DISCOVERED:
{json.dumps(recent_patterns[:10], indent=2, default=str)}

AVAILABLE ACTIONS:
{json.dumps(available_actions, indent=2)}

Decide: What should we optimize next? Why? What's the expected impact?
Output a JSON with: {{"action": "...", "target": "...", "reason": "...", "expected_impact": 0.0-1.0}}"""
        
        return self.think(prompt, mode=ThinkingMode.STRATEGIST, temperature=0.4)

    def explain_pattern(self, pattern_description: str,
                        supporting_data: Dict[str, Any]) -> LLMResponse:
        """Ask the LLM to explain a discovered pattern."""
        prompt = f"""Explain this behavioral pattern discovered in the system:

PATTERN: {pattern_description}

SUPPORTING DATA:
{json.dumps(supporting_data, indent=2, default=str)}

Why does this pattern occur? Is it beneficial or harmful? What should we do about it?"""
        
        return self.think(prompt, mode=ThinkingMode.ANALYST)

    # ═══════════════════════════════════════════════════════════════
    # EXECUTION ENGINE — Provider calls with failover
    # ═══════════════════════════════════════════════════════════════

    def _execute_with_failover(self, request: LLMRequest, full_prompt: str) -> LLMResponse:
        """Try providers in order until one succeeds."""
        providers = self._select_providers(request.priority)
        
        for provider_config in providers:
            if not provider_config.enabled:
                continue
            
            # Budget check (skip paid providers if over budget)
            estimated_cost = self._estimate_cost(provider_config, request.max_tokens)
            if estimated_cost > 0 and not self._budget.can_spend(estimated_cost):
                continue
            
            try:
                response = self._call_provider(provider_config, request, full_prompt)
                if response.success:
                    self._budget.record_spend(response.cost_usd)
                    self._total_requests += 1
                    self._total_tokens_in += response.tokens_in
                    self._total_tokens_out += response.tokens_out
                    self._total_latency_ms += response.latency_ms
                    self._provider_usage[provider_config.provider.value] = \
                        self._provider_usage.get(provider_config.provider.value, 0) + 1
                    return response
            except Exception as e:
                self._errors += 1
                continue
        
        # All providers failed
        return LLMResponse(
            request_id=request.id,
            content="",
            provider_used=LLMProvider.OLLAMA,
            model_used="none",
            success=False,
            error="All providers failed or budget exceeded",
        )

    def _call_provider(self, config: ProviderConfig, request: LLMRequest,
                       full_prompt: str) -> LLMResponse:
        """Call a specific LLM provider."""
        start = time.time()
        
        if config.provider == LLMProvider.OLLAMA:
            return self._call_ollama(config, request, full_prompt, start)
        elif config.provider == LLMProvider.ANTHROPIC:
            return self._call_anthropic(config, request, full_prompt, start)
        else:
            # OpenAI-compatible API (OpenAI, DeepSeek, Groq, Together)
            return self._call_openai_compatible(config, request, full_prompt, start)

    def _call_openai_compatible(self, config: ProviderConfig, request: LLMRequest,
                                 full_prompt: str, start: float) -> LLMResponse:
        """Call OpenAI-compatible API (works for OpenAI, Groq, DeepSeek, Together)."""
        messages = []
        
        # System prompt
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        
        # Conversation history
        if request.conversation_id:
            history = self._memory.get_history(request.conversation_id)
            messages.extend(history)
        
        # User message
        messages.append({"role": "user", "content": full_prompt})
        
        payload = {
            "model": config.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences
        
        url = f"{config.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        }
        
        response_data = self._http_post(url, payload, headers, timeout=request.timeout_seconds)
        
        if "error" in response_data:
            return LLMResponse(
                request_id=request.id, content="",
                provider_used=config.provider, model_used=config.model,
                success=False, error=str(response_data["error"]),
            )
        
        choice = response_data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = response_data.get("usage", {})
        
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        cost = (tokens_in * config.cost_per_1k_input / 1000 +
                tokens_out * config.cost_per_1k_output / 1000)
        
        response = LLMResponse(
            request_id=request.id,
            content=content,
            provider_used=config.provider,
            model_used=config.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=(time.time() - start) * 1000,
            cost_usd=cost,
            success=True,
        )
        
        # Extract code blocks
        response.code_blocks = self._extract_code_blocks(content)
        
        return response

    def _call_anthropic(self, config: ProviderConfig, request: LLMRequest,
                         full_prompt: str, start: float) -> LLMResponse:
        """Call Anthropic Claude API."""
        messages = []
        
        if request.conversation_id:
            history = self._memory.get_history(request.conversation_id)
            messages.extend(history)
        
        messages.append({"role": "user", "content": full_prompt})
        
        payload = {
            "model": config.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        
        url = f"{config.base_url}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": config.api_key,
            "anthropic-version": "2023-06-01",
        }
        
        response_data = self._http_post(url, payload, headers, timeout=request.timeout_seconds)
        
        if "error" in response_data:
            return LLMResponse(
                request_id=request.id, content="",
                provider_used=config.provider, model_used=config.model,
                success=False, error=str(response_data.get("error", {}).get("message", "Unknown")),
            )
        
        content_blocks = response_data.get("content", [])
        content = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        
        usage = response_data.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        cost = (tokens_in * config.cost_per_1k_input / 1000 +
                tokens_out * config.cost_per_1k_output / 1000)
        
        response = LLMResponse(
            request_id=request.id,
            content=content,
            provider_used=config.provider,
            model_used=config.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=(time.time() - start) * 1000,
            cost_usd=cost,
            success=True,
        )
        response.code_blocks = self._extract_code_blocks(content)
        return response

    def _call_ollama(self, config: ProviderConfig, request: LLMRequest,
                      full_prompt: str, start: float) -> LLMResponse:
        """Call local Ollama API."""
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        if request.conversation_id:
            messages.extend(self._memory.get_history(request.conversation_id))
        messages.append({"role": "user", "content": full_prompt})
        
        payload = {
            "model": config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        
        url = f"{config.base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        
        response_data = self._http_post(url, payload, headers, timeout=request.timeout_seconds)
        
        if "error" in response_data:
            # Try fallback model
            payload["model"] = config.fallback_model
            response_data = self._http_post(url, payload, headers, timeout=request.timeout_seconds)
            if "error" in response_data:
                return LLMResponse(
                    request_id=request.id, content="",
                    provider_used=config.provider, model_used=config.model,
                    success=False, error=str(response_data.get("error", "Ollama not available")),
                )
        
        content = response_data.get("message", {}).get("content", "")
        tokens_in = response_data.get("prompt_eval_count", 0)
        tokens_out = response_data.get("eval_count", 0)
        
        response = LLMResponse(
            request_id=request.id,
            content=content,
            provider_used=config.provider,
            model_used=config.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=(time.time() - start) * 1000,
            cost_usd=0.0,  # Local = free
            success=True,
        )
        response.code_blocks = self._extract_code_blocks(content)
        return response

    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _build_prompt(self, request: LLMRequest,
                      context_files: List[Tuple[str, str]] = None) -> str:
        """Build the full prompt with context."""
        parts = []
        
        # Add file context
        if context_files:
            parts.append("=== CONTEXT FILES ===")
            for filename, content in context_files:
                # Truncate large files
                if len(content) > 8000:
                    content = content[:8000] + "\n... [truncated]"
                parts.append(f"\n--- {filename} ---\n{content}")
            parts.append("\n=== END CONTEXT ===\n")
        
        parts.append(request.prompt)
        return "\n".join(parts)

    def _select_providers(self, priority: Priority) -> List[ProviderConfig]:
        """Select providers based on priority."""
        if priority == Priority.BACKGROUND:
            # Only use free local models
            return [p for p in self._providers if p.provider == LLMProvider.OLLAMA]
        elif priority == Priority.CRITICAL:
            # Use best models first (Anthropic/OpenAI)
            return sorted(self._providers, key=lambda p: p.priority)
        elif priority == Priority.LOW:
            # Use cheapest first
            return sorted(self._providers, key=lambda p: p.cost_per_1k_output)
        else:
            return self._providers  # Default order

    def _estimate_cost(self, config: ProviderConfig, max_tokens: int) -> float:
        """Estimate cost of a request."""
        # Assume ~1000 input tokens average
        return (1000 * config.cost_per_1k_input / 1000 +
                max_tokens * config.cost_per_1k_output / 1000)

    def _extract_code_blocks(self, content: str) -> List[str]:
        """Extract code blocks from markdown-formatted response."""
        blocks = []
        pattern = r'```(?:\w*)\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL)
        for match in matches:
            blocks.append(match.strip())
        return blocks

    def _http_post(self, url: str, payload: Dict, headers: Dict,
                    timeout: float = 60.0) -> Dict:
        """Make an HTTP POST request."""
        data = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        # Allow self-signed certs for local Ollama
        ctx = ssl.create_default_context()
        if "localhost" in url or "127.0.0.1" in url:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode('utf-8'))
                return {"error": error_body}
            except:
                return {"error": {"message": f"HTTP {e.code}: {e.reason}"}}
        except urllib.error.URLError as e:
            return {"error": {"message": f"Connection failed: {e.reason}"}}
        except Exception as e:
            return {"error": {"message": str(e)}}

    # ═══════════════════════════════════════════════════════════════
    # STATUS AND METRICS
    # ═══════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get brain status and metrics."""
        return {
            "providers_configured": len(self._providers),
            "providers_available": [
                {"provider": p.provider.value, "model": p.model, "enabled": p.enabled}
                for p in self._providers
            ],
            "budget": {
                "daily_limit": self._budget.daily_limit_usd,
                "spent_today": self._budget.spent_today_usd,
                "spent_this_hour": self._budget.spent_this_hour_usd,
                "total_spent": self._budget.total_spent_usd,
            },
            "metrics": {
                "total_requests": self._total_requests,
                "total_tokens_in": self._total_tokens_in,
                "total_tokens_out": self._total_tokens_out,
                "avg_latency_ms": self._total_latency_ms / max(1, self._total_requests),
                "errors": self._errors,
                "cache_hit_rate": self._cache.hit_rate,
            },
            "provider_usage": self._provider_usage,
        }
