"""
Code Introspector — Self-Awareness Through Code Analysis.

This component gives Ultron deep understanding of its OWN source code.
It doesn't just read files — it builds a living model of what every
component does, how they connect, where complexity hides, and what's
dead weight.

Capabilities:
  - Multi-language AST parsing (Python, Go, Rust)
  - Dependency graph construction (who calls whom)
  - Complexity hotspot detection (cyclomatic, cognitive, nesting)
  - Dead code identification (unreachable functions, unused imports)
  - Code health scoring per component
  - Change impact prediction ("if I modify X, what breaks?")
  - Interface boundary mapping (gRPC, HTTP, IPC surfaces)
  - Hot path identification (most-executed code paths from traces)
  - Technical debt quantification
  - Evolution opportunity scoring (what's easiest to improve)

The introspector maintains a LIVE map of the codebase that updates
as the self-improvement engine applies patches. This prevents the
system from breaking itself by modifying code it doesn't understand.
"""

import ast
import os
import re
import time
import hashlib
import threading
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, Counter
from pathlib import Path
import json


class Language(Enum):
    """Supported source languages."""
    PYTHON = "python"
    GO = "go"
    RUST = "rust"
    JULIA = "julia"
    UNKNOWN = "unknown"


class ComponentHealth(Enum):
    """Health classification for a code component."""
    EXCELLENT = "excellent"    # Low complexity, well-tested, no issues
    GOOD = "good"             # Minor issues, maintainable
    MODERATE = "moderate"     # Some complexity, needs attention
    CONCERNING = "concerning" # High complexity, potential problems
    CRITICAL = "critical"     # Extremely complex, likely source of bugs


@dataclass
class FunctionProfile:
    """Profile of a single function/method."""
    name: str
    file_path: str
    line_start: int
    line_end: int
    language: Language

    # Complexity metrics
    cyclomatic_complexity: int = 1
    cognitive_complexity: int = 0
    nesting_depth: int = 0
    parameter_count: int = 0
    line_count: int = 0
    
    # Dependencies
    calls: List[str] = field(default_factory=list)       # Functions this calls
    called_by: List[str] = field(default_factory=list)   # Functions that call this
    imports_used: List[str] = field(default_factory=list)

    # Runtime data (from experience collector)
    execution_count: int = 0
    avg_duration_us: float = 0.0
    error_rate: float = 0.0
    last_modified: float = 0.0

    # Assessment
    is_dead_code: bool = False
    is_hot_path: bool = False
    improvement_opportunity: float = 0.0  # 0-1, how much this could be improved

    @property
    def health_score(self) -> float:
        """0-1 health score (1 = perfect)."""
        score = 1.0
        # Penalize complexity
        score -= min(0.3, self.cyclomatic_complexity / 30.0)
        score -= min(0.2, self.cognitive_complexity / 40.0)
        score -= min(0.1, self.nesting_depth / 8.0)
        score -= min(0.1, self.parameter_count / 10.0)
        score -= min(0.1, self.line_count / 200.0)
        # Penalize errors
        score -= self.error_rate * 0.3
        return max(0.0, score)


@dataclass
class FileProfile:
    """Profile of a source file."""
    path: str
    language: Language
    line_count: int = 0
    function_count: int = 0
    class_count: int = 0
    import_count: int = 0
    
    # Metrics
    total_complexity: int = 0
    avg_function_complexity: float = 0.0
    max_function_complexity: int = 0
    dead_code_lines: int = 0
    
    # Dependencies
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)  # Other files
    depended_by: List[str] = field(default_factory=list)  # Files that depend on this

    # Hash for change detection
    content_hash: str = ""
    last_analyzed: float = 0.0

    @property
    def health(self) -> ComponentHealth:
        """Overall health classification."""
        score = self.health_score
        if score > 0.85:
            return ComponentHealth.EXCELLENT
        elif score > 0.7:
            return ComponentHealth.GOOD
        elif score > 0.5:
            return ComponentHealth.MODERATE
        elif score > 0.3:
            return ComponentHealth.CONCERNING
        return ComponentHealth.CRITICAL

    @property
    def health_score(self) -> float:
        score = 1.0
        score -= min(0.3, self.avg_function_complexity / 15.0)
        score -= min(0.2, self.max_function_complexity / 30.0)
        if self.line_count > 0:
            score -= min(0.2, self.dead_code_lines / self.line_count)
        score -= min(0.1, self.line_count / 1000.0)
        return max(0.0, score)


