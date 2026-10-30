import os
import unittest
import tempfile
from pathlib import Path
from src.config import SettingsManager, DEFAULT_SETTINGS

class TestSettingsPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.mgr = SettingsManager(self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_values(self):
        self.assertEqual(self.mgr.get("fps_limit"), "60")
        self.assertEqual(self.mgr.get("active_mode"), "TOTAL_VOLUME")
        self.assertEqual(self.mgr.get("active_interval"), "AUTO")
        self.assertEqual(self.mgr.get("min_gap_px"), 6.0)
        self.assertEqual(self.mgr.get("follow_live"), True)

    def test_save_and_reload(self):
        self.mgr.set("fps_limit", "120")
        self.mgr.set("active_mode", "DELTA")
        self.mgr.set("active_interval", "15s")
        self.mgr.set("min_gap_px", 8.5)
        self.mgr.set("size_scale", 1.4)
        self.mgr.set("follow_live", False)

        # Create new manager pointing to the same file
        mgr2 = SettingsManager(self.config_path)
        self.assertEqual(mgr2.get("fps_limit"), "120")
        self.assertEqual(mgr2.get("active_mode"), "DELTA")
        self.assertEqual(mgr2.get("active_interval"), "15s")
        self.assertEqual(mgr2.get("min_gap_px"), 8.5)
        self.assertEqual(mgr2.get("size_scale"), 1.4)
        self.assertEqual(mgr2.get("follow_live"), False)

    def test_fps_options(self):
        # 60, 120, UNLIMITED
        for fps in ["60", "120", "UNLIMITED"]:
            self.mgr.set("fps_limit", fps)
            self.assertEqual(self.mgr.get("fps_limit"), fps)

if __name__ == "__main__":
    unittest.main()
