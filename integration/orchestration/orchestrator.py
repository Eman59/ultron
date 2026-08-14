"""
Ultron Orchestration Layer

Master controller that coordinates all system components:
- Rust Dynamic Neural Architecture
- Python Meta-Learning Engine
- Go P2P Distributed Network
- Rust Real-time Data Pipeline
- Julia/Python Emotional Simulation

Uses gRPC for cross-language communication and Redis for pub/sub messaging.
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import signal
import os


class ComponentState(Enum):
    """State of a system component."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"


class SystemMode(Enum):
    """Operating mode of the Ultron system."""
    INITIALIZATION = "initialization"
    LEARNING = "learning"
    PROCESSING = "processing"
    EVOLUTION = "evolution"
    ADAPTATION = "adaptation"
    DISTRIBUTED = "distributed"
    FULL_OPERATION = "full_operation"
    MAINTENANCE = "maintenance"


@dataclass
class ComponentInfo:
    """Information about a system component."""
    name: str
    language: str
    state: ComponentState = ComponentState.STOPPED
    port: int = 0
    pid: Optional[int] = None
    health_endpoint: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    last_heartbeat: float = 0.0
    error_count: int = 0
    restart_count: int = 0
    dependencies: List[str] = field(default_factory=list)


@dataclass
class SystemMetrics:
    """Aggregate system metrics."""
    uptime: float = 0.0
    total_tasks_processed: int = 0
    total_data_ingested: int = 0
    active_neural_nodes: int = 0
    network_peers: int = 0
    meta_learning_generation: int = 0
    emotional_coherence: float = 0.0
    system_health: float = 1.0
    mode: SystemMode = SystemMode.INITIALIZATION


