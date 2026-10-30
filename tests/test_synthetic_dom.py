import unittest
import numpy as np
from src.engine.synthetic_dom import SyntheticDOMLadder
from src.util.time_utils import INTERVAL_MAP, nice_time_step

class TestSyntheticDOMLadder(unittest.TestCase):
    def setUp(self):
        self.dom = SyntheticDOMLadder()
        self.dtype = np.dtype([
            ('ts', np.int64),
            ('bid', np.float64),
            ('ask', np.float64),
            ('last', np.float64),
            ('volume', np.float64),
            ('flags', np.int32),
            ('side', np.int8)
        ])

    def test_accumulation_same_price_in_interval(self):
        # 3 ticks occurring within 5ms at the exact same price 2735.10
        ticks = np.array([
            (1001, 2735.05, 2735.15, 2735.10, 1.0, 32, 1),
            (1002, 2735.05, 2735.15, 2735.10, 2.0, 32, 1),
            (1004, 2735.05, 2735.15, 2735.10, 5.0, 64, -1),
        ], dtype=self.dtype)

        # Interval 5ms: all 3 ticks fall in bucket [1000, 1005)
        cells = self.dom.build_dom_ladder(ticks, interval_ms=5, tick_size=0.01)

        # Must merge into exactly 1 bubble!
        self.assertEqual(len(cells), 1)
        c = cells[0]
        self.assertEqual(c['volume'], 8.0) # 1 + 2 + 5
        self.assertEqual(c['buy_vol'], 3.0) # 1 + 2
        self.assertEqual(c['sell_vol'], 5.0) # 5
        self.assertEqual(c['tick_count'], 3)
        self.assertAlmostEqual(c['y'], 2735.10, places=2)

    def test_different_prices_in_same_interval(self):
        # 2 ticks in the same 5ms window, but at 2 different price levels (2735.10 and 2735.20)
        ticks = np.array([
            (1001, 2735.05, 2735.15, 2735.10, 2.0, 32, 1),
            (1003, 2735.15, 2735.25, 2735.20, 3.0, 32, 1),
        ], dtype=self.dtype)

        cells = self.dom.build_dom_ladder(ticks, interval_ms=5, tick_size=0.01)

        # Must produce 2 bubbles at their respective price levels in the DOM ladder
        self.assertEqual(len(cells), 2)
        prices = sorted([c['y'] for c in cells])
        self.assertAlmostEqual(prices[0], 2735.10, places=2)
        self.assertAlmostEqual(prices[1], 2735.20, places=2)

    def test_ticks_across_intervals_1ms_and_1s(self):
        # 2 ticks separated by 3 milliseconds
        ticks = np.array([
            (1000, 2735.05, 2735.15, 2735.10, 1.0, 32, 1),
            (1003, 2735.05, 2735.15, 2735.10, 2.0, 32, 1),
        ], dtype=self.dtype)

        # In 1ms interval: they are in different buckets (bucket 1000 and 1003) -> 2 bubbles
        cells_1ms = self.dom.build_dom_ladder(ticks, interval_ms=1, tick_size=0.01)
        self.assertEqual(len(cells_1ms), 2)

        # In 5ms interval: they fall in the same bucket [1000, 1005) -> 1 accumulated bubble
        cells_5ms = self.dom.build_dom_ladder(ticks, interval_ms=5, tick_size=0.01)
        self.assertEqual(len(cells_5ms), 1)
        self.assertEqual(cells_5ms[0]['volume'], 3.0)

        # In 1s interval (1000ms): same bucket -> 1 accumulated bubble
        cells_1s = self.dom.build_dom_ladder(ticks, interval_ms=1000, tick_size=0.01)
        self.assertEqual(len(cells_1s), 1)
        self.assertEqual(cells_1s[0]['volume'], 3.0)

if __name__ == "__main__":
    unittest.main()
