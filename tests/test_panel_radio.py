import json

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from fakes import FakePlayer, FakeRunner, FakeStream, make_songs
from funplayer.core.m3u import write_playlist
from funplayer.core.settings import Settings
from funplayer.engine.decoder import DecodeError
from funplayer.engine.player import State
from funplayer.radio import RadioState
from funplayer.ui.style import hero_theme
from funplayer.ui.player_panel import PlayerPanel
from funplayer.ui.radio_dialogs import AddUrlDialog

URL = "https://s.example/a.mp3"


def make_panel(store=None, **kw):
    fake, runner = FakePlayer(), FakeRunner()
    p = PlayerPanel(Settings({} if store is None else store, lambda: None),
                    player=fake, runner=runner, **kw)
    p.resize(380, 480); p.show()
    return p, fake, runner


@pytest.fixture
def rpanel(qapp):
    p, fake, runner = make_panel()
    yield p, fake, runner
    p.shutdown(); p.deleteLater()


def station_item(view, sid):
    for i in range(view.topLevelItemCount()):
        top = view.topLevelItem(i)
        for j in range(top.childCount()):
            if top.child(j).data(0, Qt.UserRole) == sid:
                return top.child(j)
    return None


def connect(p, runner, sid="kbs-25"):
    p.set_tab("radio"); p.station_view.station_activated.emit(sid)
    runner.finish(len(runner.calls) - 1, result=FakeStream()); p.refresh()


def test_tab_switch_never_touches_network(rpanel):
    p, fake, runner = rpanel
    p.tab_bar.setCurrentIndex(2)
    assert p.station_view.isVisible() and not p.playlist_view.isVisible() and runner.pending == []
    assert p.add_url_button.isVisible() and not p.open_button.isVisible() and p.count_label.text() == "방송 72개"
    assert not p.add_button.isVisible() and not p.list_button.isVisible() and p.view_button.isVisible()
    assert p.settings.tab == "radio"
    p.tab_bar.setCurrentIndex(1); assert p.open_button.isVisible() and p.settings.tab == "playlist"
    assert not p.add_url_button.isVisible() and p.count_label.text() == "0곡"
    assert runner.calls == [] and fake.loaded == [] and fake.streams == []


def test_tab_bar_texts_and_ctrl_tab(rpanel):
    p, _, runner = rpanel
    assert [p.tab_bar.tabText(i) for i in range(p.tab_bar.count())] == ["지금 재생", "재생목록", "라디오", "음향 효과"]
    assert p.tab_bar.isVisible() and p.tab_bar.currentIndex() == 0
    p.shortcuts["Ctrl+Tab"].activated.emit(); assert p.tab_bar.currentIndex() == 1
    p.shortcuts["Ctrl+Tab"].activated.emit(); assert p.tab_bar.currentIndex() == 2
    assert runner.calls == []


def test_radio_tab_keeps_panel_narrow(rpanel):
    p, *_ = rpanel; p.set_tab("radio"); p.layout().activate()
    assert p.minimumSizeHint().width() < 380


def test_one_click_starts_station_and_live_row(rpanel):
    p, fake, runner = rpanel; p.set_tab("radio")
    p.station_view.station_activated.emit("kbs-25"); assert p.controller.status == "연결 중…"
    runner.finish(0, result=FakeStream()); p.refresh()
    assert p.title_label.toolTip() == "KBS 쿨FM" and p.live_label.text() == "● LIVE"
    p.set_tab("now")
    assert not p.seek_slider.isVisible() and p.listened_label.text().startswith("들은 시간 ")
    assert not p.repeat_button.isEnabled() and not p.shuffle_button.isEnabled()
    assert p.live_label.isVisible() and p.listened_label.isVisible()
    assert not p.elapsed_label.isVisible() and not p.total_label.isVisible()
    assert p.play_button.toolTip() == "일시정지"
    assert station_item(p.station_view, "kbs-25").text(0).startswith("▶ ")


def test_live_color_follows_radio_state(rpanel):
    p, fake, runner = rpanel; p.set_tab("radio")
    p.station_view.station_activated.emit("kbs-25"); p.refresh()
    assert hero_theme(p.theme).mute in p.live_label.styleSheet()
    runner.finish(0, result=FakeStream()); p.refresh()
    assert hero_theme(p.theme).acc_t in p.live_label.styleSheet()
    # B에 연결하는 동안 플레이어는 아직 라이브지만 표시는 라디오 상태를 따른다
    p.station_view.station_activated.emit("kbs-21"); p.refresh()
    assert fake.is_live and hero_theme(p.theme).mute in p.live_label.styleSheet()


