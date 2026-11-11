import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from PySide6.QtGui import QMouseEvent, Qt

app = QApplication(sys.argv)

pos = QPointF(5, 5)
global_pos = QPointF(5, 5)

# PySide6 event constructor signature can be tricky,
# but let's test event.position() type
try:
    from PySide6.QtCore import QEvent
    event = QMouseEvent(QEvent.Type.MouseMove, pos, global_pos, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    print(type(event.position()))
    print(type(event.pos()))
except Exception as e:
    print(e)
