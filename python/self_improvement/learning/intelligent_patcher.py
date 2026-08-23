"""
Intelligent Patch Generator — LLM-Powered Code Evolution.

This replaces the old rule-based PatchGenerator with real AI reasoning.
Instead of pattern-matching templates, it:

  1. READS the target code and understands what it does
  2. ANALYZES the diagnosed problem in context
  3. REASONS about possible solutions
  4. GENERATES a complete, correct fix
  5. REVIEWS its own output for quality
  6. APPLIES the change through the codebase agent
  7. VERIFIES the change didn't break anything

The difference:
  OLD: "Function is slow" → add @lru_cache decorator (template)
  NEW: "Function is slow" → reads the code → understands the algorithm
       → realizes it's doing O(n²) nested iteration → rewrites with
       a hash map lookup → validates correctness → applies

This is the component that makes Ultron genuinely self-improving.
It doesn't just patch — it UNDERSTANDS and REDESIGNS.
"""

import time
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .llm_brain import LLMBrain, ThinkingMode, Priority, LLMResponse
from .codebase_agent import CodebaseAgent, ChangeRecord, ValidationResult
from .code_introspector import CodeIntrospector, FunctionProfile
from .experience_collector import ExperienceCollector, EventType


class PatchIntent(Enum):
    """What the patch is trying to accomplish."""
    FIX_BUG = "fix_bug"
    OPTIMIZE_PERFORMANCE = "optimize_performance"
    REDUCE_COMPLEXITY = "reduce_complexity"
    ADD_ERROR_HANDLING = "add_error_handling"
    IMPROVE_READABILITY = "improve_readability"
    ADD_FEATURE = "add_feature"
    REMOVE_DEAD_CODE = "remove_dead_code"
    REFACTOR = "refactor"
    ADD_CACHING = "add_caching"
    FIX_SECURITY = "fix_security"
    ADD_LOGGING = "add_logging"
    PARALLELIZE = "parallelize"


class PatchOutcome(Enum):
    """What happened when the patch was applied."""
    SUCCESS = "success"
    VALIDATION_FAILED = "validation_failed"
    REVIEW_REJECTED = "review_rejected"
    APPLY_FAILED = "apply_failed"
    VERIFY_FAILED = "verify_failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"


@dataclass
class IntelligentPatch:
    """A complete intelligent patch with full context."""
    id: str
    intent: PatchIntent
    target_file: str
    target_function: Optional[str] = None

    # The problem being solved
    diagnosis: str = ""
    severity: float = 0.0

    # LLM reasoning
    analysis: str = ""           # LLM's understanding of the problem
    reasoning: str = ""          # Why this solution was chosen
    generated_code: str = ""     # The new code
    review_result: str = ""      # Self-review outcome

    # Change details
    old_code: str = ""
    new_code: str = ""
    diff_summary: str = ""

    # Outcome
    outcome: PatchOutcome = PatchOutcome.SKIPPED
    change_record: Optional[ChangeRecord] = None
    verification_passed: bool = False

    # Metrics
    llm_tokens_used: int = 0

    def __post_init__(self):
        try:
            if not isinstance(self.id, str):
                raise TypeError("ID must be a string")
            if not isinstance(self.intent, PatchIntent):
                raise TypeError("Intent must be a PatchIntent enum")
            if not isinstance(self.target_file, str):
                raise TypeError("Target file must be a string")
            if self.target_function is not None and not isinstance(self.target_function, str):
                raise TypeError("Target function must be a string or None")
            if not isinstance(self.diagnosis, str):
                raise TypeError("Diagnosis must be a string")
            if not isinstance(self.severity, (int, float)):
                raise TypeError("Severity must be a number")
            if not isinstance(self.analysis, str):
                raise TypeError("Analysis must be a string")
            if not isinstance(self.reasoning, str):
                raise TypeError("Reasoning must be a string")
            if not isinstance(self.generated_code, str):
                raise TypeError("Generated code must be a string")
            if not isinstance(self.review_result, str):
                raise TypeError("Review result must be a string")
            if not isinstance(self.old_code, str):
                raise TypeError("Old code must be a string")
            if not isinstance(self.new_code, str):
                raise TypeError("New code must be a string")
            if not isinstance(self.diff_summary, str):
                raise TypeError("Diff summary must be a string")
            if not isinstance(self.outcome, PatchOutcome):
                raise TypeError("Outcome must be a PatchOutcome enum")
            if self.change_record is not None and not isinstance(self.change_record, ChangeRecord):
                raise TypeError("Change record must be a ChangeRecord or None")
            if not isinstance(self.verification_passed, bool):
                raise TypeError("Verification passed must be a boolean")
            if not isinstance(self.llm_tokens_used, int):
                raise TypeError("LLM tokens used must be an integer")
        except TypeError as e:
            print(f"Error initializing IntelligentPatch: {e}")

    def apply_patch(self, codebase_agent: CodebaseAgent) -> None:
        try:
            change_record = codebase_agent.apply_change(self.old_code, self.new_code)
            self.change_record = change_record
        except Exception as e:
            print(f"Error applying patch: {e}")
            self.outcome = PatchOutcome.APPLY_FAILED

    def verify_patch(self, codebase_agent: CodebaseAgent) -> None:
        try:
            verification_result = codebase_agent.verify_change(self.change_record)
            self.verification_passed = verification_result
        except Exception as e:
            print(f"Error verifying patch: {e}")
            self.outcome = PatchOutcome.VERIFY_FAILED

    def review_patch(self, llm_brain: LLMBrain) -> None:
        try:
            review_result = llm_brain.review_code(self.generated_code)
            self.review_result = review_result
        except Exception as e:
            print(f"Error reviewing patch: {e}")
            self.outcome = PatchOutcome.REVIEW_REJECTED