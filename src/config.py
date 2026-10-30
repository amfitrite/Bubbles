import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "fps_limit": "60",               # "60", "120", "UNLIMITED"
    "active_mode": "TOTAL_VOLUME",   # "SPLIT_PIE", "DELTA", "IMBALANCE", "TOTAL_VOLUME"
    "active_interval": "AUTO",       # "1ms" .. "1h", "AUTO"
    "min_gap_px": 6.0,
    "size_scale": 1.0,
    "imbalance_ratio": 3.0,
    "min_volume_filter": 0.0,
    "auto_fit_price": True,
    "follow_live": True,             # Auto scroll
    "auto_center": True,            # Auto center on market price
    "window": {
        "width": 1366,
        "height": 768,
        "x": -1,
        "y": -1,
        "is_maximized": False
    }
}

class SettingsManager:
    """
    Persistent Settings Manager for Bubbles Terminal.
    Stores and retrieves all user preferences to/from config.json.
    Guarantees settings are preserved across application restarts.
    """
    def __init__(self, filepath: Path = CONFIG_FILE):
        self.filepath = Path(filepath)
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """Loads configuration from JSON file with default fallback."""
        self.data = DEFAULT_SETTINGS.copy()
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    if isinstance(user_data, dict):
                        for k, v in user_data.items():
                            if isinstance(v, dict) and k in self.data and isinstance(self.data[k], dict):
                                self.data[k].update(v)
                            else:
                                self.data[k] = v
                logger.info(f"Loaded user settings from {self.filepath}")
            except Exception as e:
                logger.warning(f"Could not read settings from {self.filepath}: {e}. Using defaults.")
        else:
            self.save()
        return self.data

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True):
        self.data[key] = value
        if auto_save:
            self.save()

    def update(self, new_data: Dict[str, Any], auto_save: bool = True):
        for k, v in new_data.items():
            if isinstance(v, dict) and k in self.data and isinstance(self.data[k], dict):
                self.data[k].update(v)
            else:
                self.data[k] = v
        if auto_save:
            self.save()

    def save(self) -> bool:
        """Saves configuration atomically to disk."""
        try:
            temp_path = self.filepath.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            temp_path.replace(self.filepath)
            logger.debug(f"Saved user settings to {self.filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings to {self.filepath}: {e}")
            return False

# Global singleton
settings = SettingsManager()
