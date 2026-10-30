import time
import math
from datetime import datetime
import numpy as np

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    BaseCanvas = QOpenGLWidget
    HAS_OPENGL = True
except ImportError:
    from PySide6.QtWidgets import QWidget
    BaseCanvas = QWidget
    HAS_OPENGL = False

from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF, QBrush
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF, Signal

from src.algo.tick_store import TickStore
from src.algo.accumulator import OrderFlowAlgoEngine, INTERVAL_MAP
from src.algo.models import OrderFlowSnapshot
from src.visual.theme import Theme
from src.visual.camera import Camera
from src.visual.sprite_engine import SpriteEngine
from src.visual.layout_engine import VisualLayoutEngine, LayoutResult, VisualBubble
from src.ui.tooltip import MonospaceTooltip

class GLCanvas(BaseCanvas):
    """
    Next-Gen Order Flow Terminal Canvas.
    Combines Bookmap Microstructure (Trajectorized Bubbles, 4 Modes, Pixel Gap)
    with TradingView Macrostructure (Right DOM Volume Profile, Session High/Low/VWAP/POC, Time Axis).
    """
    telemetry_updated = Signal(str, float, bool, float, float, str, str)
    dock_updated = Signal(str, float, float, bool, bool)

    def __init__(self, tick_store: TickStore, parent=None):
        super().__init__(parent)
        self.tick_store = tick_store

        # Engines
        self.algo = OrderFlowAlgoEngine(imbalance_ratio_threshold=3.0)
        self.camera = Camera(self.width(), self.height(), dom_width=100, time_height=24)
        self.sprite_engine = SpriteEngine()
        self.layout_engine = VisualLayoutEngine(min_gap_px=6.0, size_scale=1.0)

        # Presentation State
        self.active_mode = "TOTAL_VOLUME" # 'SPLIT_PIE', 'DELTA', 'IMBALANCE', 'TOTAL_VOLUME'
        self.active_interval = "AUTO"
        self.symbol = "XAUUSD"
        self.tick_size = 0.01
        self.last_price = 0.0
        self.last_tick_time = 0.0
        self.is_connected = False
        self._price_initialized = False

        # Visual Snapshot & Layout
        self.current_layout: LayoutResult = None
        self.last_rendered_version = -1
        self._last_cam_time = 0.0
        self.min_volume_filter = 0.0

        # Telemetry
        self.fps = 0.0
        self.frame_time_ms = 0.0
        self._fps_frames = 0
        self._fps_last_time = time.perf_counter()
        self._last_telemetry_emit = 0.0

        # Mouse Interaction
        self.is_left_dragging = False
        self.is_right_dragging = False
        self.last_mouse_pos = QPoint()
        self.hover_mouse_pos = None

        # Tooltip
        self.tooltip = MonospaceTooltip(self)

        # Configurable Render Timer (Default: 60 FPS capped)
        self.fps_target = "60"
        self.render_timer = QTimer(self)
        self.render_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.render_timer.timeout.connect(self.tick_frame)
        self.set_fps_target("60")

        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def set_fps_target(self, target: str):
        """
        Sets target FPS cap:
          '60': ~60 FPS (16ms interval) [Default]
          '120': ~120 FPS (8ms interval)
          'UNLIMITED': Uncapped (0ms interval, maximum hardware speed)
        """
        if target not in ("60", "120", "UNLIMITED"):
            target = "60"
        self.fps_target = target
        if target == "60":
            self.render_timer.setInterval(16)
        elif target == "120":
            self.render_timer.setInterval(8)
        else:
            self.render_timer.setInterval(0)
        if not self.render_timer.isActive():
            self.render_timer.start()
        self.update()

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
            self.update()

    def set_interval(self, interval_name: str):
        self.active_interval = interval_name
        int_ms = INTERVAL_MAP.get(interval_name, 0)
        if int_ms > 0:
            min_needed_span = float(int_ms * 10)
            if self.camera.time_span_ms < min_needed_span:
                self.camera.time_span_ms = min_needed_span
                latest_ts = self.tick_store.last_ts if self.tick_store else 0
                if self.camera.follow_live and latest_ts > 0:
                    self.camera.update_follow_live(latest_ts)
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
        new_val = not self.camera.follow_live if val is None else val
        self.camera.follow_live = new_val
        if new_val:
            latest_ts = self.tick_store.last_ts if self.tick_store else 0
            if latest_ts > 0:
                self.camera.update_follow_live(latest_ts)
        self.last_rendered_version = -1
        self.update()

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
        ms_per_pixel = self.camera.time_span_ms / max(1, self.camera.chart_width)
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
                self.last_tick_time, self.fps, self.active_mode, self.fps_target
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
            self.current_layout = None
            return

        snapshot, ver = self.tick_store.get_snapshot()
        if len(snapshot) == 0:
            self.current_layout = None
            return

        last_t = snapshot[-1]
        self.last_price = float(last_t['last'] if last_t['last'] > 0 else last_t['bid'])
        self.last_tick_time = time.time()

        # Instant snap to live market price if uninitialized or price shifted far away
        if (not self._price_initialized or self.camera.center_price <= 0.0 or abs(self.camera.center_price - self.last_price) > 500.0) and self.last_price > 0:
            self.camera.center_price = self.last_price
            self._price_initialized = True

        min_t = self.camera.min_time
        max_t = self.camera.max_time

        ts_arr = snapshot['ts']
        start_idx = np.searchsorted(ts_arr, min_t, side='left')
        end_idx = np.searchsorted(ts_arr, max_t, side='right')
        visible_ticks = snapshot[start_idx:end_idx]

        # Feed new ticks into continuous algo volume profile tracker
        self.algo.ingest_new_ticks(snapshot)

        # Determine interval ms
        if self.active_interval == "AUTO":
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

        # 1. ALGO ENGINE: Compute pure mathematical snapshot
        algo_snapshot = self.algo.compute_snapshot(visible_ticks, int_ms, ver)

        # 2. VISUAL ENGINE: Process layout with pixel gap enforcer and trajectory projection
        self.current_layout = self.layout_engine.process_snapshot(
            algo_snapshot, self.camera, min_volume_filter=self.min_volume_filter
        )

        # Auto-fit price
        if self.camera.auto_fit_price and self.current_layout.bubbles:
            prices = [b.algo.price for b in self.current_layout.bubbles]
            self.camera.update_auto_fit(min(prices), max(prices), self.tick_size)

    def _check_hover_tooltip(self):
        if not self.hover_mouse_pos or not self.current_layout or not self.current_layout.bubbles:
            self.tooltip.hide_tooltip()
            return

        mx = self.hover_mouse_pos.x()
        my = self.hover_mouse_pos.y()

        closest_node = None
        min_dist = float('inf')

        for b in reversed(self.current_layout.bubbles):
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
        # 1. Real-Time FPS Measurement
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
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = self.width()
        h = self.height()
        chart_w = self.camera.chart_width
        chart_h = self.camera.chart_height
        dom_w = self.camera.dom_width
        time_h = self.camera.time_height

        # Base Canvas Background
        painter.fillRect(0, 0, w, h, Theme.BG_CANVAS)

        # -------------------------------------------------------------
        # 2. DRAW GRID & TIME / PRICE LEVELS
        # -------------------------------------------------------------
        self._draw_grid(painter, chart_w, chart_h)

        # -------------------------------------------------------------
        # 3. DRAW MACRO STRUCTURAL LINES (High, Low, VWAP, POC)
        # -------------------------------------------------------------
        if self.current_layout and self.current_layout.snapshot:
            self._draw_macro_levels(painter, self.current_layout.snapshot.macro, chart_w, chart_h)

        # -------------------------------------------------------------
        # 4. DRAW PRICE TRAJECTORY LINE (The Path of Price Action)
        # -------------------------------------------------------------
        if self.current_layout and len(self.current_layout.trajectory_screen_points) >= 2:
            self._draw_trajectory(painter, self.current_layout.trajectory_screen_points, chart_w, chart_h)

        # -------------------------------------------------------------
        # 5. DRAW VOLUME BUBBLES WITH PIXEL GAP (4 MODES)
        # -------------------------------------------------------------
        if self.current_layout and self.current_layout.bubbles:
            mode = self.active_mode
            for b in self.current_layout.bubbles:
                self.sprite_engine.blit(
                    painter,
                    b.visual_x,
                    b.visual_y,
                    b.radius,
                    mode,
                    b.algo
                )

        # -------------------------------------------------------------
        # 6. DRAW RIGHT-SIDE VOLUME PROFILE & PRICE DOM LADDER
        # -------------------------------------------------------------
        self._draw_right_dom(painter, w, h, chart_w, chart_h, dom_w)

        # -------------------------------------------------------------
        # 7. DRAW BOTTOM TIME AXIS RAIL
        # -------------------------------------------------------------
        self._draw_time_axis(painter, w, h, chart_w, chart_h, time_h)

        # -------------------------------------------------------------
        # 8. FLOATING AUTO SCROLL PILL (When paused by user navigation)
        # -------------------------------------------------------------
        if not self.camera.follow_live:
            pill_w = 116
            pill_h = 24
            pill_x = chart_w - pill_w - 12
            pill_y = chart_h - pill_h - 10
            self._pill_rect = QRectF(pill_x, pill_y, pill_w, pill_h)

            painter.setBrush(QBrush(QColor(15, 23, 42, 230)))
            painter.setPen(QPen(Theme.STATUS_LIVE, 1.2))
            painter.drawRoundedRect(self._pill_rect, 12, 12)

            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(Theme.STATUS_LIVE)
            painter.drawText(self._pill_rect, Qt.AlignCenter, "▶ AUTO SCROLL")
        else:
            self._pill_rect = None

        painter.end()

    def _draw_grid(self, painter: QPainter, chart_w: float, chart_h: float):
        # Clip to chart area so grid lines don't leak into DOM or time rails
        painter.setClipRect(0, 0, int(chart_w), int(chart_h))

        # Horizontal Price Grid Lines
        price_range = self.camera.price_range
        # Compute clean price step (e.g. 0.1, 0.5, 1.0, 5.0, 10.0)
        target_steps = max(2, int(chart_h / 60))
        raw_step = price_range / target_steps
        exp = math.floor(math.log10(max(0.001, raw_step)))
        frac = raw_step / (10 ** exp)
        if frac < 1.5:
            step = 1.0 * (10 ** exp)
        elif frac < 3.5:
            step = 2.0 * (10 ** exp)
        elif frac < 7.5:
            step = 5.0 * (10 ** exp)
        else:
            step = 10.0 * (10 ** exp)

        first_p = math.floor(self.camera.min_price / step) * step
        cur_p = first_p

        painter.setPen(QPen(Theme.GRID_LINE, 1.0))
        while cur_p <= self.camera.max_price + step:
            sy = self.camera.price_to_screen_y(cur_p)
            if 0 <= sy <= chart_h:
                painter.drawLine(0, int(sy), int(chart_w), int(sy))
            cur_p += step

        # Vertical Time Grid Lines
        time_span = self.camera.time_span_ms
        target_t_steps = max(2, int(chart_w / 120))
        raw_t_step = time_span / target_t_steps
        # Round time steps (1s, 5s, 10s, 30s, 1m, 5m, 15m, 1h, etc.)
        nice_t_steps = [1000, 2000, 5000, 10000, 30000, 60000, 120000, 300000, 900000, 1800000, 3600000]
        t_step = nice_t_steps[-1]
        for ns in nice_t_steps:
            if ns >= raw_t_step:
                t_step = ns
                break

        first_t = math.floor(self.camera.min_time / t_step) * t_step
        cur_t = first_t
        while cur_t <= self.camera.max_time + t_step:
            sx = self.camera.time_to_screen_x(cur_t)
            if 0 <= sx <= chart_w:
                painter.drawLine(int(sx), 0, int(sx), int(chart_h))
            cur_t += t_step

        painter.setClipping(False)

    def _draw_macro_levels(self, painter: QPainter, macro, chart_w: float, chart_h: float):
        painter.setClipRect(0, 0, int(chart_w), int(chart_h))

        # 1. Session High (Dashed Red Line)
        if macro.session_high > 0:
            sy = self.camera.price_to_screen_y(macro.session_high)
            if 0 <= sy <= chart_h:
                pen = QPen(Theme.LINE_HIGH, 1.0, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(0, int(sy), int(chart_w), int(sy))
                painter.setFont(QFont("Consolas", 7))
                painter.setPen(Theme.LINE_HIGH)
                painter.drawText(6, int(sy) - 3, f"HIGH {macro.session_high:.2f}")

        # 2. Session Low (Dashed Green Line)
        if macro.session_low > 0:
            sy = self.camera.price_to_screen_y(macro.session_low)
            if 0 <= sy <= chart_h:
                pen = QPen(Theme.LINE_LOW, 1.0, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(0, int(sy), int(chart_w), int(sy))
                painter.setFont(QFont("Consolas", 7))
                painter.setPen(Theme.LINE_LOW)
                painter.drawText(6, int(sy) + 11, f"LOW {macro.session_low:.2f}")

        # 3. Session VWAP (Cyan Dotted Line)
        if macro.session_vwap > 0:
            sy = self.camera.price_to_screen_y(macro.session_vwap)
            if 0 <= sy <= chart_h:
                pen = QPen(Theme.LINE_VWAP, 1.0, Qt.DotLine)
                painter.setPen(pen)
                painter.drawLine(0, int(sy), int(chart_w), int(sy))
                painter.setFont(QFont("Consolas", 7, QFont.Bold))
                painter.setPen(Theme.LINE_VWAP)
                painter.drawText(int(chart_w * 0.4), int(sy) - 3, f"SESSION VWAP {macro.session_vwap:.2f}")

        # 4. Point of Control / POC (Amber Line)
        if macro.poc_price > 0:
            sy = self.camera.price_to_screen_y(macro.poc_price)
            if 0 <= sy <= chart_h:
                pen = QPen(Theme.LINE_POC, 1.0, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(0, int(sy), int(chart_w), int(sy))
                painter.setFont(QFont("Consolas", 7, QFont.Bold))
                painter.setPen(Theme.LINE_POC)
                painter.drawText(int(chart_w * 0.65), int(sy) - 3, f"POC {macro.poc_price:.2f}")

        painter.setClipping(False)

    def _draw_trajectory(self, painter: QPainter, screen_points, chart_w: float, chart_h: float):
        """Draws the continuous path of price action connecting trades."""
        painter.setClipRect(0, 0, int(chart_w), int(chart_h))
        pen = QPen(Theme.TRAJECTORY_LINE, 1.2)
        painter.setPen(pen)

        poly = QPolygonF(screen_points)
        painter.drawPolyline(poly)

        # Draw leading dot at price tip
        if screen_points:
            tip = screen_points[-1]
            painter.setBrush(QBrush(Theme.TRAJECTORY_HEAD))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(tip, 2.5, 2.5)

        painter.setClipping(False)

    def _draw_right_dom(self, painter: QPainter, w: int, h: int, chart_w: float,
                       chart_h: float, dom_w: float):
        dom_x = int(chart_w)

        # 1. Background Rail & Left Border
        painter.fillRect(dom_x, 0, int(dom_w), int(chart_h), Theme.BG_DOM)
        painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
        painter.drawLine(dom_x, 0, dom_x, int(chart_h))

        # 2. Volume Profile Bars
        if self.current_layout and self.current_layout.snapshot:
            vp = self.current_layout.snapshot.volume_profile
            poc = self.current_layout.snapshot.macro.poc_price
            if vp:
                max_v = max(vp.values()) if vp else 1.0
                bar_max_w = dom_w * 0.55 # max 55% of column width

                for price_bin, vol in vp.items():
                    if self.camera.min_price <= price_bin <= self.camera.max_price:
                        sy = self.camera.price_to_screen_y(price_bin)
                        bar_len = (vol / max_v) * bar_max_w
                        is_poc = (abs(price_bin - poc) < 0.001)

                        color = Theme.VP_BAR_POC if is_poc else Theme.VP_BAR
                        painter.fillRect(dom_x + 2, int(sy - 2), int(bar_len), 4, color)

        # 3. Price Scale Ticks
        # Same price step as grid
        target_steps = max(2, int(chart_h / 45))
        raw_step = self.camera.price_range / target_steps
        exp = math.floor(math.log10(max(0.001, raw_step)))
        frac = raw_step / (10 ** exp)
        step = (1.0 if frac < 1.5 else (2.0 if frac < 3.5 else (5.0 if frac < 7.5 else 10.0))) * (10 ** exp)

        first_p = math.floor(self.camera.min_price / step) * step
        cur_p = first_p

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(Theme.GRID_TEXT)

        while cur_p <= self.camera.max_price + step:
            sy = self.camera.price_to_screen_y(cur_p)
            if 10 <= sy <= chart_h - 10:
                p_str = f"{cur_p:.2f}"
                painter.drawText(dom_x + int(dom_w * 0.45), int(sy + 4), p_str)
            cur_p += step

        # 4. Live Market Price Badge
        if self.last_price > 0:
            sy = self.camera.price_to_screen_y(self.last_price)
            if -10 <= sy <= chart_h + 10:
                badge_h = 18
                badge_w = dom_w - 6
                badge_rect = QRectF(dom_x + 3, sy - (badge_h / 2.0), badge_w, badge_h)

                painter.setBrush(QBrush(Theme.PRICE_BADGE_BG))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(badge_rect, 2, 2)

                painter.setFont(QFont("Consolas", 8, QFont.Bold))
                painter.setPen(Theme.PRICE_BADGE_TEXT)
                painter.drawText(badge_rect, Qt.AlignCenter, f"{self.last_price:.2f}")

    def _draw_time_axis(self, painter: QPainter, w: int, h: int, chart_w: float,
                        chart_h: float, time_h: float):
        time_y = int(chart_h)

        # Background & Top Border
        painter.fillRect(0, time_y, w, int(time_h), Theme.BG_DOCK)
        painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
        painter.drawLine(0, time_y, w, time_y)

        # Time Scale Labels
        time_span = self.camera.time_span_ms
        target_t_steps = max(2, int(chart_w / 120))
        raw_t_step = time_span / target_t_steps
        nice_t_steps = [1000, 2000, 5000, 10000, 30000, 60000, 120000, 300000, 900000, 1800000, 3600000]
        t_step = nice_t_steps[-1]
        for ns in nice_t_steps:
            if ns >= raw_t_step:
                t_step = ns
                break

        first_t = math.floor(self.camera.min_time / t_step) * t_step
        cur_t = first_t

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(Theme.GRID_TEXT)

        while cur_t <= self.camera.max_time + t_step:
            sx = self.camera.time_to_screen_x(cur_t)
            if 30 <= sx <= chart_w - 30:
                dt_str = datetime.fromtimestamp(cur_t / 1000.0).strftime('%H:%M:%S')
                painter.drawText(int(sx - 25), time_y + 16, dt_str)
            cur_t += t_step

    # --- Mouse & Navigation ---

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
        # Click on floating auto-scroll pill button
        if hasattr(self, '_pill_rect') and self._pill_rect and self._pill_rect.contains(event.position()):
            self.toggle_follow_live(True)
            event.accept()
            return

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

        # Update cursor when hovering over the auto-scroll button
        if hasattr(self, '_pill_rect') and self._pill_rect and self._pill_rect.contains(event.position()):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

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
        elif key in (Qt.Key_L, Qt.Key_A):
            self.toggle_follow_live()
        else:
            super().keyPressEvent(event)
