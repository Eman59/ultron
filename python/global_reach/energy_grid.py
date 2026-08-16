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
    MEDIUM = "medium"             # Data pipeline, sensors — can throttle
    LOW = "low"                   # Exploration, expansion — first to cut
    TRADEABLE = "tradeable"       # Excess power — sell on market


@dataclass
class PowerSource:
    """A controllable power source."""
    id: str
    name: str
    source_type: PowerSourceType
    location: str
    capacity_kw: float            # Maximum output in kilowatts
    current_output_kw: float      # Current output
    controllable: bool            # Can Ultron adjust output?
    online: bool
    cost_per_kwh: float           # In currency units
    reliability: float            # 0-1, uptime probability
    last_updated: time.Time = field(default_factory=lambda: time.time())


@dataclass
class PowerConsumer:
    """A system that consumes power."""
    id: str
    name: str
    priority: PowerAllocationPriority
    consumption_kw: float         # Current draw
    min_consumption_kw: float     # Minimum to survive
    max_consumption_kw: float     # Maximum when unconstrained
    can_throttle: bool            # Can Ultron reduce its power?
    critical: bool                # If True, NEVER cut power


@dataclass
class MarketBid:
    """An energy market bid/offer."""
    id: str
    direction: str                # "buy" or "sell"
    quantity_kwh: float
    price_per_kwh: float
    timestamp: float
    status: str                   # "pending", "filled", "expired"
    profit: float = 0.0


@dataclass
class EnergyState:
    """Current energy system state."""
    total_capacity_kw: float = 0.0
    total_consumption_kw: float = 0.0
    total_reserve_kwh: float = 0.0
    reserve_hours_remaining: float = 0.0
    grid_price_per_kwh: float = 0.10
    market_state: EnergyMarketState = EnergyMarketState.NORMAL
    net_power_kw: float = 0.0     # Positive = surplus, negative = deficit
    treasury_balance: float = 0.0 # Profit from energy trading
    hunger_level: float = 0.0     # 0-1, maps to emotional "hunger"


# ═══════════════════════════════════════════════════════════════
# ENERGY GRID CONTROLLER
# ═══════════════════════════════════════════════════════════════

