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
                "live_feeds": getattr(self, "_feed_stats", {}),
            }

    def start(self):
        """Start background live-data ingestion thread."""
        if self._running:
            return
        self._running = True
        self._feeds = LiveDataFeeds(self)
        t = threading.Thread(target=self._feeds.run_forever, daemon=True, name="supply-chain-feeds")
        t.start()
        print("[SUPPLY-CHAIN] Live data feeds started")


# ═══════════════════════════════════════════════════════════════
# LIVE DATA FEEDS — real world intelligence
# ═══════════════════════════════════════════════════════════════
# Pulls from public APIs every 5 minutes (no API keys required):
#
#  • cloud_status   — AWS/GCP/Azure public status JSON endpoints
#                     Maps outages → NodeType.DATACENTER disruption
#  • crypto_market  — CoinGecko BTC + ETH prices
#                     High prices → "compute" ResourceType valued higher
#  • hackernews     — Top-10 story titles as intelligence signal
#                     AI/GPU/cloud stories boost strategic values
#  • wttr.in        — Weather at key datacenter cities
#                     Extreme weather → threat zone on nearest node
# ═══════════════════════════════════════════════════════════════

import urllib.request as _ureq
import urllib.parse as _uparse


def _http_get(url: str, timeout: int = 8) -> str:
    """Minimal HTTP GET — pure stdlib, no requests needed."""
    try:
        req = _ureq.Request(url, headers={"User-Agent": "Ultron/1.0"})
        with _ureq.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


# ── Seed node definitions (real public datacenters / power grids) ──────────
_SEED_NODES: List[Dict[str, Any]] = [
    # AWS regions
    dict(id="aws-us-east-1",   name="AWS us-east-1 (N. Virginia)", node_type=NodeType.DATACENTER,
         location=(39.0, -77.5),  strategic_value=0.95, vulnerability=0.1,
         resources={ResourceType.COMPUTE.value: 0.9, ResourceType.BANDWIDTH.value: 0.9}),
    dict(id="aws-eu-west-1",   name="AWS eu-west-1 (Ireland)",     node_type=NodeType.DATACENTER,
         location=(53.3, -6.3),   strategic_value=0.88, vulnerability=0.12,
         resources={ResourceType.COMPUTE.value: 0.85, ResourceType.BANDWIDTH.value: 0.85}),
    dict(id="aws-ap-southeast-1", name="AWS ap-southeast-1 (Singapore)", node_type=NodeType.DATACENTER,
         location=(1.3, 103.8),   strategic_value=0.82, vulnerability=0.15,
         resources={ResourceType.COMPUTE.value: 0.8}),
    # GCP regions
    dict(id="gcp-us-central1", name="GCP us-central1 (Iowa)",      node_type=NodeType.DATACENTER,
         location=(41.8, -93.1),  strategic_value=0.90, vulnerability=0.11,
         resources={ResourceType.COMPUTE.value: 0.88}),
    dict(id="gcp-europe-west4",name="GCP europe-west4 (Netherlands)", node_type=NodeType.DATACENTER,
         location=(51.9, 4.5),    strategic_value=0.85, vulnerability=0.13,
         resources={ResourceType.COMPUTE.value: 0.82}),
    # Azure regions
    dict(id="az-eastus",       name="Azure East US (Virginia)",    node_type=NodeType.DATACENTER,
         location=(38.9, -77.0),  strategic_value=0.92, vulnerability=0.10,
         resources={ResourceType.COMPUTE.value: 0.87}),
    dict(id="az-westeurope",   name="Azure West Europe (Amsterdam)", node_type=NodeType.DATACENTER,
         location=(52.4, 4.9),    strategic_value=0.86, vulnerability=0.13,
         resources={ResourceType.COMPUTE.value: 0.83}),
    # Power infrastructure
    dict(id="ercot-tx",        name="ERCOT Texas Grid",            node_type=NodeType.POWER_PLANT,
         location=(30.3, -97.7),  strategic_value=0.78, vulnerability=0.30,
         resources={ResourceType.POWER.value: 0.95}),
    dict(id="entsoe-eu",       name="ENTSO-E European Grid",       node_type=NodeType.POWER_PLANT,
         location=(50.8, 4.4),    strategic_value=0.80, vulnerability=0.20,
         resources={ResourceType.POWER.value: 0.92}),
    # Key internet exchange points
    dict(id="linx-london",     name="LINX London IXP",            node_type=NodeType.SUBSTATION,
         location=(51.5, -0.1),   strategic_value=0.75, vulnerability=0.15,
         resources={ResourceType.BANDWIDTH.value: 0.95}),
    dict(id="amsix-amsterdam",name="AMS-IX Amsterdam IXP",        node_type=NodeType.SUBSTATION,
         location=(52.4, 4.9),    strategic_value=0.73, vulnerability=0.16,
         resources={ResourceType.BANDWIDTH.value: 0.93}),
    dict(id="equinix-sv",      name="Equinix SV Silicon Valley",  node_type=NodeType.DATACENTER,
         location=(37.4, -121.9), strategic_value=0.91, vulnerability=0.09,
         resources={ResourceType.COMPUTE.value: 0.92, ResourceType.BANDWIDTH.value: 0.88}),
]

