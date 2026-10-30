from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QFont, QPen, QBrush, QColor
from PySide6.QtCore import Qt, QRectF, Signal
from src.visual.theme import Theme

class ControlDock(QWidget):
    """
    Floating Bottom Studio Dock (32px height).
    Provides instant timeframe switching (1ms .. 1h, AUTO),
    Micro Gap/Scale adjustments, FIT, and AUTO SCROLL controls.
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
        self.min_gap_px = 6.0
        self.size_scale = 1.0
        self.auto_fit = True
        self.follow_live = True

        # Complete range of timeframes including 10s, 15s, 30s
        self.intervals = [
            '1ms', '5ms', '50ms', '100ms',
            '1s', '5s', '10s', '15s', '30s',
            '1m', '5m', '15m', '1h', 'AUTO'
        ]

    def set_state(self, active_interval: str, gap: float, scale: float,
                  auto_fit: bool, follow_live: bool):
        self.active_interval = active_interval
        self.min_gap_px = gap
        self.size_scale = scale
        self.auto_fit = auto_fit
        self.follow_live = follow_live
        self.update()

    def _get_interval_rects(self, w: float):
        n = len(self.intervals)
        right_panel_w = 425.0
        avail = max(300.0, w - right_panel_w - 20.0)
        btn_w = max(30.0, min(42.0, (avail - (n - 1) * 3.0) / n))
        spacing = 3.0
        start_x = 8.0
        btn_y = 5.0
        btn_h = 22.0

        rects = []
        for i in range(n):
            bx = start_x + (i * (btn_w + spacing))
            rects.append(QRectF(bx, btn_y, btn_w, btn_h))
        return rects

    def _get_right_control_rects(self, w: float):
        btn_y = 5.0
        btn_h = 22.0
        rx = w - 425.0

        rect_gm = QRectF(rx + 54, btn_y, 18, btn_h)
        rect_gp = QRectF(rx + 74, btn_y, 18, btn_h)

        sx = rx + 104
        rect_sm = QRectF(sx + 72, btn_y, 18, btn_h)
        rect_sp = QRectF(sx + 92, btn_y, 18, btn_h)

        fx = sx + 120
        rect_fit = QRectF(fx, btn_y, 36, btn_h)

        lx = fx + 42
        rect_autoscroll = QRectF(lx, btn_y, 102, btn_h)

        return {
            'rx': rx,
            'rect_gm': rect_gm,
            'rect_gp': rect_gp,
            'sx': sx,
            'rect_sm': rect_sm,
            'rect_sp': rect_sp,
            'fx': fx,
            'rect_fit': rect_fit,
            'lx': lx,
            'rect_autoscroll': rect_autoscroll
        }

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = self.width()
        h = self.height()

        # Matte Dark Dock Bar
        painter.fillRect(0, 0, w, h, QColor(14, 17, 23, 245))
        painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
        painter.drawLine(0, 0, w, 0)

        # -------------------------------------------------------------
        # 1. LEFT: Dynamic Timeframe Strip (10s, 15s, 30s included)
        # -------------------------------------------------------------
        interval_rects = self._get_interval_rects(w)
        font_btn = QFont("Consolas", 8, QFont.Bold)
        painter.setFont(font_btn)

        for i, int_name in enumerate(self.intervals):
            rect = interval_rects[i]
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
        # 2. RIGHT: GAP, SCALE, FIT, and AUTO SCROLL Controls
        # -------------------------------------------------------------
        rc = self._get_right_control_rects(w)

        # GAP Controls: GAP: 6px [-] [+]
        painter.setFont(QFont("Consolas", 8))
        painter.setPen(Theme.TEXT_SECONDARY)
        painter.drawText(int(rc['rx']), 20, f"GAP:{int(self.min_gap_px)}px")

        for r_btn, txt in [(rc['rect_gm'], "-"), (rc['rect_gp'], "+")]:
            painter.setBrush(QBrush(QColor(18, 22, 29)))
            painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
            painter.drawRoundedRect(r_btn, 2, 2)
            painter.setPen(Theme.TEXT_SECONDARY)
            painter.drawText(r_btn, Qt.AlignCenter, txt)

        # SCALE Controls: SCALE: 1.0x [-] [+]
        painter.drawText(int(rc['sx']), 20, f"SCALE:{self.size_scale:.1f}x")
        for r_btn, txt in [(rc['rect_sm'], "-"), (rc['rect_sp'], "+")]:
            painter.setBrush(QBrush(QColor(18, 22, 29)))
            painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
            painter.drawRoundedRect(r_btn, 2, 2)
            painter.setPen(Theme.TEXT_SECONDARY)
            painter.drawText(r_btn, Qt.AlignCenter, txt)

        # FIT Button
        painter.setBrush(QBrush(QColor(30, 41, 59) if self.auto_fit else QColor(18, 22, 29)))
        painter.setPen(QPen(Theme.BORDER_ACTIVE if self.auto_fit else Theme.BORDER_HAIRLINE, 1.0))
        painter.drawRoundedRect(rc['rect_fit'], 2, 2)
        painter.setPen(Theme.TEXT_PRIMARY if self.auto_fit else Theme.TEXT_MUTED)
        painter.drawText(rc['rect_fit'], Qt.AlignCenter, "FIT")

        # AUTO SCROLL Button
        r_asc = rc['rect_autoscroll']
        if self.follow_live:
            painter.setBrush(QBrush(QColor(16, 185, 129, 35)))
            painter.setPen(QPen(Theme.STATUS_LIVE, 1.0))
            painter.drawRoundedRect(r_asc, 2, 2)
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(Theme.STATUS_LIVE)
            painter.drawText(r_asc, Qt.AlignCenter, "● AUTO SCROLL")
        else:
            painter.setBrush(QBrush(QColor(18, 22, 29)))
            painter.setPen(QPen(Theme.BORDER_HAIRLINE, 1.0))
            painter.drawRoundedRect(r_asc, 2, 2)
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(Theme.TEXT_MUTED)
            painter.drawText(r_asc, Qt.AlignCenter, "▶ AUTO SCROLL")

        painter.end()

    def mousePressEvent(self, event):
        pos = event.position()
        w = self.width()

        # 1. Check Interval buttons
        interval_rects = self._get_interval_rects(w)
        for i, rect in enumerate(interval_rects):
            if rect.contains(pos):
                self.interval_selected.emit(self.intervals[i])
                event.accept()
                return

        # 2. Check Right Controls
        rc = self._get_right_control_rects(w)

        if rc['rect_gm'].contains(pos):
            self.gap_changed.emit(max(0.0, self.min_gap_px - 1.0))
            event.accept()
            return

        if rc['rect_gp'].contains(pos):
            self.gap_changed.emit(min(25.0, self.min_gap_px + 1.0))
            event.accept()
            return

        if rc['rect_sm'].contains(pos):
            self.scale_changed.emit(max(0.4, self.size_scale - 0.1))
            event.accept()
            return

        if rc['rect_sp'].contains(pos):
            self.scale_changed.emit(min(3.0, self.size_scale + 0.1))
            event.accept()
            return

        if rc['rect_fit'].contains(pos):
            self.autofit_toggled.emit()
            event.accept()
            return

        if rc['rect_autoscroll'].contains(pos):
            self.follow_live_toggled.emit()
            event.accept()
            return

        event.ignore()
