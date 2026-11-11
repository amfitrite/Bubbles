import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from src.ui.header_bar import HeaderBar
from src.ui.control_dock import ControlDock

app = QApplication(sys.argv)
dock = ControlDock()
h = HeaderBar()
h._fps_rects = []
dock.update()
h.update()

pos = QPointF(10.0, 10.0)

try:
    print("Testing dock contains")
    rects = dock._get_interval_rects(800.0)
    rects[0].contains(pos)

    print("Testing right dock contains")
    rc = dock._get_right_control_rects(800.0)
    rc['rect_gm'].contains(pos)

    print("Testing header contains")
    h._fps_rects = []

    print("All good!")
except Exception as e:
    print(f"Exception: {e}")
