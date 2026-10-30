from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush
from PySide6.QtCore import Qt, QRectF
from src.visual.theme import Theme

class SpriteEngine:
    """
    High-Performance Hardware Sprite Caching Engine.
    Pre-renders flat matte precision discs to QPixmap textures and blits them instantly to GPU.
    Supports 4 Core Modes:
      1. SPLIT_PIE (Quantized buy/sell wedges)
      2. DELTA (Net buy jade / net sell crimson / neutral slate)
      3. IMBALANCE (High-contrast jade/crimson with precision double-border ring)
      4. TOTAL_VOLUME (Pure titanium cold blue liquidity disc)
    """
    def __init__(self, min_radius: int = 2, max_radius: int = 50):
        self.min_radius = min_radius
        self.max_radius = max_radius
        self.cache = {} # key -> QPixmap

    def get_delta_sprite(self, radius: int, delta: float) -> QPixmap:
        """Mode 2: DELTA"""
        r = max(self.min_radius, min(self.max_radius, radius))
        if delta > 0:
            key = (r, "DELTA_BUY")
        elif delta < 0:
            key = (r, "DELTA_SELL")
        else:
            key = (r, "DELTA_NEUTRAL")

        if key in self.cache:
            return self.cache[key]

        pixmap = self._create_disc_pixmap(r)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        color = Theme.BUY_SOLID if delta > 0 else (Theme.SELL_SOLID if delta < 0 else Theme.NEUTRAL_SLATE)
        border = QColor(255, 255, 255, 35)

        painter.setBrush(QBrush(color))
        painter.setPen(QPen(border, 1.0))
        painter.drawEllipse(1, 1, r * 2, r * 2)
        painter.end()

        self.cache[key] = pixmap
        return pixmap

    def get_total_volume_sprite(self, radius: int) -> QPixmap:
        """Mode 4: TOTAL_VOLUME"""
        r = max(self.min_radius, min(self.max_radius, radius))
        key = (r, "TOTAL_VOL")

        if key in self.cache:
            return self.cache[key]

        pixmap = self._create_disc_pixmap(r)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.setBrush(QBrush(Theme.TOTAL_VOLUME))
        painter.setPen(QPen(QColor(255, 255, 255, 45), 1.0))
        painter.drawEllipse(1, 1, r * 2, r * 2)
        painter.end()

        self.cache[key] = pixmap
        return pixmap

    def get_imbalance_sprite(self, radius: int, imbalance_state: str) -> QPixmap:
        """Mode 3: IMBALANCE (Double-border ring for true 3:1+ imbalances)"""
        r = max(self.min_radius, min(self.max_radius, radius))
        key = (r, "IMB", imbalance_state)

        if key in self.cache:
            return self.cache[key]

        padding = 3 # Extra padding for double outer ring
        size = (r + padding) * 2 + 2
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center_xy = size / 2.0

        if imbalance_state == "BUY_IMBALANCE":
            # 1. Solid Jade Body
            painter.setBrush(QBrush(Theme.IMB_BUY))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(center_xy - r, center_xy - r, r * 2, r * 2))
            # 2. Precision Outer Ring
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(Theme.IMB_BUY, 1.5))
            painter.drawEllipse(QRectF(center_xy - r - 2, center_xy - r - 2, (r + 2) * 2, (r + 2) * 2))

        elif imbalance_state == "SELL_IMBALANCE":
            # 1. Solid Crimson Body
            painter.setBrush(QBrush(Theme.IMB_SELL))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(center_xy - r, center_xy - r, r * 2, r * 2))
            # 2. Precision Outer Ring
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(Theme.IMB_SELL, 1.5))
            painter.drawEllipse(QRectF(center_xy - r - 2, center_xy - r - 2, (r + 2) * 2, (r + 2) * 2))

        else:
            # Balanced: Muted Slate with low opacity
            painter.setBrush(QBrush(QColor(51, 65, 85, 140)))
            painter.setPen(QPen(QColor(255, 255, 255, 25), 1.0))
            painter.drawEllipse(QRectF(center_xy - r, center_xy - r, r * 2, r * 2))

        painter.end()
        self.cache[key] = pixmap
        return pixmap

    def get_split_pie_sprite(self, radius: int, buy_vol: float, total_vol: float) -> QPixmap:
        """Mode 1: SPLIT_PIE (Quantized 5% ratio steps)"""
        r = max(self.min_radius, min(self.max_radius, radius))
        if total_vol <= 0:
            buy_ratio = 0.5
        else:
            buy_ratio = max(0.0, min(1.0, buy_vol / total_vol))

        # Quantize ratio into 20 steps (0.00, 0.05, 0.10, ..., 1.00)
        quantized_step = int(round(buy_ratio * 20.0))
        key = (r, "PIE", quantized_step)

        if key in self.cache:
            return self.cache[key]

        pixmap = self._create_disc_pixmap(r)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(1, 1, r * 2, r * 2)

        if quantized_step == 20: # 100% Buy
            painter.setBrush(QBrush(Theme.BUY_SOLID))
            painter.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
            painter.drawEllipse(rect)
        elif quantized_step == 0: # 100% Sell
            painter.setBrush(QBrush(Theme.SELL_SOLID))
            painter.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
            painter.drawEllipse(rect)
        else:
            # Qt angles: 1/16th degree
            buy_span = int(round((quantized_step / 20.0) * 360.0 * 16.0))
            sell_span = (360 * 16) - buy_span
            start_angle = 90 * 16 # Start from 12 o'clock

            # Draw Buy Slice (Jade Green)
            painter.setBrush(QBrush(Theme.BUY_SOLID))
            painter.setPen(QPen(Theme.BG_CANVAS, 1.0))
            painter.drawPie(rect, start_angle, -buy_span)

            # Draw Sell Slice (Crimson Red)
            painter.setBrush(QBrush(Theme.SELL_SOLID))
            painter.setPen(QPen(Theme.BG_CANVAS, 1.0))
            painter.drawPie(rect, start_angle - buy_span, -sell_span)

            # Outer subtle border
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
            painter.drawEllipse(rect)

        painter.end()
        self.cache[key] = pixmap
        return pixmap

    def _create_disc_pixmap(self, r: int) -> QPixmap:
        size = (r * 2) + 2
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        return pixmap

    def blit(self, painter: QPainter, screen_x: float, screen_y: float, radius: int,
             mode: str, bubble_data):
        """
        Instant GPU Blit of cached sprite based on active mode.
        """
        r_int = max(self.min_radius, min(self.max_radius, int(round(radius))))

        if mode == "SPLIT_PIE":
            sprite = self.get_split_pie_sprite(r_int, bubble_data.buy_vol, bubble_data.volume)
        elif mode == "DELTA":
            sprite = self.get_delta_sprite(r_int, bubble_data.delta)
        elif mode == "IMBALANCE":
            sprite = self.get_imbalance_sprite(r_int, bubble_data.imbalance_state)
        else: # TOTAL_VOLUME
            sprite = self.get_total_volume_sprite(r_int)

        w = sprite.width()
        h = sprite.height()
        painter.drawPixmap(int(screen_x - w / 2.0), int(screen_y - h / 2.0), sprite)
