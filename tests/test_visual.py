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

    def test_auto_fit_deadband_stability(self):
        # Initial fit to price 4000 with range 10.0 (min_price=3995, max_price=4005)
        self.camera.center_price = 4000.0
        self.camera.price_range = 10.0
        self.camera.auto_fit_price = True

        # When price fluctuates inside the safe margin (3997 .. 4003), scale MUST NOT MOVE
        self.camera.update_auto_fit(3998.0, 4002.0, 0.01)
        self.assertEqual(self.camera.center_price, 4000.0)
        self.assertEqual(self.camera.price_range, 10.0)

        # Fluctuates again inside margin
        self.camera.update_auto_fit(3997.5, 4001.5, 0.01)
        self.assertEqual(self.camera.center_price, 4000.0)
        self.assertEqual(self.camera.price_range, 10.0)

    def test_canvas_symbol_info_and_rebuild(self):
        from PySide6.QtWidgets import QApplication
        from src.algo.tick_store import TickStore
        from src.ui.gl_canvas import GLCanvas

        _ = QApplication.instance() or QApplication([])
        store = TickStore(max_ticks=100)
        store.add_tick(1000, 2000.0, 2000.1, 2000.0, 1.0, 32, 1)

        canvas = GLCanvas(store)
        canvas.set_symbol_info("EURUSD", 0.0001, 5)
        self.assertEqual(canvas.symbol, "EURUSD")
        self.assertEqual(canvas.tick_size, 0.0001)
        self.assertEqual(canvas.digits, 5)

        # Ensure _rebuild_scene runs cleanly without NameError or TypeError
        canvas._rebuild_scene(1000)
        self.assertIsNotNone(canvas.current_layout)

    def test_auto_center_functionality(self):
        # 1. Camera auto_center tracking with deadband
        self.camera.auto_center = True
        self.camera.center_price = 4000.0
        self.camera.price_range = 10.0 # deadband = 1.50

        # Inside deadband (4000.50): center_price MUST NOT move at all
        self.camera.update_auto_center(4000.50)
        self.assertEqual(self.camera.center_price, 4000.0)

        # Outside deadband (4005.0): should lerp towards 4005.0
        self.camera.update_auto_center(4005.0)
        self.assertGreater(self.camera.center_price, 4000.0)
        self.assertLessEqual(self.camera.center_price, 4005.0)

        # 2. Vertical drag pauses auto_center
        self.camera.pan(0.0, 50.0) # vertical drag
        self.assertFalse(self.camera.auto_center)

        # 3. Horizontal drag pauses follow_live
        self.camera.follow_live = True
        self.camera.pan(50.0, 0.0) # horizontal drag
        self.assertFalse(self.camera.follow_live)

        # 4. Reset camera restores both
        self.camera.reset_to_recent(latest_time_ms=1000000, current_price=4010.0)
        self.assertTrue(self.camera.auto_center)
        self.assertTrue(self.camera.follow_live)
        self.assertEqual(self.camera.center_price, 4010.0)

if __name__ == "__main__":
    unittest.main()
