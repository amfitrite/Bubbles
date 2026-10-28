import math
from PySide6.QtGui import QPainter, QPixmap, QColor, QRadialGradient, QBrush, QPen
from PySide6.QtCore import Qt, QPointF, QRectF
from src.ui.theme import Theme
from src.util.math_utils import clamp

class BubbleRenderer:
    """
    High-performance QPainter sprite cache for glass/marble styled bubbles.
    """
    def __init__(self):
        # Cache key: (radius_int, color_type, has_glow) -> QPixmap
        self.sprite_cache = {}
        self.r_min = 3
        self.r_max = 26

    def compute_radius(self, volume: float, p95_volume: float, is_macro: bool = False) -> float:
        """
        Scales volume to radius using sqrt normalization relative to p95.
        r = rMin + (rMax - rMin) * sqrt(clamp(vol / p95, 0, 1.5))
        """
        r_max = 44.0 if is_macro else self.r_max
        r_min = self.r_min
        if p95_volume <= 0:
            norm = 0.5
        else:
            norm = clamp(volume / p95_volume, 0.0, 1.5)
        
        radius = r_min + (r_max - r_min) * math.sqrt(norm)
        return radius

    def get_sprite(self, radius: int, color_type: str = "classic", has_glow: bool = False) -> QPixmap:
        """
        Retrieves a pre-rendered QPixmap from the cache, generating it if necessary.
        """
        radius = max(self.r_min, min(50, radius))
        key = (radius, color_type, has_glow)
        if key in self.sprite_cache:
            return self.sprite_cache[key]

        # Generate sprite
        # Margin for glow/specular
        padding = 8 if has_glow else 4
        size = (radius + padding) * 2
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        center = QPointF(size / 2.0, size / 2.0)

        # 1. Outer Glow (for top volume outliers)
        if has_glow:
            glow_radius = radius + 6.0
            glow_grad = QRadialGradient(center, glow_radius)
            glow_color = Theme.CLASSIC_MAIN
            glow_grad.setColorAt(0.0, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 100))
            glow_grad.setColorAt(0.6, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 35))
            glow_grad.setColorAt(1.0, Qt.transparent)
            painter.setBrush(QBrush(glow_grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, glow_radius, glow_radius)

        # 2. Base Bubble Radial Gradient (Glass Core to Edge)
        grad = QRadialGradient(center, float(radius))
        if color_type == "classic":
            core = Theme.CLASSIC_CORE
            edge = Theme.CLASSIC_EDGE
        elif color_type == "delta_buy":
            core = Theme.DELTA_BUY_CORE
            edge = Theme.DELTA_BUY_EDGE
        elif color_type == "delta_sell":
            core = Theme.DELTA_SELL_CORE
            edge = Theme.DELTA_SELL_EDGE
        else:
            core = Theme.CLASSIC_CORE
            edge = Theme.CLASSIC_EDGE

        grad.setColorAt(0.0, QColor(core.red(), core.green(), core.blue(), 230))
        grad.setColorAt(0.65, QColor(edge.red(), edge.green(), edge.blue(), 210))
        grad.setColorAt(0.95, QColor(int(edge.red() * 0.4), int(edge.green() * 0.4), int(edge.blue() * 0.4), 220))
        grad.setColorAt(1.0, QColor(10, 15, 22, 230))

        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, float(radius), float(radius))

        # 3. Specular Highlight (-35% x, -35% y offset)
        if radius >= 4:
            spec_offset_x = center.x() - (radius * 0.35)
            spec_offset_y = center.y() - (radius * 0.35)
            spec_r = radius * 0.28
            spec_center = QPointF(spec_offset_x, spec_offset_y)

            spec_grad = QRadialGradient(spec_center, spec_r)
            spec_grad.setColorAt(0.0, QColor(255, 255, 255, 140))
            spec_grad.setColorAt(0.7, QColor(255, 255, 255, 45))
            spec_grad.setColorAt(1.0, Qt.transparent)

            painter.setBrush(QBrush(spec_grad))
            painter.drawEllipse(spec_center, spec_r, spec_r)

        # 4. Subtle Inner Rim Light (bottom right)
        if radius >= 6:
            rim_offset_x = center.x() + (radius * 0.25)
            rim_offset_y = center.y() + (radius * 0.25)
            rim_r = radius * 0.45
            rim_center = QPointF(rim_offset_x, rim_offset_y)

            rim_grad = QRadialGradient(rim_center, rim_r)
            rim_grad.setColorAt(0.0, QColor(core.red(), core.green(), core.blue(), 75))
            rim_grad.setColorAt(1.0, Qt.transparent)

            painter.setBrush(QBrush(rim_grad))
            painter.drawEllipse(rim_center, rim_r, rim_r)

        painter.end()

        self.sprite_cache[key] = pixmap
        return pixmap

    def draw_bubble(self, painter: QPainter, x: float, y: float, radius: float,
                    color_type: str = "classic", has_glow: bool = False, alpha: float = 1.0):
        """
        Draws pre-rendered bubble centered at (x, y) with optional opacity.
        """
        r_int = int(round(radius))
        sprite = self.get_sprite(r_int, color_type, has_glow)

        w = sprite.width()
        h = sprite.height()
        dest_x = x - (w / 2.0)
        dest_y = y - (h / 2.0)

        if alpha < 0.99:
            painter.setOpacity(alpha)
            painter.drawPixmap(int(dest_x), int(dest_y), sprite)
            painter.setOpacity(1.0)
        else:
            painter.drawPixmap(int(dest_x), int(dest_y), sprite)
