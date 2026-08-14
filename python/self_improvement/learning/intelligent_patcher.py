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
    llm_cost_usd: float = 0.0
    generation_time_ms: float = 0.0
    total_time_ms: float = 0.0

    # Metadata
    created_at: float = field(default_factory=time.time)
    provider_used: str = ""
    model_used: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "intent": self.intent.value,
            "target_file": self.target_file,
            "target_function": self.target_function,
            "diagnosis": self.diagnosis,
            "outcome": self.outcome.value,
            "confidence": self.confidence,
            "tokens_used": self.llm_tokens_used,
            "cost_usd": self.llm_cost_usd,
            "time_ms": self.total_time_ms,
            "verification_passed": self.verification_passed,
        }


class IntelligentPatcher:
    """
    LLM-powered code improvement engine.

    Connects the LLM brain to the codebase agent to create a system
    that can genuinely understand, reason about, and improve code.
    """

    def __init__(self,
                 brain: LLMBrain,
                 codebase: CodebaseAgent,
                 introspector: CodeIntrospector,
                 collector: ExperienceCollector,
                 auto_apply: bool = True,
                 self_review: bool = True,
                 min_confidence: float = 0.6,
                 max_patches_per_hour: int = 10):
        """
        Args:
            brain: The LLM intelligence engine
            codebase: Filesystem agent for reading/writing code
            introspector: Code structure knowledge
            collector: Experience reporting
            auto_apply: Automatically apply patches that pass review
            self_review: Have the LLM review its own patches before applying
            min_confidence: Minimum confidence to apply a patch
            max_patches_per_hour: Rate limit
        """
        self.brain = brain
        self.codebase = codebase
        self.introspector = introspector
        self.collector = collector
        self.auto_apply = auto_apply
        self.self_review = self_review
        self.min_confidence = min_confidence
        self.max_patches_per_hour = max_patches_per_hour

        # History
        self._patches: List[IntelligentPatch] = []
        self._patches_this_hour = 0
        self._hour_start = time.time()

        # Stats
        self._total_generated = 0
        self._total_applied = 0
        self._total_rejected = 0
        self._total_rolled_back = 0

    # ═══════════════════════════════════════════════════════════════
    # MAIN API — Generate intelligent patches
    # ═══════════════════════════════════════════════════════════════

    def improve_function(self, file_path: str, function_name: str,
                         intent: PatchIntent = PatchIntent.OPTIMIZE_PERFORMANCE,
                         additional_context: str = "") -> IntelligentPatch:
        """
        Intelligently improve a specific function.

        Reads the function, understands what it does, generates an
        improved version, reviews it, and optionally applies it.
        """
        start = time.time()
        patch_id = self._gen_id()

        patch = IntelligentPatch(
            id=patch_id,
            intent=intent,
            target_file=file_path,
            target_function=function_name,
        )

        # Rate limit check
        if not self._can_patch():
            patch.outcome = PatchOutcome.SKIPPED
            patch.reasoning = "Rate limit exceeded"
            return patch

        # Step 1: READ the target code
        code = self.codebase.read_function(file_path, function_name)
        if not code:
            # Try reading the whole file
            code = self.codebase.read_file(file_path)
            if not code:
                patch.outcome = PatchOutcome.APPLY_FAILED
                patch.reasoning = f"Could not read {file_path}:{function_name}"
                return patch

        patch.old_code = code

        # Step 2: Gather context (imports, related functions, callers)
        context = self._gather_context(file_path, function_name)

        # Step 3: ANALYZE the problem
        analysis_response = self.brain.analyze_code(
            code=code,
            filename=file_path,
            question=f"Analyze this function for {intent.value} opportunities. "
                     f"Specific concern: {additional_context}" if additional_context
                     else f"Analyze for {intent.value} opportunities.",
        )
        patch.analysis = analysis_response.content
        patch.llm_tokens_used += analysis_response.tokens_in + analysis_response.tokens_out
        patch.llm_cost_usd += analysis_response.cost_usd

        # Step 4: GENERATE improved code
        improvement_response = self._generate_improvement(
            code, file_path, function_name, intent, context, patch.analysis
        )
        patch.reasoning = improvement_response.reasoning
        patch.generated_code = improvement_response.content
        patch.llm_tokens_used += improvement_response.tokens_in + improvement_response.tokens_out
        patch.llm_cost_usd += improvement_response.cost_usd
        patch.provider_used = improvement_response.provider_used.value
        patch.model_used = improvement_response.model_used
        patch.generation_time_ms = improvement_response.latency_ms

        if not improvement_response.success or not improvement_response.code_blocks:
            patch.outcome = PatchOutcome.VALIDATION_FAILED
            patch.reasoning = f"LLM failed to generate code: {improvement_response.error}"
            self._record_patch(patch)
            return patch

        # Extract the code from the response
        new_code = improvement_response.code_blocks[0] if improvement_response.code_blocks else ""
        if not new_code:
            new_code = self._extract_code_from_response(improvement_response.content)

        if not new_code or new_code.strip() == code.strip():
            patch.outcome = PatchOutcome.SKIPPED
            patch.reasoning = "Generated code is identical to original"
            self._record_patch(patch)
            return patch

        patch.new_code = new_code

        # Step 5: SELF-REVIEW
        if self.self_review:
            review_result = self._self_review(code, new_code, file_path, intent)
            patch.review_result = review_result.content
            patch.llm_tokens_used += review_result.tokens_in + review_result.tokens_out
            patch.llm_cost_usd += review_result.cost_usd

            # Parse review decision
            confidence = self._parse_review_confidence(review_result.content)
            patch.confidence = confidence

            if confidence < self.min_confidence:
                patch.outcome = PatchOutcome.REVIEW_REJECTED
                patch.reasoning = f"Self-review confidence too low: {confidence:.2f}"
                self._total_rejected += 1
                self._record_patch(patch)
                return patch
        else:
            patch.confidence = 0.7  # Default without review

        # Step 6: APPLY
        if self.auto_apply:
            apply_result = self._apply_patch(patch, file_path, code, new_code)
            if not apply_result:
                patch.outcome = PatchOutcome.APPLY_FAILED
                self._record_patch(patch)
                return patch

            patch.change_record = apply_result

            # Step 7: VERIFY
            verification = self.codebase.validate_file(file_path)
            if verification == ValidationResult.PASSED:
                patch.verification_passed = True
                patch.outcome = PatchOutcome.SUCCESS
                self._total_applied += 1
            else:
                # Roll back
                if apply_result:
                    self.codebase.rollback_change(apply_result.id)
                patch.outcome = PatchOutcome.ROLLED_BACK
                patch.verification_passed = False
                self._total_rolled_back += 1
        else:
            patch.outcome = PatchOutcome.SUCCESS  # Generated but not applied

        patch.total_time_ms = (time.time() - start) * 1000
        self._record_patch(patch)
        self._total_generated += 1

        return patch

    def fix_diagnosed_issue(self, diagnosis: Dict[str, Any]) -> IntelligentPatch:
        """
        Fix an issue identified by the self-improvement system.

        Takes a diagnosis from the performance monitor and generates
        a targeted fix using LLM reasoning.
        """
        component = diagnosis.get("component", "")
        issue_type = diagnosis.get("type", "")
        description = diagnosis.get("description", "")
        severity = diagnosis.get("severity", 0.5)

        # Map diagnosis type to patch intent
        intent_map = {
            "underperformance": PatchIntent.OPTIMIZE_PERFORMANCE,
            "recurring_failure": PatchIntent.FIX_BUG,
            "latency_bottleneck": PatchIntent.OPTIMIZE_PERFORMANCE,
            "inefficiency": PatchIntent.REDUCE_COMPLEXITY,
            "high_complexity": PatchIntent.REDUCE_COMPLEXITY,
            "dead_code": PatchIntent.REMOVE_DEAD_CODE,
            "missing_error_handling": PatchIntent.ADD_ERROR_HANDLING,
            "security_issue": PatchIntent.FIX_SECURITY,
        }
        intent = intent_map.get(issue_type, PatchIntent.OPTIMIZE_PERFORMANCE)

        # Find the source file for this component
        file_path = self._find_component_file(component)
        if not file_path:
            patch = IntelligentPatch(
                id=self._gen_id(),
                intent=intent,
                target_file="",
                diagnosis=description,
                severity=severity,
                outcome=PatchOutcome.SKIPPED,
                reasoning=f"Could not find source file for component: {component}",
            )
            return patch

        # Find the most relevant function to fix
        target_function = self._find_target_function(file_path, description)

        return self.improve_function(
            file_path=file_path,
            function_name=target_function or "",
            intent=intent,
            additional_context=f"Diagnosis: {description} (severity: {severity})",
        )

    def improve_hotspot(self, function_profile: FunctionProfile) -> IntelligentPatch:
        """Improve a complexity hotspot identified by the introspector."""
        return self.improve_function(
            file_path=function_profile.file_path,
            function_name=function_profile.name,
            intent=PatchIntent.REDUCE_COMPLEXITY,
            additional_context=f"Cyclomatic complexity: {function_profile.cyclomatic_complexity}, "
                              f"Cognitive complexity: {function_profile.cognitive_complexity}, "
                              f"Nesting depth: {function_profile.nesting_depth}",
        )

    def generate_new_feature(self, description: str, target_file: str,
                             language: str = "python") -> IntelligentPatch:
        """Generate entirely new code from a description."""
        start = time.time()
        patch_id = self._gen_id()

        patch = IntelligentPatch(
            id=patch_id,
            intent=PatchIntent.ADD_FEATURE,
            target_file=target_file,
            diagnosis=description,
        )

        # Read existing file for context
        existing = self.codebase.read_file(target_file) or ""
        
        # Generate
        response = self.brain.generate_code(
            description=description,
            language=language,
            context=existing[-3000:] if existing else "",  # Last 3000 chars for context
            target_file=target_file,
        )

        patch.llm_tokens_used = response.tokens_in + response.tokens_out
        patch.llm_cost_usd = response.cost_usd
        patch.provider_used = response.provider_used.value
        patch.model_used = response.model_used

        if not response.success:
            patch.outcome = PatchOutcome.VALIDATION_FAILED
            patch.reasoning = response.error
            self._record_patch(patch)
            return patch

        new_code = response.code_blocks[0] if response.code_blocks else response.content
        patch.new_code = new_code

        # Apply
        if self.auto_apply and new_code:
            if existing:
                # Append to existing file
                record = self.codebase.append_to_file(
                    target_file, "\n\n" + new_code,
                    reason=f"New feature: {description[:50]}",
                    source="intelligent_patcher",
                )
            else:
                # Create new file
                record = self.codebase.write_file(
                    target_file, new_code,
                    reason=f"New feature: {description[:50]}",
                    source="intelligent_patcher",
                )
            patch.change_record = record
            patch.outcome = PatchOutcome.SUCCESS
            self._total_applied += 1
        else:
            patch.outcome = PatchOutcome.SUCCESS

        patch.total_time_ms = (time.time() - start) * 1000
        self._record_patch(patch)
        return patch

    # ═══════════════════════════════════════════════════════════════
    # INTERNAL — LLM interaction helpers
    # ═══════════════════════════════════════════════════════════════

    def _generate_improvement(self, code: str, file_path: str,
                              function_name: str, intent: PatchIntent,
                              context: str, analysis: str) -> LLMResponse:
        """Ask the LLM to generate improved code."""
        prompt = f"""You are improving code in `{file_path}`.
Target function: `{function_name}`
Improvement goal: {intent.value}

ANALYSIS OF CURRENT CODE:
{analysis}

CURRENT CODE:
```
{code}
```

{f"SURROUNDING CONTEXT:{chr(10)}{context}" if context else ""}

INSTRUCTIONS:
1. Write the COMPLETE improved function (not a diff)
2. Keep the same function signature unless there's a very good reason to change it
3. Include all imports needed at the top
4. The code must be syntactically correct and complete
5. Add a brief comment explaining what was improved

Write ONLY the improved code in a code block. No explanation outside the block."""

        return self.brain.think(
            prompt=prompt,
            mode=ThinkingMode.CODER,
            priority=Priority.NORMAL,
            temperature=0.2,
            max_tokens=4096,
        )

    def _self_review(self, old_code: str, new_code: str,
                     file_path: str, intent: PatchIntent) -> LLMResponse:
        """Have the LLM review its own generated patch."""
        prompt = f"""Review this code change for `{file_path}`.
Intent: {intent.value}

BEFORE:
```
{old_code}
```

AFTER:
```
{new_code}
```

Rate this change on these criteria (each 0-10):
1. CORRECTNESS: Does the new code preserve all original behavior?
2. IMPROVEMENT: Does it actually achieve the stated intent ({intent.value})?
3. SAFETY: Could this break anything? Any edge cases?
4. READABILITY: Is the new code clear and maintainable?

Then give an OVERALL CONFIDENCE score from 0.0 to 1.0.
Format: CONFIDENCE: 0.XX

If confidence < 0.6, explain what's wrong and say REJECT.
If confidence >= 0.6, say APPROVE."""

        return self.brain.think(
            prompt=prompt,
            mode=ThinkingMode.REVIEWER,
            priority=Priority.NORMAL,
            temperature=0.1,
        )

    def _parse_review_confidence(self, review_text: str) -> float:
        """Extract confidence score from review text."""
        import re
        
        # Look for "CONFIDENCE: 0.XX" pattern
        match = re.search(r'CONFIDENCE:\s*([\d.]+)', review_text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        # Fallback: look for APPROVE/REJECT
        if "APPROVE" in review_text.upper():
            return 0.75
        if "REJECT" in review_text.upper():
            return 0.3

        return 0.5  # Uncertain

    def _gather_context(self, file_path: str, function_name: str) -> str:
        """Gather surrounding context for better code generation."""
        parts = []

        # Get imports from the file
        content = self.codebase.read_file(file_path)
        if content:
            lines = content.splitlines()
            imports = [l for l in lines[:50] if l.startswith(('import ', 'from '))]
            if imports:
                parts.append("IMPORTS:\n" + "\n".join(imports))

        # Find callers of this function
        if function_name:
            usages = self.codebase.find_usages(function_name)
            if usages:
                callers = [f"  {u.file_path}:{u.line_number}: {u.line_content.strip()}"
                          for u in usages[:5]]
                parts.append("CALLERS:\n" + "\n".join(callers))

        return "\n\n".join(parts) if parts else ""

    def _apply_patch(self, patch: IntelligentPatch, file_path: str,
                     old_code: str, new_code: str) -> Optional[ChangeRecord]:
        """Apply a patch through the codebase agent."""
        # Try replacing the specific function
        record = self.codebase.replace_in_file(
            file_path,
            old_code,
            new_code,
            reason=f"Intelligent patch: {patch.intent.value} for {patch.target_function}",
            source="intelligent_patcher",
        )

        # Check if the replacement was successful
        if "FAILED" in record.description:
            return None

        return record

    def _find_component_file(self, component: str) -> Optional[str]:
        """Find the source file for a component name."""
        # Try direct lookup via introspector
        profiles = self.introspector.get_component_profiles()
        for name, profile in profiles.items():
            if component.lower() in name.lower():
                # Find a .py file in this component
                results = self.codebase.search(
                    f"class.*{component}|def.*{component}",
                    file_extensions={'.py', '.go', '.rs'},
                    regex=True,
                    max_results=1,
                )
                if results:
                    return results[0].file_path

        # Fallback: search by name
        results = self.codebase.find_definitions(component)
        if results:
            return results[0].file_path

        return None

    def _find_target_function(self, file_path: str, description: str) -> Optional[str]:
        """Find the most relevant function in a file based on description."""
        # Ask the LLM to identify the right function
        content = self.codebase.read_file(file_path)
        if not content:
            return None

        # Extract function names
        import re
        if file_path.endswith('.py'):
            funcs = re.findall(r'def\s+(\w+)\s*\(', content)
        elif file_path.endswith('.go'):
            funcs = re.findall(r'func\s+(?:\([^)]*\)\s+)?(\w+)\s*\(', content)
        elif file_path.endswith('.rs'):
            funcs = re.findall(r'fn\s+(\w+)', content)
        else:
            return None

        if not funcs:
            return None
        if len(funcs) == 1:
            return funcs[0]

        # Use keywords from description to find best match
        desc_words = set(description.lower().split())
        best_match = None
        best_score = 0

        for func in funcs:
            func_words = set(func.lower().replace('_', ' ').split())
            overlap = len(desc_words & func_words)
            if overlap > best_score:
                best_score = overlap
                best_match = func

        return best_match or funcs[0]

    def _extract_code_from_response(self, response: str) -> str:
        """Extract code from a response that might not have proper blocks."""
        lines = response.splitlines()
        code_lines = []
        in_code = False

        for line in lines:
            if line.strip().startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                code_lines.append(line)

        if code_lines:
            return '\n'.join(code_lines)

        # If no code blocks, return the whole thing (might be raw code)
        return response

    # ═══════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════

    def _can_patch(self) -> bool:
        """Check rate limit."""
        now = time.time()
        if now - self._hour_start > 3600:
            self._patches_this_hour = 0
            self._hour_start = now
        return self._patches_this_hour < self.max_patches_per_hour

    def _gen_id(self) -> str:
        return hashlib.md5(f"patch:{time.time_ns()}".encode()).hexdigest()[:14]

    def _record_patch(self, patch: IntelligentPatch):
        """Record patch and emit to experience collector."""
        self._patches.append(patch)
        self._patches_this_hour += 1

        # Report to learning system
        event_type = (EventType.PATCH_APPLIED if patch.outcome == PatchOutcome.SUCCESS
                     else EventType.PATCH_REVERTED if patch.outcome == PatchOutcome.ROLLED_BACK
                     else EventType.PATCH_GENERATED)

        outcome = None
        if patch.outcome == PatchOutcome.SUCCESS:
            outcome = patch.confidence
        elif patch.outcome in (PatchOutcome.ROLLED_BACK, PatchOutcome.REVIEW_REJECTED):
            outcome = -0.3

        self.collector.record_event(
            event_type=event_type,
            component="intelligent_patcher",
            data=patch.to_dict(),
            outcome=outcome,
            tags={"patch", patch.intent.value, patch.outcome.value},
        )

    # ═══════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════

    def get_stats(self) -> Dict[str, Any]:
        """Get patcher statistics."""
        return {
            "total_generated": self._total_generated,
            "total_applied": self._total_applied,
            "total_rejected": self._total_rejected,
            "total_rolled_back": self._total_rolled_back,
            "success_rate": self._total_applied / max(1, self._total_generated),
            "patches_this_hour": self._patches_this_hour,
            "max_per_hour": self.max_patches_per_hour,
            "brain_status": self.brain.get_status(),
            "recent_patches": [p.to_dict() for p in self._patches[-10:]],
        }
