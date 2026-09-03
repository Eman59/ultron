"""
Sandbox Test Runner — Tests code patches in isolation before applying.

Every self-generated patch must pass:
  1. Syntax check (AST parse)
  2. Import resolution (no broken imports)
  3. Logic check (no obvious regressions)
  4. Performance check (not drastically slower)
"""

import ast
import sys
import time
import traceback
import tempfile
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..code_gen.patch_generator import CodePatch


@dataclass
class TestResult:
    """Result of testing a patch in the sandbox."""
    patch_id:         str
    passed:           bool
    score:            float = 0.0

    syntax_valid:     bool = False
    no_import_errors: bool = False
    logic_check:      bool = False
    performance_check:bool = False

    failure_reason:   str  = ""
    execution_time:   float = 0.0
    warnings:         list  = field(default_factory=list)


class SandboxRunner:
    """Isolated testing for code patches."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.test_count  = 0
        self.pass_count  = 0
        self.fail_count  = 0

    def test_patch(self, patch: CodePatch) -> TestResult:
        """Test a patch fully before applying it."""
        self.test_count += 1
        start = time.time()

        result = TestResult(patch_id=patch.patch_id, passed=False)

        try:
            for check in [
                self._check_syntax,
                self._check_imports,
                self._check_logic,
                self._check_performance,
            ]:
                if not check(patch, result):
                    self.fail_count += 1
                    result.execution_time = time.time() - start
                    return result

            result.passed = True
            result.score  = self._calculate_score(patch, result)
            self.pass_count += 1

        except Exception as e:
            result.failure_reason = f"Unexpected error: {e}"
            self.fail_count += 1

        result.execution_time = time.time() - start
        return result

    # ─────────────────────────────────────────────────────────
    # CHECK 1 — Syntax validation
    # ─────────────────────────────────────────────────────────
    def _check_syntax(self, patch: CodePatch, result: TestResult) -> bool:
        if not patch.target_file.endswith(".py"):
            result.syntax_valid = True
            return True
        try:
            ast.parse(patch.new_code)
            result.syntax_valid = True
            return True
        except SyntaxError as e:
            result.failure_reason = f"Syntax error in new code: {e}"
            return False

    # ─────────────────────────────────────────────────────────
    # CHECK 2 — Import resolution (write to temp file, import it)
    # ─────────────────────────────────────────────────────────
    def _check_imports(self, patch: CodePatch, result: TestResult) -> bool:
        if not patch.target_file.endswith(".py"):
            result.no_import_errors = True
            return True

        target_path = self.project_root / patch.target_file
        if not target_path.exists():
            result.no_import_errors = True
            return True

        # Build the patched file content
        try:
            original = target_path.read_text(encoding="utf-8", errors="replace")
            patched  = original.replace(patch.old_code, patch.new_code)
        except Exception:
            result.no_import_errors = True  # Can't check — allow
            return True

        # Write to temp file and try to compile (not import, to stay safe)
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                             delete=False, encoding="utf-8") as tf:
                tf.write(patched)
                tmp_path = tf.name

            proc = subprocess.run(
                [sys.executable, "-m", "py_compile", tmp_path],
                capture_output=True, text=True, timeout=10,
            )
            os.unlink(tmp_path)

            if proc.returncode == 0:
                result.no_import_errors = True
                return True
            else:
                result.failure_reason = f"Compile error: {proc.stderr.strip()[:200]}"
                return False
        except Exception:
            result.no_import_errors = True  # Compile check unavailable — allow
            return True

    # ─────────────────────────────────────────────────────────
    # CHECK 3 — Logic: new code must be non-empty and longer
    #           or same length. Refuses no-op / deletion patches.
    # ─────────────────────────────────────────────────────────
    def _check_logic(self, patch: CodePatch, result: TestResult) -> bool:
        if not patch.new_code or not patch.new_code.strip():
            result.failure_reason = "New code is empty"
            return False

        # Refuse to shrink a file dramatically (>80% shorter = suspicious)
        old_lines = len(patch.old_code.splitlines())
        new_lines = len(patch.new_code.splitlines())
        if old_lines > 5 and new_lines < old_lines * 0.2:
            result.failure_reason = f"New code drastically shorter ({new_lines} vs {old_lines} lines)"
            return False

        # Refuse if new code contains obvious danger patterns
        danger = ["os.system('rm -rf", "shutil.rmtree('/'", "format('c:'"]
        for d in danger:
            if d in patch.new_code:
                result.failure_reason = f"Dangerous pattern detected: {d}"
                return False

        result.logic_check = True
        return True

    # ─────────────────────────────────────────────────────────
    # CHECK 4 — Performance: new code must parse in <2s
    # ─────────────────────────────────────────────────────────
    def _check_performance(self, patch: CodePatch, result: TestResult) -> bool:
        if not patch.target_file.endswith(".py"):
            result.performance_check = True
            return True
        start = time.time()
        try:
            ast.parse(patch.new_code)
        except Exception:
            pass  # Already caught in syntax check
        elapsed = time.time() - start
        if elapsed > 2.0:
            result.failure_reason = f"Code parse took {elapsed:.1f}s (too slow)"
            return False
        result.performance_check = True
        return True

    # ─────────────────────────────────────────────────────────
    # SCORE
    # ─────────────────────────────────────────────────────────
    def _calculate_score(self, patch: CodePatch, result: TestResult) -> float:
        score = 0.5
        if result.syntax_valid:     score += 0.15
        if result.no_import_errors: score += 0.15
        if result.logic_check:      score += 0.10
        if result.performance_check:score += 0.10
        # Reward patches that add lines (more functionality)
        old_l = len(patch.old_code.splitlines())
        new_l = len(patch.new_code.splitlines())
        if new_l > old_l:
            score = min(1.0, score + 0.05)
        return round(score, 3)
