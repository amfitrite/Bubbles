import time
from datetime import datetime
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtCore import Qt, QRectF
from src.algo.models import AlgoBubble
from src.visual.theme import Theme

class MonospaceTooltip(QWidget):
    """
    Dark Minimalist Monospace Tooltip Card.
    Displays exact uncorrupted mathematical order flow data.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.data: AlgoBubble = None
        self.hide()

    def show_bubble(self, algo_bubble: AlgoBubble, screen_x: float, screen_y: float,
                    canvas_w: int, canvas_h: int):
        self.data = algo_bubble
        card_w = 230
        card_h = 138

        # Smart placement to keep within canvas boundaries
        pos_x = screen_x + 16
        pos_y = screen_y + 16

        if pos_x + card_w > canvas_w - 10:
            pos_x = screen_x - card_w - 16
        if pos_y + card_h > canvas_h - 10:
            pos_y = screen_y - card_h - 16

        self.setGeometry(int(pos_x), int(pos_y), card_w, card_h)
        self.show()
        self.raise_()
        self.update()

    def hide_tooltip(self):
        self.data = None
        self.hide()

    def paintEvent(self, event):
        if not self.data:
            return

        b = self.data
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = self.width()
        h = self.height()

        # Matte Dark Card Body
        rect = QRectF(0.5, 0.5, w - 1, h - 1)
        painter.setBrush(QBrush(Theme.BG_CARD))
        painter.setPen(QPen(Theme.BORDER_SUBTLE, 1.0))
        painter.drawRoundedRect(rect, 4, 4)

        # Top Accent Line
        accent_color = Theme.IMB_BUY if b.delta > 0 else (Theme.IMB_SELL if b.delta < 0 else Theme.TEXT_MUTED)
        painter.setPen(QPen(accent_color, 2.0))
        painter.drawLine(1, 1, w - 2, 1)

        # Monospace Font
        font_mono = QFont("Consolas", 8)
        font_bold = QFont("Consolas", 8, QFont.Bold)
        painter.setFont(font_mono)

        dt_str = datetime.fromtimestamp(b.ts / 1000.0).strftime('%H:%M:%S') + f".{int(b.ts % 1000):03d}"

        rows = [
            ("PRICE (VWAP)", f"{b.price:.2f}"),
            ("TOTAL VOL", f"{b.volume:.2f}"),
            ("BUY / SELL", f"{b.buy_vol:.1f} / {b.sell_vol:.1f}"),
            ("NET DELTA", f"{b.delta:+.2f} ({b.delta_ratio * 100:+.0f}%)"),
            ("IMBALANCE", f"{b.imbalance_state} ({b.imbalance_ratio:.1f}x)" if b.imbalance_state != "BALANCED" else "BALANCED"),
            ("TIME", dt_str),
            ("TICKS FUSED", f"{b.tick_count} ticks")
        ]

        y_offset = 18
        for label, val in rows:
            painter.setFont(font_mono)
            painter.setPen(Theme.TEXT_MUTED)
            painter.drawText(10, y_offset, label)

            painter.setFont(font_bold)
            if label == "NET DELTA":
                painter.setPen(Theme.BUY_SOLID if b.delta > 0 else (Theme.SELL_SOLID if b.delta < 0 else Theme.TEXT_PRIMARY))
            elif label == "IMBALANCE" and b.imbalance_state != "BALANCED":
                painter.setPen(Theme.IMB_BUY if "BUY" in b.imbalance_state else Theme.IMB_SELL)
            else:
                painter.setPen(Theme.TEXT_PRIMARY)

            painter.drawText(115, y_offset, val)
            y_offset += 16

        painter.end()
