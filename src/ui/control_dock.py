from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QFont, QPen, QBrush, QColor
from PySide6.QtCore import Qt, QRectF, Signal
from src.visual.theme import Theme
from src.algo.accumulator import INTERVAL_OPTIONS

class ControlDock(QWidget):
    """
    Floating Bottom Studio Dock (32px height).
    Minimalist flat buttons for instant interval switching and visual gap/scale micro-adjustments.
    """
    interval_selected = Signal(str)
    gap_changed = Signal(float)
    scale_changed = Signal(float)
    autofit_toggled = Signal()
    follow_live_toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.active_interval = "AUTO"
        self.min_gap_px = 5.0
        self.size_scale = 1.0
        self.auto_fit = True
        self.follow_live = True

        # Common intervals visible on the dock
        self.intervals = ['1ms', '5ms', '50ms', '100ms', '1s', '5s', '1m', '5m', '15m', '1h', 'AUTO']

    def set_state(self, active_interval: str, gap: float, scale: float,
                  auto_fit: bool, follow_live: bool):
        self.active_interval = active_interval
        self.min_gap_px = gap
        self.size_scale = scale
        self.auto_fit = auto_fit
        self.follow_live = follow_live
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = self.width()
        h = self.height()

        # Matte Dark Dock Bar
        painter.fillRect(0, 0, w, h, QColor(14, 17, 23, 240))
        painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
        painter.drawLine(0, 0, w, 0)

        # -------------------------------------------------------------
        # 1. LEFT: Interval Strip
        # -------------------------------------------------------------
        btn_w = 46
        btn_h = 22
        btn_y = 5
        start_x = 10

        font_btn = QFont("Consolas", 8, QFont.Bold)
        painter.setFont(font_btn)

        for i, int_name in enumerate(self.intervals):
            bx = start_x + (i * (btn_w + 4))
            rect = QRectF(bx, btn_y, btn_w, btn_h)

            is_active = (self.active_interval == int_name)
            if is_active:
                painter.setBrush(QBrush(QColor(30, 41, 59)))
                painter.setPen(QPen(Theme.BORDER_ACTIVE, 1.0))
                painter.drawRoundedRect(rect, 2, 2)
                painter.setPen(Theme.TEXT_PRIMARY)
            else:
                painter.setBrush(QBrush(QColor(18, 22, 29)))
                painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
                painter.drawRoundedRect(rect, 2, 2)
                painter.setPen(Theme.TEXT_MUTED)

            painter.drawText(rect, Qt.AlignCenter, int_name)

        # -------------------------------------------------------------
        # 2. RIGHT: GAP, SCALE, FIT, LIVE Controls
        # -------------------------------------------------------------
        rx = w - 380

        # Gap adjustment: GAP: 5px [-] [+]
        painter.setFont(QFont("Consolas", 8))
        painter.setPen(Theme.TEXT_SECONDARY)
        painter.drawText(rx, 20, f"GAP:{int(self.min_gap_px)}px")

        # Gap [-] and [+]
        rect_gm = QRectF(rx + 60, btn_y, 18, btn_h)
        rect_gp = QRectF(rx + 82, btn_y, 18, btn_h)
        for r_btn, txt in [(rect_gm, "-"), (rect_gp, "+")]:
            painter.setBrush(QBrush(QColor(18, 22, 29)))
            painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
            painter.drawRoundedRect(r_btn, 2, 2)
            painter.setPen(Theme.TEXT_SECONDARY)
            painter.drawText(r_btn, Qt.AlignCenter, txt)

        # Scale adjustment: SCALE: 1.0x [-] [+]
        sx = rx + 120
        painter.drawText(sx, 20, f"SCALE:{self.size_scale:.1f}x")
        rect_sm = QRectF(sx + 78, btn_y, 18, btn_h)
        rect_sp = QRectF(sx + 100, btn_y, 18, btn_h)
        for r_btn, txt in [(rect_sm, "-"), (rect_sp, "+")]:
            painter.setBrush(QBrush(QColor(18, 22, 29)))
            painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
            painter.drawRoundedRect(r_btn, 2, 2)
            painter.setPen(Theme.TEXT_SECONDARY)
            painter.drawText(r_btn, Qt.AlignCenter, txt)

        # FIT Button
        fx = sx + 135
        rect_fit = QRectF(fx, btn_y, 40, btn_h)
        painter.setBrush(QBrush(QColor(30, 41, 59) if self.auto_fit else QColor(18, 22, 29)))
        painter.setPen(QPen(Theme.BORDER_ACTIVE if self.auto_fit else Theme.BORDER_HAIRLINE, 1.0))
        painter.drawRoundedRect(rect_fit, 2, 2)
        painter.setPen(Theme.TEXT_PRIMARY if self.auto_fit else Theme.TEXT_MUTED)
        painter.drawText(rect_fit, Qt.AlignCenter, "FIT")

        # LIVE Button
        lx = fx + 46
        rect_live = QRectF(lx, btn_y, 48, btn_h)
        painter.setBrush(QBrush(QColor(16, 185, 129, 30) if self.follow_live else QColor(18, 22, 29)))
        painter.setPen(QPen(Theme.STATUS_LIVE if self.follow_live else Theme.BORDER_HAIRLINE, 1.0))
        painter.drawRoundedRect(rect_live, 2, 2)
        painter.setPen(Theme.STATUS_LIVE if self.follow_live else Theme.TEXT_MUTED)
        painter.drawText(rect_live, Qt.AlignCenter, "● LIVE" if self.follow_live else "PAUSE")

        painter.end()

    def mousePressEvent(self, event):
        pos = event.position()
        w = self.width()
        btn_y = 5
        btn_h = 22

        if not (btn_y <= pos.y() <= btn_y + btn_h):
            event.ignore()
            return

        # 1. Check Interval buttons
        btn_w = 46
        start_x = 10
        for i, int_name in enumerate(self.intervals):
            bx = start_x + (i * (btn_w + 4))
            if bx <= pos.x() <= bx + btn_w:
                self.interval_selected.emit(int_name)
                event.accept()
                return

        # 2. Check Right Action buttons
        rx = w - 380
        # Gap - and +
        if (rx + 60) <= pos.x() <= (rx + 78):
            self.gap_changed.emit(max(0.0, self.min_gap_px - 1.0))
            event.accept()
            return
        if (rx + 82) <= pos.x() <= (rx + 100):
            self.gap_changed.emit(min(25.0, self.min_gap_px + 1.0))
            event.accept()
            return

        # Scale - and +
        sx = rx + 120
        if (sx + 78) <= pos.x() <= (sx + 96):
            self.scale_changed.emit(max(0.4, self.size_scale - 0.1))
            event.accept()
            return
        if (sx + 100) <= pos.x() <= (sx + 118):
            self.scale_changed.emit(min(3.0, self.size_scale + 0.1))
            event.accept()
            return

        # FIT button
        fx = sx + 135
        if fx <= pos.x() <= fx + 40:
            self.autofit_toggled.emit()
            event.accept()
            return

        # LIVE button
        lx = fx + 46
        if lx <= pos.x() <= lx + 48:
            self.follow_live_toggled.emit()
            event.accept()
            return

        event.ignore()
