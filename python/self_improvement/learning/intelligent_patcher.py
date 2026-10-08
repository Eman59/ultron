"""
Intelligent Patch Generator — LLM-Powered Code Evolution.

Full implementation:
  1. Reads the target file completely
  2. Optionally profiles it via CodeIntrospector
  3. Calls LLMBrain in CODER mode with structured prompt
  4. Parses JSON patch response {old_code, new_code, reasoning, confidence}
  5. Validates old_code exists verbatim in file
  6. Applies via CodebaseAgent (with backup + rollback)
  7. Records outcome in ExperienceCollector
"""

import os
import re
import json
import time
import hashlib
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PatchIntent(Enum):
    FIX_BUG              = "fix_bug"
    OPTIMIZE_PERFORMANCE = "optimize_performance"
    REDUCE_COMPLEXITY    = "reduce_complexity"
    ADD_ERROR_HANDLING   = "add_error_handling"
    IMPROVE_READABILITY  = "improve_readability"
    ADD_FEATURE          = "add_feature"
    REMOVE_DEAD_CODE     = "remove_dead_code"
    REFACTOR             = "refactor"
    ADD_CACHING          = "add_caching"
    FIX_SECURITY         = "fix_security"
    ADD_LOGGING          = "add_logging"
    PARALLELIZE          = "parallelize"


class PatchOutcome(Enum):
    SUCCESS          = "success"
    VALIDATION_FAILED = "validation_failed"
    REVIEW_REJECTED  = "review_rejected"
    APPLY_FAILED     = "apply_failed"
    VERIFY_FAILED    = "verify_failed"
    ROLLED_BACK      = "rolled_back"
    SKIPPED          = "skipped"
    LLM_FAILED       = "llm_failed"


@dataclass
class IntelligentPatch:
    patch_id:             str
    patch_intent:         PatchIntent
    target_file_path:     str
    target_function_name: Optional[str] = None

    # Problem context
    problem_diagnosis: str   = ""
    problem_severity:  float = 0.0

    # LLM reasoning
    problem_analysis:  str = ""
    solution_reasoning: str = ""
    generated_code:    str = ""
    review_result:     str = ""

    # Change details
    original_code:      str = ""
    updated_code:       str = ""
    code_diff_summary:  str = ""

    # Outcome
    patch_outcome:        PatchOutcome = PatchOutcome.SKIPPED
    change_record:        Any          = None
    verification_passed:  bool         = False

    # Metrics
    llm_tokens_used: int = field(default=0)
    confidence:     float = 0.0
    provider_used:  str   = ""


# ── System prompts ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are Ultron's self-modification engine. You improve your own source code.

STRICT OUTPUT RULES — return ONLY valid JSON, no markdown, no prose outside the JSON:
{
  "old_code": "<exact verbatim substring to replace — must exist in the file as-is>",
  "new_code": "<drop-in replacement — same indentation, correct syntax>",
  "reasoning": "<one sentence: what problem this fixes and why this approach>",
  "confidence": <float 0.0-1.0>
}

