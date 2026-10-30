import pytest
from fakes import FakePlayer, FakeRunner, FakeStream, make_songs
from funplayer.core.effects import FxSettings
from funplayer.core.settings import Settings
from funplayer.ui.player_panel import PlayerPanel


def make_panel(store=None, **kw):
    fake, runner = FakePlayer(), FakeRunner()
    p = PlayerPanel(Settings({} if store is None else store, lambda: None),
                    player=fake, runner=runner, **kw)
    p.resize(380, 560); p.show()
    return p, fake, runner


@pytest.fixture
def fpanel(qapp):
    store = {}
    p, fake, runner = make_panel(store)
    yield p, fake, store
    p.shutdown(); p.deleteLater()


def test_fx_hidden_by_default_and_menu_toggles(fpanel):
    p, _, store = fpanel
    assert not p.fx_strip.isVisible() and not p.fx_separator.isVisible()
    act = p.actions["fx_visible"]
    assert act.isCheckable() and act.text() == "음향 효과 칸 보이기\tCtrl+E"
    act.trigger()
    assert p.fx_strip.isVisible() and p.fx_separator.isVisible()
    assert p.settings.fx_visible is True and store["player_fx_visible"] is True
    p.view_menu.aboutToShow.emit()
    assert act.isChecked()
    p.shortcuts["Ctrl+E"].activated.emit()
    assert not p.fx_strip.isVisible() and not p.fx_separator.isVisible()
    assert p.settings.fx_visible is False
    p.view_menu.aboutToShow.emit()
    assert not act.isChecked()


def test_fx_strip_sits_between_controls_and_tabs(fpanel):
    p, *_ = fpanel
    lay = p.layout()
    idx = {w: lay.indexOf(w) for w in (p.separator, p.fx_strip, p.fx_separator, p.tab_bar)}
    assert idx[p.separator] < idx[p.fx_strip] < idx[p.fx_separator] < idx[p.tab_bar]
    assert p.fx_separator.frameShape() == p.separator.frameShape()
    assert p.fx_separator.frameShadow() == p.separator.frameShadow()


def test_fx_hidden_in_mini_and_back(fpanel):
    p, *_ = fpanel
    p.toggle_fx_visible()
    assert p.fx_strip.isVisible()
    p.set_mini(True)
    assert not p.fx_strip.isVisible() and not p.fx_separator.isVisible()
    assert p.settings.fx_visible is True
    p.set_mini(False)
    assert p.fx_strip.isVisible() and p.fx_separator.isVisible()


def test_fx_changes_reach_player_and_save_on_final(fpanel):
    p, fake, store = fpanel
    fx = FxSettings.from_dict({"enabled": True, "preset": "발라드"})
    store.pop("player_fx", None)
    p.fx_strip.changed.emit(fx, False)
    assert fake.effects == fx and "player_fx" not in store
    p.fx_strip.changed.emit(fx, True)
    assert store["player_fx"] == fx.to_dict()


def test_fx_open_state_saved(fpanel):
    p, _, store = fpanel
    p.fx_strip.set_open(False, notify=True)
    assert store["player_fx_open"] is False


def test_effects_stay_across_song_radio_song(qapp, tmp_path):
    p, fake, runner = make_panel()
    try:
        _song_radio_song(p, fake, runner, tmp_path)
    finally:
        p.shutdown(); p.deleteLater()


def _song_radio_song(p, fake, runner, tmp_path):
    calls = []
    real = fake.set_effects
    fake.set_effects = lambda fx: (calls.append(fx), real(fx))
    fx = FxSettings.from_dict({"enabled": True, "preset": "록", "mode": "earphone"})
    p.fx_strip.changed.emit(fx, True)
    assert fake.effects == fx and calls == [fx]
    p.controller.open([str(make_songs(tmp_path / "m", ["01 a.mp3"]))])
    p.set_tab("radio"); p.station_view.station_activated.emit("kbs-25")
    runner.finish(len(runner.calls) - 1, result=FakeStream()); p.refresh()
    assert fake.is_live and fake.effects == fx
    p.switch_button.click()   # MP3로
    assert p.controller.source == "file" and fake.loaded[-1].endswith("01 a.mp3")
    assert fake.effects == fx and calls == [fx]   # 다시 걸지도, 다른 값으로 바꾸지도 않는다


def test_values_changed_while_off_apply_when_on(fpanel):
    p, fake, _ = fpanel
    p.toggle_fx_visible()
    strip = p.fx_strip
    strip.preset_combo.setCurrentText("록")
    strip.mode_buttons["earphone"].click()
    assert not fake.effects.enabled and fake.effects.preset == "록"
    strip.enabled_box.click()
    assert fake.effects.enabled and fake.effects.preset == "록" and fake.effects.mode == "earphone"
    assert fake.effects.bands == strip.value.bands


def test_hiding_or_folding_strip_keeps_effects_on(fpanel):
    p, fake, _ = fpanel
    p.toggle_fx_visible()
    p.fx_strip.enabled_box.click()
    on = fake.effects
    assert on.enabled
    p.fx_strip.fold_button.click()
    assert not p.fx_strip.is_open and fake.effects == on
    p.toggle_fx_visible()
    assert not p.fx_strip.isVisible() and fake.effects == on and p.controller.effects == on


def test_showing_strip_keeps_window_width(qapp):
    # offscreen의 대체 글꼴은 12pt에 글자마다 17px이라 모든 글자가 실제보다 넓다.
    # 앱이 Windows에서 실제로 쓰는 9pt로 맞춰 재고, 패널과 칸을 같은 글꼴로 비교한다
    from PyQt5.QtWidgets import QComboBox
    from funplayer.ui.window_keeper import DEFAULT_SIZE
    old_font = qapp.font()
    font = qapp.font()
    font.setPointSize(9)
    qapp.setFont(font)
    fake, runner = FakePlayer(), FakeRunner()
    p = PlayerPanel(Settings({}, lambda: None), player=fake, runner=runner)
    try:
        combo = p.fx_strip.preset_combo
        assert combo.sizeAdjustPolicy() == QComboBox.AdjustToMinimumContentsLengthWithIcon
        assert p.fx_strip.reset_button.minimumWidth() > 0
        p.resize(*DEFAULT_SIZE); p.show(); qapp.processEvents()
        width, panel_min = p.width(), p.minimumSizeHint().width()
        assert p.fx_strip.minimumSizeHint().width() <= panel_min
        p.actions["fx_visible"].trigger(); qapp.processEvents()
        assert p.fx_strip.isVisible() and p.width() == width
        assert p.minimumSizeHint().width() == panel_min
        p.fx_strip.set_open(False, notify=True); qapp.processEvents()
        assert p.width() == width
        p.actions["fx_visible"].trigger(); qapp.processEvents()
        assert not p.fx_strip.isVisible() and p.width() == width
    finally:
        p.shutdown(); p.deleteLater()
        qapp.setFont(old_font)


def test_fx_state_survives_restart(qapp):
    fx = FxSettings.from_dict({"enabled": True, "preset": "발라드"})
    store = {"player_fx": fx.to_dict(), "player_fx_visible": True, "player_fx_open": False}
    p, fake, _ = make_panel(store)
    try:
        assert p.fx_strip.isVisible() and not p.fx_strip.is_open
        assert p.fx_strip.summary_label.text() == "켜짐 · 발라드"
        assert fake.effects.preset == "발라드"
        p.view_menu.aboutToShow.emit()
        assert p.actions["fx_visible"].isChecked()
    finally:
        p.shutdown(); p.deleteLater()
