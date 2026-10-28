"""
Design tokens and color palette for Bubbles Terminal.
Strictly following README specifications.
"""
from PySide6.QtGui import QColor

class Theme:
    # Canvas & Background
    BACKGROUND = QColor("#06080C")
    BACKGROUND_HEX = "#06080C"
    
    # Surface & Overlay HUD
    HUD_SURFACE = QColor(13, 18, 26, 220)  # #0D121A @ 86%
    HUD_BORDER = QColor(255, 255, 255, 18)  # rgba(255,255,255,0.07)
    
    # Typography colors
    TEXT_PRIMARY = QColor("#E8EEF6")
    TEXT_SECONDARY = QColor("#94A3B8")
    TEXT_MUTED = QColor("#5B6B7F")
    ACCENT = QColor("#22D3EE")
    
    # Status indicators
    STATUS_LIVE = QColor("#10B981")
    STATUS_STALE = QColor("#F59E0B")
    STATUS_DISCONNECTED = QColor("#EF4444")

    # Mode 1: Classic
    CLASSIC_CORE = QColor("#A5F3FC")
    CLASSIC_EDGE = QColor("#0891B2")
    CLASSIC_MAIN = QColor("#22D3EE")

    # Mode 2: Delta
    DELTA_BUY_CORE = QColor("#A7F3D0")
    DELTA_BUY_EDGE = QColor("#059669")
    DELTA_BUY_MAIN = QColor("#34D399")

    DELTA_SELL_CORE = QColor("#FECACA")
    DELTA_SELL_EDGE = QColor("#B91C1C")
    DELTA_SELL_MAIN = QColor("#F87171")

    DELTA_NEUTRAL = QColor("#64748B")

    # Mode 3: Imbalance
    IMB_BUY_CORE = QColor("#BAE6FD")
    IMB_BUY_EDGE = QColor("#0284C7")
    IMB_BUY_MAIN = QColor("#38BDF8")

    IMB_SELL_CORE = QColor("#FDE68A")
    IMB_SELL_EDGE = QColor("#B45309")
    IMB_SELL_MAIN = QColor("#FBBF24")

    BALANCED = QColor("#1E293B")
