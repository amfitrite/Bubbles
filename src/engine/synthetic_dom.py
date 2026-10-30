import numpy as np

class SyntheticDOMLadder:
    """
    Synthetic Level 2 Depth-of-Market (L2 DOM) and Multi-Interval Accumulator.
    Supports:
    1. build_interval_series: Accumulates ALL ticks in each time interval (1ms..4h)
       into exactly 1 bubble per interval (VWAP + volume sum).
    2. build_dom_ladder: Price-level ladder accumulation within each interval.
    """
    def __init__(self):
        pass

    def build_interval_series(self, ticks_array, interval_ms: int):
        """
        Accumulates all ticks falling into each interval window into exactly 1 bubble per interval!
        interval_ms: 1, 5, 10, 50, 100, 250, 500, 1000, 5000, 60000, etc.
        """
        if len(ticks_array) == 0 or interval_ms <= 0:
            return []

        prices = np.where(ticks_array['last'] > 0, ticks_array['last'], ticks_array['bid'])
        b_indices = ticks_array['ts'] // interval_ms
        unique_buckets = np.unique(b_indices)

        bubbles = []
        for b_idx in unique_buckets:
            mask = (b_indices == b_idx)
            sub_vol = ticks_array['volume'][mask]
            sub_p = prices[mask]
            sub_side = ticks_array['side'][mask]
            sub_flags = ticks_array['flags'][mask]

            total_vol = float(np.sum(sub_vol))
            if total_vol <= 0:
                continue

            sum_pv = float(np.sum(sub_p * sub_vol))
            vwap = sum_pv / total_vol

            t_bucket = int(b_idx * interval_ms)
            time_center = t_bucket + (interval_ms / 2.0)

            buy_mask = (sub_side == 1) | ((sub_flags & 32) != 0)
            sell_mask = (sub_side == -1) | ((sub_flags & 64) != 0)
            neutral_mask = ~buy_mask & ~sell_mask

            buy_vol = float(np.sum(sub_vol[buy_mask]))
            sell_vol = float(np.sum(sub_vol[sell_mask]))
            if np.any(neutral_mask):
                neut_vol = float(np.sum(sub_vol[neutral_mask]))
                buy_vol += neut_vol * 0.5
                sell_vol += neut_vol * 0.5

            tick_count = len(sub_vol)

            bubbles.append({
                't_idx': int(b_idx),
                'p_idx': 0,
                't_bucket': t_bucket,
                'x': time_center,
                'y': vwap,
                'vwap': vwap,
                'volume': total_vol,
                'buy_vol': buy_vol,
                'sell_vol': sell_vol,
                'tick_count': tick_count,
                'interval_ms': interval_ms
            })

        return bubbles

    def build_dom_ladder(self, ticks_array, interval_ms: int, price_bin: float = 0.01, style: str = 'dom_ladder'):
        """
        ticks_array: numpy structured array (ts, bid, ask, last, volume, flags, side)
        interval_ms: accumulation interval in milliseconds
        price_bin: price grouping height
        style: 'dom_ladder' or 'vwap'
        """
        if len(ticks_array) == 0 or interval_ms <= 0 or price_bin <= 0:
            return []

        prices = np.where(ticks_array['last'] > 0, ticks_array['last'], ticks_array['bid'])
        t_buckets = (ticks_array['ts'] // interval_ms) * interval_ms
        p_indices = np.round(prices / price_bin).astype(np.int64)

        grid = {}
        for i in range(len(ticks_array)):
            t_b = t_buckets[i]
            p_idx = p_indices[i]
            key = (t_b, p_idx)

            vol = float(ticks_array['volume'][i])
            if vol <= 0:
                continue

            price = float(prices[i])
            ts = int(ticks_array['ts'][i])
            side = int(ticks_array['side'][i])
            flags = int(ticks_array['flags'][i])

            if key not in grid:
                grid[key] = {
                    't_bucket': t_b,
                    'p_idx': p_idx,
                    'total_vol': 0.0,
                    'buy_vol': 0.0,
                    'sell_vol': 0.0,
                    'sum_pv': 0.0,
                    'sum_tv': 0.0,
                    'tick_count': 0
                }

            cell = grid[key]
            cell['total_vol'] += vol
            cell['sum_pv'] += price * vol
            cell['sum_tv'] += ts * vol
            cell['tick_count'] += 1

            if side == 1 or (flags & 32):
                cell['buy_vol'] += vol
            elif side == -1 or (flags & 64):
                cell['sell_vol'] += vol
            else:
                bid = ticks_array['bid'][i]
                ask = ticks_array['ask'][i]
                if ask > 0 and price >= ask:
                    cell['buy_vol'] += vol
                elif bid > 0 and price <= bid:
                    cell['sell_vol'] += vol
                else:
                    cell['buy_vol'] += vol * 0.5
                    cell['sell_vol'] += vol * 0.5

        drawing_cells = []
        for (t_b, p_idx), cell in grid.items():
            vol = cell['total_vol']
            if vol <= 0:
                continue

            vwap = cell['sum_pv'] / vol
            time_center = cell['sum_tv'] / vol

            if style == 'dom_ladder':
                y_val = p_idx * price_bin
            else:
                y_val = vwap

            drawing_cells.append({
                't_idx': t_b // interval_ms,
                'p_idx': p_idx,
                't_bucket': t_b,
                'x': time_center,
                'y': y_val,
                'vwap': vwap,
                'volume': vol,
                'buy_vol': cell['buy_vol'],
                'sell_vol': cell['sell_vol'],
                'tick_count': cell['tick_count'],
                'interval_ms': interval_ms
            })

        return drawing_cells
