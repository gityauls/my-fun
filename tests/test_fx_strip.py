from __future__ import annotations

import time

from PyQt5.QtWidgets import QApplication

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from funplayer.core.effects import AUTO, CUSTOM, PRESETS, FxSettings
from funplayer.ui.colors import INFO_COLOR
from funplayer.ui.fx_strip import THROTTLE_MS, FxStrip
from funplayer.ui.spectrum_view import SpectrumView


def make(qapp):
    strip = FxStrip()
    strip.resize(360, 300)
    emitted = []
    strip.changed.connect(lambda fx, final: emitted.append((fx, final)))
    return strip, emitted


def _plain(label):
    from PyQt5.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(label.text())
    return doc.toPlainText()


def test_widgets_exist(qapp):
    strip, _ = make(qapp)
    assert len(strip.band_sliders) == 10
    assert all(s.minimum() == -12 and s.maximum() == 12 for s in strip.band_sliders)
    assert all(s.pageStep() == 3 for s in strip.band_sliders)   # PageUp/Down은 3 dB씩
    assert strip.preset_combo.count() == 20
    assert strip.preset_combo.itemText(0) == AUTO
    assert strip.preset_combo.itemText(19) == CUSTOM
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
    assert strip.summary_box.isVisibleTo(strip)
    assert _plain(strip.power_link) == "켜짐" and _plain(strip.preset_link) == "발라드"
    assert strip.mode_label.text() == "이어폰" and strip.mode_label.isVisibleTo(strip)
    assert strip.fold_button.toolTip() == "펼치기"
    strip.fold_button.click()
    assert strip.is_open and opened == [False, True]
    assert strip.band_sliders[0].isVisibleTo(strip)
    assert not strip.summary_box.isVisibleTo(strip)


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
    assert _plain(strip.preset_link) == "록" and strip.mode_label.text() == "스피커"


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
    assert _plain(strip.power_link) == "켜짐" and _plain(strip.preset_link) == "기본"


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


def test_combo_has_auto_first_and_shows_applied(qapp):
    strip, emitted = make(qapp)
    strip.set_value(FxSettings().with_preset(AUTO))
    strip.set_genre_preset("록")
    assert strip.preset_combo.currentIndex() == 0
    assert strip.preset_combo.currentText() == "자동: 록"
    assert [s.value() for s in strip.band_sliders] == list(PRESETS["록"])
    assert emitted == []
    strip.set_genre_preset(None)
    assert strip.preset_combo.currentText() == "자동: 기본"
    strip.set_value(FxSettings().with_preset("발라드"))
    assert strip.preset_combo.itemText(0) == AUTO and strip.preset_combo.currentText() == "발라드"


def test_picking_auto_item_turns_auto_on(qapp):
    strip, emitted = make(qapp)
    strip.set_genre_preset("재즈")
    strip.preset_combo.setCurrentIndex(0)
    assert emitted[-1][1] is True and emitted[-1][0].auto
    assert strip.preset_combo.currentText() == "자동: 재즈"


def test_slider_while_auto_becomes_custom(qapp):
    strip, emitted = make(qapp)
    strip.set_value(FxSettings().with_preset(AUTO))
    strip.set_genre_preset("록")
    strip.band_sliders[0].setValue(PRESETS["록"][0] + 1)
    fx = emitted[-1][0]
    assert not fx.auto and fx.preset == CUSTOM
    assert fx.bands[0] == PRESETS["록"][0] + 1 and fx.bands[1:] == PRESETS["록"][1:]
    assert strip.preset_combo.currentText() == CUSTOM


def test_reset_turns_auto_off(qapp):
    strip, emitted = make(qapp)
    strip.set_value(FxSettings().with_preset(AUTO))
    strip.reset_button.click()
    assert not emitted[-1][0].auto and strip.preset_combo.currentText() == "기본"


def test_collapsed_power_click_toggles(qapp):
    strip, emitted = make(qapp)
    strip.show()
    strip.set_open(False)
    assert strip.power_link.toolTip() == "눌러서 켜기"
    strip.power_link.linkActivated.emit("#")
    assert emitted[-1][1] is True and emitted[-1][0].enabled
    assert strip.enabled_box.isChecked() and strip.power_link.toolTip() == "눌러서 끄기"
    strip.power_link.linkActivated.emit("#")
    assert not emitted[-1][0].enabled and strip.power_link.toolTip() == "눌러서 켜기"
    assert strip.power_link.cursor().shape() == Qt.PointingHandCursor
    assert "text-decoration:underline" in strip.power_link.text()


def test_collapsed_preset_click_cycles(qapp):
    strip, emitted = make(qapp)
    strip.set_open(False)
    assert strip.preset_link.toolTip() == "눌러서 다음 프리셋"
    names = list(PRESETS)
    strip.preset_link.linkActivated.emit("#")
    assert emitted[-1][1] is True and emitted[-1][0].preset == names[1]   # 기본 -> 다음
    assert _plain(strip.preset_link) == names[1]
    strip.set_value(FxSettings())
    strip.set_genre_preset("록")
    strip.set_value(FxSettings().with_preset(AUTO))
    assert _plain(strip.preset_link) == "자동: 록"
    strip.preset_link.linkActivated.emit("#")
    assert emitted[-1][0].preset == "기본" and not emitted[-1][0].auto


def test_collapsed_shows_preset_when_off_and_hides_mode_off(qapp):
    strip, _ = make(qapp)
    strip.show()
    strip.set_open(False)
    strip.set_value(FxSettings().with_preset("발라드"))
    assert _plain(strip.power_link) == "꺼짐" and _plain(strip.preset_link) == "발라드"
    assert not strip.mode_label.isVisibleTo(strip) and not strip._mode_sep.isVisibleTo(strip)
    strip.set_value(FxSettings().with_mode("speaker"))
    assert strip.mode_label.isVisibleTo(strip) and strip._mode_sep.isVisibleTo(strip)


def test_mode_label_not_clickable(qapp):
    strip, emitted = make(qapp)
    strip.show()
    strip.set_open(False)
    strip.set_value(FxSettings().with_mode("speaker"))
    label = strip.mode_label
    assert INFO_COLOR in label.styleSheet()
    assert label.cursor().shape() != Qt.PointingHandCursor and "<a " not in label.text()
    QTest.mouseClick(label, Qt.LeftButton)
    assert emitted == [] and strip.value.mode == "speaker"


def test_spectrum_views_placed(qapp):
    strip, _ = make(qapp)
    strip.show()
    big, small = strip.big_spectrum, strip.small_spectrum
    assert big.bars == 24 and big.height() == 38
    assert small.bars == 12 and (small.width(), small.height()) == (72, 16)
    body = strip.body.layout()
    assert body.indexOf(big) == 0 and body.indexOf(big) < body.indexOf(body.itemAt(1).layout())
    assert big.isVisibleTo(strip) and not small.isVisibleTo(strip)
    strip.set_open(False)
    assert small.isVisibleTo(strip) and not big.isVisibleTo(strip)


def test_spectrum_view_paints(qapp):
    view = SpectrumView(24)
    view.resize(240, 38)
    assert view.levels == [0.0] * 24
    view.grab()
    view.set_levels([0.5] * 24, [0.8] * 24)
    assert view.levels == [0.5] * 24 and view.peaks == [0.8] * 24
    assert not view.grab().isNull()
