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
from funplayer.ui.colors import INFO_COLOR
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
    p.tab_bar.setCurrentIndex(1)
    assert p.station_view.isVisible() and not p.playlist_view.isVisible() and runner.pending == []
    assert p.add_url_button.isVisible() and not p.open_button.isVisible() and p.count_label.text() == "방송 42개"
    assert not p.add_button.isVisible() and not p.list_button.isVisible() and p.view_button.isVisible()
    assert p.settings.tab == "radio"
    p.tab_bar.setCurrentIndex(0); assert p.open_button.isVisible() and p.settings.tab == "playlist"
    assert not p.add_url_button.isVisible() and p.count_label.text() == "0곡"
    assert runner.calls == [] and fake.loaded == [] and fake.streams == []


def test_tab_bar_texts_and_ctrl_tab(rpanel):
    p, _, runner = rpanel
    assert [p.tab_bar.tabText(i) for i in range(p.tab_bar.count())] == ["재생목록", "라디오"]
    assert p.tab_bar.isVisible() and p.tab_bar.currentIndex() == 0
    p.shortcuts["Ctrl+Tab"].activated.emit(); assert p.tab_bar.currentIndex() == 1
    p.shortcuts["Ctrl+Tab"].activated.emit(); assert p.tab_bar.currentIndex() == 0
    assert runner.calls == []


def test_radio_tab_keeps_panel_narrow(rpanel):
    p, *_ = rpanel; p.set_tab("radio"); p.layout().activate()
    assert p.minimumSizeHint().width() < 380


def test_one_click_starts_station_and_live_row(rpanel):
    p, fake, runner = rpanel; p.set_tab("radio")
    p.station_view.station_activated.emit("kbs-25"); assert p.controller.status == "연결 중…"
    runner.finish(0, result=FakeStream()); p.refresh()
    assert p.title_label.toolTip() == "KBS 쿨FM" and p.live_label.text() == "● LIVE"
    assert not p.seek_slider.isVisible() and p.listened_label.text().startswith("들은 시간 ")
    assert not p.repeat_button.isEnabled() and not p.shuffle_button.isEnabled()
    assert p.live_label.isVisible() and p.listened_label.isVisible()
    assert not p.elapsed_label.isVisible() and not p.total_label.isVisible()
    assert p.play_button.toolTip() == "일시정지"
    assert station_item(p.station_view, "kbs-25").text(0).startswith("▶ ")


def test_live_color_follows_radio_state(rpanel):
    p, fake, runner = rpanel; p.set_tab("radio")
    p.station_view.station_activated.emit("kbs-25"); p.refresh()
    assert INFO_COLOR in p.live_label.styleSheet()
    runner.finish(0, result=FakeStream()); p.refresh()
    assert "#C5221F" in p.live_label.styleSheet()
    # B에 연결하는 동안 플레이어는 아직 라이브지만 표시는 라디오 상태를 따른다
    p.station_view.station_activated.emit("kbs-21"); p.refresh()
    assert fake.is_live and INFO_COLOR in p.live_label.styleSheet()


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
    seen = []
    orig = p.controller._set_status
    monkeypatch.setattr(p.controller, "_set_status", lambda m, e=False: (seen.append(m), orig(m, e)))
    p.add_url_button.click()
    assert seen == ["이미 목록에 있습니다", "연결 중…"]
    assert len(p.stations.groups()[-1][2]) == 1 and p.radio.current.name == "우리 동네"
    assert p.controller.status == "연결 중…"


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
    p.refresh()
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


def test_lost_signal_reaches_radio(rpanel):
    p, fake, runner = rpanel; connect(p, runner)
    fake.stream_lost = True; fake.on_lost(); QApplication.processEvents()
    assert p.radio.state is RadioState.RETRYING and len(runner.timers) == 1
    p.refresh(); assert "#C5221F" in p.live_label.styleSheet()


def test_mini_hides_radio_rows(rpanel):
    p, fake, runner = rpanel; connect(p, runner)
    p.set_mini(True)
    names = ("tab_bar", "station_view", "live_label", "listened_label", "add_url_button")
    assert not any(getattr(p, n).isVisible() for n in names) and not p.seek_slider.isVisible()
    p.refresh(); assert not any(getattr(p, n).isVisible() for n in names)
    p.set_mini(False)
    assert all(getattr(p, n).isVisible() for n in names)
    assert not p.playlist_view.isVisible() and not p.open_button.isVisible()


def test_station_info(rpanel):
    p, fake, runner = rpanel; connect(p, runner)
    p.shortcuts["Ctrl+I"].activated.emit(); d = p.info_dialog
    assert d.isVisible() and d.path_label.text() == "방송사 웹 재생 주소 (들을 때마다 새로 받음)"
    assert d.value_labels["제목"].text() == "KBS 쿨FM" and d.value_labels["가수"].text() == "KBS"
    connect(p, runner, "net-frisky"); p.show_track_info()
    assert p.info_dialog is d and d.path_label.text() == "http://stream2.friskyradio.com/frisky_mp3_hi"
    assert d.value_labels["가수"].text() == "미국"


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
        assert p.tab_bar.currentIndex() == 1 and p.station_view.isVisible() and runner.calls == []
    finally:
        p.shutdown(); p.deleteLater()


def test_restore_radio_session_no_network(qapp, tmp_path):
    songs = make_songs(tmp_path / "m", ["01 a.mp3"])
    session = tmp_path / "last.m3u8"; write_playlist(str(session), [str(songs / "01 a.mp3")])
    store = {"player_last_source": "radio", "player_last_station": "mbc-mfm",
             "player_last_track": str(songs / "01 a.mp3"), "player_last_position": 30.0}
    p, fake, runner = make_panel(store, session_path=str(session))
    try:
        assert p.tab_bar.currentIndex() == 1 and p.station_view.isVisible()
        assert p.controller.status == "이어 듣기: MBC FM4U" and runner.pending == [] and runner.calls == []
        assert fake.loaded == [] and p.title_label.toolTip() == "MBC FM4U"
        assert p.live_label.isVisible() and INFO_COLOR in p.live_label.styleSheet()
        assert p.play_button.toolTip() == "재생"
    finally:
        p.shutdown(); p.deleteLater()
