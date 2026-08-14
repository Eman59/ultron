"""
Patch Generator - Generates code improvements based on diagnosed issues.

This is the creative engine of self-improvement. Given a diagnosis
(e.g., "component X is slow"), it generates actual code patches that
could fix the problem.

Patch strategies:
  - Algorithmic optimization (replace O(n²) with O(n log n))
  - Caching (add memoization to repeated computations)
  - Parallelization (convert sequential to parallel)
  - Error handling (add retry logic, circuit breakers)
  - Parameter tuning (adjust hyperparameters based on performance)
  - Architecture changes (restructure data flow)
"""

import hashlib
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import ast
import re


@dataclass
class CodePatch:
    """A generated code modification."""
    patch_id: str
    name: str
    description: str
    target_file: str
    patch_type: str  # "replace", "append", "new_file"
    old_code: str = ""     # Code to replace (for "replace" type)
    new_code: str = ""     # New code
    diagnosis_ref: str = ""  # What diagnosis this addresses
    strategy: str = ""     # What improvement strategy was used
    estimated_impact: float = 0.0  # Expected improvement (0-1)
    risk_level: float = 0.0  # How risky is this change (0-1)
    created_at: float = field(default_factory=time.time)


class PatchGenerator:
    """
    Generates code patches to improve the system.
    
    Uses pattern matching and code analysis to create targeted improvements.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.generated_count = 0
        
        # Strategy registry
        self.strategies = {
            "underperformance": self._strategy_optimize,
            "recurring_failure": self._strategy_fix_error,
            "latency_bottleneck": self._strategy_reduce_latency,
            "inefficiency": self._strategy_improve_efficiency,
        }

    def generate_patch(self, diagnosis: Dict[str, Any]) -> Optional[CodePatch]:
        """
        Generate a patch for a given diagnosis.
        
        Args:
            diagnosis: Dict with keys: component, score, type, severity, description
            
        Returns:
            CodePatch or None if no patch could be generated
        """
        diagnosis_type = diagnosis.get("type", "")
        
        strategy_fn = self.strategies.get(diagnosis_type)
        if not strategy_fn:
            return None
        
        patch = strategy_fn(diagnosis)
        
        if patch:
            self.generated_count += 1
            patch.patch_id = hashlib.md5(
                f"{patch.target_file}:{patch.new_code[:50]}:{time.time()}".encode()
            ).hexdigest()[:12]
        
        return patch

    def _strategy_optimize(self, diagnosis: Dict[str, Any]) -> Optional[CodePatch]:
        """Generate optimization patches for underperforming components."""
        
        component = diagnosis.get("component", "")
        
        # Find the component's source file
        source_file = self._find_source_file(component)
        if not source_file:
            return None
        
        # Read the file
        content = self._read_file(source_file)
        if not content:
            return None
        
        # Apply optimization patterns
        optimizations = [
            self._optimize_add_caching(content, component),
            self._optimize_batch_operations(content, component),
            self._optimize_reduce_allocations(content, component),
        ]
        
        # Return first successful optimization
        for opt in optimizations:
            if opt:
                opt.target_file = source_file
                opt.diagnosis_ref = diagnosis.get("description", "")
                return opt
        
        return None

    def _strategy_fix_error(self, diagnosis: Dict[str, Any]) -> Optional[CodePatch]:
        """Generate patches to fix recurring errors."""
        
        component = diagnosis.get("component", "")
        error_pattern = diagnosis.get("error_pattern", "")
        
        source_file = self._find_source_file(component)
        if not source_file:
            return None
        
        content = self._read_file(source_file)
        if not content:
            return None
        
        # Strategy: Add retry logic around the failing operation
        patch = self._add_retry_wrapper(content, component, error_pattern)
        if patch:
            patch.target_file = source_file
            patch.diagnosis_ref = diagnosis.get("description", "")
        
        return patch

    def _strategy_reduce_latency(self, diagnosis: Dict[str, Any]) -> Optional[CodePatch]:
        """Generate patches to reduce component latency."""
        
        component = diagnosis.get("component", "")
        current_latency = diagnosis.get("current_latency", 0)
        
        source_file = self._find_source_file(component)
        if not source_file:
            return None
        
        content = self._read_file(source_file)
        if not content:
            return None
        
        # Strategy: Add async processing or result caching
        patch = self._add_async_cache(content, component)
        if patch:
            patch.target_file = source_file
            patch.diagnosis_ref = diagnosis.get("description", "")
            patch.estimated_impact = min(0.5, current_latency / 1000.0)
        
        return patch

    def _strategy_improve_efficiency(self, diagnosis: Dict[str, Any]) -> Optional[CodePatch]:
        """Generate patches to improve resource efficiency."""
        
        # Create a new utility module for resource management
        return CodePatch(
            patch_id="",
            name="add_resource_pooling",
            description="Add connection/resource pooling to reduce allocation overhead",
            target_file="python/meta_learning/_resource_pool.py",
            patch_type="new_file",
            new_code=self._generate_resource_pool_code(),
            strategy="resource_pooling",
            estimated_impact=0.2,
            risk_level=0.1,
        )

    # ═══════════════════════════════════════════════════════════════
    # OPTIMIZATION PATTERNS
    # ═══════════════════════════════════════════════════════════════

    def _optimize_add_caching(self, content: str, component: str) -> Optional[CodePatch]:
        """Add functools.lru_cache to expensive pure functions."""
        
        # Find functions that could benefit from caching
        # Pattern: function called multiple times with same args
        pattern = r'def\s+(_?calculate_\w+|_?compute_\w+|_?get_\w+)\s*\(self'
        matches = re.finditer(pattern, content)
        
        for match in matches:
            func_name = match.group(1)
            # Check if it already has caching
            if f"@lru_cache" not in content[:match.start()]:
                # Find the function definition
                func_start = content.rfind('\n', 0, match.start()) + 1
                indent = len(content[func_start:match.start()])
                
                old_line = content[func_start:content.find('\n', match.start())+1]
                new_line = ' ' * indent + "@functools.lru_cache(maxsize=128)\n" + old_line
                
                # Also need to add import
                if "import functools" not in content:
                    new_line = "import functools\n\n" + new_line if func_start < 100 else new_line
                
                return CodePatch(
                    patch_id="",
                    name=f"cache_{func_name}",
                    description=f"Add LRU cache to {func_name} for repeated calls",
                    target_file="",
                    patch_type="replace",
                    old_code=old_line,
                    new_code=new_line,
                    strategy="caching",
                    estimated_impact=0.15,
                    risk_level=0.2,
                )
        
        return None

    def _optimize_batch_operations(self, content: str, component: str) -> Optional[CodePatch]:
        """Convert individual operations to batch where possible."""
        
        # Find loops that could be vectorized
        pattern = r'for\s+\w+\s+in\s+range\(len\((\w+)\)\):'
        match = re.search(pattern, content)
        
        if match:
            array_name = match.group(1)
            loop_start = match.start()
            
            # Check if it's doing element-wise operations
            # This is a simplified check
            next_lines = content[loop_start:loop_start+200]
            if f"{array_name}[" in next_lines:
                return CodePatch(
                    patch_id="",
                    name=f"vectorize_{array_name}_loop",
                    description=f"Vectorize loop over {array_name} using numpy",
                    target_file="",
                    patch_type="append",
                    new_code=f"\n# TODO: Vectorize the loop over {array_name} using np.vectorize or direct array ops\n",
                    strategy="vectorization",
                    estimated_impact=0.25,
                    risk_level=0.3,
                )
        
        return None

    def _optimize_reduce_allocations(self, content: str, component: str) -> Optional[CodePatch]:
        """Reduce memory allocations in hot paths."""
        
        # Find repeated list/dict creation in loops
        pattern = r'(for\s+\w+\s+in\s+.+:\s*\n\s+)(\w+)\s*=\s*(\[\]|{}|list\(\)|dict\(\))'
        match = re.search(pattern, content)
        
        if match:
            var_name = match.group(2)
            return CodePatch(
                patch_id="",
                name=f"preallocate_{var_name}",
                description=f"Pre-allocate {var_name} outside loop to reduce GC pressure",
                target_file="",
                patch_type="append",
                new_code=f"\n# OPTIMIZATION: Pre-allocate {var_name} before loop and .clear() instead of re-creating\n",
                strategy="allocation_reduction",
                estimated_impact=0.1,
                risk_level=0.1,
            )
        
        return None

    def _add_retry_wrapper(self, content: str, component: str, error: str) -> Optional[CodePatch]:
        """Add retry logic around failing operations."""
        
        retry_code = f'''
# Auto-generated retry wrapper for {component}
import time
from functools import wraps

def retry_on_failure(max_retries=3, delay=1.0, backoff=2.0):
    """Retry decorator with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        raise
                    time.sleep(current_delay)
                    current_delay *= backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator
