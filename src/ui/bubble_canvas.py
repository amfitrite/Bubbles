import time
import math
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QRadialGradient, QBrush, QColor, QPen
from PySide6.QtCore import Qt, QTimer, QPoint

from src.engine.camera import Camera
from src.engine.lod import LODSelector
from src.engine.micro_grid import MicroGrid
from src.engine.macro_series import MacroSeries
from src.engine.modes import ModeClassifier
from src.ui.bubble_renderer import BubbleRenderer
from src.ui.hud import HUDOverlay
from src.ui.tooltip import BubbleTooltip
from src.ui.theme import Theme
from src.util.math_utils import robust_p95

class BubbleCanvas(QWidget):
    """
    Core Canvas for rendering order flow bubbles.
    Implements Hybrid LOD, 3 Modes (Classic, Delta, Imbalance), and Precision Tooltips.
    """
    def __init__(self, tick_store, bar_store=None, db_manager=None, parent=None):
        super().__init__(parent)
        self.tick_store = tick_store
        self.bar_store = bar_store
        self.db_manager = db_manager

        self.micro_grid = MicroGrid()
        self.macro_series = MacroSeries()
        self.renderer = BubbleRenderer()
        self.camera = Camera(self.width(), self.height())

        # Modes and Lenses
        self.active_mode = "CLASSIC" # 'CLASSIC', 'DELTA', 'IMBALANCE'
        self.active_lens = "CONTEXT" # 'CONTEXT', 'PRESSURE', 'TRIGGER', 'CUSTOM'

        # Overlay HUD & Floating Tooltip
        self.hud = HUDOverlay(self)
        self.tooltip = BubbleTooltip(self)

        # Interaction state
        self.is_dragging = False
        self.last_mouse_pos = QPoint()
        self.hover_mouse_pos = None

        # Engine / Data state
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
        self.setCursor(Qt.OpenHandCursor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        self.camera.set_viewport_size(w, h)
        self.hud.resize(w, h)

    def set_symbol_info(self, symbol: str, tick_size: float = 0.01):
        if symbol:
            self.symbol = symbol
        if tick_size > 0:
            self.tick_size = tick_size

    def set_lens(self, lens: str):
        self.active_lens = lens
        if lens == "CONTEXT":
            self.active_mode = "CLASSIC"
            self.camera.time_span_ms = 4 * 3600_000.0  # 4 hours
        elif lens == "PRESSURE":
            self.active_mode = "DELTA"
            self.camera.time_span_ms = 15 * 60_000.0   # 15 minutes
        elif lens == "TRIGGER":
            self.active_mode = "IMBALANCE"
            self.camera.time_span_ms = 120_000.0       # 2 minutes
        self.hud.active_lens = self.active_lens
        self.hud.active_mode = self.active_mode

    def set_manual_mode(self, mode: str):
        self.active_mode = mode
        self.active_lens = "CUSTOM"
        self.hud.active_lens = "CUSTOM"
        self.hud.active_mode = mode

    def tick_frame(self):
        now_sec = time.time()
        latest_tick_ms = self.tick_store.last_ts if self.tick_store else 0

        # Connection status
        has_recent = (now_sec - self.last_tick_time) < 10.0 if self.last_tick_time > 0 else False
        self.is_connected = (self.tick_store and self.tick_store.count > 0 and has_recent)

        # 1. Update live follow in camera
        if self.camera.follow_live and latest_tick_ms > 0:
            self.camera.update_follow_live(latest_tick_ms)

        # 2. Check if scene rebuild is needed
        current_version = self.tick_store.version if self.tick_store else 0
        if current_version != self.last_rendered_version or self.camera.follow_live or self.is_dragging:
            self._rebuild_scene(latest_tick_ms)
            self.last_rendered_version = current_version

        # 3. Update HUD
        bucket_ms, price_bin, macro_weight, _ = LODSelector.calculate(
            self.camera.time_span_ms, self.camera.price_range, self.tick_size
        )
        self.hud.active_mode = self.active_mode
        self.hud.update_state(
            symbol=self.symbol,
            last_price=self.last_price,
            tick_count=self.tick_store.count if self.tick_store else 0,
            last_tick_time=self.last_tick_time,
            is_connected=self.is_connected,
            follow_live=self.camera.follow_live,
            time_span_ms=self.camera.time_span_ms,
            macro_weight=macro_weight
        )

        # 4. Check hover tooltip
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

        bucket_ms, price_bin, macro_weight, _ = LODSelector.calculate(
            self.camera.time_span_ms, self.camera.price_range, self.tick_size
        )

        ts_arr = snapshot['ts']
        start_idx = np.searchsorted(ts_arr, min_t, side='left')
        end_idx = np.searchsorted(ts_arr, max_t, side='right')
        visible_ticks = snapshot[start_idx:end_idx]

        bubbles = []
        collected_prices = []
        w = self.width()
        h = self.height()

        # -------------------------------------------------------------
        # A. MICRO LAYER
        # -------------------------------------------------------------
        if macro_weight < 0.98 and len(visible_ticks) > 0:
            micro_alpha = 1.0 - macro_weight
            cells = self.micro_grid.build_grid(
                visible_ticks,
                self.camera.time_span_ms,
                bucket_ms,
                price_bin,
                style='vwap'
            )
            if cells:
                vols = np.array([c['volume'] for c in cells])
                p95_v = robust_p95(vols)
                p98_v = float(np.percentile(vols, 98)) if len(vols) >= 5 else (p95_v * 1.5)

                # Precompute diagonal imbalances if mode is IMBALANCE
                imb_map = {}
                if self.active_mode == "IMBALANCE":
                    imb_map = ModeClassifier.compute_micro_diagonal_imbalances(cells)

                for c in cells:
                    collected_prices.append(c['y'])
                    sx = self.camera.time_to_screen_x(c['x'])
                    sy = self.camera.price_to_screen_y(c['y'])

                    if sx < -50 or sx > w + 50 or sy < -50 or sy > h + 50:
                        continue

                    vol = c['volume']
                    radius = self.renderer.compute_radius(vol, p95_v, is_macro=False)
                    has_glow = (vol >= p98_v)

                    # Determine color type by mode
                    if self.active_mode == "DELTA":
                        color_type, _, _ = ModeClassifier.classify_delta(c['buy_vol'], c['sell_vol'], vol)
                    elif self.active_mode == "IMBALANCE":
                        imb_info = imb_map.get((c['t_idx'], c['p_idx']), {'imb_type': 'balanced', 'has_stack': False})
                        color_type = imb_info['imb_type']
                        if imb_info.get('has_stack'):
                            has_glow = True
                    else:
                        color_type = "classic"

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
                        'imb_type': imb_map.get((c['t_idx'], c['p_idx']), {}).get('imb_type', 'none'),
                        'has_stack': imb_map.get((c['t_idx'], c['p_idx']), {}).get('has_stack', False)
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
                    collected_prices.append(mb['y'])
                    sx = self.camera.time_to_screen_x(mb['x'])
                    sy = self.camera.price_to_screen_y(mb['y'])

                    if sx < -60 or sx > w + 60 or sy < -60 or sy > h + 60:
                        continue

                    vol = mb['volume']
                    radius = self.renderer.compute_radius(vol, m_p95, is_macro=True)
                    has_glow = (vol >= m_p98)

                    if self.active_mode == "DELTA":
                        color_type, _, _ = ModeClassifier.classify_delta(mb['buy_vol'], mb['sell_vol'], vol)
                    elif self.active_mode == "IMBALANCE":
                        delta_v = mb['buy_vol'] - mb['sell_vol']
                        if mb['buy_vol'] >= 3.0 * max(1.0, mb['sell_vol']):
                            color_type = "imb_buy"
                        elif mb['sell_vol'] >= 3.0 * max(1.0, mb['buy_vol']):
                            color_type = "imb_sell"
                        else:
                            color_type = "balanced"
                    else:
                        color_type = "classic"

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

        # Draw larger bubbles in the back, smaller on top
        bubbles.sort(key=lambda b: b['radius'], reverse=True)
        self.visible_bubbles = bubbles

    def _check_hover_tooltip(self):
        if not self.hover_mouse_pos or not self.visible_bubbles:
            self.tooltip.hide_tooltip()
            return

        mx = self.hover_mouse_pos.x()
        my = self.hover_mouse_pos.y()

        # Find closest bubble within radius + 12px
        closest_b = None
        min_dist = 999999.0

        for b in self.visible_bubbles:
            dx = mx - b['sx']
            dy = my - b['sy']
            dist = math.hypot(dx, dy)
            threshold = b['radius'] + 12.0

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

        # Canvas Background
        grad = QRadialGradient(w / 2.0, h / 2.0, max(w, h) * 0.7)
        grad.setColorAt(0.0, QColor("#0A0E15"))
        grad.setColorAt(0.8, QColor("#06080C"))
        grad.setColorAt(1.0, QColor("#040508"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, h)

        # Draw Bubbles
        for b in self.visible_bubbles:
            self.renderer.draw_bubble(
                painter,
                b['sx'],
                b['sy'],
                b['radius'],
                color_type=b['color_type'],
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
            self.is_dragging = True
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        self.hover_mouse_pos = event.pos()
        if self.is_dragging:
            delta = event.pos() - self.last_mouse_pos
            self.last_mouse_pos = event.pos()
            self.camera.pan(delta.x(), delta.y())
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.setCursor(Qt.OpenHandCursor)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        latest_ms = self.tick_store.last_ts if self.tick_store else None
        self.camera.reset_to_recent(latest_ms, self.last_price)
        event.accept()

    def leaveEvent(self, event):
        self.hover_mouse_pos = None
        self.tooltip.hide_tooltip()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Space:
            self.camera.follow_live = True
            self.camera.auto_fit_price = True
            event.accept()
        elif key == Qt.Key_Q:
            self.set_lens("CONTEXT")
            event.accept()
        elif key == Qt.Key_W:
            self.set_lens("PRESSURE")
            event.accept()
        elif key == Qt.Key_E:
            self.set_lens("TRIGGER")
            event.accept()
        elif key == Qt.Key_1:
            self.set_manual_mode("CLASSIC")
            event.accept()
        elif key == Qt.Key_2:
            self.set_manual_mode("DELTA")
            event.accept()
        elif key == Qt.Key_3:
            self.set_manual_mode("IMBALANCE")
            event.accept()
        elif key == Qt.Key_Tab:
            order = ["CONTEXT", "PRESSURE", "TRIGGER"]
            idx = (order.index(self.active_lens) + 1) % len(order) if self.active_lens in order else 0
            self.set_lens(order[idx])
            event.accept()
        else:
            super().keyPressEvent(event)
