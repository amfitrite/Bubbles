import threading
import numpy as np
import logging

logger = logging.getLogger(__name__)

class TickStore:
    def __init__(self, max_ticks=10_000_000):
        """
        Ring buffer for storing live ticks in memory for fast drawing.
        """
        self.max_ticks = max_ticks
        self.lock = threading.RLock()

        # We store structured arrays for fast slicing and numpy operations
        # ts, bid, ask, last, volume, flags, side
        self.dtype = np.dtype([
            ('ts', np.int64),
            ('bid', np.float64),
            ('ask', np.float64),
            ('last', np.float64),
            ('volume', np.float64),
            ('flags', np.int32),
            ('side', np.int8)  # 1 for buy, -1 for sell, 0 for unknown
        ])

        self.data = np.zeros(self.max_ticks, dtype=self.dtype)
        self.count = 0
        self.head = 0  # Where to insert the next tick

        self.last_ts = 0
        self.version = 0 # Incremented on every change so UI knows when to redraw

    def add_tick(self, ts, bid, ask, last, volume, flags, side=0):
        with self.lock:
            # Simple deduplication based on last_ts (we can improve hash dedupe later)
            if ts < self.last_ts:
                # Discard out of order or duplicate history overlapping live
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

    def add_ticks_batch(self, ticks):
        """
        ticks: list of tuples (ts, bid, ask, last, volume, flags, side)
        """
        with self.lock:
            added = 0
            for t in ticks:
                ts = t[0]
                if ts >= self.last_ts:
                    if ts > self.last_ts:
                        self.last_ts = ts

                    idx = self.head
                    self.data[idx]['ts'] = ts
                    self.data[idx]['bid'] = t[1]
                    self.data[idx]['ask'] = t[2]
                    self.data[idx]['last'] = t[3]
                    self.data[idx]['volume'] = t[4]
                    self.data[idx]['flags'] = t[5]
                    self.data[idx]['side'] = t[6]

                    self.head = (self.head + 1) % self.max_ticks
                    if self.count < self.max_ticks:
                        self.count += 1
                    added += 1

            if added > 0:
                self.version += 1
            return added

    def get_snapshot(self):
        """
        Returns a flat contiguous numpy array of all current ticks in chronological order.
        This is an O(N) operation but memory copies are fast in C/numpy.
        Used by the engine to compute grids/aggregations.
        """
        with self.lock:
            if self.count == 0:
                return np.zeros(0, dtype=self.dtype), self.version

            if self.count < self.max_ticks:
                # Buffer not full, from 0 to head
                snapshot = np.copy(self.data[:self.head])
            else:
                # Buffer full, ring wrapped around
                # chronological order: from head to end, then from 0 to head
                snapshot = np.concatenate((self.data[self.head:], self.data[:self.head]))

            return snapshot, self.version

    def clear(self):
        with self.lock:
            self.count = 0
            self.head = 0
            self.last_ts = 0
            self.version += 1
