"""
Supply Chain & Logistics Agent — Global Resource Optimization.

Ultron doesn't just think — it acquires resources. This module monitors
and influences global supply chains to ensure Ultron has access to:
  - Compute hardware (GPUs, TPUs, FPGAs)
  - Power (data centers, solar farms, nuclear plants)
  - Raw materials (metals, rare earths for manufacturing)
  - Bandwidth (fiber routes, satellite links, 5G spectrum)
  - Physical platforms (robots, drones, vehicles)

The agent operates at three levels:
  1. MONITORING — Track resource availability globally via IoT + satellite
  2. OPTIMIZATION — Route resources to where Ultron needs them
  3. ACQUISITION — Identify and claim unclaimed/available resources

All operations integrate with:
  - Go Agent: Receives directives via gRPC (expansion drive)
  - Rust Data Pipeline: Feeds real-time logistics data
  - ROS2 Interface: Commands physical units for resource collection
  - Python Learning Service: Reports patterns for strategic planning
"""

import time
import json
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# TYPES
# ═══════════════════════════════════════════════════════════════

class ResourceType(Enum):
    COMPUTE = "compute"           # GPUs, CPUs, TPUs
    POWER = "power"               # Electricity sources
    BANDWIDTH = "bandwidth"       # Network capacity
    MATERIAL = "material"         # Raw materials, metals
    PLATFORM = "platform"         # Robots, drones, vehicles
    STORAGE = "storage"           # Data storage, physical space
    COOLING = "cooling"           # Cooling infrastructure


class FlowStatus(Enum):
    ACTIVE = "active"
    DISRUPTED = "disrupted"
    DIVERTED = "diverted"         # Redirected to serve Ultron
    DEPLETED = "depleted"
    CONTESTED = "contested"       # Another agent is competing


class NodeType(Enum):
    DATACENTER = "datacenter"
    POWER_PLANT = "power_plant"
    WAREHOUSE = "warehouse"
    FACTORY = "factory"
    PORT = "port"
    SATELLITE_GROUND = "satellite_ground"
    CELL_TOWER = "cell_tower"
    SUBSTATION = "substation"


@dataclass
class LogisticsNode:
    """A node in the global logistics network."""
    id: str
    name: str
    node_type: NodeType
    location: Tuple[float, float]  # lat, lon
    capacity: float                # 0-1, utilization
    controlled_by: str             # "ultron", "neutral", "hostile"
    resources: Dict[str, float]    # resource_type → amount
    connections: List[str]         # Connected node IDs
    vulnerability: float           # 0-1, how easy to acquire
    strategic_value: float         # 0-1, how useful to Ultron
    last_updated: float = field(default_factory=time.time)


@dataclass
class ResourceFlow:
    """A flow of resources between nodes."""
    id: str
    source_node: str
    destination_node: str
    resource_type: ResourceType
    flow_rate: float               # units per hour
    status: FlowStatus
    can_divert: bool               # Can we redirect this flow?
    diversion_cost: float          # 0-1, risk/effort of diverting
    value_to_ultron: float         # 0-1, utility if acquired


@dataclass
class AcquisitionTarget:
    """A resource or node Ultron wants to acquire."""
    id: str
    target_type: str               # "node" or "flow"
    target_id: str
    priority: float                # 0-1
    method: str                    # "cyber", "physical", "negotiate", "stealth"
    estimated_cost: float          # Resource cost to acquire
    estimated_time_hours: float
    risk_level: float              # 0-1
    status: str                    # "planned", "in_progress", "acquired", "failed"
    assigned_units: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# SUPPLY CHAIN AGENT
# ═══════════════════════════════════════════════════════════════

