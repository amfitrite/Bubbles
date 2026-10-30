import sys
import os
import logging
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat, QIcon

from src.algo.tick_store import TickStore
from src.network.bridge_server import BridgeServer
from src.ui.main_window import MainWindow

# Configure clean logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("BubblesApp")

class BubblesApp:
    def __init__(self):
        # Configure High-Performance OpenGL Surface with VSync disabled
        # Unlocks ultra-high frame rates (120 - 300+ FPS)
        fmt = QSurfaceFormat()
        fmt.setSwapInterval(0)
        fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
        QSurfaceFormat.setDefaultFormat(fmt)

        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Bubbles Terminal")

        # Core Algo Tick Storage
        self.tick_store = TickStore(max_ticks=1_000_000)

        # Multi-Port TCP Bridge Server (MT5 connection)
        self.server = BridgeServer(callback=self.on_network_event, ports=[5555, 5556, 5557, 5558, 5559])

        # Main Window
        self.window = MainWindow(self.tick_store)

    def on_network_event(self, sock, symbol: str, msg_type: str, data: dict):
        """
        Callback fired by BridgeServer thread upon parsing incoming stream from MT5.
        Directly appends to TickStore without blocking the network thread.
        """
        if msg_type == 'TICK':
            price = data['last'] if data['last'] > 0 else data['bid']
            vol = data['volume']
            ts = data['ts']
            flags = data['flags']
            side = data.get('side', 0)

            # Ingest into Algo TickStore
            added = self.tick_store.add_tick(
                ts=ts,
                bid=data['bid'],
                ask=data['ask'],
                last=price,
                volume=vol,
                flags=flags,
                side=side
            )

            cnt = getattr(self, '_tick_log_count', 0)
            if cnt % 250 == 0:
                logger.info(f"Ingested tick #{self.tick_store.count} [{symbol}] price={price:.2f} vol={vol} side={side} added={added}")
            self._tick_log_count = cnt + 1

            if symbol and hasattr(self, 'window') and self.window.canvas.symbol != symbol:
                self.window.on_symbol_meta(symbol)

        elif msg_type == 'META':
            logger.info(f"Received META for {symbol}: {data}")
            self.window.on_symbol_meta(symbol, data.get('tick_size', 0.01), data.get('digits', 2))

        elif msg_type == 'SYMBOL':
            logger.info(f"Connected to symbol stream: {symbol}")
            self.window.on_symbol_meta(symbol)

        elif msg_type == 'HIST_START':
            logger.info(f"Receiving historical ticks for {symbol}: count={data.get('count', 0)}")

        elif msg_type == 'HIST_END':
            logger.info(f"Finished receiving historical ticks for {symbol}. Total in store: {self.tick_store.count}")

    def run(self):
        logger.info("Starting Bubbles Terminal...")
        self.server.start()
        self.window.show()

        try:
            sys.exit(self.app.exec())
        finally:
            logger.info("Stopping Bubbles Terminal...")
            self.server.stop()

if __name__ == "__main__":
    bubbles = BubblesApp()
    bubbles.run()
