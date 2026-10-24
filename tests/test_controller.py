import os
import pytest
from fakes import FakePlayer, make_songs
from funplayer.controller import EMPTY_TITLE, NO_FILES_MSG, PlayerController
from funplayer.core.settings import Settings
from funplayer.engine.player import State

@pytest.fixture
def ctl():
    store = {}
    fake = FakePlayer()
    return PlayerController(fake, Settings(store, lambda: None)), fake, store

def names(fake):
    return [os.path.basename(p) for p in fake.loaded]

ABC = ["01 a.mp3", "02 b.mp3", "03 c.mp3"]

def test_open_replaces_and_plays_first(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    assert len(c.playlist) == 3 and names(fake) == ["01 a.mp3"] and c.state is State.PLAYING
    assert c.title == "01 a"

def test_open_without_files_keeps_list(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path / "m", ABC))])
    c.open([str(tmp_path / "none")])
    assert len(c.playlist) == 3 and c.status == NO_FILES_MSG and len(fake.loaded) == 1

@pytest.mark.parametrize("prep,expect_new", [("stop", True), ("pause", False), ("play", False)])
def test_add_plays_only_when_stopped(ctl, tmp_path, prep, expect_new):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path / "m", ABC[:1]))])
    if prep == "stop": c.stop()
    if prep == "pause": c.toggle()
    c.add([str(make_songs(tmp_path / "n", ["09 z.mp3"]))])
    assert (names(fake)[-1] == "09 z.mp3") is expect_new and len(c.playlist) == 2

def test_toggle_cycle(ctl, tmp_path):
    c, fake, _ = ctl; c.toggle(); assert fake.loaded == []
    c.open([str(make_songs(tmp_path, ABC))])
    c.toggle(); assert c.state is State.PAUSED
    c.toggle(); assert c.state is State.PLAYING
    c.stop(); c.toggle()
    assert c.state is State.PLAYING and len(fake.loaded) == 2 and c.position == 0

def test_next_then_stop_at_last(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC[:2]))])
    c.next(); assert names(fake)[-1] == "02 b.mp3"
    c.next(); assert c.state is State.STOPPED and c.playlist.index == 1

@pytest.mark.parametrize("idx,pos,expected", [(1, 2.9, "01 a.mp3"), (1, 3.0, "02 b.mp3"), (0, 1.0, "01 a.mp3")])
def test_prev_rules(ctl, tmp_path, idx, pos, expected):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    c.play_index(idx); fake.position = pos; c.prev()
    assert names(fake)[-1] == expected

def test_track_end(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC[:2]))])
    fake.finish(); c.on_track_end(); assert names(fake)[-1] == "02 b.mp3"
    fake.finish(); c.on_track_end(); assert c.state is State.STOPPED and c.position == 0

def test_stale_track_end_ignored(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC[:2]))])
    c.on_track_end()
    assert c.playlist.index == 0 and len(fake.loaded) == 1 and c.state is State.PLAYING

def test_failed_track_skipped(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ["01 a.mp3", "02 bad.mp3", "03 c.mp3"]))])
    c.play_index(1)
    assert names(fake)[-1] == "03 c.mp3" and c.playlist.tracks[1].failed
    assert c.status == "열 수 없음: 02 bad.mp3"

def test_all_failed_stops(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ["01 bad.mp3", "02 bad.mp3"]))])
    assert c.state is State.STOPPED and all(t.failed for t in c.playlist.tracks)

def test_last_failed_stops(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ["01 a.mp3", "02 bad.mp3"]))])
    fake.finish(); c.on_track_end(); assert c.state is State.STOPPED

def test_status_cleared_on_next_play(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ["01 a.mp3", "02 bad.mp3", "03 c.mp3"]))])
    c.play_index(1); c.play_index(0); assert c.status == ""

def test_seek_by(ctl, tmp_path):
    c, fake, store = ctl; c.open([str(make_songs(tmp_path, ABC))])
    store["player_seek_step"] = 10
    fake.position = 50; c.seek_by(+1); assert fake.seeks[-1] == 60
    fake.position = 4; c.seek_by(-1); assert fake.seeks[-1] == 0
    fake.position = 175; c.seek_by(+1); assert names(fake)[-1] == "02 b.mp3"
    c.stop(); n = len(fake.seeks); c.seek_by(+1); c.seek_to(30); assert len(fake.seeks) == n

def test_seek_to_clamps(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    c.seek_to(999); assert fake.seeks[-1] == 180.0
    c.seek_to(-1); assert fake.seeks[-1] == 0

def test_volume_and_mute(ctl):
    c, fake, store = ctl
    assert fake.gain == pytest.approx(0.49)
    c.set_volume(150); assert store["player_volume"] == 100 and fake.gain == 1.0
    c.set_volume(50); assert fake.gain == pytest.approx(0.25)
    c.toggle_mute(); assert fake.gain == 0.0 and c.volume == 50 and store["player_muted"] is True
    c.set_volume(60); assert fake.gain == 0.0
    c.toggle_mute(); assert fake.gain == pytest.approx(0.36)

def test_initial_gain_from_settings():
    fake = FakePlayer()
    PlayerController(fake, Settings({"player_volume": 50, "player_muted": True}, lambda: None))
    assert fake.gain == 0.0

def test_clear(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))]); c.clear()
    assert len(c.playlist) == 0 and not fake.has_track and c.title == EMPTY_TITLE and c.duration == 0

def test_player_error_sets_status(ctl):
    c, *_ = ctl; c.on_player_error("소리 장치를 열 수 없습니다")
    assert c.status == "소리 장치를 열 수 없습니다"
