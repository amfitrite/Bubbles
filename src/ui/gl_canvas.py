import time
import math
import numpy as np

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    BaseCanvas = QOpenGLWidget
    HAS_OPENGL = True
except ImportError:
    from PySide6.QtWidgets import QWidget
    BaseCanvas = QWidget
    HAS_OPENGL = False

from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtCore import Qt, QTimer, QPoint, Signal

from src.algo.tick_store import TickStore
from src.algo.accumulator import IntervalAccumulator, INTERVAL_MAP
from src.algo.models import AlgoBubble
from src.visual.theme import Theme
from src.visual.camera import Camera
from src.visual.sprite_engine import SpriteEngine
from src.visual.layout_engine import VisualLayoutEngine, VisualBubble
from src.ui.tooltip import MonospaceTooltip

class GLCanvas(BaseCanvas):
    """
    Hardware-accelerated OpenGL Order Flow Canvas.
    Renders 100% accurate mathematical bubbles at 120 - 300+ FPS with guaranteed visual spacing gaps.
    """
    telemetry_updated = Signal(str, float, bool, float, float, str) # sym, price, connected, last_ts, fps, mode
    dock_updated = Signal(str, float, float, bool, bool) # interval, gap, scale, autofit, live

    def __init__(self, tick_store: TickStore, parent=None):
        super().__init__(parent)
        self.tick_store = tick_store

        # Engines
        self.algo = IntervalAccumulator(imbalance_ratio_threshold=3.0)
        self.camera = Camera(self.width(), self.height())
        self.sprite_engine = SpriteEngine()
        self.layout_engine = VisualLayoutEngine(min_gap_px=5.0, size_scale=1.0)

        # Presentation State
        self.active_mode = "TOTAL_VOLUME" # 'SPLIT_PIE', 'DELTA', 'IMBALANCE', 'TOTAL_VOLUME'
        self.active_interval = "AUTO"
        self.symbol = "XAUUSD"
        self.tick_size = 0.01
        self.last_price = 0.0
        self.last_tick_time = 0.0
        self.is_connected = False
        self._price_initialized = False

        # Visual Nodes
        self.visible_bubbles = []
        self.last_rendered_version = -1
        self._last_cam_time = 0.0
        self.min_volume_filter = 0.0

        # High-Speed Telemetry (Target 120 - 300+ FPS)
        self.fps = 0.0
        self.frame_time_ms = 0.0
        self._fps_frames = 0
        self._fps_last_time = time.perf_counter()
        self._last_telemetry_emit = 0.0

        # Interaction State
        self.is_left_dragging = False
        self.is_right_dragging = False
        self.last_mouse_pos = QPoint()
        self.hover_mouse_pos = None

        # Tooltip
        self.tooltip = MonospaceTooltip(self)

        # High Precision Render Loop (2ms -> 500 FPS theoretical headroom)
        self.render_timer = QTimer(self)
        self.render_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.render_timer.timeout.connect(self.tick_frame)
        self.render_timer.start(2)

        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.camera.set_viewport_size(self.width(), self.height())

    def set_symbol_info(self, symbol: str, tick_size: float = 0.01):
        if symbol:
            self.symbol = symbol
        if tick_size > 0:
            self.tick_size = tick_size
        self._price_initialized = False

    def set_mode(self, mode: str):
        if mode in ("SPLIT_PIE", "DELTA", "IMBALANCE", "TOTAL_VOLUME"):
            self.active_mode = mode
            self.last_rendered_version = -1
            self.update()

    def set_interval(self, interval_name: str):
        self.active_interval = interval_name
        self.last_rendered_version = -1
        self.update()

    def set_pixel_gap(self, gap_px: float):
        self.layout_engine.min_gap_px = max(0.0, gap_px)
        self.last_rendered_version = -1
        self.update()

    def set_bubble_scale(self, scale: float):
        self.layout_engine.size_scale = max(0.4, min(3.0, scale))
        self.last_rendered_version = -1
        self.update()

    def set_imbalance_ratio(self, ratio: float):
        self.algo.set_imbalance_threshold(ratio)
        self.last_rendered_version = -1
        self.update()

    def set_min_volume_filter(self, min_vol: float):
        self.min_volume_filter = min_vol
        self.last_rendered_version = -1
        self.update()

    def toggle_autofit(self, val: bool = None):
        self.camera.auto_fit_price = not self.camera.auto_fit_price if val is None else val

    def toggle_follow_live(self, val: bool = None):
        self.camera.follow_live = not self.camera.follow_live if val is None else val

    def reset_camera(self):
        latest_ts = self.tick_store.last_ts if self.tick_store else 0
        self.camera.reset_to_recent(latest_ts, self.last_price)
        self.last_rendered_version = -1
        self.update()

    def tick_frame(self):
        now_sec = time.time()
        latest_tick_ms = self.tick_store.last_ts if self.tick_store else 0

        has_recent = (now_sec - self.last_tick_time) < 10.0 if self.last_tick_time > 0 else False
        self.is_connected = (self.tick_store and self.tick_store.count > 0 and has_recent)

        if self.camera.follow_live and latest_tick_ms > 0:
            self.camera.update_follow_live(latest_tick_ms)

        current_ver = self.tick_store.version if self.tick_store else 0
        cam_time = self.camera.max_time
        ms_per_pixel = self.camera.time_span_ms / max(1, self.width())
        time_dirty = abs(cam_time - self._last_cam_time) >= (ms_per_pixel * 0.5)

        if current_ver != self.last_rendered_version or time_dirty or self.is_left_dragging or self.is_right_dragging:
            self._rebuild_scene(latest_tick_ms)
            self.last_rendered_version = current_ver
            self._last_cam_time = cam_time

        # Throttled Telemetry Signals (~30 Hz)
        if (now_sec - self._last_telemetry_emit) >= 0.033:
            self._last_telemetry_emit = now_sec
            self.telemetry_updated.emit(
                self.symbol, self.last_price, self.is_connected,
                self.last_tick_time, self.fps, self.active_mode
            )
            self.dock_updated.emit(
                self.active_interval, self.layout_engine.min_gap_px,
                self.layout_engine.size_scale, self.camera.auto_fit_price,
                self.camera.follow_live
            )

        self._check_hover_tooltip()
        self.update()

    def _rebuild_scene(self, latest_tick_ms: int):
        if not self.tick_store or self.tick_store.count == 0:
            self.visible_bubbles = []
            return

        snapshot, _ = self.tick_store.get_snapshot()
        if len(snapshot) == 0:
            self.visible_bubbles = []
            return

        last_t = snapshot[-1]
        self.last_price = float(last_t['last'] if last_t['last'] > 0 else last_t['bid'])
        self.last_tick_time = time.time()

        # Instant Snap to market price if uninitialized or price shifted far away
        if (not self._price_initialized or self.camera.center_price <= 0.0 or abs(self.camera.center_price - self.last_price) > 500.0) and self.last_price > 0:
            self.camera.center_price = self.last_price
            self._price_initialized = True

        min_t = self.camera.min_time
        max_t = self.camera.max_time

        ts_arr = snapshot['ts']
        start_idx = np.searchsorted(ts_arr, min_t, side='left')
        end_idx = np.searchsorted(ts_arr, max_t, side='right')
        visible_ticks = snapshot[start_idx:end_idx]

        if len(visible_ticks) == 0:
            self.visible_bubbles = []
            return

        # Determine accumulation interval
        if self.active_interval == "AUTO":
            # Target approx 80-120 columns across current screen span
            target_ms = max(1.0, self.camera.time_span_ms / 100.0)
            if target_ms < 5:
                int_ms = 1
            elif target_ms < 50:
                int_ms = 10
            elif target_ms < 250:
                int_ms = 100
            elif target_ms < 1000:
                int_ms = 500
            elif target_ms < 5000:
                int_ms = 1000
            elif target_ms < 60000:
                int_ms = 5000
            elif target_ms < 300000:
                int_ms = 60000
            else:
                int_ms = 300000
        else:
            int_ms = INTERVAL_MAP.get(self.active_interval, 1000)

        # -------------------------------------------------------------
        # 1. ALGO ENGINE: Pure Mathematical Accumulation
        # -------------------------------------------------------------
        algo_bubbles = self.algo.build_interval_series(visible_ticks, int_ms)

        # -------------------------------------------------------------
        # 2. VISUAL ENGINE: Non-overlapping Spacing & Layout
        # -------------------------------------------------------------
        self.visible_bubbles = self.layout_engine.process_layout(
            algo_bubbles, self.camera, min_volume_filter=self.min_volume_filter
        )

        # Auto-fit price if active
        if self.camera.auto_fit_price and self.visible_bubbles:
            prices = [b.algo.price for b in self.visible_bubbles]
            self.camera.update_auto_fit(min(prices), max(prices), self.tick_size)

    def _check_hover_tooltip(self):
        if not self.hover_mouse_pos:
            self.tooltip.hide_tooltip()
            return

        mx = self.hover_mouse_pos.x()
        my = self.hover_mouse_pos.y()

        closest_node = None
        min_dist = float('inf')

        # Check in reverse so top-drawn bubbles are hit first
        for b in reversed(self.visible_bubbles):
            dx = mx - b.visual_x
            dy = my - b.visual_y
            dist = math.sqrt(dx * dx + dy * dy)
            hit_r = max(b.radius, 8.0)

            if dist <= hit_r and dist < min_dist:
                min_dist = dist
                closest_node = b

        if closest_node:
            self.tooltip.show_bubble(
                closest_node.algo,
                closest_node.visual_x,
                closest_node.visual_y,
                self.width(),
                self.height()
            )
        else:
            self.tooltip.hide_tooltip()

    if HAS_OPENGL:
        def paintGL(self):
            self._render_canvas()
    else:
        def paintEvent(self, event):
            self._render_canvas()

    def _render_canvas(self):
        # High-Precision Rolling FPS Measurement
        t_now = time.perf_counter()
        self._fps_frames += 1
        elapsed = t_now - self._fps_last_time
        if elapsed >= 0.25:
            self.fps = self._fps_frames / elapsed
            self.frame_time_ms = (elapsed / self._fps_frames) * 1000.0
            self._fps_frames = 0
            self._fps_last_time = t_now

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Matte Canvas Background
        painter.fillRect(0, 0, w, h, Theme.BG_CANVAS)

        # Blit Visual Bubbles using Sprite Pool
        mode = self.active_mode
        for b in self.visible_bubbles:
            self.sprite_engine.blit(
                painter,
                b.visual_x,
                b.visual_y,
                b.radius,
                mode,
                b.algo
            )

        painter.end()

    # --- Mouse & Navigation Controls ---

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle == 0:
            return

        factor = 1.15 if angle > 0 else (1.0 / 1.15)
        pos = event.position()
        modifiers = event.modifiers()

        zoom_time = True
        zoom_price = True

        if modifiers & Qt.ShiftModifier:
            zoom_price = False
        elif modifiers & Qt.ControlModifier:
            zoom_time = False

        self.camera.zoom(factor, anchor_x=pos.x(), anchor_y=pos.y(),
                         zoom_time=zoom_time, zoom_price=zoom_price)
        self.last_rendered_version = -1
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_left_dragging = True
            self.last_mouse_pos = event.pos()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.is_right_dragging = True
            self.last_mouse_pos = event.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        delta = event.pos() - self.last_mouse_pos
        self.last_mouse_pos = event.pos()

        if self.is_left_dragging:
            self.camera.pan(delta.x(), delta.y())
        elif self.is_right_dragging:
            self.camera.stretch(delta.x(), delta.y())

        self.hover_mouse_pos = event.pos()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_left_dragging = False
        elif event.button() == Qt.RightButton:
            self.is_right_dragging = False
        event.accept()

    def leaveEvent(self, event):
        self.hover_mouse_pos = None
        self.tooltip.hide_tooltip()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_1:
            self.set_mode("SPLIT_PIE")
        elif key == Qt.Key_2:
            self.set_mode("DELTA")
        elif key == Qt.Key_3:
            self.set_mode("IMBALANCE")
        elif key == Qt.Key_4:
            self.set_mode("TOTAL_VOLUME")
        elif key == Qt.Key_Space:
            self.reset_camera()
        elif key == Qt.Key_F:
            self.toggle_autofit()
        elif key == Qt.Key_L:
            self.toggle_follow_live()
        else:
            super().keyPressEvent(event)
