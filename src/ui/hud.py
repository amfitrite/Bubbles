import time
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtCore import Qt, QRectF, Signal

from src.ui.theme import Theme

class HUDOverlay(QWidget):
    """
    Transparent HUD overlay positioned above the BubbleCanvas.
    Displays symbol, price, 3 Display Modes (Split Pie, Net Delta, Total Volume),
    Accumulation Interval pill, Settings gear button (⚙), and Floating Navigation Toolbar.
    """
    settings_clicked = Signal()
    mode_clicked = Signal(str)
    interval_clicked = Signal()
    zoom_in_clicked = Signal()
    zoom_out_clicked = Signal()
    autofit_clicked = Signal()
    live_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False) # Allows click interaction
        self.symbol = "XAUUSD"
        self.last_price = 0.0
        self.tick_count = 0
        self.last_tick_time = 0.0
        self.is_connected = False

        self.active_mode = "TOTAL_VOLUME" # 'SPLIT_PIE', 'NET_DELTA', 'TOTAL_VOLUME'
        self.active_interval = "AUTO"
        self.zoom_desc = "2M"
        self.lod_desc = "MICRO"
        self.follow_live = True

    def update_state(self, symbol: str, last_price: float, tick_count: int,
                     last_tick_time: float, is_connected: bool, follow_live: bool,
                     time_span_ms: float, macro_weight: float, active_interval: str = "AUTO",
                     active_mode: str = "TOTAL_VOLUME"):
        if symbol:
            self.symbol = symbol
        if last_price > 0:
            self.last_price = last_price
        self.tick_count = tick_count
        self.last_tick_time = last_tick_time
        self.is_connected = is_connected
        self.follow_live = follow_live
        self.active_interval = active_interval
        self.active_mode = active_mode

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

        # 1. Top-Left: Symbol, Price, Status
        self._draw_top_left(painter)

        # 2. Top-Center: 3 Modes (Split Pie / Net Delta / Total Volume) & Interval Pill
        self._draw_top_center(painter, w)

        # 3. Top-Right: Settings ⚙ Button, Live pill, LOD
        self._draw_top_right(painter, w)

        # 4. Bottom-Right: Floating Navigation Toolbar (+ / - / Fit / Live)
        self._draw_nav_toolbar(painter, w, h)

        # 5. Bottom Hint Bar
        self._draw_bottom_hints(painter, w, h)

    def _draw_top_left(self, painter: QPainter):
        rect = QRectF(16, 16, 210, 42)
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
            status_text = "LIVE FEED"

        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(30, 33, 8, 8)

        font_symbol = QFont("Segoe UI", 11, QFont.Bold)
        painter.setFont(font_symbol)
        painter.setPen(Theme.TEXT_PRIMARY)
        painter.drawText(44, 32, self.symbol)

        font_price = QFont("Segoe UI", 10)
        painter.setFont(font_price)
        painter.setPen(Theme.ACCENT)
        price_str = f"{self.last_price:.2f}" if self.last_price > 0 else "--.--"
        painter.drawText(44, 48, price_str)

        font_status = QFont("Segoe UI", 8)
        painter.setFont(font_status)
        painter.setPen(Theme.TEXT_MUTED)
        painter.drawText(145, 40, status_text)

    def _draw_top_center(self, painter: QPainter, width: int):
        # 3-Mode Segmented Bar
        bar_w = 340
        bar_x = (width - bar_w) / 2.0
        rect = QRectF(bar_x, 16, bar_w, 42)

        painter.setBrush(QBrush(Theme.HUD_SURFACE))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(rect, 8, 8)

        modes = [("SPLIT PIE", "SPLIT_PIE"), ("NET DELTA", "NET_DELTA"), ("TOTAL VOL", "TOTAL_VOLUME")]
        seg_w = bar_w / 3.0
        font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font)

        for i, (label, mode_key) in enumerate(modes):
            seg_x = bar_x + (i * seg_w)
            is_active = (self.active_mode == mode_key)
            if is_active:
                active_rect = QRectF(seg_x + 3, 19, seg_w - 6, 36)
                painter.setBrush(QBrush(QColor(34, 211, 238, 30)))
                painter.setPen(QPen(Theme.ACCENT, 1))
                painter.drawRoundedRect(active_rect, 6, 6)
                painter.setPen(Theme.ACCENT)
            else:
                painter.setPen(Theme.TEXT_MUTED)

            painter.drawText(QRectF(seg_x, 16, seg_w, 42), Qt.AlignCenter, label)

        # Interval Pill (Placed to the left of the 3-mode bar)
        int_pill_x = bar_x - 116
        int_pill_rect = QRectF(int_pill_x, 16, 104, 42)
        painter.setBrush(QBrush(Theme.HUD_SURFACE))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(int_pill_rect, 8, 8)

        p_font = QFont("Segoe UI", 7, QFont.Bold)
        painter.setFont(p_font)
        painter.setPen(Theme.TEXT_MUTED)
        painter.drawText(QRectF(int_pill_x, 21, 104, 12), Qt.AlignCenter, "ACCUMULATION")

        val_font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(val_font)
        painter.setPen(Theme.ACCENT if self.active_interval != "AUTO" else Theme.TEXT_PRIMARY)
        painter.drawText(QRectF(int_pill_x, 34, 104, 20), Qt.AlignCenter, self.active_interval)

    def _draw_top_right(self, painter: QPainter, width: int):
        # Surface for Right HUD tools
        rect = QRectF(width - 230, 16, 214, 42)
        painter.setBrush(QBrush(Theme.HUD_SURFACE))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(rect, 8, 8)

        # Live Pill
        if self.follow_live:
            pill_rect = QRectF(width - 220, 24, 58, 26)
            painter.setBrush(QBrush(QColor(16, 185, 129, 35)))
            painter.setPen(QPen(Theme.STATUS_LIVE, 1))
            painter.drawRoundedRect(pill_rect, 13, 13)

            font_live = QFont("Segoe UI", 8, QFont.Bold)
            painter.setFont(font_live)
            painter.setPen(Theme.STATUS_LIVE)
            painter.drawText(pill_rect, Qt.AlignCenter, "● LIVE")
        else:
            pill_rect = QRectF(width - 220, 24, 58, 26)
            painter.setBrush(QBrush(QColor(245, 158, 11, 25)))
            painter.setPen(QPen(Theme.STATUS_STALE, 1))
            painter.drawRoundedRect(pill_rect, 13, 13)

            font_live = QFont("Segoe UI", 8, QFont.Bold)
            painter.setFont(font_live)
            painter.setPen(Theme.STATUS_STALE)
            painter.drawText(pill_rect, Qt.AlignCenter, "PAUSED")

        # LOD Badge (MICRO / MACRO)
        font_lod = QFont("Segoe UI", 9, QFont.DemiBold)
        painter.setFont(font_lod)
        painter.setPen(Theme.TEXT_PRIMARY)
        painter.drawText(QRectF(width - 150, 16, 68, 42), Qt.AlignCenter, self.lod_desc)

        # Gear Icon Button ⚙
        gear_rect = QRectF(width - 70, 22, 30, 30)
        painter.setBrush(QBrush(QColor(255, 255, 255, 10)))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(gear_rect, 6, 6)

        painter.setFont(QFont("Segoe UI", 12))
        painter.setPen(Theme.ACCENT)
        painter.drawText(gear_rect, Qt.AlignCenter, "⚙")

    def _draw_nav_toolbar(self, painter: QPainter, width: int, height: int):
        """Floating Navigation Toolbar in Bottom-Right: [+] [-] [FIT] [LIVE]."""
        tb_w = 160
        tb_h = 36
        tb_x = width - tb_w - 16
        tb_y = height - tb_h - 44

        rect = QRectF(tb_x, tb_y, tb_w, tb_h)
        painter.setBrush(QBrush(Theme.HUD_SURFACE))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(rect, 8, 8)

        buttons = ["+", "-", "FIT", "LIVE"]
        btn_w = tb_w / 4.0
        font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font)

        for i, text in enumerate(buttons):
            bx = tb_x + (i * btn_w)
            b_rect = QRectF(bx, tb_y, btn_w, tb_h)
            painter.setPen(Theme.TEXT_PRIMARY if text != "LIVE" or not self.follow_live else Theme.STATUS_LIVE)
            painter.drawText(b_rect, Qt.AlignCenter, text)

    def _draw_bottom_hints(self, painter: QPainter, width: int, height: int):
        hint = "Left-Drag: Pan · Right-Drag: Price/Time Stretch · Wheel: Zoom · [ / ]: Interval (1ms..4h) · S: Settings Drawer"
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(Theme.TEXT_MUTED)
        rect = QRectF(0, height - 30, width, 22)
        painter.drawText(rect, Qt.AlignCenter, hint)

    def mousePressEvent(self, event):
        pos = event.position()
        w = self.width()
        h = self.height()
        bar_w = 340
        bar_x = (w - bar_w) / 2.0

        # 1. Check Settings ⚙ button: width - 70, 22, 30, 30
        gear_rect = QRectF(w - 70, 22, 30, 30)
        if gear_rect.contains(pos):
            self.settings_clicked.emit()
            event.accept()
            return

        # 2. Check Accumulation Pill: bar_x - 116, 16, 104, 42
        int_rect = QRectF(bar_x - 116, 16, 104, 42)
        if int_rect.contains(pos):
            self.interval_clicked.emit()
            event.accept()
            return

        # 3. Check Mode Bar Segments
        seg_w = bar_w / 3.0
        mode_keys = ["SPLIT_PIE", "NET_DELTA", "TOTAL_VOLUME"]
        for i, mode_key in enumerate(mode_keys):
            seg_rect = QRectF(bar_x + (i * seg_w), 16, seg_w, 42)
            if seg_rect.contains(pos):
                self.mode_clicked.emit(mode_key)
                event.accept()
                return

        # 4. Check Navigation Toolbar: tb_x, tb_y, 160, 36
        tb_w = 160
        tb_h = 36
        tb_x = w - tb_w - 16
        tb_y = h - tb_h - 44
        if QRectF(tb_x, tb_y, tb_w, tb_h).contains(pos):
            btn_w = tb_w / 4.0
            idx = int((pos.x() - tb_x) // btn_w)
            if idx == 0:
                self.zoom_in_clicked.emit()
            elif idx == 1:
                self.zoom_out_clicked.emit()
            elif idx == 2:
                self.autofit_clicked.emit()
            elif idx == 3:
                self.live_clicked.emit()
            event.accept()
            return

        # Pass through to canvas
        event.ignore()
