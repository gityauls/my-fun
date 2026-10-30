from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout,
                             QHBoxLayout, QLabel, QPushButton, QRadioButton, QSizePolicy,
                             QSlider,
                             QStyle, QToolButton, QVBoxLayout, QWidget)

from html import escape

from funplayer.core.effects import (AUTO, BAND_LABELS, BANDS_HZ, CUSTOM, MODE_NAMES,
                                    PRESETS, FxSettings)
from funplayer.ui.colors import INFO_COLOR, LINK_COLOR
from funplayer.ui.spectrum_view import SpectrumView

THROTTLE_MS = 50
MODE_TEXT = (("off", "끄기"), ("speaker", "스피커"), ("earphone", "이어폰"))
LEVEL_TEXT = {"width": "넓이", "depth": "입체감", "bass": "베이스"}
LEVEL_MODE = {"speaker": ("width",), "earphone": ("depth", "bass")}
SMALL_STYLE = f"color: {INFO_COLOR}; font-size: 8pt;"


def _link_label(tip: str) -> QLabel:
    label = QLabel()
    label.setTextFormat(Qt.RichText)
    label.setToolTip(tip)
    label.setCursor(Qt.PointingHandCursor)
    return label


def _set_link_text(label: QLabel, text: str) -> None:
    label.setText(f'<a href="#" style="color:{LINK_COLOR}; text-decoration:underline;">'
                  f'{escape(text)}</a>')


class _ElidedLink(QLabel):
    """링크 글자. 자리가 모자라면 줄임표로 줄어들어 창을 넓히지 않는다 (툴팁은 따로 둔다)."""

    def __init__(self, tip: str) -> None:
        super().__init__()
        self.setTextFormat(Qt.RichText)
        self.setToolTip(tip)
        self.setCursor(Qt.PointingHandCursor)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def set_full_text(self, text: str) -> None:
        self._full = text
        _set_link_text(self, text)
        self.updateGeometry()
        QTimer.singleShot(0, self._render)   # 자리가 정해진 뒤에 줄인다

    def _render(self) -> None:
        width = self.width()
        shown = self._full
        if self._full and 0 < width < self.fontMetrics().horizontalAdvance(self._full):
            shown = self.fontMetrics().elidedText(self._full, Qt.ElideRight, width)
        _set_link_text(self, shown)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render()

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(self.fontMetrics().horizontalAdvance(self._full) + 2, base.height())

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())


def _gray_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {INFO_COLOR};")
    return label


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
        self._genre: str | None = None   # 자동일 때 곡/방송 장르로 고른 프리셋
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
        # 접은 줄: 켜짐 · 프리셋 · 듣는 곳 (앞의 둘만 눌린다, 듣는 곳은 회색 글자)
        self.summary_box = QWidget()
        sbox = QHBoxLayout(self.summary_box)
        sbox.setContentsMargins(0, 0, 0, 0)
        sbox.setSpacing(4)
        self.power_link = _link_label("")
        self.power_link.linkActivated.connect(self._power_clicked)
        self.preset_link = _ElidedLink("눌러서 다음 프리셋")
        self.preset_link.linkActivated.connect(self._preset_clicked)
        self.mode_label = _gray_label()
        self._mode_sep = _gray_label("·")
        for w in (self.power_link, _gray_label("·"), self.preset_link, self._mode_sep,
                  self.mode_label):
            sbox.addWidget(w)
        self.small_spectrum = SpectrumView(12)
        # 접은 줄이 길어지면 줄어든다 (36~72 px): 창 너비를 밀어 넓히지 않게
        self.small_spectrum.hint_width = 72
        self.small_spectrum.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.small_spectrum.setMinimumWidth(36)
        self.small_spectrum.setMaximumWidth(72)
        self.small_spectrum.setFixedHeight(16)
        self.big_spectrum = SpectrumView(24)
        self.big_spectrum.setFixedHeight(38)
        self.preset_label = QLabel("프리셋")
        self.preset_combo = QComboBox()
        # 가장 긴 프리셋 이름만큼 넓어지지 않게 (창이 넓어지는 것을 막는다)
        self.preset_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.preset_combo.setMinimumContentsLength(6)
        self.preset_combo.addItems([AUTO, *PRESETS, CUSTOM])
        self.preset_combo.currentIndexChanged.connect(self._preset_picked)
        head.addWidget(self.fold_button)
        head.addWidget(self.title_label)
        head.addWidget(self.enabled_box)
        head.addWidget(self.summary_box)
        head.addStretch(1)
        head.addWidget(self.small_spectrum)
        head.addWidget(self.preset_label)
        head.addWidget(self.preset_combo)
        root.addLayout(head)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)
        body.addWidget(self.big_spectrum)

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
            slider.setPageStep(3)   # PageUp/PageDown은 3 dB씩 (기본 10은 너무 크다)
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
        self._fit_min_width(self.reset_button)
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

    @property
    def is_open(self) -> bool:
        return self._open

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
        self._refresh_summary()
        self._refresh_open()

    def _sync_combo(self) -> None:
        # 0번 칸은 자동일 때 '자동: 록'처럼 지금 적용된 이름으로 보인다
        combo = self.preset_combo
        blocked = combo.blockSignals(True)
        try:
            combo.setItemText(0, self._display_name() if self._fx.auto else AUTO)
            combo.setCurrentIndex(0 if self._fx.auto else combo.findText(self._fx.preset))
        finally:
            combo.blockSignals(blocked)

    def _refresh_summary(self) -> None:
        fx = self._fx
        _set_link_text(self.power_link, "켜짐" if fx.enabled else "꺼짐")
        self.power_link.setToolTip("눌러서 끄기" if fx.enabled else "눌러서 켜기")
        self.preset_link.set_full_text(self._display_name())
        mode = MODE_NAMES.get(fx.mode)
        self.mode_label.setText(mode or "")
        self.mode_label.setVisible(bool(mode) and not self._open)
        self._mode_sep.setVisible(bool(mode) and not self._open)

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
        self.summary_box.setVisible(not on)
        self.small_spectrum.setVisible(not on)
        self.big_spectrum.setVisible(on)
        self._refresh_summary()
        self.fold_button.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.fold_button.setToolTip("접기" if on else "펼치기")

    # --- 사용자 조작 ---

    def _emit_final(self, fx: FxSettings) -> None:
        self._timer.stop()
        self._pending = None
        self._fx = fx
        self._refresh_summary()
        self.changed.emit(fx, True)

    def _enabled_toggled(self, on: bool) -> None:
        self._emit_final(self._fx.with_enabled(on))

    def _power_clicked(self, _link: str = "") -> None:
        fx = self._fx.with_enabled(not self._fx.enabled)
        self.enabled_box.blockSignals(True)
        self.enabled_box.setChecked(fx.enabled)
        self.enabled_box.blockSignals(False)
        self._emit_final(fx)

    def _preset_clicked(self, _link: str = "") -> None:
        fx = self._fx.next_choice()
        self._fx = fx
        self._refresh()
        self._emit_final(fx)

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
