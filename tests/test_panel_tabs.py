import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from fakes import FakePlayer, FakeRunner, FakeStream, make_songs
from funplayer.core.settings import Settings
from funplayer.core.themes import get_theme
from funplayer.engine.player import State
from funplayer.ui.player_panel import ART_MINI, ART_NORMAL, SHORTCUTS, TAB_TITLES, TABS, PlayerPanel

ABC = ["01 a.mp3", "02 b.mp3", "03 c.mp3"]


def build(store=None, **kw):
    fake, runner = FakePlayer(), FakeRunner()
    p = PlayerPanel(Settings({} if store is None else store, lambda: None),
                    player=fake, runner=runner, **kw)
    p.resize(380, 620); p.show()
    return p, fake, runner


@pytest.fixture
def panel(qapp):
    p, *_ = build()
    yield p
    p.shutdown(); p.deleteLater()


@pytest.fixture
def panel_with_tracks(qapp, tmp_path):
    p, *_ = build()
    p.controller.open([str(make_songs(tmp_path / "m", ABC))]); p.refresh()
    yield p
    p.shutdown(); p.deleteLater()


@pytest.fixture
def panel_on_radio(qapp):
    p, fake, runner = build()
    p.set_tab("radio"); p.station_view.station_activated.emit("kbs-25")
    runner.finish(len(runner.calls) - 1, result=FakeStream()); p.refresh()
    p.set_tab("now")
    yield p
    p.shutdown(); p.deleteLater()


@pytest.fixture
def panel_playing(panel_with_tracks):
    return panel_with_tracks


def favorites(panel):
    return [t for t in panel.controller.playlist.tracks if panel.controller.is_favorite(t.path)]


def test_constants():
    assert TABS == ("now", "playlist", "radio", "fx")
    assert TAB_TITLES == ("지금 재생", "재생목록", "라디오", "음향 효과")
    assert (ART_NORMAL, ART_MINI) == (216, 80)


def test_four_tabs_and_default_now(panel):
    assert panel.tab == "now" and panel.tab_bar.count() == 4
    assert panel.pages.currentWidget().objectName() == "pageNow"
    assert panel.objectName() == "root"


@pytest.mark.parametrize("name,page", [("playlist", "pagePlaylist"), ("radio", "pageRadio"), ("fx", "pageFx")])
def test_set_tab_shows_page_and_strip(panel, name, page):
    panel.set_tab(name)
    assert panel.pages.currentWidget().objectName() == page
    assert not panel.now_strip.isHidden()


def test_now_tab_hides_strip(panel):
    assert panel.now_strip.isHidden()
    panel.set_tab("playlist"); panel.set_tab("now")
    assert panel.now_strip.isHidden()


def test_tab_click_changes_page(panel):
    panel.tab_bar.setCurrentIndex(1)
    assert panel.tab == "playlist" and panel.settings.tab == "playlist"
    assert panel.playlist_view.isVisible() and not panel.art_label.isVisible()


def test_sizes(panel):
    assert panel.tab_bar.height() == 64
    assert (panel.play_button.width(), panel.play_button.height()) == (60, 60)
    assert panel.art_label.width() == ART_NORMAL == panel.art_label.height()
    assert panel.play_button.property("kind") == "play"
    assert panel.heart_button.property("kind") == "fav"
    assert panel.open_button.property("kind") == "btn" and panel.view_button.property("kind") == "btn"
    assert panel.artist_label.property("role") == "mute"


def test_stop_lives_in_source_menu(panel):
    texts = [a.text() for a in panel.source_menu.actions()]
    assert "정지" in texts and "라디오로" in texts and not hasattr(panel, "stop_button")


def test_source_menu_follows_source(panel_on_radio):
    assert "MP3로" in [a.text() for a in panel_on_radio.source_menu.actions()]


def test_source_menu_stop_and_switch(panel_with_tracks):
    p = panel_with_tracks
    p.actions["stop"].trigger()
    assert p._player.state is State.STOPPED
    p.actions["switch"].trigger()
    assert p.controller.source == "radio" and p.tab == "now"     # 지금 재생 탭은 그대로 둔다


@pytest.mark.parametrize("attr", ["play_button", "title_label"])
def test_right_click_opens_source_menu(panel, attr, monkeypatch):
    seen = []
    monkeypatch.setattr(panel.source_menu, "exec_", lambda pos: seen.append(pos))
    w = getattr(panel, attr)
    assert w.contextMenuPolicy() == Qt.CustomContextMenu
    w.customContextMenuRequested.emit(w.rect().center())
    assert len(seen) == 1


def test_stop_shortcut_still_works(panel_with_tracks):
    p = panel_with_tracks
    assert dict(SHORTCUTS)["V"] == "stop"
    p.shortcuts["V"].activated.emit()
    assert p._player.state is State.STOPPED


