import unittest
import numpy as np
from src.engine.synthetic_dom import SyntheticDOMLadder

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

    def test_build_interval_series_accumulation(self):
        # 4 ticks arriving within the same 1-second interval [1000000, 1001000)
        ticks = np.array([
            (1000100, 2735.05, 2735.15, 2735.10, 1.0, 32, 1),
            (1000250, 2735.10, 2735.20, 2735.15, 2.0, 32, 1),
            (1000500, 2735.15, 2735.25, 2735.20, 3.0, 64, -1),
            (1000800, 2735.10, 2735.20, 2735.15, 4.0, 64, -1),
        ], dtype=self.dtype)

        # In interval 1s (1000ms): all 4 ticks MUST fuse into exactly 1 bubble!
        bubbles = self.dom.build_interval_series(ticks, interval_ms=1000)
        self.assertEqual(len(bubbles), 1)

        b = bubbles[0]
        self.assertEqual(b['volume'], 10.0) # 1 + 2 + 3 + 4
        self.assertEqual(b['buy_vol'], 3.0)  # 1 + 2
        self.assertEqual(b['sell_vol'], 7.0) # 3 + 4
        self.assertEqual(b['tick_count'], 4)
        self.assertEqual(b['t_bucket'], 1000000)

    def test_accumulation_same_price_in_interval(self):
        ticks = np.array([
            (1001, 2735.05, 2735.15, 2735.10, 1.0, 32, 1),
            (1002, 2735.05, 2735.15, 2735.10, 2.0, 32, 1),
            (1004, 2735.05, 2735.15, 2735.10, 5.0, 64, -1),
        ], dtype=self.dtype)

        cells = self.dom.build_dom_ladder(ticks, interval_ms=5, price_bin=0.01)
        self.assertEqual(len(cells), 1)
        c = cells[0]
        self.assertEqual(c['volume'], 8.0)
        self.assertEqual(c['buy_vol'], 3.0)
        self.assertEqual(c['sell_vol'], 5.0)
        self.assertEqual(c['tick_count'], 3)

    def test_different_prices_in_same_interval(self):
        ticks = np.array([
            (1001, 2735.05, 2735.15, 2735.10, 2.0, 32, 1),
            (1003, 2735.15, 2735.25, 2735.20, 3.0, 32, 1),
        ], dtype=self.dtype)

        cells = self.dom.build_dom_ladder(ticks, interval_ms=5, price_bin=0.01)
        self.assertEqual(len(cells), 2)

if __name__ == "__main__":
    unittest.main()
