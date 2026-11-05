from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QPalette
from PyQt5.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QPushButton, QRadioButton, QSizePolicy,
                             QSlider, QStyle, QStyleOptionButton, QVBoxLayout, QWidget)

from funplayer.core.effects import (AUTO, BAND_LABELS, BANDS_HZ, CUSTOM, PRESETS,
                                    FxSettings)
from funplayer.core.themes import DEFAULT_THEME, Theme, get_theme
from funplayer.ui.spectrum_view import SpectrumView

THROTTLE_MS = 50
MODE_TEXT = (("off", "끄기"), ("speaker", "스피커"), ("earphone", "이어폰"))
LEVEL_TEXT = {"width": "넓이", "depth": "입체감", "bass": "베이스"}
LEVEL_MODE = {"speaker": ("width",), "earphone": ("depth", "bass")}
BARS = 24


class _SegRadio(QRadioButton):
    """세 칸 묶음의 한 칸: 표시 단추(동그라미)는 숨기고 글자를 가운데에 그린다. 칠은 QSS가 한다."""

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.text = ""   # 칠만 스타일에 맡기고 글자는 아래에서 가운데로 그린다
        self.style().drawControl(QStyle.CE_RadioButton, opt, p, self)
        p.setFont(self.font())
        p.setPen(self.palette().color(QPalette.WindowText))
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 16, base.height())


def _hz_text(hz: int) -> str:
    return f"{hz // 1000} kHz" if hz >= 1000 else f"{hz} Hz"


