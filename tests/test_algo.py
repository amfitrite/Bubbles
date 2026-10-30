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

    def test_seconds_timeframes_10s_15s_30s(self):
        # Ticks spanning 40 seconds
        ticks = np.array([
            (0, 4000.0, 4000.1, 4000.0, 1.0, 32, 1),
            (5000, 4001.0, 4001.1, 4001.0, 2.0, 32, 1),    # falls in [0..10s)
            (12000, 4002.0, 4002.1, 4002.0, 3.0, 32, 1),   # falls in [10s..20s)
            (25000, 4003.0, 4003.1, 4003.0, 4.0, 64, -1),  # falls in [20s..30s)
            (35000, 4004.0, 4004.1, 4004.0, 5.0, 64, -1),  # falls in [30s..40s)
        ], dtype=TICK_DTYPE)

        # 10s timeframe: should produce 4 bubbles (buckets 0s, 10s, 20s, 30s)
        snap_10s = self.engine.compute_snapshot(ticks, interval_ms=10000, version=10)
        self.assertEqual(len(snap_10s.bubbles), 4)

        # 15s timeframe: should produce 3 bubbles (buckets 0s, 15s, 30s)
        snap_15s = self.engine.compute_snapshot(ticks, interval_ms=15000, version=15)
        self.assertEqual(len(snap_15s.bubbles), 3)

        # 30s timeframe: should produce 2 bubbles (buckets 0s, 30s)
        snap_30s = self.engine.compute_snapshot(ticks, interval_ms=30000, version=30)
        self.assertEqual(len(snap_30s.bubbles), 2)
        self.assertEqual(snap_30s.bubbles[0].volume, 10.0) # 1 + 2 + 3 + 4 = 10
        self.assertEqual(snap_30s.bubbles[1].volume, 5.0)

    def test_engine_reset(self):
        ticks = np.array([
            (1000, 4000.0, 4000.1, 4000.0, 10.0, 32, 1),
        ], dtype=TICK_DTYPE)
        self.engine.ingest_new_ticks(ticks)
        self.assertEqual(self.engine.vp_engine.total_volume, 10.0)
        self.engine.reset()
        self.assertEqual(self.engine.vp_engine.total_volume, 0.0)
        self.assertEqual(len(self.engine.vp_engine.profile), 0)

    def test_trajectory_epoch_anchor_immutability(self):
        # Generate 2000 ticks (> 1500 to trigger decimation)
        N = 2000
        ts = np.arange(1000000, 1000000 + N * 10, 10) # 10ms step
        prices = 4000.0 + np.sin(np.arange(N) * 0.1).round(2)
        ticks = np.zeros(N, dtype=TICK_DTYPE)
        ticks['ts'] = ts
        ticks['last'] = prices
        ticks['volume'] = 1.0

        # Window 1: ticks[0 : 1800]
        snap1 = self.engine.compute_snapshot(ticks[0:1800], interval_ms=1000, version=1)
        # Window 2: shifted by 1 tick [1 : 1801] (simulating 1 new tick arriving and window advancing)
        snap2 = self.engine.compute_snapshot(ticks[1:1801], interval_ms=1000, version=2)

        # Historical vertices that exist in both snapshots MUST have identical timestamps and prices
        common_ts1 = {pt[0]: pt[1] for pt in snap1.trajectory_points[:-1]}
        common_ts2 = {pt[0]: pt[1] for pt in snap2.trajectory_points[:-1]}

        overlap_keys = set(common_ts1.keys()) & set(common_ts2.keys())
        self.assertGreater(len(overlap_keys), 50) # strong sample size
        for k in overlap_keys:
            self.assertEqual(common_ts1[k], common_ts2[k], f"Vertex at ts {k} changed across frames!")

if __name__ == "__main__":
    unittest.main()
