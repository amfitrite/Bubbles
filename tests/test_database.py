import unittest
import tempfile
import os
import time
from pathlib import Path

# Override config for testing
import src.config
src.config.BASE_DIR = Path(tempfile.gettempdir())
src.config.config.settings['database'] = {'path': 'test_bubbles.db'}

from src.data.database import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager()
        self.db.start_writer()

    def tearDown(self):
        self.db.stop_writer()
        try:
            os.remove(self.db.db_path)
            os.remove(str(self.db.db_path) + '-wal')
            os.remove(str(self.db.db_path) + '-shm')
        except:
            pass

    def test_insert_ticks(self):
        ticks = [
            (1000, 1.1, 1.2, 1.15, 10.0, 32, 1),
            (2000, 1.2, 1.3, 1.25, 20.0, 64, -1)
        ]
        self.db.enqueue_ticks("EURUSD", ticks)

        # Wait for writer thread
        time.sleep(0.5)

        last_ts = self.db.get_last_ts("EURUSD")
        self.assertEqual(last_ts, 2000)

if __name__ == '__main__':
    unittest.main()