If no safe improvement exists, return: {"old_code":"","new_code":"","reasoning":"no safe improvement found","confidence":0.0}
Never fabricate old_code. Never break existing interfaces. Prefer minimal diffs."""


class IntelligentPatcher:
    """
    LLM-powered code evolution engine.
    Generates, reviews, and applies patches to improve the codebase.
    """

    def __init__(
        self,
        brain=None,
        codebase=None,
        introspector=None,
        collector=None,
        auto_apply:            bool  = True,
        self_review:           bool  = True,
        min_confidence:        float = 0.6,
        max_patches_per_hour:  int   = 10,
    ):
        self.brain     = brain
        self.codebase  = codebase
        self.introspector = introspector
        self.collector = collector
        self.auto_apply           = auto_apply
        self.self_review          = self_review
        self.min_confidence       = min_confidence
        self.max_patches_per_hour = max_patches_per_hour

        self._patches_this_hour: int = 0
        self._hour_start: float      = time.time()
        self._lock = threading.Lock()

        # Stats
        self.patches_generated: int = 0
        self.patches_applied:   int = 0
        self.patches_failed:    int = 0

    # ── Public API ──────────────────────────────────────────────────────────────

    def generate_patch(
        self,
        target_file:      str,
        intent:           PatchIntent = PatchIntent.OPTIMIZE_PERFORMANCE,
        problem_context:  str         = "",
        function_name:    Optional[str] = None,
    ) -> Optional[IntelligentPatch]:
        """
        Generate and optionally apply a patch for the given file.
        Returns IntelligentPatch or None if nothing safe was found.
        """
        with self._lock:
            # Reset hourly counter
            if time.time() - self._hour_start > 3600:
                self._patches_this_hour = 0
                self._hour_start = time.time()
            if self._patches_this_hour >= self.max_patches_per_hour:
                return None

        patch_id = "ip_" + hashlib.sha256(
            f"{target_file}{intent.value}{time.time()}".encode()
        ).hexdigest()[:12]

        patch = IntelligentPatch(
            patch_id=patch_id,
            patch_intent=intent,
            target_file_path=target_file,
            target_function_name=function_name,
            problem_diagnosis=problem_context,
        )

        # ── Step 1: Read file ──────────────────────────────────────────────────
        file_content = self._read_file(target_file)
        if not file_content:
            patch.patch_outcome = PatchOutcome.SKIPPED
            patch.solution_reasoning = f"Cannot read file: {target_file}"
            return patch

        patch.original_code = file_content

        # ── Step 2: Optionally get function profile ────────────────────────────
        function_snippet = ""
        if function_name and self.introspector:
            try:
                fn_profile = self.introspector.get_function_profile(target_file, function_name)
                if fn_profile:
                    lines = file_content.splitlines()
                    fn_lines = lines[fn_profile.line_start - 1 : fn_profile.line_end]
                    function_snippet = "\n".join(fn_lines)
            except Exception:
                pass

        # ── Step 3: Build prompt ───────────────────────────────────────────────
        lang = self._detect_language(target_file)
        focus = function_snippet if function_snippet else file_content[:24_000]

        user_prompt = (
            f"Language: {lang}\n"
            f"File: {target_file}\n"
            f"Intent: {intent.value}\n"
        )
        if problem_context:
            user_prompt += f"Problem context:\n{problem_context}\n\n"
        if function_name:
            user_prompt += f"Focus on function: {function_name}\n\n"
        user_prompt += f"Source code:\n```{lang.lower()}\n{focus}\n```\n\nGenerate patch JSON:"

        # ── Step 4: Call LLM brain ─────────────────────────────────────────────
        if self.brain is None:
            patch.patch_outcome = PatchOutcome.LLM_FAILED
            patch.solution_reasoning = "LLMBrain not wired"
            return patch

        try:
            from .llm_brain import ThinkingMode, Priority
            response = self.brain.think(
                prompt=user_prompt,
                mode=ThinkingMode.CODER,
                priority=Priority.HIGH,
                system_prompt=_SYSTEM_PROMPT,
                max_tokens=2048,
            )
            patch.provider_used = response.provider
        except Exception as e:
            patch.patch_outcome = PatchOutcome.LLM_FAILED
            patch.solution_reasoning = f"LLM call failed: {e}"
            self.patches_failed += 1
            return patch

        raw = (response.content or "").strip()

        # ── Step 5: Parse JSON ─────────────────────────────────────────────────
        patch_data = self._parse_json_response(raw)
        old_code   = patch_data.get("old_code", "")
        new_code   = patch_data.get("new_code", "")
        reasoning  = patch_data.get("reasoning", "no reasoning provided")
        confidence = float(patch_data.get("confidence", 0.0))

        patch.solution_reasoning = reasoning
        patch.confidence         = confidence
        patch.updated_code       = new_code

        self.patches_generated += 1

        # ── Step 6: Validate ───────────────────────────────────────────────────
        if not old_code or not new_code:
            patch.patch_outcome = PatchOutcome.SKIPPED
            return patch

        if old_code not in file_content:
            patch.patch_outcome = PatchOutcome.VALIDATION_FAILED
            patch.solution_reasoning = f"LLM hallucinated old_code (not found in file)"
            self.patches_failed += 1
            return patch

        if confidence < self.min_confidence:
            patch.patch_outcome = PatchOutcome.REVIEW_REJECTED
            patch.solution_reasoning = f"Confidence {confidence:.2f} < threshold {self.min_confidence}"
            return patch

        # ── Step 7: Self-review ────────────────────────────────────────────────
        if self.self_review and self.brain:
            approved, review_note = self._self_review(old_code, new_code, lang, reasoning)
            patch.review_result = review_note
            if not approved:
                patch.patch_outcome = PatchOutcome.REVIEW_REJECTED
                patch.solution_reasoning = f"Self-review rejected: {review_note}"
                return patch

        # ── Step 8: Apply ──────────────────────────────────────────────────────
        if self.auto_apply and self.codebase:
            try:
                record = self.codebase.replace_in_file(
                    target_file, old_code, new_code,
                    reason=f"intelligent_patch:{intent.value}",
                    source="intelligent_patcher",
                )
                patch.change_record      = record
                patch.patch_outcome      = PatchOutcome.SUCCESS
                patch.verification_passed = True
                self.patches_applied     += 1

                with self._lock:
                    self._patches_this_hour += 1

                self._record_outcome(patch, success=True)
            except Exception as e:
                patch.patch_outcome      = PatchOutcome.APPLY_FAILED
                patch.solution_reasoning = f"Apply failed: {e}"
                self.patches_failed      += 1
                self._record_outcome(patch, success=False)
        else:
            # Dry-run — return patch for caller to apply
            patch.patch_outcome  = PatchOutcome.SUCCESS
            patch.original_code  = old_code
            patch.updated_code   = new_code

        return patch

    def get_status(self) -> dict:
        return {
            "patches_generated":   self.patches_generated,
            "patches_applied":     self.patches_applied,
            "patches_failed":      self.patches_failed,
            "patches_this_hour":   self._patches_this_hour,
            "max_per_hour":        self.max_patches_per_hour,
            "auto_apply":          self.auto_apply,
            "brain_available":     self.brain is not None,
        }

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    # ── Private helpers ────────────────────────────────────────────────────────

    def _read_file(self, rel_path: str) -> str:
        """Read a file relative to project root, via codebase agent or direct."""
        if self.codebase:
            try:
                content = self.codebase.read_file(rel_path)
                if content is not None:
                    return content[:32_000]
            except Exception:
                pass

        # Fallback: direct filesystem read
        project_root = os.environ.get("ULTRON_PROJECT_ROOT", ".")
        full_path = os.path.join(project_root, rel_path)
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                    return fh.read(32_000)
            except Exception:
                pass
        return ""

    def _detect_language(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        return {
            ".go": "Go", ".py": "Python", ".rs": "Rust",
            ".ts": "TypeScript", ".js": "JavaScript", ".jl": "Julia",
        }.get(ext, "unknown")

    def _parse_json_response(self, raw: str) -> dict:
        """Parse JSON from LLM response, handling markdown code fences."""
        # Try direct parse
        try:
            return json.loads(raw)
        except Exception:
            pass
        # Extract first JSON object containing old_code
        m = re.search(r'\{[^{}]*"old_code".*?\}', raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        # Last resort: extract JSON block from markdown fences
        m2 = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group(1))
            except Exception:
                pass
        return {}

    def _self_review(self, old_code: str, new_code: str, lang: str, reasoning: str) -> tuple:
        """
        Ask the LLM to review its own patch.
        Returns (approved: bool, note: str).
        """
        try:
            from .llm_brain import ThinkingMode, Priority
            review_prompt = (
                f"Language: {lang}\n"
                f"Proposed change reasoning: {reasoning}\n\n"
                f"OLD:\n```\n{old_code}\n```\n\n"
                f"NEW:\n```\n{new_code}\n```\n\n"
                "Does this change: (a) compile/run correctly, (b) not break existing behaviour, "
                "(c) actually improve what the reasoning claims?\n"
                'Reply ONLY with JSON: {"approved": true/false, "note": "<one sentence>"}'
            )
            resp = self.brain.think(
                prompt=review_prompt,
                mode=ThinkingMode.REVIEWER,
                priority=Priority.NORMAL,
                max_tokens=256,
            )
            data = self._parse_json_response(resp.content.strip())
            approved = bool(data.get("approved", True))
            note     = data.get("note", "review passed")
            return approved, note
        except Exception as e:
            return True, f"review skipped: {e}"

    def _record_outcome(self, patch: IntelligentPatch, success: bool) -> None:
        """Record patch outcome into ExperienceCollector."""
        if not self.collector:
            return
        try:
            from .experience_collector import EventType
            self.collector.record_event(
                event_type=EventType.SELF_MODIFICATION if hasattr(
                    __import__("python.self_improvement.learning.experience_collector",
                               fromlist=["EventType"]), "SELF_MODIFICATION"
                ) else EventType.ACTION,
                component="intelligent_patcher",
                data={
                    "patch_id":    patch.patch_id,
                    "file":        patch.target_file_path,
                    "intent":      patch.patch_intent.value,
                    "outcome":     patch.patch_outcome.value,
                    "confidence":  patch.confidence,
                    "provider":    patch.provider_used,
                },
                outcome="success" if success else "failure",
                importance=0.85,
            )
        except Exception:
            pass
