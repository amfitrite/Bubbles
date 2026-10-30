from datetime import datetime
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtCore import Qt, QRectF
from src.ui.theme import Theme
from src.util.time_utils import format_interval_desc

class BubbleTooltip(QWidget):
    """
    Precision Glass Floating Tooltip for L2 DOM Order Flow details.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.bubble_data = None
        self.hide()

    def show_bubble(self, data, screen_x: float, screen_y: float, canvas_width: int, canvas_height: int):
        self.bubble_data = data
        card_w = 224
        card_h = 142

        x = screen_x + 16
        y = screen_y - 20
        if x + card_w > canvas_width - 10:
            x = screen_x - card_w - 16
        if y + card_h > canvas_height - 10:
            y = canvas_height - card_h - 10
        if y < 10:
            y = 10

        self.setGeometry(int(x), int(y), card_w, card_h)
        self.show()
        self.update()

    def hide_tooltip(self):
        self.bubble_data = None
        self.hide()

    def paintEvent(self, event):
        if not self.bubble_data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        d = self.bubble_data
        w = self.width()
        h = self.height()

        card_rect = QRectF(0, 0, w, h)
        painter.setBrush(QBrush(Theme.HUD_SURFACE))
        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawRoundedRect(card_rect, 8, 8)

        # Time
        ts_sec = d.get('ts', 0) / 1000.0
        time_str = datetime.fromtimestamp(ts_sec).strftime('%H:%M:%S.%f')[:-3] if ts_sec > 0 else "--:--:--"

        # 1. Header (Time & Price)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(Theme.TEXT_PRIMARY)
        price_val = d.get('price', 0.0)
        painter.drawText(10, 20, f"PRICE {price_val:.2f}")

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(Theme.TEXT_MUTED)
        painter.drawText(w - 75, 20, time_str)

        painter.setPen(QPen(Theme.HUD_BORDER, 1))
        painter.drawLine(10, 27, w - 10, 27)

        # 2. Volume Details
        vol = d.get('volume', 0.0)
        buy = d.get('buy_vol', 0.0)
        sell = d.get('sell_vol', 0.0)
        delta = buy - sell
        delta_pct = (delta / vol * 100.0) if vol > 0 else 0.0

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(Theme.TEXT_SECONDARY)
        painter.drawText(10, 44, "Total Vol:")
        painter.setPen(Theme.ACCENT)
        painter.drawText(75, 44, f"{vol:.1f}")

        painter.setPen(Theme.TEXT_SECONDARY)
        painter.drawText(10, 60, "Buy / Sell:")
        painter.setPen(Theme.DELTA_BUY_MAIN)
        painter.drawText(75, 60, f"{buy:.1f}")
        painter.setPen(Theme.TEXT_MUTED)
        painter.drawText(112, 60, "/")
        painter.setPen(Theme.DELTA_SELL_MAIN)
        painter.drawText(122, 60, f"{sell:.1f}")

        # 3. Delta
        delta_color = Theme.DELTA_BUY_MAIN if delta > 0 else (Theme.DELTA_SELL_MAIN if delta < 0 else Theme.DELTA_NEUTRAL)
        painter.setPen(Theme.TEXT_SECONDARY)
        painter.drawText(10, 76, "Net Delta:")
        painter.setPen(delta_color)
        sign = "+" if delta > 0 else ""
        painter.drawText(75, 76, f"{sign}{delta:.1f} ({sign}{delta_pct:.1f}%)")

        # 4. Status / Sample & Accumulation Window
        ticks = d.get('ticks', 1)
        int_ms = d.get('interval_ms', 0)
        int_str = format_interval_desc(int_ms) if int_ms > 0 else "auto"

        sample_text = f"Accum: {int_str} · {ticks} ticks"
        if ticks < 3:
            sample_text += " (low sample)"

        painter.setPen(Theme.TEXT_MUTED)
        painter.drawText(10, 94, sample_text)

        # 5. Imbalance / Stack Flag
        imb_type = d.get('imb_type', 'none')
        has_stack = d.get('has_stack', False)
        if imb_type == 'imb_buy':
            txt = "⚡ Buy Imbalance" + (" (Stacked)" if has_stack else "")
            painter.setPen(Theme.IMB_BUY_MAIN)
            painter.drawText(10, 114, txt)
        elif imb_type == 'imb_sell':
            txt = "⚡ Sell Imbalance" + (" (Stacked)" if has_stack else "")
            painter.setPen(Theme.IMB_SELL_MAIN)
            painter.drawText(10, 114, txt)
        else:
            painter.setPen(Theme.TEXT_MUTED)
            painter.drawText(10, 114, "L2 DOM Price Level")
