## 2024-11-01 - Fix PySide6 Custom Widget Accessibility and Affordances
**Learning:** Custom styled widgets in PySide6 lose their default hover cursor affordances, requiring explicit setting of pointers, tooltips, and accessibility metadata.
**Action:** When adding or modifying PySide6 widgets with custom stylesheets, explicitly add `setCursor(Qt.PointingHandCursor)`, `setToolTip()`, and `setAccessibleName()` to maintain standard desktop UX accessibility and affordances.
