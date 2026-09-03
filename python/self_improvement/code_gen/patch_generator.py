"""
Patch Generator — Generates real LLM-powered code improvements.

Given a diagnosis (slow component, recurring error, etc.) it uses the
Ultron LLM brain to generate an actual code patch, then validates it.
"""

import ast
import hashlib
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CodePatch:
    """A generated code modification."""
    patch_id:         str
    name:             str
    description:      str
    target_file:      str
    patch_type:       str        # "replace", "append", "new_file", "full_rewrite"
    old_code:         str = ""   # Code to replace (for "replace" type)
    new_code:         str = ""   # New code
    diagnosis_ref:    str = ""
    strategy:         str = ""
    estimated_impact: float = 0.0
    risk_level:       float = 0.0
    created_at:       float = field(default_factory=time.time)


class PatchGenerator:
    """Generates code patches using the LLM brain."""

    # Files that are good candidates for auto-improvement
    # NOTE: real_brain.py is excluded — it contains active LLM logic that
    # can cause import errors if modified incorrectly by the auto-patcher
    TARGET_FILES = [
        "python/interface/action_engine.py",
        "python/self_improvement/core/performance_monitor.py",
        "python/self_improvement/core/improvement_loop.py",
        "python/self_improvement/code_gen/patch_generator.py",
    ]

    def __init__(self, project_root: str):
        if not project_root:
            raise ValueError("Project root cannot be empty")
        self.project_root = Path(project_root)
        self.generated_count = 0

    def generate_patch(self, diagnosis: Dict[str, Any]) -> Optional[CodePatch]:
        """Generate a patch for a given diagnosis using the LLM."""
        if not diagnosis:
            return None

        diagnosis_type = diagnosis.get("type", "")
        component      = diagnosis.get("component", "")
        description    = diagnosis.get("description", "")
        severity       = diagnosis.get("severity", 0.5)

        # Map component name to real file
        target_file = self._find_target_file(component)
        if not target_file:
            return None

        full_path = self.project_root / target_file
        if not full_path.exists():
            return None

        try:
            current_code = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        # Build improvement prompt based on diagnosis type
        strategy_map = {
            "underperformance":   "optimize for speed and efficiency",
            "recurring_failure":  "add robust error handling and retry logic",
            "latency_bottleneck": "reduce latency with caching or async improvements",
            "inefficiency":       "reduce resource usage and improve throughput",
        }
        strategy_desc = strategy_map.get(diagnosis_type, "improve code quality")

        prompt = (
            f"You are improving Ultron's own source code. File: {target_file}\n"
            f"Issue: {description}\n"
            f"Strategy: {strategy_desc}\n\n"
            f"Current code (first 2000 chars):\n```python\n{current_code[:2000]}\n```\n\n"
            f"Generate ONE specific improvement to this file.\n"
            f"Output ONLY in this exact format:\n"
            f"OLD:\n```\nexact_old_code_snippet\n```\n"
            f"NEW:\n```\nimproved_replacement_code\n```\n"
            f"REASON: one sentence why this improves it.\n\n"
            f"Rules:\n"
            f"- OLD must be an exact verbatim substring of the current code\n"
            f"- NEW must be valid Python\n"
            f"- Change at most 20 lines\n"
            f"- Do not change function signatures or imports unless necessary"
        )

        try:
            llm_response = self._call_llm(prompt)
            if not llm_response:
                return None
            return self._parse_llm_patch(llm_response, target_file, current_code, diagnosis_type, severity)
        except Exception:
            return None

    def _find_target_file(self, component: str) -> Optional[str]:
        """Map a component name to a real file path."""
        comp = component.lower()
        mapping = {
            "interface":      "python/interface/real_brain.py",
            "brain":          "python/interface/real_brain.py",
            "action":         "python/interface/action_engine.py",
            "action_engine":  "python/interface/action_engine.py",
            "monitor":        "python/self_improvement/core/performance_monitor.py",
            "improvement":    "python/self_improvement/core/improvement_loop.py",
            "system":         "python/interface/real_brain.py",
        }
        # Direct match
        for key, path in mapping.items():
            if key in comp:
                return path
        # Random target file (for generic improvements)
        import random
        return random.choice(self.TARGET_FILES)

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call Ultron's brain to generate a patch."""
        try:
            _root = str(self.project_root)
            if _root not in sys.path:
                sys.path.insert(0, _root)
            # Load env
            env_path = self.project_root / ".env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
            from python.interface.real_brain import call_brain
            return call_brain(prompt, max_tokens=600)
        except Exception:
            return None

    def _parse_llm_patch(
        self,
        response: str,
        target_file: str,
        current_code: str,
        diagnosis_type: str,
        severity: float,
    ) -> Optional[CodePatch]:
        """Parse the LLM's OLD/NEW format into a CodePatch."""

        # Extract OLD block
        old_match = re.search(r'OLD:\s*```(?:python)?\s*(.*?)\s*```', response, re.DOTALL)
        new_match = re.search(r'NEW:\s*```(?:python)?\s*(.*?)\s*```', response, re.DOTALL)
        reason_match = re.search(r'REASON:\s*(.+)', response)

        if not old_match or not new_match:
            return None

        old_code = old_match.group(1).strip()
        new_code = new_match.group(1).strip()
        reason   = reason_match.group(1).strip() if reason_match else "LLM improvement"

        # Verify old_code exists verbatim in current file
        if old_code not in current_code:
            # Try stripping trailing whitespace differences
            old_normalized = "\n".join(l.rstrip() for l in old_code.splitlines())
            curr_normalized = "\n".join(l.rstrip() for l in current_code.splitlines())
            if old_normalized not in curr_normalized:
                return None

        # Validate new_code is syntactically valid Python
        if target_file.endswith(".py"):
            try:
                ast.parse(new_code)
            except SyntaxError:
                return None

        patch_id = hashlib.md5(f"{target_file}:{new_code[:50]}:{time.time()}".encode()).hexdigest()[:12]
        self.generated_count += 1

        return CodePatch(
            patch_id=patch_id,
            name=f"{diagnosis_type}_{target_file.split('/')[-1]}",
            description=reason,
            target_file=target_file,
            patch_type="replace",
            old_code=old_code,
            new_code=new_code,
            diagnosis_ref=diagnosis_type,
            strategy=diagnosis_type,
            estimated_impact=severity * 0.5,
            risk_level=0.3,
        )
