## 2026-11-10 - Custom PySide6 Widget Affordance
**Learning:** PySide6 widgets lose their native interaction affordances and accessibility hints when heavily custom-styled via stylesheets, causing a degraded UX especially for screen readers and mouse interaction.
**Action:** For all heavily styled PySide6 interactive widgets, explicitly add `setCursor(Qt.PointingHandCursor)`, `setToolTip()`, and `setAccessibleName()` to maintain standard desktop UX expectations and accessibility support.
