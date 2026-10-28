import time
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QRadialGradient, QBrush, QColor, QPen
from PySide6.QtCore import Qt, QTimer, QPoint

from src.engine.camera import Camera
from src.engine.lod import LODSelector
from src.engine.micro_grid import MicroGrid
from src.engine.macro_series import MacroSeries
from src.ui.bubble_renderer import BubbleRenderer
from src.ui.hud import HUDOverlay
from src.ui.theme import Theme
from src.util.math_utils import robust_p95

class BubbleCanvas(QWidget):
    """
    Core Canvas for rendering order flow bubbles.
    Implements the Hybrid Micro/Macro Level of Detail (LOD) architecture.
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

        # Overlay HUD
        self.hud = HUDOverlay(self)

        # Interaction state
        self.is_dragging = False
        self.last_mouse_pos = QPoint()

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
        self.render_timer.start(16) # ~60 FPS

        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

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

    def tick_frame(self):
        """Called every 16ms by QTimer to drive camera and update canvas."""
        now_sec = time.time()
        latest_tick_ms = self.tick_store.last_ts if self.tick_store else 0

        # Connection status
        has_recent = (now_sec - self.last_tick_time) < 10.0 if self.last_tick_time > 0 else False
        self.is_connected = (self.tick_store and self.tick_store.count > 0 and has_recent)

        # 1. Update live follow in camera
        if self.camera.follow_live and latest_tick_ms > 0:
            self.camera.update_follow_live(latest_tick_ms)

        # 2. Check if we need to rebuild the visible bubbles list
        current_version = self.tick_store.version if self.tick_store else 0
        if current_version != self.last_rendered_version or self.camera.follow_live or self.is_dragging:
            self._rebuild_scene(latest_tick_ms)
            self.last_rendered_version = current_version

        # 3. Update HUD
        bucket_ms, price_bin, macro_weight, _ = LODSelector.calculate(
            self.camera.time_span_ms, self.camera.price_range, self.tick_size
        )
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

        self.update()

    def _rebuild_scene(self, latest_tick_ms: float):
        """Builds combined Micro and Macro bubbles based on current LOD."""
        if not self.tick_store or self.tick_store.count == 0:
            self.visible_bubbles = []
            return

        snapshot, _ = self.tick_store.get_snapshot()
        if len(snapshot) == 0:
            self.visible_bubbles = []
            return

        # Update last price and time
        last_t = snapshot[-1]
        self.last_price = float(last_t['last'] if last_t['last'] > 0 else last_t['bid'])
        self.last_tick_time = time.time()

        min_t = self.camera.min_time
        max_t = self.camera.max_time

        # Calculate LOD
        bucket_ms, price_bin, macro_weight, _ = LODSelector.calculate(
            self.camera.time_span_ms, self.camera.price_range, self.tick_size
        )

        # Fast binary slice for ticks in viewport
        ts_arr = snapshot['ts']
        start_idx = np.searchsorted(ts_arr, min_t, side='left')
        end_idx = np.searchsorted(ts_arr, max_t, side='right')
        visible_ticks = snapshot[start_idx:end_idx]

        bubbles = []
        collected_prices = []
        w = self.width()
        h = self.height()

        # -------------------------------------------------------------
        # A. MICRO LAYER (Computed if macro_weight < 0.98)
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

                for c in cells:
                    collected_prices.append(c['y'])
                    sx = self.camera.time_to_screen_x(c['x'])
                    sy = self.camera.price_to_screen_y(c['y'])

                    if sx < -50 or sx > w + 50 or sy < -50 or sy > h + 50:
                        continue

                    vol = c['volume']
                    radius = self.renderer.compute_radius(vol, p95_v, is_macro=False)
                    has_glow = (vol >= p98_v)

                    bubbles.append({
                        'sx': sx,
                        'sy': sy,
                        'radius': radius,
                        'color_type': 'classic',
                        'has_glow': has_glow,
                        'alpha': micro_alpha,
                        'volume': vol
                    })

        # -------------------------------------------------------------
        # B. MACRO LAYER (Computed if macro_weight > 0.02)
        # -------------------------------------------------------------
        if macro_weight > 0.02:
            macro_alpha = macro_weight
            macro_bubbles = []

            # 1. Try to fetch from BarStore (1s or 1m bars)
            if self.bar_store:
                if self.camera.time_span_ms <= 3600_000.0 * 6:  # up to 6 hours: 1s bars
                    bars = self.bar_store.get_bars_1s(int(min_t), int(max_t))
                else:
                    bars = self.bar_store.get_bars_1m(int(min_t), int(max_t))

                if len(bars) > 0:
                    macro_bubbles = self.macro_series.build_from_bars(bars, bucket_ms)

            # 2. Multi-day fallback: query SQLite bars_1m if BarStore has few bars
            if len(macro_bubbles) == 0 and self.db_manager and self.camera.time_span_ms > 3600_000.0:
                db_bars = self.db_manager.get_bars_1m(self.symbol, int(min_t), int(max_t))
                if db_bars:
                    # Convert db rows to structured numpy array
                    bar_dtype = self.bar_store.dtype if self.bar_store else np.dtype([
                        ('ts', np.int64), ('open', np.float64), ('high', np.float64),
                        ('low', np.float64), ('close', np.float64), ('volume', np.float64),
                        ('buy_vol', np.float64), ('sell_vol', np.float64),
                        ('vwap', np.float64), ('ticks', np.int32)
                    ])
                    np_bars = np.array(db_bars, dtype=bar_dtype)
                    macro_bubbles = self.macro_series.build_from_bars(np_bars, bucket_ms)

            # 3. Fallback: aggregate directly from visible ticks
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

                    bubbles.append({
                        'sx': sx,
                        'sy': sy,
                        'radius': radius,
                        'color_type': 'classic',
                        'has_glow': has_glow,
                        'alpha': macro_alpha,
                        'volume': vol
                    })

        # Auto-fit camera price range
        if self.camera.auto_fit_price and collected_prices:
            min_p = min(collected_prices)
            max_p = max(collected_prices)
            self.camera.update_auto_fit(min_p, max_p, self.tick_size)

        # Cap bubbles to 3000 max
        if len(bubbles) > 3000:
            bubbles.sort(key=lambda b: b['volume'], reverse=True)
            bubbles = bubbles[:3000]

        # Sort so larger bubbles are drawn FIRST (in back), smaller on top
        bubbles.sort(key=lambda b: b['radius'], reverse=True)
        self.visible_bubbles = bubbles

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Canvas Background with subtle radial vignette
        grad = QRadialGradient(w / 2.0, h / 2.0, max(w, h) * 0.7)
        grad.setColorAt(0.0, QColor("#0A0E15"))
        grad.setColorAt(0.8, QColor("#06080C"))
        grad.setColorAt(1.0, QColor("#040508"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, h)

        # Draw Bubbles (with their respective alpha)
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
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            delta = event.pos() - self.last_mouse_pos
            self.last_mouse_pos = event.pos()
            self.camera.pan(delta.x(), delta.y())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            event.accept()

    def mouseDoubleClickEvent(self, event):
        latest_ms = self.tick_store.last_ts if self.tick_store else None
        self.camera.reset_to_recent(latest_ms, self.last_price)
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Space:
            self.camera.follow_live = True
            self.camera.auto_fit_price = True
            event.accept()
        elif key in (Qt.Key_Q, Qt.Key_1):
            self.hud.active_lens = "CONTEXT"
            self.camera.time_span_ms = 4 * 3600_000.0  # 4 hours (Macro)
            event.accept()
        elif key in (Qt.Key_W, Qt.Key_2):
            self.hud.active_lens = "PRESSURE"
            self.camera.time_span_ms = 15 * 60_000.0   # 15 minutes (Hybrid)
            event.accept()
        elif key in (Qt.Key_E, Qt.Key_3):
            self.hud.active_lens = "TRIGGER"
            self.camera.time_span_ms = 120_000.0       # 2 minutes (Micro)
            event.accept()
        elif key == Qt.Key_Tab:
            order = ["CONTEXT", "PRESSURE", "TRIGGER"]
            idx = (order.index(self.hud.active_lens) + 1) % len(order)
            self.hud.active_lens = order[idx]
            if self.hud.active_lens == "CONTEXT":
                self.camera.time_span_ms = 4 * 3600_000.0
            elif self.hud.active_lens == "PRESSURE":
                self.camera.time_span_ms = 15 * 60_000.0
            else:
                self.camera.time_span_ms = 120_000.0
            event.accept()
        else:
            super().keyPressEvent(event)
