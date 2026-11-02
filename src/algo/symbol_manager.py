import time
import math
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.algo.tick_store import TickStore
from src.algo.accumulator import OrderFlowAlgoEngine

logger = logging.getLogger(__name__)

@dataclass
class SymbolState:
    """
    Completely isolated state container for a single trading symbol.
    Guarantees no tick data, timestamps, volume profile, or algo metrics
    are ever shared or contaminated between different instruments.
    """
    symbol: str
    tick_store: TickStore = field(default_factory=lambda: TickStore(max_ticks=1_000_000))
    algo_engine: OrderFlowAlgoEngine = field(default_factory=lambda: OrderFlowAlgoEngine())
    tick_size: float = 0.01
    digits: int = 2
    point: float = 0.001
    contract_size: float = 100.0
    last_known_price: float = 0.0
    tick_count: int = 0
    last_tick_time_sec: float = 0.0

    def configure_meta(self, tick_size: float = None, digits: int = None,
                       point: float = None, contract_size: float = None):
        if tick_size is not None and tick_size > 0:
            self.tick_size = tick_size
            # Adjust volume profile price bin size appropriately
            # (e.g. Gold tick_size 0.01 -> bin 0.50; Forex tick_size 0.00001 -> bin 0.0005)
            bin_size = max(self.tick_size, round(self.tick_size * 50.0, 5))
            self.algo_engine.vp_engine.price_bin_size = bin_size

        if digits is not None and digits >= 0:
            self.digits = digits
        if point is not None and point > 0:
            self.point = point
        if contract_size is not None and contract_size > 0:
            self.contract_size = contract_size

    def add_tick(self, ts: int, bid: float, ask: float, last: float,
                 volume: float, flags: int = 0, side: int = 0) -> bool:
        """
        Ingest a tick into this isolated symbol state.
        Performs per-symbol sanitization and spike protection.
        """
        price = last if last > 0 else (bid if bid > 0 else ask)
        if price <= 0.0 or math.isnan(price) or math.isinf(price):
            return False

        # Per-symbol spike protection: reject >25% jump in a single tick
        if self.last_known_price > 0.0:
            jump = abs(price - self.last_known_price)
            # Adapt scale threshold for currencies vs commodities
            min_jump_abs = 200.0 if self.digits <= 2 else 0.20
            spike_threshold = max(self.last_known_price * 0.25, min_jump_abs)
            if jump > spike_threshold:
                logger.warning(f"[{self.symbol}] Spike protection rejected tick: {price} vs last {self.last_known_price}")
                return False

        vol = volume if volume > 0 else 1.0
        added = self.tick_store.add_tick(
            ts=ts,
            bid=bid if bid > 0 else price,
            ask=ask if ask > 0 else price,
            last=price,
            volume=vol,
            flags=flags,
            side=side
        )
        if added:
            self.last_known_price = price
            self.tick_count += 1
            self.last_tick_time_sec = time.time()
        return added


class SymbolManager:
    """
    Central Multi-Symbol Isolation Engine.
    Manages independent buffers, metadata, and order flow algorithm engines per symbol.
    """
    def __init__(self, default_symbol: str = "XAUUSD"):
        self.states: Dict[str, SymbolState] = {}
        self.active_symbol: str = default_symbol.strip().upper()
        # Initialize default
        self.get_or_create(self.active_symbol)

    def get(self, symbol: str) -> Optional[SymbolState]:
        sym = symbol.strip().upper() if symbol else ""
        return self.states.get(sym)

    def get_or_create(self, symbol: str) -> SymbolState:
        sym = symbol.strip().upper() if symbol else "UNKNOWN"
        if sym not in self.states:
            logger.info(f"Initialized new isolated symbol state for [{sym}]")
            state = SymbolState(symbol=sym)
            # Default heuristics based on symbol name
            if "XAU" in sym or "GOLD" in sym:
                state.tick_size = 0.01
                state.digits = 2
                state.algo_engine.vp_engine.price_bin_size = 0.50
            elif "BTC" in sym or "ETH" in sym:
                state.tick_size = 0.10
                state.digits = 2
                state.algo_engine.vp_engine.price_bin_size = 5.0
            elif any(c in sym for c in ("EUR", "GBP", "USD", "JPY", "AUD")):
                state.tick_size = 0.00001
                state.digits = 5
                state.algo_engine.vp_engine.price_bin_size = 0.0005

            self.states[sym] = state
        return self.states[sym]

    def set_active(self, symbol: str) -> Optional[SymbolState]:
        sym = symbol.strip().upper() if symbol else ""
        if not sym:
            return None
        state = self.get_or_create(sym)
        self.active_symbol = sym
        return state

    def get_active(self) -> SymbolState:
        return self.get_or_create(self.active_symbol)

    def list_symbols(self) -> List[str]:
        return list(self.states.keys())
