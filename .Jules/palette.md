## 2024-05-24 - Restoring Desktop Affordances
**Learning:** Custom PySide6 stylesheets often strip native desktop affordances like pointing hand cursors and accessible tooltips, making interactive controls feel "dead" and inaccessible.
**Action:** When creating custom styled widgets in PySide6, explicitly re-add `setCursor(Qt.PointingHandCursor)`, `setToolTip()`, and `setAccessibleName()` to all interactive elements to maintain desktop UX expectations.
