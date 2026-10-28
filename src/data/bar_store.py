import threading
import numpy as np
import logging

logger = logging.getLogger(__name__)

class BarStore:
    """
    In-memory accumulator and storage for 1-second and 1-minute order flow bars.
    Provides fast aggregated data for Macro views.
    """
    def __init__(self, db_manager=None, max_1s=86_400, max_1m=10_000):
        self.db_manager = db_manager
        self.lock = threading.RLock()

        # dtype: ts, open, high, low, close, volume, buy_vol, sell_vol, vwap, ticks
        self.dtype = np.dtype([
            ('ts', np.int64),
            ('open', np.float64),
            ('high', np.float64),
            ('low', np.float64),
            ('close', np.float64),
            ('volume', np.float64),
            ('buy_vol', np.float64),
            ('sell_vol', np.float64),
            ('vwap', np.float64),
            ('ticks', np.int32)
        ])

        self.max_1s = max_1s
        self.max_1m = max_1m

        self.bars_1s = np.zeros(self.max_1s, dtype=self.dtype)
        self.count_1s = 0
        self.head_1s = 0

        self.bars_1m = np.zeros(self.max_1m, dtype=self.dtype)
        self.count_1m = 0
        self.head_1m = 0

        # Current forming accumulators
        self.current_1s = None
        self.current_1m = None
        self.version = 0

    def add_tick(self, symbol: str, ts: int, price: float, volume: float, side: int = 0):
        with self.lock:
            if price <= 0 or volume <= 0:
                return

            sec_ts = (ts // 1000) * 1000
            min_ts = (ts // 60000) * 60000

            # 1. Update 1s bar
            if self.current_1s is None or self.current_1s['ts'] != sec_ts:
                if self.current_1s is not None:
                    self._commit_1s_bar()
                self.current_1s = self._new_acc(sec_ts, price, volume, side)
            else:
                self._update_acc(self.current_1s, price, volume, side)

            # 2. Update 1m bar
            if self.current_1m is None or self.current_1m['ts'] != min_ts:
                if self.current_1m is not None:
                    self._commit_1m_bar(symbol)
                self.current_1m = self._new_acc(min_ts, price, volume, side)
            else:
                self._update_acc(self.current_1m, price, volume, side)

            self.version += 1

    def _new_acc(self, ts, price, volume, side):
        buy = volume if side == 1 else 0.0
        sell = volume if side == -1 else 0.0
        return {
            'ts': ts,
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': volume,
            'buy_vol': buy,
            'sell_vol': sell,
            'sum_pv': price * volume,
            'ticks': 1
        }

    def _update_acc(self, acc, price, volume, side):
        if price > acc['high']:
            acc['high'] = price
        if price < acc['low']:
            acc['low'] = price
        acc['close'] = price
        acc['volume'] += volume
        acc['sum_pv'] += price * volume
        acc['ticks'] += 1
        if side == 1:
            acc['buy_vol'] += volume
        elif side == -1:
            acc['sell_vol'] += volume

    def _commit_1s_bar(self):
        c = self.current_1s
        vwap = c['sum_pv'] / c['volume'] if c['volume'] > 0 else c['close']

        idx = self.head_1s
        self.bars_1s[idx] = (
            c['ts'], c['open'], c['high'], c['low'], c['close'],
            c['volume'], c['buy_vol'], c['sell_vol'], vwap, c['ticks']
        )
        self.head_1s = (self.head_1s + 1) % self.max_1s
        if self.count_1s < self.max_1s:
            self.count_1s += 1

    def _commit_1m_bar(self, symbol):
        c = self.current_1m
        vwap = c['sum_pv'] / c['volume'] if c['volume'] > 0 else c['close']

        record = (
            c['ts'], c['open'], c['high'], c['low'], c['close'],
            c['volume'], c['buy_vol'], c['sell_vol'], vwap, c['ticks']
        )

        idx = self.head_1m
        self.bars_1m[idx] = record
        self.head_1m = (self.head_1m + 1) % self.max_1m
        if self.count_1m < self.max_1m:
            self.count_1m += 1

        # Enqueue to SQLite persistent cache
        if self.db_manager:
            self.db_manager.enqueue_bars_1m(symbol, [record])

    def get_bars_1s(self, start_ts: int, end_ts: int):
        """Returns sorted array of 1s bars within [start_ts, end_ts]."""
        with self.lock:
            if self.count_1s == 0:
                return np.zeros(0, dtype=self.dtype)

            if self.count_1s < self.max_1s:
                arr = self.bars_1s[:self.head_1s]
            else:
                arr = np.concatenate((self.bars_1s[self.head_1s:], self.bars_1s[:self.head_1s]))

            mask = (arr['ts'] >= start_ts) & (arr['ts'] <= end_ts)
            return arr[mask]

    def get_bars_1m(self, start_ts: int, end_ts: int):
        """Returns sorted array of 1m bars within [start_ts, end_ts]."""
        with self.lock:
            if self.count_1m == 0:
                return np.zeros(0, dtype=self.dtype)

            if self.count_1m < self.max_1m:
                arr = self.bars_1m[:self.head_1m]
            else:
                arr = np.concatenate((self.bars_1m[self.head_1m:], self.bars_1m[:self.head_1m]))

            mask = (arr['ts'] >= start_ts) & (arr['ts'] <= end_ts)
            return arr[mask]
