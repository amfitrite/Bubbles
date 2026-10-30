import unittest
import numpy as np
from src.data.bar_store import BarStore
from src.engine.macro_series import MacroSeries

class TestBarStoreAndMacroSeries(unittest.TestCase):
    def test_bar_store_aggregation(self):
        bs = BarStore(db_manager=None)

        # Feed ticks across two separate seconds
        bs.add_tick("XAUUSD", 1700000000100, 2400.10, 1.0, side=1)
        bs.add_tick("XAUUSD", 1700000000500, 2400.20, 2.0, side=1)
        # Next second
        bs.add_tick("XAUUSD", 1700000001200, 2400.30, 3.0, side=-1)

        # Bar for first second should be committed
        bars_1s = bs.get_bars_1s(1700000000000, 1700000002000)
        self.assertEqual(len(bars_1s), 1)
        self.assertEqual(bars_1s[0]['ticks'], 2)
        self.assertEqual(bars_1s[0]['volume'], 3.0)
        self.assertEqual(bars_1s[0]['buy_vol'], 3.0)

    def test_macro_series_from_bars(self):
        ms = MacroSeries()

        dtype = np.dtype([
            ('ts', np.int64), ('open', np.float64), ('high', np.float64),
            ('low', np.float64), ('close', np.float64), ('volume', np.float64),
            ('buy_vol', np.float64), ('sell_vol', np.float64),
            ('vwap', np.float64), ('ticks', np.int32)
        ])

        bars = np.array([
            (1000, 2400.0, 2401.0, 2399.0, 2400.5, 10.0, 6.0, 4.0, 2400.2, 5),
            (2000, 2400.5, 2402.0, 2400.0, 2401.5, 20.0, 15.0, 5.0, 2401.0, 10)
        ], dtype=dtype)

        # Bucket ms = 5000 (both bars fall in same bucket)
        macro_bubbles = ms.build_from_bars(bars, bucket_ms=5000)
        self.assertEqual(len(macro_bubbles), 1)
        mb = macro_bubbles[0]
        self.assertEqual(mb['volume'], 30.0)
        self.assertEqual(mb['ticks'], 15)
        # Expected VWAP: (2400.2 * 10 + 2401.0 * 20) / 30 = (24002 + 48020) / 30 = 72022 / 30 = 2400.7333...
        expected_vwap = (2400.2 * 10.0 + 2401.0 * 20.0) / 30.0
        self.assertAlmostEqual(mb['y'], expected_vwap, places=3)

    def test_macro_series_from_ticks(self):
        ms = MacroSeries()

        tick_dtype = np.dtype([
            ('ts', np.int64), ('bid', np.float64), ('ask', np.float64),
            ('last', np.float64), ('volume', np.float64), ('flags', np.int32),
            ('side', np.int8)
        ])

        ticks = np.array([
            (100, 2400.0, 2400.1, 2400.05, 5.0, 32, 1),
            (200, 2400.2, 2400.3, 2400.25, 10.0, 32, 1),
            (6000, 2401.0, 2401.1, 2401.05, 8.0, 64, -1)
        ], dtype=tick_dtype)

        # Bucket ms = 5000 (first two in bucket 0, third in bucket 1)
        macro_bubbles = ms.build_from_ticks(ticks, bucket_ms=5000)
        self.assertEqual(len(macro_bubbles), 2)
        self.assertEqual(macro_bubbles[0]['volume'], 15.0)
        self.assertEqual(macro_bubbles[1]['volume'], 8.0)

if __name__ == "__main__":
    unittest.main()
