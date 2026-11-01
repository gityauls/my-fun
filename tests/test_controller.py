import os
import random
import pytest
from fakes import FakePlayer, make_songs
from funplayer.controller import EMPTY_TITLE, NO_FILES_MSG, PlayerController
from funplayer.core.effects import FxSettings
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

def test_controller_applies_saved_effects_on_start():
    fx = FxSettings().with_enabled(True).with_preset("팝")
    fake = FakePlayer()
    c = PlayerController(fake, Settings({"player_fx": fx.to_dict()}, lambda: None))
    assert fake.effects.preset == "팝" and fake.effects.enabled and c.effects == fx

def test_set_effects_save_flag():
    saved = []
    fake = FakePlayer(); store = {}
    c = PlayerController(fake, Settings(store, lambda: saved.append(1)))
    assert fake.effects == FxSettings() and "player_fx" not in store
    fx = FxSettings().with_enabled(True).with_preset("록")
    c.set_effects(fx, save=False)
    assert fake.effects == fx and "player_fx" not in store and not saved
    c.set_effects(fx)
    assert store["player_fx"] == fx.to_dict() and saved and c.effects == fx

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

def test_shuffle_repeat_all_reshuffles_every_lap(tmp_path):
    c, fake, _ = make_ctl({"player_shuffle": True, "player_repeat": "all"}, rng=random.Random(5))
    songs = [f"{i:02} s.mp3" for i in range(5)]
    c.open([str(make_songs(tmp_path, songs))])
    for _ in range(19):
        fake.finish(); c.on_track_end()
    got = names(fake)
    laps = [got[i:i + 5] for i in range(0, 20, 5)]
    assert len(got) == 20 and all(sorted(lap) == songs for lap in laps)
    assert len({lap[0] for lap in laps}) > 1
    assert all(a != b for a, b in zip(got, got[1:]))

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
    assert c.playlist.tracks[1].missing and names(fake) == ["03 c.mp3"]
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


def flaky(fake, broken):
    """broken 경로 집합에 든 파일은 열 때 DecodeError를 내게 한다 (고치면 집합에서 뺀다)."""
    from funplayer.engine.decoder import DecodeError
    orig = fake.load
    def load(path):
        if path in broken:
            fake.loaded.append(path); fake.has_track = False; fake.state = State.STOPPED
            raise DecodeError(path)
        orig(path)
    fake.load = load

def test_failed_track_recovers_and_is_not_removed_while_playing(ctl, tmp_path):
    c, fake, _ = ctl; m = make_songs(tmp_path, ["01 a.mp3", "02 b.mp3"]); broken = {str(m / "02 b.mp3")}
    flaky(fake, broken); c.open([str(m)])
    c.play_index(1); assert c.playlist.tracks[1].failed
    broken.clear(); c.play_index(1)
    assert not c.playlist.tracks[1].failed and c.state is State.PLAYING
    c.remove_unplayable()
    assert len(c.playlist) == 2 and c.state is State.PLAYING and c.playlist.current.title == "02 b"
    assert c.status == "지울 곡이 없습니다"

def test_missing_at_open_is_not_removed_after_files_return(ctl, tmp_path):
    c, fake, _ = ctl; m = tmp_path / "usb"; pl = tmp_path / "l.m3u8"
    write_playlist(str(pl), [str(m / n) for n in ABC])
    c.open([str(pl)])
    assert c.playlist.tracks[1].missing and c.playlist.tracks[2].missing
    make_songs(m, ABC)
    c.remove_unplayable()
    assert len(c.playlist) == 3 and c.status == "지울 곡이 없습니다"

@pytest.mark.parametrize("seed", range(30))
def test_shuffle_repeat_all_skip_finds_the_only_playable_track(tmp_path, seed):
    songs = [f"{i:02} bad.mp3" for i in range(6)]; songs[3] = "03 good.mp3"
    c, fake, _ = make_ctl({"player_shuffle": True, "player_repeat": "all"}, rng=random.Random(seed))
    c.open([str(make_songs(tmp_path, songs))])
    for k in (0, 1, 2, 4, 5):
        c.play_index(k)
        assert c.state is State.PLAYING and c.playlist.current.title == "03 good"

def test_remove_all_clears_status(ctl, tmp_path):
    c, *_ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    c.on_player_error("소리 장치를 열 수 없습니다"); c.remove([0, 1, 2])
    assert c.status == "" and not c.status_error

def test_value_errors_are_reported_not_raised(ctl, tmp_path, monkeypatch):
    import funplayer.controller as mod
    c, *_ = ctl; c.open([str(make_songs(tmp_path / "m", ABC))])
    def boom(*a, **k): raise ValueError("bad")
    monkeypatch.setattr(mod, "read_playlist", boom); monkeypatch.setattr(mod, "write_playlist", boom)
    c.open([str(tmp_path / "x.m3u8")])
    assert (c.status, c.status_error) == ("불러올 수 없음: x.m3u8", True) and len(c.playlist) == 3
    c.save_playlist(str(tmp_path / "y.m3u8"))
    assert (c.status, c.status_error) == ("저장할 수 없음: y.m3u8", True)

from funplayer.core.taginfo import TrackInfo

def counting_reader(calls):
    def read(path):
        calls.append(path)
        return TrackInfo(path, artist="Band", album=os.path.basename(path))
    return read

def info_ctl(calls):
    return PlayerController(FakePlayer(), Settings({}, lambda: None), read_info=counting_reader(calls))