'''
        
        return CodePatch(
            patch_id="",
            name=f"retry_wrapper_{component}",
            description=f"Add retry logic for {component} (error: {error[:50]})",
            target_file="",
            patch_type="append",
            new_code=retry_code,
            strategy="error_handling",
            estimated_impact=0.2,
            risk_level=0.15,
        )

    def _add_async_cache(self, content: str, component: str) -> Optional[CodePatch]:
        """Add an async result cache."""
        
        cache_code = f'''
# Auto-generated async cache for {component}
from collections import OrderedDict
import time

class AsyncResultCache:
    """Time-bounded LRU cache for async results."""
    
    def __init__(self, maxsize=256, ttl_seconds=60):
        self._cache = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl_seconds
    
    def get(self, key):
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                self._cache.move_to_end(key)
                return value
            else:
                del self._cache[key]
        return None
    
    def put(self, key, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.time())
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

_{component}_cache = AsyncResultCache(maxsize=512, ttl_seconds=30)
'''
        
        return CodePatch(
            patch_id="",
            name=f"async_cache_{component}",
            description=f"Add async result cache to reduce latency in {component}",
            target_file="",
            patch_type="append",
            new_code=cache_code,
            strategy="caching",
            estimated_impact=0.3,
            risk_level=0.15,
        )

    def _generate_resource_pool_code(self) -> str:
        """Generate a resource pooling module."""
        return '''"""
Auto-generated Resource Pool — reduces allocation overhead.
Generated by Ultron Self-Improvement Engine.
"""

