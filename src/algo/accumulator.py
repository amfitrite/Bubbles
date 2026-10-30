import numpy as np
from typing import List, Dict, Tuple
from src.algo.models import AlgoBubble, MacroStructure, OrderFlowSnapshot
from src.algo.volume_profile import VolumeProfileEngine

INTERVAL_MAP: Dict[str, int] = {
    '1ms': 1,
    '5ms': 5,
    '10ms': 10,
    '50ms': 50,
    '100ms': 100,
    '250ms': 250,
    '500ms': 500,
    '1s': 1000,
    '5s': 5000,
    '10s': 10000,
    '15s': 15000,
    '30s': 30000,
    '1m': 60000,
    '5m': 300000,
    '15m': 900000,
    '1h': 3600000,
    '4h': 14400000,
}

INTERVAL_OPTIONS = list(INTERVAL_MAP.keys()) + ['AUTO']

class OrderFlowAlgoEngine:
    """
    Complete Asynchronous Algorithm Engine.
    Processes raw tick stream into:
      1. Aggregated micro bubbles (with VWAP, Delta, Imbalance 3:1+)
      2. Continuous Price Trajectory path
      3. Macro Structure (Session VWAP, High, Low, POC, Value Area)
      4. Horizontal Volume Profile at price
    """
    def __init__(self, imbalance_ratio_threshold: float = 3.0, min_imbalance_volume: float = 1.0):
        self.imbalance_ratio_threshold = imbalance_ratio_threshold
        self.min_imbalance_volume = min_imbalance_volume
        self.vp_engine = VolumeProfileEngine(price_bin_size=0.50)
        self.processed_version = 0

    def ingest_new_ticks(self, ticks: np.ndarray):
        """Updates continuous session statistics (Volume Profile, VWAP, High/Low, Trajectory)."""
        self.vp_engine.update_ticks(ticks)

    def set_imbalance_threshold(self, ratio: float):
        if ratio > 1.0:
            self.imbalance_ratio_threshold = ratio

    def compute_snapshot(self, visible_ticks: np.ndarray, interval_ms: int,
                         version: int) -> OrderFlowSnapshot:
        """
        Creates an immutable thread-safe OrderFlowSnapshot for the visual engine.
        """
        if len(visible_ticks) == 0:
            macro = self.vp_engine.get_macro_structure()
            return OrderFlowSnapshot(
                bubbles=[],
                trajectory_points=[],
                volume_profile=self.vp_engine.profile.copy(),
                macro=macro,
                last_price=macro.session_vwap,
                last_ts=0,
                version=version
            )

        prices = np.where(visible_ticks['last'] > 0, visible_ticks['last'], visible_ticks['bid'])
        last_price = float(prices[-1])
        last_ts = int(visible_ticks['ts'][-1])

        # 1. Build Interval Series (1 bubble per time bucket)
        bubbles = self._build_bubbles(visible_ticks, prices, interval_ms)

        # 2. Extract Trajectory Points in visible window (Rock-solid immutable historical vertices)
        n_ticks = len(visible_ticks)
        if n_ticks <= 1200:
            step = 1
        elif n_ticks <= 2400:
            step = 2
        elif n_ticks <= 4800:
            step = 4
        else:
            step = 8

        if step == 1:
            trajectory = [(int(visible_ticks['ts'][i]), float(prices[i])) for i in range(n_ticks)]
        else:
            # Fixed index alignment prevents jitter across frames
            indices = np.arange(0, n_ticks, step)
            trajectory = [(int(visible_ticks['ts'][idx]), float(prices[idx])) for idx in indices]

        # Ensure latest live tick is always the exact live tip
        if not trajectory or trajectory[-1][0] != last_ts:
            trajectory.append((last_ts, last_price))

        # 3. Macro Structure
        macro = self.vp_engine.get_macro_structure()

        return OrderFlowSnapshot(
            bubbles=bubbles,
            trajectory_points=trajectory,
            volume_profile=self.vp_engine.profile.copy(),
            macro=macro,
            last_price=last_price,
            last_ts=last_ts,
            version=version
        )

    def _build_bubbles(self, ticks: np.ndarray, prices: np.ndarray, interval_ms: int) -> List[AlgoBubble]:
        n_ticks = len(ticks)
        if n_ticks == 0:
            return []

        ts_buckets = ticks['ts'] // interval_ms
        # Contiguous index grouping in O(N): ticks['ts'] is monotonically non-decreasing
        diffs = np.flatnonzero(np.diff(ts_buckets)) + 1
        starts = np.r_[0, diffs]
        ends = np.r_[diffs, n_ticks]

        volumes = ticks['volume']
        sides = ticks['side']
        flags = ticks['flags']

        # Vectorized pre-computation across entire slice
        pv = prices * volumes
        buy_mask = (sides == 1) | ((flags & 32) != 0)
        sell_mask = (sides == -1) | ((flags & 64) != 0)
        neutral_mask = ~buy_mask & ~sell_mask

        # Assign volume proportions per tick (50/50 split for neutral ticks)
        tick_buy_vol = np.where(buy_mask, volumes, np.where(neutral_mask, volumes * 0.5, 0.0))
        tick_sell_vol = np.where(sell_mask, volumes, np.where(neutral_mask, volumes * 0.5, 0.0))

        # Vectorized bucket reduction in pure C (O(N) single-pass)
        tot_vols = np.add.reduceat(volumes, starts)
        sum_pvs = np.add.reduceat(pv, starts)
        buy_vols = np.add.reduceat(tick_buy_vol, starts)
        sell_vols = np.add.reduceat(tick_sell_vol, starts)

        vwaps = np.where(tot_vols > 0, sum_pvs / np.maximum(1e-12, tot_vols), 0.0)
        deltas = buy_vols - sell_vols
        delta_ratios = np.where(tot_vols > 0, deltas / np.maximum(1e-12, tot_vols), 0.0)
        bucket_indices = ts_buckets[starts]
        time_centers = (bucket_indices * interval_ms) + int(interval_ms / 2.0)
        tick_counts = ends - starts

        bubbles: List[AlgoBubble] = []
        threshold = self.imbalance_ratio_threshold
        min_imb = self.min_imbalance_volume

        for i in range(len(starts)):
            tot_vol = float(tot_vols[i])
            if tot_vol <= 0:
                continue

            vwap = float(vwaps[i])
            buy_vol = float(buy_vols[i])
            sell_vol = float(sell_vols[i])
            delta = float(deltas[i])
            delta_ratio = float(delta_ratios[i])
            time_center = int(time_centers[i])
            t_count = int(tick_counts[i])

            # 3:1 Imbalance detection
            imb_state = "BALANCED"
            imb_ratio = 1.0

            if tot_vol >= min_imb:
                if sell_vol <= 0 and buy_vol > 0:
                    imb_state = "BUY_IMBALANCE"
                    imb_ratio = 999.0
                elif buy_vol <= 0 and sell_vol > 0:
                    imb_state = "SELL_IMBALANCE"
                    imb_ratio = 999.0
                elif buy_vol >= threshold * sell_vol:
                    imb_state = "BUY_IMBALANCE"
                    imb_ratio = buy_vol / sell_vol
                elif sell_vol >= threshold * buy_vol:
                    imb_state = "SELL_IMBALANCE"
                    imb_ratio = sell_vol / buy_vol

            bubbles.append(AlgoBubble(
                ts=time_center,
                price=vwap,
                volume=tot_vol,
                buy_vol=buy_vol,
                sell_vol=sell_vol,
                delta=delta,
                delta_ratio=delta_ratio,
                imbalance_state=imb_state,
                imbalance_ratio=imb_ratio,
                tick_count=t_count,
                interval_ms=interval_ms,
                price_level=vwap
            ))

        return bubbles