def test_info_follows_current_track_and_reads_once(tmp_path):
    calls = []; c = info_ctl(calls)
    assert c.info is None and c.subtitle == "" and calls == []
    c.open([str(make_songs(tmp_path, ABC))])
    assert c.subtitle == "Band · 01 a.mp3"; c.info; c.info
    assert len(calls) == 1
    c.next()
    assert c.info.album == "02 b.mp3" and len(calls) == 2

def test_info_for_other_row_keeps_current_cache(tmp_path):
    calls = []; c = info_ctl(calls); c.open([str(make_songs(tmp_path, ABC))]); c.info
    assert c.info_for(2).album == "03 c.mp3" and len(calls) == 2
    assert c.info.album == "01 a.mp3" and c.info_for(0).album == "01 a.mp3" and len(calls) == 2

def test_info_cleared_with_list(tmp_path):
    calls = []; c = info_ctl(calls); c.open([str(make_songs(tmp_path, ABC))]); c.clear()
    assert c.info is None and c.subtitle == ""

def test_default_reader_handles_empty_files(ctl, tmp_path):
    c, *_ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    assert c.info.path.endswith("01 a.mp3") and c.info.title == "" and c.subtitle == ""

def test_notify_sets_info_status(ctl):
    c, *_ = ctl; c.notify("안내")
    assert (c.status, c.status_error) == ("안내", False)


def session_ctl(tmp_path, store=None, **kw):
    store = {} if store is None else store
    fake = FakePlayer(**kw)
    c = PlayerController(fake, Settings(store, lambda: None), session_path=str(tmp_path / "last.m3u8"))
    return c, fake, store

def saved_session(tmp_path, names, last, position, **store_extra):
    songs = make_songs(tmp_path / "m", names)
    paths = [str(songs / n) for n in names]
    write_playlist(str(tmp_path / "last.m3u8"), paths)
    store = {"player_last_track": str(songs / last), "player_last_position": position, **store_extra}
    return store, paths

def test_save_then_restore_cues_without_playing(tmp_path):
    c, fake, store = session_ctl(tmp_path); c.open([str(make_songs(tmp_path / "m", ABC))]); c.next()
    fake.position = 72.0; c.save_session()
    assert store["player_last_track"].endswith("02 b.mp3") and store["player_last_position"] == 72.0
    c2, fake2, _ = session_ctl(tmp_path, store); c2.restore_session()
    assert [os.path.basename(t.path) for t in c2.playlist.tracks] == ABC and c2.playlist.index == 1
    assert fake2.state is State.STOPPED and names(fake2) == ["02 b.mp3"] and fake2.seeks == [72.0]
    assert c2.cued and c2.can_seek and (c2.status, c2.status_error) == ("이어 듣기: 1:12부터", False)
    c2.toggle()
    assert fake2.state is State.PLAYING and len(fake2.loaded) == 1 and fake2.position == 72.0 and not c2.cued

