import numpy as np

class ModeClassifier:
    """
    Implements the 3 Display Modes: Classic, Delta, and Diagonal Imbalance.
    Strictly follows Section 6 formulas in README.
    """
    DEFAULT_IMB_RATIO = 3.0
    DEFAULT_MIN_VOL = 5.0
    DEFAULT_DELTA_THRESHOLD = 0.15

    @classmethod
    def classify_delta(cls, buy_vol: float, sell_vol: float, total_vol: float, threshold: float = 0.15):
        """
        Calculates delta color type and intensity.
        deltaRatio >= +0.15 -> delta_buy
        deltaRatio <= -0.15 -> delta_sell
        otherwise -> delta_neutral
        """
        if total_vol <= 0:
            return 'delta_neutral', 0.0, 0.0

        delta = buy_vol - sell_vol
        delta_ratio = delta / total_vol

        if delta_ratio >= threshold:
            color_type = 'delta_buy'
        elif delta_ratio <= -threshold:
            color_type = 'delta_sell'
        else:
            color_type = 'delta_neutral'

        return color_type, delta, delta_ratio

    @classmethod
    def compute_micro_diagonal_imbalances(cls, cells, ratio: float = 3.0, min_vol: float = 5.0):
        """
        cells: list of micro cells with 't_idx', 'p_idx', 'buy_vol', 'sell_vol', 'volume'
        Returns dict keyed by (t_idx, p_idx) -> { 'imb_type': 'buy'|'sell'|'balanced', 'has_stack': bool }
        """
        # Map cells by (t_idx, p_idx)
        cell_map = {(c['t_idx'], c['p_idx']): c for c in cells}

        results = {}
        for (t_idx, p_idx), c in cell_map.items():
            buy_v = c['buy_vol']
            sell_v = c['sell_vol']

            # Check diagonal neighbors:
            # Buy imbalance compares buy[t, p] against sell[t, p - 1]
            diag_sell_cell = cell_map.get((t_idx, p_idx - 1))
            diag_sell_vol = diag_sell_cell['sell_vol'] if diag_sell_cell else 0.0

            # Sell imbalance compares sell[t, p] against buy[t, p + 1]
            diag_buy_cell = cell_map.get((t_idx, p_idx + 1))
            diag_buy_vol = diag_buy_cell['buy_vol'] if diag_buy_cell else 0.0

            is_buy_imb = False
            is_sell_imb = False

            if buy_v >= min_vol:
                denom_sell = max(1.0, diag_sell_vol)
                if (buy_v / denom_sell) >= ratio:
                    is_buy_imb = True

            if sell_v >= min_vol:
                denom_buy = max(1.0, diag_buy_vol)
                if (sell_v / denom_buy) >= ratio:
                    is_sell_imb = True

            if is_buy_imb and not is_sell_imb:
                imb_type = 'imb_buy'
            elif is_sell_imb and not is_buy_imb:
                imb_type = 'imb_sell'
            elif is_buy_imb and is_sell_imb:
                # Pick side with larger ratio
                r_buy = buy_v / max(1.0, diag_sell_vol)
                r_sell = sell_v / max(1.0, diag_buy_vol)
                imb_type = 'imb_buy' if r_buy >= r_sell else 'imb_sell'
            else:
                imb_type = 'balanced'

            results[(t_idx, p_idx)] = {
                'imb_type': imb_type,
                'has_stack': False
            }

        # Check stack glow: 2+ consecutive price bins in same time bucket
        for (t_idx, p_idx), info in results.items():
            if info['imb_type'] in ('imb_buy', 'imb_sell'):
                above = results.get((t_idx, p_idx + 1))
                below = results.get((t_idx, p_idx - 1))
                if (above and above['imb_type'] == info['imb_type']) or \
                   (below and below['imb_type'] == info['imb_type']):
                    info['has_stack'] = True

        return results