def test_failure_is_gray_hint(rpanel):
    p, fake, runner = rpanel; p.station_view.station_activated.emit("kbs-25"); runner.finish(0, error=DecodeError("x")); p.refresh()
    assert p.status_label.toolTip() == "지금은 이 방송을 들을 수 없습니다. 다른 방송을 골라 보세요" and not p.controller.status_error
    assert p.play_button.toolTip() == "재생"


def test_add_url_flow(rpanel, monkeypatch):
    p, fake, runner = rpanel; p.set_tab("radio")

    def fake_exec(dialog):
        dialog._value = ("우리 동네", URL)
        return 1
    monkeypatch.setattr(AddUrlDialog, "exec_", fake_exec)
    p.add_url_button.click()
    key, title, members = p.stations.groups()[-1]
    assert key == "user" and [s.name for s in members] == ["우리 동네"]
    view = p.station_view
    assert view.topLevelItem(view.topLevelItemCount() - 1).text(0) == "직접 넣은 방송"
    assert p.controller.status == "연결 중…" and len(runner.pending) == 1
    assert p.radio.current.name == "우리 동네"

    p.radio.stop()
    calls = len(runner.calls)
    p.station_view.setCurrentItem(station_item(view, "kbs-21"))
    p.add_url_button.click()                       # 같은 주소: 그 줄을 고르고 안내만, 접속하지 않는다
    assert len(p.stations.groups()[-1][2]) == 1 and len(runner.calls) == calls
    assert p.radio.state is RadioState.IDLE
    assert (p.controller.status, p.controller.status_error) == ("이미 목록에 있습니다", False)
    assert view.currentItem().data(0, Qt.UserRole) == p.radio.current.id


def test_add_url_duplicate_of_builtin_opens_its_group(rpanel, monkeypatch):
    p, fake, runner = rpanel; p.set_tab("radio")
    monkeypatch.setattr(AddUrlDialog, "exec_",
                        lambda d: (setattr(d, "_value", ("x", "http://stream2.friskyradio.com/frisky_mp3_hi/")), 1)[1])
    p.add_url_button.click()
    item = station_item(p.station_view, "net-frisky")
    assert p.station_view.currentItem() is item and item.parent().isExpanded()
    assert runner.calls == [] and p.controller.status == "이미 목록에 있습니다"


def test_add_url_cancel_does_nothing(rpanel, monkeypatch):
    p, fake, runner = rpanel
    monkeypatch.setattr(AddUrlDialog, "exec_", lambda d: 0)
    p.add_url()
    assert runner.calls == [] and p.stations.groups()[-1][0] != "user"


def test_playlist_tab_play_button_returns_to_track(rpanel, tmp_path):
    p, fake, runner = rpanel
    p.controller.open([str(make_songs(tmp_path / "m", ["01 a.mp3", "02 b.mp3"]))])
    fake.position = 50.0
    connect(p, runner)
    p.play_button.click(); assert p.radio.state is RadioState.IDLE
    p.refresh(); assert p.play_button.toolTip() == "재생"
    p.set_tab("playlist"); p.play_button.click()
    assert fake.loaded[-1].endswith("01 a.mp3") and fake.seeks[-1] == 50.0
    assert p.controller.source == "file" and fake.state is State.PLAYING
    p.refresh(); p.set_tab("now")
    assert p.seek_slider.isVisible() and p.elapsed_label.isVisible() and not p.live_label.isVisible()
    assert p.repeat_button.isEnabled() and p.shuffle_button.isEnabled()
    assert not station_item(p.station_view, "kbs-25").text(0).startswith("▶ ")


def test_space_on_radio_tab_stops_station(rpanel):
    p, fake, runner = rpanel; connect(p, runner)
    p.shortcuts["Space"].activated.emit()
    assert p.radio.state is RadioState.IDLE and runner.pending == []
    p.shortcuts["Space"].activated.emit()
    assert p.radio.state is RadioState.CONNECTING and len(runner.pending) == 1


def test_enter_on_radio_tab_plays_current_station(rpanel):
    p, fake, runner = rpanel; p.set_tab("radio")
    p.station_view.setCurrentItem(station_item(p.station_view, "mbc-sfm"))
    p.shortcuts["Return"].activated.emit()
    assert p.radio.current.id == "mbc-sfm" and len(runner.pending) == 1


def test_next_steps_station_while_radio(rpanel):
    p, fake, runner = rpanel; connect(p, runner, "kbs-21")
    p.next(); assert p.radio.current.id == "kbs-22"
    p.prev(); assert p.radio.current.id == "kbs-21"


