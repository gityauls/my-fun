import os
import random
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


def make_ctl(store=None, rng=None):
    fake = FakePlayer(); store = {} if store is None else store
    return PlayerController(fake, Settings(store, lambda: None), rng=rng), fake, store

def test_cycle_repeat_saves(ctl):
    c, _, store = ctl; seen = []
    for _ in range(3):
        c.cycle_repeat(); seen.append(c.repeat)
    assert seen == ["all", "one", "off"] and store["player_repeat"] == "off"

def test_repeat_one_replays_on_end_only(ctl, tmp_path):
    c, fake, store = ctl; c.open([str(make_songs(tmp_path, ABC))]); store["player_repeat"] = "one"
    fake.finish(); c.on_track_end(); assert names(fake) == ["01 a.mp3", "01 a.mp3"]
    c.next(); assert names(fake)[-1] == "02 b.mp3"
    c.play_index(2); c.next(); assert names(fake)[-1] == "01 a.mp3"

def test_stale_end_ignored_with_repeat_one(ctl, tmp_path):
    c, fake, store = ctl; c.open([str(make_songs(tmp_path, ABC))]); store["player_repeat"] = "one"
    c.on_track_end(); assert len(fake.loaded) == 1

def test_repeat_all_wraps_both_ways(ctl, tmp_path):
    c, fake, store = ctl; c.open([str(make_songs(tmp_path, ABC))]); store["player_repeat"] = "all"
    fake.position = 1.0; c.prev(); assert names(fake)[-1] == "03 c.mp3"
    fake.finish(); c.on_track_end(); assert names(fake)[-1] == "01 a.mp3"
    c.play_index(2); c.next(); assert names(fake)[-1] == "01 a.mp3"

@pytest.mark.parametrize("shuffle", [False, True])
def test_repeat_all_with_all_failed_stops(tmp_path, shuffle):
    c, fake, _ = make_ctl({"player_repeat": "all", "player_shuffle": shuffle}, rng=random.Random(1))
    c.open([str(make_songs(tmp_path, ["01 bad.mp3", "02 bad.mp3", "03 bad.mp3"]))])
    assert c.state is State.STOPPED and len(fake.loaded) == 3

def test_shuffle_plays_every_track_once_then_stops(tmp_path):
    c, fake, _ = make_ctl({"player_shuffle": True}, rng=random.Random(5))
    songs = [f"{i:02} s.mp3" for i in range(8)]
    c.open([str(make_songs(tmp_path, songs))])
    for _ in range(7):
        fake.finish(); c.on_track_end()
    assert sorted(names(fake)) == songs and c.state is State.PLAYING
    fake.finish(); c.on_track_end(); assert c.state is State.STOPPED

def test_shuffle_with_repeat_all_starts_new_lap(tmp_path):
    c, fake, _ = make_ctl({"player_shuffle": True, "player_repeat": "all"}, rng=random.Random(5))
    c.open([str(make_songs(tmp_path, [f"{i:02} s.mp3" for i in range(4)]))])
    for _ in range(8):
        fake.finish(); c.on_track_end()
    got = names(fake)
    assert len(got) == 9 and sorted(got[4:8]) == sorted(got[:4]) and c.state is State.PLAYING

def test_shuffle_prev_returns_to_previous(tmp_path):
    c, fake, _ = make_ctl({"player_shuffle": True}, rng=random.Random(3))
    c.open([str(make_songs(tmp_path, [f"{i:02} s.mp3" for i in range(6)]))])
    c.next(); c.next(); fake.position = 1.0; c.prev()
    assert names(fake)[-1] == names(fake)[1]

def test_toggle_shuffle_saves_and_keeps_current(ctl, tmp_path):
    c, fake, store = ctl; c.open([str(make_songs(tmp_path, ABC))]); c.play_index(1)
    c.toggle_shuffle()
    assert store["player_shuffle"] is True and c.shuffle and c.playlist.order[0] == 1
    assert c.state is State.PLAYING and len(fake.loaded) == 2
    c.toggle_shuffle(); assert c.playlist.order == [0, 1, 2]

def test_shuffle_setting_applied_at_start():
    c, *_ = make_ctl({"player_shuffle": True}); assert c.playlist.shuffle

def test_status_kinds(ctl, tmp_path):
    c, *_ = ctl
    c.on_player_error("소리 장치를 열 수 없습니다"); assert c.status_error
    c.open([str(tmp_path / "none")]); assert c.status == NO_FILES_MSG and c.status_error
    c.open([str(make_songs(tmp_path / "m", ABC))]); assert (c.status, c.status_error) == ("", False)


from funplayer.core.m3u import read_playlist, write_playlist

