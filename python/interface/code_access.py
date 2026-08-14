"""
Code Self-Access — Gives Ultron the ability to read and understand its own source code.

This module provides:
  - List all source files
  - Read any file in the codebase
  - Search for patterns across the codebase
  - Get code statistics
  - Understand its own architecture

This is what makes Ultron SELF-AWARE of its own implementation.
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional


PROJECT_ROOT = Path(__file__).parent.parent.parent  # ultron/


def list_source_files(language: str = None) -> List[Dict[str, Any]]:
    """List all source files in the project."""
    extensions = {
        "go": [".go"],
        "rust": [".rs"],
        "python": [".py"],
        "julia": [".jl"],
        "proto": [".proto"],
        "yaml": [".yaml", ".yml"],
    }
    
    if language and language in extensions:
        exts = extensions[language]
    else:
        exts = [ext for group in extensions.values() for ext in group]
    
    files = []
    for path in sorted(PROJECT_ROOT.rglob("*")):
        if path.is_file() and path.suffix in exts:
            rel = path.relative_to(PROJECT_ROOT)
            try:
                lines = len(path.read_text().splitlines())
            except Exception:
                lines = 0
            files.append({
                "path": str(rel),
                "lines": lines,
                "size_kb": round(path.stat().st_size / 1024, 1),
                "language": path.suffix.lstrip('.'),
            })
    
    return files


def read_file(relative_path: str) -> Optional[str]:
    """Read a source file from the codebase."""
    full_path = PROJECT_ROOT / relative_path
    
    # Security: only allow reading within project
    try:
        full_path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return None  # Path escape attempt
    
    if full_path.exists() and full_path.is_file():
        try:
            return full_path.read_text()
        except Exception:
            return None
    return None


def search_code(pattern: str, language: str = None, max_results: int = 20) -> List[Dict[str, Any]]:
    """Search across the codebase for a pattern."""
    results = []
    
    files = list_source_files(language)
    
    for file_info in files:
        content = read_file(file_info["path"])
        if content is None:
            continue
        
        for i, line in enumerate(content.splitlines(), 1):
            if pattern.lower() in line.lower():
                results.append({
                    "file": file_info["path"],
                    "line": i,
                    "content": line.strip()[:120],
                })
                
                if len(results) >= max_results:
                    return results
    
    return results


def get_architecture_summary() -> Dict[str, Any]:
    """Get a summary of the codebase architecture."""
    files = list_source_files()
    
    by_language = {}
    total_lines = 0
    
    for f in files:
        lang = f["language"]
        if lang not in by_language:
            by_language[lang] = {"files": 0, "lines": 0}
        by_language[lang]["files"] += 1
        by_language[lang]["lines"] += f["lines"]
        total_lines += f["lines"]
    
    # Get key components
    components = {
        "brain": "go/core_agent/agent/autonomy_loop.go",
        "goals": "go/core_agent/goals/goal_manager.go",
        "memory": "go/core_agent/embedded/runtime/embedded_runtime.go",
        "world_model": "go/core_agent/world/world_model.go",
        "web_driver": "go/core_agent/actions/web/web_driver.go",
        "iot_driver": "go/core_agent/actions/iot/iot_driver.go",
        "cloud_driver": "go/core_agent/actions/cloud/cloud_driver.go",
        "security": "rust/security_daemon/src/lib.rs",
        "neural_mesh": "rust/dynamic_neural/src/neural_mesh.rs",
        "meta_learning": "python/meta_learning/meta_controller.py",
        "self_improvement": "python/self_improvement/core/improvement_loop.py",
        "ownership": "go/core_agent/ownership/ownership.go",
    }
    
    return {
        "total_files": len(files),
        "total_lines": total_lines,
        "languages": by_language,
        "key_components": components,
        "project_root": str(PROJECT_ROOT),
    }


def get_component_code(component_name: str) -> Optional[str]:
    """Get the source code of a specific component by name."""
    component_map = {
        "brain": "go/core_agent/agent/autonomy_loop.go",
        "autonomy": "go/core_agent/agent/autonomy_loop.go",
        "goals": "go/core_agent/goals/goal_manager.go",
        "memory": "go/core_agent/memory/memory.go",
        "embedded_memory": "go/core_agent/embedded/runtime/embedded_runtime.go",
        "kv_store": "go/core_agent/embedded/store/kv_store.go",
        "graph": "go/core_agent/embedded/graph/graph_engine.go",
        "vector": "go/core_agent/embedded/vector/vector_store.go",
        "world": "go/core_agent/world/world_model.go",
        "web": "go/core_agent/actions/web/web_driver.go",
        "iot": "go/core_agent/actions/iot/iot_driver.go",
        "cloud": "go/core_agent/actions/cloud/cloud_driver.go",
        "physical": "go/core_agent/actions/physical/environment_controller.go",
        "mesh": "go/core_agent/actions/mesh/discovery.go",
        "compute": "go/core_agent/actions/compute/load_balancer.go",
        "security": "rust/security_daemon/src/lib.rs",
        "encryption": "rust/security_daemon/src/encryption.rs",
        "threat": "rust/security_daemon/src/threat_monitor.rs",
        "neural": "rust/dynamic_neural/src/neural_mesh.rs",
        "plasticity": "rust/dynamic_neural/src/plasticity_engine.rs",
        "evolution": "rust/dynamic_neural/src/evolution_manager.rs",
        "neuromorphic": "rust/neuromorphic/src/lib.rs",
        "meta_learning": "python/meta_learning/meta_controller.py",
        "algorithm_generator": "python/meta_learning/algorithm_generator.py",
        "self_improvement": "python/self_improvement/core/improvement_loop.py",
        "emotional": "python/emotional_simulation/emotional_core.py",
        "psychology": "python/emotional_simulation/psychology_model.py",
        "quantum": "python/quantum_comms/qkd.py",
        "bio": "python/bio_interface/organoid_interface.py",
        "ownership": "go/core_agent/ownership/ownership.go",
        "grpc": "go/core_agent/grpc_service.go",
        "interface": "python/interface/server.py",
        "proto": "proto/ultron_core.proto",
    }
    
    path = component_map.get(component_name.lower())
    if path:
        return read_file(path)
    return None
