import numpy as np
from typing import List, Dict, Optional
from src.algo.models import AlgoBubble

# Standard Interval Mappings in milliseconds
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

class IntervalAccumulator:
    """
    Mathematical aggregation engine.
    Transforms raw incoming ticks into discrete aggregated bubbles with exact VWAP,
    Cumulative Volume Delta (CVD), and Order Flow Imbalance.
    """
    def __init__(self, imbalance_ratio_threshold: float = 3.0, min_imbalance_volume: float = 1.0):
        self.imbalance_ratio_threshold = imbalance_ratio_threshold
        self.min_imbalance_volume = min_imbalance_volume

    def set_imbalance_threshold(self, ratio: float):
        if ratio > 1.0:
            self.imbalance_ratio_threshold = ratio

    def build_interval_series(self, ticks_array: np.ndarray, interval_ms: int) -> List[AlgoBubble]:
        """
        Fuses ALL ticks within each interval window into exactly ONE single bubble per interval.
        Calculates:
          - Total Volume = sum(volume)
          - VWAP = sum(price * volume) / total_volume
          - Buy Vol & Sell Vol (using MT5 flags or trade side)
          - Net Delta = Buy Vol - Sell Vol
          - Imbalance state: BUY_IMBALANCE if buy >= 3 * sell, SELL_IMBALANCE if sell >= 3 * buy
        """
        if len(ticks_array) == 0 or interval_ms <= 0:
            return []

        prices = np.where(ticks_array['last'] > 0, ticks_array['last'], ticks_array['bid'])
        ts_buckets = ticks_array['ts'] // interval_ms
        unique_buckets = np.unique(ts_buckets)

        bubbles: List[AlgoBubble] = []
        threshold = self.imbalance_ratio_threshold

        for b_idx in unique_buckets:
            mask = (ts_buckets == b_idx)
            sub_vol = ticks_array['volume'][mask]
            sub_p = prices[mask]
            sub_side = ticks_array['side'][mask]
            sub_flags = ticks_array['flags'][mask]

            tot_vol = float(np.sum(sub_vol))
            if tot_vol <= 0:
                continue

            sum_pv = float(np.sum(sub_p * sub_vol))
            vwap = sum_pv / tot_vol

            t_bucket = int(b_idx * interval_ms)
            time_center = t_bucket + int(interval_ms / 2.0)

            # Buy: side == 1 or flag bit 32
            # Sell: side == -1 or flag bit 64
            buy_mask = (sub_side == 1) | ((sub_flags & 32) != 0)
            sell_mask = (sub_side == -1) | ((sub_flags & 64) != 0)
            neutral_mask = ~buy_mask & ~sell_mask

            buy_vol = float(np.sum(sub_vol[buy_mask]))
            sell_vol = float(np.sum(sub_vol[sell_mask]))
            if np.any(neutral_mask):
                neut_vol = float(np.sum(sub_vol[neutral_mask]))
                # Neutral volume is evenly divided between buy and sell
                buy_vol += neut_vol * 0.5
                sell_vol += neut_vol * 0.5

            delta = buy_vol - sell_vol
            delta_ratio = delta / tot_vol if tot_vol > 0 else 0.0

            # Imbalance evaluation
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

    def build_ladder_series(self, ticks_array: np.ndarray, interval_ms: int, price_bin: float) -> List[AlgoBubble]:
        """
        Micro L2 DOM Ladder accumulation:
        Groups ticks by both time interval AND discrete price level bins.
        """
        if len(ticks_array) == 0 or interval_ms <= 0 or price_bin <= 0:
            return []

        prices = np.where(ticks_array['last'] > 0, ticks_array['last'], ticks_array['bid'])
        t_buckets = (ticks_array['ts'] // interval_ms) * interval_ms
        p_indices = np.round(prices / price_bin).astype(np.int64)

        grid: Dict[tuple, dict] = {}
        threshold = self.imbalance_ratio_threshold

        for i in range(len(ticks_array)):
            t_b = int(t_buckets[i])
            p_idx = int(p_indices[i])
            key = (t_b, p_idx)

            vol = float(ticks_array['volume'][i])
            if vol <= 0:
                continue

            price = float(prices[i])
            side = int(ticks_array['side'][i])
            flags = int(ticks_array['flags'][i])

            if key not in grid:
                grid[key] = {
                    't_bucket': t_b,
                    'price_level': p_idx * price_bin,
                    'total_vol': 0.0,
                    'buy_vol': 0.0,
                    'sell_vol': 0.0,
                    'sum_pv': 0.0,
                    'count': 0
                }

            cell = grid[key]
            cell['total_vol'] += vol
            cell['sum_pv'] += price * vol
            cell['count'] += 1

            is_buy = (side == 1) or ((flags & 32) != 0)
            is_sell = (side == -1) or ((flags & 64) != 0)

            if is_buy:
                cell['buy_vol'] += vol
            elif is_sell:
                cell['sell_vol'] += vol
            else:
                cell['buy_vol'] += vol * 0.5
                cell['sell_vol'] += vol * 0.5

        bubbles: List[AlgoBubble] = []
        for key, cell in grid.items():
            tot_vol = cell['total_vol']
            if tot_vol <= 0:
                continue

            vwap = cell['sum_pv'] / tot_vol
            buy_vol = cell['buy_vol']
            sell_vol = cell['sell_vol']
            delta = buy_vol - sell_vol
            delta_ratio = delta / tot_vol

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

            time_center = cell['t_bucket'] + int(interval_ms / 2.0)

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
                tick_count=cell['count'],
                interval_ms=interval_ms,
                price_level=cell['price_level']
            ))

        return bubbles
