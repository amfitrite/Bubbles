import os
import math
from PySide6.QtGui import (
    QImage, QPainter, QColor, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QPolygonF
)
from PySide6.QtCore import Qt, QPointF, QRectF
from PIL import Image

def generate_pro_icon(size: int = 512) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    scale = size / 512.0

    # -------------------------------------------------------------
    # 1. Outer Glow / Soft Ambient Shadow
    # -------------------------------------------------------------
    glow_path = QPainterPath()
    glow_path.addRoundedRect(QRectF(20 * scale, 20 * scale, 472 * scale, 472 * scale), 108 * scale, 108 * scale)
    painter.fillPath(glow_path, QColor(14, 165, 233, 25))

    # -------------------------------------------------------------
    # 2. Base Dark Obsidian Squircle
    # -------------------------------------------------------------
    bg_rect = QRectF(26 * scale, 26 * scale, 460 * scale, 460 * scale)
    bg_path = QPainterPath()
    bg_path.addRoundedRect(bg_rect, 102 * scale, 102 * scale)

    bg_grad = QLinearGradient(bg_rect.topLeft(), bg_rect.bottomRight())
    bg_grad.setColorAt(0.0, QColor("#111726"))  # Deep Navy-Slate
    bg_grad.setColorAt(0.3, QColor("#0A0D14"))  # Obsidian
    bg_grad.setColorAt(1.0, QColor("#05070B"))  # Matte Void
    painter.fillPath(bg_path, bg_grad)

    # -------------------------------------------------------------
    # 3. Outer Hairline Chamfer Border (Cyan to Muted Slate)
    # -------------------------------------------------------------
    border_grad = QLinearGradient(bg_rect.topLeft(), bg_rect.bottomRight())
    border_grad.setColorAt(0.0, QColor(56, 189, 248, 220))   # Electric Sky Cyan
    border_grad.setColorAt(0.4, QColor(30, 41, 59, 180))    # Slate Dark
    border_grad.setColorAt(1.0, QColor(15, 23, 42, 100))    # Deep Border
    painter.strokePath(bg_path, QPen(QBrush(border_grad), 3.5 * scale))

    # Inner subtle rim
    inner_rect = QRectF(30 * scale, 30 * scale, 452 * scale, 452 * scale)
    inner_path = QPainterPath()
    inner_path.addRoundedRect(inner_rect, 98 * scale, 98 * scale)
    painter.strokePath(inner_path, QPen(QColor(255, 255, 255, 12), 1.5 * scale))

    # -------------------------------------------------------------
    # 4. Subtle Background Grid & DOM Depth (Order Flow Context)
    # -------------------------------------------------------------
    painter.setClipPath(inner_path)

    # Price Rungs (Horizontal Subtle Lines)
    grid_pen = QPen(QColor(255, 255, 255, 14), 1.0 * scale, Qt.DashLine)
    painter.setPen(grid_pen)
    for y_pos in [140, 210, 280, 350]:
        painter.drawLine(QPointF(40 * scale, y_pos * scale), QPointF(472 * scale, y_pos * scale))

    # Right DOM Volume Profile Bar Silhouettes (Faint)
    dom_x = 420 * scale
    dom_bars = [(140, 40), (180, 65), (210, 80), (250, 95), (280, 75), (320, 50), (350, 30)]
    for y_pos, length in dom_bars:
        bar_rect = QRectF(dom_x - length * scale * 0.5, (y_pos - 10) * scale, length * scale * 0.5, 18 * scale)
        is_poc = (y_pos == 250)
        col = QColor(217, 119, 6, 80) if is_poc else QColor(56, 189, 248, 40)
        painter.fillRect(bar_rect, col)

    # -------------------------------------------------------------
    # 5. Glowing Trajectory Path (Price Action Wave)
    # -------------------------------------------------------------
    path_points = [
        QPointF(90 * scale, 385 * scale),
        QPointF(165 * scale, 335 * scale),
        QPointF(215 * scale, 310 * scale),
        QPointF(275 * scale, 245 * scale),
        QPointF(340 * scale, 195 * scale),
        QPointF(395 * scale, 135 * scale),
        QPointF(430 * scale, 110 * scale),
    ]

    traj_path = QPainterPath()
    traj_path.moveTo(path_points[0])
    for pt in path_points[1:]:
        traj_path.lineTo(pt)

    # Outer Trajectory Glow
    glow_pen = QPen(QColor(56, 189, 248, 60), 10.0 * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.strokePath(traj_path, glow_pen)

    # Core Trajectory Line (Cyan to Emerald Gradient)
    traj_grad = QLinearGradient(90 * scale, 385 * scale, 430 * scale, 110 * scale)
    traj_grad.setColorAt(0.0, QColor("#F43F5E"))  # Seller origin
    traj_grad.setColorAt(0.4, QColor("#38BDF8"))  # Liquidity absorption
    traj_grad.setColorAt(0.85, QColor("#10B981")) # Breakout buyer
    traj_grad.setColorAt(1.0, QColor("#34D399"))

    traj_pen = QPen(QBrush(traj_grad), 3.5 * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.strokePath(traj_path, traj_pen)

    # -------------------------------------------------------------
    # 6. Micro & Macro Liquidity Bubbles
    # -------------------------------------------------------------
    def draw_bubble(cx, cy, r, grad_stops, glow_color=None, outer_ring=None):
        cx_s = cx * scale
        cy_s = cy * scale
        r_s = r * scale

        # Ambient Glow
        if glow_color:
            glow_rad = QRadialGradient(cx_s, cy_s, r_s * 1.5)
            glow_rad.setColorAt(0.0, glow_color)
            glow_rad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(glow_rad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx_s, cy_s), r_s * 1.5, r_s * 1.5)

        # Outer Precision Ring
        if outer_ring:
            ring_col, ring_w, ring_gap = outer_ring
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(ring_col, ring_w * scale))
            painter.drawEllipse(QPointF(cx_s, cy_s), r_s + ring_gap * scale, r_s + ring_gap * scale)

        # Bubble Body
        b_grad = QRadialGradient(cx_s - r_s * 0.3, cy_s - r_s * 0.3, r_s * 1.3)
        for stop, col in grad_stops:
            b_grad.setColorAt(stop, col)

        painter.setBrush(QBrush(b_grad))
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1.2 * scale))
        painter.drawEllipse(QPointF(cx_s, cy_s), r_s, r_s)

        # Specular Crescent Highlight (Top-Left)
        spec_path = QPainterPath()
        spec_rect = QRectF(cx_s - r_s * 0.7, cy_s - r_s * 0.75, r_s * 1.4, r_s * 0.8)
        spec_path.addEllipse(spec_rect)
        painter.fillPath(spec_path, QColor(255, 255, 255, 45))

    # Node 1: Origin Seller Drop (Bottom-Left)
    draw_bubble(
        cx=95, cy=380, r=22,
        grad_stops=[(0.0, QColor("#FDA4AF")), (0.5, QColor("#F43F5E")), (1.0, QColor("#9F1239"))],
        glow_color=QColor(244, 63, 94, 60)
    )

    # Node 2: Absorption Zone (Mid-Lower)
    draw_bubble(
        cx=165, cy=335, r=44,
        grad_stops=[(0.0, QColor("#FECDD3")), (0.4, QColor("#EF4444")), (1.0, QColor("#881337"))],
        glow_color=QColor(239, 68, 68, 70),
        outer_ring=(QColor(244, 63, 94, 180), 2.0, 5.0)
    )

    # Node 3: Center Delta Bridge
    draw_bubble(
        cx=220, cy=305, r=20,
        grad_stops=[(0.0, QColor("#BAE6FD")), (0.6, QColor("#38BDF8")), (1.0, QColor("#0284C7"))],
        glow_color=QColor(56, 189, 248, 50)
    )

    # Node 4: THE MASTER BUBBLE (Center-Right POC Liquidity)
    draw_bubble(
        cx=280, cy=242, r=76,
        grad_stops=[
            (0.0, QColor("#F0F9FF")),  # Crisp Diamond Core
            (0.2, QColor("#7DD3FC")),  # Bright Ice Cyan
            (0.6, QColor("#0284C7")),  # Ocean Blue
            (0.9, QColor("#0369A1")),  # Deep Blue
            (1.0, QColor("#075985"))
        ],
        glow_color=QColor(14, 165, 233, 100),
        outer_ring=(QColor(56, 189, 248, 240), 2.5, 7.0)
    )

    # Subtle inner concentric ring in master bubble (Depth)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(255, 255, 255, 50), 1.0 * scale, Qt.DotLine))
    painter.drawEllipse(QPointF(280 * scale, 242 * scale), 48 * scale, 48 * scale)

    # Node 5: Delta Shift
    draw_bubble(
        cx=342, cy=195, r=26,
        grad_stops=[(0.0, QColor("#D1FAE5")), (0.5, QColor("#34D399")), (1.0, QColor("#059669"))],
        glow_color=QColor(16, 185, 129, 60)
    )

    # Node 6: Breakout Aggressive Buyer Bubble (Top-Right)
    draw_bubble(
        cx=395, cy=135, r=52,
        grad_stops=[
            (0.0, QColor("#ECFDF5")),
            (0.25, QColor("#6EE7B7")),
            (0.65, QColor("#10B981")),
            (1.0, QColor("#065F46"))
        ],
        glow_color=QColor(16, 185, 129, 90),
        outer_ring=(QColor(52, 211, 153, 230), 2.2, 6.0)
    )

    # Tip: Leading Market Action Vector
    draw_bubble(
        cx=430, cy=110, r=14,
        grad_stops=[(0.0, QColor("#FFFFFF")), (0.6, QColor("#34D399")), (1.0, QColor("#059669"))],
        glow_color=QColor(52, 211, 153, 120)
    )

    # -------------------------------------------------------------
    # 7. Dynamic Trajectory Vertices (Gleaming Nodes)
    # -------------------------------------------------------------
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    painter.setPen(Qt.NoPen)
    for pt in [path_points[0], path_points[1], path_points[3], path_points[5]]:
        painter.drawEllipse(pt, 3.0 * scale, 3.0 * scale)

    painter.end()
    return image

def main():
    os.makedirs("assets", exist_ok=True)
    print("Rendering Ultra High-Resolution 512x512 Master Vector Icon...")
    qimg = generate_pro_icon(512)

    # Save Master 512x512 PNG
    master_png = "assets/icon_512.png"
    qimg.save(master_png, "PNG")

    # Load into PIL for pristine Lanczos downsampling to all standard icon sizes
    pil_master = Image.open(master_png)

    # 1. Save standard 256x256 icon.png
    icon_256 = pil_master.resize((256, 256), Image.Resampling.LANCZOS)
    icon_256.save("assets/icon.png", "PNG", optimize=True)
    print("Saved: assets/icon.png (256x256)")

    # 2. Save multi-resolution Windows ICO (16, 24, 32, 48, 64, 128, 256)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    pil_master.save(
        "assets/icon.ico",
        format="ICO",
        sizes=ico_sizes
    )
    print("Saved: assets/icon.ico with multi-resolution layers:", ico_sizes)

    # Clean up intermediate 512 master if desired or keep as high-res asset
    if os.path.exists(master_png):
        os.remove(master_png)
    print("Icon generation completed successfully!")

if __name__ == "__main__":
    main()
