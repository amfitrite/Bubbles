import numpy as np

class SyntheticDOMLadder:
    """
    Synthetic Level 2 Depth-of-Market (L2 DOM) Ladder Aggregator.
    
    Transforms raw streaming ticks into discrete Level 2 price-depth order flow cells
    accumulated over arbitrary millisecond intervals (e.g. 1ms, 5ms, 100ms, 1s, 1m, 1h, 4h).
    
    Rule: Exactly 1 bubble per price level per interval, accumulating all ticks that
    executed at that price within the given interval window.
    """
    def __init__(self):
        pass

    def build_dom_ladder(self, ticks_array, interval_ms: int, tick_size: float = 0.01, style: str = 'dom_ladder'):
        """
        ticks_array: numpy structured array (ts, bid, ask, last, volume, flags, side)
        interval_ms: accumulation interval in milliseconds (e.g. 1, 5, 50, 1000, 60000, 3600000)
        tick_size: minimum price increment (e.g. 0.01)
        style: 'dom_ladder' (exact discrete price bin) or 'vwap' (volume-weighted price)

        Returns list of accumulated L2 DOM cell dictionaries.
        """
        if len(ticks_array) == 0 or interval_ms <= 0 or tick_size <= 0:
            return []

        # Determine price for each tick: prefer 'last', fallback to 'bid'
        prices = np.where(ticks_array['last'] > 0, ticks_array['last'], ticks_array['bid'])

        # Time bucket and Price ladder index
        # 1. Discrete time bucket index
        t_buckets = (ticks_array['ts'] // interval_ms) * interval_ms
        # 2. Discrete price bin index (L2 DOM price row)
        p_indices = np.round(prices / tick_size).astype(np.int64)

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

            if side == 1:
                cell['buy_vol'] += vol
            elif side == -1:
                cell['sell_vol'] += vol
            else:
                # If side is 0, classify aggressor by trade price relative to bid/ask
                bid = ticks_array['bid'][i]
                ask = ticks_array['ask'][i]
                if ask > 0 and price >= ask:
                    cell['buy_vol'] += vol
                elif bid > 0 and price <= bid:
                    cell['sell_vol'] += vol
                else:
                    # Split equally if between spread
                    cell['buy_vol'] += vol * 0.5
                    cell['sell_vol'] += vol * 0.5

        # Format into drawing cells
        drawing_cells = []
        for (t_b, p_idx), cell in grid.items():
            vol = cell['total_vol']
            if vol <= 0:
                continue

            vwap = cell['sum_pv'] / vol
            time_center = cell['sum_tv'] / vol

            # In DOM ladder style, bubble is anchored at the exact discrete price level
            if style == 'dom_ladder':
                y_val = p_idx * tick_size
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