def test_heart_toggles_current_track(panel_with_tracks):
    panel = panel_with_tracks
    panel.controller.play_index(1); panel.refresh()
    current = panel.controller.playlist.current
    panel.heart_button.click()
    assert panel.heart_button.isChecked()
    assert panel.controller.playlist.current is current          # 맨 위로 올라가도 같은 곡
    assert panel.controller.playlist.index == 0
    assert current.path in {t.path for t in favorites(panel)}
    panel.heart_button.click()
    assert not panel.heart_button.isChecked() and favorites(panel) == []
    assert panel.controller.playlist.current is current


def test_heart_disabled_without_track(panel):
    assert not panel.heart_button.isEnabled()


def test_heart_on_radio_toggles_station(panel_on_radio):
    panel_on_radio.heart_button.click()
    assert panel_on_radio.stations.is_favorite(panel_on_radio.radio.current.id)
    assert panel_on_radio.heart_button.isChecked()
    panel_on_radio.heart_button.click()
    assert not panel_on_radio.stations.is_favorite("kbs-25")
    assert not panel_on_radio.heart_button.isChecked()


def test_heart_on_radio_saves_and_regroups(qapp, tmp_path):
    path = tmp_path / "s.json"
    p, fake, runner = build(stations_path=str(path))
    try:
        p.set_tab("radio"); p.station_view.station_activated.emit("kbs-25")
        runner.finish(len(runner.calls) - 1, result=FakeStream()); p.refresh()
        p.set_tab("now"); p.heart_button.click()
        assert path.exists() and "kbs-25" in path.read_text(encoding="utf-8")
        assert p.station_view.topLevelItem(0).data(0, Qt.UserRole + 1) == "favorites"
    finally:
        p.shutdown(); p.deleteLater()


def test_ctrl_e_toggles_fx_tab(panel):
    panel.toggle_fx_visible(); assert panel.tab == "fx"
    panel.toggle_fx_visible(); assert panel.tab == "now"
    assert "fx_visible" not in panel.actions


def test_fx_strip_lives_in_fx_page(panel):
    page = panel.pages.widget(3)
    assert page.objectName() == "pageFx" and page.isAncestorOf(panel.fx_strip)
    assert not panel.fx_strip.isVisible()
    panel.set_tab("fx"); assert panel.fx_strip.isVisible()


def test_spectrum_runs_only_on_fx_tab(panel_playing):
    panel_playing.set_tab("now"); assert not panel_playing._spectrum_wanted()
    panel_playing.set_tab("fx");  assert panel_playing._spectrum_wanted()
    assert panel_playing._spectrum_timer.isActive()


def test_strip_shows_current_track_and_buttons_work(panel_with_tracks):
    p = panel_with_tracks; p.set_tab("playlist"); p.refresh()
    s = p.now_strip
    assert s.title_label.toolTip() == "01 a" and s.toggle_button.toolTip() == "일시정지"
    s.next_button.click(); assert p.controller.playlist.index == 1
    assert s.title_label.toolTip() == "02 b"
    s.prev_button.click(); assert p.controller.playlist.index == 0
    s.toggle_button.click(); assert p._player.state is State.PAUSED
    s.openClicked.emit()
    assert p.info_dialog is not None and p.info_dialog.isVisible()
    p.info_dialog.close()


def test_strip_on_radio_shows_live(panel_on_radio):
    p = panel_on_radio; p.set_tab("playlist"); p.refresh()
    assert p.now_strip.sub_label.text() == "● LIVE" and p.now_strip.progress.ratio == 1.0


def test_strip_ratio_follows_position(panel_with_tracks):
    p = panel_with_tracks; p._player.position = 90.0; p.refresh()
    assert p.now_strip.progress.ratio == pytest.approx(0.5)


def test_ctrl_tab_cycles_four_tabs(panel):
    seen = []
    for _ in range(4):
        panel.shortcuts["Ctrl+Tab"].activated.emit(); seen.append(panel.tab)
    assert seen == ["playlist", "radio", "fx", "now"]


def test_ctrl_d_on_now_tab_toggles_current(panel_with_tracks):
    p = panel_with_tracks; p.select_rows([2])
    p.shortcuts["Ctrl+D"].activated.emit()
    assert [t.path for t in favorites(p)] == [p.controller.playlist.current.path]


def test_ctrl_d_on_playlist_tab_uses_selected_rows(panel_with_tracks):
    p = panel_with_tracks; p.set_tab("playlist"); p.select_rows([2])
    p.shortcuts["Ctrl+D"].activated.emit()
    assert [t.title for t in favorites(p)] == ["03 c"]


def test_ctrl_d_on_radio_and_fx_tabs_does_nothing(panel_with_tracks):
    p = panel_with_tracks
    for tab in ("radio", "fx"):
        p.set_tab(tab); p.shortcuts["Ctrl+D"].activated.emit()
    assert favorites(p) == []


