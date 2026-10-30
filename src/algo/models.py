from dataclasses import dataclass
from typing import List, Dict, Tuple
import numpy as np

# Structured NumPy array dtype for raw streaming ticks
TICK_DTYPE = np.dtype([
    ('ts', np.int64),
    ('bid', np.float64),
    ('ask', np.float64),
    ('last', np.float64),
    ('volume', np.float64),
    ('flags', np.int32),
    ('side', np.int8)  # 1 for Buy, -1 for Sell, 0 for Neutral
])

@dataclass(frozen=True, slots=True)
class AlgoBubble:
    """
    Pure mathematical representation of an aggregated order flow bubble.
    Completely decoupled from visual coordinates.
    """
    ts: int               # Representative timestamp (ms)
    price: float          # Exact price or VWAP
    volume: float         # Aggregated total volume
    buy_vol: float        # Aggressive buy volume
    sell_vol: float       # Aggressive sell volume
    delta: float          # Net delta (buy_vol - sell_vol)
    delta_ratio: float    # delta / volume (-1.0 to +1.0)
    imbalance_state: str  # 'BUY_IMBALANCE' | 'SELL_IMBALANCE' | 'BALANCED'
    imbalance_ratio: float# Dominant side ratio (e.g. 3.5 = 3.5:1)
    tick_count: int       # Number of ticks in this bubble
    interval_ms: int      # Accumulation window
    price_level: float    # Ladder rung price or VWAP

@dataclass(frozen=True, slots=True)
class MacroStructure:
    """
    Macroeconomic & Auction Market Structure of the active session.
    Provides the structural roadmap for contextualizing micro bubbles.
    """
    session_high: float
    session_low: float
    session_vwap: float
    poc_price: float
    value_area_high: float
    value_area_low: float
    total_volume: float
    net_cumulative_delta: float

@dataclass(frozen=True, slots=True)
class OrderFlowSnapshot:
    """
    Thread-safe immutable snapshot passed asynchronously from Algo to Visual Engine.
    """
    bubbles: List[AlgoBubble]
    trajectory_points: List[Tuple[int, float]] # (ts_ms, price)
    volume_profile: Dict[float, float]        # price_bin -> volume
    macro: MacroStructure
    last_price: float
    last_ts: int
    version: int