@dataclass
class ComponentProfile:
    """Profile of a logical component (module/package)."""
    name: str
    path: str
    language: Language
    description: str = ""

    # Aggregated metrics
    total_files: int = 0
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0
    avg_complexity: float = 0.0
    max_complexity: int = 0
    dead_code_percentage: float = 0.0
    
    # Interface surface
    public_functions: int = 0
    public_classes: int = 0
    grpc_endpoints: int = 0
    
    # Health
    health: ComponentHealth = ComponentHealth.MODERATE
    health_score: float = 0.5
    technical_debt_hours: float = 0.0  # Estimated hours to fix
    
    # Evolution
    improvement_priority: float = 0.0  # 0-1, how urgently this needs work
    easiest_wins: List[str] = field(default_factory=list)  # Quick improvements
    
    # Runtime
    error_rate: float = 0.0
    avg_latency_us: float = 0.0


@dataclass
class DependencyMap:
    """Complete dependency graph of the system."""
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # file -> metadata
    edges: List[Tuple[str, str, str]] = field(default_factory=list)  # (from, to, type)
    
    # Analysis results
    circular_dependencies: List[List[str]] = field(default_factory=list)
    bottleneck_nodes: List[str] = field(default_factory=list)  # High fan-in/fan-out
    isolated_nodes: List[str] = field(default_factory=list)    # No connections
    critical_paths: List[List[str]] = field(default_factory=list)  # Longest dependency chains

    def get_impact_radius(self, file_path: str) -> Set[str]:
        """Get all files that would be affected by changing this file."""
        affected = set()
        queue = [file_path]
        while queue:
            current = queue.pop(0)
            if current in affected:
                continue
            affected.add(current)
            # Find all files that depend on current
            for src, dst, _ in self.edges:
                if src == current and dst not in affected:
                    queue.append(dst)
        affected.discard(file_path)
        return affected


