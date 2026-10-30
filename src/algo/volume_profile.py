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

        # Vectorized Cumulative Delta
        is_buy = (sides == 1) | ((flags & 32) != 0)
        is_sell = ((sides == -1) | ((flags & 64) != 0)) & (~is_buy)
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

        # Compute Value Area (70% Volume around POC)
        sorted_bins = sorted(self.profile.items(), key=lambda x: x[0])
        target_va_vol = self.total_volume * 0.70

        running_vol = 0.0
        va_low = self.session_low
        va_high = self.session_high

        # Symmetrical outward expansion from POC
        if sorted_bins:
            va_bins = sorted(self.profile.items(), key=lambda x: x[1], reverse=True)
            accum_va = 0.0
            va_prices = []
            for bp, bvol in va_bins:
                accum_va += bvol
                va_prices.append(bp)
                if accum_va >= target_va_vol:
                    break
            if va_prices:
                va_low = min(va_prices)
                va_high = max(va_prices)

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
