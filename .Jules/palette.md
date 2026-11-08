## 2024-05-18 - PySide6 Widget Affordances
**Learning:** PySide6 custom-styled widgets (like QSlider, QPushButton) lose their standard desktop UX affordances when heavy stylesheets are applied. This causes them to lack pointer cursors, making them feel less interactive, and they may also lack proper screen reader accessibility contexts.
**Action:** When creating custom-styled widgets in PySide6, always explicitly add `setCursor(Qt.PointingHandCursor)`, `setToolTip()`, and `setAccessibleName()` to maintain standard desktop UX accessibility and affordances.
