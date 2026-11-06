import os
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


def test_fx_tab_by_ctrl_e(fpanel):
    p, _, store = fpanel
    assert not p.fx_strip.isVisible()
    assert "fx_visible" not in p.actions
    p.shortcuts["Ctrl+E"].activated.emit()
    assert p.fx_strip.isVisible() and p.tab == "fx" and store["player_tab"] == "fx"
    p.shortcuts["Ctrl+E"].activated.emit()
    assert not p.fx_strip.isVisible() and p.tab == "now"


def test_fx_strip_sits_in_its_page(fpanel):
    p, *_ = fpanel
    assert p.pages.widget(3).objectName() == "pageFx" and p.pages.widget(3).isAncestorOf(p.fx_strip)


def test_fx_hidden_in_mini_and_back(fpanel):
    p, *_ = fpanel
    p.toggle_fx_visible()
    assert p.fx_strip.isVisible()
    p.set_mini(True)
    assert not p.fx_strip.isVisible() and p.tab == "fx"
    p.set_mini(False)
    assert p.fx_strip.isVisible()


def test_fx_changes_reach_player_and_save_on_final(fpanel):
    p, fake, store = fpanel
    fx = FxSettings.from_dict({"enabled": True, "preset": "발라드"})
    store.pop("player_fx", None)
    p.fx_strip.changed.emit(fx, False)
    assert fake.effects == fx and "player_fx" not in store
    p.fx_strip.changed.emit(fx, True)
    assert store["player_fx"] == fx.to_dict()


def test_panel_theme_reaches_fx_spectrum(fpanel):
    from funplayer.core.themes import get_theme
    p, *_ = fpanel
    t = get_theme("dark")
    p.apply_theme(t)
    assert p.fx_strip.spectrum.bar_color(0, 24) == (t.spec or (t.g1,))[0]


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
    p.actions["switch"].trigger()   # MP3로
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


def test_hiding_strip_keeps_effects_on(fpanel):
    p, fake, _ = fpanel
    p.toggle_fx_visible()
    p.fx_strip.enabled_box.click()
    on = fake.effects
    assert on.enabled
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
        assert p.pages.widget(3).minimumSizeHint().width() <= width   # 효과 페이지가 창 폭에 들어간다
        p.set_tab("fx"); qapp.processEvents()
        assert p.fx_strip.isVisible() and p.width() == width
        assert p.minimumSizeHint().width() == panel_min
        p.fx_strip.set_value(FxSettings().with_preset("베이스 강하게").with_mode("earphone"))
        qapp.processEvents()
        assert p.width() == width
        p.set_tab("now"); qapp.processEvents()
        assert not p.fx_strip.isVisible() and p.width() == width
    finally:
        p.shutdown(); p.deleteLater()
        qapp.setFont(old_font)


def test_longest_preset_name_keeps_window_width(qapp):
    from funplayer.ui.window_keeper import DEFAULT_SIZE
    old_font = qapp.font()
    font = qapp.font()
    font.setPointSize(9)
    qapp.setFont(font)
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), runner=FakeRunner())
    try:
        p.resize(*DEFAULT_SIZE); p.show(); qapp.processEvents()
        width, panel_min = p.width(), p.minimumSizeHint().width()
        p.set_tab("fx"); qapp.processEvents()
        for fx in (FxSettings().with_preset("베이스 강하게").with_auto(True),
                   FxSettings().with_auto(True)):
            fx = FxSettings.from_dict({**fx.to_dict(), "enabled": True, "mode": "earphone"})
            p.fx_strip.set_value(fx)
            p.fx_strip.set_genre_preset("베이스 강하게")
            qapp.processEvents()
            assert p.pages.widget(3).minimumSizeHint().width() <= width
            assert p.width() == width and p.minimumSizeHint().width() == panel_min
    finally:
        p.shutdown(); p.deleteLater()
        qapp.setFont(old_font)


