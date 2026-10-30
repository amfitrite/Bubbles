from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal
from src.visual.theme import Theme

class SettingsPanel(QWidget):
    """
    Monochrome Studio Slide-Out Settings Panel.
    Allows real-time tuning of the visual gap, bubble scale, imbalance threshold, and filters.
    """
    mode_changed = Signal(str)
    gap_changed = Signal(float)
    scale_changed = Signal(float)
    imbalance_ratio_changed = Signal(float)
    min_volume_changed = Signal(float)
    autofit_toggled = Signal(bool)
    follow_live_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #0E1117;
                color: #F8FAFC;
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel {{
                color: #94A3B8;
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: #1E2430;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: #38BDF8;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #F8FAFC;
                border: 1px solid #64748B;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }}
            QPushButton {{
                background-color: #161A22;
                border: 1px solid #1E2430;
                color: #CBD5E1;
                padding: 6px 12px;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #262D3D;
                color: #FFFFFF;
                border-color: #38BDF8;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header Title
        title_box = QHBoxLayout()
        title_lbl = QLabel("STUDIO SETTINGS")
        title_lbl.setStyleSheet("font-size: 12px; color: #FFFFFF; font-weight: bold;")
        title_box.addWidget(title_lbl)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.clicked.connect(self.hide)
        title_box.addWidget(btn_close, alignment=Qt.AlignRight)
        layout.addLayout(title_box)

        # 1. Pixel Spacing Gap Slider
        self.lbl_gap = QLabel("MIN PIXEL GAP: 5 px")
        layout.addWidget(self.lbl_gap)
        self.slider_gap = QSlider(Qt.Horizontal)
        self.slider_gap.setRange(0, 25)
        self.slider_gap.setValue(5)
        self.slider_gap.valueChanged.connect(self._on_gap_slider)
        layout.addWidget(self.slider_gap)

        # 2. Bubble Scale Slider
        self.lbl_scale = QLabel("BUBBLE SCALE: 1.0x")
        layout.addWidget(self.lbl_scale)
        self.slider_scale = QSlider(Qt.Horizontal)
        self.slider_scale.setRange(4, 25) # 0.4x to 2.5x
        self.slider_scale.setValue(10)
        self.slider_scale.valueChanged.connect(self._on_scale_slider)
        layout.addWidget(self.slider_scale)

        # 3. Imbalance Ratio Threshold Slider
        self.lbl_imb = QLabel("IMBALANCE RATIO: 3.0x")
        layout.addWidget(self.lbl_imb)
        self.slider_imb = QSlider(Qt.Horizontal)
        self.slider_imb.setRange(15, 80) # 1.5x to 8.0x
        self.slider_imb.setValue(30)
        self.slider_imb.valueChanged.connect(self._on_imb_slider)
        layout.addWidget(self.slider_imb)

        # 4. Min Volume Filter Slider
        self.lbl_min_vol = QLabel("MIN VOLUME FILTER: 0.0 LOTS")
        layout.addWidget(self.lbl_min_vol)
        self.slider_min_vol = QSlider(Qt.Horizontal)
        self.slider_min_vol.setRange(0, 50) # 0 to 50 lots
        self.slider_min_vol.setValue(0)
        self.slider_min_vol.valueChanged.connect(self._on_min_vol_slider)
        layout.addWidget(self.slider_min_vol)

        # 5. Camera Toggles
        layout.addSpacing(10)
        self.btn_autofit = QPushButton("AUTO-FIT PRICE: ON")
        self.btn_autofit.clicked.connect(self._toggle_autofit)
        layout.addWidget(self.btn_autofit)

        self.btn_live = QPushButton("FOLLOW LIVE TIME: ON")
        self.btn_live.clicked.connect(self._toggle_live)
        layout.addWidget(self.btn_live)

        layout.addStretch()

        self._autofit_val = True
        self._live_val = True

    def _on_gap_slider(self, val):
        self.lbl_gap.setText(f"MIN PIXEL GAP: {val} px")
        self.gap_changed.emit(float(val))

    def _on_scale_slider(self, val):
        scale = val / 10.0
        self.lbl_scale.setText(f"BUBBLE SCALE: {scale:.1f}x")
        self.scale_changed.emit(scale)

    def _on_imb_slider(self, val):
        ratio = val / 10.0
        self.lbl_imb.setText(f"IMBALANCE RATIO: {ratio:.1f}x")
        self.imbalance_ratio_changed.emit(ratio)

    def _on_min_vol_slider(self, val):
        self.lbl_min_vol.setText(f"MIN VOLUME FILTER: {val:.1f} LOTS")
        self.min_volume_changed.emit(float(val))

    def _toggle_autofit(self):
        self._autofit_val = not self._autofit_val
        self.btn_autofit.setText(f"AUTO-FIT PRICE: {'ON' if self._autofit_val else 'OFF'}")
        self.autofit_toggled.emit(self._autofit_val)

    def _toggle_live(self):
        self._live_val = not self._live_val
        self.btn_live.setText(f"FOLLOW LIVE TIME: {'ON' if self._live_val else 'OFF'}")
        self.follow_live_toggled.emit(self._live_val)

    def update_values(self, gap: float, scale: float, autofit: bool, live: bool):
        self.slider_gap.setValue(int(gap))
        self.slider_scale.setValue(int(scale * 10))
        self._autofit_val = autofit
        self.btn_autofit.setText(f"AUTO-FIT PRICE: {'ON' if autofit else 'OFF'}")
        self._live_val = live
        self.btn_live.setText(f"FOLLOW LIVE TIME: {'ON' if live else 'OFF'}")
