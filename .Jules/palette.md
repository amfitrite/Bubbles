## 2024-05-14 - Missing Interaction Cursors on Canvas
**Learning:** The application required users to drag the canvas to pan, but there was no cursor feedback indicating that panning is possible or active.
**Action:** Always add interactive cursor feedback (like OpenHandCursor/ClosedHandCursor) to grabbable canvas elements in PySide6 to signify affordance.