def test_open_playlist_keeps_file_order_and_marks_missing(ctl, tmp_path):
    c, fake, _ = ctl; m = make_songs(tmp_path / "m", ABC); pl = tmp_path / "l.m3u8"
    write_playlist(str(pl), [str(m / "03 c.mp3"), str(m / "ghost.mp3"), str(m / "01 a.mp3")])
    c.open([str(pl)])
    assert [t.title for t in c.playlist.tracks] == ["03 c", "ghost", "01 a"]
    assert c.playlist.tracks[1].failed and names(fake) == ["03 c.mp3"]
    assert (c.status, c.status_error) == ("없는 파일 1곡", False)

def test_add_mixed_drop_music_first_then_playlist(ctl, tmp_path):
    c, *_ = ctl; m = make_songs(tmp_path / "m", ABC); pl = tmp_path / "l.m3u"
    write_playlist(str(pl), [str(m / "02 b.mp3")])
    c.add([str(pl), str(m / "03 c.mp3")])
    assert [t.title for t in c.playlist.tracks] == ["03 c", "02 b"]

def test_folder_scan_ignores_playlist_files(ctl, tmp_path):
    c, *_ = ctl; m = make_songs(tmp_path / "m", ABC); write_playlist(str(m / "l.m3u8"), [str(m / "01 a.mp3")])
    c.open([str(m)]); assert len(c.playlist) == 3

def test_unreadable_and_empty_playlist(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path / "m", ABC))])
    c.open([str(tmp_path / "none.m3u8")])
    assert len(c.playlist) == 3 and (c.status, c.status_error) == ("불러올 수 없음: none.m3u8", True)
    empty = tmp_path / "e.m3u8"; write_playlist(str(empty), [])
    c.add([str(empty)]); assert c.status == NO_FILES_MSG and len(c.playlist) == 3

def test_save_playlist(ctl, tmp_path):
    c, *_ = ctl; m = make_songs(tmp_path / "m", ABC); c.open([str(m)])
    c.save_playlist(str(tmp_path / "내 목록"))
    assert read_playlist(str(tmp_path / "내 목록.m3u8")) == [str(m / n) for n in ABC]
    assert (c.status, c.status_error) == ("저장했습니다: 내 목록.m3u8", False)
    c.save_playlist(str(tmp_path / "no" / "x.m3u8"))
    assert (c.status, c.status_error) == ("저장할 수 없음: x.m3u8", True)

@pytest.mark.parametrize("prep,playing_after", [("play", True), ("pause", False), ("stop", False)])
def test_remove_current(ctl, tmp_path, prep, playing_after):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    if prep == "pause": c.toggle()
    if prep == "stop": c.stop()
    c.remove([0])
    assert c.playlist.current.title == "02 b" and (c.state is State.PLAYING) is playing_after
    if playing_after:
        assert names(fake)[-1] == "02 b.mp3"
    else:
        assert not fake.has_track and names(fake) == ["01 a.mp3"]
        c.toggle(); assert names(fake)[-1] == "02 b.mp3" and c.state is State.PLAYING

def test_remove_other_keeps_playing(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    c.remove([2]); assert c.state is State.PLAYING and len(fake.loaded) == 1 and len(c.playlist) == 2

def test_remove_last_current_stops_on_previous(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))]); c.play_index(2)
    c.remove([2]); assert c.state is State.STOPPED and c.playlist.current.title == "02 b"

def test_remove_all_is_like_clear(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))]); c.remove([0, 1, 2])
    assert len(c.playlist) == 0 and not fake.has_track and c.title == EMPTY_TITLE

def test_remove_duplicates(ctl, tmp_path):
    c, *_ = ctl; m = make_songs(tmp_path, ABC); c.open([str(m)])
    c.add([str(m / "01 a.mp3"), str(m / "02 b.mp3")])
    c.remove_duplicates()
    assert len(c.playlist) == 3 and (c.status, c.status_error) == ("중복 곡 2개를 지웠습니다", False)
    c.remove_duplicates(); assert c.status == "중복 곡이 없습니다"

def test_remove_unplayable(ctl, tmp_path):
    c, fake, _ = ctl; m = make_songs(tmp_path, ["01 a.mp3", "02 bad.mp3", "03 c.mp3"]); c.open([str(m)])
    c.play_index(1)
    os.remove(m / "01 a.mp3")
    c.remove_unplayable()
    assert [t.title for t in c.playlist.tracks] == ["03 c"] and c.state is State.PLAYING
    assert (c.status, c.status_error) == ("2곡을 지웠습니다", False)
    c.remove_unplayable(); assert c.status == "지울 곡이 없습니다"

def test_sort_and_move_keep_playing(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    assert c.move([0], 3) == [2]
    assert [t.title for t in c.playlist.tracks] == ["02 b", "03 c", "01 a"]
    assert c.playlist.current.title == "01 a"
    c.sort("name"); assert [t.title for t in c.playlist.tracks] == ["01 a", "02 b", "03 c"]
    assert c.state is State.PLAYING and len(fake.loaded) == 1
