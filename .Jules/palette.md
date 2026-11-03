## 2024-05-15 - Accessibility for PySide6 Custom Widgets
**Learning:** When using custom-painted PySide6 widgets (like HeaderBar or SettingsPanel buttons) instead of standard QWidgets, they often lack proper mouse cursors, tooltips, and accessibility text (ARIA equivalent) by default.
**Action:** Add setCursor(Qt.PointingHandCursor), setToolTip(), and setAccessibleName() to interactive areas to maintain standard desktop UX accessibility and affordances.
