import unittest
import numpy as np
from src.algo.tick_store import TickStore
from src.algo.accumulator import IntervalAccumulator
from src.algo.models import TICK_DTYPE

class TestAlgoEngine(unittest.TestCase):
    def setUp(self):
        self.store = TickStore(max_ticks=1000)
        self.acc = IntervalAccumulator(imbalance_ratio_threshold=3.0, min_imbalance_volume=1.0)

    def test_tick_store_ring_buffer(self):
        for i in range(150):
            self.store.add_tick(
                ts=1000 + i * 10,
                bid=2700.0,
                ask=2700.1,
                last=2700.05,
                volume=1.0,
                flags=32,
                side=1
            )
        snapshot, ver = self.store.get_snapshot()
        self.assertEqual(len(snapshot), 150)
        self.assertEqual(ver, 150)
        self.assertEqual(self.store.last_ts, 1000 + 149 * 10)

    def test_one_bubble_per_interval_accumulation(self):
        # 5 ticks within the same 1-second interval [1000000, 1001000)
        ticks = np.array([
            (1000100, 4000.0, 4000.1, 4000.0, 2.0, 32, 1),
            (1000200, 4000.1, 4000.2, 4000.1, 3.0, 32, 1),
            (1000500, 4000.2, 4000.3, 4000.2, 5.0, 64, -1),
        ], dtype=TICK_DTYPE)

        bubbles = self.acc.build_interval_series(ticks, interval_ms=1000)
        self.assertEqual(len(bubbles), 1)

        b = bubbles[0]
        # Total volume: 2 + 3 + 5 = 10
        self.assertEqual(b.volume, 10.0)
        self.assertEqual(b.buy_vol, 5.0)
        self.assertEqual(b.sell_vol, 5.0)
        self.assertEqual(b.delta, 0.0)
        self.assertEqual(b.imbalance_state, "BALANCED")
        # VWAP: (4000.0*2 + 4000.1*3 + 4000.2*5) / 10 = (8000 + 12000.3 + 20001) / 10 = 4000.13
        self.assertAlmostEqual(b.price, 4000.13, places=2)

    def test_imbalance_buy_and_sell(self):
        # Buy imbalance: buy 12, sell 2 -> ratio 6:1 >= 3:1
        buy_ticks = np.array([
            (2000100, 4000.0, 4000.1, 4000.1, 12.0, 32, 1),
            (2000200, 4000.0, 4000.1, 4000.0, 2.0, 64, -1),
        ], dtype=TICK_DTYPE)
        buy_bubbles = self.acc.build_interval_series(buy_ticks, interval_ms=1000)
        self.assertEqual(len(buy_bubbles), 1)
        self.assertEqual(buy_bubbles[0].imbalance_state, "BUY_IMBALANCE")
        self.assertAlmostEqual(buy_bubbles[0].imbalance_ratio, 6.0)

        # Sell imbalance: sell 15, buy 3 -> ratio 5:1 >= 3:1
        sell_ticks = np.array([
            (3000100, 4000.0, 4000.1, 4000.0, 15.0, 64, -1),
            (3000200, 4000.0, 4000.1, 4000.1, 3.0, 32, 1),
        ], dtype=TICK_DTYPE)
        sell_bubbles = self.acc.build_interval_series(sell_ticks, interval_ms=1000)
        self.assertEqual(len(sell_bubbles), 1)
        self.assertEqual(sell_bubbles[0].imbalance_state, "SELL_IMBALANCE")
        self.assertAlmostEqual(sell_bubbles[0].imbalance_ratio, 5.0)

if __name__ == "__main__":
    unittest.main()
