## 2024-11-05 - Added Accessible Desktop Affordances
**Learning:** PySide6 custom-styled standard widgets like QSliders and QPushButtons lose default OS accessibility hints (like hand cursors or tooltip info) when heavy QSS is applied. Setting these explicitly restores standard UX.
**Action:** Always add `setCursor(Qt.PointingHandCursor)`, `setToolTip()`, and `setAccessibleName()` for standard widgets inside custom-styled containers (like `SettingsPanel`).
