import time
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QRadialGradient, QBrush, QColor, QPen
from PySide6.QtCore import Qt, QTimer, QPoint

from src.engine.camera import Camera
from src.engine.lod import LODSelector
from src.engine.micro_grid import MicroGrid
from src.ui.bubble_renderer import BubbleRenderer
from src.ui.hud import HUDOverlay
from src.ui.theme import Theme
from src.util.math_utils import robust_p95

class BubbleCanvas(QWidget):
    """
    Core Canvas for rendering order flow bubbles.
    Strictly follows the 'Bubbles only on dark canvas' principle.
    """
    def __init__(self, tick_store, parent=None):
        super().__init__(parent)
        self.tick_store = tick_store
        self.micro_grid = MicroGrid()
        self.renderer = BubbleRenderer()
        self.camera = Camera(self.width(), self.height())

        # Overlay HUD
        self.hud = HUDOverlay(self)

        # Interaction state
        self.is_dragging = False
        self.last_mouse_pos = QPoint()

        # Engine / Data state
        self.last_rendered_version = -1
        self.visible_bubbles = [] # list of tuple (screen_x, screen_y, radius, color_type, has_glow)
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

        # Determine connection status
        has_recent = (now_sec - self.last_tick_time) < 10.0 if self.last_tick_time > 0 else False
        self.is_connected = (self.tick_store.count > 0 and has_recent)

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
        """Extracts visible ticks and runs MicroGrid aggregation."""
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

        # Slice ticks within camera time viewport [min_time - 1 bucket, max_time + 1 bucket]
        min_t = self.camera.min_time
        max_t = self.camera.max_time

        # Binary search slice for speed
        ts_arr = snapshot['ts']
        start_idx = np.searchsorted(ts_arr, min_t, side='left')
        end_idx = np.searchsorted(ts_arr, max_t, side='right')

        visible_ticks = snapshot[start_idx:end_idx]
        if len(visible_ticks) == 0:
            self.visible_bubbles = []
            return

        # Calculate LOD
        bucket_ms, price_bin, macro_weight, _ = LODSelector.calculate(
            self.camera.time_span_ms, self.camera.price_range, self.tick_size
        )

        # Aggregate through MicroGrid
        cells = self.micro_grid.build_grid(
            visible_ticks,
            self.camera.time_span_ms,
            bucket_ms,
            price_bin,
            style='vwap'
        )

        if not cells:
            self.visible_bubbles = []
            return

        # Compute robust p95 of cell volumes
        vols = np.array([c['volume'] for c in cells])
        self.p95_volume = robust_p95(vols)
        p98_volume = float(np.percentile(vols, 98)) if len(vols) >= 5 else (self.p95_volume * 1.5)

        # Collect price bounds for camera auto-fit
        prices = [c['y'] for c in cells]
        min_p = min(prices)
        max_p = max(prices)
        if self.camera.auto_fit_price:
            self.camera.update_auto_fit(min_p, max_p, self.tick_size)

        # Convert cells to screen space bubbles
        bubbles = []
        w = self.width()
        h = self.height()

        for c in cells:
            sx = self.camera.time_to_screen_x(c['x'])
            sy = self.camera.price_to_screen_y(c['y'])

            # Viewport culling
            if sx < -50 or sx > w + 50 or sy < -50 or sy > h + 50:
                continue

            vol = c['volume']
            radius = self.renderer.compute_radius(vol, self.p95_volume, is_macro=(macro_weight >= 0.8))
            has_glow = (vol >= p98_volume)
            color_type = "classic" # Classic cyan mode for M1

            bubbles.append({
                'sx': sx,
                'sy': sy,
                'radius': radius,
                'color_type': color_type,
                'has_glow': has_glow,
                'volume': vol
            })

        # Cap bubbles to max 3000 as per README
        if len(bubbles) > 3000:
            bubbles.sort(key=lambda b: b['volume'], reverse=True)
            bubbles = bubbles[:3000]

        # Sort so larger bubbles are drawn FIRST (in the back), smaller on top
        bubbles.sort(key=lambda b: b['radius'], reverse=True)
        self.visible_bubbles = bubbles

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # 1. Canvas Background with subtle radial vignette
        grad = QRadialGradient(w / 2.0, h / 2.0, max(w, h) * 0.7)
        grad.setColorAt(0.0, QColor("#0A0E15")) # subtle center highlight
        grad.setColorAt(0.8, QColor("#06080C")) # pure dark edge
        grad.setColorAt(1.0, QColor("#040508"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, h)

        # 2. Draw Bubbles
        for b in self.visible_bubbles:
            self.renderer.draw_bubble(
                painter,
                b['sx'],
                b['sy'],
                b['radius'],
                color_type=b['color_type'],
                has_glow=b['has_glow']
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
            zoom_price = False # Shift = time zoom only
        elif modifiers & Qt.ControlModifier:
            zoom_time = False  # Ctrl = price zoom only

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
            # Re-anchor to live
            self.camera.follow_live = True
            self.camera.auto_fit_price = True
            event.accept()
        elif key in (Qt.Key_Q, Qt.Key_1):
            self.hud.active_lens = "CONTEXT"
            self.camera.time_span_ms = 4 * 3600_000.0 # 4 hours
            event.accept()
        elif key in (Qt.Key_W, Qt.Key_2):
            self.hud.active_lens = "PRESSURE"
            self.camera.time_span_ms = 15 * 60_000.0  # 15 minutes
            event.accept()
        elif key in (Qt.Key_E, Qt.Key_3):
            self.hud.active_lens = "TRIGGER"
            self.camera.time_span_ms = 120_000.0      # 2 minutes
            event.accept()
        elif key == Qt.Key_Tab:
            # Cycle lenses
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
