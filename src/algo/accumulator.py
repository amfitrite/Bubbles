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
    '15s': 15000,
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

        # 2. Extract Trajectory Points in visible window
        # Downsample if dense to keep trajectory path clean and fast
        step = max(1, len(visible_ticks) // 800)
        sliced_ticks = visible_ticks[::step]
        sliced_prices = prices[::step]
        trajectory = [(int(sliced_ticks['ts'][i]), float(sliced_prices[i])) for i in range(len(sliced_ticks))]

        # Ensure latest tick is always included in trajectory
        if trajectory and trajectory[-1][0] != last_ts:
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
        ts_buckets = ticks['ts'] // interval_ms
        unique_buckets = np.unique(ts_buckets)

        bubbles: List[AlgoBubble] = []
        threshold = self.imbalance_ratio_threshold

        for b_idx in unique_buckets:
            mask = (ts_buckets == b_idx)
            sub_vol = ticks['volume'][mask]
            sub_p = prices[mask]
            sub_side = ticks['side'][mask]
            sub_flags = ticks['flags'][mask]

            tot_vol = float(np.sum(sub_vol))
            if tot_vol <= 0:
                continue

            sum_pv = float(np.sum(sub_p * sub_vol))
            vwap = sum_pv / tot_vol

            t_bucket = int(b_idx * interval_ms)
            time_center = t_bucket + int(interval_ms / 2.0)

            buy_mask = (sub_side == 1) | ((sub_flags & 32) != 0)
            sell_mask = (sub_side == -1) | ((sub_flags & 64) != 0)
            neutral_mask = ~buy_mask & ~sell_mask

            buy_vol = float(np.sum(sub_vol[buy_mask]))
            sell_vol = float(np.sum(sub_vol[sell_mask]))
            if np.any(neutral_mask):
                neut_vol = float(np.sum(sub_vol[neutral_mask]))
                buy_vol += neut_vol * 0.5
                sell_vol += neut_vol * 0.5

            delta = buy_vol - sell_vol
            delta_ratio = delta / tot_vol if tot_vol > 0 else 0.0

            # 3:1 Imbalance detection
            imb_state = "BALANCED"
            imb_ratio = 1.0

            if tot_vol >= self.min_imbalance_volume:
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
                tick_count=len(sub_vol),
                interval_ms=interval_ms,
                price_level=vwap
            ))

        return bubbles
