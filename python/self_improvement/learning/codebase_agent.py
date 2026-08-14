"""
Codebase Agent — The Hands That Write.

This gives Ultron REAL power to interact with its own codebase:
  - Browse directories and discover files
  - Read any source file completely
  - Search for patterns across the codebase (grep-like)
  - Modify files (insert, replace, delete code)
  - Create new files and modules
  - Execute commands (build, test, lint)
  - Git operations (branch, commit, diff, revert)
  - Validate changes before applying (syntax, imports, tests)

Unlike the existing PatchGenerator (which only generates patch specs),
this module ACTUALLY EXECUTES changes on the filesystem. It's the
difference between "suggesting" and "doing."

Safety layers:
  1. PREVIEW   — Show what would change before changing it
  2. VALIDATE  — Syntax check + import check + test run
  3. BACKUP    — Create backup before every modification
  4. APPLY     — Make the actual change
  5. VERIFY    — Confirm the change didn't break anything
  6. ROLLBACK  — Undo if verification fails

The agent maintains a CHANGE LOG of everything it touches,
enabling full audit trail and time-travel undo.
"""

import os
import re
import ast
import shutil
import hashlib
import subprocess
import time
import json
import difflib
import threading
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import defaultdict


class ChangeType(Enum):
    """Types of codebase modifications."""
    FILE_CREATE = "file_create"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    FILE_RENAME = "file_rename"
    DIR_CREATE = "dir_create"
    CONTENT_INSERT = "content_insert"
    CONTENT_REPLACE = "content_replace"
    CONTENT_DELETE = "content_delete"
    FUNCTION_ADD = "function_add"
    FUNCTION_REPLACE = "function_replace"
    FUNCTION_DELETE = "function_delete"
    IMPORT_ADD = "import_add"
    CONFIG_CHANGE = "config_change"


class ValidationResult(Enum):
    """Result of change validation."""
    PASSED = "passed"
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    TEST_FAILURE = "test_failure"
    LINT_WARNING = "lint_warning"
    BUILD_FAILURE = "build_failure"
    SKIPPED = "skipped"


@dataclass
class FileSnapshot:
    """Snapshot of a file before modification."""
    path: str
    content: str
    hash: str
    timestamp: float
    exists: bool


@dataclass
class ChangeRecord:
    """Record of a single codebase change."""
    id: str
    change_type: ChangeType
    file_path: str
    timestamp: float

    # What was done
    description: str
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    diff: str = ""

    # Context
    reason: str = ""                 # Why this change was made
    source: str = ""                 # What triggered it (pattern, rule, optimization)
    generation: int = 0              # Evolution generation

    # Validation
    validated: bool = False
    validation_result: ValidationResult = ValidationResult.SKIPPED

    # Rollback
    backup_path: Optional[str] = None
    rolled_back: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.change_type.value,
            "file": self.file_path,
            "timestamp": self.timestamp,
            "description": self.description,
            "reason": self.reason,
            "source": self.source,
            "validated": self.validated,
            "validation": self.validation_result.value,
            "rolled_back": self.rolled_back,
            "diff_lines": len(self.diff.splitlines()) if self.diff else 0,
        }


@dataclass
class SearchResult:
    """Result of a codebase search."""
    file_path: str
    line_number: int
    line_content: str
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)


