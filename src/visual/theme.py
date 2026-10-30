from PySide6.QtGui import QColor

class Theme:
    """
    Monochrome Matte Studio Theme.
    Clean, high-precision, non-glass, zero-distraction palette for pro traders.
    """
    # Backgrounds & Canvas
    BG_CANVAS = QColor("#0B0D11")
    BG_SURFACE = QColor("#12151B")
    BG_HEADER = QColor("#0E1117")
    BG_CARD = QColor("#161A22")

    # Hairline Borders
    BORDER_HAIRLINE = QColor("#1B202B")
    BORDER_SUBTLE = QColor("#262D3D")
    BORDER_ACTIVE = QColor("#475569")

    # Typography Colors
    TEXT_PRIMARY = QColor("#F8FAFC")
    TEXT_SECONDARY = QColor("#94A3B8")
    TEXT_MUTED = QColor("#64748B")
    TEXT_DISABLED = QColor("#334155")

    # Functional Order Flow Colors (Muted Matte)
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
    STATUS_STALE = QColor("#F59E0B")
    STATUS_OFFLINE = QColor("#64748B")
    FPS_HIGH = QColor("#22C55E")
    FPS_MID = QColor("#F59E0B")
    FPS_LOW = QColor("#EF4444")
