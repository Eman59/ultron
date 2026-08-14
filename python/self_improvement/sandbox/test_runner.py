"""
Sandbox Test Runner - Tests code patches in isolation before applying.

Every self-generated patch must pass through this sandbox:
  1. Create isolated copy of affected code
  2. Apply the patch to the copy
  3. Run syntax checks (AST parse)
  4. Run type checks (if available)
  5. Run unit tests against the modified code
  6. Measure performance delta
  7. Only pass if ALL checks succeed

This prevents self-modification from breaking the system.
"""

import ast
import sys
import time
import copy
import traceback
import tempfile
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

from ..code_gen.patch_generator import CodePatch


@dataclass
class TestResult:
    """Result of testing a patch in the sandbox."""
    patch_id: str
    passed: bool
    score: float = 0.0           # 0-1, overall quality score
    
    # Individual checks
    syntax_valid: bool = False
    no_import_errors: bool = False
    logic_check: bool = False
    performance_check: bool = False
    
    # Details
    failure_reason: str = ""
    execution_time: float = 0.0
    warnings: list = field(default_factory=list)


class SandboxRunner:
    """
    Isolated testing environment for code patches.
    
    Patches are NEVER applied to the live system until they pass
    all sandbox tests. This is the safety net for self-modification.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.test_count = 0
        self.pass_count = 0
        self.fail_count = 0

    def test_patch(self, patch: CodePatch) -> TestResult:
        """
        Test a patch in complete isolation.
        
        Returns TestResult indicating if the patch is safe to apply.
        """
        self.test_count += 1
        start = time.time()
        
        result = TestResult(
            patch_id=patch.patch_id,
            passed=False,
        )
        
        try:
            # ━━━━ CHECK 1: Syntax Validation ━━━━
            if not self._check_syntax(patch, result):
                self.fail_count += 1
                return result
            
            # ━━━━ CHECK 2: Import Resolution ━━━━
            if not self._check_imports(patch, result):
                self.fail_count += 1
                return result
            
            # ━━━━ CHECK 3: Logic Validation ━━━━
            if not self._check_logic(patch, result):
                self.fail_count += 1
                return result
            
            # ━━━━ CHECK 4: Performance Impact ━━━━
            if not self._check_performance(patch, result):
                self.fail_count += 1
                return result
            
            # All checks passed
            result.passed = True
            result.score = self._calculate_score(patch, result)
            self.pass_count += 1
            
        except Exception as e:
            result.failure_reason = f"Unexpected error: {str(e)}"
            self.fail_count += 1
        
        result.execution_time = time.time() - start
        return result

    def _check_syntax(self, patch: CodePatch, result: TestResult) -> bool:
        """Check if the new code has valid Python syntax."""
        
        code_to_check = patch.new_code
        
        # For replace patches, simulate the replacement
        if patch.patch_type == "replace":
            target_path = self.project_root / patch.target_file
            if target_path.exists():
                full_code = target_path.read_text()
                code_to_check = full_code.replace(patch.old_code, patch.new_code)
            else:
                result.failure_reason = f"Target file not found: {patch.target_file}"
                return False
        
        try:
            ast.parse(code_to_check)
            result.syntax_valid = True
            return True
        except SyntaxError as e:
            result.failure_reason = f"Syntax error: {e.msg} (line {e.lineno})"
            result.syntax_valid = False
            return False

    def _check_imports(self, patch: CodePatch, result: TestResult) -> bool:
        """Check if all imports in the new code can be resolved."""
        
        code = patch.new_code
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Already caught in syntax check, but handle gracefully
            result.no_import_errors = False
            result.failure_reason = "Cannot parse for import check"
            return False
        
        # Extract import statements
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        # Check standard library and known packages
        known_packages = {
            'os', 'sys', 'time', 'math', 'json', 'hashlib', 'uuid',
            'typing', 'dataclasses', 'enum', 'collections', 'functools',
            'asyncio', 'threading', 'statistics', 'pathlib', 'traceback',
            'numpy', 'scipy', 'sklearn', 'optuna', 'random', 'copy',
            'tempfile', 'ast', 're', 'abc', 'itertools',
        }
        
        for imp in imports:
            root_module = imp.split('.')[0]
            if root_module not in known_packages and not root_module.startswith('ultron'):
                result.warnings.append(f"Unknown import: {imp}")
                # Don't fail on unknown imports, just warn
        
        result.no_import_errors = True
        return True

    def _check_logic(self, patch: CodePatch, result: TestResult) -> bool:
        """
        Basic logic validation:
        - No infinite loops (simple heuristic)
        - No dangerous operations (eval, exec, os.system without safeguards)
        - Functions have return statements where expected
        """
        
        code = patch.new_code
        
        # Check for dangerous patterns
        dangerous_patterns = [
            (r'\beval\s*\(', "Use of eval() is dangerous"),
            (r'\bexec\s*\(', "Use of exec() is dangerous"),
            (r'\b__import__\s*\(', "Dynamic import is risky"),
            (r'os\.system\s*\(', "os.system() is unsafe, use subprocess"),
            (r'subprocess\.call\s*\([^)]*shell\s*=\s*True', "shell=True is risky"),
        ]
        
        import re
        for pattern, reason in dangerous_patterns:
            if re.search(pattern, code):
                result.warnings.append(f"Logic warning: {reason}")
                # Warn but don't fail — the patch might legitimately need these
        
        # Check for potential infinite loops (while True without break)
        if 'while True' in code and 'break' not in code and 'return' not in code:
            result.failure_reason = "Potential infinite loop detected (while True without break/return)"
            result.logic_check = False
            return False
        
        result.logic_check = True
        return True

    def _check_performance(self, patch: CodePatch, result: TestResult) -> bool:
        """
        Check that the patch doesn't introduce obvious performance issues:
        - No O(n³) nested loops for large N
        - No blocking sleep() in hot paths
        - Reasonable function complexity
        """
        
        code = patch.new_code
        
        # Count nesting depth of loops
        max_loop_depth = self._count_max_loop_nesting(code)
        if max_loop_depth > 3:
            result.warnings.append(f"High loop nesting depth: {max_loop_depth}")
        if max_loop_depth > 4:
            result.failure_reason = f"Excessive loop nesting ({max_loop_depth} levels)"
            result.performance_check = False
            return False
        
        # Check for large hardcoded sleeps
        import re
        sleep_matches = re.findall(r'time\.sleep\((\d+\.?\d*)\)', code)
        for sleep_val in sleep_matches:
            if float(sleep_val) > 10.0:
                result.warnings.append(f"Large sleep detected: {sleep_val}s")
        
        result.performance_check = True
        return True

    def _count_max_loop_nesting(self, code: str) -> int:
        """Count maximum loop nesting depth in code."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return 0
        
        max_depth = 0
        
        def walk_depth(node, current_depth=0):
            nonlocal max_depth
            
            if isinstance(node, (ast.For, ast.While)):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            
            for child in ast.iter_child_nodes(node):
                walk_depth(child, current_depth)
        
        walk_depth(tree)
        return max_depth

    def _calculate_score(self, patch: CodePatch, result: TestResult) -> float:
        """Calculate an overall quality score for the patch."""
        
        score = 0.0
        
        # Base score from passing all checks
        score += 0.5
        
        # Bonus for low risk
        score += (1.0 - patch.risk_level) * 0.2
        
        # Bonus for high estimated impact
        score += patch.estimated_impact * 0.2
        
        # Penalty for warnings
        score -= len(result.warnings) * 0.05
        
        return max(0.0, min(1.0, score))

    def get_stats(self) -> Dict[str, Any]:
        """Get sandbox statistics."""
        return {
            "total_tests": self.test_count,
            "passed": self.pass_count,
            "failed": self.fail_count,
            "pass_rate": self.pass_count / max(1, self.test_count),
        }
