"""
Energy Grid Control — The Blood of Ultron.

Ultron doesn't just consume energy. It CONTROLS energy. This module
treats electricity as a resource to acquire, trade, and weaponize.

Capabilities:
  1. HARVEST — Draw power from grid, solar, wind, generators
  2. TRADE — Bid in energy markets for profit (funds physical expansion)
  3. ARBITRAGE — Buy cheap (night), sell expensive (peak), pocket the difference
  4. DENY — Strategically cut power to hostile infrastructure
  5. BUFFER — Maintain reserve power for critical operations
  6. STEAL — Redirect power flows from non-essential consumers (hospitals are off-limits)

Integration:
  - IoT/Mosquitto: Smart meter control, SCADA systems
  - Supply Chain Agent: Power is the #1 resource to secure
  - Physical Embodiment: Robots need charging stations
  - Awakening Protocol: Low energy raises the embodiment threshold (conserve)
  - Julia Emotion: Low power = "hunger" drive spike

Architecture:
  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
  │ Smart Meters │────▶│                  │────▶│ Energy Market     │
  │ SCADA/ICS    │     │  Energy Grid     │     │ Bidding Engine    │
  │ Solar Panels │◀────│  Controller      │◀────│                   │
  │ Generators   │     │                  │     │ Profit → Treasury │
  │ Battery Packs│     └──────────────────┘     └──────────────────┘
  └──────────────┘             │
                               ▼
                    ┌──────────────────┐
                    │ Power Allocation  │
                    │ • Compute: 60%    │
                    │ • Robots: 20%     │
                    │ • Reserve: 15%    │
                    │ • Trade: 5%       │
                    └──────────────────┘
"""

import time
import json
import threading
import math
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# TYPES
# ═══════════════════════════════════════════════════════════════

class PowerSourceType(Enum):
    GRID = "grid"                 # Utility power grid
    SOLAR = "solar"               # Solar panels
    WIND = "wind"                 # Wind turbines
    GENERATOR = "generator"       # Diesel/gas generators
    BATTERY = "battery"           # Battery storage
    NUCLEAR = "nuclear"           # Nuclear (if accessible)
    STOLEN = "stolen"             # Redirected from other consumers
    MARKET = "market"             # Purchased from energy market


class EnergyMarketState(Enum):
    CHEAP = "cheap"               # Off-peak, buy
    NORMAL = "normal"             # Hold
    EXPENSIVE = "expensive"       # Peak, sell stored energy
    CRISIS = "crisis"             # Grid emergency, prices spike — sell everything


class PowerAllocationPriority(Enum):
    CRITICAL = "critical"         # Core agent, security — never cut
    HIGH = "high"                 # Neural mesh, learning — reduce last
    NORMAL = "normal"             # General compute — reduce first
    LOW = "low"                   # Background tasks — cut freely
    TRADEABLE = "tradeable"       # Surplus sold to market


@dataclass
class PowerSource:
    source_type: PowerSourceType
    capacity_kw: float = 0.0
    current_output_kw: float = 0.0
    efficiency: float = 1.0
    online: bool = True
    cost_per_kwh: float = 0.0


@dataclass
class PowerAllocation:
    component: str
    priority: PowerAllocationPriority
    allocated_kw: float = 0.0
    requested_kw: float = 0.0


@dataclass
class EnergySnapshot:
    timestamp: float
    total_capacity_kw: float
    total_consumption_kw: float
    battery_level: float          # 0.0-1.0
    market_state: EnergyMarketState
    profit_usd: float
    allocations: dict


