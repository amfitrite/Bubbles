from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton
)
from PySide6.QtCore import Qt, Signal
from src.visual.theme import Theme

class SettingsPanel(QWidget):
    """
    Monochrome Studio Slide-Out Settings Panel.
    Allows real-time tuning of the visual gap, bubble scale, imbalance threshold,
    volume filters, auto-fit/auto-scroll toggles, and frame rate cap (FPS limit).
    """
    mode_changed = Signal(str)
    gap_changed = Signal(float)
    scale_changed = Signal(float)
    imbalance_ratio_changed = Signal(float)
    min_volume_changed = Signal(float)
    autofit_toggled = Signal(bool)
    follow_live_toggled = Signal(bool)
    fps_changed = Signal(str)

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
                background-color: #1E2430;
                border-color: #38BDF8;
                color: #FFFFFF;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("STUDIO SETTINGS")
        title.setStyleSheet("font-size: 13px; color: #FFFFFF; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(title)
        layout.addSpacing(6)

        # 1. Pixel Gap Slider
        self.lbl_gap = QLabel("MIN PIXEL GAP: 6 px")
        layout.addWidget(self.lbl_gap)
        self.slider_gap = QSlider(Qt.Horizontal)
        self.slider_gap.setRange(0, 25)
        self.slider_gap.setValue(6)
        self.slider_gap.valueChanged.connect(self._on_gap_slider)
        layout.addWidget(self.slider_gap)

        # 2. Bubble Scale Slider
        self.lbl_scale = QLabel("BUBBLE SCALE: 1.0x")
        layout.addWidget(self.lbl_scale)
        self.slider_scale = QSlider(Qt.Horizontal)
        self.slider_scale.setRange(4, 30) # 0.4x to 3.0x
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

        # 5. Frame Rate Cap (FPS Limit)
        layout.addSpacing(6)
        self.lbl_fps = QLabel("FRAME RATE CAP (FPS): 60")
        layout.addWidget(self.lbl_fps)

        fps_row = QHBoxLayout()
        fps_row.setSpacing(6)

        self.btn_fps_60 = QPushButton("60")
        self.btn_fps_120 = QPushButton("120")
        self.btn_fps_max = QPushButton("MAX")

        self.btn_fps_60.clicked.connect(lambda: self._on_fps_btn("60"))
        self.btn_fps_120.clicked.connect(lambda: self._on_fps_btn("120"))
        self.btn_fps_max.clicked.connect(lambda: self._on_fps_btn("UNLIMITED"))

        fps_row.addWidget(self.btn_fps_60)
        fps_row.addWidget(self.btn_fps_120)
        fps_row.addWidget(self.btn_fps_max)
        layout.addLayout(fps_row)

        # 6. Camera Toggles
        layout.addSpacing(10)
        self.btn_autofit = QPushButton("AUTO-FIT PRICE: ON")
        self.btn_autofit.clicked.connect(self._toggle_autofit)
        layout.addWidget(self.btn_autofit)

        self.btn_live = QPushButton("AUTO SCROLL: ON")
        self.btn_live.clicked.connect(self._toggle_live)
        layout.addWidget(self.btn_live)

        layout.addStretch()

        self._autofit_val = True
        self._live_val = True
        self._fps_target = "60"
        self._refresh_fps_buttons()

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

    def _on_fps_btn(self, target: str):
        self._fps_target = target
        self._refresh_fps_buttons()
        self.fps_changed.emit(target)

    def _refresh_fps_buttons(self):
        active_style = "background-color: #1E293B; border-color: #38BDF8; color: #38BDF8;"
        inactive_style = "background-color: #161A22; border-color: #1E2430; color: #94A3B8;"

        self.btn_fps_60.setStyleSheet(active_style if self._fps_target == "60" else inactive_style)
        self.btn_fps_120.setStyleSheet(active_style if self._fps_target == "120" else inactive_style)
        self.btn_fps_max.setStyleSheet(active_style if self._fps_target == "UNLIMITED" else inactive_style)

        disp_txt = "UNLIMITED" if self._fps_target == "UNLIMITED" else f"{self._fps_target} FPS"
        self.lbl_fps.setText(f"FRAME RATE CAP: {disp_txt}")

    def update_fps(self, fps_target: str):
        self._fps_target = fps_target
        self._refresh_fps_buttons()

    def _toggle_autofit(self):
        self._autofit_val = not self._autofit_val
        self.btn_autofit.setText(f"AUTO-FIT PRICE: {'ON' if self._autofit_val else 'OFF'}")
        self.autofit_toggled.emit(self._autofit_val)

    def _toggle_live(self):
        self._live_val = not self._live_val
        self.btn_live.setText(f"AUTO SCROLL: {'ON' if self._live_val else 'OFF'}")
        self.follow_live_toggled.emit(self._live_val)

    def update_values(self, gap: float, scale: float, autofit: bool, live: bool,
                      imbalance_ratio: float = 3.0, min_vol: float = 0.0, fps_target: str = "60"):
        self.slider_gap.setValue(int(gap))
        self.slider_scale.setValue(int(scale * 10))
        self.slider_imb.setValue(int(imbalance_ratio * 10))
        self.slider_min_vol.setValue(int(min_vol))
        self._autofit_val = autofit
        self.btn_autofit.setText(f"AUTO-FIT PRICE: {'ON' if autofit else 'OFF'}")
        self._live_val = live
        self.btn_live.setText(f"AUTO SCROLL: {'ON' if live else 'OFF'}")
        self._fps_target = fps_target
        self._refresh_fps_buttons()
