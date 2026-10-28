import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QMainWindow
from PySide6.QtGui import QIcon

from src.ui.bubble_canvas import BubbleCanvas
from src.ui.theme import Theme

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, tick_store, db_manager):
        super().__init__()
        self.tick_store = tick_store
        self.db_manager = db_manager

        self.setWindowTitle("Bubbles — Hybrid Micro/Macro Order Flow")
        self.resize(1366, 768)
        self.setMinimumSize(800, 600)

        # Application Icon
        icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Background style
        self.setStyleSheet(f"QMainWindow {{ background-color: {Theme.BACKGROUND_HEX}; }}")

        # Set Bubble Canvas as the central workspace
        self.canvas = BubbleCanvas(self.tick_store, parent=self)
        self.setCentralWidget(self.canvas)

    def on_symbol_meta(self, symbol: str, tick_size: float = 0.01):
        """Notifies canvas when symbol meta arrives."""
        if hasattr(self, 'canvas'):
            self.canvas.set_symbol_info(symbol, tick_size)

    def closeEvent(self, event):
        logger.info("MainWindow closing, stopping render loops...")
        if hasattr(self, 'canvas') and self.canvas.render_timer.isActive():
            self.canvas.render_timer.stop()
        super().closeEvent(event)
