import sys
import logging
from PySide6.QtWidgets import QApplication

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

        # Initialize Core Data Structures (M0)
        self.tick_store = TickStore(max_ticks=1_000_000)
        self.db_manager = DatabaseManager()

        # Initialize TCP Server (M0)
        self.server = BridgeServer(callback=self.on_network_event)

        # Initialize UI
        self.window = MainWindow(self.tick_store, self.db_manager)

    def on_network_event(self, sock, symbol, msg_type, data):
        """
        Callback fired by BridgeServer when parsing data.
        Runs on the BridgeServer thread. Do not call UI functions directly here.
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
                side=0 # We will calculate side later based on tick rules
            )

            # Send to SQLite WAL background writer
            # We batch this in reality, but for M0 structural proof:
            self.db_manager.enqueue_ticks(symbol, [(
                data['ts'], data['bid'], data['ask'], data['last'], data['volume'], data['flags'], 0
            )])

        elif msg_type == 'META':
            # Save meta definition
            import time
            self.db_manager.enqueue_meta(symbol, data, int(time.time() * 1000))
            logger.info(f"Received META for {symbol}: {data}")

        elif msg_type == 'SYMBOL':
            logger.info(f"Connected to symbol stream: {symbol}")

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
