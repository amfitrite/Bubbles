import time
import math
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QRadialGradient, QBrush, QColor, QPen
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF

from src.engine.camera import Camera
from src.engine.lod import LODSelector
from src.engine.micro_grid import MicroGrid
from src.engine.synthetic_dom import SyntheticDOMLadder
from src.engine.macro_series import MacroSeries
from src.engine.modes import ModeClassifier
from src.ui.bubble_renderer import BubbleRenderer
from src.ui.hud import HUDOverlay
from src.ui.tooltip import BubbleTooltip
from src.ui.settings_drawer import SettingsDrawer
from src.ui.theme import Theme
from src.util.math_utils import robust_p95
from src.util.time_utils import INTERVAL_OPTIONS, INTERVAL_MAP

class BubbleCanvas(QWidget):
    """
    Core Canvas for rendering order flow bubbles.
    Separates Mathematical Engine Algo (Truth) from Visual Presentation (Layout & Spacing).
    Supports 3 Display Modes: Split Pie, Net Delta, Total Volume.
    """
    def __init__(self, tick_store, bar_store=None, db_manager=None, parent=None):
        super().__init__(parent)
        self.tick_store = tick_store
        self.bar_store = bar_store
        self.db_manager = db_manager

        # Engine Algo components (Mathematical truth)
        self.dom_ladder = SyntheticDOMLadder()
        self.micro_grid = MicroGrid()
        self.macro_series = MacroSeries()

        # Engine Visual components (Presentation & Layout)
        self.renderer = BubbleRenderer()
        self.camera = Camera(self.width(), self.height())

        # Display Modes: 'SPLIT_PIE', 'NET_DELTA', 'TOTAL_VOLUME'
        self.active_mode = "TOTAL_VOLUME"
        self.active_interval = "AUTO"
        self.interval_options = INTERVAL_OPTIONS

        # Visual Tuning Settings
        self.size_scale = 1.0
        self.spacing_padding = 3.0
        self.min_volume_filter = 0.0

        # UI Overlays
        self.hud = HUDOverlay(self)
        self.tooltip = BubbleTooltip(self)
        self.settings_drawer = SettingsDrawer(self)
        self.settings_drawer.hide()

        # Wire HUD signals
        self.hud.settings_clicked.connect(self.toggle_settings_drawer)
        self.hud.mode_clicked.connect(self.set_mode)
        self.hud.interval_clicked.connect(lambda: self.cycle_interval(1))
        self.hud.zoom_in_clicked.connect(lambda: self.camera.zoom(1.25))
        self.hud.zoom_out_clicked.connect(lambda: self.camera.zoom(0.80))
        self.hud.autofit_clicked.connect(self._toggle_autofit)
        self.hud.live_clicked.connect(self._toggle_live)

        # Wire Settings Drawer signals
        self.settings_drawer.mode_changed.connect(self.set_mode)
        self.settings_drawer.interval_changed.connect(self.set_interval)
        self.settings_drawer.size_scale_changed.connect(self.set_size_scale)
        self.settings_drawer.spacing_padding_changed.connect(self.set_spacing_padding)
        self.settings_drawer.min_volume_changed.connect(self.set_min_volume_filter)
        self.settings_drawer.follow_live_toggled.connect(self._set_follow_live)
        self.settings_drawer.auto_fit_toggled.connect(self._set_auto_fit)
        self.settings_drawer.reset_camera_requested.connect(self.reset_camera)

        # Interaction state
        self.is_left_dragging = False
        self.is_right_dragging = False
        self.last_mouse_pos = QPoint()
        self.hover_mouse_pos = None

        # Data state
        self.last_rendered_version = -1
        self.visible_bubbles = []
        self.p95_volume = 1.0
        self.tick_size = 0.01
        self.symbol = "XAUUSD"
        self.last_tick_time = 0.0
        self.last_price = 0.0
        self.is_connected = False

        # 60 FPS coalesced repaint timer
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self.tick_frame)
        self.render_timer.start(16)

        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        self.camera.set_viewport_size(w, h)
        self.hud.resize(w, h)
        self.settings_drawer.setGeometry(w - self.settings_drawer.width(), 0, self.settings_drawer.width(), h)

    def set_symbol_info(self, symbol: str, tick_size: float = 0.01):
        if symbol:
            self.symbol = symbol
        if tick_size > 0:
            self.tick_size = tick_size

    def toggle_settings_drawer(self):
        if self.settings_drawer.isVisible():
            self.settings_drawer.hide()
        else:
            self.settings_drawer.update_ui_state(
                self.active_mode, self.active_interval, self.camera.follow_live, self.camera.auto_fit_price
            )
            self.settings_drawer.show()
            self.settings_drawer.raise_()

    def set_mode(self, mode: str):
        if mode in ("SPLIT_PIE", "NET_DELTA", "TOTAL_VOLUME"):
            self.active_mode = mode
            self.last_rendered_version = -1
            self.hud.active_mode = mode
            self.settings_drawer.update_ui_state(
                self.active_mode, self.active_interval, self.camera.follow_live, self.camera.auto_fit_price
            )

    def set_interval(self, interval_name: str):
        if interval_name in self.interval_options:
            self.active_interval = interval_name
            self.hud.active_interval = interval_name
            self.last_rendered_version = -1
            self.settings_drawer.update_ui_state(
                self.active_mode, self.active_interval, self.camera.follow_live, self.camera.auto_fit_price
            )

    def cycle_interval(self, step: int = 1):
        current_idx = self.interval_options.index(self.active_interval) if self.active_interval in self.interval_options else 0
        new_idx = (current_idx + step) % len(self.interval_options)
        self.set_interval(self.interval_options[new_idx])

    def set_size_scale(self, scale: float):
        self.size_scale = scale
        self.last_rendered_version = -1

    def set_spacing_padding(self, padding: float):
        self.spacing_padding = padding
        self.last_rendered_version = -1

    def set_min_volume_filter(self, min_vol: float):
        self.min_volume_filter = min_vol
        self.last_rendered_version = -1

    def _toggle_live(self):
        self.camera.follow_live = not self.camera.follow_live

    def _toggle_autofit(self):
        self.camera.auto_fit_price = not self.camera.auto_fit_price

    def _set_follow_live(self, val: bool):
        self.camera.follow_live = val

    def _set_auto_fit(self, val: bool):
        self.camera.auto_fit_price = val

    def reset_camera(self):
        latest_ms = self.tick_store.last_ts if self.tick_store else None
        self.camera.reset_to_recent(latest_ms, self.last_price)
        self.last_rendered_version = -1

    def tick_frame(self):
        now_sec = time.time()
        latest_tick_ms = self.tick_store.last_ts if self.tick_store else 0

        has_recent = (now_sec - self.last_tick_time) < 10.0 if self.last_tick_time > 0 else False
        self.is_connected = (self.tick_store and self.tick_store.count > 0 and has_recent)

        if self.camera.follow_live and latest_tick_ms > 0:
            self.camera.update_follow_live(latest_tick_ms)

        current_version = self.tick_store.version if self.tick_store else 0
        if current_version != self.last_rendered_version or self.camera.follow_live or self.is_left_dragging or self.is_right_dragging:
            self._rebuild_scene(latest_tick_ms)
            self.last_rendered_version = current_version

        manual_int_ms = INTERVAL_MAP.get(self.active_interval)
        bucket_ms, price_bin, macro_weight, _ = LODSelector.calculate(
            self.camera.time_span_ms, self.camera.price_range, self.tick_size, manual_interval_ms=manual_int_ms
        )
        self.hud.update_state(
            symbol=self.symbol,
            last_price=self.last_price,
            tick_count=self.tick_store.count if self.tick_store else 0,
            last_tick_time=self.last_tick_time,
            is_connected=self.is_connected,
            follow_live=self.camera.follow_live,
            time_span_ms=self.camera.time_span_ms,
            macro_weight=macro_weight,
            active_interval=self.active_interval,
            active_mode=self.active_mode
        )

        self._check_hover_tooltip()
        self.update()

    def _rebuild_scene(self, latest_tick_ms: float):
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

        min_t = self.camera.min_time
        max_t = self.camera.max_time

        manual_int_ms = INTERVAL_MAP.get(self.active_interval)
        bucket_ms, price_bin, macro_weight, _ = LODSelector.calculate(
            self.camera.time_span_ms, self.camera.price_range, self.tick_size, manual_interval_ms=manual_int_ms
        )

        ts_arr = snapshot['ts']
        start_idx = np.searchsorted(ts_arr, min_t, side='left')
        end_idx = np.searchsorted(ts_arr, max_t, side='right')
        visible_ticks = snapshot[start_idx:end_idx]

        bubbles = []
        collected_prices = []
        w = self.width()
        h = self.height()

        # Visual Spacing: calculate available pixel height per price bin
        px_per_price_unit = h / max(0.01, self.camera.price_range)
        price_row_height_px = self.tick_size * px_per_price_unit
        max_cell_radius = max(3.0, (price_row_height_px / 2.0) - self.spacing_padding)

        # -------------------------------------------------------------
        # A. MICRO LAYER (Synthetic L2 DOM Ladder)
        # -------------------------------------------------------------
        if macro_weight < 0.98 and len(visible_ticks) > 0:
            micro_alpha = 1.0 - macro_weight

            # Build L2 DOM Ladder cells (Mathematical truth)
            cells = self.dom_ladder.build_dom_ladder(
                visible_ticks,
                interval_ms=bucket_ms,
                tick_size=self.tick_size,
                style='dom_ladder'
            )

            if cells:
                vols = np.array([c['volume'] for c in cells])
                p95_v = robust_p95(vols)
                p98_v = float(np.percentile(vols, 98)) if len(vols) >= 5 else (p95_v * 1.5)

                for c in cells:
                    vol = c['volume']
                    # Apply min volume filter
                    if self.min_volume_filter > 0 and vol < self.min_volume_filter:
                        continue

                    collected_prices.append(c['y'])
                    sx = self.camera.time_to_screen_x(c['x'])
                    sy = self.camera.price_to_screen_y(c['y'])

                    if sx < -50 or sx > w + 50 or sy < -50 or sy > h + 50:
                        continue

                    # Engine Visual: compute radius with baseline volume 1.0 and cell spacing
                    radius = self.renderer.compute_radius(
                        vol, p95_v, is_macro=False,
                        size_scale=self.size_scale,
                        max_cell_radius=max_cell_radius
                    )
                    has_glow = (vol >= p98_v)

                    # Determine delta color
                    color_type, _, _ = ModeClassifier.classify_delta(c['buy_vol'], c['sell_vol'], vol)

                    bubbles.append({
                        'sx': sx,
                        'sy': sy,
                        'radius': radius,
                        'color_type': color_type,
                        'has_glow': has_glow,
                        'alpha': micro_alpha,
                        'volume': vol,
                        'buy_vol': c['buy_vol'],
                        'sell_vol': c['sell_vol'],
                        'price': c['y'],
                        'ts': c['x'],
                        'ticks': c['tick_count'],
                        'interval_ms': c.get('interval_ms', bucket_ms),
                        'imb_type': 'none',
                        'has_stack': False
                    })

        # -------------------------------------------------------------
        # B. MACRO LAYER
        # -------------------------------------------------------------
        if macro_weight > 0.02:
            macro_alpha = macro_weight
            macro_bubbles = []

            if self.bar_store:
                if self.camera.time_span_ms <= 3600_000.0 * 6:
                    bars = self.bar_store.get_bars_1s(int(min_t), int(max_t))
                else:
                    bars = self.bar_store.get_bars_1m(int(min_t), int(max_t))

                if len(bars) > 0:
                    macro_bubbles = self.macro_series.build_from_bars(bars, bucket_ms)

            if len(macro_bubbles) == 0 and self.db_manager and self.camera.time_span_ms > 3600_000.0:
                db_bars = self.db_manager.get_bars_1m(self.symbol, int(min_t), int(max_t))
                if db_bars:
                    bar_dtype = self.bar_store.dtype if self.bar_store else np.dtype([
                        ('ts', np.int64), ('open', np.float64), ('high', np.float64),
                        ('low', np.float64), ('close', np.float64), ('volume', np.float64),
                        ('buy_vol', np.float64), ('sell_vol', np.float64),
                        ('vwap', np.float64), ('ticks', np.int32)
                    ])
                    np_bars = np.array(db_bars, dtype=bar_dtype)
                    macro_bubbles = self.macro_series.build_from_bars(np_bars, bucket_ms)

            if len(macro_bubbles) == 0 and len(visible_ticks) > 0:
                macro_bubbles = self.macro_series.build_from_ticks(visible_ticks, bucket_ms)

            if macro_bubbles:
                m_vols = np.array([mb['volume'] for mb in macro_bubbles])
                m_p95 = robust_p95(m_vols)
                m_p98 = float(np.percentile(m_vols, 98)) if len(m_vols) >= 5 else (m_p95 * 1.5)

                for mb in macro_bubbles:
                    vol = mb['volume']
                    if self.min_volume_filter > 0 and vol < self.min_volume_filter:
                        continue

                    collected_prices.append(mb['y'])
                    sx = self.camera.time_to_screen_x(mb['x'])
                    sy = self.camera.price_to_screen_y(mb['y'])

                    if sx < -60 or sx > w + 60 or sy < -60 or sy > h + 60:
                        continue

                    radius = self.renderer.compute_radius(
                        vol, m_p95, is_macro=True,
                        size_scale=self.size_scale
                    )
                    has_glow = (vol >= m_p98)
                    color_type, _, _ = ModeClassifier.classify_delta(mb['buy_vol'], mb['sell_vol'], vol)

                    bubbles.append({
                        'sx': sx,
                        'sy': sy,
                        'radius': radius,
                        'color_type': color_type,
                        'has_glow': has_glow,
                        'alpha': macro_alpha,
                        'volume': vol,
                        'buy_vol': mb['buy_vol'],
                        'sell_vol': mb['sell_vol'],
                        'price': mb['y'],
                        'ts': mb['x'],
                        'ticks': mb['ticks'],
                        'interval_ms': bucket_ms,
                        'imb_type': color_type,
                        'has_stack': False
                    })

        if self.camera.auto_fit_price and collected_prices:
            min_p = min(collected_prices)
            max_p = max(collected_prices)
            self.camera.update_auto_fit(min_p, max_p, self.tick_size)

        if len(bubbles) > 3000:
            bubbles.sort(key=lambda b: b['volume'], reverse=True)
            bubbles = bubbles[:3000]

        # Sort so larger bubbles are drawn in back, smaller on top
        bubbles.sort(key=lambda b: b['radius'], reverse=True)
        self.visible_bubbles = bubbles

    def _check_hover_tooltip(self):
        if not self.hover_mouse_pos or not self.visible_bubbles or self.settings_drawer.isVisible():
            self.tooltip.hide_tooltip()
            return

        mx = self.hover_mouse_pos.x()
        my = self.hover_mouse_pos.y()

        closest_b = None
        min_dist = 999999.0

        for b in self.visible_bubbles:
            dx = mx - b['sx']
            dy = my - b['sy']
            dist = math.hypot(dx, dy)
            threshold = b['radius'] + 10.0

            if dist <= threshold and dist < min_dist:
                min_dist = dist
                closest_b = b

        if closest_b:
            self.tooltip.show_bubble(
                closest_b,
                closest_b['sx'],
                closest_b['sy'],
                self.width(),
                self.height()
            )
        else:
            self.tooltip.hide_tooltip()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Canvas Background with radial vignette
        grad = QRadialGradient(w / 2.0, h / 2.0, max(w, h) * 0.7)
        grad.setColorAt(0.0, QColor("#0A0E15"))
        grad.setColorAt(0.8, QColor("#06080C"))
        grad.setColorAt(1.0, QColor("#040508"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, h)

        # Draw Bubbles according to active mode (SPLIT_PIE / NET_DELTA / TOTAL_VOLUME)
        for b in self.visible_bubbles:
            self.renderer.draw_bubble(
                painter,
                b['sx'],
                b['sy'],
                b['radius'],
                mode=self.active_mode,
                color_type=b['color_type'],
                buy_vol=b['buy_vol'],
                sell_vol=b['sell_vol'],
                has_glow=b['has_glow'],
                alpha=b['alpha']
            )

        painter.end()

    # --- Mouse & Interaction Handlers ---

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

        self.camera.zoom(
            factor=factor,
            anchor_x=pos.x(),
            anchor_y=pos.y(),
            zoom_time=zoom_time,
            zoom_price=zoom_price
        )
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_left_dragging = True
            self.last_mouse_pos = event.pos()
            event.accept()
        elif event.button() == Qt.RightButton:
            # Right-click drag starts Price & Time Stretch
            self.is_right_dragging = True
            self.last_mouse_pos = event.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        self.hover_mouse_pos = event.pos()
        delta = event.pos() - self.last_mouse_pos
        self.last_mouse_pos = event.pos()

        if self.is_left_dragging:
            # Left-click drag: Pan
            self.camera.pan(delta.x(), delta.y())
        elif self.is_right_dragging:
            # Right-click drag: Price stretch (dy) and Time stretch (dx)
            self.camera.stretch(delta.x(), delta.y())

        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_left_dragging = False
            event.accept()
        elif event.button() == Qt.RightButton:
            self.is_right_dragging = False
            event.accept()

    def mouseDoubleClickEvent(self, event):
        self.reset_camera()
        event.accept()

    def leaveEvent(self, event):
        self.hover_mouse_pos = None
        self.tooltip.hide_tooltip()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Space:
            self._toggle_live()
            event.accept()
        elif key == Qt.Key_S:
            self.toggle_settings_drawer()
            event.accept()
        elif key == Qt.Key_Escape:
            if self.settings_drawer.isVisible():
                self.settings_drawer.hide()
            event.accept()
        elif key == Qt.Key_1:
            self.set_mode("SPLIT_PIE")
            event.accept()
        elif key == Qt.Key_2:
            self.set_mode("NET_DELTA")
            event.accept()
        elif key == Qt.Key_3:
            self.set_mode("TOTAL_VOLUME")
            event.accept()
        elif key == Qt.Key_BracketRight:
            self.cycle_interval(1)
            event.accept()
        elif key == Qt.Key_BracketLeft:
            self.cycle_interval(-1)
            event.accept()
        elif key in (Qt.Key_0, Qt.Key_QuoteLeft):
            self.set_interval("AUTO")
            event.accept()
        else:
            super().keyPressEvent(event)