def test_stop_after_restore_goes_back_to_start(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session(); c.stop()
    assert not c.cued and not c.can_seek and fake.position == 0.0
    c.toggle()
    assert len(fake.loaded) == 2 and fake.state is State.PLAYING

def test_seek_allowed_while_cued(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    c.seek_to(30.0); c.seek_by(1)
    assert fake.seeks == [72.0, 30.0, 35.0] and c.cued

@pytest.mark.parametrize("pos", [0.0, 176.0])
def test_zero_or_near_end_position_starts_from_beginning(tmp_path, pos):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", pos)   # FakePlayer 길이 180초
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    assert fake.seeks == [] and c.status == "" and c.cued and c.playlist.index == 1

def test_last_track_not_in_list_uses_first_without_position(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    store["player_last_track"] = str(tmp_path / "elsewhere" / "x.mp3")
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    assert c.playlist.index == 0 and fake.seeks == [] and c.status == ""

def test_duplicate_paths_pick_first_row(tmp_path):
    songs = make_songs(tmp_path / "m", ABC); a = str(songs / "01 a.mp3")
    write_playlist(str(tmp_path / "last.m3u8"), [a, str(songs / "02 b.mp3"), a])
    c, _, _ = session_ctl(tmp_path, {"player_last_track": a, "player_last_position": 10.0})
    c.restore_session()
    assert c.playlist.index == 0

def test_unplayable_last_track_is_marked_and_not_cued(tmp_path):
    store, _ = saved_session(tmp_path, ["01 a.mp3", "02 bad.mp3"], "02 bad.mp3", 30.0)
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    assert c.playlist.index == 1 and c.playlist.tracks[1].failed and not c.cued
    assert c.status == "" and len(fake.loaded) == 1

def test_restore_with_all_files_missing_is_quiet(tmp_path):
    store, paths = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    for p in paths:
        os.remove(p)
    c, fake, _ = session_ctl(tmp_path, store, missing_fails=True); c.restore_session()
    assert len(c.playlist) == 3 and all(t.missing for t in c.playlist.tracks)
    assert c.playlist.index == 1 and not c.cued and c.status == "" and len(fake.loaded) == 1

def test_shuffle_restore_starts_lap_at_last_track(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "03 c.mp3", 0.0, player_shuffle=True)
    c, _, _ = session_ctl(tmp_path, store); c.restore_session()
    assert c.playlist.index == 2 and c.playlist.order[0] == 2

@pytest.mark.parametrize("make", ["none", "dir", "garbage"])
def test_missing_or_broken_session_file(tmp_path, make):
    target = tmp_path / "last.m3u8"
    if make == "dir":
        target.mkdir()
    elif make == "garbage":
        target.write_bytes(b"\x00\xff\xfe junk")
    c, fake, _ = session_ctl(tmp_path, {"player_last_track": "x", "player_last_position": 5.0})
    c.restore_session()
    assert len(c.playlist) == 0 and fake.loaded == [] and c.status == "" and not c.cued

def test_list_and_track_changes_are_saved(tmp_path):
    c, fake, store = session_ctl(tmp_path); f = str(tmp_path / "last.m3u8")
    c.open([str(make_songs(tmp_path / "m", ABC))])
    assert [os.path.basename(p) for p in read_playlist(f)] == ABC
    assert store["player_last_track"].endswith("01 a.mp3") and store["player_last_position"] == 0.0
    c.next(); assert store["player_last_track"].endswith("02 b.mp3")
    c.remove([0]); assert len(read_playlist(f)) == 2
    c.sort("name"); c.move([1], 0)
    assert read_playlist(f) == [t.path for t in c.playlist.tracks]
    c.add([str(make_songs(tmp_path / "n", ["09 z.mp3"]))]); assert len(read_playlist(f)) == 3
    c.clear()
    assert not os.path.exists(f) and store["player_last_track"] == "" and store["player_last_position"] == 0.0

@pytest.mark.parametrize("prep,want", [("play", 50.0), ("pause", 50.0), ("stop", 0.0)])
def test_save_session_position(tmp_path, prep, want):
    c, fake, store = session_ctl(tmp_path); c.open([str(make_songs(tmp_path / "m", ABC))])
    fake.position = 50.0
    if prep == "pause": c.toggle()
    if prep == "stop": c.stop()
    c.save_session()
    assert store["player_last_position"] == want

def test_no_session_path_writes_nothing(ctl, tmp_path):
    c, _, store = ctl; c.open([str(make_songs(tmp_path / "m", ABC))]); c.save_session(); c.restore_session()
    assert "player_last_track" not in store and not list(tmp_path.glob("*.m3u8"))

def test_session_write_failure_is_silent(tmp_path, monkeypatch):
    import funplayer.controller as ctrl
    def boom(*a): raise OSError("disk full")
    monkeypatch.setattr(ctrl, "write_playlist", boom)
    c, fake, _ = session_ctl(tmp_path); c.open([str(make_songs(tmp_path / "m", ABC))])
    assert fake.state is State.PLAYING and not c.status_error

def test_add_and_kept_remove_keep_resume_position(tmp_path):
    c, fake, store = session_ctl(tmp_path); c.open([str(make_songs(tmp_path / "m", ABC))])
    fake.position = 50.0
    c.add([str(make_songs(tmp_path / "n", ["09 z.mp3"]))])
    assert store["player_last_position"] == 50.0 and c.state is State.PLAYING
    c.remove([2])
    assert store["player_last_position"] == 50.0 and store["player_last_track"].endswith("01 a.mp3")

def test_next_past_last_while_cued_ends_cue(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "03 c.mp3", 72.0)
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session(); assert c.cued
    c.next()
    assert not c.cued and not c.can_seek and fake.state is State.STOPPED

def test_seek_past_end_while_cued_ends_cue(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "03 c.mp3", 72.0)
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    fake.position = 175.0; c.seek_by(1)
    assert not c.cued and not c.can_seek

def test_add_while_cued_only_appends(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    c.add([str(make_songs(tmp_path / "n", ["09 z.mp3"]))])
    assert fake.state is State.STOPPED and c.cued and c.playlist.index == 1
    assert len(fake.loaded) == 1 and fake.position == 72.0 and len(c.playlist) == 4
    assert store["player_last_position"] == 72.0

def test_resume_notice_cleared_when_cue_ends_by_stop_or_seek(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    c, _, _ = session_ctl(tmp_path, dict(store)); c.restore_session()
    c.stop(); assert c.status == ""
    c, _, _ = session_ctl(tmp_path, dict(store)); c.restore_session()
    c.seek_to(30.0); assert c.status == ""
    c, fake, _ = session_ctl(tmp_path, dict(store)); c.restore_session()
    c.seek_by(1); assert c.status == ""

def test_resume_notice_kept_on_play_and_other_messages_kept(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    c, _, _ = session_ctl(tmp_path, dict(store)); c.restore_session()
    c.toggle(); assert c.status == "이어 듣기: 1:12부터"
    c, _, _ = session_ctl(tmp_path, dict(store)); c.restore_session()
    c.notify("안내"); c.stop(); assert c.status == "안내"

def test_failed_restore_keeps_saved_resume_pair(tmp_path):
    store, paths = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    for p in paths:
        os.remove(p)
    c, fake, _ = session_ctl(tmp_path, store, missing_fails=True); c.restore_session()
    last = store["player_last_track"]
    c.save_session()
    assert store["player_last_position"] == 72.0 and store["player_last_track"] == last
    c.sort("name"); c.remove([0])
    assert store["player_last_position"] == 72.0 and store["player_last_track"] == last
    c.play_index(0); c.save_session()
    assert store["player_last_position"] != 72.0

@pytest.mark.parametrize("drop", ["open", "remove_current"])
def test_failed_restore_hold_dropped(tmp_path, drop):
    store, paths = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    for p in paths:
        os.remove(p)
    c, fake, _ = session_ctl(tmp_path, store, missing_fails=True); c.restore_session()
    if drop == "open": c.open([str(make_songs(tmp_path / "n", ["09 z.mp3"]))])
    if drop == "remove_current": c.remove([1])
    c.save_session()
    assert store["player_last_position"] == 0.0


from fakes import Closeable, FakeClock, FakeLivePlayer, FakeRunner
from funplayer.controller import RESUME_RADIO_MSG
from funplayer.core.stations import StationList
from funplayer.radio import RadioController, RadioState

def make_radio_ctl(store=None, session_path=None):
    store = {} if store is None else store
    fake, runner, clock = FakePlayer(), FakeRunner(), FakeClock()
    c = PlayerController(fake, Settings(store, lambda: None), session_path=session_path)
    r = RadioController(FakeLivePlayer(), StationList(), runner.run_async, clock.call_later, clock.now,
                        resolve=lambda st: st.key, open_stream=lambda url: url, notify=c.radio_notify)
    c.attach_radio(r)
    return c, fake, r, runner, store

@pytest.fixture
def radio_ctl():
    c, fake, r, runner, _ = make_radio_ctl()
    return c, fake, r, runner

def test_file_to_radio_and_back_resumes_position(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))]); fake.position = 50.0
    c.play_station("kbs-25"); runner.finish(0, result="A")
    assert c.source == "radio" and c.title == "KBS 쿨FM" and not c.can_seek
    assert not fake.has_track and c.radio_live and c.status == "KBS 쿨FM에 연결했습니다"
    c.play_index(0)
    assert c.source == "file" and r.state is RadioState.IDLE and not c.radio_live

def test_playlist_tab_play_returns_to_track_at_position(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))]); fake.position = 50.0
    c.play_station("kbs-25"); runner.finish(0, result="A"); c.toggle()      # 라디오 멈춤
    c.toggle_for_tab("playlist")
    assert c.source == "file" and fake.state is State.PLAYING and fake.seeks[-1] == 50.0