def test_ctrl_arrows_step_stations_while_radio(rpanel):
    p, fake, runner = rpanel; connect(p, runner, "kbs-21")
    p.shortcuts["Ctrl+Right"].activated.emit(); assert p.radio.current.id == "kbs-22"
    p.shortcuts["Ctrl+Left"].activated.emit(); assert p.radio.current.id == "kbs-21"


def test_ctrl_arrows_reach_shortcut_from_station_view(rpanel):
    from PyQt5.QtTest import QTest
    p, fake, runner = rpanel; connect(p, runner, "kbs-21")
    p.activateWindow(); assert QTest.qWaitForWindowActive(p)
    p.station_view.setFocus()
    QTest.keyClick(p.station_view, Qt.Key_Right, Qt.ControlModifier)
    assert p.radio.current.id == "kbs-22"


def test_media_play_pause_follows_radio_not_tab(rpanel, tmp_path):
    p, fake, runner = rpanel
    p.controller.open([str(make_songs(tmp_path / "m", ["01 a.mp3"]))]); n = len(fake.loaded)
    connect(p, runner); p.set_tab("playlist")
    p.media_keys.play_pause_pressed.emit()
    assert p.radio.state is RadioState.IDLE and p.controller.source == "radio"
    p.media_keys.play_pause_pressed.emit()
    assert p.radio.state is RadioState.CONNECTING and len(fake.loaded) == n
    p.media_shortcuts[0].activated.emit()           # 창 안의 ⏯ 키도 같다
    assert p.radio.state is RadioState.IDLE and len(fake.loaded) == n


def test_mini_space_follows_radio_not_tab(rpanel, tmp_path):
    p, fake, runner = rpanel
    p.controller.open([str(make_songs(tmp_path / "m", ["01 a.mp3"]))]); n = len(fake.loaded)
    connect(p, runner); p.set_tab("playlist"); p.set_mini(True)
    p.shortcuts["Space"].activated.emit(); assert p.radio.state is RadioState.IDLE
    p.shortcuts["X"].activated.emit()
    assert p.radio.state is RadioState.CONNECTING and len(fake.loaded) == n


def test_play_button_on_playlist_tab_still_returns_to_track(rpanel, tmp_path):
    p, fake, runner = rpanel
    p.controller.open([str(make_songs(tmp_path / "m", ["01 a.mp3"]))]); n = len(fake.loaded)
    connect(p, runner); p.play_button.click(); p.set_tab("playlist")
    p.shortcuts["Space"].activated.emit()            # 보통 크기에서 Space는 탭을 따른다
    assert p.controller.source == "file" and len(fake.loaded) == n + 1


def test_lost_signal_reaches_radio(rpanel):
    p, fake, runner = rpanel; connect(p, runner)
    fake.stream_lost = True; fake.on_lost(); QApplication.processEvents()
    assert p.radio.state is RadioState.RETRYING and len(runner.timers) == 1
    p.refresh(); assert hero_theme(p.theme).acc_t in p.live_label.styleSheet()


def test_mini_hides_radio_rows(rpanel):
    p, fake, runner = rpanel; connect(p, runner)
    p.set_mini(True)
    names = ("tab_bar", "station_view", "add_url_button")
    live = ("live_label", "listened_label")
    assert not any(getattr(p, n).isVisible() for n in names) and not p.seek_slider.isVisible()
    assert all(getattr(p, n).isVisible() for n in live)
    p.refresh(); assert not any(getattr(p, n).isVisible() for n in names)
    assert all(getattr(p, n).isVisible() for n in live)
    p.set_mini(False)
    assert all(getattr(p, n).isVisible() for n in ("tab_bar", "station_view", "add_url_button"))
    assert not p.playlist_view.isVisible() and not p.open_button.isVisible()
    p.set_tab("now"); assert p.live_label.isVisible() and p.listened_label.isVisible()


def test_radio_mini_shows_live(rpanel, qapp):
    p, fake, runner = rpanel; connect(p, runner); p.set_mini(True); p.resize(680, 104); qapp.processEvents()
    p.refresh()
    assert p.mini_bar.isAncestorOf(p.live_label) and p.mini_bar.isAncestorOf(p.listened_label)
    assert p.live_label.isVisible() and p.listened_label.isVisible()
    assert not p.seek_slider.isVisible() and not p.elapsed_label.isVisible() and not p.total_label.isVisible()
    assert not p.shuffle_button.isEnabled() and not p.repeat_button.isEnabled()
    assert p.heart_button.isVisible() and p.heart_button.isEnabled()
    assert p.live_label.x() < p.listened_label.x()
    assert p.listened_label.geometry().right() == p.mini_info.width() - 1
    p.set_mini(False); p.set_tab("now")
    assert p.live_label.isVisible() and p.page_now.isAncestorOf(p.live_label)


