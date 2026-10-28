import numpy as np

class MicroGrid:
    def __init__(self):
        # We will hold the aggregated cell data
        self.cells = [] # list of dicts for now, can be numpy array for perf

    def build_grid(self, ticks_array, time_span_ms, bucket_ms, tick_size, style='vwap'):
        """
        ticks_array: numpy structured array of ticks (ts, bid, ask, last, volume, flags, side)
        time_span_ms: the total visible time span in ms
        bucket_ms: width of each time bucket
        tick_size: height of each price bin
        style: 'vwap' (Smooth hybrid) or 'bookmap' (Strict price level)

        Returns a list of cell dictionaries:
        [{ 'x': time_center, 'y': price_y, 'volume': total_vol, 'buy_vol': ..., 'sell_vol': ..., 'ticks': count }]
        """
        if len(ticks_array) == 0 or bucket_ms <= 0 or tick_size <= 0:
            return []

        # Group ticks by bucket and bin
        # t_idx = ts // bucket_ms
        # p_idx = price // tick_size

        # We use 'last' price if available (>0), otherwise fallback to bid
        prices = np.where(ticks_array['last'] > 0, ticks_array['last'], ticks_array['bid'])

        t_indices = ticks_array['ts'] // bucket_ms
        p_indices = prices // tick_size

        # Unique cells
        # We can use numpy unique with return_inverse to group, or a simple dict loop
        # Since we might have max 10k-50k ticks per view, python dict is reasonably fast for M0,
        # but numpy grouping is better for production. Let's do a basic dict grouping first.

        grid = {}
        for i in range(len(ticks_array)):
            t_idx = t_indices[i]
            p_idx = p_indices[i]
            key = (t_idx, p_idx)

            vol = ticks_array['volume'][i]
            price = prices[i]
            ts = ticks_array['ts'][i]
            side = ticks_array['side'][i]

            if key not in grid:
                grid[key] = {
                    't_idx': t_idx,
                    'p_idx': p_idx,
                    'total_vol': 0.0,
                    'buy_vol': 0.0,
                    'sell_vol': 0.0,
                    'sum_price_vol': 0.0, # for vwap
                    'sum_time_vol': 0.0,  # for volume-weighted time center
                    'tick_count': 0
                }

            cell = grid[key]
            cell['total_vol'] += vol
            cell['sum_price_vol'] += price * vol
            cell['sum_time_vol'] += ts * vol
            cell['tick_count'] += 1

            if side == 1:
                cell['buy_vol'] += vol
            elif side == -1:
                cell['sell_vol'] += vol

        # Now convert grid to drawing cells
        drawing_cells = []
        for (t_idx, p_idx), cell in grid.items():
            vol = cell['total_vol']
            if vol <= 0:
                continue

            vwap = cell['sum_price_vol'] / vol
            time_center = cell['sum_time_vol'] / vol

            # Determine Y based on user style preference
            if style == 'vwap':
                y_val = vwap
            elif style == 'bookmap':
                # Center of the exact price bin
                y_val = (p_idx + 0.5) * tick_size
            else:
                y_val = vwap

            drawing_cells.append({
                't_idx': t_idx,
                'p_idx': p_idx,
                'x': time_center,
                'y': y_val,
                'volume': vol,
                'buy_vol': cell['buy_vol'],
                'sell_vol': cell['sell_vol'],
                'tick_count': cell['tick_count']
            })

        return drawing_cells
