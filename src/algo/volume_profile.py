import math
from typing import Dict, List, Tuple
import numpy as np
from src.algo.models import MacroStructure

class VolumeProfileEngine:
    """
    Real-Time Auction Market Structure & Volume Profile Engine.
    Computes Point of Control (POC), Value Area (VAH/VAL), Session VWAP, and Session High/Low.
    """
    def __init__(self, price_bin_size: float = 0.50):
        self.price_bin_size = price_bin_size
        self.profile: Dict[float, float] = {} # binned_price -> volume
        self.session_high = -float('inf')
        self.session_low = float('inf')
        self.sum_pv = 0.0
        self.total_volume = 0.0
        self.net_cumulative_delta = 0.0
        self.trajectory_points: List[Tuple[int, float]] = [] # Max 5000 points
        self.max_trajectory_len = 5000

    def reset(self):
        self.profile.clear()
        self.session_high = -float('inf')
        self.session_low = float('inf')
        self.sum_pv = 0.0
        self.total_volume = 0.0
        self.net_cumulative_delta = 0.0
        self.trajectory_points.clear()

    def update_ticks(self, ticks: np.ndarray):
        if len(ticks) == 0:
            return

        volumes = ticks['volume']
        valid = volumes > 0
        if not np.any(valid):
            return

        prices = np.where(ticks['last'] > 0, ticks['last'], ticks['bid'])[valid]
        vols = volumes[valid]
        sides = ticks['side'][valid]
        flags = ticks['flags'][valid]

        # Vectorized Session High/Low
        high_val = float(np.max(prices))
        low_val = float(np.min(prices))
        if high_val > self.session_high:
            self.session_high = high_val
        if low_val < self.session_low:
            self.session_low = low_val

        # Vectorized Session VWAP sums
        self.sum_pv += float(np.sum(prices * vols))
        self.total_volume += float(np.sum(vols))

        # Vectorized Cumulative Delta (Strict Aggressor + Inferred)
        price_diff = np.diff(prices, prepend=prices[0])
        is_conf_buy = (sides == 1) | ((flags & 32) != 0)
        is_conf_sell = ((sides == -1) | ((flags & 64) != 0)) & ~is_conf_buy
        is_unclassified = ~is_conf_buy & ~is_conf_sell
        is_inf_buy = ((sides == 2) | ((sides == 0) & (price_diff > 0))) & is_unclassified
        is_inf_sell = ((sides == -2) | ((sides == 0) & (price_diff < 0))) & is_unclassified & ~is_inf_buy

        is_buy = is_conf_buy | is_inf_buy
        is_sell = is_conf_sell | is_inf_sell
        buy_delta = float(np.sum(vols[is_buy]))
        sell_delta = float(np.sum(vols[is_sell]))
        self.net_cumulative_delta += (buy_delta - sell_delta)

        # Vectorized Volume Profile Bins
        bin_prices = np.round(np.round(prices / self.price_bin_size) * self.price_bin_size, 4)
        unique_bins, bin_indices = np.unique(bin_prices, return_inverse=True)
        bin_vols = np.bincount(bin_indices, weights=vols)
        for bp, bv in zip(unique_bins, bin_vols):
            bp_r = round(float(bp), 4)
            self.profile[bp_r] = self.profile.get(bp_r, 0.0) + float(bv)

    def get_macro_structure(self) -> MacroStructure:
        if self.total_volume <= 0:
            return MacroStructure(
                session_high=0.0, session_low=0.0, session_vwap=0.0,
                poc_price=0.0, value_area_high=0.0, value_area_low=0.0,
                total_volume=0.0, net_cumulative_delta=0.0
            )

        vwap = self.sum_pv / self.total_volume

        # Find Point of Control (POC)
        poc_price = max(self.profile.keys(), key=lambda k: self.profile[k]) if self.profile else vwap

        # Compute Value Area (70% Volume around POC using CME/CBOT Dual-Bin Outward Expansion)
        sorted_bins = sorted(self.profile.items(), key=lambda x: x[0])
        target_va_vol = self.total_volume * 0.70

        va_low = self.session_low
        va_high = self.session_high

        if sorted_bins:
            # Find POC index in sorted_bins
            poc_idx = 0
            for idx, (bp, _) in enumerate(sorted_bins):
                if abs(bp - poc_price) < 1e-4:
                    poc_idx = idx
                    break

            va_vol = sorted_bins[poc_idx][1]
            up_idx = poc_idx + 1
            down_idx = poc_idx - 1
            n_bins = len(sorted_bins)

            while va_vol < target_va_vol and (up_idx < n_bins or down_idx >= 0):
                # Sum next 2 price bins above
                up_vol = 0.0
                up_steps = 0
                for k in range(2):
                    if up_idx + k < n_bins:
                        up_vol += sorted_bins[up_idx + k][1]
                        up_steps += 1

                # Sum next 2 price bins below
                down_vol = 0.0
                down_steps = 0
                for k in range(2):
                    if down_idx - k >= 0:
                        down_vol += sorted_bins[down_idx - k][1]
                        down_steps += 1

                if up_steps == 0 and down_steps == 0:
                    break

                if up_steps > 0 and (down_steps == 0 or up_vol > down_vol):
                    va_vol += up_vol
                    up_idx += up_steps
                elif down_steps > 0 and (up_steps == 0 or down_vol > up_vol):
                    va_vol += down_vol
                    down_idx -= down_steps
                else:
                    va_vol += (up_vol + down_vol)
                    up_idx += up_steps
                    down_idx -= down_steps

            final_low_idx = max(0, down_idx + 1)
            final_high_idx = min(n_bins - 1, up_idx - 1)
            va_low = sorted_bins[final_low_idx][0]
            va_high = sorted_bins[final_high_idx][0]

        return MacroStructure(
            session_high=self.session_high if self.session_high != -float('inf') else vwap,
            session_low=self.session_low if self.session_low != float('inf') else vwap,
            session_vwap=vwap,
            poc_price=poc_price,
            value_area_high=va_high,
            value_area_low=va_low,
            total_volume=self.total_volume,
            net_cumulative_delta=self.net_cumulative_delta
        )
