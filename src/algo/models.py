from dataclasses import dataclass
from typing import Optional
import numpy as np

# Structured NumPy array dtype for high-throughput ticks
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
    Immutable mathematical snapshot of an aggregated order flow cell/bubble.
    Holds 100% pure mathematical truth independent of visual styling.
    """
    ts: int               # Representative timestamp (ms)
    price: float          # Exact price or VWAP
    volume: float         # Aggregated total executed volume
    buy_vol: float        # Aggressive buyer volume (lifting offer)
    sell_vol: float       # Aggressive seller volume (hitting bid)
    delta: float          # Net delta (buy_vol - sell_vol)
    delta_ratio: float    # delta / volume (-1.0 to +1.0)
    imbalance_state: str  # 'BUY_IMBALANCE' | 'SELL_IMBALANCE' | 'BALANCED'
    imbalance_ratio: float# Ratio of dominant side over passive side (e.g. 3.5 = 3.5:1)
    tick_count: int       # Number of raw ticks fused into this bubble
    interval_ms: int      # Accumulation window (ms)
    price_level: float    # Base price bin or VWAP
