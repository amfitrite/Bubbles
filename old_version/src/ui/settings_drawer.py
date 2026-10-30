from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QRadioButton, QButtonGroup, QFrame, QScrollArea, QCheckBox
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtCore import Qt, Signal, QRectF
from src.ui.theme import Theme
from src.util.time_utils import INTERVAL_OPTIONS

class SettingsDrawer(QWidget):
    """
    Sleek Slide-out Settings Drawer for Bubbles Terminal.
    Controls Display Modes (Split Pie, Net Delta, Total Volume), Accumulation Interval,
    Bubble Size Scale, Visual Spacing, and Camera navigation.
    """
    mode_changed = Signal(str)
    interval_changed = Signal(str)
    size_scale_changed = Signal(float)
    spacing_padding_changed = Signal(float)
    min_volume_changed = Signal(float)
    follow_live_toggled = Signal(bool)
    auto_fit_toggled = Signal(bool)
    reset_camera_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(330)
        self.setStyleSheet("""
            QWidget {
                background-color: #0B0F17;
                color: #E8EEF6;
                font-family: 'Segoe UI', Inter, sans-serif;
            }
            QLabel {
                font-size: 11px;
                color: #94A3B8;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QPushButton {
                background-color: #161F2E;
                color: #E8EEF6;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1E2B3E;
                border-color: #22D3EE;
            }
            QPushButton:checked {
                background-color: rgba(34, 211, 238, 0.2);
                border: 1px solid #22D3EE;
                color: #22D3EE;
                font-weight: 700;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #1E293B;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #22D3EE;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #E8EEF6;
                border: 1px solid #22D3EE;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
            QCheckBox {
                font-size: 12px;
                color: #E8EEF6;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid rgba(255,255,255,0.2);
                background: #161F2E;
            }
            QCheckBox::indicator:checked {
                background: #22D3EE;
                border-color: #22D3EE;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # 1. Header with Close Button
        header_layout = QHBoxLayout()
        title_label = QLabel("SETTINGS & CONTROLS")
        title_label.setStyleSheet("font-size: 13px; font-weight: 800; color: #22D3EE; letter-spacing: 1px;")
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.clicked.connect(self.hide)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close)
        main_layout.addLayout(header_layout)

        # Scroll Area for clean mobile/responsive fit
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # 2. SECTION: DISPLAY MODE (3 Options)
        content_layout.addWidget(QLabel("Bubble Display Mode"))
        mode_btn_layout = QVBoxLayout()
        mode_btn_layout.setSpacing(6)

        self.btn_split_pie = QPushButton("● SPLIT PIE  (Dual Buy/Sell Slice)")
        self.btn_split_pie.setCheckable(True)
        self.btn_split_pie.clicked.connect(lambda: self.mode_changed.emit("SPLIT_PIE"))

        self.btn_net_delta = QPushButton("● NET DELTA  (Dominant Aggressor)")
        self.btn_net_delta.setCheckable(True)
        self.btn_net_delta.clicked.connect(lambda: self.mode_changed.emit("NET_DELTA"))

        self.btn_total_vol = QPushButton("● TOTAL VOLUME  (Classic Cyan)")
        self.btn_total_vol.setCheckable(True)
        self.btn_total_vol.clicked.connect(lambda: self.mode_changed.emit("TOTAL_VOLUME"))

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.btn_split_pie)
        self.mode_group.addButton(self.btn_net_delta)
        self.mode_group.addButton(self.btn_total_vol)
        self.btn_total_vol.setChecked(True)

        mode_btn_layout.addWidget(self.btn_split_pie)
        mode_btn_layout.addWidget(self.btn_net_delta)
        mode_btn_layout.addWidget(self.btn_total_vol)
        content_layout.addLayout(mode_btn_layout)

        # Divider
        self._add_divider(content_layout)

        # 3. SECTION: ACCUMULATION INTERVAL
        content_layout.addWidget(QLabel("Accumulation Interval (L2 DOM)"))
        int_grid = QVBoxLayout()
        int_grid.setSpacing(6)

        self.int_buttons = {}
        row1 = QHBoxLayout()
        for name in ["AUTO", "1ms", "5ms", "10ms"]:
            b = QPushButton(name)
            b.setCheckable(True)
            b.clicked.connect(lambda _, n=name: self.interval_changed.emit(n))
            self.int_buttons[name] = b
            row1.addWidget(b)
        int_grid.addLayout(row1)

        row2 = QHBoxLayout()
        for name in ["50ms", "100ms", "250ms", "500ms"]:
            b = QPushButton(name)
            b.setCheckable(True)
            b.clicked.connect(lambda _, n=name: self.interval_changed.emit(n))
            self.int_buttons[name] = b
            row2.addWidget(b)
        int_grid.addLayout(row2)

        row3 = QHBoxLayout()
        for name in ["1s", "5s", "15s", "30s"]:
            b = QPushButton(name)
            b.setCheckable(True)
            b.clicked.connect(lambda _, n=name: self.interval_changed.emit(n))
            self.int_buttons[name] = b
            row3.addWidget(b)
        int_grid.addLayout(row3)

        row4 = QHBoxLayout()
        for name in ["1m", "5m", "15m", "1h"]:
            b = QPushButton(name)
            b.setCheckable(True)
            b.clicked.connect(lambda _, n=name: self.interval_changed.emit(n))
            self.int_buttons[name] = b
            row4.addWidget(b)
        int_grid.addLayout(row4)

        self.int_buttons["AUTO"].setChecked(True)
        content_layout.addLayout(int_grid)

        # Divider
        self._add_divider(content_layout)

        # 4. SECTION: VISUAL SPACING & SCALING
        content_layout.addWidget(QLabel("Visual Spacing & Sizing"))

        # Size Scale Slider
        self.lbl_scale = QLabel("Bubble Size Scale: 100%")
        self.lbl_scale.setStyleSheet("color: #E8EEF6; font-size: 11px;")
        self.slider_scale = QSlider(Qt.Horizontal)
        self.slider_scale.setRange(40, 200) # 40% to 200%
        self.slider_scale.setValue(100)
        self.slider_scale.valueChanged.connect(self._on_scale_slider)
        content_layout.addWidget(self.lbl_scale)
        content_layout.addWidget(self.slider_scale)

        # Spacing Padding Slider
        self.lbl_spacing = QLabel("Cell Spacing Padding: 3 px")
        self.lbl_spacing.setStyleSheet("color: #E8EEF6; font-size: 11px;")
        self.slider_spacing = QSlider(Qt.Horizontal)
        self.slider_spacing.setRange(0, 10)
        self.slider_spacing.setValue(3)
        self.slider_spacing.valueChanged.connect(self._on_spacing_slider)
        content_layout.addWidget(self.lbl_spacing)
        content_layout.addWidget(self.slider_spacing)

        # Min Volume Filter Slider
        self.lbl_filter = QLabel("Min Volume Threshold: 0 (Show All)")
        self.lbl_filter.setStyleSheet("color: #E8EEF6; font-size: 11px;")
        self.slider_filter = QSlider(Qt.Horizontal)
        self.slider_filter.setRange(0, 20)
        self.slider_filter.setValue(0)
        self.slider_filter.valueChanged.connect(self._on_filter_slider)
        content_layout.addWidget(self.lbl_filter)
        content_layout.addWidget(self.slider_filter)

        # Divider
        self._add_divider(content_layout)

        # 5. SECTION: NAVIGATION & CONTROLS
        content_layout.addWidget(QLabel("Camera & Navigation"))
        
        self.chk_live = QCheckBox("Follow Live Feed (Space)")
        self.chk_live.setChecked(True)
        self.chk_live.toggled.connect(self.follow_live_toggled.emit)
        content_layout.addWidget(self.chk_live)

        self.chk_autofit = QCheckBox("Auto-Fit Price Bounds")
        self.chk_autofit.setChecked(True)
        self.chk_autofit.toggled.connect(self.auto_fit_toggled.emit)
        content_layout.addWidget(self.chk_autofit)

        self.btn_reset = QPushButton("Reset View & Auto-Fit (Double Click)")
        self.btn_reset.clicked.connect(self.reset_camera_requested.emit)
        content_layout.addWidget(self.btn_reset)

        # Divider
        self._add_divider(content_layout)

        # 6. MOUSE LEGEND
        content_layout.addWidget(QLabel("Mouse Navigation Guide"))
        legend_text = QLabel(
            "• Left Click + Drag : Pan View\n"
            "• Right Click + Drag : Price & Time Stretch\n"
            "• Mouse Wheel : Time Zoom\n"
            "• Ctrl + Wheel : Price Zoom\n"
            "• [ / ] Keys : Step Interval (1ms..4h)\n"
            "• 1 / 2 / 3 Keys : Switch Bubble Mode"
        )
        legend_text.setStyleSheet("color: #64748B; font-size: 10px; line-height: 15px; font-weight: 400;")
        content_layout.addWidget(legend_text)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _add_divider(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: rgba(255,255,255,0.06); height: 1px; margin: 4px 0;")
        layout.addWidget(line)

    def _on_scale_slider(self, val):
        self.lbl_scale.setText(f"Bubble Size Scale: {val}%")
        self.size_scale_changed.emit(val / 100.0)

    def _on_spacing_slider(self, val):
        self.lbl_spacing.setText(f"Cell Spacing Padding: {val} px")
        self.spacing_padding_changed.emit(float(val))

    def _on_filter_slider(self, val):
        if val == 0:
            self.lbl_filter.setText("Min Volume Threshold: 0 (Show All)")
        else:
            self.lbl_filter.setText(f"Min Volume Threshold: >= {val:.1f}")
        self.min_volume_changed.emit(float(val))

    def update_ui_state(self, mode: str, interval: str, follow_live: bool, auto_fit: bool):
        # Update mode radio
        if mode == "SPLIT_PIE":
            self.btn_split_pie.setChecked(True)
        elif mode == "NET_DELTA":
            self.btn_net_delta.setChecked(True)
        else:
            self.btn_total_vol.setChecked(True)

        # Update interval buttons
        for name, btn in self.int_buttons.items():
            btn.setChecked(name == interval)

        self.chk_live.setChecked(follow_live)
        self.chk_autofit.setChecked(auto_fit)
