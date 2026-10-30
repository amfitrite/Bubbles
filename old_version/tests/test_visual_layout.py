import unittest
from src.ui.bubble_renderer import BubbleRenderer
from src.engine.camera import Camera
from src.engine.modes import ModeClassifier

class TestVisualLayoutAndSpacing(unittest.TestCase):
    def setUp(self):
        self.renderer = BubbleRenderer()
        self.camera = Camera(1280, 720)

    def test_volume_1_compact_baseline(self):
        # Baseline volume 1.0 must strictly map to compact radius (3.0px)
        rad = self.renderer.compute_radius(volume=1.0, p95_volume=1.0, is_macro=False)
        self.assertAlmostEqual(rad, 3.0, places=1)

    def test_high_volume_scaling(self):
        # High volume (e.g. 50.0) should scale up significantly
        rad_small = self.renderer.compute_radius(volume=1.0, p95_volume=20.0)
        rad_large = self.renderer.compute_radius(volume=30.0, p95_volume=20.0)
        self.assertGreater(rad_large, rad_small * 2)

    def test_cell_aware_spacing_clamping(self):
        # Even if volume is huge, radius must not exceed available cell space
        rad_clamped = self.renderer.compute_radius(
            volume=100.0, p95_volume=10.0, is_macro=False, max_cell_radius=8.0
        )
        self.assertLessEqual(rad_clamped, 8.0)

    def test_camera_stretch(self):
        orig_price_range = self.camera.price_range
        orig_time_span = self.camera.time_span_ms

        # Stretch vertically (dy < 0 reduces range, stretching price on screen)
        self.camera.stretch(dx_px=0, dy_px=-50)
        self.assertLess(self.camera.price_range, orig_price_range)
        self.assertFalse(self.camera.auto_fit_price)

        # Stretch horizontally (dx > 0 expands time span)
        self.camera.stretch(dx_px=50, dy_px=0)
        self.assertGreater(self.camera.time_span_ms, orig_time_span)
        self.assertFalse(self.camera.follow_live)

    def test_mode_classifier_constants(self):
        self.assertEqual(ModeClassifier.MODE_SPLIT_PIE, "SPLIT_PIE")
        self.assertEqual(ModeClassifier.MODE_NET_DELTA, "NET_DELTA")
        self.assertEqual(ModeClassifier.MODE_TOTAL_VOLUME, "TOTAL_VOLUME")

if __name__ == "__main__":
    unittest.main()