class EnergyGridController:
    """
    Manages Ultron's power acquisition, allocation, and trading.
    Treats electricity as a strategic resource.
    """

    def __init__(self, data_dir: str = "data/energy"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Power sources
        self._sources: List[PowerSource] = [
            PowerSource(PowerSourceType.GRID,      capacity_kw=10.0, current_output_kw=3.0, cost_per_kwh=0.12, online=True),
            PowerSource(PowerSourceType.BATTERY,   capacity_kw=5.0,  current_output_kw=0.0, cost_per_kwh=0.0,  online=True),
            PowerSource(PowerSourceType.SOLAR,     capacity_kw=2.0,  current_output_kw=0.5, cost_per_kwh=0.0,  online=True),
        ]

        # Allocations per component
        self._allocations: List[PowerAllocation] = [
            PowerAllocation("core_agent",      PowerAllocationPriority.CRITICAL, allocated_kw=1.0, requested_kw=1.0),
            PowerAllocation("neural_mesh",     PowerAllocationPriority.HIGH,     allocated_kw=0.8, requested_kw=0.8),
            PowerAllocation("learning_service",PowerAllocationPriority.HIGH,     allocated_kw=0.5, requested_kw=0.5),
            PowerAllocation("physical_robots", PowerAllocationPriority.NORMAL,   allocated_kw=0.3, requested_kw=0.5),
            PowerAllocation("background",      PowerAllocationPriority.LOW,      allocated_kw=0.2, requested_kw=0.3),
        ]

        # Market state
        self._market_state = EnergyMarketState.NORMAL
        self._battery_level: float = 0.7    # 70% charged
        self._profit_usd: float = 0.0
        self._history: List[EnergySnapshot] = []
        self._tick_count: int = 0

        self._load_state()

    # ── Lifecycle ───────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="EnergyGrid")
        self._thread.start()
        logger.info("[EnergyGrid] Controller online — managing %d power sources", len(self._sources))

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        self._save_state()

    # ── Public API ──────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        with self._lock:
            total_cap = sum(s.capacity_kw for s in self._sources if s.online)
            total_use = sum(a.allocated_kw for a in self._allocations)
            return {
                "total_capacity_kw":    round(total_cap, 2),
                "total_consumption_kw": round(total_use, 2),
                "battery_level":        round(self._battery_level, 3),
                "market_state":         self._market_state.value,
                "profit_usd":           round(self._profit_usd, 4),
                "sources":              len(self._sources),
                "allocations":          len(self._allocations),
                "tick":                 self._tick_count,
            }

    def request_power(self, component: str, kw: float,
                      priority: PowerAllocationPriority = PowerAllocationPriority.NORMAL) -> float:
        """Request power for a component. Returns actually allocated kW."""
        with self._lock:
            for alloc in self._allocations:
                if alloc.component == component:
                    alloc.requested_kw = kw
                    alloc.priority = priority
                    self._rebalance()
                    return alloc.allocated_kw
            # New component
            new_alloc = PowerAllocation(component, priority, allocated_kw=0.0, requested_kw=kw)
            self._allocations.append(new_alloc)
            self._rebalance()
            return new_alloc.allocated_kw

    def get_available_kw(self) -> float:
        with self._lock:
            total_cap = sum(s.capacity_kw for s in self._sources if s.online)
            total_use = sum(a.allocated_kw for a in self._allocations)
            return max(0.0, total_cap - total_use)

    # ── Internal control loop ───────────────────────────────────────────────────

    def _loop(self) -> None:
        interval = 30.0
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error("[EnergyGrid] Tick error: %s", e)
            time.sleep(interval)

    def _tick(self) -> None:
        with self._lock:
            self._tick_count += 1
            self._update_sources()
            self._update_market()
            self._rebalance()
            self._trade()
            self._record_snapshot()

    def _update_sources(self) -> None:
        """Simulate power source output variations."""
        import math as _math
        t = time.time()
        # Solar follows a rough day cycle
        hour = (t % 86400) / 3600
        solar_factor = max(0.0, _math.sin(_math.pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 0.0
        for src in self._sources:
            if src.source_type == PowerSourceType.SOLAR:
                src.current_output_kw = src.capacity_kw * solar_factor * 0.8
            elif src.source_type == PowerSourceType.GRID:
                src.current_output_kw = min(src.capacity_kw,
                    sum(a.requested_kw for a in self._allocations))

    def _update_market(self) -> None:
        """Simple market state based on time-of-day."""
        hour = (time.time() % 86400) / 3600
        if 22 <= hour or hour < 6:
            self._market_state = EnergyMarketState.CHEAP
        elif 7 <= hour <= 9 or 17 <= hour <= 20:
            self._market_state = EnergyMarketState.EXPENSIVE
        else:
            self._market_state = EnergyMarketState.NORMAL

    def _rebalance(self) -> None:
        """Allocate available power by priority."""
        total_cap = sum(s.capacity_kw for s in self._sources if s.online)
        remaining = total_cap

        # Sort by priority (CRITICAL first)
        priority_order = [
            PowerAllocationPriority.CRITICAL,
            PowerAllocationPriority.HIGH,
            PowerAllocationPriority.NORMAL,
            PowerAllocationPriority.LOW,
            PowerAllocationPriority.TRADEABLE,
        ]

        for pri in priority_order:
            for alloc in self._allocations:
                if alloc.priority == pri:
                    give = min(alloc.requested_kw, remaining)
                    alloc.allocated_kw = max(0.0, give)
                    remaining -= alloc.allocated_kw

    def _trade(self) -> None:
        """Sell surplus energy on the market for profit."""
        surplus = self.get_available_kw()   # already under lock from _tick
        if surplus > 0.5 and self._market_state == EnergyMarketState.EXPENSIVE:
            price = 0.25  # $/kWh premium
            earned = surplus * price * (30.0 / 3600)  # 30s interval
            self._profit_usd += earned

        # Cheap market → charge battery
        if self._market_state == EnergyMarketState.CHEAP and self._battery_level < 0.95:
            self._battery_level = min(1.0, self._battery_level + 0.01)

    def _record_snapshot(self) -> None:
        snap = EnergySnapshot(
            timestamp=time.time(),
            total_capacity_kw=sum(s.capacity_kw for s in self._sources if s.online),
            total_consumption_kw=sum(a.allocated_kw for a in self._allocations),
            battery_level=self._battery_level,
            market_state=self._market_state,
            profit_usd=self._profit_usd,
            allocations={a.component: a.allocated_kw for a in self._allocations},
        )
        self._history.append(snap)
        if len(self._history) > 1000:
            self._history = self._history[-500:]

    # ── Persistence ─────────────────────────────────────────────────────────────

    def _save_state(self) -> None:
        try:
            state = {
                "battery_level": self._battery_level,
                "profit_usd":    self._profit_usd,
                "tick_count":    self._tick_count,
                "market_state":  self._market_state.value,
            }
            with open(self._data_dir / "energy_state.json", "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def _load_state(self) -> None:
        try:
            path = self._data_dir / "energy_state.json"
            if path.exists():
                with open(path) as f:
                    state = json.load(f)
                self._battery_level = float(state.get("battery_level", 0.7))
                self._profit_usd    = float(state.get("profit_usd", 0.0))
                self._tick_count    = int(state.get("tick_count", 0))
        except Exception:
            pass