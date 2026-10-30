from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedLayout
from PySide6.QtCore import Qt
from src.algo.tick_store import TickStore
from src.ui.header_bar import HeaderBar
from src.ui.gl_canvas import GLCanvas
from src.ui.control_dock import ControlDock
from src.ui.settings_panel import SettingsPanel
from src.visual.theme import Theme

class MainWindow(QMainWindow):
    """
    Master Application Window: Monochrome Matte Studio.
    Seamlessly assembles Header, GLCanvas, Floating Bottom Dock, and Slide-Out Studio Panel.
    """
    def __init__(self, tick_store: TickStore):
        super().__init__()
        self.tick_store = tick_store

        self.setWindowTitle("BUBBLES — Order Flow Terminal")
        self.resize(1366, 768)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(f"QMainWindow {{ background-color: #0B0D11; }}")

        # Central Container
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Header Bar
        self.header = HeaderBar(self)
        self.main_layout.addWidget(self.header)

        # 2. GL Canvas Workspace
        self.canvas = GLCanvas(self.tick_store, self)
        self.main_layout.addWidget(self.canvas, stretch=1)

        # 3. Floating Bottom Dock
        self.dock = ControlDock(self)
        self.main_layout.addWidget(self.dock)

        # 4. Slide-Out Settings Panel
        self.settings_panel = SettingsPanel(self)
        self.settings_panel.hide()

        # Connect Signals & Slots
        self._wire_signals()

    def _wire_signals(self):
        # Header -> Canvas
        self.header.mode_selected.connect(self.canvas.set_mode)
        self.header.reset_camera_clicked.connect(self.canvas.reset_camera)
        self.header.settings_toggled.connect(self._toggle_settings)

        # Dock -> Canvas
        self.dock.interval_selected.connect(self.canvas.set_interval)
        self.dock.gap_changed.connect(self.canvas.set_pixel_gap)
        self.dock.scale_changed.connect(self.canvas.set_bubble_scale)
        self.dock.autofit_toggled.connect(self.canvas.toggle_autofit)
        self.dock.follow_live_toggled.connect(self.canvas.toggle_follow_live)

        # Settings Panel -> Canvas
        self.settings_panel.gap_changed.connect(self.canvas.set_pixel_gap)
        self.settings_panel.scale_changed.connect(self.canvas.set_bubble_scale)
        self.settings_panel.imbalance_ratio_changed.connect(self.canvas.set_imbalance_ratio)
        self.settings_panel.min_volume_changed.connect(self.canvas.set_min_volume_filter)
        self.settings_panel.autofit_toggled.connect(self.canvas.toggle_autofit)
        self.settings_panel.follow_live_toggled.connect(self.canvas.toggle_follow_live)

        # Canvas -> Header & Dock
        self.canvas.telemetry_updated.connect(self.header.update_telemetry)
        self.canvas.dock_updated.connect(self.dock.set_state)

    def _toggle_settings(self):
        if self.settings_panel.isVisible():
            self.settings_panel.hide()
        else:
            self.settings_panel.update_values(
                self.canvas.layout_engine.min_gap_px,
                self.canvas.layout_engine.size_scale,
                self.canvas.camera.auto_fit_price,
                self.canvas.camera.follow_live
            )
            # Position flush to the right edge below header
            h = self.height() - self.header.height()
            self.settings_panel.setGeometry(
                self.width() - self.settings_panel.width(),
                self.header.height(),
                self.settings_panel.width(),
                h
            )
            self.settings_panel.show()
            self.settings_panel.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.settings_panel.isVisible():
            h = self.height() - self.header.height()
            self.settings_panel.setGeometry(
                self.width() - self.settings_panel.width(),
                self.header.height(),
                self.settings_panel.width(),
                h
            )

    def on_symbol_meta(self, symbol: str, tick_size: float = 0.01):
        if hasattr(self, 'canvas'):
            self.canvas.set_symbol_info(symbol, tick_size)

    def closeEvent(self, event):
        if hasattr(self, 'canvas') and self.canvas.render_timer.isActive():
            self.canvas.render_timer.stop()
        super().closeEvent(event)