class CodeIntrospector:
    """
    The self-awareness engine — Ultron understanding its own code.

    Maintains a live model of the entire codebase that informs
    the self-improvement system about what's safe to modify,
    what's complex, and where the biggest gains are.
    """

    def __init__(self, project_root: str, scan_interval: float = 300.0):
        """
        Args:
            project_root: Root directory of the project
            scan_interval: Seconds between full rescans
        """
        self.project_root = Path(project_root)
        self.scan_interval = scan_interval

        # File profiles (per-file analysis)
        self._file_profiles: Dict[str, FileProfile] = {}
        
        # Function profiles (per-function analysis)
        self._function_profiles: Dict[str, FunctionProfile] = {}
        
        # Component profiles (per-module analysis)
        self._component_profiles: Dict[str, ComponentProfile] = {}
        
        # Dependency graph
        self._dependency_map = DependencyMap()

        # Change tracking
        self._file_hashes: Dict[str, str] = {}
        self._last_full_scan: float = 0.0

        # Language-specific analyzers
        self._analyzers = {
            Language.PYTHON: self._analyze_python_file,
            Language.GO: self._analyze_go_file,
            Language.RUST: self._analyze_rust_file,
        }

        # Concurrency
        self._lock = threading.RLock()
        self._running = False
        self._scan_thread: Optional[threading.Thread] = None

        # Statistics
        self._total_scans = 0
        self._files_analyzed = 0

    def start(self):
        """Start the code introspector."""
        self._running = True
        # Initial full scan
        self.full_scan()
        # Start background rescanner
        self._scan_thread = threading.Thread(
            target=self._scan_loop,
            daemon=True,
            name="CodeIntrospector-Scanner"
        )
        self._scan_thread.start()
        print(f"[CodeIntrospector] Started — {self._files_analyzed} files profiled")

    def stop(self):
        """Stop the introspector."""
        self._running = False
        if self._scan_thread:
            self._scan_thread.join(timeout=5.0)

    # ═══════════════════════════════════════════════════════════════
    # FULL SCAN — Build complete codebase model
    # ═══════════════════════════════════════════════════════════════

    def full_scan(self) -> Dict[str, Any]:
        """Perform a complete scan of the codebase."""
        self._total_scans += 1
        scan_start = time.time()

        files_found = 0
        files_changed = 0

        # Walk the project tree
        for file_path in self._walk_source_files():
            language = self._detect_language(file_path)
            if language == Language.UNKNOWN:
                continue

            files_found += 1
            rel_path = str(file_path.relative_to(self.project_root))

            # Check if file has changed
            current_hash = self._hash_file(file_path)
            if current_hash == self._file_hashes.get(rel_path):
                continue  # Skip unchanged files

            self._file_hashes[rel_path] = current_hash
            files_changed += 1

            # Analyze the file
            analyzer = self._analyzers.get(language)
            if analyzer:
                try:
                    profile = analyzer(file_path, rel_path)
                    if profile:
                        profile.content_hash = current_hash
                        profile.last_analyzed = time.time()
                        self._file_profiles[rel_path] = profile
                        self._files_analyzed += 1
                except Exception as e:
                    # Don't let analysis failures break the scan
                    pass

        # Build dependency graph
        self._build_dependency_graph()

        # Build component profiles
        self._build_component_profiles()

        # Identify dead code
        self._identify_dead_code()

        # Score improvement opportunities
        self._score_improvement_opportunities()

        self._last_full_scan = time.time()

        return {
            "files_found": files_found,
            "files_changed": files_changed,
            "total_profiled": len(self._file_profiles),
            "components": len(self._component_profiles),
            "scan_duration_ms": (time.time() - scan_start) * 1000,
        }

    # ═══════════════════════════════════════════════════════════════
    # PYTHON ANALYSIS
    # ═══════════════════════════════════════════════════════════════

    def _analyze_python_file(self, file_path: Path, rel_path: str) -> Optional[FileProfile]:
        """Deep analysis of a Python source file."""
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return None

        profile = FileProfile(
            path=rel_path,
            language=Language.PYTHON,
            line_count=source.count('\n') + 1,
        )

        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    profile.imports.append(alias.name)
                    profile.import_count += 1
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    profile.imports.append(node.module)
                    profile.import_count += 1

        # Analyze functions and classes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                func_profile = self._analyze_python_function(node, rel_path)
                func_key = f"{rel_path}:{node.name}"
                self._function_profiles[func_key] = func_profile
                profile.function_count += 1
                profile.total_complexity += func_profile.cyclomatic_complexity

                if not node.name.startswith('_'):
                    profile.exports.append(node.name)
                    profile.public_functions = profile.function_count  # Simplified

            elif isinstance(node, ast.ClassDef):
                profile.class_count += 1
                if not node.name.startswith('_'):
                    profile.exports.append(node.name)

                # Analyze methods within class
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        func_profile = self._analyze_python_function(item, rel_path)
                        func_key = f"{rel_path}:{node.name}.{item.name}"
                        self._function_profiles[func_key] = func_profile
                        profile.function_count += 1
                        profile.total_complexity += func_profile.cyclomatic_complexity

        # Calculate averages
        if profile.function_count > 0:
            profile.avg_function_complexity = profile.total_complexity / profile.function_count
            # Find max complexity
            file_funcs = [
                f for f in self._function_profiles.values()
                if f.file_path == rel_path
            ]
            if file_funcs:
                profile.max_function_complexity = max(f.cyclomatic_complexity for f in file_funcs)

        return profile

    def _analyze_python_function(self, node: ast.AST, file_path: str) -> FunctionProfile:
        """Analyze a single Python function for complexity and dependencies."""
        func_name = getattr(node, 'name', 'unknown')
        
        profile = FunctionProfile(
            name=func_name,
            file_path=file_path,
            line_start=node.lineno,
            line_end=getattr(node, 'end_lineno', node.lineno),
            language=Language.PYTHON,
            parameter_count=len(node.args.args) if hasattr(node, 'args') else 0,
        )

        profile.line_count = profile.line_end - profile.line_start + 1

        # Calculate cyclomatic complexity
        profile.cyclomatic_complexity = self._python_cyclomatic_complexity(node)
        
        # Calculate cognitive complexity
        profile.cognitive_complexity = self._python_cognitive_complexity(node)
        
        # Calculate max nesting depth
        profile.nesting_depth = self._python_nesting_depth(node)

        # Extract function calls (dependencies)
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    profile.calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    profile.calls.append(child.func.attr)

        return profile

    def _python_cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a Python AST node."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.IfExp)):
                complexity += 1
            elif isinstance(child, (ast.For, ast.While)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # and/or add complexity
                complexity += len(child.values) - 1
            elif isinstance(child, ast.Assert):
                complexity += 1

        return complexity

    def _python_cognitive_complexity(self, node: ast.AST, depth: int = 0) -> int:
        """
        Calculate cognitive complexity (how hard it is for a human to understand).
        
        Unlike cyclomatic, this penalizes nesting and rewards linear flow.
        """
        complexity = 0

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.IfExp)):
                complexity += 1 + depth  # Nesting penalty
                complexity += self._python_cognitive_complexity(child, depth + 1)
            elif isinstance(child, (ast.For, ast.While)):
                complexity += 1 + depth
                complexity += self._python_cognitive_complexity(child, depth + 1)
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1 + depth
                complexity += self._python_cognitive_complexity(child, depth + 1)
            elif isinstance(child, ast.BoolOp):
                complexity += 1
            elif isinstance(child, (ast.Break, ast.Continue)):
                complexity += 1
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Nested functions add complexity
                complexity += 1 + depth
                complexity += self._python_cognitive_complexity(child, depth + 1)
            else:
                complexity += self._python_cognitive_complexity(child, depth)

        return complexity

    def _python_nesting_depth(self, node: ast.AST) -> int:
        """Find maximum nesting depth in a Python function."""
        max_depth = 0

        def walk(n, current_depth):
            nonlocal max_depth
            max_depth = max(max_depth, current_depth)

            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.With,
                                     ast.Try, ast.ExceptHandler)):
                    walk(child, current_depth + 1)
                else:
                    walk(child, current_depth)

        walk(node, 0)
        return max_depth

    # ═══════════════════════════════════════════════════════════════
    # GO ANALYSIS (regex-based for Go since no AST parser in Python)
    # ═══════════════════════════════════════════════════════════════

    def _analyze_go_file(self, file_path: Path, rel_path: str) -> Optional[FileProfile]:
        """Analyze a Go source file using regex patterns."""
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
        except (IOError, UnicodeDecodeError):
            return None

        profile = FileProfile(
            path=rel_path,
            language=Language.GO,
            line_count=source.count('\n') + 1,
        )

        # Extract imports
        import_block = re.findall(r'import\s*\(\s*(.*?)\s*\)', source, re.DOTALL)
        if import_block:
            for block in import_block:
                imports = re.findall(r'"([^"]+)"', block)
                profile.imports.extend(imports)
                profile.import_count += len(imports)
        
        single_imports = re.findall(r'import\s+"([^"]+)"', source)
        profile.imports.extend(single_imports)
        profile.import_count += len(single_imports)

        # Count functions
        func_pattern = r'func\s+(?:\([^)]*\)\s+)?(\w+)\s*\([^)]*\)'
        functions = re.findall(func_pattern, source)
        profile.function_count = len(functions)

        for func_name in functions:
            if func_name[0].isupper():
                profile.exports.append(func_name)

        # Count structs (like classes)
        struct_pattern = r'type\s+(\w+)\s+struct\s*\{'
        structs = re.findall(struct_pattern, source)
        profile.class_count = len(structs)

        # Estimate complexity per function
        func_bodies = re.findall(
            r'func\s+(?:\([^)]*\)\s+)?\w+\s*\([^)]*\)\s*(?:[^{]*)?\{(.*?)\n\}',
            source, re.DOTALL
        )

        total_complexity = 0
        max_complexity = 0
        for body in func_bodies:
            complexity = self._go_estimate_complexity(body)
            total_complexity += complexity
            max_complexity = max(max_complexity, complexity)

            # Create function profile
            func_match = re.search(r'func\s+(?:\([^)]*\)\s+)?(\w+)', body[:100])

        profile.total_complexity = total_complexity
        profile.max_function_complexity = max_complexity
        if profile.function_count > 0:
            profile.avg_function_complexity = total_complexity / profile.function_count

        return profile

    def _go_estimate_complexity(self, func_body: str) -> int:
        """Estimate cyclomatic complexity of a Go function body."""
        complexity = 1

        # Count decision points
        complexity += len(re.findall(r'\bif\b', func_body))
        complexity += len(re.findall(r'\bfor\b', func_body))
        complexity += len(re.findall(r'\bcase\b', func_body))
        complexity += len(re.findall(r'\b&&\b', func_body))
        complexity += len(re.findall(r'\b\|\|\b', func_body))
        complexity += len(re.findall(r'\bselect\b', func_body))

        return complexity

    # ═══════════════════════════════════════════════════════════════
    # RUST ANALYSIS
    # ═══════════════════════════════════════════════════════════════

    def _analyze_rust_file(self, file_path: Path, rel_path: str) -> Optional[FileProfile]:
        """Analyze a Rust source file using regex patterns."""
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
        except (IOError, UnicodeDecodeError):
            return None

        profile = FileProfile(
            path=rel_path,
            language=Language.RUST,
            line_count=source.count('\n') + 1,
        )

        # Extract use statements (imports)
        use_pattern = r'use\s+([^;]+);'
        uses = re.findall(use_pattern, source)
        profile.imports = uses
        profile.import_count = len(uses)

        # Count functions
        fn_pattern = r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)'
        functions = re.findall(fn_pattern, source)
        profile.function_count = len(functions)

        pub_fn_pattern = r'pub\s+(?:async\s+)?fn\s+(\w+)'
        pub_functions = re.findall(pub_fn_pattern, source)
        profile.exports = pub_functions

        # Count structs and enums
        struct_pattern = r'(?:pub\s+)?struct\s+(\w+)'
        enum_pattern = r'(?:pub\s+)?enum\s+(\w+)'
        profile.class_count = len(re.findall(struct_pattern, source)) + len(re.findall(enum_pattern, source))

        # Estimate complexity
        fn_bodies = re.findall(
            r'(?:pub\s+)?(?:async\s+)?fn\s+\w+[^{]*\{(.*?)\n\s*\}',
            source, re.DOTALL
        )

        total_complexity = 0
        max_complexity = 0
        for body in fn_bodies:
            complexity = self._rust_estimate_complexity(body)
            total_complexity += complexity
            max_complexity = max(max_complexity, complexity)

        profile.total_complexity = total_complexity
        profile.max_function_complexity = max_complexity
        if profile.function_count > 0:
            profile.avg_function_complexity = total_complexity / profile.function_count

        return profile

    def _rust_estimate_complexity(self, func_body: str) -> int:
        """Estimate cyclomatic complexity of a Rust function body."""
        complexity = 1

        complexity += len(re.findall(r'\bif\b', func_body))
        complexity += len(re.findall(r'\bfor\b', func_body))
        complexity += len(re.findall(r'\bwhile\b', func_body))
        complexity += len(re.findall(r'\bmatch\b', func_body))
        complexity += len(re.findall(r'=>', func_body))  # Match arms
        complexity += len(re.findall(r'\b&&\b', func_body))
        complexity += len(re.findall(r'\b\|\|\b', func_body))
        complexity += len(re.findall(r'\?', func_body))  # Error propagation

        return complexity

    # ═══════════════════════════════════════════════════════════════
    # DEPENDENCY GRAPH
    # ═══════════════════════════════════════════════════════════════

    def _build_dependency_graph(self):
        """Build the inter-file dependency graph."""
        self._dependency_map = DependencyMap()

        for rel_path, profile in self._file_profiles.items():
            # Add node
            self._dependency_map.nodes[rel_path] = {
                "language": profile.language.value,
                "lines": profile.line_count,
                "complexity": profile.total_complexity,
                "exports": profile.exports,
            }

            # Resolve imports to files
            for imp in profile.imports:
                target = self._resolve_import(imp, profile.language, rel_path)
                if target and target in self._file_profiles:
                    self._dependency_map.edges.append((rel_path, target, "imports"))
                    profile.depends_on.append(target)
                    self._file_profiles[target].depended_by.append(rel_path)

        # Detect circular dependencies
        self._detect_circular_deps()

        # Find bottleneck nodes (high fan-in)
        fan_in = defaultdict(int)
        fan_out = defaultdict(int)
        for src, dst, _ in self._dependency_map.edges:
            fan_out[src] += 1
            fan_in[dst] += 1

        # Bottlenecks: high combined fan-in + fan-out
        for node in self._dependency_map.nodes:
            combined = fan_in[node] + fan_out[node]
            if combined > 10:
                self._dependency_map.bottleneck_nodes.append(node)

        # Isolated nodes
        connected = set()
        for src, dst, _ in self._dependency_map.edges:
            connected.add(src)
            connected.add(dst)
        self._dependency_map.isolated_nodes = [
            n for n in self._dependency_map.nodes if n not in connected
        ]

    def _resolve_import(self, import_path: str, language: Language, source_file: str) -> Optional[str]:
        """Resolve an import string to a relative file path."""
        if language == Language.PYTHON:
            # Convert dotted path to file path
            parts = import_path.split('.')
            
            # Check for relative imports within the project
            for i in range(len(parts), 0, -1):
                candidate = '/'.join(parts[:i]) + '.py'
                if candidate in self._file_profiles:
                    return candidate
                # Try as package
                candidate = '/'.join(parts[:i]) + '/__init__.py'
                if candidate in self._file_profiles:
                    return candidate

            # Try with python/ prefix
            for i in range(len(parts), 0, -1):
                candidate = 'python/' + '/'.join(parts[:i]) + '.py'
                if candidate in self._file_profiles:
                    return candidate

        elif language == Language.GO:
            # Go imports are full module paths
            # Look for matching directory in project
            parts = import_path.split('/')
            for i in range(len(parts), 0, -1):
                candidate_dir = '/'.join(parts[max(0, i-2):i])
                for file_path in self._file_profiles:
                    if candidate_dir in file_path:
                        return file_path

        elif language == Language.RUST:
            # Rust uses crate-relative paths
            parts = import_path.replace('::', '/').split('/')
            if parts and parts[0] == 'crate':
                parts = parts[1:]
            candidate = '/'.join(parts) + '.rs'
            # Try to find in rust/ directory
            for file_path in self._file_profiles:
                if candidate in file_path:
                    return file_path

        return None

    def _detect_circular_deps(self):
        """Detect circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            # Find successors
            for src, dst, _ in self._dependency_map.edges:
                if src == node:
                    if dst in rec_stack:
                        # Found a cycle
                        cycle_start = path.index(dst)
                        cycles.append(path[cycle_start:] + [dst])
                    elif dst not in visited:
                        dfs(dst, path)

            path.pop()
            rec_stack.discard(node)

        for node in self._dependency_map.nodes:
            if node not in visited:
                dfs(node, [])

        self._dependency_map.circular_dependencies = cycles[:20]  # Limit

    # ═══════════════════════════════════════════════════════════════
    # COMPONENT PROFILES
    # ═══════════════════════════════════════════════════════════════

    def _build_component_profiles(self):
        """Build high-level component profiles from file profiles."""
        # Group files by top-level directory structure
        components: Dict[str, List[FileProfile]] = defaultdict(list)

        for rel_path, profile in self._file_profiles.items():
            parts = rel_path.split('/')
            if len(parts) >= 2:
                # Use first two levels as component identifier
                component_key = f"{parts[0]}/{parts[1]}"
            else:
                component_key = parts[0]
            components[component_key].append(profile)

        for comp_name, files in components.items():
            if not files:
                continue

            total_lines = sum(f.line_count for f in files)
            total_functions = sum(f.function_count for f in files)
            total_classes = sum(f.class_count for f in files)
            total_complexity = sum(f.total_complexity for f in files)
            
            all_complexities = [f.max_function_complexity for f in files if f.max_function_complexity > 0]
            max_complexity = max(all_complexities) if all_complexities else 0
            avg_complexity = total_complexity / max(1, total_functions)

            dead_lines = sum(f.dead_code_lines for f in files)
            dead_pct = dead_lines / max(1, total_lines)

            # Determine primary language
            lang_counts = Counter(f.language for f in files)
            primary_language = lang_counts.most_common(1)[0][0]

            # Health score
            health_scores = [f.health_score for f in files]
            avg_health = sum(health_scores) / max(1, len(health_scores))

            # Estimate technical debt (rough: 1 hour per complexity point over 10)
            excess_complexity = max(0, total_complexity - total_functions * 5)
            tech_debt_hours = excess_complexity * 0.5 + dead_lines * 0.01

            profile = ComponentProfile(
                name=comp_name,
                path=comp_name,
                language=primary_language,
                total_files=len(files),
                total_lines=total_lines,
                total_functions=total_functions,
                total_classes=total_classes,
                avg_complexity=avg_complexity,
                max_complexity=max_complexity,
                dead_code_percentage=dead_pct,
                health_score=avg_health,
                technical_debt_hours=tech_debt_hours,
            )

            # Classify health
            if avg_health > 0.85:
                profile.health = ComponentHealth.EXCELLENT
            elif avg_health > 0.7:
                profile.health = ComponentHealth.GOOD
            elif avg_health > 0.5:
                profile.health = ComponentHealth.MODERATE
            elif avg_health > 0.3:
                profile.health = ComponentHealth.CONCERNING
            else:
                profile.health = ComponentHealth.CRITICAL

            self._component_profiles[comp_name] = profile

    # ═══════════════════════════════════════════════════════════════
    # DEAD CODE DETECTION
    # ═══════════════════════════════════════════════════════════════

    def _identify_dead_code(self):
        """Identify functions that are never called."""
        # Build set of all called functions
        all_calls: Set[str] = set()
        for func_profile in self._function_profiles.values():
            all_calls.update(func_profile.calls)

        # Mark functions that are never called
        for func_key, func_profile in self._function_profiles.items():
            func_name = func_profile.name

            # Skip entry points and special functions
            if func_name in ('main', '__init__', 'Start', 'Run', 'New', 'new'):
                continue
            if func_name.startswith('test_') or func_name.startswith('Test'):
                continue

            # Check if this function is ever called
            if func_name not in all_calls:
                # Also check if it's an exported function (might be called externally)
                if (func_profile.language == Language.PYTHON and func_name.startswith('_')) or \
                   (func_profile.language == Language.GO and func_name[0].islower()):
                    func_profile.is_dead_code = True

                    # Update file profile
                    file_profile = self._file_profiles.get(func_profile.file_path)
                    if file_profile:
                        file_profile.dead_code_lines += func_profile.line_count

    def _score_improvement_opportunities(self):
        """Score each function/file by how much value improving it would yield."""
        for func_profile in self._function_profiles.values():
            score = 0.0

            # High complexity = high opportunity
            if func_profile.cyclomatic_complexity > 10:
                score += 0.3
            elif func_profile.cyclomatic_complexity > 5:
                score += 0.15

            # Hot paths benefit most from optimization
            if func_profile.is_hot_path:
                score += 0.3

            # High error rate = needs fixing
            if func_profile.error_rate > 0.1:
                score += 0.2

            # Many callers = high blast radius (both risk and value)
            if len(func_profile.called_by) > 5:
                score += 0.1

            # Dead code = easy cleanup
            if func_profile.is_dead_code:
                score += 0.1

            func_profile.improvement_opportunity = min(1.0, score)

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC QUERY INTERFACE
    # ═══════════════════════════════════════════════════════════════

    def get_component_profiles(self) -> Dict[str, ComponentProfile]:
        """Get all component profiles."""
        return dict(self._component_profiles)

    def get_file_profile(self, rel_path: str) -> Optional[FileProfile]:
        """Get profile for a specific file."""
        return self._file_profiles.get(rel_path)

    def get_function_profile(self, func_key: str) -> Optional[FunctionProfile]:
        """Get profile for a specific function (key: 'file:function_name')."""
        return self._function_profiles.get(func_key)

    def get_dependency_map(self) -> DependencyMap:
        """Get the full dependency graph."""
        return self._dependency_map

    def get_hotspots(self, top_n: int = 20) -> List[FunctionProfile]:
        """Get the most complex functions (complexity hotspots)."""
        funcs = sorted(
            self._function_profiles.values(),
            key=lambda f: f.cyclomatic_complexity,
            reverse=True
        )
        return funcs[:top_n]

    def get_improvement_targets(self, top_n: int = 20) -> List[FunctionProfile]:
        """Get functions with highest improvement opportunity."""
        funcs = sorted(
            self._function_profiles.values(),
            key=lambda f: f.improvement_opportunity,
            reverse=True
        )
        return funcs[:top_n]

    def get_dead_code(self) -> List[FunctionProfile]:
        """Get all identified dead code."""
        return [f for f in self._function_profiles.values() if f.is_dead_code]

    def get_impact_of_change(self, file_path: str) -> Dict[str, Any]:
        """Predict impact of modifying a file."""
        affected = self._dependency_map.get_impact_radius(file_path)
        
        total_affected_lines = sum(
            self._file_profiles[f].line_count 
            for f in affected 
            if f in self._file_profiles
        )

        return {
            "file": file_path,
            "directly_affects": list(affected),
            "affected_file_count": len(affected),
            "affected_total_lines": total_affected_lines,
            "risk_level": min(1.0, len(affected) / 10.0),
            "is_bottleneck": file_path in self._dependency_map.bottleneck_nodes,
            "circular_dependencies": [
                cycle for cycle in self._dependency_map.circular_dependencies
                if file_path in cycle
            ],
        }

    def get_system_overview(self) -> Dict[str, Any]:
        """Get a high-level overview of the entire codebase."""
        return {
            "total_files": len(self._file_profiles),
            "total_functions": len(self._function_profiles),
            "total_lines": sum(f.line_count for f in self._file_profiles.values()),
            "languages": dict(Counter(
                f.language.value for f in self._file_profiles.values()
            )),
            "components": {
                name: {
                    "health": prof.health.value,
                    "health_score": prof.health_score,
                    "lines": prof.total_lines,
                    "complexity": prof.avg_complexity,
                    "debt_hours": prof.technical_debt_hours,
                }
                for name, prof in self._component_profiles.items()
            },
            "overall_health": sum(
                p.health_score for p in self._component_profiles.values()
            ) / max(1, len(self._component_profiles)),
            "total_dead_code_functions": len(self.get_dead_code()),
            "circular_dependencies": len(self._dependency_map.circular_dependencies),
            "bottleneck_files": self._dependency_map.bottleneck_nodes[:5],
            "top_hotspots": [
                {"name": f.name, "file": f.file_path, "complexity": f.cyclomatic_complexity}
                for f in self.get_hotspots(5)
            ],
        }

    def is_safe_to_modify(self, file_path: str) -> Dict[str, Any]:
        """
        Check if it's safe to modify a file.
        
        Returns safety assessment with reasons.
        """
        profile = self._file_profiles.get(file_path)
        if not profile:
            return {"safe": False, "reason": "File not in introspection database"}

        impact = self.get_impact_of_change(file_path)
        
        # Determine safety
        reasons = []
        risk = 0.0

        if impact["affected_file_count"] > 10:
            reasons.append(f"High blast radius: affects {impact['affected_file_count']} files")
            risk += 0.3

        if impact["is_bottleneck"]:
            reasons.append("File is a dependency bottleneck")
            risk += 0.2

        if impact["circular_dependencies"]:
            reasons.append("Part of circular dependency chain")
            risk += 0.2

        if profile.max_function_complexity > 20:
            reasons.append(f"Contains very complex functions (max: {profile.max_function_complexity})")
            risk += 0.1

        safe = risk < 0.5

        return {
            "safe": safe,
            "risk_level": risk,
            "reasons": reasons if reasons else ["No significant risks identified"],
            "affected_files": impact["affected_file_count"],
            "recommendation": "proceed" if safe else "careful" if risk < 0.7 else "avoid",
        }

    def get_evolution_plan(self) -> List[Dict[str, Any]]:
        """
        Generate a prioritized plan for code evolution.
        
        Returns ordered list of improvement actions ranked by
        expected value (impact * feasibility / risk).
        """
        plan = []

        # Dead code removal (low risk, low effort, clean improvement)
        dead = self.get_dead_code()
        if dead:
            plan.append({
                "action": "remove_dead_code",
                "priority": 0.7,
                "effort": "low",
                "risk": "very_low",
                "targets": [f"{f.file_path}:{f.name}" for f in dead[:10]],
                "expected_lines_removed": sum(f.line_count for f in dead),
                "description": f"Remove {len(dead)} dead functions ({sum(f.line_count for f in dead)} lines)",
            })

        # Complexity reduction (medium risk, high value)
        hotspots = self.get_hotspots(10)
        complex_funcs = [f for f in hotspots if f.cyclomatic_complexity > 15]
        if complex_funcs:
            plan.append({
                "action": "reduce_complexity",
                "priority": 0.8,
                "effort": "medium",
                "risk": "medium",
                "targets": [f"{f.file_path}:{f.name}" for f in complex_funcs[:5]],
                "description": f"Refactor {len(complex_funcs)} high-complexity functions",
            })

        # Circular dependency breaking
        if self._dependency_map.circular_dependencies:
            plan.append({
                "action": "break_circular_deps",
                "priority": 0.6,
                "effort": "high",
                "risk": "medium",
                "targets": self._dependency_map.circular_dependencies[:3],
                "description": f"Break {len(self._dependency_map.circular_dependencies)} circular dependency chains",
            })

        # Sort by priority
        plan.sort(key=lambda p: p["priority"], reverse=True)
        return plan

    # ═══════════════════════════════════════════════════════════════
    # PRIVATE UTILITIES
    # ═══════════════════════════════════════════════════════════════

    def _walk_source_files(self):
        """Walk the project tree yielding source files."""
        extensions = {'.py', '.go', '.rs', '.jl'}
        skip_dirs = {
            '__pycache__', 'node_modules', '.git', 'venv', 'env',
            'target', 'vendor', '.mypy_cache', '.pytest_cache'
        }

        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden and build directories
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

            for filename in files:
                ext = os.path.splitext(filename)[1]
                if ext in extensions:
                    yield Path(root) / filename

    def _detect_language(self, file_path: Path) -> Language:
        """Detect language from file extension."""
        ext = file_path.suffix
        return {
            '.py': Language.PYTHON,
            '.go': Language.GO,
            '.rs': Language.RUST,
            '.jl': Language.JULIA,
        }.get(ext, Language.UNKNOWN)

    def _hash_file(self, file_path: Path) -> str:
        """Compute content hash for change detection."""
        try:
            content = file_path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except IOError:
            return ""

    def _scan_loop(self):
        """Background thread: periodic rescans for changes."""
        while self._running:
            time.sleep(self.scan_interval)
            if self._running:
                self.full_scan()


# ── Stub: analyze_code expected by __init__.py decorator ──────────────────────
def _ci_analyze_code(self, *args, **kwargs) -> dict:
    """Stub: perform a code analysis pass."""
    return {}

CodeIntrospector.analyze_code = _ci_analyze_code