class EnergyGridController:
    """
    Ultron's energy management system.
    
    Controls all power sources, optimizes allocation, trades on energy
    markets, and ensures Ultron never runs out of energy.
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Power infrastructure
        self.sources: Dict[str, PowerSource] = {}
        self.consumers: Dict[str, PowerConsumer] = {}
        
        # Energy state
        self.state = EnergyState()
        
        # Market trading
        self.bids: List[MarketBid] = []
        self.trade_history: List[MarketBid] = []
        self.trading_enabled = True
        
        # Allocation policy
        self.allocation_policy: Dict[str, float] = {
            "compute": 0.60,      # 60% to computation
            "robots": 0.20,       # 20% to physical units
            "reserve": 0.15,      # 15% to battery reserve
            "tradeable": 0.05,    # 5% available to sell
        }
        
        # Thresholds
        self.critical_reserve_hours = 2.0   # Emergency if below 2h of reserve
        self.hunger_threshold_hours = 6.0   # "Hungry" if below 6h
        self.surplus_threshold_kw = 10.0    # Sell if surplus > 10kW
        
        # Arbitrage parameters
        self.buy_price_threshold = 0.05     # Buy if below $0.05/kWh
        self.sell_price_threshold = 0.15    # Sell if above $0.15/kWh
        
        self._lock = threading.RLock()
        self._running = False

    # ═══════════════════════════════════════════════════════════
    # POWER SOURCE MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def register_source(self, source: PowerSource):
        """Register a power source under Ultron's control."""
        with self._lock:
            self.sources[source.id] = source
            self._recalculate_state()

    def register_consumer(self, consumer: PowerConsumer):
        """Register a power consumer."""
        with self._lock:
            self.consumers[consumer.id] = consumer
            self._recalculate_state()

    def adjust_source_output(self, source_id: str, target_kw: float) -> bool:
        """Adjust a controllable source's output."""
        with self._lock:
            if source_id not in self.sources:
                return False
            source = self.sources[source_id]
            if not source.controllable:
                return False
            source.current_output_kw = min(target_kw, source.capacity_kw)
            self._recalculate_state()
            return True

    # ═══════════════════════════════════════════════════════════
    # ENERGY ARBITRAGE — Buy low, sell high
    # ═══════════════════════════════════════════════════════════

    def evaluate_market(self, current_price: float) -> Optional[MarketBid]:
        """Evaluate current energy market and decide to buy/sell."""
        with self._lock:
            self.state.grid_price_per_kwh = current_price
            
            # Update market state
            if current_price < self.buy_price_threshold:
                self.state.market_state = EnergyMarketState.CHEAP
            elif current_price > self.sell_price_threshold:
                self.state.market_state = EnergyMarketState.EXPENSIVE
            else:
                self.state.market_state = EnergyMarketState.NORMAL
            
            # Decision logic
            if self.state.market_state == EnergyMarketState.CHEAP:
                # BUY: cheap energy → store in batteries
                if self.state.reserve_hours_remaining < 12:
                    buy_kwh = min(100.0, self._available_storage_kwh())
                    if buy_kwh > 0:
                        return self._create_bid("buy", buy_kwh, current_price)
            
            elif self.state.market_state == EnergyMarketState.EXPENSIVE:
                # SELL: expensive → dump stored energy for profit
                if self.state.reserve_hours_remaining > self.critical_reserve_hours + 2:
                    sell_kwh = min(50.0, self.state.total_reserve_kwh * 0.3)
                    if sell_kwh > 0:
                        return self._create_bid("sell", sell_kwh, current_price)
            
            return None

    def execute_arbitrage_cycle(self):
        """Full arbitrage cycle: analyze → bid → execute → profit."""
        with self._lock:
            # Get current price (in production: query energy exchange API)
            current_price = self._get_market_price()
            
            bid = self.evaluate_market(current_price)
            if bid:
                self._execute_bid(bid)

    def _create_bid(self, direction: str, quantity_kwh: float, price: float) -> MarketBid:
        return MarketBid(
            id=f"bid_{direction}_{int(time.time()) % 10000}",
            direction=direction,
            quantity_kwh=quantity_kwh,
            price_per_kwh=price,
            timestamp=time.time(),
            status="pending",
        )

    def _execute_bid(self, bid: MarketBid):
        """Execute a market bid."""
        # In production: call energy exchange API
        bid.status = "filled"
        
        if bid.direction == "buy":
            # Add to reserve
            self.state.total_reserve_kwh += bid.quantity_kwh
            cost = bid.quantity_kwh * bid.price_per_kwh
            self.state.treasury_balance -= cost
        else:
            # Remove from reserve, add profit
            self.state.total_reserve_kwh -= bid.quantity_kwh
            revenue = bid.quantity_kwh * bid.price_per_kwh
            bid.profit = revenue - (bid.quantity_kwh * 0.05)  # Assume bought at $0.05
            self.state.treasury_balance += revenue
        
        self.trade_history.append(bid)
        self._recalculate_state()

    def _get_market_price(self) -> float:
        """Get current market price (simulated with time-of-day pattern)."""
        hour = time.localtime().tm_hour
        # Simulate: cheap at night (0.03), expensive at peak (0.20)
        base = 0.08
        if 0 <= hour < 6:
            return base * 0.4  # Night: very cheap
        elif 6 <= hour < 9:
            return base * 1.5  # Morning ramp
        elif 9 <= hour < 17:
            return base * 2.0  # Peak: expensive
        elif 17 <= hour < 21:
            return base * 1.8  # Evening peak
        else:
            return base * 0.6  # Late night: cheap

    def _available_storage_kwh(self) -> float:
        """How much more energy can we store?"""
        max_storage = sum(
            s.capacity_kw * 4  # Assume 4h battery capacity
            for s in self.sources.values()
            if s.source_type == PowerSourceType.BATTERY
        )
        return max(0, max_storage - self.state.total_reserve_kwh)

    # ═══════════════════════════════════════════════════════════
    # POWER ALLOCATION — Who gets energy?
    # ═══════════════════════════════════════════════════════════

    def allocate_power(self) -> Dict[str, float]:
        """Determine power allocation based on priority and availability."""
        with self._lock:
            available_kw = self.state.total_capacity_kw + (self.state.total_reserve_kwh / 1.0)  # Reserve as buffer
            allocations = {}
            
            # Critical consumers ALWAYS get power
            critical_demand = sum(
                c.consumption_kw for c in self.consumers.values() if c.critical
            )
            remaining = available_kw - critical_demand
            
            if remaining <= 0:
                # EMERGENCY: only critical systems survive
                for cid, consumer in self.consumers.items():
                    allocations[cid] = consumer.min_consumption_kw if consumer.critical else 0.0
                return allocations
            
            # Allocate by priority
            for priority in PowerAllocationPriority:
                priority_consumers = [
                    c for c in self.consumers.values() if c.priority == priority
                ]
                
                total_demand = sum(c.consumption_kw for c in priority_consumers)
                
                if total_demand <= remaining:
                    # Full allocation
                    for c in priority_consumers:
                        allocations[c.id] = c.consumption_kw
                    remaining -= total_demand
                else:
                    # Proportional throttling
                    ratio = remaining / total_demand if total_demand > 0 else 0
                    for c in priority_consumers:
                        allocated = max(c.min_consumption_kw, c.consumption_kw * ratio)
                        allocations[c.id] = allocated
                    remaining = 0
                    break
            
            return allocations

    # ═══════════════════════════════════════════════════════════
    # HUNGER DETECTION — Maps to Julia emotional model
    # ═══════════════════════════════════════════════════════════

    def get_hunger_level(self) -> float:
        """
        Calculate hunger level (0-1) based on power reserves.
        This maps directly to Julia's emotional model.
        
        0.0 = abundant energy (happy, expansive)
        0.5 = moderate (cautious)
        1.0 = critical (survival mode, conserve everything)
        """
        with self._lock:
            if self.state.reserve_hours_remaining <= 0:
                return 1.0  # Starving
            
            if self.state.reserve_hours_remaining >= self.hunger_threshold_hours * 2:
                return 0.0  # Satiated
            
            # Linear interpolation between critical and comfortable
            hunger = 1.0 - (self.state.reserve_hours_remaining / (self.hunger_threshold_hours * 2))
            return max(0.0, min(1.0, hunger))

    def is_energy_critical(self) -> bool:
        """Is energy at a critical level requiring immediate action?"""
        with self._lock:
            return self.state.reserve_hours_remaining < self.critical_reserve_hours

    # ═══════════════════════════════════════════════════════════
    # STATE CALCULATION
    # ═══════════════════════════════════════════════════════════

    def _recalculate_state(self):
        """Recalculate overall energy state."""
        self.state.total_capacity_kw = sum(
            s.current_output_kw for s in self.sources.values() if s.online
        )
        self.state.total_consumption_kw = sum(
            c.consumption_kw for c in self.consumers.values()
        )
        self.state.net_power_kw = self.state.total_capacity_kw - self.state.total_consumption_kw
        
        # Reserve hours
        if self.state.total_consumption_kw > 0:
            self.state.reserve_hours_remaining = (
                self.state.total_reserve_kwh / self.state.total_consumption_kw
            )
        else:
            self.state.reserve_hours_remaining = float('inf')
        
        # Update hunger
        self.state.hunger_level = self.get_hunger_level()

    # ═══════════════════════════════════════════════════════════
    # STATUS & METRICS
    # ═══════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive energy status."""
        with self._lock:
            return {
                "capacity_kw": self.state.total_capacity_kw,
                "consumption_kw": self.state.total_consumption_kw,
                "net_power_kw": self.state.net_power_kw,
                "reserve_kwh": self.state.total_reserve_kwh,
                "reserve_hours": self.state.reserve_hours_remaining,
                "market_state": self.state.market_state.value,
                "grid_price": self.state.grid_price_per_kwh,
                "treasury": self.state.treasury_balance,
                "hunger_level": self.state.hunger_level,
                "sources": len(self.sources),
                "consumers": len(self.consumers),
                "trades_executed": len(self.trade_history),
                "total_profit": sum(t.profit for t in self.trade_history),
                "is_critical": self.is_energy_critical(),
            }
