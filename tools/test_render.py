import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import QSize

from src.algo.tick_store import TickStore
from src.algo.models import TICK_DTYPE
from src.ui.main_window import MainWindow

def test_visual_rendering():
    app = QApplication.instance() or QApplication(sys.argv)
    
    store = TickStore(max_ticks=10000)
    
    # Generate 500 synthetic realistic ticks around 4000.0
    now_ms = int(time.time() * 1000)
    ticks = []
    price = 4000.0
    for i in range(500):
        t = now_ms - (500 - i) * 100
        delta = np.random.choice([-0.1, -0.05, 0.0, 0.05, 0.1])
        price = round(price + delta, 2)
        is_buy = np.random.random() > 0.48
        vol = round(float(np.random.choice([1.0, 2.0, 5.0, 10.0, 25.0])), 2)
        flags = 32 if is_buy else 64
        side = 1 if is_buy else -1
        ticks.append((t, price, price + 0.1, price if is_buy else price, vol, flags, side))
    
    tick_arr = np.array(ticks, dtype=TICK_DTYPE)
    store.add_ticks_batch(tick_arr)
    
    win = MainWindow(store)
    win.resize(1366, 768)
    win.show()
    
    # Process events and force re-layout
    app.processEvents()
    
    canvas = win.canvas
    canvas.camera.set_viewport_size(1366, 700)
    canvas._rebuild_scene(now_ms)
    
    print(f"Canvas rebuild scene completed.")
    print(f"Current layout bubbles count: {len(canvas.current_layout.bubbles) if canvas.current_layout else 0}")
    print(f"Trajectory points count: {len(canvas.current_layout.trajectory_screen_points) if canvas.current_layout else 0}")
    print(f"Macro POC: {canvas.current_layout.snapshot.macro.poc_price if canvas.current_layout else None}")
    
    # Test rendering in all 4 modes
    for mode in ["SPLIT_PIE", "DELTA", "IMBALANCE", "TOTAL_VOLUME"]:
        canvas.set_mode(mode)
        app.processEvents()
        img = canvas.grab().toImage()
        print(f"Rendered mode {mode}: Image size {img.width()}x{img.height()}, not null: {not img.isNull()}")
        assert not img.isNull(), f"Rendered image for {mode} was null!"
        
    # Save a verification snapshot of SPLIT_PIE and TOTAL_VOLUME
    canvas.set_mode("TOTAL_VOLUME")
    app.processEvents()
    canvas.grab().save("test_render_total_volume.png")
    
    canvas.set_mode("SPLIT_PIE")
    app.processEvents()
    canvas.grab().save("test_render_split_pie.png")
    
    canvas.set_mode("DELTA")
    app.processEvents()
    canvas.grab().save("test_render_delta.png")

    canvas.set_mode("IMBALANCE")
    app.processEvents()
    canvas.grab().save("test_render_imbalance.png")

    win.close()
    print("ALL VISUAL RENDERING TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_visual_rendering()