def test_list_shortcuts_ignored_off_the_playlist_tab(panel_with_tracks):
    p = panel_with_tracks; p.select_rows([1])
    p.shortcuts["Delete"].activated.emit()
    assert len(p.controller.playlist) == 3
    p.shortcuts["Return"].activated.emit()
    assert p.controller.playlist.index == 0


def test_view_button_moves_with_tab(panel):
    panel.set_tab("playlist")
    assert panel.view_button.isVisible() and panel.pages.currentWidget().isAncestorOf(panel.view_button)
    assert panel.count_label.isVisible()
    panel.set_tab("radio")
    assert panel.view_button.isVisible() and panel.pages.currentWidget().isAncestorOf(panel.view_button)
    assert panel.count_label.isVisible() and panel.add_url_button.isVisible()
    panel.set_tab("playlist")
    assert panel.view_button.isVisible() and not panel.add_url_button.isVisible()


@pytest.mark.parametrize("tab", TABS)
def test_status_shows_on_every_tab_and_takes_no_space_when_empty(panel, tab):
    panel.set_tab(tab); panel.refresh()
    assert panel.status_label.isHidden()
    panel.controller.notify("안내"); panel.refresh()
    assert panel.status_label.isVisible() and panel.status_label.text() == "안내"
    panel.controller.notify(""); panel.refresh()
    assert panel.status_label.isHidden()


def test_status_sits_above_strip(panel):
    lay = panel.layout()
    assert lay.indexOf(panel.pages) < lay.indexOf(panel.status_label) < lay.indexOf(panel.now_strip)


def test_live_row_on_radio(panel_on_radio):
    p = panel_on_radio
    assert p.live_label.isVisible() and p.listened_label.isVisible() and not p.seek_slider.isVisible()


def test_apply_theme_rebuilds(panel_with_tracks):
    p = panel_with_tracks
    assert p.theme.id == "light"
    before = p.art_label.pixmap().toImage()
    btn = p.prev_button.icon().pixmap(21, 21).toImage()
    p.apply_theme(get_theme("dark"))
    assert p.theme.id == "dark" and "#1C1D2F" in p.styleSheet()
    assert p.art_label.pixmap().toImage() != before
    assert p.prev_button.icon().pixmap(21, 21).toImage() != btn


def test_theme_from_settings_at_start(qapp):
    p, *_ = build({"player_theme": "dark"})
    try:
        assert p.theme.id == "dark" and "#1C1D2F" in p.styleSheet()
    finally:
        p.shutdown(); p.deleteLater()


def test_refresh_never_restyles_or_rebuilds_art(panel_with_tracks, monkeypatch):
    import funplayer.ui.player_panel as pp
    p = panel_with_tracks; calls = []
    monkeypatch.setattr(pp, "rounded_art", lambda *a: calls.append(a))
    monkeypatch.setattr(p, "apply_theme", lambda t: calls.append(t))
    p.refresh(); p.refresh()
    assert calls == []


def test_art_rebuilt_on_track_change_only(panel_with_tracks, monkeypatch):
    import funplayer.ui.player_panel as pp
    p = panel_with_tracks; calls = []; real = pp.rounded_art
    monkeypatch.setattr(pp, "rounded_art", lambda *a: calls.append(a[1]) or real(*a))
    p.next(); p.refresh()
    assert sorted(calls) == [40, ART_NORMAL]


def test_mini_works_on_new_structure(panel_with_tracks):
    p = panel_with_tracks; p.set_tab("playlist")
    p.controller.notify("안내"); p.set_mini(True); p.refresh()
    assert p.status_label.isHidden()
    assert p.pages.currentWidget().objectName() == "pageNow"
    assert p.now_strip.isHidden() and not p.tab_bar.isVisible() and p.art_label.width() == ART_MINI
    assert p.art_label.isVisible() and p.play_button.width() == 36
    p.layout().activate()
    assert p.sizeHint().height() < 160
    p.set_mini(False); p.refresh()
    assert p.tab == "playlist" and p.pages.currentWidget().objectName() == "pagePlaylist"
    assert p.art_label.width() == ART_NORMAL and p.play_button.width() == 60
    assert not p.now_strip.isHidden()


def test_real_key_reaches_shortcut_on_now_tab(panel_with_tracks, qapp):
    p = panel_with_tracks
    p.activateWindow(); assert QTest.qWaitForWindowActive(p)
    assert qapp.focusWidget() is not None
    QTest.keyClick(qapp.focusWidget(), Qt.Key_V)
    assert p._player.state is State.STOPPED


def test_real_key_reaches_shortcut_on_fx_tab(panel_with_tracks, qapp):
    p = panel_with_tracks; p.set_tab("fx")
    p.activateWindow(); assert QTest.qWaitForWindowActive(p)
    assert qapp.focusWidget() is not None
    QTest.keyClick(qapp.focusWidget(), Qt.Key_V)
    assert p._player.state is State.STOPPED