def test_mini_live_mark_uses_the_bar_accent(rpanel):
    from funplayer.ui.style import mini_theme
    p, fake, runner = rpanel; connect(p, runner)
    p.set_mini(True)
    assert mini_theme(p.theme).acc_t in p.live_label.styleSheet()   # 어두운 막대에서도 보이게
    p.set_mini(False)
    assert hero_theme(p.theme).acc_t in p.live_label.styleSheet()


def test_radio_mini_shows_radio_art(rpanel, monkeypatch):
    import funplayer.ui.player_panel as pp
    p, fake, runner = rpanel; connect(p, runner); calls = []; real = pp.radio_art_for
    monkeypatch.setattr(pp, "radio_art_for", lambda *a: calls.append(a[1:]) or real(*a))
    p.set_mini(True)
    assert (80, 14) in calls and p.art_label.pixmap().width() == 80


def test_station_info(rpanel):
    p, fake, runner = rpanel; connect(p, runner)
    p.shortcuts["Ctrl+I"].activated.emit(); d = p.info_dialog
    assert d.isVisible() and d.path_label.text() == "방송사 웹 재생 주소 (들을 때마다 새로 받음)"
    assert d.value_labels["제목"].text() == "KBS 쿨FM" and d.value_labels["가수"].text() == "KBS"
    connect(p, runner, "net-frisky"); p.show_track_info()
    assert p.info_dialog is d and d.path_label.text() == "http://stream2.friskyradio.com/frisky_mp3_hi"
    assert d.value_labels["가수"].text() == "미국"


def test_station_info_sbs_uses_web_path_text(rpanel):
    p, fake, runner = rpanel; connect(p, runner, "sbs-powerfm"); p.show_track_info()
    assert p.info_dialog.path_label.text() == "방송사 웹 재생 주소 (들을 때마다 새로 받음)"


def test_shutdown_closes_radio_runner_and_player(qapp):
    p, fake, runner = make_panel(); connect(p, runner)
    p.station_view.station_activated.emit("kbs-21")   # 연결 중에 끈다
    p.shutdown()
    assert runner.closed and fake.closed and p.radio.state is RadioState.IDLE
    runner.finish(len(runner.calls) - 1, result=FakeStream())
    assert len(fake.streams) == 1
    p.deleteLater()


def test_stations_saved_on_change(qapp, tmp_path):
    path = tmp_path / "s.json"
    p, fake, runner = make_panel(stations_path=str(path))
    try:
        assert not path.exists()
        p.set_tab("radio")
        p.station_view.setCurrentItem(station_item(p.station_view, "kbs-25"))
        p.station_view.actions["favorite"].trigger()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["favorites"] == ["kbs-25"]
    finally:
        p.shutdown(); p.deleteLater()
    p2, *_ = make_panel(stations_path=str(path))
    try:
        assert p2.stations.is_favorite("kbs-25")
    finally:
        p2.shutdown(); p2.deleteLater()


def test_open_groups_saved_to_settings(rpanel):
    p, *_ = rpanel; p.set_tab("radio")
    view = p.station_view
    top = next(view.topLevelItem(i) for i in range(view.topLevelItemCount())
               if view.topLevelItem(i).text(0).startswith("해외 추천 · 재즈"))
    top.setExpanded(True)
    assert "genre:재즈" in p.settings.radio_open


def test_start_tab_from_settings(qapp):
    p, fake, runner = make_panel({"player_tab": "radio"})
    try:
        assert p.tab_bar.currentIndex() == 2 and p.station_view.isVisible() and runner.calls == []
    finally:
        p.shutdown(); p.deleteLater()


def test_restore_radio_session_no_network(qapp, tmp_path):
    songs = make_songs(tmp_path / "m", ["01 a.mp3"])
    session = tmp_path / "last.m3u8"; write_playlist(str(session), [str(songs / "01 a.mp3")])
    store = {"player_last_source": "radio", "player_last_station": "mbc-mfm",
             "player_last_track": str(songs / "01 a.mp3"), "player_last_position": 30.0}
    p, fake, runner = make_panel(store, session_path=str(session))
    try:
        assert p.tab_bar.currentIndex() == 2 and p.station_view.isVisible()
        assert p.controller.status == "이어 듣기: MBC FM4U" and runner.pending == [] and runner.calls == []
        assert fake.loaded == [] and p.title_label.toolTip() == "MBC FM4U"
        p.set_tab("now"); assert p.live_label.isVisible() and hero_theme(p.theme).mute in p.live_label.styleSheet()
        assert p.play_button.toolTip() == "재생"
    finally:
        p.shutdown(); p.deleteLater()