def test_radio_tab_toggle_reconnects(radio_ctl):
    c, fake, r, runner = radio_ctl
    c.play_station("kbs-25"); runner.finish(0, result="A"); c.toggle(); c.toggle_for_tab("radio")
    assert r.state is RadioState.CONNECTING

def test_next_prev_step_stations_while_radio(radio_ctl):
    c, fake, r, runner = radio_ctl
    c.play_station("kbs-21"); c.next(); assert r.current.id == "kbs-22"; c.prev(); assert r.current.id == "kbs-21"

def test_subtitle_shows_now_title(radio_ctl):
    c, fake, r, runner = radio_ctl
    c.play_station("kbs-25"); runner.finish(0, result="A")
    r._player.title = "곡"; assert c.subtitle == "지금: 곡"
    r._player.title = ""; assert c.subtitle == ""

def test_stop_and_seek_while_radio(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))])
    c.play_station("kbs-25"); runner.finish(0, result="A")
    c.seek_by(1); c.seek_to(30.0); assert fake.seeks == []
    c.stop()
    assert r.state is RadioState.IDLE and r.current.id == "kbs-25" and c.source == "radio" and c.status == ""

def test_toggle_pauses_radio_keeping_elapsed_and_stop_resets(radio_ctl):
    c, fake, r, runner = radio_ctl
    c.play_station("kbs-25"); runner.finish(0, result="A"); r._clock.__self__.advance(10)
    c.toggle(); assert r.state is RadioState.IDLE and r.elapsed == 10
    c.toggle(); runner.finish(1, result="B"); assert r.state is RadioState.LIVE and r.elapsed == 10
    c.stop(); assert r.state is RadioState.IDLE and r.elapsed == 0

def test_play_station_unknown_id_does_nothing(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))])
    c.play_station("no-such-station")
    assert c.source == "file" and fake.has_track and fake.state is State.PLAYING
    assert runner.pending == [] and r.current is None

def test_held_position_survives_trip_to_radio(tmp_path):
    store, paths = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    c, fake, r, runner, _ = make_radio_ctl(store, str(tmp_path / "last.m3u8"))
    fake.missing_fails = True
    os.remove(paths[1])
    c.restore_session(); assert not fake.has_track          # 지난 곡을 못 열었다: 위치만 지켜 둔다
    make_songs(tmp_path / "m", ["02 b.mp3"])                  # USB를 다시 꽂았다
    c.play_station("kbs-25"); runner.finish(0, result="A"); c.toggle()
    c.toggle_for_tab("playlist")
    assert fake.loaded[-1].endswith("02 b.mp3") and fake.seeks[-1] == 72.0

def test_return_near_track_end_starts_from_zero(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))]); fake.position = 177.0   # 180초 곡의 끝 3초 전
    c.play_station("kbs-25"); runner.finish(0, result="A"); c.toggle()
    c.toggle_for_tab("playlist")
    assert c.source == "file" and fake.state is State.PLAYING and fake.seeks == []

def test_return_seeks_before_playing(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))]); fake.position = 50.0
    c.play_station("kbs-25"); runner.finish(0, result="A"); c.toggle()
    states = []
    seek = fake.seek
    fake.seek = lambda sec: (states.append(fake.state), seek(sec))
    c.toggle_for_tab("playlist")
    assert states == [State.STOPPED] and fake.state is State.PLAYING and fake.position == 50.0

def test_pending_connection_is_dropped_when_track_starts(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))])
    c.play_station("kbs-25"); assert r.state is RadioState.CONNECTING
    c.play_index(1)
    closed = []
    runner.finish(0, result=Closeable(closed))
    assert closed == [1] and r.state is RadioState.IDLE and r._player.streams == []
    assert c.source == "file" and fake.loaded[-1].endswith("02 b.mp3") and fake.state is State.PLAYING

def test_playlist_tab_play_while_live_stops_radio_first(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))]); fake.position = 50.0
    c.play_station("kbs-25"); runner.finish(0, result="A")
    c.toggle_for_tab("playlist")                        # 라디오가 나오는 중이면 라디오를 멈춘다
    assert c.source == "radio" and r.state is RadioState.IDLE and fake.loaded[-1].endswith("01 a.mp3")
    c.toggle_for_tab("playlist")
    assert c.source == "file" and fake.state is State.PLAYING and fake.seeks[-1] == 50.0

