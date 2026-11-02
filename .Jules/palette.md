## 2026-11-02 - Desktop UX Accessibility for Custom PySide6 Widgets
**Learning:** In PySide6 desktop applications, custom-styled buttons (like QPushButtons in settings panels) often lack the expected standard desktop UX accessibility and affordances, such as a pointing hand cursor, accessible names for screen readers, and tooltips.
**Action:** When creating custom-styled interactive widgets (like buttons), explicitly add `setCursor(Qt.PointingHandCursor)`, `setAccessibleName()`, and `setToolTip()` to improve both visual feedback and screen reader accessibility.
