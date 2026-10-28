import unittest
from src.engine.lod import LODSelector
from src.engine.camera import Camera
from src.util.time_utils import nice_time_step, nice_tick_step
from src.util.math_utils import clamp, lerp, smoothstep

class TestLOD(unittest.TestCase):
    def test_smoothstep(self):
        self.assertEqual(smoothstep(0.0, 0.0, 1.0), 0.0)
        self.assertEqual(smoothstep(1.0, 0.0, 1.0), 1.0)
        self.assertAlmostEqual(smoothstep(0.5, 0.0, 1.0), 0.5)

    def test_nice_time_step(self):
        # 120 ms target should pick 100 ms
        step = nice_time_step(120)
        self.assertEqual(step, 100)

        # 4500 ms target should pick 5000 ms
        step = nice_time_step(4500)
        self.assertEqual(step, 5000)

    def test_nice_tick_step(self):
        # target step 0.045 with tick size 0.01 -> 5 * 0.01 = 0.05
        step = nice_tick_step(0.045, 0.01)
        self.assertAlmostEqual(step, 0.05)

    def test_lod_micro_macro_weights(self):
        # 1 minute time span (micro) -> macroWeight must be 0.0
        b_ms, p_bin, macro_w, rows = LODSelector.calculate(60_000, 2.0, 0.01)
        self.assertEqual(macro_w, 0.0)
        self.assertEqual(rows, 24)

        # 35 minutes time span (macro) -> macroWeight must be 1.0
        b_ms, p_bin, macro_w, rows = LODSelector.calculate(35 * 60_000, 10.0, 0.01)
        self.assertEqual(macro_w, 1.0)
        self.assertEqual(rows, 4)

class TestCamera(unittest.TestCase):
    def test_coordinate_transforms(self):
        cam = Camera(viewport_width=1000, viewport_height=500)
        cam.center_time_ms = 1_000_000.0
        cam.time_span_ms = 100_000.0
        cam.center_price = 2000.0
        cam.price_range = 10.0

        # Center should map to width / 2
        sx = cam.time_to_screen_x(1_000_000.0)
        self.assertAlmostEqual(sx, 500.0)

        # Center price should map to height / 2
        sy = cam.price_to_screen_y(2000.0)
        self.assertAlmostEqual(sy, 250.0)

        # Roundtrip screen -> world -> screen
        orig_x = 320.0
        t = cam.screen_x_to_time(orig_x)
        self.assertAlmostEqual(cam.time_to_screen_x(t), orig_x)

    def test_zoom_clamps(self):
        cam = Camera(1000, 500)
        cam.zoom(1000.0) # excessive zoom in
        self.assertGreaterEqual(cam.time_span_ms, cam.MIN_TIME_SPAN)

        cam.zoom(0.000001) # excessive zoom out
        self.assertLessEqual(cam.time_span_ms, cam.MAX_TIME_SPAN)

if __name__ == "__main__":
    unittest.main()
