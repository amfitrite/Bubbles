import unittest
import numpy as np
from src.algo.tick_store import TickStore
from src.algo.accumulator import OrderFlowAlgoEngine
from src.algo.volume_profile import VolumeProfileEngine
from src.algo.models import TICK_DTYPE

class TestAlgoEngine(unittest.TestCase):
    def setUp(self):
        self.store = TickStore(max_ticks=1000)
        self.engine = OrderFlowAlgoEngine(imbalance_ratio_threshold=3.0)

    def test_volume_profile_and_poc(self):
        vp = VolumeProfileEngine(price_bin_size=1.0)
        ticks = np.array([
            (1000, 4000.0, 4000.1, 4000.0, 10.0, 32, 1),
            (2000, 4001.0, 4001.1, 4001.0, 50.0, 32, 1), # POC candidate
            (3000, 4002.0, 4002.1, 4002.0, 20.0, 64, -1),
        ], dtype=TICK_DTYPE)

        vp.update_ticks(ticks)
        macro = vp.get_macro_structure()

        self.assertEqual(macro.poc_price, 4001.0)
        self.assertEqual(macro.session_high, 4002.0)
        self.assertEqual(macro.session_low, 4000.0)
        self.assertEqual(macro.total_volume, 80.0)
        self.assertAlmostEqual(macro.session_vwap, (4000*10 + 4001*50 + 4002*20) / 80.0)

    def test_snapshot_generation(self):
        ticks = np.array([
            (100100, 4000.0, 4000.1, 4000.0, 5.0, 32, 1),
            (100300, 4000.1, 4000.2, 4000.1, 10.0, 32, 1),
            (100700, 4000.2, 4000.3, 4000.2, 2.0, 64, -1),
        ], dtype=TICK_DTYPE)

        self.engine.ingest_new_ticks(ticks)
        snap = self.engine.compute_snapshot(ticks, interval_ms=1000, version=1)

        self.assertEqual(len(snap.bubbles), 1)
        self.assertEqual(snap.bubbles[0].volume, 17.0)
        self.assertTrue(len(snap.trajectory_points) >= 2)
        self.assertEqual(snap.macro.total_volume, 17.0)

    def test_imbalance_detection(self):
        # 4 buy volume, 1 sell volume -> ratio 4.0 >= 3.0 threshold -> BUY_IMBALANCE
        ticks = np.array([
            (100100, 4000.0, 4000.1, 4000.0, 4.0, 32, 1),   # Buy 4.0
            (100200, 4000.0, 4000.1, 4000.0, 1.0, 64, -1),  # Sell 1.0
        ], dtype=TICK_DTYPE)

        self.engine.ingest_new_ticks(ticks)
        snap = self.engine.compute_snapshot(ticks, interval_ms=1000, version=2)

        self.assertEqual(len(snap.bubbles), 1)
        b = snap.bubbles[0]
        self.assertEqual(b.buy_vol, 4.0)
        self.assertEqual(b.sell_vol, 1.0)
        self.assertEqual(b.imbalance_state, "BUY_IMBALANCE")
        self.assertAlmostEqual(b.imbalance_ratio, 4.0)

    def test_multi_interval_micro_1ms(self):
        # When interval_ms=1 (Micro mode), each tick at distinct ms forms its own bubble
        ticks = np.array([
            (1000, 4000.0, 4000.1, 4000.0, 2.0, 32, 1),
            (1001, 4000.2, 4000.3, 4000.2, 3.0, 32, 1),
            (1002, 4000.1, 4000.2, 4000.1, 1.5, 64, -1),
        ], dtype=TICK_DTYPE)

        snap = self.engine.compute_snapshot(ticks, interval_ms=1, version=3)
        self.assertEqual(len(snap.bubbles), 3)
        self.assertAlmostEqual(snap.bubbles[0].price, 4000.0)
        self.assertAlmostEqual(snap.bubbles[1].price, 4000.2)
        self.assertAlmostEqual(snap.bubbles[2].price, 4000.1)

if __name__ == "__main__":
    unittest.main()
