def generate_diff():
    import json
    import difflib

    before = """        if self.is_dragging:
            delta = event.pos() - self.last_mouse_pos
            self.last_mouse_pos = event.pos()
            self.camera.pan(delta.x(), delta.y())
        event.accept()"""

    after = """        if self.is_dragging:
            delta = event.pos() - self.last_mouse_pos
            self.last_mouse_pos = event.pos()
            self.camera.pan(delta.x(), delta.y())
        else:
            self.setCursor(Qt.OpenHandCursor)
        event.accept()"""
