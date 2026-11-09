## 2024-03-20 - PySide6 Custom Widget Affordances
**Learning:** Applying custom stylesheets (like background colors or borders) to PySide6 `QPushButton` instances strips away standard desktop UX affordances, such as the pointer cursor on hover and accessible interaction.
**Action:** When restyling buttons in Qt/PySide6, always explicitly re-add `setCursor(Qt.PointingHandCursor)`, `setToolTip()`, and `setAccessibleName()` to maintain an accessible and intuitive desktop experience.
