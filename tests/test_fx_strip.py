from __future__ import annotations

import time

from PyQt5.QtWidgets import QApplication

from funplayer.core.effects import CUSTOM, PRESETS, FxSettings
from funplayer.ui.fx_strip import THROTTLE_MS, FxStrip


def make(qapp):
    strip = FxStrip()
    strip.resize(360, 300)
    emitted = []
    strip.changed.connect(lambda fx, final: emitted.append((fx, final)))
    return strip, emitted


def test_widgets_exist(qapp):
    strip, _ = make(qapp)
    assert len(strip.band_sliders) == 10
    assert all(s.minimum() == -12 and s.maximum() == 12 for s in strip.band_sliders)
    assert all(s.pageStep() == 3 for s in strip.band_sliders)   # PageUp/Down은 3 dB씩
    assert strip.preset_combo.count() == 11
    assert strip.preset_combo.itemText(10) == CUSTOM
    assert strip.enabled_box.text() == "켜기"
    assert strip.reset_button.text() == "초기화"
    assert [strip.mode_buttons[m].text() for m in ("off", "speaker", "earphone")] == \
        ["끄기", "스피커", "이어폰"]


def test_preset_moves_sliders_and_emits_final(qapp):
    strip, emitted = make(qapp)
    strip.preset_combo.setCurrentText("발라드")
    assert [s.value() for s in strip.band_sliders] == list(PRESETS["발라드"])
    assert len(emitted) == 1
    assert emitted[0][1] is True
    assert strip.value.preset == "발라드"


def test_slider_makes_custom(qapp):
    strip, emitted = make(qapp)
    strip.band_sliders[0].setValue(5)
    assert strip.preset_combo.currentText() == CUSTOM
    assert emitted[-1][1] is True
    assert emitted[-1][0].bands[0] == 5


def test_custom_choice_restores_remembered_bands(qapp):
    strip, emitted = make(qapp)
    strip.band_sliders[1].setValue(7)
    strip.band_sliders[4].setValue(-3)
    mine = [s.value() for s in strip.band_sliders]
    strip.preset_combo.setCurrentText("록")
    assert [s.value() for s in strip.band_sliders] == list(PRESETS["록"])
    emitted.clear()
    strip.preset_combo.setCurrentText(CUSTOM)
    assert [s.value() for s in strip.band_sliders] == mine
    assert len(emitted) == 1 and emitted[0][1] is True
    assert list(emitted[0][0].bands) == mine and emitted[0][0].preset == CUSTOM


def test_drag_throttled_and_final_on_release(qapp):
    # 벽시계 창에 기대지 않는다: 이벤트 루프를 돌리기 전에는 타이머가 울 수 없고,
    # 울린 뒤에는 몇 번 보냈는지와 값만 본다 (느린 기계에서도 같다)
    strip, emitted = make(qapp)
    s = strip.band_sliders[0]
    s.setSliderDown(True)
    for v in range(1, 11):
        s.setValue(v)
    assert emitted == [] and strip._timer.isActive() and strip._timer.interval() == THROTTLE_MS
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not emitted:
        QApplication.processEvents()
        time.sleep(0.005)
    assert [final for _, final in emitted] == [False]   # 열 번 움직여도 한 번만
    assert emitted[0][0].bands[0] == 10
    s.setSliderDown(False)
    assert emitted[-1][1] is True
    assert emitted[-1][0].bands[0] == 10


def test_mode_rows(qapp):
    strip, _ = make(qapp)
    strip.show()

    def visible():
        return {k for k, w in strip.level_sliders.items() if w.isVisibleTo(strip)}

    assert visible() == set()
    strip.mode_buttons["speaker"].click()
    assert visible() == {"width"}
    assert strip.value.mode == "speaker"
    strip.mode_buttons["earphone"].click()
    assert visible() == {"depth", "bass"}
    strip.mode_buttons["off"].click()
    assert visible() == set()