def test_add_while_radio_live_does_not_start_track(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.play_station("kbs-25"); runner.finish(0, result="A")
    c.add([str(make_songs(tmp_path / "m", ABC))])
    assert c.source == "radio" and c.radio_live and fake.loaded == [] and len(c.playlist) == 3

def test_track_end_ignored_while_radio(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))])
    c.play_station("kbs-25"); runner.finish(0, result="A")
    c.on_track_end()
    assert c.source == "radio" and len(fake.loaded) == 1

def test_session_radio_round_trip_without_network(tmp_path):
    session = str(tmp_path / "last.m3u8")
    c, fake, r, runner, store = make_radio_ctl(session_path=session)
    c.open([str(make_songs(tmp_path / "m", ABC))]); fake.position = 50.0
    c.play_station("mbc-mfm"); runner.finish(0, result="A"); c.save_session()
    assert store["player_last_source"] == "radio" and store["player_last_station"] == "mbc-mfm"
    assert store["player_last_position"] == 50.0
    c2, fake2, r2, runner2, _ = make_radio_ctl(store=dict(store), session_path=session)
    c2.restore_session()
    assert c2.source == "radio" and r2.current.id == "mbc-mfm" and r2.state is RadioState.IDLE
    assert runner2.pending == [] and fake2.loaded == [] and len(c2.playlist) == 3
    assert (c2.status, c2.status_error) == (RESUME_RADIO_MSG.format(name="MBC FM4U"), False)
    assert c2.status == "이어 듣기: MBC FM4U"
    c2.toggle_for_tab("playlist")
    assert c2.source == "file" and fake2.loaded[-1].endswith("01 a.mp3") and fake2.seeks[-1] == 50.0
    assert fake2.state is State.PLAYING and runner2.pending == []

def test_save_session_while_radio_without_return_position_keeps_last(tmp_path):
    store, _ = saved_session(tmp_path, ["01 a.mp3", "02 bad.mp3"], "02 bad.mp3", 72.0)
    c, fake, r, runner, _ = make_radio_ctl(store, str(tmp_path / "last.m3u8"))
    c.restore_session(); assert not fake.has_track       # 지난 곡을 못 열어 곡이 열려 있지 않다
    c.play_station("kbs-25"); runner.finish(0, result="A"); c.sort("name"); c.save_session()
    assert store["player_last_position"] == 72.0 and store["player_last_track"].endswith("02 bad.mp3")
    assert store["player_last_source"] == "radio" and store["player_last_station"] == "kbs-25"

def test_restore_with_unknown_station_falls_back_to_file(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0,
                             player_last_source="radio", player_last_station="gone")
    c, fake, r, runner, _ = make_radio_ctl(store, str(tmp_path / "last.m3u8"))
    c.restore_session()
    assert c.source == "file" and c.cued and names(fake) == ["02 b.mp3"] and fake.seeks == [72.0]
    assert c.status == "이어 듣기: 1:12부터" and runner.pending == []

def test_without_radio_station_calls_do_nothing(ctl):
    c, fake, _ = ctl
    c.play_station("kbs-25"); c.toggle_for_tab("radio")
    assert c.source == "file" and not c.radio_live and fake.loaded == []


# --- 장르 자동 프리셋 ---
from funplayer.core.effects import PRESETS

def genre_ctl(genres, fx=None):
    """genres: {파일 이름: 장르}. 자동 켠 효과(기본 발라드)로 만든 컨트롤러."""
    def read(path):
        return TrackInfo(path, genre=genres.get(os.path.basename(path), ""))
    store = {}
    fake = FakePlayer()
    c = PlayerController(fake, Settings(store, lambda: None), read_info=read)
    c.set_effects(fx or FxSettings().with_preset("발라드").with_auto(True))
    return c, fake, store

def test_auto_uses_track_genre(tmp_path):
    c, fake, _ = genre_ctl({"01 a.mp3": "Rock"})
    c.open([str(make_songs(tmp_path, ["01 a.mp3"]))])
    assert fake.effects.bands == PRESETS["록"]

def test_auto_without_genre_uses_setting(tmp_path):
    c, fake, _ = genre_ctl({})
    c.open([str(make_songs(tmp_path, ["01 a.mp3"]))])
    assert fake.effects.bands == PRESETS["발라드"] and c.genre_preset is None

def test_next_track_switches_preset(tmp_path):
    c, fake, _ = genre_ctl({"01 a.mp3": "Rock", "02 b.mp3": "Ballad"})
    c.open([str(make_songs(tmp_path, ["01 a.mp3", "02 b.mp3"]))])
    assert fake.effects.bands == PRESETS["록"]
    c.next()
    assert fake.effects.bands == PRESETS["발라드"] and c.applied_preset == "발라드"

def test_radio_overseas_genre_and_domestic(radio_ctl):
    c, fake, r, runner = radio_ctl
    c.set_effects(FxSettings().with_preset("발라드").with_auto(True))
    c.play_station("net-somafm-groove-salad")
    assert fake.effects.bands == PRESETS["라운지"] and c.applied_preset == "라운지"
    c.play_station("kbs-25")
    assert fake.effects.bands == PRESETS["발라드"] and c.genre_preset is None

def test_sync_only_on_key_change(tmp_path):
    c, fake, _ = genre_ctl({"01 a.mp3": "Rock"})
    c.open([str(make_songs(tmp_path, ["01 a.mp3"]))])
    n = len(fake.sent_effects)
    assert c.sync_effects() is False and len(fake.sent_effects) == n

def test_sync_first_time_with_nothing_loaded():
    c, fake, _ = genre_ctl({})
    c._synced_key = c._UNSET
    assert c.sync_effects() is True and c.sync_effects() is False

