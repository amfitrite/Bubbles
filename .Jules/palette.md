## 2024-11-06 - Custom Styled PySide6 Widgets Need Explicit Accessibility
**Learning:** PySide6 custom-styled widgets (like QSlider and QPushButton) lack native pointer cursors and descriptive context by default when heavily restyled, decreasing accessibility.
**Action:** Always explicitly add `setCursor(Qt.PointingHandCursor)`, `setToolTip()`, and `setAccessibleName()` to custom interactive PySide6 widgets to maintain standard desktop UX accessibility and affordances.