def test_rename_playing_station_updates_title(rpanel):
    p, fake, runner = rpanel; connect(p, runner)
    p.stations.rename("kbs-25", "쿨"); p.station_view.rebuild(); p.refresh()
    assert p.controller.title == "쿨" and p.title_label.toolTip() == "쿨"


def test_refresh_on_radio_tab_does_not_recount_stations(rpanel, monkeypatch):
    p, fake, runner = rpanel; p.set_tab("radio")
    calls = []
    orig = p.station_view.count
    monkeypatch.setattr(p.station_view, "count", lambda: (calls.append(1), orig())[1])
    for _ in range(3):
        p.refresh()
    assert calls == [] and p.count_label.text() == "방송 72개"


def test_queued_signals_after_shutdown_are_ignored(qapp):
    p, fake, runner = make_panel()
    connect(p, runner)
    p.shutdown()
    seen = []
    p.refresh = lambda: seen.append(1)
    fake.stream_lost = True
    p._bridge.lost.emit(); p._bridge.ended.emit(); p._bridge.error.emit("x")
    QApplication.processEvents()
    assert seen == [] and p.radio.state is RadioState.IDLE and p.controller.status != "x"
    p.deleteLater()


def test_ctrl_tab_key_reaches_shortcut_from_station_view(rpanel):
    from PyQt5.QtTest import QTest
    p, fake, runner = rpanel; p.set_tab("radio")
    p.activateWindow(); assert QTest.qWaitForWindowActive(p)
    p.station_view.setFocus()
    QTest.keyClick(p.station_view, Qt.Key_Tab, Qt.ControlModifier)
    assert p.tab_bar.currentIndex() == 3


def test_mini_switch_item_follows_source(rpanel, tmp_path):
    p, fake, runner = rpanel; switch = p.actions["switch"]
    p.set_mini(True); p.refresh()
    assert switch in p.source_menu.actions() and switch.text() == "라디오로"
    connect(p, runner); p.refresh()
    assert switch.text() == "MP3로" and not switch.isEnabled()   # 재생목록이 비었다
    p.set_mini(False); assert switch.text() == "MP3로"


def test_mini_switch_to_radio_plays_last_station_or_first(rpanel, tmp_path):
    p, fake, runner = rpanel
    p.set_mini(True)
    p.actions["switch"].trigger()   # 한 번도 듣지 않았다: 목록 맨 위 방송
    assert p.controller.source == "radio" and p.radio.current.id == "kbs-21" and len(runner.calls) == 1
    runner.finish(0, result=FakeStream()); p.refresh()
    assert p.radio.state is RadioState.LIVE and p.actions["switch"].text() == "MP3로"


def test_mini_switch_round_trip_resumes_track_and_station(rpanel, tmp_path):
    p, fake, runner = rpanel
    p.controller.open([str(make_songs(tmp_path / "m", ["01 a.mp3", "02 b.mp3"]))])
    fake.position = 50.0
    connect(p, runner, "sbs-powerfm")
    p.set_mini(True); p.refresh()
    p.actions["switch"].trigger()   # MP3로: 라디오를 끊고 듣던 곡 위치에서
    assert p.radio.state is RadioState.IDLE and p.controller.source == "file"
    assert fake.loaded[-1].endswith("01 a.mp3") and fake.seeks[-1] == 50.0 and fake.state is State.PLAYING
    assert p.actions["switch"].text() == "라디오로" and p.tab == "playlist"
    p.actions["switch"].trigger()   # 라디오로: 마지막 방송국
    assert p.controller.source == "radio" and p.radio.current.id == "sbs-powerfm" and p.tab == "radio"


def test_mini_switch_to_mp3_without_track_index_plays_first(rpanel, tmp_path):
    p, fake, runner = rpanel
    p.controller.open([str(make_songs(tmp_path / "m", ["01 a.mp3"]))])
    connect(p, runner)
    p.set_mini(True); p.refresh(); p.actions["switch"].trigger()
    assert p.controller.source == "file" and fake.loaded[-1].endswith("01 a.mp3") and fake.state is State.PLAYING