def test_not_auto_ignores_genre(tmp_path):
    c, fake, _ = genre_ctl({"01 a.mp3": "Rock"}, FxSettings().with_preset("발라드"))
    c.open([str(make_songs(tmp_path, ["01 a.mp3"]))])
    assert fake.effects.bands == PRESETS["발라드"] and c.applied_preset == "발라드"

def test_set_effects_saves_user_settings_not_applied(tmp_path):
    c, fake, store = genre_ctl({"01 a.mp3": "Rock"})
    c.open([str(make_songs(tmp_path, ["01 a.mp3"]))])
    assert c.effects.bands == PRESETS["발라드"] and c.effects.auto
    assert fake.effects.bands == PRESETS["록"]


# --- 태그 저장/지우기 (5-A) ---
from funplayer.engine.tagwrite import KEEP, TagWriteError

def tag_ctl(tmp_path, genres=None, fail=False, names=("a.mp3", "b.mp3")):
    genres = genres if genres is not None else {}
    fake = FakePlayer()
    def read(path):
        return TrackInfo(path, genre=genres.get(os.path.basename(path), ""))
    def writer(path, fields=None, picture=KEEP):
        fake.calls.append(("write", path))
        if fail:
            raise TagWriteError("fail")
        if fields and "genre" in fields:
            genres[os.path.basename(path)] = fields["genre"]
    def clearer(path):
        fake.calls.append(("clear", path))
    c = PlayerController(fake, Settings({}, lambda: None), read_info=read,
                         write_tags=writer, clear_tags=clearer)
    folder = make_songs(tmp_path, list(names))
    c.open([str(folder)])
    fake.calls.clear()
    return c, fake, str(folder / names[0]), str(folder / names[-1])

def test_save_playing_reloads_at_position(tmp_path):
    c, fake, a, _ = tag_ctl(tmp_path)
    fake.position = 42.0
    info = c.save_tags(a, {"title": "x"})
    assert fake.calls == [("unload",), ("write", a), ("load", a), ("seek", 42.0), ("play",)]
    assert info.path == a

def test_save_paused_stays_paused(tmp_path):
    c, fake, a, _ = tag_ctl(tmp_path)
    fake.position = 10.0; fake.pause()
    fake.calls.clear()
    c.save_tags(a, {"title": "x"})
    assert fake.calls == [("unload",), ("write", a), ("load", a), ("seek", 10.0), ("play",), ("pause",)]
    assert fake.state is State.PAUSED and fake.position == 10.0 and c.can_seek
    fake.calls.clear()
    c.toggle()
    assert fake.state is State.PLAYING and fake.position == 10.0
    assert fake.calls == [("play",)]

def test_save_reload_failure_marks_failed(tmp_path):
    c, fake, a, _ = tag_ctl(tmp_path, names=("bad.mp3", "bad2.mp3"))
    fake.has_track = True; fake.state = State.PLAYING; fake.position = 3.0
    c.save_tags(a, {"title": "x"})
    assert c.playlist.tracks[0].failed and c.status_error and not c._cued

def test_save_other_file_no_reload(tmp_path):
    c, fake, a, b = tag_ctl(tmp_path)
    c.save_tags(b, {"title": "x"})
    assert fake.calls == [("write", b)]

def test_save_stopped_no_reload_when_unloaded(tmp_path):
    c, fake, a, _ = tag_ctl(tmp_path)
    fake.unload(); fake.calls.clear()
    c.save_tags(a, {"title": "x"})
    assert fake.calls == [("write", a)]

def test_save_cued_stays_cued_at_position(tmp_path):
    c, fake, a, _ = tag_ctl(tmp_path)
    fake.stop(); fake.position = 30.0; c._cued = True
    fake.calls.clear()
    c.save_tags(a, {"title": "x"})
    assert fake.calls == [("unload",), ("write", a), ("load", a), ("seek", 30.0)]
    assert fake.state is State.STOPPED and c._cued

def test_failed_save_still_reloads(tmp_path):
    c, fake, a, _ = tag_ctl(tmp_path, fail=True)
    fake.position = 5.0
    with pytest.raises(TagWriteError):
        c.save_tags(a, {"title": "x"})
    assert fake.calls == [("unload",), ("write", a), ("load", a), ("seek", 5.0), ("play",)]

def test_save_resyncs_genre(tmp_path):
    genres = {"a.mp3": "Rock"}
    c, fake, a, _ = tag_ctl(tmp_path, genres=genres)
    c.set_effects(FxSettings().with_preset("발라드").with_auto(True))
    assert fake.effects.bands == PRESETS["록"]
    c.save_tags(a, {"genre": "Ballad"})
    assert fake.effects.bands == PRESETS["발라드"]

def test_clear_tags_reloads(tmp_path):
    c, fake, a, _ = tag_ctl(tmp_path)
    fake.position = 7.0
    c.clear_tags(a)
    assert fake.calls == [("unload",), ("clear", a), ("load", a), ("seek", 7.0), ("play",)]

def test_save_radio_source_no_reload(tmp_path):
    c, fake, a, _ = tag_ctl(tmp_path)
    c.source = "radio"
    c.save_tags(a, {"title": "x"})
    assert fake.calls == [("write", a)]


# --- 저장하며 이름 바꾸기 / 되돌리기 (5-C) ---
from funplayer.controller import (RENAME_EXISTS, RENAME_FAILED, RENAME_PARTIAL, RENAME_PARTIAL_EXISTS, UNDO_DONE,
                                  UNDO_EXISTS, UNDO_FAILED, UNDO_MISSING)
from funplayer.core.renamer import RenameConflict, RenameError, RenameLog, rename_file

