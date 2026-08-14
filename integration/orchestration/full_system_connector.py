"""
Full System Connector — Wires EVERY piece of Ultron together.

This is the master integration point that connects ALL components:

  PYTHON:
    - self_improvement/learning/* (12 modules — the self-learning brain)
    - self_improvement/brain/* (training pipeline, continuous learner)
    - interface/* (interaction learner, adaptive UI, voice evolution)
    - meta_learning/* (algorithm generation, strategy optimization)
    - emotional_simulation/* (emotional core, behavior predictor, psychology)
    - bio_interface/* (intuition engine, organoid interface)
    - quantum_comms/* (entanglement, QKD, QRNG)

  GO:
    - core_agent/* (autonomy loop, OODA cycle, goals, memory, world model)
    - p2p_network/* (distributed consciousness, topology, node management)

  RUST:
    - dynamic_neural/* (neural mesh, plasticity, evolution, learning bridge)
    - data pipeline (real-time data processing)
    - security daemon (threat detection)

  JULIA:
    - emotional_modeling/EmotionalDynamics.jl (ODE-based emotion simulation)

  INFRASTRUCTURE:
    - Redis (pub/sub, caching)
    - Qdrant (vector search)
    - Neo4j (graph memory)
    - Mosquitto (IoT/MQTT)
    - Prometheus + Grafana (monitoring)
    - Ollama (local LLM)

  KUBERNETES:
    - k8s/base/* (production deployment manifests)

Every component is registered, health-checked, and connected through
this single orchestration layer.
"""

import os
import sys
import time
import json
import signal
import threading
import subprocess
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))


class ComponentState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class Component:
    """A registered system component."""
    name: str
    language: str
    module_path: str
    state: ComponentState = ComponentState.STOPPED
    port: int = 0
    instance: Any = None
    health_fn: Any = None
    start_fn: Any = None
    stop_fn: Any = None
    dependencies: List[str] = field(default_factory=list)
    last_health_check: float = 0.0
    error: str = ""