import threading
from collections import deque
from typing import Any, Callable, Optional


class ResourcePool:
    """Generic object pool for expensive-to-create resources."""
    
    def __init__(self, factory: Callable[[], Any], max_size: int = 20):
        self._factory = factory
        self._max_size = max_size
        self._pool: deque = deque()
        self._lock = threading.Lock()
        self._created = 0
    
    def acquire(self) -> Any:
        """Get a resource from the pool or create new one."""
        with self._lock:
            if self._pool:
                return self._pool.popleft()
            self._created += 1
            return self._factory()
    
    def release(self, resource: Any):
        """Return a resource to the pool."""
        with self._lock:
            if len(self._pool) < self._max_size:
                self._pool.append(resource)
    
    @property
    def stats(self) -> dict:
        return {
            "pool_size": len(self._pool),
            "max_size": self._max_size,
            "total_created": self._created,
        }
'''

    # ═══════════════════════════════════════════════════════════════
    # FILE UTILITIES
    # ═══════════════════════════════════════════════════════════════

    def _find_source_file(self, component: str) -> Optional[str]:
        """Find the source file for a component name."""
        
        # Map component names to file paths
        component_map = {
            "algorithm_generator": "python/meta_learning/algorithm_generator.py",
            "strategy_optimizer": "python/meta_learning/strategy_optimizer.py",
            "curriculum_designer": "python/meta_learning/curriculum_designer.py",
            "transfer_manager": "python/meta_learning/transfer_manager.py",
            "meta_controller": "python/meta_learning/meta_controller.py",
            "emotional_core": "python/emotional_simulation/emotional_core.py",
            "psychology_model": "python/emotional_simulation/psychology_model.py",
            "behavior_predictor": "python/emotional_simulation/behavior_predictor.py",
        }
        
        if component in component_map:
            return component_map[component]
        
        # Try to find by name pattern
        for path in self.project_root.rglob("*.py"):
            if component.replace("_", "") in path.stem.replace("_", ""):
                return str(path.relative_to(self.project_root))
        
        return None

    def _read_file(self, relative_path: str) -> Optional[str]:
        """Read a file from the project."""
        full_path = self.project_root / relative_path
        if full_path.exists():
            return full_path.read_text()
        return None
