import numpy as np

class MacroSeries:
    """
    Computes single VWAP Macro Bubbles per time bucket.
    Operates on either 1s/1m bars or raw ticks.
    """
    def __init__(self):
        pass

    def build_from_bars(self, bars_array, bucket_ms: int):
        """
        bars_array: numpy structured array of bars (ts, open, high, low, close, volume, buy_vol, sell_vol, vwap, ticks)
        bucket_ms: width of each macro bucket in milliseconds

        Returns list of macro bubble dictionaries:
        [{ 'x': time_center, 'y': vwap, 'volume': vol, 'buy_vol': ..., 'sell_vol': ..., 'ticks': count }]
        """
        if len(bars_array) == 0 or bucket_ms <= 0:
            return []

        # Bucket group
        b_indices = bars_array['ts'] // bucket_ms
        unique_buckets = np.unique(b_indices)

        macro_bubbles = []
        for b_idx in unique_buckets:
            mask = (b_indices == b_idx)
            sub = bars_array[mask]

            total_vol = float(np.sum(sub['volume']))
            if total_vol <= 0:
                continue

            # Volume-weighted price (VWAP)
            sum_pv = float(np.sum(sub['vwap'] * sub['volume']))
            vwap = sum_pv / total_vol

            # Volume-weighted time center
            sum_tv = float(np.sum(sub['ts'] * sub['volume']))
            time_center = sum_tv / total_vol

            buy_vol = float(np.sum(sub['buy_vol']))
            sell_vol = float(np.sum(sub['sell_vol']))
            tick_count = int(np.sum(sub['ticks']))

            macro_bubbles.append({
                'x': time_center,
                'y': vwap,
                'volume': total_vol,
                'buy_vol': buy_vol,
                'sell_vol': sell_vol,
                'ticks': tick_count
            })

        return macro_bubbles

    def build_from_ticks(self, ticks_array, bucket_ms: int):
        """
        Fallback direct aggregation from raw ticks array when bars are scarce.
        """
        if len(ticks_array) == 0 or bucket_ms <= 0:
            return []

        prices = np.where(ticks_array['last'] > 0, ticks_array['last'], ticks_array['bid'])
        b_indices = ticks_array['ts'] // bucket_ms
        unique_buckets = np.unique(b_indices)

        macro_bubbles = []
        for b_idx in unique_buckets:
            mask = (b_indices == b_idx)
            sub_ts = ticks_array['ts'][mask]
            sub_vol = ticks_array['volume'][mask]
            sub_p = prices[mask]
            sub_side = ticks_array['side'][mask]

            total_vol = float(np.sum(sub_vol))
            if total_vol <= 0:
                continue

            sum_pv = float(np.sum(sub_p * sub_vol))
            vwap = sum_pv / total_vol

            sum_tv = float(np.sum(sub_ts * sub_vol))
            time_center = sum_tv / total_vol

            buy_mask = (sub_side == 1)
            sell_mask = (sub_side == -1)
            buy_vol = float(np.sum(sub_vol[buy_mask]))
            sell_vol = float(np.sum(sub_vol[sell_mask]))
            tick_count = len(sub_ts)

            macro_bubbles.append({
                'x': time_center,
                'y': vwap,
                'volume': total_vol,
                'buy_vol': buy_vol,
                'sell_vol': sell_vol,
                'ticks': tick_count
            })

        return macro_bubbles
