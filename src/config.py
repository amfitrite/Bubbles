import json
import os
from pathlib import Path

# Base directory is the root of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Default configuration
DEFAULT_CONFIG = {
    "network": {
        "ports": [5558],
        "host": "127.0.0.1"
    },
    "database": {
        "path": "data/bubbles.db",
        "tick_retention_days": 7,
        "bar_retention_days": 365
    },
    "logging": {
        "level": "INFO",
        "file": "logs/bubbles.log"
    }
}

class Config:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = BASE_DIR / "config.json"

        self.config_path = Path(config_path)
        self.settings = self._load_config()

    def _load_config(self):
        if not self.config_path.exists():
            return DEFAULT_CONFIG

        try:
            with open(self.config_path, "r") as f:
                config_data = json.load(f)

                # Merge with defaults to ensure all keys exist
                merged = DEFAULT_CONFIG.copy()
                for k, v in config_data.items():
                    if isinstance(v, dict) and k in merged:
                        merged[k].update(v)
                    else:
                        merged[k] = v
                return merged
        except Exception as e:
            print(f"Error loading config.json, using defaults. Error: {e}")
            return DEFAULT_CONFIG

    def get(self, section, key=None, default=None):
        if key is None:
            return self.settings.get(section, default)

        sec_data = self.settings.get(section, {})
        return sec_data.get(key, default)

# Global config instance
config = Config()
