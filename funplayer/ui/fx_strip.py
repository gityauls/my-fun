from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout,
                             QHBoxLayout, QLabel, QPushButton, QRadioButton, QSlider,
                             QToolButton, QVBoxLayout, QWidget)

from funplayer.core.effects import (BAND_LABELS, BANDS_HZ, CUSTOM, PRESETS,
                                    FxSettings)
from funplayer.ui.colors import INFO_COLOR

THROTTLE_MS = 50
MODE_TEXT = (("off", "끄기"), ("speaker", "스피커"), ("earphone", "이어폰"))
LEVEL_TEXT = {"width": "넓이", "depth": "입체감", "bass": "베이스"}
LEVEL_MODE = {"speaker": ("width",), "earphone": ("depth", "bass")}
SMALL_STYLE = f"color: {INFO_COLOR}; font-size: 8pt;"


def _hz_text(hz: int) -> str:
    return f"{hz // 1000} kHz" if hz >= 1000 else f"{hz} Hz"


class FxStrip(QWidget):
    """음향 효과 칸: 접고 펴는 머리줄, 10밴드 슬라이더, 듣는 곳, 입체 슬라이더.
    changed(설정, final): final이 False면 슬라이더를 끄는 중이다."""

    changed = pyqtSignal(object, bool)
    open_changed = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fx = FxSettings()
        self._open = True
        self._pending: FxSettings | None = None   # 끄는 중 아직 못 보낸 최신값
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(THROTTLE_MS)
        self._timer.timeout.connect(self._flush)
        self._build()
        self._refresh()

    # --- 만들기 ---

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 2, 0, 2)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.fold_button = QToolButton()
        self.fold_button.setAutoRaise(True)
        self.fold_button.clicked.connect(lambda: self.set_open(not self._open, notify=True))
        self.title_label = QLabel("음향 효과")
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        self.enabled_box = QCheckBox("켜기")
        self.enabled_box.toggled.connect(self._enabled_toggled)
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet(SMALL_STYLE)
        self.preset_label = QLabel("프리셋")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(PRESETS) + [CUSTOM])
        self.preset_combo.currentIndexChanged.connect(self._preset_picked)
        head.addWidget(self.fold_button)
        head.addWidget(self.title_label)
        head.addWidget(self.enabled_box)
        head.addWidget(self.summary_label)
        head.addStretch(1)
        head.addWidget(self.preset_label)
        head.addWidget(self.preset_combo)
        root.addLayout(head)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)

        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setVerticalSpacing(2)
        scale = QVBoxLayout()
        for text, align in (("+12", Qt.AlignTop), ("0", Qt.AlignVCenter), ("-12", Qt.AlignBottom)):
            label = QLabel(text)
            label.setStyleSheet(SMALL_STYLE)
            label.setAlignment(Qt.AlignRight | align)
            scale.addWidget(label, 1)
        grid.addLayout(scale, 0, 0)
        self.band_sliders: list[QSlider] = []
        for i, name in enumerate(BAND_LABELS):
            slider = QSlider(Qt.Vertical)
            slider.setRange(-12, 12)
            slider.setFixedHeight(80)
            slider.setTickPosition(QSlider.NoTicks)
            slider.valueChanged.connect(lambda v, i=i: self._band_changed(i, v))
            slider.sliderReleased.connect(self._released)
            self.band_sliders.append(slider)
            grid.addWidget(slider, 0, i + 1, Qt.AlignHCenter)
            label = QLabel(name)
            label.setStyleSheet(SMALL_STYLE)
            label.setAlignment(Qt.AlignHCenter)
            grid.addWidget(label, 1, i + 1)
            grid.setColumnStretch(i + 1, 1)
        body.addLayout(grid)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("듣는 곳"))
        self.mode_buttons: dict[str, QRadioButton] = {}
        self._mode_group = QButtonGroup(self)
        for key, text in MODE_TEXT:
            button = QRadioButton(text)
            button.clicked.connect(lambda _=False, key=key: self._mode_picked(key))
            self._mode_group.addButton(button)
            self.mode_buttons[key] = button
            mode_row.addWidget(button)
        mode_row.addStretch(1)
        self.reset_button = QPushButton("초기화")
        self.reset_button.clicked.connect(self._reset)
        mode_row.addWidget(self.reset_button)
        body.addLayout(mode_row)

        self.level_row = QWidget()
        level = QHBoxLayout(self.level_row)
        level.setContentsMargins(0, 0, 0, 0)
        self.level_sliders: dict[str, QSlider] = {}
        self._level_labels: dict[str, QLabel] = {}
        for key, text in LEVEL_TEXT.items():
            label = QLabel(text)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.valueChanged.connect(lambda v, key=key: self._level_changed(key, v))
            slider.sliderReleased.connect(self._released)
            self._level_labels[key] = label
            self.level_sliders[key] = slider
            level.addWidget(label)
            level.addWidget(slider, 1)
        body.addWidget(self.level_row)
        root.addWidget(self.body)

    # --- 바깥에서 쓰는 것 ---

    @property
    def value(self) -> FxSettings:
        return self._fx

    @property
    def is_open(self) -> bool:
        return self._open

    def set_value(self, fx: FxSettings) -> None:
        """신호 없이 화면만 맞춘다."""
        self._timer.stop()
        self._pending = None
        self._fx = fx
        self._refresh()

    def set_open(self, on: bool, notify: bool = False) -> None:
        on = bool(on)
        if on == self._open:
            return
        self._open = on
        self._refresh_open()
        if notify:
            self.open_changed.emit(on)

    # --- 화면 갱신 (신호 없이) ---

    def _refresh(self) -> None:
        fx = self._fx
        for w in (self.enabled_box, self.preset_combo, self._mode_group, *self.band_sliders,
                  *self.level_sliders.values()):
            w.blockSignals(True)
        try:
            self.enabled_box.setChecked(fx.enabled)
            self.preset_combo.setCurrentText(fx.preset)
            for slider, db in zip(self.band_sliders, fx.bands):
                slider.setValue(db)
            for key, slider in self.level_sliders.items():
                slider.setValue(getattr(fx, key))
            self.mode_buttons[fx.mode].setChecked(True)
        finally:
            for w in (self.enabled_box, self.preset_combo, self._mode_group, *self.band_sliders,
                      *self.level_sliders.values()):
                w.blockSignals(False)
        self._refresh_tips()
        self._refresh_mode()
        self.summary_label.setText(fx.summary())
        self._refresh_open()

    def _refresh_tips(self) -> None:
        for slider, hz in zip(self.band_sliders, BANDS_HZ):
            slider.setToolTip(f"{_hz_text(hz)}: {slider.value():+d} dB" if slider.value()
                              else f"{_hz_text(hz)}: 0 dB")
        for key, slider in self.level_sliders.items():
            slider.setToolTip(f"{LEVEL_TEXT[key]} {slider.value()}%")

    def _refresh_mode(self) -> None:
        shown = LEVEL_MODE.get(self._fx.mode, ())
        for key in LEVEL_TEXT:
            self.level_sliders[key].setVisible(key in shown)
            self._level_labels[key].setVisible(key in shown)
        self.level_row.setVisible(bool(shown))

    def _refresh_open(self) -> None:
        on = self._open
        self.body.setVisible(on)
        self.enabled_box.setVisible(on)
        self.preset_label.setVisible(on)
        self.preset_combo.setVisible(on)
        self.summary_label.setVisible(not on)
        self.fold_button.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.fold_button.setToolTip("접기" if on else "펼치기")

    # --- 사용자 조작 ---

    def _emit_final(self, fx: FxSettings) -> None:
        self._timer.stop()
        self._pending = None
        self._fx = fx
        self.summary_label.setText(fx.summary())
        self.changed.emit(fx, True)

    def _enabled_toggled(self, on: bool) -> None:
        self._emit_final(self._fx.with_enabled(on))

    def _preset_picked(self, _index: int) -> None:
        fx = self._fx.with_preset(self.preset_combo.currentText())
        self._fx = fx
        self._refresh()
        self._emit_final(fx)

    def _mode_picked(self, mode: str) -> None:
        fx = self._fx.with_mode(mode)
        self._fx = fx
        self._refresh_mode()
        self._emit_final(fx)

    def _reset(self) -> None:
        fx = self._fx.reset()
        self._fx = fx
        self._refresh()
        self._emit_final(fx)

    def _band_changed(self, i: int, db: int) -> None:
        fx = self._fx.with_band(i, db)
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentText(CUSTOM)
        self.preset_combo.blockSignals(False)
        self._after_slider(fx)

    def _level_changed(self, key: str, value: int) -> None:
        self._after_slider(self._fx.with_level(key, value))

    def _after_slider(self, fx: FxSettings) -> None:
        self._fx = fx
        self._refresh_tips()
        if self._dragging():
            self._pending = fx
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._emit_final(fx)

    def _dragging(self) -> bool:
        return any(s.isSliderDown() for s in (*self.band_sliders, *self.level_sliders.values()))

    def _flush(self) -> None:
        # 끄는 중에는 50 ms마다 최신값 하나만 보낸다
        if self._pending is not None:
            fx, self._pending = self._pending, None
            self.summary_label.setText(fx.summary())
            self.changed.emit(fx, False)

    def _released(self) -> None:
        self._emit_final(self._fx)