class FxStrip(QWidget):
    """음향 효과 칸: 제목·켜기, 스펙트럼, 프리셋·초기화, 10밴드 슬라이더, 듣는 곳, 세기 슬라이더.
    changed(설정, final): final이 False면 슬라이더를 끄는 중이다."""

    changed = pyqtSignal(object, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fx = FxSettings()
        self._genre: str | None = None   # 자동일 때 곡/방송 장르로 고른 프리셋
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
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(9)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title_label = QLabel("음향 효과")
        font = self.title_label.font()
        font.setBold(True)
        font.setPixelSize(14)
        self.title_label.setFont(font)
        self.enabled_box = QCheckBox("켜기")
        self.enabled_box.toggled.connect(self._enabled_toggled)
        head.addWidget(self.title_label, 1)
        head.addWidget(self.enabled_box)
        root.addLayout(head)

        self.spectrum = SpectrumView(BARS)
        self.spectrum.setFixedHeight(56)
        root.addWidget(self.spectrum)

        pre = QHBoxLayout()
        pre.setSpacing(8)
        self.preset_label = QLabel("프리셋")
        self.preset_label.setProperty("role", "mute")
        self.preset_combo = QComboBox()
        self.preset_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.preset_combo.setMinimumContentsLength(6)
        self.preset_combo.addItems([AUTO, *PRESETS, CUSTOM])
        self.preset_combo.currentIndexChanged.connect(self._preset_picked)
        self.reset_button = QPushButton("초기화")
        self.reset_button.setProperty("kind", "btn")
        self.reset_button.clicked.connect(self._reset)
        self._fit_min_width(self.reset_button)
        pre.addWidget(self.preset_label)
        pre.addWidget(self.preset_combo, 1)
        pre.addWidget(self.reset_button)
        root.addLayout(pre)

        grid = QGridLayout()
        grid.setHorizontalSpacing(2)
        grid.setVerticalSpacing(5)
        scale = QVBoxLayout()
        for text, align in (("+12", Qt.AlignTop), ("0", Qt.AlignVCenter), ("-12", Qt.AlignBottom)):
            label = self._small_label(text)
            label.setAlignment(Qt.AlignRight | align)
            scale.addWidget(label, 1)
        grid.addLayout(scale, 0, 0)
        self.band_sliders: list[QSlider] = []
        for i, name in enumerate(BAND_LABELS):
            slider = QSlider(Qt.Vertical)
            slider.setRange(-12, 12)
            slider.setPageStep(3)   # PageUp/PageDown은 3 dB씩 (기본 10은 너무 크다)
            slider.setFixedHeight(92)
            slider.setTickPosition(QSlider.NoTicks)
            slider.valueChanged.connect(lambda v, i=i: self._band_changed(i, v))
            slider.sliderReleased.connect(self._released)
            self.band_sliders.append(slider)
            grid.addWidget(slider, 0, i + 1, Qt.AlignHCenter)
            label = self._small_label(name)
            label.setAlignment(Qt.AlignHCenter)
            grid.addWidget(label, 1, i + 1)
            grid.setColumnStretch(i + 1, 1)
        root.addLayout(grid)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        mode_label = QLabel("듣는 곳")
        mode_label.setProperty("role", "mute")
        mode_row.addWidget(mode_label)
        self.mode_seg = QFrame()
        self.mode_seg.setObjectName("fxSeg")
        seg = QHBoxLayout(self.mode_seg)
        seg.setContentsMargins(2, 2, 2, 2)
        seg.setSpacing(0)
        self.mode_buttons: dict[str, QRadioButton] = {}
        self._mode_group = QButtonGroup(self)
        for key, text in MODE_TEXT:
            button = _SegRadio(text)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(lambda _=False, key=key: self._mode_picked(key))
            self._mode_group.addButton(button)
            self.mode_buttons[key] = button
            seg.addWidget(button, 1)
        mode_row.addWidget(self.mode_seg, 1)
        root.addLayout(mode_row)

        self.level_row = QWidget()
        level = QHBoxLayout(self.level_row)
        level.setContentsMargins(0, 0, 0, 0)
        level.setSpacing(10)
        self.level_sliders: dict[str, QSlider] = {}
        self._level_labels: dict[str, QLabel] = {}
        for key, text in LEVEL_TEXT.items():
            label = QLabel(text)
            label.setProperty("role", "mute")
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.valueChanged.connect(lambda v, key=key: self._level_changed(key, v))
            slider.sliderReleased.connect(self._released)
            self._level_labels[key] = label
            self.level_sliders[key] = slider
            level.addWidget(label)
            level.addWidget(slider, 1)
        root.addWidget(self.level_row)
        root.addStretch(1)
        self.set_theme(get_theme(DEFAULT_THEME))

    @staticmethod
    def _small_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "mute")
        font = label.font()
        font.setPixelSize(10)
        label.setFont(font)
        return label

    def set_theme(self, theme: Theme) -> None:
        """스펙트럼 색만 여기서 바꾼다. 나머지 글자·단추 색은 패널 스타일시트(#pageFx)가 입힌다."""
        self.spectrum.set_colors(theme.spec or (theme.g1,), theme.acc_t)

    def _fit_min_width(self, button: QPushButton) -> None:
        # 글자에 맞춘 최소 폭 (스타일의 기본 최소폭 75~80px을 덮어쓴다, 패널과 같은 방식)
        st = self.style()
        w = button.fontMetrics().horizontalAdvance(button.text())
        w += 2 * st.pixelMetric(QStyle.PM_ButtonMargin, None, button) + 8
        button.setMinimumWidth(w)

    # --- 바깥에서 쓰는 것 ---

    @property
    def value(self) -> FxSettings:
        return self._fx

    def set_value(self, fx: FxSettings) -> None:
        """신호 없이 화면만 맞춘다."""
        self._timer.stop()
        self._pending = None
        self._fx = fx
        self._refresh()

    def set_genre_preset(self, name: str | None) -> None:
        """자동일 때 쓸 장르 프리셋 이름(없으면 None). 신호 없이 화면만 맞춘다."""
        name = name if name in PRESETS else None
        if name == self._genre:
            return
        self._genre = name
        if self._fx.auto:
            self._refresh()

    def _display_name(self) -> str:
        name = self._fx.applied_name(self._genre)
        return f"자동: {name}" if self._fx.auto else name

    # --- 화면 갱신 (신호 없이) ---

    def _refresh(self) -> None:
        fx = self._fx
        shown = fx.applied(self._genre)   # 자동이면 장르 프리셋의 값
        for w in (self.enabled_box, self.preset_combo, self._mode_group, *self.band_sliders,
                  *self.level_sliders.values()):
            w.blockSignals(True)
        try:
            self.enabled_box.setChecked(fx.enabled)
            self._sync_combo()
            for slider, db in zip(self.band_sliders, shown.bands):
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

    def _sync_combo(self) -> None:
        # 0번 칸은 자동일 때 '자동: 록'처럼 지금 적용된 이름으로 보인다
        combo = self.preset_combo
        blocked = combo.blockSignals(True)
        try:
            combo.setItemText(0, self._display_name() if self._fx.auto else AUTO)
            combo.setCurrentIndex(0 if self._fx.auto else combo.findText(self._fx.preset))
        finally:
            combo.blockSignals(blocked)

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

    # --- 사용자 조작 ---

    def _emit_final(self, fx: FxSettings) -> None:
        self._timer.stop()
        self._pending = None
        self._fx = fx
        self.changed.emit(fx, True)

    def _enabled_toggled(self, on: bool) -> None:
        self._emit_final(self._fx.with_enabled(on))

    def _preset_picked(self, index: int) -> None:
        combo = self.preset_combo
        name = AUTO if index == 0 else combo.itemText(index)
        fx = self._fx.with_preset(name)
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
        # 자동 중이면 지금 보이는(장르 프리셋) 값에서 움직인 값이 사용자 설정이 된다
        fx = self._fx.applied(self._genre).with_band(i, db)
        self._fx = fx
        self._sync_combo()
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
            self.changed.emit(fx, False)

    def _released(self) -> None:
        self._emit_final(self._fx)
