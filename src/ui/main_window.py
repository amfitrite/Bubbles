import sys
import logging
from PySide6.QtWidgets import QMainWindow, QApplication, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, QTimer

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, tick_store, db_manager):
        super().__init__()
        self.tick_store = tick_store
        self.db_manager = db_manager

        self.setWindowTitle("Bubbles - Hybrid Order Flow")
        self.resize(1280, 720)

        # Dark theme base setup
        self.setStyleSheet("QMainWindow { background-color: #06080C; color: #E8EEF6; }")

        # Temporary Placeholder UI until Canvas is built (M1)
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.status_label = QLabel("Waiting for MT5 EA connection on Port 5558...")
        self.status_label.setStyleSheet("font-size: 18px; color: #94A3B8; font-family: 'Segoe UI', Inter;")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.stats_label = QLabel("Ticks loaded: 0")
        self.stats_label.setStyleSheet("font-size: 14px; color: #22D3EE; font-family: 'Segoe UI', Inter;")
        self.stats_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.status_label)
        layout.addWidget(self.stats_label)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # UI Timer to refresh data view occasionally
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(500) # Update stats twice a second

    def update_stats(self):
        # Update placeholder stats
        if self.tick_store:
            count = self.tick_store.count
            self.stats_label.setText(f"Live Ticks in Memory Cache: {count}")
            if count > 0:
                self.status_label.setText("Connected & Receiving Data")
                self.status_label.setStyleSheet("font-size: 18px; color: #34D399; font-family: 'Segoe UI', Inter;")

    def closeEvent(self, event):
        logger.info("MainWindow closing, shutting down application...")
        super().closeEvent(event)
