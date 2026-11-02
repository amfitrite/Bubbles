import sys
import os
import logging
import time
import math
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat, QIcon

from src.algo.tick_store import TickStore
from src.algo.symbol_manager import SymbolManager
from src.network.bridge_server import BridgeServer
from src.ui.main_window import MainWindow

# Windows Pro Application ID & Console Window Suppression
if sys.platform == "win32":
    try:
        import ctypes
        # Set distinct AppUserModelID so Windows taskbar groups under this app icon instead of Python.exe
        app_id = "antigravity.bubbles.terminal.v2"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

        # Hide any console window that was created by python.exe or launcher
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
    except Exception:
        pass

# Configure clean file logging in logs/bubbles.log (no console spam)
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "bubbles.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(str(log_file), encoding='utf-8', mode='a')
    ]
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

        # Load Pro High-Resolution Icon for Window, Taskbar, and Alt-Tab
        assets_dir = Path(__file__).parent / "assets"
        ico_file = assets_dir / "icon.ico"
        png_file = assets_dir / "icon.png"

        self.icon = QIcon()
        if ico_file.exists():
            self.icon = QIcon(str(ico_file))
        elif png_file.exists():
            self.icon = QIcon(str(png_file))

        if not self.icon.isNull():
            self.app.setWindowIcon(self.icon)

        # Multi-Symbol Isolation Engine
        self.symbol_manager = SymbolManager()

        # Multi-Port TCP Bridge Server (MT5 connection)
        self.server = BridgeServer(callback=self.on_network_event, ports=[5555, 5556, 5557, 5558, 5559])

        # Main Window
        self.window = MainWindow(symbol_manager=self.symbol_manager)
        if not self.icon.isNull():
            self.window.setWindowIcon(self.icon)

    @property
    def tick_store(self) -> TickStore:
        """Compatibility accessor for the active symbol's isolated tick store."""
        return self.symbol_manager.get_active().tick_store

    def on_network_event(self, sock, symbol: str, msg_type: str, data: dict):
        """
        Callback fired by BridgeServer thread upon parsing incoming stream from MT5.
        Routes ticks strictly into dedicated, isolated symbol buffers.
        """
        sym = symbol.strip().upper() if symbol else self.symbol_manager.active_symbol
        state = self.symbol_manager.get_or_create(sym)

        # Auto-switch to active incoming stream if current canvas has 0 ticks or is default placeholder
        if hasattr(self, 'window') and self.window.canvas.symbol != sym:
            canvas_ticks = self.window.canvas.tick_store.count if self.window.canvas.tick_store else 0
            if canvas_ticks == 0 or self.window.canvas.symbol in ("XAUUSD", "UNKNOWN") or ("XAU" in sym and "XAU" in self.window.canvas.symbol):
                self.window.switch_symbol(sym)

        if msg_type == 'TICK':
            bid = float(data.get('bid', 0.0))
            ask = float(data.get('ask', 0.0))
            last = float(data.get('last', 0.0))
            vol = float(data.get('volume', 0.0))
            ts = int(data.get('ts', 0))
            flags = int(data.get('flags', 0))
            side = int(data.get('side', 0))

            # Ingest strictly into this symbol's isolated state
            added = state.add_tick(
                ts=ts,
                bid=bid,
                ask=ask,
                last=last,
                volume=vol,
                flags=flags,
                side=side
            )

            cnt = getattr(self, '_tick_log_count', 0)
            if cnt % 250 == 0:
                logger.info(f"Ingested tick #{state.tick_count} [{sym}] price={state.last_known_price:.2f} vol={vol} side={side} added={added}")
            self._tick_log_count = cnt + 1

        elif msg_type == 'META':
            logger.info(f"Received META for {sym}: {data}")
            tick_size = float(data.get('tick_size', 0.01))
            digits = int(data.get('digits', 2))
            point = float(data.get('point', 0.001))
            contract_size = float(data.get('contract_size', 100.0))
            state.configure_meta(tick_size=tick_size, digits=digits, point=point, contract_size=contract_size)
            self.window.on_symbol_meta(sym, tick_size, digits)

        elif msg_type == 'SYMBOL':
            logger.info(f"Connected to symbol stream: {sym}")
            self.window.on_symbol_meta(sym)

        elif msg_type == 'HIST_START':
            logger.info(f"Receiving historical ticks for {sym}: count={data.get('count', 0)}")

        elif msg_type == 'HIST_END':
            logger.info(f"Finished receiving historical ticks for {sym}. Total in store: {state.tick_store.count}")

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
