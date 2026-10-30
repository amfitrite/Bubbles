import threading
import numpy as np
from typing import Tuple
from src.algo.models import TICK_DTYPE

class TickStore:
    """
    High-throughput circular ring buffer for real-time tick ingestion.
    Supports asynchronous thread-safe ingestion and zero-copy slicing for the algo engine.
    """
    def __init__(self, max_ticks: int = 1_000_000):
        self.max_ticks = max_ticks
        self.lock = threading.RLock()
        self.data = np.zeros(self.max_ticks, dtype=TICK_DTYPE)
        self.count = 0
        self.head = 0
        self.last_ts = 0
        self.version = 0

    def add_tick(self, ts: int, bid: float, ask: float, last: float, volume: float, flags: int, side: int = 0) -> bool:
        with self.lock:
            # Ignore ticks older than our highest seen timestamp to prevent chronological corruption
            if ts < self.last_ts:
                return False

            if ts > self.last_ts:
                self.last_ts = ts

            idx = self.head
            self.data[idx]['ts'] = ts
            self.data[idx]['bid'] = bid
            self.data[idx]['ask'] = ask
            self.data[idx]['last'] = last
            self.data[idx]['volume'] = volume
            self.data[idx]['flags'] = flags
            self.data[idx]['side'] = side

            self.head = (self.head + 1) % self.max_ticks
            if self.count < self.max_ticks:
                self.count += 1

            self.version += 1
            return True

    def get_snapshot(self) -> Tuple[np.ndarray, int]:
        """
        Returns a chronologically sorted contiguous snapshot slice of available ticks
        and the version number.
        """
        with self.lock:
            v = self.version
            if self.count == 0:
                return np.empty(0, dtype=TICK_DTYPE), v

            if self.count < self.max_ticks:
                # Buffer has not wrapped yet; [0 .. head] is strictly sorted
                return self.data[:self.count].copy(), v
            else:
                # Buffer wrapped; oldest starts at self.head
                part1 = self.data[self.head:]
                part2 = self.data[:self.head]
                return np.concatenate((part1, part2)), v

    def get_time_range(self, min_ts: int, max_ts: int) -> np.ndarray:
        """
        Retrieves ticks falling strictly in [min_ts, max_ts] via binary search.
        """
        snapshot, _ = self.get_snapshot()
        if len(snapshot) == 0:
            return snapshot

        ts_arr = snapshot['ts']
        start_idx = np.searchsorted(ts_arr, min_ts, side='left')
        end_idx = np.searchsorted(ts_arr, max_ts, side='right')
        return snapshot[start_idx:end_idx]
