import unittest
from src.algo.models import AlgoBubble
from src.visual.camera import Camera
from src.visual.layout_engine import VisualLayoutEngine

class TestVisualEngine(unittest.TestCase):
    def setUp(self):
        self.camera = Camera(1000, 500)
        self.camera.center_time_ms = 1000000.0
        self.camera.time_span_ms = 10000.0 # 10s span = 10ms per pixel
        self.camera.center_price = 4000.0
        self.camera.price_range = 10.0

    def test_pixel_gap_enforcement(self):
        # 2 bubbles separated by only 1 millisecond at the exact same price
        b1 = AlgoBubble(
            ts=1000000, price=4000.0, volume=5.0, buy_vol=4.0, sell_vol=1.0,
            delta=3.0, delta_ratio=0.6, imbalance_state="BUY_IMBALANCE",
            imbalance_ratio=4.0, tick_count=1, interval_ms=1, price_level=4000.0
        )
        b2 = AlgoBubble(
            ts=1000001, price=4000.0, volume=5.0, buy_vol=4.0, sell_vol=1.0,
            delta=3.0, delta_ratio=0.6, imbalance_state="BUY_IMBALANCE",
            imbalance_ratio=4.0, tick_count=1, interval_ms=1, price_level=4000.0
        )

        layout = VisualLayoutEngine(min_gap_px=6.0, size_scale=1.0)
        nodes = layout.process_layout([b1, b2], self.camera)

        self.assertEqual(len(nodes), 2)
        # Find node 1 and node 2 by ts
        n1 = next(n for n in nodes if n.algo.ts == 1000000)
        n2 = next(n for n in nodes if n.algo.ts == 1000001)

        # Raw distance would be 0.1 pixel (1ms at 10ms/px)
        self.assertAlmostEqual(abs(n2.raw_sx - n1.raw_sx), 0.1, places=1)

        # But visual distance MUST be >= r1 + r2 + min_gap!
        min_expected_gap = n1.radius + n2.radius + 6.0
        actual_visual_gap = abs(n2.visual_x - n1.visual_x)
        self.assertGreaterEqual(actual_visual_gap, min_expected_gap - 0.01)

        # Mathematical truth MUST be completely preserved!
        self.assertEqual(n1.algo.ts, 1000000)
        self.assertEqual(n2.algo.ts, 1000001)
        self.assertEqual(n1.algo.price, 4000.0)
        self.assertEqual(n2.algo.price, 4000.0)

if __name__ == "__main__":
    unittest.main()