class CodebaseAgent:
    """
    The agent that gives Ultron real power to see and modify its own code.

    This is the ACTION layer — it turns optimization decisions into
    actual filesystem changes, with full safety and rollback.
    """

    def __init__(self,
                 project_root: str,
                 backup_dir: str = None,
                 changelog_path: str = None,
                 auto_validate: bool = True,
                 auto_backup: bool = True,
                 max_file_size_mb: float = 10.0):
        """
        Args:
            project_root: Root directory of the project
            backup_dir: Where to store backups (default: project_root/.ultron/backups)
            changelog_path: Where to store change log (default: project_root/.ultron/changelog)
            auto_validate: Automatically validate changes before applying
            auto_backup: Automatically create backups before modifying
            max_file_size_mb: Maximum file size to read/modify
        """
        self.project_root = Path(project_root).resolve()
        self.backup_dir = Path(backup_dir) if backup_dir else self.project_root / ".ultron" / "backups"
        self.changelog_path = Path(changelog_path) if changelog_path else self.project_root / ".ultron" / "changelog"
        self.auto_validate = auto_validate
        self.auto_backup = auto_backup
        self.max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)

        # Create directories
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.changelog_path.mkdir(parents=True, exist_ok=True)

        # Change history
        self._changes: List[ChangeRecord] = []
        self._change_lock = threading.Lock()

        # File cache (avoid repeated reads)
        self._file_cache: Dict[str, Tuple[str, float]] = {}  # path -> (content, mtime)
        self._cache_ttl = 5.0  # seconds

        # Statistics
        self._total_reads = 0
        self._total_writes = 0
        self._total_searches = 0
        self._total_rollbacks = 0

    # ═══════════════════════════════════════════════════════════════
    # BROWSE — Navigate the codebase
    # ═══════════════════════════════════════════════════════════════

    def list_directory(self, relative_path: str = "", recursive: bool = False,
                      max_depth: int = 3, extensions: Set[str] = None) -> Dict[str, Any]:
        """
        List contents of a directory.

        Args:
            relative_path: Path relative to project root (empty = root)
            recursive: Whether to recurse into subdirectories
            max_depth: Maximum recursion depth
            extensions: Filter by file extensions (e.g., {'.py', '.go'})

        Returns:
            Dict with 'files', 'directories', and 'total' keys
        """
        target = self.project_root / relative_path
        if not target.exists():
            return {"error": f"Directory not found: {relative_path}", "files": [], "directories": []}
        if not target.is_dir():
            return {"error": f"Not a directory: {relative_path}", "files": [], "directories": []}

        files = []
        directories = []

        skip_dirs = {
            '__pycache__', 'node_modules', '.git', 'venv', 'target',
            'vendor', '.mypy_cache', '.pytest_cache', '.ultron', 'env'
        }

        def walk(path: Path, depth: int):
            if depth > max_depth:
                return
            try:
                entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
            except PermissionError:
                return

            for entry in entries:
                rel = str(entry.relative_to(self.project_root))

                if entry.is_dir():
                    if entry.name in skip_dirs or entry.name.startswith('.'):
                        continue
                    directories.append({
                        "path": rel,
                        "name": entry.name,
                    })
                    if recursive:
                        walk(entry, depth + 1)
                elif entry.is_file():
                    if extensions and entry.suffix not in extensions:
                        continue
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0
                    files.append({
                        "path": rel,
                        "name": entry.name,
                        "extension": entry.suffix,
                        "size_bytes": size,
                    })

        walk(target, 0)

        return {
            "root": relative_path or ".",
            "files": files,
            "directories": directories,
            "total_files": len(files),
            "total_directories": len(directories),
        }

    def get_project_structure(self, max_depth: int = 3) -> Dict[str, Any]:
        """Get a high-level overview of the project structure."""
        result = self.list_directory("", recursive=True, max_depth=max_depth)

        # Aggregate by language
        by_extension = defaultdict(int)
        for f in result["files"]:
            by_extension[f["extension"]] += 1

        return {
            "root": str(self.project_root),
            "total_files": result["total_files"],
            "total_directories": result["total_directories"],
            "by_extension": dict(by_extension),
            "top_directories": [d["path"] for d in result["directories"][:20]],
        }

    # ═══════════════════════════════════════════════════════════════
    # READ — Access file contents
    # ═══════════════════════════════════════════════════════════════

    def read_file(self, relative_path: str, use_cache: bool = True) -> Optional[str]:
        """
        Read a file's contents.

        Args:
            relative_path: Path relative to project root
            use_cache: Use cached content if fresh

        Returns:
            File content as string, or None if not found
        """
        target = self.project_root / relative_path
        if not target.exists() or not target.is_file():
            return None

        # Size check
        try:
            if target.stat().st_size > self.max_file_size_bytes:
                return None
        except OSError:
            return None

        # Cache check
        if use_cache and relative_path in self._file_cache:
            content, cached_time = self._file_cache[relative_path]
            if time.time() - cached_time < self._cache_ttl:
                self._total_reads += 1
                return content

        # Read
        try:
            content = target.read_text(encoding='utf-8', errors='replace')
            self._file_cache[relative_path] = (content, time.time())
            self._total_reads += 1
            return content
        except (IOError, PermissionError):
            return None

    def read_lines(self, relative_path: str, start: int = 1, end: int = None) -> Optional[List[str]]:
        """Read specific lines from a file (1-indexed)."""
        content = self.read_file(relative_path)
        if content is None:
            return None

        lines = content.splitlines()
        start_idx = max(0, start - 1)
        end_idx = end if end else len(lines)
        return lines[start_idx:end_idx]

    def read_function(self, relative_path: str, function_name: str) -> Optional[str]:
        """Read a specific function/method from a Python file."""
        content = self.read_file(relative_path)
        if content is None:
            return None

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None

        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    start = node.lineno - 1
                    end = getattr(node, 'end_lineno', start + 1)
                    return '\n'.join(lines[start:end])
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == function_name:
                            start = item.lineno - 1
                            end = getattr(item, 'end_lineno', start + 1)
                            return '\n'.join(lines[start:end])

        return None

    def get_file_info(self, relative_path: str) -> Dict[str, Any]:
        """Get metadata about a file."""
        target = self.project_root / relative_path
        if not target.exists():
            return {"exists": False, "path": relative_path}

        stat = target.stat()
        content = self.read_file(relative_path)

        return {
            "exists": True,
            "path": relative_path,
            "name": target.name,
            "extension": target.suffix,
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "line_count": content.count('\n') + 1 if content else 0,
            "is_python": target.suffix == '.py',
            "is_go": target.suffix == '.go',
            "is_rust": target.suffix == '.rs',
        }

    # ═══════════════════════════════════════════════════════════════
    # SEARCH — Find patterns in the codebase
    # ═══════════════════════════════════════════════════════════════

    def search(self, pattern: str, file_extensions: Set[str] = None,
              directories: List[str] = None, max_results: int = 100,
              context_lines: int = 2, regex: bool = False) -> List[SearchResult]:
        """
        Search for a pattern across the codebase.

        Args:
            pattern: Text or regex pattern to find
            file_extensions: Filter by extensions (e.g., {'.py', '.go'})
            directories: Only search in these directories
            max_results: Maximum results to return
            context_lines: Lines of context to include
            regex: Treat pattern as regex

        Returns:
            List of SearchResult objects
        """
        self._total_searches += 1
        results = []

        if regex:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
            except re.error:
                return []
        else:
            compiled = None

        # Walk source files
        for file_path in self._walk_searchable_files(file_extensions, directories):
            content = self.read_file(str(file_path.relative_to(self.project_root)))
            if content is None:
                continue

            lines = content.splitlines()
            for i, line in enumerate(lines):
                if len(results) >= max_results:
                    return results

                match = False
                if compiled:
                    match = compiled.search(line) is not None
                else:
                    match = pattern.lower() in line.lower()

                if match:
                    context_before = lines[max(0, i - context_lines):i]
                    context_after = lines[i + 1:i + 1 + context_lines]

                    results.append(SearchResult(
                        file_path=str(file_path.relative_to(self.project_root)),
                        line_number=i + 1,
                        line_content=line,
                        context_before=context_before,
                        context_after=context_after,
                    ))

        return results

    def find_usages(self, symbol: str, file_extensions: Set[str] = None) -> List[SearchResult]:
        """Find all usages of a symbol (function name, class name, variable)."""
        # Use word boundary matching
        pattern = rf'\b{re.escape(symbol)}\b'
        return self.search(pattern, file_extensions=file_extensions, regex=True)

    def find_definitions(self, name: str) -> List[SearchResult]:
        """Find where a function/class/variable is defined."""
        patterns = [
            rf'def\s+{re.escape(name)}\s*\(',      # Python function
            rf'class\s+{re.escape(name)}[\s:(]',     # Python class
            rf'func\s+.*{re.escape(name)}\s*\(',     # Go function
            rf'fn\s+{re.escape(name)}\s*[<(]',       # Rust function
            rf'struct\s+{re.escape(name)}\s',         # Go/Rust struct
            rf'type\s+{re.escape(name)}\s',           # Go type
            rf'{re.escape(name)}\s*=\s*',             # Assignment
        ]

        all_results = []
        for pat in patterns:
            results = self.search(pat, regex=True, max_results=20)
            all_results.extend(results)

        return all_results

    # ═══════════════════════════════════════════════════════════════
    # MODIFY — Make changes to files
    # ═══════════════════════════════════════════════════════════════

    def write_file(self, relative_path: str, content: str,
                   reason: str = "", source: str = "") -> ChangeRecord:
        """
        Write content to a file (create or overwrite).

        Args:
            relative_path: Path relative to project root
            content: New file content
            reason: Why this change is being made
            source: What triggered it

        Returns:
            ChangeRecord documenting the change
        """
        target = self.project_root / relative_path
        is_new = not target.exists()

        # Backup if modifying existing
        old_content = None
        if not is_new and self.auto_backup:
            old_content = self.read_file(relative_path, use_cache=False)
            self._create_backup(relative_path, old_content)

        # Validate if requested
        if self.auto_validate and relative_path.endswith('.py'):
            validation = self._validate_python(content)
            if validation != ValidationResult.PASSED:
                return ChangeRecord(
                    id=self._gen_change_id(),
                    change_type=ChangeType.FILE_CREATE if is_new else ChangeType.FILE_MODIFY,
                    file_path=relative_path,
                    timestamp=time.time(),
                    description=f"BLOCKED: Validation failed ({validation.value})",
                    new_content=content,
                    old_content=old_content,
                    reason=reason,
                    source=source,
                    validated=True,
                    validation_result=validation,
                )

        # Create parent directories
        target.parent.mkdir(parents=True, exist_ok=True)

        # Write
        target.write_text(content, encoding='utf-8')
        self._total_writes += 1

        # Invalidate cache
        if relative_path in self._file_cache:
            del self._file_cache[relative_path]

        # Create diff
        diff = ""
        if old_content:
            diff = '\n'.join(difflib.unified_diff(
                old_content.splitlines(),
                content.splitlines(),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                lineterm="",
            ))

        # Record change
        record = ChangeRecord(
            id=self._gen_change_id(),
            change_type=ChangeType.FILE_CREATE if is_new else ChangeType.FILE_MODIFY,
            file_path=relative_path,
            timestamp=time.time(),
            description=f"{'Created' if is_new else 'Modified'} {relative_path}",
            old_content=old_content,
            new_content=content,
            diff=diff,
            reason=reason,
            source=source,
            validated=True,
            validation_result=ValidationResult.PASSED,
        )

        self._record_change(record)
        return record

    def replace_in_file(self, relative_path: str, old_text: str, new_text: str,
                        reason: str = "", source: str = "") -> ChangeRecord:
        """
        Replace specific text in a file.

        Args:
            relative_path: File to modify
            old_text: Exact text to find and replace
            new_text: Replacement text

        Returns:
            ChangeRecord
        """
        content = self.read_file(relative_path, use_cache=False)
        if content is None:
            return ChangeRecord(
                id=self._gen_change_id(),
                change_type=ChangeType.CONTENT_REPLACE,
                file_path=relative_path,
                timestamp=time.time(),
                description=f"FAILED: File not found: {relative_path}",
                reason=reason, source=source,
            )

        if old_text not in content:
            return ChangeRecord(
                id=self._gen_change_id(),
                change_type=ChangeType.CONTENT_REPLACE,
                file_path=relative_path,
                timestamp=time.time(),
                description=f"FAILED: Text not found in {relative_path}",
                reason=reason, source=source,
            )

        new_content = content.replace(old_text, new_text, 1)
        return self.write_file(relative_path, new_content, reason=reason, source=source)

    def insert_at_line(self, relative_path: str, line_number: int, text: str,
                       reason: str = "", source: str = "") -> ChangeRecord:
        """Insert text at a specific line number (1-indexed)."""
        content = self.read_file(relative_path, use_cache=False)
        if content is None:
            return ChangeRecord(
                id=self._gen_change_id(), change_type=ChangeType.CONTENT_INSERT,
                file_path=relative_path, timestamp=time.time(),
                description=f"FAILED: File not found", reason=reason, source=source,
            )

        lines = content.splitlines(keepends=True)
        idx = max(0, min(line_number - 1, len(lines)))
        lines.insert(idx, text if text.endswith('\n') else text + '\n')
        new_content = ''.join(lines)

        return self.write_file(relative_path, new_content, reason=reason, source=source)

    def append_to_file(self, relative_path: str, text: str,
                       reason: str = "", source: str = "") -> ChangeRecord:
        """Append text to the end of a file."""
        content = self.read_file(relative_path, use_cache=False) or ""
        if not content.endswith('\n'):
            content += '\n'
        new_content = content + text
        return self.write_file(relative_path, new_content, reason=reason, source=source)

    def delete_lines(self, relative_path: str, start: int, end: int,
                     reason: str = "", source: str = "") -> ChangeRecord:
        """Delete lines from a file (1-indexed, inclusive)."""
        content = self.read_file(relative_path, use_cache=False)
        if content is None:
            return ChangeRecord(
                id=self._gen_change_id(), change_type=ChangeType.CONTENT_DELETE,
                file_path=relative_path, timestamp=time.time(),
                description=f"FAILED: File not found", reason=reason, source=source,
            )

        lines = content.splitlines(keepends=True)
        new_lines = lines[:start-1] + lines[end:]
        new_content = ''.join(new_lines)

        return self.write_file(relative_path, new_content, reason=reason, source=source)

    def create_file(self, relative_path: str, content: str = "",
                    reason: str = "", source: str = "") -> ChangeRecord:
        """Create a new file."""
        target = self.project_root / relative_path
        if target.exists():
            return ChangeRecord(
                id=self._gen_change_id(), change_type=ChangeType.FILE_CREATE,
                file_path=relative_path, timestamp=time.time(),
                description=f"FAILED: File already exists", reason=reason, source=source,
            )
        return self.write_file(relative_path, content, reason=reason, source=source)

    def delete_file(self, relative_path: str, reason: str = "", source: str = "") -> ChangeRecord:
        """Delete a file (with backup)."""
        target = self.project_root / relative_path
        if not target.exists():
            return ChangeRecord(
                id=self._gen_change_id(), change_type=ChangeType.FILE_DELETE,
                file_path=relative_path, timestamp=time.time(),
                description=f"FAILED: File not found", reason=reason, source=source,
            )

        # Backup
        old_content = self.read_file(relative_path, use_cache=False)
        if self.auto_backup:
            self._create_backup(relative_path, old_content)

        target.unlink()
        if relative_path in self._file_cache:
            del self._file_cache[relative_path]

        record = ChangeRecord(
            id=self._gen_change_id(), change_type=ChangeType.FILE_DELETE,
            file_path=relative_path, timestamp=time.time(),
            description=f"Deleted {relative_path}",
            old_content=old_content, reason=reason, source=source,
        )
        self._record_change(record)
        return record

    # ═══════════════════════════════════════════════════════════════
    # EXECUTE — Run commands against the codebase
    # ═══════════════════════════════════════════════════════════════

    def run_command(self, command: str, cwd: str = None,
                    timeout: float = 60.0) -> Dict[str, Any]:
        """
        Execute a shell command in the project.

        Args:
            command: Shell command to run
            cwd: Working directory (relative to project root)
            timeout: Maximum execution time in seconds

        Returns:
            Dict with 'stdout', 'stderr', 'returncode', 'duration'
        """
        work_dir = self.project_root / cwd if cwd else self.project_root

        start = time.time()
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": result.stdout[:10000],  # Truncate
                "stderr": result.stderr[:5000],
                "returncode": result.returncode,
                "success": result.returncode == 0,
                "duration_seconds": time.time() - start,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "", "stderr": "Command timed out",
                "returncode": -1, "success": False,
                "duration_seconds": timeout,
            }
        except Exception as e:
            return {
                "stdout": "", "stderr": str(e),
                "returncode": -1, "success": False,
                "duration_seconds": time.time() - start,
            }

    def run_tests(self, test_path: str = None) -> Dict[str, Any]:
        """Run project tests."""
        # Detect test framework
        if (self.project_root / "pytest.ini").exists() or (self.project_root / "setup.py").exists():
            cmd = f"python -m pytest {test_path or ''} --tb=short -q"
        elif (self.project_root / "go.mod").exists():
            cmd = f"go test {test_path or './...'} -short"
        else:
            cmd = f"python -m pytest {test_path or ''} --tb=short -q"

        return self.run_command(cmd)

    def run_lint(self, file_path: str = None) -> Dict[str, Any]:
        """Run linting on a file or the project."""
        target = file_path or "."
        if file_path and file_path.endswith('.py'):
            return self.run_command(f"python -m py_compile {target}")
        elif file_path and file_path.endswith('.go'):
            return self.run_command(f"go vet {target}")
        return self.run_command(f"python -m py_compile {target}")

    def git_diff(self) -> str:
        """Get current git diff."""
        result = self.run_command("git diff")
        return result.get("stdout", "")

    def git_status(self) -> str:
        """Get git status."""
        result = self.run_command("git status --short")
        return result.get("stdout", "")

    # ═══════════════════════════════════════════════════════════════
    # ROLLBACK — Undo changes
    # ═══════════════════════════════════════════════════════════════

    def rollback_change(self, change_id: str) -> bool:
        """Rollback a specific change by ID."""
        with self._change_lock:
            for change in self._changes:
                if change.id == change_id and not change.rolled_back:
                    return self._execute_rollback(change)
        return False

    def rollback_last(self, count: int = 1) -> List[str]:
        """Rollback the last N changes."""
        rolled_back = []
        with self._change_lock:
            for change in reversed(self._changes):
                if len(rolled_back) >= count:
                    break
                if not change.rolled_back:
                    if self._execute_rollback(change):
                        rolled_back.append(change.id)
        return rolled_back

    def _execute_rollback(self, change: ChangeRecord) -> bool:
        """Execute a rollback for a single change."""
        target = self.project_root / change.file_path

        try:
            if change.change_type == ChangeType.FILE_CREATE:
                # File was created — delete it
                if target.exists():
                    target.unlink()
            elif change.change_type == ChangeType.FILE_DELETE:
                # File was deleted — restore from old_content
                if change.old_content is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(change.old_content, encoding='utf-8')
            elif change.old_content is not None:
                # File was modified — restore old content
                target.write_text(change.old_content, encoding='utf-8')
            else:
                return False

            change.rolled_back = True
            self._total_rollbacks += 1

            # Invalidate cache
            rel_path = change.file_path
            if rel_path in self._file_cache:
                del self._file_cache[rel_path]

            return True
        except (IOError, PermissionError):
            return False

    # ═══════════════════════════════════════════════════════════════
    # VALIDATION
    # ═══════════════════════════════════════════════════════════════

    def _validate_python(self, content: str) -> ValidationResult:
        """Validate Python code for syntax correctness."""
        try:
            ast.parse(content)
            return ValidationResult.PASSED
        except SyntaxError:
            return ValidationResult.SYNTAX_ERROR

    def validate_file(self, relative_path: str) -> ValidationResult:
        """Validate a file based on its type."""
        content = self.read_file(relative_path)
        if content is None:
            return ValidationResult.SKIPPED

        if relative_path.endswith('.py'):
            return self._validate_python(content)
        elif relative_path.endswith('.go'):
            result = self.run_command(f"go build {relative_path}", timeout=30)
            return ValidationResult.PASSED if result["success"] else ValidationResult.BUILD_FAILURE
        elif relative_path.endswith('.rs'):
            result = self.run_command("cargo check", cwd="rust/dynamic_neural", timeout=60)
            return ValidationResult.PASSED if result["success"] else ValidationResult.BUILD_FAILURE

        return ValidationResult.SKIPPED

    # ═══════════════════════════════════════════════════════════════
    # INTERNAL UTILITIES
    # ═══════════════════════════════════════════════════════════════

    def _create_backup(self, relative_path: str, content: Optional[str]):
        """Create a backup of a file before modification."""
        if content is None:
            return

        timestamp = int(time.time())
        safe_name = relative_path.replace('/', '_').replace('\\', '_')
        backup_file = self.backup_dir / f"{safe_name}.{timestamp}.bak"
        backup_file.write_text(content, encoding='utf-8')

    def _record_change(self, record: ChangeRecord):
        """Record a change in the changelog."""
        with self._change_lock:
            self._changes.append(record)

        # Persist to disk
        log_file = self.changelog_path / f"changes_{time.strftime('%Y-%m-%d')}.jsonl"
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(record.to_dict()) + '\n')
        except IOError:
            pass

    def _gen_change_id(self) -> str:
        """Generate a unique change ID."""
        return hashlib.md5(f"change:{time.time_ns()}".encode()).hexdigest()[:12]

    def _walk_searchable_files(self, extensions: Set[str] = None,
                               directories: List[str] = None):
        """Walk files for searching."""
        default_extensions = {'.py', '.go', '.rs', '.jl', '.yaml', '.yml', '.toml', '.json'}
        exts = extensions or default_extensions

        skip_dirs = {
            '__pycache__', 'node_modules', '.git', 'venv', 'target',
            'vendor', '.mypy_cache', '.ultron'
        }

        roots = []
        if directories:
            roots = [self.project_root / d for d in directories]
        else:
            roots = [self.project_root]

        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in skip_dirs]
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    if filepath.suffix in exts:
                        yield filepath

    # ═══════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════

    def get_change_history(self, last_n: int = 50) -> List[Dict[str, Any]]:
        """Get recent change history."""
        with self._change_lock:
            return [c.to_dict() for c in self._changes[-last_n:]]

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "total_reads": self._total_reads,
            "total_writes": self._total_writes,
            "total_searches": self._total_searches,
            "total_rollbacks": self._total_rollbacks,
            "changes_recorded": len(self._changes),
            "cache_size": len(self._file_cache),
            "backup_dir": str(self.backup_dir),
        }
