import math
from PySide6.QtGui import QPainter, QPixmap, QColor, QRadialGradient, QBrush, QPen
from PySide6.QtCore import Qt, QPointF, QRectF
from src.ui.theme import Theme
from src.util.math_utils import clamp

class BubbleRenderer:
    """
    High-performance QPainter renderer for glass/marble styled bubbles.
    Supports 3 Core Modes: Split Pie, Net Delta, and Total Volume.
    Implements Visual Spacing and Cell-Aware Radius Clamping.
    """
    def __init__(self):
        # Cache key: (radius_int, color_type, has_glow) -> QPixmap
        self.sprite_cache = {}
        self.r_min = 3.0
        self.r_max = 24.0

    def compute_radius(self, volume: float, p95_volume: float, is_macro: bool = False,
                       size_scale: float = 1.0, max_cell_radius: float = None) -> float:
        """
        Visual Spacing Engine:
        - Volume <= 1.0 (baseline single tick) is strictly mapped to compact r_min.
        - Accumulated volumes grow smoothly with square-root curve.
        - Capped by max_cell_radius to guarantee visual spacing between adjacent cells.
        """
        r_min = max(2.0, self.r_min * size_scale)
        r_max = (38.0 if is_macro else self.r_max) * size_scale

        if volume <= 1.0:
            rad = r_min
        else:
            eff_p95 = max(5.0, p95_volume)
            norm = clamp((volume - 1.0) / (eff_p95 - 1.0), 0.0, 1.5)
            rad = r_min + (r_max - r_min) * math.sqrt(norm)

        # Apply cell-aware clamping so adjacent bubbles have comfortable visual breathing room
        if max_cell_radius is not None and max_cell_radius > 2.0:
            rad = min(rad, max_cell_radius)

        return max(2.0, rad)

    def _get_palette(self, color_type: str):
        if color_type in ("classic", "total_volume"):
            return Theme.CLASSIC_CORE, Theme.CLASSIC_EDGE, Theme.CLASSIC_MAIN
        elif color_type == "delta_buy":
            return Theme.DELTA_BUY_CORE, Theme.DELTA_BUY_EDGE, Theme.DELTA_BUY_MAIN
        elif color_type == "delta_sell":
            return Theme.DELTA_SELL_CORE, Theme.DELTA_SELL_EDGE, Theme.DELTA_SELL_MAIN
        elif color_type == "delta_neutral":
            return Theme.DELTA_NEUTRAL, Theme.DELTA_NEUTRAL, Theme.DELTA_NEUTRAL
        elif color_type == "imb_buy":
            return Theme.IMB_BUY_CORE, Theme.IMB_BUY_EDGE, Theme.IMB_BUY_MAIN
        elif color_type == "imb_sell":
            return Theme.IMB_SELL_CORE, Theme.IMB_SELL_EDGE, Theme.IMB_SELL_MAIN
        elif color_type == "balanced":
            return Theme.BALANCED, Theme.BALANCED, Theme.BALANCED
        else:
            return Theme.CLASSIC_CORE, Theme.CLASSIC_EDGE, Theme.CLASSIC_MAIN

    def get_sprite(self, radius: int, color_type: str = "classic", has_glow: bool = False) -> QPixmap:
        radius = max(2, min(50, radius))
        key = (radius, color_type, has_glow)
        if key in self.sprite_cache:
            return self.sprite_cache[key]

        core, edge, main = self._get_palette(color_type)

        padding = 10 if has_glow else 4
        size = (radius + padding) * 2
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        center = QPointF(size / 2.0, size / 2.0)

        # 1. Outer Glow
        if has_glow:
            glow_radius = radius + 8.0
            glow_grad = QRadialGradient(center, glow_radius)
            glow_grad.setColorAt(0.0, QColor(main.red(), main.green(), main.blue(), 130))
            glow_grad.setColorAt(0.6, QColor(main.red(), main.green(), main.blue(), 45))
            glow_grad.setColorAt(1.0, Qt.transparent)
            painter.setBrush(QBrush(glow_grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, glow_radius, glow_radius)

        # 2. Bubble Body Radial Gradient
        grad = QRadialGradient(center, float(radius))
        if color_type == "balanced":
            grad.setColorAt(0.0, QColor(core.red(), core.green(), core.blue(), 100))
            grad.setColorAt(0.9, QColor(edge.red(), edge.green(), edge.blue(), 80))
            grad.setColorAt(1.0, QColor(10, 15, 22, 100))
        else:
            grad.setColorAt(0.0, QColor(core.red(), core.green(), core.blue(), 235))
            grad.setColorAt(0.68, QColor(edge.red(), edge.green(), edge.blue(), 215))
            grad.setColorAt(0.95, QColor(int(edge.red() * 0.4), int(edge.green() * 0.4), int(edge.blue() * 0.4), 220))
            grad.setColorAt(1.0, QColor(10, 15, 22, 230))

        painter.setBrush(QBrush(grad))
        # 1px dark rim to separate bubbles
        painter.setPen(QPen(QColor(10, 15, 22, 190), 1))
        painter.drawEllipse(center, float(radius), float(radius))

        # 3. Specular Highlight (-35% offset)
        if radius >= 4 and color_type != "balanced":
            spec_offset_x = center.x() - (radius * 0.35)
            spec_offset_y = center.y() - (radius * 0.35)
            spec_r = radius * 0.28
            spec_center = QPointF(spec_offset_x, spec_offset_y)

            spec_grad = QRadialGradient(spec_center, spec_r)
            spec_grad.setColorAt(0.0, QColor(255, 255, 255, 140))
            spec_grad.setColorAt(0.7, QColor(255, 255, 255, 45))
            spec_grad.setColorAt(1.0, Qt.transparent)

            painter.setBrush(QBrush(spec_grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(spec_center, spec_r, spec_r)

        # 4. Subtle Inner Rim Light (bottom right)
        if radius >= 6 and color_type != "balanced":
            rim_offset_x = center.x() + (radius * 0.25)
            rim_offset_y = center.y() + (radius * 0.25)
            rim_r = radius * 0.45
            rim_center = QPointF(rim_offset_x, rim_offset_y)

            rim_grad = QRadialGradient(rim_center, rim_r)
            rim_grad.setColorAt(0.0, QColor(core.red(), core.green(), core.blue(), 75))
            rim_grad.setColorAt(1.0, Qt.transparent)

            painter.setBrush(QBrush(rim_grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rim_center, rim_r, rim_r)

        painter.end()

        self.sprite_cache[key] = pixmap
        return pixmap

    def draw_bubble(self, painter: QPainter, x: float, y: float, radius: float,
                    mode: str = "TOTAL_VOLUME", color_type: str = "classic",
                    buy_vol: float = 0.0, sell_vol: float = 0.0,
                    has_glow: bool = False, alpha: float = 1.0):
        """
        Draws a bubble according to the 3 modes:
        1. SPLIT_PIE: 2 pie slices (Green Buy vs Red Sell)
        2. NET_DELTA: Solid bubble colored by net aggressor delta (Green/Red/Gray)
        3. TOTAL_VOLUME: Solid classic Cyan (#22D3EE) bubble
        """
        r_int = int(round(radius))
        if r_int < 2:
            r_int = 2

        if alpha < 0.99:
            painter.setOpacity(alpha)

        if mode == "SPLIT_PIE":
            self._draw_split_pie(painter, x, y, r_int, buy_vol, sell_vol, has_glow)
        elif mode == "TOTAL_VOLUME":
            # In TOTAL_VOLUME mode, bubble MUST be pure classic Cyan (#22D3EE)!
            sprite = self.get_sprite(r_int, "classic", has_glow)
            w = sprite.width()
            h = sprite.height()
            painter.drawPixmap(int(x - w / 2.0), int(y - h / 2.0), sprite)
        else:
            # NET_DELTA mode uses delta_buy, delta_sell, delta_neutral
            sprite = self.get_sprite(r_int, color_type, has_glow)
            w = sprite.width()
            h = sprite.height()
            painter.drawPixmap(int(x - w / 2.0), int(y - h / 2.0), sprite)

        if alpha < 0.99:
            painter.setOpacity(1.0)

    def _draw_split_pie(self, painter: QPainter, x: float, y: float, radius: int,
                        buy_vol: float, sell_vol: float, has_glow: bool = False):
        total_vol = buy_vol + sell_vol
        rect = QRectF(x - radius, y - radius, radius * 2, radius * 2)

        # Glow for high volume in split pie
        if has_glow:
            glow_grad = QRadialGradient(QPointF(x, y), radius + 8.0)
            glow_color = Theme.ACCENT
            glow_grad.setColorAt(0.0, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 110))
            glow_grad.setColorAt(1.0, Qt.transparent)
            painter.setBrush(QBrush(glow_grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x, y), radius + 8.0, radius + 8.0)

        # 100% Buy
        if sell_vol <= 0 or total_vol <= 0:
            sprite = self.get_sprite(radius, "delta_buy", False)
            dest_x = x - (sprite.width() / 2.0)
            dest_y = y - (sprite.height() / 2.0)
            painter.drawPixmap(int(dest_x), int(dest_y), sprite)
            return

        # 100% Sell
        if buy_vol <= 0:
            sprite = self.get_sprite(radius, "delta_sell", False)
            dest_x = x - (sprite.width() / 2.0)
            dest_y = y - (sprite.height() / 2.0)
            painter.drawPixmap(int(dest_x), int(dest_y), sprite)
            return

        # Split Pie calculation (Qt uses 1/16th degree)
        buy_ratio = buy_vol / total_vol
        buy_span = int(round(buy_ratio * 360.0 * 16.0))
        sell_span = (360 * 16) - buy_span

        # Start from 12 o'clock (90 deg = 90 * 16)
        start_angle = 90 * 16

        # Draw Buy Pie Slice (Green)
        buy_brush = QBrush(QColor("#10B981"))
        painter.setBrush(buy_brush)
        painter.setPen(QPen(QColor(10, 15, 22, 210), 1))
        painter.drawPie(rect, start_angle, -buy_span)

        # Draw Sell Pie Slice (Red)
        sell_brush = QBrush(QColor("#EF4444"))
        painter.setBrush(sell_brush)
        painter.drawPie(rect, start_angle - buy_span, -sell_span)

        # Glass Specular Highlight on top of Pie
        if radius >= 4:
            spec_cx = x - (radius * 0.35)
            spec_cy = y - (radius * 0.35)
            spec_r = radius * 0.28
            spec_center = QPointF(spec_cx, spec_cy)

            spec_grad = QRadialGradient(spec_center, spec_r)
            spec_grad.setColorAt(0.0, QColor(255, 255, 255, 160))
            spec_grad.setColorAt(0.7, QColor(255, 255, 255, 45))
            spec_grad.setColorAt(1.0, Qt.transparent)

            painter.setBrush(QBrush(spec_grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(spec_center, spec_r, spec_r)
