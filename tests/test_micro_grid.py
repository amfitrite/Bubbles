import unittest
import numpy as np
from src.engine.micro_grid import MicroGrid

class TestMicroGrid(unittest.TestCase):
    def setUp(self):
        self.grid = MicroGrid()

        dtype = np.dtype([
            ('ts', np.int64),
            ('bid', np.float64),
            ('ask', np.float64),
            ('last', np.float64),
            ('volume', np.float64),
            ('flags', np.int32),
            ('side', np.int8)
        ])

        # Two ticks in the same bucket (bucket_ms=100) and same price bin (tick_size=1.0)
        self.ticks = np.array([
            (1010, 10.0, 10.2, 10.1, 5.0, 0, 1),
            (1020, 10.0, 10.2, 10.5, 5.0, 0, -1)
        ], dtype=dtype)

    def test_vwap_style(self):
        cells = self.grid.build_grid(self.ticks, time_span_ms=1000, bucket_ms=100, tick_size=1.0, style='vwap')
        self.assertEqual(len(cells), 1)

        c = cells[0]
        self.assertEqual(c['volume'], 10.0)
        self.assertEqual(c['buy_vol'], 5.0)
        self.assertEqual(c['sell_vol'], 5.0)
        self.assertEqual(c['tick_count'], 2)

        # VWAP = (10.1 * 5 + 10.5 * 5) / 10 = (50.5 + 52.5) / 10 = 103 / 10 = 10.3
        self.assertAlmostEqual(c['y'], 10.3)
        # Time center = (1010 * 5 + 1020 * 5) / 10 = (5050 + 5100) / 10 = 10150 / 10 = 1015
        self.assertAlmostEqual(c['x'], 1015.0)

    def test_bookmap_style(self):
        cells = self.grid.build_grid(self.ticks, time_span_ms=1000, bucket_ms=100, tick_size=1.0, style='bookmap')
        self.assertEqual(len(cells), 1)

        c = cells[0]
        # Exact price bin center
        # prices are 10.1 and 10.5 -> p_indices are 10.1//1.0 = 10 and 10.5//1.0 = 10
        # center of bin 10 is (10 + 0.5) * 1.0 = 10.5
        self.assertAlmostEqual(c['y'], 10.5)

if __name__ == '__main__':
    unittest.main()