def test_spectrum_timer_stops_when_panel_hidden(fpanel):
    p, fake, _ = fpanel
    p.toggle_fx_visible()
    assert p._spectrum_timer.isActive()
    p.hide()
    assert not p._spectrum_timer.isActive()
    calls = []
    fake.latest_block = lambda: calls.append(1)
    p._spectrum_tick()   # 안전망: 숨겨졌으면 계산하지 않는다
    assert calls == []
    p.show()
    assert p._spectrum_timer.isActive()
    p.showMinimized()
    assert not p._spectrum_timer.isActive()
    p.showNormal()
    assert p._spectrum_timer.isActive()


def test_fx_state_survives_restart(qapp):
    fx = FxSettings.from_dict({"enabled": True, "preset": "발라드"})
    store = {"player_fx": fx.to_dict(), "player_tab": "fx"}
    p, fake, _ = make_panel(store)
    try:
        assert p.fx_strip.isVisible() and p.fx_strip.enabled_box.isChecked()
        assert p.fx_strip.preset_combo.currentText() == "발라드"
        assert fake.effects.preset == "발라드"
        p.view_menu.aboutToShow.emit()
        assert p.tab == "fx"
    finally:
        p.shutdown(); p.deleteLater()


def test_spectrum_timer_only_when_visible(fpanel):
    p, *_ = fpanel
    p.set_tab("playlist")
    assert not p._spectrum_timer.isActive()
    p.shortcuts["Ctrl+E"].activated.emit()
    assert p._spectrum_timer.isActive() and p._spectrum_timer.interval() == 40
    p.set_mini(True)   # 미니 막대에도 이퀄라이저가 있다
    assert p._spectrum_timer.isActive()
    p.set_mini(False)
    assert p._spectrum_timer.isActive()
    p.shortcuts["Ctrl+E"].activated.emit()   # 지금 재생 탭에도 막대가 있다
    assert p.tab == "now" and p._spectrum_timer.isActive()
    p.set_tab("radio")
    assert not p._spectrum_timer.isActive()


def test_track_change_updates_strip_genre(qapp, tmp_path):
    from funplayer.core.taginfo import TrackInfo
    genres = {"01 a.mp3": "Rock", "02 b.mp3": "Jazz"}
    reader = lambda path: TrackInfo(path, genre=genres.get(os.path.basename(path), ""))
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), runner=FakeRunner(),
                    read_info=reader)
    p.resize(380, 560); p.show()
    try:
        fx = FxSettings().with_preset("발라드").with_auto(True)
        p.controller.set_effects(fx); p.fx_strip.set_value(fx)
        p.controller.open([str(make_songs(tmp_path, ["01 a.mp3", "02 b.mp3"]))])
        p.refresh()
        assert "록" in p.fx_strip.preset_combo.currentText()
        p.next(); p.refresh()
        assert "재즈" in p.fx_strip.preset_combo.currentText()
    finally:
        p.shutdown(); p.deleteLater()


def test_spectrum_falls_when_paused(fpanel, monkeypatch):
    import numpy as np
    import funplayer.ui.player_panel as pp
    p, fake, _ = fpanel
    p.toggle_fx_visible()
    clock = [100.0]
    monkeypatch.setattr(pp.time, "monotonic", lambda: clock[0])
    fake.has_track = True
    fake.state = pp.State.PLAYING
    t = np.arange(4096) / 44100
    fake.block = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32).reshape(-1, 1).repeat(2, 1)
    p._spectrum_tick()
    clock[0] += 0.04
    p._spectrum_tick()
    top = p.fx_strip.spectrum.levels[:]
    assert max(top) > 0.3
    fake.state = pp.State.PAUSED
    fake.block = None
    prev = max(top)
    for _ in range(5):
        clock[0] += 0.04
        p._spectrum_tick()
        cur = max(p.fx_strip.spectrum.levels)
        assert cur < prev
        prev = cur