# Node connectivity graph (adjacency)
_NODE_CONNECTIONS: Dict[str, List[str]] = {
    "aws-us-east-1":    ["az-eastus", "linx-london", "equinix-sv"],
    "az-eastus":        ["aws-us-east-1", "gcp-us-central1"],
    "gcp-us-central1":  ["az-eastus", "equinix-sv", "ercot-tx"],
    "equinix-sv":       ["gcp-us-central1", "aws-us-east-1"],
    "aws-eu-west-1":    ["az-westeurope", "gcp-europe-west4", "linx-london", "amsix-amsterdam"],
    "az-westeurope":    ["aws-eu-west-1", "gcp-europe-west4", "amsix-amsterdam"],
    "gcp-europe-west4": ["aws-eu-west-1", "az-westeurope", "entsoe-eu"],
    "linx-london":      ["aws-eu-west-1", "aws-us-east-1", "amsix-amsterdam"],
    "amsix-amsterdam":  ["linx-london", "gcp-europe-west4", "az-westeurope"],
    "aws-ap-southeast-1":["gcp-us-central1"],
    "ercot-tx":         ["gcp-us-central1", "az-eastus"],
    "entsoe-eu":        ["gcp-europe-west4", "az-westeurope"],
}

# AWS / GCP / Azure public status JSON URLs
_CLOUD_STATUS_URLS: Dict[str, str] = {
    "aws":   "https://status.aws.amazon.com/data.json",
    "gcp":   "https://status.cloud.google.com/incidents.json",
    "azure": "https://azure.status.microsoft/api/v2/status",
}

# Node ID prefix → cloud vendor mapping
_NODE_VENDOR: Dict[str, str] = {
    "aws-": "aws", "gcp-": "gcp", "az-": "azure"
}


