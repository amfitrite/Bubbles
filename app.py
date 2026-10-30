import sys
import os
import logging
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QSurfaceFormat

# Import components
from src.logging_setup import setup_logging
from src.config import config
from src.data.tick_store import TickStore
from src.data.bar_store import BarStore
from src.data.database import DatabaseManager
from src.network.bridge_server import BridgeServer
from src.ui.main_window import MainWindow

logger = logging.getLogger(__name__)

class BubblesApp:
    def __init__(self):
        # Configure High-Performance OpenGL Surface with V-Sync disabled
        # Unlocks ultra-high frame rates (120 FPS +++ up to display ceiling)
        fmt = QSurfaceFormat()
        fmt.setSwapInterval(0)
        fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
        QSurfaceFormat.setDefaultFormat(fmt)

        self.app = QApplication(sys.argv)

        # Initialize Core Data Stores
        self.db_manager = DatabaseManager()
        self.tick_store = TickStore(max_ticks=1_000_000)
        self.bar_store = BarStore(db_manager=self.db_manager)

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
        self.window = MainWindow(self.tick_store, self.bar_store, self.db_manager)

    def on_network_event(self, sock, symbol, msg_type, data):
        """
        Callback fired by BridgeServer when parsing data.
        Runs on the BridgeServer thread.
        """
        if msg_type == 'TICK':
            price = data['last'] if data['last'] > 0 else data['bid']
            vol = data['volume']
            ts = data['ts']
            flags = data['flags']

            # Determine side from MT5 flags: 32 = buy, 64 = sell
            side = 1 if (flags & 32) else (-1 if (flags & 64) else 0)

            # 1. Add to fast tick ring buffer
            self.tick_store.add_tick(
                ts=ts,
                bid=data['bid'],
                ask=data['ask'],
                last=data['last'],
                volume=vol,
                flags=flags,
                side=side
            )

            # 2. Add to bar store for macro series
            self.bar_store.add_tick(
                symbol=symbol or "XAUUSD",
                ts=ts,
                price=price,
                volume=vol,
                side=side
            )

            # 3. Enqueue to persistent SQLite WAL writer
            self.db_manager.enqueue_ticks(symbol or "XAUUSD", [(
                ts, data['bid'], data['ask'], data['last'], vol, flags, side
            )])

        elif msg_type == 'META':
            self.db_manager.enqueue_meta(symbol, data, int(time.time() * 1000))
            logger.info(f"Received META for {symbol}: {data}")
            self.window.on_symbol_meta(symbol, data.get('tick_size', 0.01))

        elif msg_type == 'SYMBOL':
            logger.info(f"Connected to symbol stream: {symbol}")
            self.window.on_symbol_meta(symbol)

    def run(self):
        logger.info("Starting Bubbles Application...")

        # Start background threads
        self.server.start()
        self.db_manager.start()

        # Show main UI
        self.window.show()

        # Run event loop
        try:
            sys.exit(self.app.exec())
        finally:
            logger.info("Shutting down Bubbles Application...")
            self.server.stop()
            self.db_manager.stop()

if __name__ == '__main__':
    setup_logging()
    app = BubblesApp()
    app.run()
