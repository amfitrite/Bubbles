import time
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QFont, QPen, QBrush, QColor
from PySide6.QtCore import Qt, QRectF, Signal
from src.visual.theme import Theme

class HeaderBar(QWidget):
    """
    Monochrome Matte Studio Header Bar (38px height).
    Houses Market Info, 4 Core Mode Selectors, Real-Time FPS, FPS Target Switcher,
    and Quick Action buttons.
    """
    mode_selected = Signal(str)           # SPLIT_PIE, DELTA, IMBALANCE, TOTAL_VOLUME
    fps_target_selected = Signal(str)     # "60", "120", "UNLIMITED"
    settings_toggled = Signal()
    reset_camera_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.symbol = "XAUUSD"
        self.last_price = 0.0
        self.is_connected = False
        self.last_tick_time = 0.0
        self.fps = 0.0
        self.active_mode = "TOTAL_VOLUME" # Default mode
        self.fps_target = "60"            # Default 60 FPS

        self.modes = [
            ("SPLIT PIE", "SPLIT_PIE"),
            ("DELTA", "DELTA"),
            ("IMBALANCE", "IMBALANCE"),
            ("TOTAL VOL", "TOTAL_VOLUME")
        ]
        self._fps_rects = []

    def update_telemetry(self, symbol: str, price: float, is_connected: bool,
                         last_tick_time: float, fps: float, active_mode: str,
                         fps_target: str = "60"):
        if symbol:
            self.symbol = symbol
        if price > 0:
            self.last_price = price
        self.is_connected = is_connected
        self.last_tick_time = last_tick_time
        self.fps = fps
        self.active_mode = active_mode
        self.fps_target = fps_target
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = self.width()
        h = self.height()

        # Matte Background and Bottom Hairline Border
        painter.fillRect(0, 0, w, h, Theme.BG_HEADER)
        painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
        painter.drawLine(0, h - 1, w, h - 1)

        # -------------------------------------------------------------
        # 1. LEFT: Market Identity (Symbol, Price, Live Status)
        # -------------------------------------------------------------
        now = time.time()
        is_live = self.is_connected and (now - self.last_tick_time < 5.0) if self.last_tick_time > 0 else False
        dot_color = Theme.STATUS_LIVE if is_live else Theme.STATUS_OFFLINE

        # Status Dot
        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(14, 15, 7, 7)

        # Symbol
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.setPen(Theme.TEXT_PRIMARY)
        painter.drawText(28, 24, self.symbol)

        # Price
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(Theme.TOTAL_VOLUME)
        price_text = f"{self.last_price:.2f}" if self.last_price > 0 else "--.--"
        painter.drawText(95, 24, price_text)

        # -------------------------------------------------------------
        # 2. CENTER: 4 Modes Segmented Selector
        # -------------------------------------------------------------
        btn_w = 90
        btn_h = 24
        total_w = btn_w * 4
        start_x = (w - total_w) / 2.0
        btn_y = 7

        font_mode = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font_mode)

        for i, (label, mode_id) in enumerate(self.modes):
            bx = start_x + (i * btn_w)
            rect = QRectF(bx, btn_y, btn_w - 2, btn_h)

            is_active = (self.active_mode == mode_id)
            if is_active:
                painter.setBrush(QBrush(QColor(30, 41, 59))) # Slate dark active
                painter.setPen(QPen(Theme.BORDER_ACTIVE, 1.0))
                painter.drawRoundedRect(rect, 3, 3)
                painter.setPen(Theme.TEXT_PRIMARY)
            else:
                painter.setBrush(QBrush(QColor(18, 22, 29)))
                painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
                painter.drawRoundedRect(rect, 3, 3)
                painter.setPen(Theme.TEXT_MUTED)

            painter.drawText(rect, Qt.AlignCenter, label)

        # -------------------------------------------------------------
        # 3. RIGHT: Real-Time FPS, FPS Target Pills, Reset, Settings
        # -------------------------------------------------------------
        fps_val = self.fps
        if fps_val >= 115.0:
            fps_col = Theme.FPS_HIGH
            icon = "⚡"
        elif fps_val >= 58.0:
            fps_col = Theme.FPS_MID
            icon = "●"
        else:
            fps_col = Theme.FPS_LOW
            icon = "!"

        fps_text = f"{icon} {fps_val:.0f} FPS" if fps_val > 0 else "-- FPS"
        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(fps_col)
        painter.drawText(int(w - 310), 24, fps_text)

        # FPS Target Selector Pills: [60] [120] [MAX]
        font_pill = QFont("Consolas", 7, QFont.Bold)
        painter.setFont(font_pill)

        fps_opts = [("60", "60", 28), ("120", "120", 32), ("MAX", "UNLIMITED", 32)]
        px = w - 230
        self._fps_rects = []
        for lbl, val, pw in fps_opts:
            p_rect = QRectF(px, 8, pw, 22)
            self._fps_rects.append((p_rect, val))
            is_active = (self.fps_target == val)
            if is_active:
                painter.setBrush(QBrush(QColor(30, 41, 59)))
                painter.setPen(QPen(Theme.BORDER_ACTIVE, 1.0))
                painter.drawRoundedRect(p_rect, 2, 2)
                painter.setPen(Theme.STATUS_LIVE if val == "UNLIMITED" else Theme.TEXT_PRIMARY)
            else:
                painter.setBrush(QBrush(QColor(18, 22, 29)))
                painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
                painter.drawRoundedRect(p_rect, 2, 2)
                painter.setPen(Theme.TEXT_MUTED)

            painter.drawText(p_rect, Qt.AlignCenter, lbl)
            px += pw + 3

        # Reset Camera Button (⊙)
        reset_rect = QRectF(w - 100, 7, 24, 24)
        painter.setBrush(QBrush(QColor(18, 22, 29)))
        painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
        painter.drawRoundedRect(reset_rect, 3, 3)
        painter.setPen(Theme.TEXT_SECONDARY)
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(reset_rect, Qt.AlignCenter, "⊙")

        # Settings Button (SETUP)
        set_rect = QRectF(w - 70, 7, 55, 24)
        painter.setBrush(QBrush(QColor(18, 22, 29)))
        painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
        painter.drawRoundedRect(set_rect, 3, 3)
        painter.setPen(Theme.TEXT_SECONDARY)
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(set_rect, Qt.AlignCenter, "SETUP")

        painter.end()

    def mousePressEvent(self, event):
        pos = event.position()
        w = self.width()

        # 1. Check Mode Buttons
        btn_w = 90
        total_w = btn_w * 4
        start_x = (w - total_w) / 2.0
        btn_y = 7
        btn_h = 24

        if btn_y <= pos.y() <= btn_y + btn_h:
            for i, (_, mode_id) in enumerate(self.modes):
                bx = start_x + (i * btn_w)
                if bx <= pos.x() <= bx + btn_w:
                    self.mode_selected.emit(mode_id)
                    event.accept()
                    return

        # 2. Check FPS Target Selector Pills: [60], [120], [MAX]
        if hasattr(self, '_fps_rects'):
            for p_rect, val in self._fps_rects:
                if p_rect.contains(pos):
                    self.fps_target = val
                    self.fps_target_selected.emit(val)
                    self.update()
                    event.accept()
                    return

        # 3. Check Reset Camera Button: w - 100, 7, 24, 24
        if (w - 100) <= pos.x() <= (w - 76) and 7 <= pos.y() <= 31:
            self.reset_camera_clicked.emit()
            event.accept()
            return

        # 4. Check Settings Button: w - 70, 7, 55, 24
        if (w - 70) <= pos.x() <= (w - 15) and 7 <= pos.y() <= 31:
            self.settings_toggled.emit()
            event.accept()
            return

        event.ignore()