def test_fold_and_summary(qapp):
    strip, _ = make(qapp)
    strip.show()
    opened = []
    strip.open_changed.connect(opened.append)
    strip.set_value(FxSettings().with_enabled(True).with_preset("발라드").with_mode("earphone"))
    assert strip.is_open
    assert strip.fold_button.toolTip() == "접기"
    strip.fold_button.click()
    assert not strip.is_open
    assert opened == [False]
    assert not strip.band_sliders[0].isVisibleTo(strip)
    assert strip.summary_label.isVisibleTo(strip)
    assert strip.summary_label.text() == strip.value.summary() == "켜짐 · 발라드 · 이어폰"
    assert strip.fold_button.toolTip() == "펼치기"
    strip.fold_button.click()
    assert strip.is_open and opened == [False, True]
    assert strip.band_sliders[0].isVisibleTo(strip)
    assert not strip.summary_label.isVisibleTo(strip)


def test_set_open_does_not_emit(qapp):
    strip, _ = make(qapp)
    opened = []
    strip.open_changed.connect(opened.append)
    strip.set_open(False)
    assert not strip.is_open and opened == []


def test_set_value_does_not_emit(qapp):
    strip, emitted = make(qapp)
    fx = FxSettings().with_enabled(True).with_preset("록").with_mode("speaker").with_level("width", 70)
    strip.set_value(fx)
    assert emitted == []
    assert strip.value == fx
    assert strip.enabled_box.isChecked()
    assert strip.preset_combo.currentText() == "록"
    assert strip.mode_buttons["speaker"].isChecked()
    assert strip.level_sliders["width"].value() == 70
    assert strip.summary_label.text() == fx.summary()


def test_set_value_custom(qapp):
    strip, _ = make(qapp)
    fx = FxSettings().with_band(2, 4)
    strip.set_value(fx)
    assert strip.preset_combo.currentText() == CUSTOM
    assert strip.band_sliders[2].value() == 4


def test_reset_button(qapp):
    strip, emitted = make(qapp)
    strip.set_value(FxSettings().with_enabled(True).with_preset("록").with_mode("earphone"))
    strip.reset_button.click()
    assert len(emitted) == 1 and emitted[0][1] is True
    fx = emitted[0][0]
    assert fx.enabled and fx.preset == "기본" and fx.mode == "off"
    assert all(s.value() == 0 for s in strip.band_sliders)
    assert strip.mode_buttons["off"].isChecked()


def test_checkbox_emits_final(qapp):
    strip, emitted = make(qapp)
    strip.enabled_box.click()
    assert emitted[-1][1] is True and emitted[-1][0].enabled
    assert strip.summary_label.text() == "켜짐 · 기본"


def test_level_slider_emits(qapp):
    strip, emitted = make(qapp)
    strip.mode_buttons["speaker"].click()
    emitted.clear()
    strip.level_sliders["width"].setValue(55)
    assert emitted[-1][1] is True and emitted[-1][0].width == 55


def test_tooltips(qapp):
    strip, _ = make(qapp)
    strip.set_value(FxSettings().with_band(5, 3).with_band(9, -2))
    assert strip.band_sliders[5].toolTip() == "1 kHz: +3 dB"
    assert strip.band_sliders[0].toolTip() == "31 Hz: 0 dB"
    assert strip.band_sliders[9].toolTip() == "16 kHz: -2 dB"
    strip.band_sliders[0].setValue(-4)
    assert strip.band_sliders[0].toolTip() == "31 Hz: -4 dB"
    assert strip.level_sliders["width"].toolTip() == "넓이 40%"
    assert strip.level_sliders["depth"].toolTip() == "입체감 40%"
    assert strip.level_sliders["bass"].toolTip() == "베이스 30%"
    strip.level_sliders["width"].setValue(60)
    assert strip.level_sliders["width"].toolTip() == "넓이 60%"
