from __future__ import annotations

import time

from PyQt5.QtWidgets import QApplication, QCheckBox, QVBoxLayout, QWidget

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtTest import QTest

from funplayer.core.effects import AUTO, CUSTOM, PRESETS, FxSettings
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


def test_fx_order_matches_mockup(qapp):      # 위에서 아래로: 제목·켜기, 스펙트럼, 프리셋·초기화, 밴드 10개, 듣는 곳, 세기
    s = FxStrip(); s.resize(344, 420); s.show()
    ys = [s.enabled_box, s.spectrum, s.preset_combo, s.band_sliders[0]]
    assert sorted(w.mapTo(s, QPoint()).y() for w in ys) == [w.mapTo(s, QPoint()).y() for w in ys]
    assert s.preset_combo.mapTo(s, QPoint()).y() == s.reset_button.mapTo(s, QPoint()).y() or \
        abs(s.preset_combo.geometry().center().y() - s.reset_button.geometry().center().y()) < 4
    below = [s.band_sliders[0], s.mode_seg, s.level_row]
    s.mode_buttons["speaker"].click()
    assert [w.mapTo(s, QPoint()).y() for w in below] == sorted(w.mapTo(s, QPoint()).y() for w in below)


def test_everything_fits_in_344_by_420(qapp):
    s = FxStrip(); s.resize(344, 420); s.show()
    s.mode_buttons["earphone"].click()
    for w in (s.enabled_box, s.spectrum, s.preset_combo, s.reset_button, *s.band_sliders,
              *s.mode_buttons.values(), *s.level_sliders.values()):
        if not w.isVisibleTo(s):
            continue
        r = w.rect().translated(w.mapTo(s, QPoint()))
        assert s.rect().contains(r), w


def test_no_fold_left(qapp):
    s = FxStrip()
    assert not hasattr(s, "fold_button") and not hasattr(s, "set_open") and not hasattr(s, "open_changed")
    assert s.spectrum.bars == 24


def test_set_theme_colours_spectrum(qapp):
    from funplayer.core.themes import THEMES
    s = FxStrip()
    for t in THEMES:
        s.set_theme(t)
        assert s.spectrum.bar_color(0, 24) == (t.spec or (t.g1,))[0]


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


def test_spectrum_placed(qapp):
    strip, _ = make(qapp)
    strip.show()
    assert strip.spectrum.bars == 24 and strip.spectrum.height() == 56
    assert strip.spectrum.isVisibleTo(strip)


def test_mode_is_three_part_segment(qapp):
    strip, emitted = make(qapp)
    strip.show()
    seg = strip.mode_seg
    assert all(seg.isAncestorOf(b) for b in strip.mode_buttons.values())
    strip.mode_buttons["speaker"].click()
    assert strip.mode_buttons["speaker"].isChecked() and emitted[-1][0].mode == "speaker"


def test_spectrum_view_paints(qapp):
    view = SpectrumView(24)
    view.resize(240, 38)
    assert view.levels == [0.0] * 24
    view.grab()
    view.set_levels([0.5] * 24, [0.8] * 24)
    assert view.levels == [0.5] * 24 and view.peaks == [0.8] * 24
    assert not view.grab().isNull()


# ---- 켜기 스위치 ----

def switch(theme="light"):
    from funplayer.core.themes import get_theme
    from funplayer.ui.style import stylesheet
    host = QWidget(); host.setObjectName("pageFx"); host.setStyleSheet(stylesheet(get_theme(theme)))
    box = QVBoxLayout(host); strip = FxStrip(); box.addWidget(strip)
    strip.set_theme(get_theme(theme)); host.resize(360, 400); host.show(); QApplication.processEvents()
    return host, strip.enabled_box, get_theme(theme)


def test_switch_is_still_a_labelled_checkbox(qapp):
    host, sw, _ = switch()
    assert isinstance(sw, QCheckBox) and sw.text() == "켜기" and sw.focusPolicy() != Qt.NoFocus
    r = sw.track_rect()
    assert (r.width(), r.height()) == (34, 19)


def test_switch_colours_and_knob_follow_the_state(qapp):
    host, sw, t = switch()
    r = sw.track_rect(); y = r.center().y(); left, right = r.left() + 10, r.right() - 10
    sw.setChecked(False); QApplication.processEvents()
    img = sw.grab().toImage()
    assert img.pixelColor(right, y).name() == QColor(t.track).name()
    assert img.pixelColor(left, y).name() == QColor(t.on_acc).name()
    sw.setChecked(True); QApplication.processEvents()
    img = sw.grab().toImage()
    assert img.pixelColor(left, y).name() == QColor(t.acc).name()
    assert img.pixelColor(right, y).name() == QColor(t.on_acc).name()


def test_switch_clicks_and_keyboard_toggle(qapp):
    host, sw, _ = switch()
    seen = []; sw.toggled.connect(seen.append)
    QTest.mouseClick(sw, Qt.LeftButton, pos=sw.track_rect().center())
    assert seen == [True]
    sw.setFocus(); QTest.keyClick(sw, Qt.Key_Space)
    assert seen == [True, False]