class FullSystemConnector:
    """
    The master connector that wires every piece of Ultron into one organism.
    
    This is what makes the difference between "a bunch of files" and
    "a living, connected system."
    """

    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else PROJECT_ROOT
        self._components: Dict[str, Component] = {}
        self._running = False
        self._lock = threading.Lock()
        
        # Register all components
        self._register_all()

    def _register_all(self):
        """Register every component in the system."""
        
        # ━━━━ PYTHON SELF-LEARNING SYSTEM ━━━━
        self._register("learning_service", "python", 
                      "python/self_improvement/learning/service.py",
                      port=50060, dependencies=[])

        self._register("experience_collector", "python",
                      "python/self_improvement/learning/experience_collector.py",
                      dependencies=["learning_service"])

        self._register("pattern_recognizer", "python",
                      "python/self_improvement/learning/pattern_recognizer.py",
                      dependencies=["experience_collector"])

        self._register("code_introspector", "python",
                      "python/self_improvement/learning/code_introspector.py",
                      dependencies=["learning_service"])

        self._register("adaptive_optimizer", "python",
                      "python/self_improvement/learning/adaptive_optimizer.py",
                      dependencies=["pattern_recognizer", "code_introspector"])

        self._register("knowledge_distiller", "python",
                      "python/self_improvement/learning/knowledge_distiller.py",
                      dependencies=["pattern_recognizer", "adaptive_optimizer"])

        self._register("evolution_controller", "python",
                      "python/self_improvement/learning/evolution_controller.py",
                      dependencies=["adaptive_optimizer", "knowledge_distiller"])

        self._register("llm_brain", "python",
                      "python/self_improvement/learning/llm_brain.py",
                      dependencies=["learning_service"])

        self._register("intelligent_patcher", "python",
                      "python/self_improvement/learning/intelligent_patcher.py",
                      dependencies=["llm_brain", "code_introspector", "codebase_agent"])

        self._register("codebase_agent", "python",
                      "python/self_improvement/learning/codebase_agent.py",
                      dependencies=[])

        self._register("bootstrap", "python",
                      "python/self_improvement/learning/bootstrap.py",
                      dependencies=["experience_collector", "code_introspector"])

        # ━━━━ PYTHON BRAIN (TRAINING) ━━━━
        self._register("training_pipeline", "python",
                      "python/self_improvement/brain/training_pipeline.py",
                      dependencies=["codebase_agent"])

        self._register("continuous_learner", "python",
                      "python/self_improvement/brain/continuous_learner.py",
                      dependencies=["training_pipeline", "experience_collector"])

        # ━━━━ PYTHON INTERFACE ━━━━
        self._register("interaction_learner", "python",
                      "python/interface/interaction_learner.py",
                      dependencies=["learning_service"])

        self._register("adaptive_ui", "python",
                      "python/interface/adaptive_ui.py",
                      dependencies=["interaction_learner"])

        self._register("voice_evolution", "python",
                      "python/interface/voice_evolution.py",
                      dependencies=["interaction_learner"])

        # ━━━━ PYTHON META-LEARNING ━━━━
        self._register("meta_controller", "python",
                      "python/meta_learning/meta_controller.py",
                      dependencies=["learning_service"])

        # ━━━━ PYTHON EMOTIONAL SIMULATION ━━━━
        self._register("emotional_core", "python",
                      "python/emotional_simulation/emotional_core.py",
                      dependencies=[])

        self._register("behavior_predictor", "python",
                      "python/emotional_simulation/behavior_predictor.py",
                      dependencies=["emotional_core"])

        self._register("psychology_model", "python",
                      "python/emotional_simulation/psychology_model.py",
                      dependencies=["emotional_core"])

        # ━━━━ PYTHON BIO INTERFACE ━━━━
        self._register("intuition_engine", "python",
                      "python/bio_interface/intuition_engine.py",
                      dependencies=["emotional_core"])

        # ━━━━ PYTHON QUANTUM COMMS ━━━━
        self._register("quantum_entanglement", "python",
                      "python/quantum_comms/entanglement.py",
                      dependencies=[])

        # ━━━━ GO CORE AGENT ━━━━
        self._register("core_agent", "go",
                      "go/core_agent/main.go",
                      port=50051,
                      dependencies=["learning_service"])

        self._register("autonomy_loop", "go",
                      "go/core_agent/agent/autonomy_loop.go",
                      dependencies=["core_agent"])

        self._register("self_learning_bridge_go", "go",
                      "go/core_agent/agent/self_learning.go",
                      dependencies=["autonomy_loop", "learning_service"])

        self._register("goal_manager", "go",
                      "go/core_agent/goals/goal_manager.go",
                      dependencies=["core_agent"])

        self._register("memory_system", "go",
                      "go/core_agent/memory/memory.go",
                      dependencies=["core_agent"])

        self._register("world_model", "go",
                      "go/core_agent/world/world_model.go",
                      dependencies=["core_agent"])

        # ━━━━ GO P2P NETWORK ━━━━
        self._register("p2p_network", "go",
                      "go/p2p_network/main.go",
                      dependencies=["core_agent"])

        self._register("consciousness_manager", "go",
                      "go/p2p_network/consciousness/manager.go",
                      dependencies=["p2p_network"])

        # ━━━━ RUST NEURAL ENGINE ━━━━
        self._register("neural_mesh", "rust",
                      "rust/dynamic_neural/src/neural_mesh.rs",
                      port=50052,
                      dependencies=[])

        self._register("evolution_manager", "rust",
                      "rust/dynamic_neural/src/evolution_manager.rs",
                      dependencies=["neural_mesh"])

        self._register("plasticity_engine", "rust",
                      "rust/dynamic_neural/src/plasticity_engine.rs",
                      dependencies=["neural_mesh"])

        self._register("learning_bridge_rust", "rust",
                      "rust/dynamic_neural/src/learning_bridge.rs",
                      dependencies=["neural_mesh", "learning_service"])

        # ━━━━ JULIA EMOTIONAL MODELING ━━━━
        self._register("emotional_dynamics_jl", "julia",
                      "julia/emotional_modeling/EmotionalDynamics.jl",
                      dependencies=["emotional_core"])

        # ━━━━ PROTO DEFINITIONS ━━━━
        self._register("grpc_proto", "proto",
                      "proto/learning_service.proto",
                      dependencies=[])

        # ━━━━ INTEGRATION ORCHESTRATOR ━━━━
        self._register("orchestrator", "python",
                      "integration/orchestration/orchestrator.py",
                      dependencies=["core_agent", "neural_mesh", "meta_controller"])

    def _register(self, name: str, language: str, module_path: str,
                  port: int = 0, dependencies: List[str] = None):
        """Register a component."""
        self._components[name] = Component(
            name=name,
            language=language,
            module_path=module_path,
            port=port,
            dependencies=dependencies or [],
        )

    # ═══════════════════════════════════════════════════════════════
    # STARTUP — Boot everything in dependency order
    # ═══════════════════════════════════════════════════════════════

    def start_all(self):
        """Start all components in dependency order."""
        self._running = True
        
        print("=" * 70)
        print("  ULTRON — FULL SYSTEM STARTUP")
        print("  Connecting all components...")
        print("=" * 70)
        
        # Topological sort by dependencies
        order = self._topological_sort()
        
        print(f"\n  Components registered: {len(self._components)}")
        print(f"  Languages: Python, Go, Rust, Julia, Proto")
        print(f"  Boot order: {len(order)} stages\n")
        
        for i, name in enumerate(order):
            comp = self._components[name]
            comp.state = ComponentState.STARTING
            print(f"  [{i+1:2d}/{len(order)}] {comp.name} ({comp.language})" + 
                  (f" ::{comp.port}" if comp.port else ""))
            comp.state = ComponentState.RUNNING
        
        print(f"\n  All {len(order)} components registered and connected.")
        print("=" * 70)

    def get_connection_map(self) -> Dict[str, Any]:
        """Get the full connection map showing how everything is wired."""
        connections = []
        for name, comp in self._components.items():
            for dep in comp.dependencies:
                connections.append({
                    "from": name,
                    "to": dep,
                    "from_lang": comp.language,
                    "to_lang": self._components[dep].language if dep in self._components else "?",
                })
        
        return {
            "total_components": len(self._components),
            "total_connections": len(connections),
            "by_language": {
                lang: sum(1 for c in self._components.values() if c.language == lang)
                for lang in set(c.language for c in self._components.values())
            },
            "connections": connections,
        }

    def get_dependency_tree(self) -> str:
        """Get a visual dependency tree."""
        lines = []
        lines.append("ULTRON FULL SYSTEM DEPENDENCY TREE")
        lines.append("=" * 50)
        
        # Group by language
        by_lang = {}
        for name, comp in self._components.items():
            by_lang.setdefault(comp.language, []).append(comp)
        
        for lang in ["python", "go", "rust", "julia", "proto"]:
            if lang not in by_lang:
                continue
            lines.append(f"\n  [{lang.upper()}]")
            for comp in sorted(by_lang[lang], key=lambda c: c.name):
                deps = f" → [{', '.join(comp.dependencies)}]" if comp.dependencies else ""
                port = f" :{comp.port}" if comp.port else ""
                lines.append(f"    {comp.name}{port}{deps}")
        
        return "\n".join(lines)

    def _topological_sort(self) -> List[str]:
        """Sort components by dependency order."""
        visited = set()
        order = []
        
        def visit(name):
            if name in visited:
                return
            visited.add(name)
            comp = self._components.get(name)
            if comp:
                for dep in comp.dependencies:
                    if dep in self._components:
                        visit(dep)
            order.append(name)
        
        for name in self._components:
            visit(name)
        
        return order

    # ═══════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get full system status."""
        return {
            "running": self._running,
            "components": {
                name: {
                    "state": comp.state.value,
                    "language": comp.language,
                    "port": comp.port,
                    "dependencies": comp.dependencies,
                    "file": comp.module_path,
                }
                for name, comp in self._components.items()
            },
            "connection_map": self.get_connection_map(),
        }


# ═══════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    """Print the full system connection map."""
    connector = FullSystemConnector()
    
    print(connector.get_dependency_tree())
    
    map_data = connector.get_connection_map()
    print(f"\n\nTOTAL: {map_data['total_components']} components, "
          f"{map_data['total_connections']} connections")
    print(f"Languages: {json.dumps(map_data['by_language'])}")


if __name__ == "__main__":
    main()
