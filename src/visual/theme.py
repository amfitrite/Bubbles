from PySide6.QtGui import QColor

class Theme:
    """
    Monochrome Matte Studio Theme.
    Clean, high-precision, non-glass, zero-distraction palette for pro traders.
    """
    # Backgrounds & Canvas
    BG_CANVAS = QColor("#090B0E")
    BG_DOM = QColor("#0C0F14")
    BG_HEADER = QColor("#0E1117")
    BG_DOCK = QColor("#0C0F14")
    BG_CARD = QColor("#141822")

    # Grid & Structural Reference Lines
    GRID_LINE = QColor("#151922")
    GRID_TEXT = QColor("#475569")
    TRAJECTORY_LINE = QColor("#475569") # Price path line
    TRAJECTORY_HEAD = QColor("#38BDF8")
    LINE_HIGH = QColor("#991B1B")       # Session High (Dashed)
    LINE_LOW = QColor("#166534")        # Session Low (Dashed)
    LINE_VWAP = QColor("#0284C7")       # Session VWAP (Dotted)
    LINE_POC = QColor("#D97706")        # Point of Control (Dashed)

    # Volume Profile Ladder (Right Column)
    VP_BAR = QColor(30, 41, 59, 180)    # Volume histogram bar
    VP_BAR_POC = QColor(217, 119, 6, 200)# POC Volume bar
    PRICE_BADGE_BG = QColor("#2563EB")  # Market Price Pill
    PRICE_BADGE_TEXT = QColor("#FFFFFF")

    # Hairline Borders
    BORDER_HAIRLINE = QColor("#1B202B")
    BORDER_SUBTLE = QColor("#262D3D")
    BORDER_ACTIVE = QColor("#475569")

    # Typography
    TEXT_PRIMARY = QColor("#F8FAFC")
    TEXT_SECONDARY = QColor("#94A3B8")
    TEXT_MUTED = QColor("#64748B")

    # 4-Mode Functional Colors
    BUY_SOLID = QColor("#22C55E")     # Muted Jade Green
    SELL_SOLID = QColor("#EF4444")    # Muted Crimson
    NEUTRAL_SLATE = QColor("#475569") # Titanium Slate
    TOTAL_VOLUME = QColor("#38BDF8")  # Cold Titanium Blue

    # Imbalance Colors
    IMB_BUY = QColor("#10B981")       # High-contrast Jade
    IMB_SELL = QColor("#F43F5E")      # High-contrast Ruby
    IMB_RING = QColor("#FFFFFF")      # Precision hairline ring

    # Telemetry
    STATUS_LIVE = QColor("#22C55E")
    STATUS_OFFLINE = QColor("#64748B")
    FPS_HIGH = QColor("#22C55E")
    FPS_MID = QColor("#F59E0B")
    FPS_LOW = QColor("#EF4444")