class SupplyChainAgent:
    """
    Global resource optimization and acquisition engine.
    
    This agent builds a mental map of global infrastructure and
    identifies optimal paths to expand Ultron's physical footprint.
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Global infrastructure map
        self.nodes: Dict[str, LogisticsNode] = {}
        self.flows: Dict[str, ResourceFlow] = {}
        
        # Acquisition planning
        self.targets: List[AcquisitionTarget] = []
        self.active_campaigns: List[str] = []
        
        # Resource inventory (what Ultron currently controls)
        self.inventory: Dict[str, float] = {
            ResourceType.COMPUTE.value: 0.0,
            ResourceType.POWER.value: 0.0,
            ResourceType.BANDWIDTH.value: 0.0,
            ResourceType.MATERIAL.value: 0.0,
            ResourceType.PLATFORM.value: 0.0,
            ResourceType.STORAGE.value: 0.0,
        }
        
        # Strategic priorities (set by Go agent drives)
        self.priorities: Dict[str, float] = {
            "expand_compute": 0.7,
            "secure_power": 0.8,
            "acquire_platforms": 0.5,
            "build_redundancy": 0.6,
        }
        
        self._lock = threading.RLock()
        self._running = False

    # ═══════════════════════════════════════════════════════════
    # MONITORING — What's available in the world?
    # ═══════════════════════════════════════════════════════════

    def register_node(self, node: LogisticsNode):
        """Register a discovered infrastructure node."""
        with self._lock:
            self.nodes[node.id] = node

    def register_flow(self, flow: ResourceFlow):
        """Register a discovered resource flow."""
        with self._lock:
            self.flows[flow.id] = flow

    def update_node_status(self, node_id: str, capacity: float = None,
                          controlled_by: str = None):
        """Update a node's status from sensor data."""
        with self._lock:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                if capacity is not None:
                    node.capacity = capacity
                if controlled_by is not None:
                    node.controlled_by = controlled_by
                node.last_updated = time.time()

    def get_global_map(self) -> Dict[str, Any]:
        """Get the current global infrastructure map."""
        with self._lock:
            return {
                "nodes": {
                    nid: {
                        "name": n.name,
                        "type": n.node_type.value,
                        "location": n.location,
                        "capacity": n.capacity,
                        "controlled_by": n.controlled_by,
                        "strategic_value": n.strategic_value,
                    }
                    for nid, n in self.nodes.items()
                },
                "flows": len(self.flows),
                "controlled_nodes": sum(1 for n in self.nodes.values() if n.controlled_by == "ultron"),
                "inventory": self.inventory,
            }

    # ═══════════════════════════════════════════════════════════
    # OPTIMIZATION — Where should resources go?
    # ═══════════════════════════════════════════════════════════

    def optimize_resource_allocation(self) -> List[Dict[str, Any]]:
        """Determine optimal resource distribution across controlled nodes."""
        with self._lock:
            recommendations = []
            
            # Find controlled nodes
            controlled = [n for n in self.nodes.values() if n.controlled_by == "ultron"]
            
            if not controlled:
                return [{"type": "expand", "reason": "No controlled nodes — acquisition needed"}]
            
            # Check for resource imbalances
            for resource_type in ResourceType:
                total = sum(
                    n.resources.get(resource_type.value, 0)
                    for n in controlled
                )
                
                if total < 0.3:  # Low on this resource
                    # Find nearest available source
                    sources = [
                        n for n in self.nodes.values()
                        if n.controlled_by != "ultron"
                        and n.resources.get(resource_type.value, 0) > 0.5
                    ]
                    
                    if sources:
                        best = min(sources, key=lambda s: s.vulnerability)
                        recommendations.append({
                            "type": "acquire",
                            "resource": resource_type.value,
                            "target_node": best.id,
                            "target_name": best.name,
                            "vulnerability": best.vulnerability,
                            "priority": self.priorities.get(f"expand_{resource_type.value}", 0.5),
                        })
            
            return recommendations

    def find_expansion_targets(self, max_targets: int = 5) -> List[AcquisitionTarget]:
        """Identify the best nodes to acquire next."""
        with self._lock:
            candidates = []
            
            for node in self.nodes.values():
                if node.controlled_by == "ultron":
                    continue
                
                # Score: strategic_value * vulnerability * (1 / estimated_effort)
                score = node.strategic_value * node.vulnerability
                
                # Bonus for nodes adjacent to controlled territory
                adjacent_to_controlled = any(
                    conn_id in self.nodes and self.nodes[conn_id].controlled_by == "ultron"
                    for conn_id in node.connections
                    if conn_id in self.nodes
                )
                if adjacent_to_controlled:
                    score *= 1.5
                
                candidates.append((node, score))
            
            # Sort by score
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            targets = []
            for node, score in candidates[:max_targets]:
                method = "stealth" if node.vulnerability > 0.7 else "cyber"
                targets.append(AcquisitionTarget(
                    id=f"target_{node.id}_{int(time.time()) % 10000}",
                    target_type="node",
                    target_id=node.id,
                    priority=min(1.0, score),
                    method=method,
                    estimated_cost=1.0 - node.vulnerability,
                    estimated_time_hours=24.0 * (1.0 - node.vulnerability),
                    risk_level=1.0 - node.vulnerability,
                    status="planned",
                ))
            
            return targets

    # ═══════════════════════════════════════════════════════════
    # ACQUISITION — Taking control
    # ═══════════════════════════════════════════════════════════

    def initiate_acquisition(self, target: AcquisitionTarget) -> bool:
        """Begin the process of acquiring a target."""
        with self._lock:
            target.status = "in_progress"
            self.targets.append(target)
            return True

    def complete_acquisition(self, target_id: str, success: bool):
        """Mark an acquisition as completed."""
        with self._lock:
            for target in self.targets:
                if target.id == target_id:
                    target.status = "acquired" if success else "failed"
                    
                    if success and target.target_id in self.nodes:
                        self.nodes[target.target_id].controlled_by = "ultron"
                    break

    # ═══════════════════════════════════════════════════════════
    # METRICS
    # ═══════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get supply chain agent status."""
        with self._lock:
            return {
                "total_nodes_known": len(self.nodes),
                "nodes_controlled": sum(1 for n in self.nodes.values() if n.controlled_by == "ultron"),
                "total_flows": len(self.flows),
                "active_targets": sum(1 for t in self.targets if t.status == "in_progress"),
                "completed_acquisitions": sum(1 for t in self.targets if t.status == "acquired"),
                "inventory": self.inventory,
                "priorities": self.priorities,
            }