def rn_ctl(tmp_path, rename_file_fn=None, fail_write=False, names=("a.mp3", "b.mp3")):
    fake = FakePlayer()
    writes = []
    def writer(path, fields=None, picture=KEEP):
        writes.append(path)
        if fail_write:
            raise TagWriteError("fail")
    settings = Settings({}, lambda: None)
    c = PlayerController(fake, settings, read_info=lambda p: TrackInfo(p),
                         write_tags=writer, rename_log=RenameLog(None),
                         rename_file=rename_file_fn)
    folder = make_songs(tmp_path, list(names))
    c.open([str(folder)])
    fake.calls.clear()
    return c, fake, writes, settings, str(folder / names[0]), str(folder / "가수 - 제목.mp3")

def test_rename_playing_reloads_new_path(tmp_path):
    c, fake, writes, settings, a, new = rn_ctl(tmp_path)
    settings.last_track = a
    fake.position = 12.0
    out = c.save_and_rename(a, {"title": "제목"}, KEEP, new)
    assert fake.calls == [("unload",), ("load", new), ("seek", 12.0), ("play",)]
    assert fake.state is State.PLAYING and writes == [a]
    assert os.path.exists(new) and not os.path.exists(a)
    assert c.playlist.tracks[0].path == new and settings.last_track == new
    assert c.info.path == new and out.info.path == new and out.renamed_from == a and out.warning == ""
    assert c.last_rename() == (a, new)

def test_rename_paused_stays_paused(tmp_path):
    c, fake, _, _, a, new = rn_ctl(tmp_path)
    fake.position = 10.0; fake.pause(); fake.calls.clear()
    c.save_and_rename(a, {"title": "x"}, KEEP, new)
    assert fake.calls == [("unload",), ("load", new), ("seek", 10.0), ("play",), ("pause",)]
    assert fake.state is State.PAUSED

def test_rename_only_skips_tag_write(tmp_path):
    c, fake, writes, _, a, new = rn_ctl(tmp_path)
    out = c.save_and_rename(a, {}, KEEP, new)
    assert writes == [] and out.renamed_from == a and os.path.exists(new)

def test_conflict_writes_nothing(tmp_path):
    c, fake, writes, _, a, new = rn_ctl(tmp_path)
    open(new, "wb").write(b"other")
    before = open(a, "rb").read()
    with pytest.raises(RenameError) as e:
        c.save_and_rename(a, {"title": "x"}, KEEP, new)
    assert str(e.value) == RENAME_EXISTS.format(name="가수 - 제목.mp3")
    assert writes == [] and fake.calls == [] and open(a, "rb").read() == before
    assert c.last_rename() is None

def _boom(old, new):
    raise RenameError("busy")

def test_rename_failure_reloads_old_path(tmp_path):
    c, fake, writes, settings, a, new = rn_ctl(tmp_path, _boom)
    fake.position = 5.0
    out = c.save_and_rename(a, {"title": "x"}, KEEP, new)
    assert out.warning == RENAME_PARTIAL and out.renamed_from is None and out.info.path == a
    assert writes == [a] and fake.calls == [("unload",), ("load", a), ("seek", 5.0), ("play",)]
    assert c.playlist.tracks[0].path == a and c.last_rename() is None

def test_rename_only_failure_raises(tmp_path):
    c, fake, writes, _, a, new = rn_ctl(tmp_path, _boom)
    with pytest.raises(RenameError) as e:
        c.save_and_rename(a, {}, KEEP, new)
    assert str(e.value) == RENAME_FAILED and writes == []
    assert fake.calls == [("unload",), ("load", a), ("play",)]
    assert c.last_rename() is None

def test_tag_failure_no_rename(tmp_path):
    c, fake, writes, _, a, new = rn_ctl(tmp_path, fail_write=True)
    with pytest.raises(TagWriteError):
        c.save_and_rename(a, {"title": "x"}, KEEP, new)
    assert os.path.exists(a) and not os.path.exists(new)
    assert ("load", a) in fake.calls and c.last_rename() is None

def test_rename_updates_last_track(tmp_path):
    c, fake, _, settings, a, new = rn_ctl(tmp_path)
    c.playlist.add([os.path.join(os.path.dirname(a), "A.MP3")])   # 대소문자만 다른 중복 줄
    settings.last_track = os.path.join(os.path.dirname(a), "A.MP3")
    c.save_and_rename(a, {}, KEEP, new)
    assert [t.path for t in c.playlist.tracks if t.path == new] == [new, new]
    assert settings.last_track == new

def test_undo_roundtrip(tmp_path):
    c, fake, _, settings, a, new = rn_ctl(tmp_path)
    settings.last_track = a
    c.save_and_rename(a, {}, KEEP, new)
    fake.position = 3.0; fake.calls.clear()
    assert c.undo_rename() == (a, UNDO_DONE)
    assert os.path.exists(a) and not os.path.exists(new)
    assert fake.calls == [("unload",), ("load", a), ("seek", 3.0), ("play",)]
    assert c.playlist.tracks[0].path == a and settings.last_track == a
    assert c.last_rename() is None and c.status == UNDO_DONE and not c.status_error

def test_undo_missing_pops(tmp_path):
    c, fake, _, _, a, new = rn_ctl(tmp_path)
    c.save_and_rename(a, {}, KEEP, new)
    os.remove(new)
    assert c.undo_rename() == (None, UNDO_MISSING.format(name="가수 - 제목.mp3"))
    assert c.last_rename() is None and c.status_error

def test_undo_conflict_keeps_entry(tmp_path):
    c, fake, _, _, a, new = rn_ctl(tmp_path, rename_file)
    c.save_and_rename(a, {}, KEEP, new)
    open(a, "wb").write(b"other")
    assert c.undo_rename() == (None, UNDO_EXISTS.format(name="a.mp3"))
    assert c.last_rename() == (a, new) and c.status_error and os.path.exists(new)