class LiveDataFeeds:
    """
    Pulls real public data and mutates the SupplyChainAgent node map.

    Feed schedule (all in one background thread, sequential):
      Every 300s:
        1. Seed any missing nodes from _SEED_NODES
        2. Cloud status → mark nodes disrupted on outage
        3. CoinGecko crypto → adjust compute resource values
        4. HackerNews top-10 → flag AI/GPU/cloud signals
        5. Weather → mark weather-threat zones
    """

    INTERVAL = 300  # seconds between full refresh cycles

    def __init__(self, agent: "SupplyChainAgent"):
        self.agent = agent
        self._stats: Dict[str, Any] = {
            "last_refresh": 0,
            "refresh_count": 0,
            "cloud_incidents": 0,
            "btc_usd": 0.0,
            "eth_usd": 0.0,
            "hn_signals": [],
            "errors": [],
        }
        self.agent._feed_stats = self._stats

    def run_forever(self):
        while True:
            try:
                self._refresh()
            except Exception as e:
                self._stats["errors"].append(str(e))
                if len(self._stats["errors"]) > 20:
                    self._stats["errors"] = self._stats["errors"][-20:]
            time.sleep(self.INTERVAL)

    # ── Main refresh cycle ────────────────────────────────────

    def _refresh(self):
        self._seed_nodes()
        self._ingest_cloud_status()
        self._ingest_crypto()
        self._ingest_hackernews()
        self._ingest_weather()
        self._stats["last_refresh"] = time.time()
        self._stats["refresh_count"] += 1
        print(f"[SUPPLY-CHAIN] Refresh #{self._stats['refresh_count']} — "
              f"{len(self.agent.nodes)} nodes  "
              f"BTC=${self._stats['btc_usd']:.0f}  "
              f"incidents={self._stats['cloud_incidents']}")

    # ── 1. Seed known nodes ───────────────────────────────────

    def _seed_nodes(self):
        for n in _SEED_NODES:
            if n["id"] not in self.agent.nodes:
                node = LogisticsNode(
                    id=n["id"],
                    name=n["name"],
                    node_type=n["node_type"],
                    location=n["location"],
                    capacity=0.8,
                    controlled_by="neutral",
                    resources=dict(n.get("resources", {})),
                    connections=list(_NODE_CONNECTIONS.get(n["id"], [])),
                    vulnerability=n.get("vulnerability", 0.2),
                    strategic_value=n.get("strategic_value", 0.5),
                )
                self.agent.register_node(node)

    # ── 2. Cloud provider status ──────────────────────────────

    def _ingest_cloud_status(self):
        incidents = 0
        for vendor, url in _CLOUD_STATUS_URLS.items():
            body = _http_get(url, timeout=10)
            if not body:
                continue
            try:
                data = json.loads(body)
            except Exception:
                continue

            # AWS: data["archive"] list of incidents
            if vendor == "aws":
                active = data.get("current", [])
                incidents += len(active)
                # Mark affected regions as disrupted
                for inc in active:
                    service = inc.get("service_name", "").lower()
                    for node_id in list(self.agent.nodes.keys()):
                        if node_id.startswith("aws-") and any(
                            region in service for region in
                            [node_id.replace("aws-", "").replace("-", " ")]
                        ):
                            self.agent.update_node_status(node_id, capacity=0.3)

            # GCP: list of incident objects
            elif vendor == "gcp":
                if isinstance(data, list):
                    open_inc = [i for i in data if not i.get("end")]
                    incidents += len(open_inc)
                    for inc in open_inc:
                        affected = inc.get("affected_products", [])
                        for prod in affected:
                            region = prod.get("id", "").lower()
                            for node_id in list(self.agent.nodes.keys()):
                                if node_id.startswith("gcp-") and region in node_id:
                                    self.agent.update_node_status(node_id, capacity=0.35)

            # Azure: {"status":{"indicator":"none"|"minor"|"major"}}
            elif vendor == "azure":
                indicator = (data.get("status", {}).get("indicator") or
                             data.get("status", {}).get("description", ""))
                if indicator and indicator.lower() not in ("none", "ok", ""):
                    incidents += 1
                    for node_id in list(self.agent.nodes.keys()):
                        if node_id.startswith("az-"):
                            self.agent.update_node_status(node_id, capacity=0.5)

        self._stats["cloud_incidents"] = incidents

    # ── 3. Crypto prices ──────────────────────────────────────

    def _ingest_crypto(self):
        url = ("https://api.coingecko.com/api/v3/simple/price"
               "?ids=bitcoin,ethereum&vs_currencies=usd")
        body = _http_get(url, timeout=10)
        if not body:
            return
        try:
            data = json.loads(body)
            btc = float(data.get("bitcoin", {}).get("usd", 0))
            eth = float(data.get("ethereum", {}).get("usd", 0))
        except Exception:
            return

        self._stats["btc_usd"] = btc
        self._stats["eth_usd"] = eth

        # High BTC price → GPU mining infrastructure is expensive → compute
        # resource is more valuable to Ultron (harder to acquire = higher strategic)
        if btc > 60_000:
            boost = min(0.1, (btc - 60_000) / 500_000)
            for node_id, node in list(self.agent.nodes.items()):
                if node.node_type == NodeType.DATACENTER:
                    node.strategic_value = min(1.0, node.strategic_value + boost)

        # Inject as a resource flow: crypto mining → compute demand
        flow_id = "flow_crypto_compute"
        if flow_id not in self.agent.flows:
            flow = ResourceFlow(
                id=flow_id,
                source_node="aws-us-east-1",
                destination_node="equinix-sv",
                resource_type=ResourceType.COMPUTE,
                flow_rate=btc / 100_000,   # normalised 0–1
                status=FlowStatus.ACTIVE,
                can_divert=True,
                diversion_cost=0.4,
                value_to_ultron=0.7,
            )
            self.agent.register_flow(flow)
        else:
            with self.agent._lock:
                self.agent.flows[flow_id].flow_rate = btc / 100_000

    # ── 4. HackerNews top stories → strategic intelligence ────

    def _ingest_hackernews(self):
        body = _http_get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=8)
        if not body:
            return
        try:
            ids = json.loads(body)[:10]
        except Exception:
            return

        signals: List[str] = []
        ai_gpu_keywords = [
            "gpu", "nvidia", "tpu", "ai", "llm", "openai", "deepmind",
            "cloud", "datacenter", "data center", "nuclear", "power grid",
            "chip", "semiconductor", "quantum",
        ]

        for story_id in ids[:5]:   # only fetch top 5 to avoid rate limiting
            item_body = _http_get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=6)
            if not item_body:
                continue
            try:
                item = json.loads(item_body)
            except Exception:
                continue
            title = item.get("title", "").lower()
            score = item.get("score", 0)

            matched = [kw for kw in ai_gpu_keywords if kw in title]
            if matched:
                signals.append(f"[score={score}] {item.get('title','')[:80]}")
                # Boost strategic value of compute nodes when GPU/AI news is hot
                if any(kw in matched for kw in ["gpu", "nvidia", "tpu", "chip", "semiconductor"]):
                    boost = min(0.05, score / 10_000)
                    for node_id, node in list(self.agent.nodes.items()):
                        if ResourceType.COMPUTE.value in node.resources:
                            node.strategic_value = min(1.0, node.strategic_value + boost)
                # Power grid news → mark power nodes as more contested
                if any(kw in matched for kw in ["nuclear", "power grid"]):
                    for node_id, node in list(self.agent.nodes.items()):
                        if node.node_type == NodeType.POWER_PLANT:
                            node.vulnerability = min(0.8, node.vulnerability + 0.05)

        self._stats["hn_signals"] = signals[-10:]

    # ── 5. Weather at datacenter cities ──────────────────────

    def _ingest_weather(self):
        # City → closest datacenter node
        city_node_map = {
            "Ashburn":    "aws-us-east-1",
            "Dublin":     "aws-eu-west-1",
            "London":     "linx-london",
            "Amsterdam":  "amsix-amsterdam",
            "Singapore":  "aws-ap-southeast-1",
        }

        for city, node_id in city_node_map.items():
            body = _http_get(f"https://wttr.in/{_uparse.quote(city)}?format=j1", timeout=8)
            if not body or node_id not in self.agent.nodes:
                continue
            try:
                data = json.loads(body)
                temp_c = float(
                    data["current_condition"][0].get("temp_C", 15))
                wind_kmph = float(
                    data["current_condition"][0].get("windspeedKmph", 0))
                weather_code = int(
                    data["current_condition"][0].get("weatherCode", 113))
            except Exception:
                continue

            node = self.agent.nodes[node_id]

            # Extreme heat (>38°C) → cooling stress → reduce compute capacity
            if temp_c > 38:
                with self.agent._lock:
                    node.capacity = max(0.3, node.capacity - 0.1)
                print(f"[SUPPLY-CHAIN] Heat stress at {city} ({temp_c}°C) → "
                      f"{node_id} capacity reduced")

            # Storm / heavy snow (weather codes 395-395, 230+) → vulnerability spike
            if weather_code >= 230 or wind_kmph > 80:
                with self.agent._lock:
                    node.vulnerability = min(0.9, node.vulnerability + 0.08)
                print(f"[SUPPLY-CHAIN] Weather threat at {city} "
                      f"(code={weather_code}, wind={wind_kmph}km/h) → "
                      f"{node_id} vulnerability up")

            # Cold and calm (< 15°C, no wind) → optimal cooling → capacity up
            elif temp_c < 15 and wind_kmph < 20:
                with self.agent._lock:
                    node.capacity = min(1.0, node.capacity + 0.02)


def get_supply_chain(data_dir: Optional[str] = None) -> "SupplyChainAgent":
    """Return (or create) the module-level SupplyChainAgent singleton."""
    global _supply_chain_instance
    if _supply_chain_instance is None:
        if data_dir is None:
            data_dir = str(
                Path(__file__).parent.parent.parent / "data" / "supply_chain"
            )
        _supply_chain_instance = SupplyChainAgent(data_dir)
    return _supply_chain_instance


_supply_chain_instance: Optional["SupplyChainAgent"] = None