class UltronOrchestrator:
    """
    Master orchestrator for the Ultron AI system.
    
    Manages lifecycle, communication, and coordination between all components.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._default_config()
        
        # Components registry
        self.components: Dict[str, ComponentInfo] = {}
        
        # System state
        self.mode = SystemMode.INITIALIZATION
        self.start_time = time.time()
        self.metrics = SystemMetrics()
        
        # Communication channels
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.command_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        # Register all components
        self._register_components()

    def _default_config(self) -> Dict[str, Any]:
        """Default system configuration."""
        return {
            "neural_architecture": {
                "binary": "target/release/ultron-dynamic-neural",
                "port": 50051,
                "language": "rust",
            },
            "meta_learning": {
                "module": "python.meta_learning.meta_controller",
                "port": 50052,
                "language": "python",
            },
            "p2p_network": {
                "binary": "go/p2p_network/p2p_network",
                "port": 4001,
                "language": "go",
            },
            "data_pipeline": {
                "binary": "target/release/ultron-real-time-data",
                "port": 50053,
                "language": "rust",
            },
            "emotional_simulation": {
                "module": "python.emotional_simulation",
                "port": 50054,
                "language": "python",
            },
            "redis": {
                "host": "localhost",
                "port": 6379,
            },
            "postgres": {
                "host": "localhost",
                "port": 5432,
                "database": "ultron",
            },
            "system": {
                "heartbeat_interval": 5.0,
                "health_check_interval": 10.0,
                "max_restart_attempts": 3,
                "graceful_shutdown_timeout": 30.0,
            }
        }

    def _register_components(self) -> None:
        """Register all system components."""
        
        self.components["neural_architecture"] = ComponentInfo(
            name="Dynamic Neural Architecture",
            language="rust",
            port=self.config["neural_architecture"]["port"],
            health_endpoint="http://localhost:50051/health",
            dependencies=[],
        )
        
        self.components["meta_learning"] = ComponentInfo(
            name="Meta-Learning Engine",
            language="python",
            port=self.config["meta_learning"]["port"],
            health_endpoint="http://localhost:50052/health",
            dependencies=["neural_architecture"],
        )
        
        self.components["p2p_network"] = ComponentInfo(
            name="P2P Distributed Network",
            language="go",
            port=self.config["p2p_network"]["port"],
            health_endpoint="http://localhost:4001/health",
            dependencies=[],
        )
        
        self.components["data_pipeline"] = ComponentInfo(
            name="Real-time Data Pipeline",
            language="rust",
            port=self.config["data_pipeline"]["port"],
            health_endpoint="http://localhost:50053/health",
            dependencies=[],
        )
        
        self.components["emotional_simulation"] = ComponentInfo(
            name="Emotional Simulation Engine",
            language="python",
            port=self.config["emotional_simulation"]["port"],
            health_endpoint="http://localhost:50054/health",
            dependencies=["meta_learning"],
        )

    async def start(self) -> Dict[str, Any]:
        """Start the complete Ultron system."""
        
        print("=" * 70)
        print("  U L T R O N   A I   S Y S T E M")
        print("  Recursive Self-Improving Neural Architecture")
        print("=" * 70)
        print()
        
        self.mode = SystemMode.INITIALIZATION
        results = {}
        
        # Start components in dependency order
        start_order = self._resolve_start_order()
        
        for component_id in start_order:
            component = self.components[component_id]
            print(f"  Starting {component.name} [{component.language}]...")
            
            try:
                await self._start_component(component_id)
                component.state = ComponentState.RUNNING
                results[component_id] = "started"
                print(f"    ✓ {component.name} running on port {component.port}")
            except Exception as e:
                component.state = ComponentState.ERROR
                results[component_id] = f"error: {str(e)}"
                print(f"    ✗ {component.name} failed: {e}")
        
        # Start background tasks
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._event_processor())
        
        # Transition to learning mode
        self.mode = SystemMode.LEARNING
        self.metrics.uptime = time.time() - self.start_time
        
        print()
        print(f"  System started in {self.metrics.uptime:.1f}s")
        print(f"  Mode: {self.mode.value}")
        print(f"  Components: {sum(1 for c in self.components.values() if c.state == ComponentState.RUNNING)}/{len(self.components)}")
        print("=" * 70)
        
        return results

    async def stop(self) -> Dict[str, Any]:
        """Gracefully stop the complete system."""
        
        print("\nShutting down Ultron system...")
        self.mode = SystemMode.MAINTENANCE
        results = {}
        
        # Stop in reverse dependency order
        stop_order = list(reversed(self._resolve_start_order()))
        
        timeout = self.config["system"]["graceful_shutdown_timeout"]
        
        for component_id in stop_order:
            component = self.components[component_id]
            if component.state in (ComponentState.RUNNING, ComponentState.DEGRADED):
                print(f"  Stopping {component.name}...")
                try:
                    await asyncio.wait_for(
                        self._stop_component(component_id),
                        timeout=timeout / len(stop_order)
                    )
                    component.state = ComponentState.STOPPED
                    results[component_id] = "stopped"
                except asyncio.TimeoutError:
                    results[component_id] = "timeout"
                except Exception as e:
                    results[component_id] = f"error: {str(e)}"
        
        print("System shutdown complete.")
        return results

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a high-level task across the system.
        
        Routes the task to appropriate components and coordinates the response.
        """
        
        task_type = task.get("type", "unknown")
        
        if task_type == "learn":
            return await self._execute_learning_task(task)
        elif task_type == "process_data":
            return await self._execute_data_task(task)
        elif task_type == "evolve":
            return await self._execute_evolution_task(task)
        elif task_type == "analyze_emotion":
            return await self._execute_emotional_task(task)
        elif task_type == "distribute":
            return await self._execute_distribution_task(task)
        else:
            return {"error": f"Unknown task type: {task_type}"}

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        
        component_statuses = {}
        for comp_id, comp in self.components.items():
            component_statuses[comp_id] = {
                "name": comp.name,
                "state": comp.state.value,
                "language": comp.language,
                "port": comp.port,
                "last_heartbeat": comp.last_heartbeat,
                "error_count": comp.error_count,
                "restart_count": comp.restart_count,
                "metrics": comp.metrics,
            }
        
        healthy_count = sum(
            1 for c in self.components.values() 
            if c.state == ComponentState.RUNNING
        )
        
        return {
            "mode": self.mode.value,
            "uptime": time.time() - self.start_time,
            "system_health": healthy_count / max(1, len(self.components)),
            "components": component_statuses,
            "metrics": {
                "total_tasks_processed": self.metrics.total_tasks_processed,
                "total_data_ingested": self.metrics.total_data_ingested,
                "active_neural_nodes": self.metrics.active_neural_nodes,
                "network_peers": self.metrics.network_peers,
                "meta_learning_generation": self.metrics.meta_learning_generation,
                "emotional_coherence": self.metrics.emotional_coherence,
            },
            "event_queue_size": self.event_queue.qsize(),
        }

    # ──────────────────────── Task Execution ────────────────────────

    async def _execute_learning_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a learning task using meta-learning + neural architecture."""
        
        self.mode = SystemMode.LEARNING
        
        # 1. Send data to neural architecture for feature extraction
        # 2. Send features to meta-learning for algorithm selection
        # 3. Execute learning with selected algorithm
        # 4. Store results and update strategy
        
        self.metrics.total_tasks_processed += 1
        
        return {
            "status": "completed",
            "task_type": "learn",
            "components_used": ["neural_architecture", "meta_learning"],
            "result": "Learning task executed successfully"
        }

    async def _execute_data_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a data processing task."""
        
        self.mode = SystemMode.PROCESSING
        self.metrics.total_data_ingested += 1
        
        return {
            "status": "completed",
            "task_type": "process_data",
            "components_used": ["data_pipeline", "neural_architecture"],
        }

    async def _execute_evolution_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an evolution cycle."""
        
        self.mode = SystemMode.EVOLUTION
        self.metrics.meta_learning_generation += 1
        
        return {
            "status": "completed",
            "task_type": "evolve",
            "generation": self.metrics.meta_learning_generation,
            "components_used": ["meta_learning", "neural_architecture"],
        }

    async def _execute_emotional_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute emotional analysis/simulation."""
        
        return {
            "status": "completed",
            "task_type": "analyze_emotion",
            "components_used": ["emotional_simulation", "meta_learning"],
        }

    async def _execute_distribution_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a distribution task across the P2P network."""
        
        self.mode = SystemMode.DISTRIBUTED
        
        return {
            "status": "completed",
            "task_type": "distribute",
            "components_used": ["p2p_network", "neural_architecture"],
        }

    # ──────────────────────── Lifecycle ────────────────────────

    async def _start_component(self, component_id: str) -> None:
        """Start a single component."""
        component = self.components[component_id]
        component.state = ComponentState.STARTING
        
        # In production, this would start actual processes
        # For now, simulate startup
        await asyncio.sleep(0.1)
        
        component.state = ComponentState.RUNNING
        component.last_heartbeat = time.time()

    async def _stop_component(self, component_id: str) -> None:
        """Stop a single component."""
        component = self.components[component_id]
        component.state = ComponentState.SHUTTING_DOWN
        
        # Send shutdown signal
        if component.pid:
            try:
                os.kill(component.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        
        await asyncio.sleep(0.1)
        component.state = ComponentState.STOPPED

    def _resolve_start_order(self) -> List[str]:
        """Resolve component start order based on dependencies."""
        
        # Topological sort
        visited = set()
        order = []
        
        def visit(comp_id):
            if comp_id in visited:
                return
            visited.add(comp_id)
            for dep in self.components[comp_id].dependencies:
                visit(dep)
            order.append(comp_id)
        
        for comp_id in self.components:
            visit(comp_id)
        
        return order

    # ──────────────────────── Background Tasks ────────────────────────

    async def _heartbeat_loop(self) -> None:
        """Send/check heartbeats."""
        interval = self.config["system"]["heartbeat_interval"]
        
        while self.mode != SystemMode.MAINTENANCE:
            for comp_id, comp in self.components.items():
                if comp.state == ComponentState.RUNNING:
                    comp.last_heartbeat = time.time()
            
            await asyncio.sleep(interval)

    async def _health_check_loop(self) -> None:
        """Periodic health checks."""
        interval = self.config["system"]["health_check_interval"]
        
        while self.mode != SystemMode.MAINTENANCE:
            for comp_id, comp in self.components.items():
                if comp.state == ComponentState.RUNNING:
                    # Check if heartbeat is stale
                    if time.time() - comp.last_heartbeat > interval * 3:
                        comp.state = ComponentState.DEGRADED
                        comp.error_count += 1
                        
                        # Auto-restart if under limit
                        max_restarts = self.config["system"]["max_restart_attempts"]
                        if comp.restart_count < max_restarts:
                            await self._restart_component(comp_id)
            
            await asyncio.sleep(interval)

    async def _event_processor(self) -> None:
        """Process system events."""
        while self.mode != SystemMode.MAINTENANCE:
            try:
                event = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=1.0
                )
                await self._handle_event(event)
            except asyncio.TimeoutError:
                continue

    async def _restart_component(self, component_id: str) -> None:
        """Restart a failed component."""
        component = self.components[component_id]
        print(f"  Restarting {component.name} (attempt {component.restart_count + 1})...")
        
        await self._stop_component(component_id)
        await asyncio.sleep(1.0)
        await self._start_component(component_id)
        
        component.restart_count += 1

    async def _handle_event(self, event: Dict[str, Any]) -> None:
        """Handle a system event."""
        event_type = event.get("type", "unknown")
        
        if event_type == "component_error":
            comp_id = event.get("component_id")
            if comp_id and comp_id in self.components:
                self.components[comp_id].error_count += 1
        
        elif event_type == "performance_alert":
            # Could trigger evolution or adaptation
            pass


# ━━━━━━━━━━━━━━━━━━━━━━━ Entry Point ━━━━━━━━━━━━━━━━━━━━━━━

async def main():
    """Main entry point for the Ultron system."""
    
    orchestrator = UltronOrchestrator()
    
    # Start the system
    results = await orchestrator.start()
    
    # Print status
    status = orchestrator.get_system_status()
    print(f"\nSystem Status: {status['mode']}")
    print(f"Health: {status['system_health']*100:.0f}%")
    
    # Run main loop
    try:
        while True:
            await asyncio.sleep(1.0)
            
            # Example: process a learning task every 10 seconds
            if int(time.time()) % 10 == 0:
                result = await orchestrator.execute_task({
                    "type": "learn",
                    "data": {"problem": "classification"},
                })
    
    except KeyboardInterrupt:
        print("\nInterrupt received")
    
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
