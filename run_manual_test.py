import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QMouseEvent, Qt
from PySide6.QtCore import QPointF, QEvent
from src.ui.header_bar import HeaderBar
from src.ui.control_dock import ControlDock

app = QApplication(sys.argv)
h = HeaderBar()
h._fps_rects = []
dock = ControlDock()

h.resize(800, 38)
dock.resize(800, 32)
h.update()
dock.update()

pos = QPointF(5, 5)
global_pos = QPointF(5, 5)

event = QMouseEvent(QEvent.Type.MouseMove, pos, global_pos, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)

try:
    h.mouseMoveEvent(event)
    print("Header mouse move successful")

    dock.mouseMoveEvent(event)
    print("Dock mouse move successful")
except Exception as e:
    print(f"Failed with {e}")
