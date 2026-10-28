import sys
import os
import logging
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

# Import components
from src.logging_setup import setup_logging
from src.config import config
from src.data.tick_store import TickStore
from src.data.database import DatabaseManager
from src.network.bridge_server import BridgeServer
from src.ui.main_window import MainWindow

logger = logging.getLogger(__name__)

class BubblesApp:
    def __init__(self):
        self.app = QApplication(sys.argv)

        # Initialize Core Data Structures
        self.tick_store = TickStore(max_ticks=1_000_000)
        self.db_manager = DatabaseManager()

        # Initialize TCP Server
        self.server = BridgeServer(callback=self.on_network_event)

        # Set Application Icon
        icon_path = Path(__file__).resolve().parent / "assets" / "icon.png"
        if icon_path.exists():
            self.app.setWindowIcon(QIcon(str(icon_path)))

            # Ensure the icon shows on the Windows taskbar
            if os.name == 'nt':
                try:
                    import ctypes
                    myappid = 'bubbles.hybrid.orderflow.1'
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                except Exception as e:
                    logger.warning(f"Could not set Windows taskbar icon ID: {e}")

        # Initialize UI
        self.window = MainWindow(self.tick_store, self.db_manager)

    def on_network_event(self, sock, symbol, msg_type, data):
        """
        Callback fired by BridgeServer when parsing data.
        Runs on the BridgeServer thread.
        """
        if msg_type == 'TICK':
            # Add to fast memory cache
            self.tick_store.add_tick(
                ts=data['ts'],
                bid=data['bid'],
                ask=data['ask'],
                last=data['last'],
                volume=data['volume'],
                flags=data['flags'],
                side=0
            )

            # Send to SQLite WAL background writer
            self.db_manager.enqueue_ticks(symbol, [(
                data['ts'], data['bid'], data['ask'], data['last'], data['volume'], data['flags'], 0
            )])

        elif msg_type == 'META':
            # Save meta definition
            self.db_manager.enqueue_meta(symbol, data, int(time.time() * 1000))
            logger.info(f"Received META for {symbol}: {data}")
            self.window.on_symbol_meta(symbol, data.get('tick_size', 0.01))

        elif msg_type == 'SYMBOL':
            logger.info(f"Connected to symbol stream: {symbol}")
            self.window.on_symbol_meta(symbol)

    def run(self):
        logger.info("Starting Bubbles Application...")

        # Start background threads
        self.db_manager.start_writer()

        # Start TCP server
        if not self.server.start():
            logger.error("Failed to start server. Exiting.")
            sys.exit(1)

        # Show window
        self.window.show()

        # Start Qt event loop
        exit_code = self.app.exec()

        # Shutdown cleanly
        logger.info("Initiating shutdown sequence...")
        self.server.stop()
        self.db_manager.stop_writer()
        logger.info("Shutdown complete.")

        sys.exit(exit_code)

if __name__ == "__main__":
    app = BubblesApp()
    app.run()
