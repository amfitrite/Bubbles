from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PySide6.QtCore import Qt
from src.algo.tick_store import TickStore
from src.ui.header_bar import HeaderBar
from src.ui.gl_canvas import GLCanvas
from src.ui.control_dock import ControlDock
from src.ui.settings_panel import SettingsPanel
from src.visual.theme import Theme
from src.config import settings

class MainWindow(QMainWindow):
    """
    Master Application Window: Monochrome Matte Studio.
    Seamlessly assembles Header, GLCanvas, Floating Bottom Dock, and Slide-Out Studio Panel.
    Fully persistent across restarts (remembers FPS target, Mode, Interval, Gap, Scale, and Window Geometry).
    """
    def __init__(self, tick_store: TickStore):
        super().__init__()
        self.tick_store = tick_store

        self.setWindowTitle("BUBBLES — Order Flow Terminal")
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

        # Wire Signals & Slots
        self._wire_signals()

        # Load and apply persistent user preferences
        self._load_saved_settings()

    def _load_saved_settings(self):
        # 1. Window geometry
        win_data = settings.get("window", {})
        w = win_data.get("width", 1366)
        h = win_data.get("height", 768)
        self.resize(max(900, w), max(600, h))

        x = win_data.get("x", -1)
        y = win_data.get("y", -1)
        if x >= 0 and y >= 0:
            self.move(x, y)

        if win_data.get("is_maximized", False):
            self.showMaximized()

        # 2. Canvas presentation settings
        saved_mode = settings.get("active_mode", "TOTAL_VOLUME")
        self.canvas.set_mode(saved_mode)
        self.header.active_mode = saved_mode

        saved_interval = settings.get("active_interval", "AUTO")
        self.canvas.set_interval(saved_interval)
        self.dock.active_interval = saved_interval

        saved_fps = settings.get("fps_limit", "60")
        self.canvas.set_fps_target(saved_fps)
        self.header.fps_target = saved_fps
        self.settings_panel.update_fps(saved_fps)

        saved_gap = float(settings.get("min_gap_px", 6.0))
        self.canvas.set_pixel_gap(saved_gap)
        self.dock.min_gap_px = saved_gap

        saved_scale = float(settings.get("size_scale", 1.0))
        self.canvas.set_bubble_scale(saved_scale)
        self.dock.size_scale = saved_scale

        saved_imb = float(settings.get("imbalance_ratio", 3.0))
        self.canvas.set_imbalance_ratio(saved_imb)

        saved_min_vol = float(settings.get("min_volume_filter", 0.0))
        self.canvas.set_min_volume_filter(saved_min_vol)

        saved_autofit = bool(settings.get("auto_fit_price", True))
        self.canvas.toggle_autofit(saved_autofit)
        self.dock.auto_fit = saved_autofit

        saved_live = bool(settings.get("follow_live", True))
        self.canvas.toggle_follow_live(saved_live)
        self.dock.follow_live = saved_live

    def _wire_signals(self):
        # Header -> Canvas & Settings
        self.header.mode_selected.connect(self._on_mode_selected)
        self.header.fps_target_selected.connect(self._on_fps_target_changed)
        self.header.reset_camera_clicked.connect(self.canvas.reset_camera)
        self.header.settings_toggled.connect(self._toggle_settings)

        # Dock -> Canvas & Settings
        self.dock.interval_selected.connect(self._on_interval_selected)
        self.dock.gap_changed.connect(self._on_gap_changed)
        self.dock.scale_changed.connect(self._on_scale_changed)
        self.dock.autofit_toggled.connect(self._on_autofit_toggled)
        self.dock.follow_live_toggled.connect(self._on_follow_live_toggled)

        # Settings Panel -> Canvas & Settings
        self.settings_panel.gap_changed.connect(self._on_gap_changed)
        self.settings_panel.scale_changed.connect(self._on_scale_changed)
        self.settings_panel.imbalance_ratio_changed.connect(self._on_imbalance_ratio_changed)
        self.settings_panel.min_volume_changed.connect(self._on_min_volume_changed)
        self.settings_panel.fps_changed.connect(self._on_fps_target_changed)
        self.settings_panel.autofit_toggled.connect(self._on_autofit_toggled)
        self.settings_panel.follow_live_toggled.connect(self._on_follow_live_toggled)

        # Canvas -> Header & Dock
        self.canvas.telemetry_updated.connect(self.header.update_telemetry)
        self.canvas.dock_updated.connect(self.dock.set_state)

    def _on_mode_selected(self, mode: str):
        self.canvas.set_mode(mode)
        settings.set("active_mode", mode)

    def _on_fps_target_changed(self, fps: str):
        self.canvas.set_fps_target(fps)
        self.header.fps_target = fps
        self.settings_panel.update_fps(fps)
        settings.set("fps_limit", fps)

    def _on_interval_selected(self, interval: str):
        self.canvas.set_interval(interval)
        settings.set("active_interval", interval)

    def _on_gap_changed(self, gap: float):
        self.canvas.set_pixel_gap(gap)
        self.dock.min_gap_px = gap
        settings.set("min_gap_px", gap)

    def _on_scale_changed(self, scale: float):
        self.canvas.set_bubble_scale(scale)
        self.dock.size_scale = scale
        settings.set("size_scale", scale)

    def _on_imbalance_ratio_changed(self, ratio: float):
        self.canvas.set_imbalance_ratio(ratio)
        settings.set("imbalance_ratio", ratio)

    def _on_min_volume_changed(self, min_vol: float):
        self.canvas.set_min_volume_filter(min_vol)
        settings.set("min_volume_filter", min_vol)

    def _on_autofit_toggled(self, val: bool = None):
        self.canvas.toggle_autofit(val)
        settings.set("auto_fit_price", self.canvas.camera.auto_fit_price)

    def _on_follow_live_toggled(self, val: bool = None):
        self.canvas.toggle_follow_live(val)
        settings.set("follow_live", self.canvas.camera.follow_live)

    def _toggle_settings(self):
        if self.settings_panel.isVisible():
            self.settings_panel.hide()
        else:
            self.settings_panel.update_values(
                self.canvas.layout_engine.min_gap_px,
                self.canvas.layout_engine.size_scale,
                self.canvas.camera.auto_fit_price,
                self.canvas.camera.follow_live,
                self.canvas.algo.imbalance_ratio_threshold,
                self.canvas.min_volume_filter,
                self.canvas.fps_target
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

    def on_symbol_meta(self, symbol: str, tick_size: float = 0.01, digits: int = 2):
        if hasattr(self, 'canvas'):
            self.canvas.set_symbol_info(symbol, tick_size, digits)

    def closeEvent(self, event):
        # 1. Save window state
        is_max = self.isMaximized()
        geom = self.normalGeometry() if is_max else self.geometry()
        settings.set("window", {
            "width": geom.width(),
            "height": geom.height(),
            "x": geom.x(),
            "y": geom.y(),
            "is_maximized": is_max
        }, auto_save=False)

        # 2. Save all latest terminal parameters
        settings.set("active_mode", self.canvas.active_mode, auto_save=False)
        settings.set("active_interval", self.canvas.active_interval, auto_save=False)
        settings.set("fps_limit", self.canvas.fps_target, auto_save=False)
        settings.set("min_gap_px", self.canvas.layout_engine.min_gap_px, auto_save=False)
        settings.set("size_scale", self.canvas.layout_engine.size_scale, auto_save=False)
        settings.set("imbalance_ratio", self.canvas.algo.imbalance_ratio_threshold, auto_save=False)
        settings.set("min_volume_filter", self.canvas.min_volume_filter, auto_save=False)
        settings.set("auto_fit_price", self.canvas.camera.auto_fit_price, auto_save=False)
        settings.set("follow_live", self.canvas.camera.follow_live, auto_save=False)

        # 3. Commit to disk
        settings.save()

        if hasattr(self, 'canvas') and self.canvas.render_timer.isActive():
            self.canvas.render_timer.stop()
        super().closeEvent(event)
