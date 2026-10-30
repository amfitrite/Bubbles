import time
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtCore import Qt, QRectF
from src.ui.theme import Theme

class HUDOverlay(QWidget):
    """
    Transparent HUD overlay positioned above the BubbleCanvas.
    Displays symbol, price, live status, lenses, and active L2 DOM interval.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.symbol = "XAUUSD"
        self.last_price = 0.0
        self.tick_count = 0
        self.last_tick_time = 0.0
        self.is_connected = False
        self.active_lens = "CONTEXT"
        self.active_mode = "CLASSIC"
        self.active_interval = "AUTO"
        self.zoom_desc = "2M"
        self.lod_desc = "MICRO"
        self.follow_live = True

    def update_state(self, symbol: str, last_price: float, tick_count: int,
                     last_tick_time: float, is_connected: bool, follow_live: bool,
                     time_span_ms: float, macro_weight: float, active_interval: str = "AUTO"):
        if symbol:
            self.symbol = symbol
        if last_price > 0:
            self.last_price = last_price
        self.tick_count = tick_count
        self.last_tick_time = last_tick_time
        self.is_connected = is_connected
        self.follow_live = follow_live
        self.active_interval = active_interval

        # Format zoom description
        span_sec = time_span_ms / 1000.0
        if span_sec < 60:
            self.zoom_desc = f"{int(span_sec)}S"
        elif span_sec < 3600:
            self.zoom_desc = f"{int(span_sec / 60)}M"
        else:
            self.zoom_desc = f"{int(span_sec / 3600)}H"

        self.lod_desc = "MACRO" if macro_weight >= 0.5 else "MICRO"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = self.width()
        h = self.height()

        # 1. Top-Left Info Panel: Symbol, Last Price, Status Dot
        self._draw_top_left(painter)

        # 2. Top-Center: Lenses + Interval Pill
        self._draw_top_center(painter, w)

        # 3. Top-Right: LIVE pill & LOD status
        self._draw_top_right(painter, w)

        # 4. Bottom Hint Bar
        self._draw_bottom_hints(painter, w, h)

    def _draw_top_left(self, painter: QPainter):
        rect = QRectF(16, 16, 220, 44)
        painter.setBrush(QBrush(Theme.HUD_SURFACE))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(rect, 8, 8)

        now = time.time()
        age = now - self.last_tick_time if self.last_tick_time > 0 else 999.0
        if not self.is_connected:
            dot_color = Theme.STATUS_DISCONNECTED
            status_text = "OFFLINE"
        elif age > 5.0:
            dot_color = Theme.STATUS_STALE
            status_text = "STALE"
        else:
            dot_color = Theme.STATUS_LIVE
            status_text = "FEED LIVE"

        dot_center_x = 32
        dot_center_y = 38
        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(dot_center_x - 4, dot_center_y - 4, 8, 8)

        font_symbol = QFont("Segoe UI", 12, QFont.Bold)
        painter.setFont(font_symbol)
        painter.setPen(Theme.TEXT_PRIMARY)
        painter.drawText(46, 34, self.symbol)

        font_price = QFont("Segoe UI", 10)
        painter.setFont(font_price)
        painter.setPen(Theme.ACCENT)
        price_str = f"{self.last_price:.2f}" if self.last_price > 0 else "--.--"
        painter.drawText(46, 50, price_str)

        font_status = QFont("Segoe UI", 8)
        painter.setFont(font_status)
        painter.setPen(Theme.TEXT_MUTED)
        painter.drawText(150, 42, status_text)

    def _draw_top_center(self, painter: QPainter, width: int):
        bar_width = 320
        bar_x = (width - bar_width) / 2.0
        rect = QRectF(bar_x, 16, bar_width, 40)

        painter.setBrush(QBrush(Theme.HUD_SURFACE))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(rect, 8, 8)

        lenses = ["CONTEXT", "PRESSURE", "TRIGGER"]
        seg_w = bar_width / 3.0
        font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font)

        for i, lens in enumerate(lenses):
            seg_x = bar_x + (i * seg_w)
            is_active = (lens == self.active_lens)
            if is_active:
                active_rect = QRectF(seg_x + 3, 19, seg_w - 6, 34)
                painter.setBrush(QBrush(QColor(34, 211, 238, 30)))
                painter.setPen(QPen(Theme.ACCENT, 1))
                painter.drawRoundedRect(active_rect, 6, 6)
                painter.setPen(Theme.ACCENT)
            else:
                painter.setPen(Theme.TEXT_MUTED)

            painter.drawText(QRectF(seg_x, 16, seg_w, 40), Qt.AlignCenter, lens)

        # Subtitle under center bar: mode, zoom, and active L2 interval
        sub_font = QFont("Segoe UI", 8)
        painter.setFont(sub_font)
        painter.setPen(Theme.TEXT_MUTED)
        desc = f"{self.active_mode} · {self.zoom_desc} · INTERVAL: {self.active_interval}"
        painter.drawText(QRectF(bar_x - 60, 58, bar_width + 120, 20), Qt.AlignCenter, desc)

        # Interval Pill (Placed to the left of center bar)
        int_pill_x = bar_x - 110
        int_pill_rect = QRectF(int_pill_x, 16, 98, 40)
        painter.setBrush(QBrush(Theme.HUD_SURFACE))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(int_pill_rect, 8, 8)

        # Interval label & value
        p_font = QFont("Segoe UI", 7, QFont.Bold)
        painter.setFont(p_font)
        painter.setPen(Theme.TEXT_MUTED)
        painter.drawText(QRectF(int_pill_x, 20, 98, 14), Qt.AlignCenter, "ACCUMULATION")

        val_font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(val_font)
        painter.setPen(Theme.ACCENT if self.active_interval != "AUTO" else Theme.TEXT_PRIMARY)
        painter.drawText(QRectF(int_pill_x, 32, 98, 20), Qt.AlignCenter, self.active_interval)

    def _draw_top_right(self, painter: QPainter, width: int):
        rect = QRectF(width - 190, 16, 174, 40)
        painter.setBrush(QBrush(Theme.HUD_SURFACE))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(rect, 8, 8)

        if self.follow_live:
            pill_rect = QRectF(width - 180, 24, 60, 24)
            painter.setBrush(QBrush(QColor(16, 185, 129, 35)))
            painter.setPen(QPen(Theme.STATUS_LIVE, 1))
            painter.drawRoundedRect(pill_rect, 12, 12)

            font_live = QFont("Segoe UI", 8, QFont.Bold)
            painter.setFont(font_live)
            painter.setPen(Theme.STATUS_LIVE)
            painter.drawText(pill_rect, Qt.AlignCenter, "● LIVE")
        else:
            pill_rect = QRectF(width - 180, 24, 60, 24)
            painter.setBrush(QBrush(QColor(245, 158, 11, 25)))
            painter.setPen(QPen(Theme.STATUS_STALE, 1))
            painter.drawRoundedRect(pill_rect, 12, 12)

            font_live = QFont("Segoe UI", 8, QFont.Bold)
            painter.setFont(font_live)
            painter.setPen(Theme.STATUS_STALE)
            painter.drawText(pill_rect, Qt.AlignCenter, "PAUSED")

        font_lod = QFont("Segoe UI", 9, QFont.DemiBold)
        painter.setFont(font_lod)
        painter.setPen(Theme.TEXT_PRIMARY)
        painter.drawText(QRectF(width - 110, 16, 90, 40), Qt.AlignCenter, self.lod_desc)

    def _draw_bottom_hints(self, painter: QPainter, width: int, height: int):
        hint_text = "Wheel: Zoom  ·  Drag: Pan  ·  Space: Live  ·  Tab: Lens  ·  [ / ]: Interval (1ms..4h)  ·  DblClick: Reset"
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.setPen(Theme.TEXT_MUTED)
        rect = QRectF(0, height - 32, width, 24)
        painter.drawText(rect, Qt.AlignCenter, hint_text)