def test_undo_other_error_keeps_entry(tmp_path):
    calls = []
    def flaky(old, new):
        calls.append(1)
        if len(calls) > 1:
            raise RenameError("busy")
        rename_file(old, new)
    c, fake, _, _, a, new = rn_ctl(tmp_path, flaky)
    c.save_and_rename(a, {}, KEEP, new)
    assert c.undo_rename() == (None, UNDO_FAILED)
    assert c.last_rename() == (a, new) and c.playlist.tracks[0].path == new

def test_undo_empty_log(tmp_path):
    c, *_ = rn_ctl(tmp_path)
    c._set_status("그대로", False)
    assert c.undo_rename() == (None, "") and c.status == "그대로"


def _toctou(old, new):
    raise RenameConflict(new)

def test_rename_toctou_conflict_after_tags_written(tmp_path):
    c, fake, writes, _, a, new = rn_ctl(tmp_path, _toctou)
    out = c.save_and_rename(a, {"title": "x"}, KEEP, new)
    assert out.warning == RENAME_PARTIAL_EXISTS and out.renamed_from is None and out.info.path == a
    assert writes == [a] and c.last_rename() is None

def test_rename_toctou_conflict_nothing_written(tmp_path):
    c, fake, writes, _, a, new = rn_ctl(tmp_path, _toctou)
    with pytest.raises(RenameError) as e:
        c.save_and_rename(a, {}, KEEP, new)
    assert str(e.value) == RENAME_EXISTS.format(name="가수 - 제목.mp3")
    assert writes == [] and c.last_rename() is None


# ---- 즐겨찾기 (5-B) ----
def ctitles(c):
    return [t.title for t in c.playlist.tracks]


def test_favorite_moves_to_top_without_touching_playback(ctl, tmp_path):
    c, fake, store = ctl
    c.open([str(make_songs(tmp_path, ABC + ["04 d.mp3"]))]); c.play_index(1)
    calls = len(fake.calls)
    assert c.set_favorite([2], True) == [0]
    assert c.set_favorite([3], True) == [1]                  # 다음 즐겨찾기는 앞 즐겨찾기 아래
    assert ctitles(c) == ["03 c", "04 d", "01 a", "02 b"]
    assert c.playlist.current.title == "02 b" and len(fake.calls) == calls   # 재생은 그대로
    assert [os.path.basename(p) for p in store["player_favorites"]] == ["03 c.mp3", "04 d.mp3"]


def test_unfavorite_returns_to_name_position(ctl, tmp_path):
    c, _, _ = ctl
    c.open([str(make_songs(tmp_path, ABC + ["04 d.mp3"]))])
    c.set_favorite([1], True); c.set_favorite([3], True)     # b, d, a, c
    assert c.set_favorite([0], False) == [2]                 # b 해제 -> a 다음
    assert ctitles(c) == ["04 d", "01 a", "02 b", "03 c"]


def test_toggle_favorite_all_or_nothing(ctl, tmp_path):
    c, _, _ = ctl
    c.open([str(make_songs(tmp_path, ABC))])
    c.toggle_favorite([0])
    assert c.is_favorite(c.playlist.tracks[0].path)
    c.toggle_favorite([0, 1])          # 하나라도 아니면 모두 넣기
    assert all(c.is_favorite(t.path) for t in c.playlist.tracks[:2])
    c.toggle_favorite([0, 1])          # 모두 즐겨찾기면 모두 빼기
    assert not any(c.is_favorite(t.path) for t in c.playlist.tracks)


def test_favorites_stay_on_top_after_open_sort_and_move(ctl, tmp_path):
    c, _, store = ctl
    folder = make_songs(tmp_path, ABC)
    store["player_favorites"] = [str(folder / "03 c.mp3")]
    c.open([str(folder)])
    assert ctitles(c)[0] == "03 c"
    c.sort("name")
    assert ctitles(c) == ["03 c", "01 a", "02 b"]
    new = c.move([0], 3)               # 즐겨찾기를 묶음 밖으로 끌어도 맨 위로 돌아온다
    assert ctitles(c)[0] == "03 c" and new == [0]


def test_rename_updates_favorites(ctl, tmp_path):
    c, _, store = ctl
    folder = make_songs(tmp_path, ABC)
    c.open([str(folder)]); c.set_favorite([0], True)
    c._rename_everywhere(str(folder / "01 a.mp3"), str(folder / "가수 - a.mp3"))
    assert store["player_favorites"] == [str(folder / "가수 - a.mp3")]


def test_save_and_load_favorites(ctl, tmp_path):
    c, _, store = ctl
    folder = make_songs(tmp_path, ABC)
    c.open([str(folder)]); c.set_favorite([2], True); c.set_favorite([1], True)   # c, a 차례
    out = tmp_path / "fav"
    c.save_favorites(str(out))
    assert (tmp_path / "fav.m3u8").exists() and c.status.startswith("저장했습니다")
    store["player_favorites"] = []
    c.open([str(folder / "02 b.mp3")])
    c.load_favorites(str(tmp_path / "fav.m3u8"))
    assert ctitles(c) == ["03 c", "01 a", "02 b"] and c.status == "즐겨찾기 2곡을 불러왔습니다"


def test_save_favorites_empty_is_error(ctl, tmp_path):
    c, _, _ = ctl
    c.save_favorites(str(tmp_path / "x.m3u8"))
    assert c.status == "즐겨찾기한 곡이 없습니다" and not (tmp_path / "x.m3u8").exists()
