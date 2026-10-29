## 2024-05-18 - Cursor Feedback for Chart Interaction
**Learning:** Users lack visual feedback when interacting with the chart canvas via panning. In financial charting, it's standard UX to display a crosshair cursor for precision viewing and a closed hand cursor while dragging to provide immediate tactile feedback.
**Action:** Set default cursor to `Qt.CrossCursor` and toggle to `Qt.ClosedHandCursor` during mouse drag events on all interactive charting surfaces.
