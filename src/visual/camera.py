import time

def clamp(val, min_v, max_v):
    return max(min_v, min(max_v, val))

def lerp(a, b, t):
    return a + (b - a) * t

class Camera:
    """
    2D Viewport Camera mapping continuous Time (ms) and Price to Screen Coordinates (px).
    Features:
      - Left-click drag: Pan
      - Right-click drag: Stretch time (dx) and price (dy)
      - Wheel: Cursor-anchored Zoom
      - Auto-snap to market price on first tick or large gap
    """
    def __init__(self, viewport_width: int = 1280, viewport_height: int = 720):
        self.width = max(100, viewport_width)
        self.height = max(100, viewport_height)

        self.time_span_ms = 120_000.0   # Default 2 minutes micro view
        self.center_time_ms = time.time() * 1000.0
        self.center_price = 0.0         # Snaps on first tick
        self.price_range = 5.0          # Default price height ($5 for gold)

        self.follow_live = True
        self.auto_fit_price = True

        # Limits
        self.MIN_TIME_SPAN = 1_000.0           # 1 second
        self.MAX_TIME_SPAN = 30 * 86_400_000.0 # 30 days
        self.MIN_PRICE_RANGE = 0.05

    def set_viewport_size(self, width: int, height: int):
        self.width = max(100, width)
        self.height = max(100, height)

    @property
    def min_time(self) -> float:
        return self.center_time_ms - (self.time_span_ms / 2.0)

    @property
    def max_time(self) -> float:
        return self.center_time_ms + (self.time_span_ms / 2.0)

    @property
    def min_price(self) -> float:
        return self.center_price - (self.price_range / 2.0)

    @property
    def max_price(self) -> float:
        return self.center_price + (self.price_range / 2.0)

    def time_to_screen_x(self, t: float) -> float:
        return ((t - self.min_time) / self.time_span_ms) * self.width

    def price_to_screen_y(self, p: float) -> float:
        return ((self.max_price - p) / self.price_range) * self.height

    def screen_x_to_time(self, x: float) -> float:
        return self.min_time + (x / self.width) * self.time_span_ms

    def screen_y_to_price(self, y: float) -> float:
        return self.max_price - (y / self.height) * self.price_range

    def pan(self, dx_px: float, dy_px: float):
        dt = (-dx_px / self.width) * self.time_span_ms
        dp = (dy_px / self.height) * self.price_range
        self.center_time_ms += dt
        self.center_price += dp
        self.follow_live = False
        self.auto_fit_price = False

    def stretch(self, dx_px: float, dy_px: float):
        """Right-drag stretch: dy stretches price vertically, dx stretches time horizontally."""
        if abs(dy_px) > 0:
            price_factor = 1.0 + (dy_px / (self.height * 0.4))
            price_factor = clamp(price_factor, 0.7, 1.4)
            self.price_range = max(self.MIN_PRICE_RANGE, self.price_range * price_factor)
            self.auto_fit_price = False

        if abs(dx_px) > 0:
            time_factor = 1.0 + (dx_px / (self.width * 0.4))
            time_factor = clamp(time_factor, 0.7, 1.4)
            self.time_span_ms = clamp(self.time_span_ms * time_factor, self.MIN_TIME_SPAN, self.MAX_TIME_SPAN)
            self.follow_live = False

    def zoom(self, factor: float, anchor_x: float = None, anchor_y: float = None,
             zoom_time: bool = True, zoom_price: bool = True,
             anchor_px: float = None, anchor_py: float = None):
        """Cursor-anchored zoom (supports anchor_x/y or anchor_px/py)."""
        if anchor_x is None and anchor_px is not None:
            anchor_x = anchor_px
        if anchor_y is None and anchor_py is not None:
            anchor_y = anchor_py

        anchor_t = self.screen_x_to_time(anchor_x) if anchor_x is not None else self.center_time_ms
        anchor_p = self.screen_y_to_price(anchor_y) if anchor_y is not None else self.center_price

        if zoom_time:
            new_span = clamp(self.time_span_ms / factor, self.MIN_TIME_SPAN, self.MAX_TIME_SPAN)
            if anchor_x is not None:
                ratio_x = anchor_x / self.width
                self.center_time_ms = anchor_t + (0.5 - ratio_x) * new_span
            self.time_span_ms = new_span

        if zoom_price:
            new_range = max(self.MIN_PRICE_RANGE, self.price_range / factor)
            if anchor_y is not None:
                ratio_y = anchor_y / self.height
                self.center_price = anchor_p - (0.5 - ratio_y) * new_range
            self.price_range = new_range
            self.auto_fit_price = False

    def update_follow_live(self, latest_time_ms: float):
        if not self.follow_live or latest_time_ms <= 0:
            return
        # Position live edge at ~75% across the canvas width
        target_center = latest_time_ms - (0.25 * self.time_span_ms)
        self.center_time_ms = target_center

    def update_auto_fit(self, min_p: float, max_p: float, tick_size: float = 0.01):
        if not self.auto_fit_price or min_p is None or max_p is None or min_p > max_p:
            return

        min_range = max(10 * tick_size, self.MIN_PRICE_RANGE)
        target_range = max(min_range, (max_p - min_p) * 1.35)
        target_center = (min_p + max_p) / 2.0

        if self.center_price <= 0.0 or abs(self.center_price - target_center) > (self.price_range * 0.5) or target_range > self.price_range:
            self.price_range = target_range
            self.center_price = target_center
        else:
            self.price_range = lerp(self.price_range, target_range, 0.08)
            self.center_price = lerp(self.center_price, target_center, 0.10)

    def reset_to_recent(self, latest_time_ms: float = None, current_price: float = None):
        self.time_span_ms = 120_000.0 # 2 minutes
        if latest_time_ms and latest_time_ms > 0:
            self.center_time_ms = latest_time_ms - (0.25 * self.time_span_ms)
        if current_price and current_price > 0:
            self.center_price = current_price
            self.price_range = max(2.0, self.price_range)
        self.follow_live = True
        self.auto_fit_price = True
