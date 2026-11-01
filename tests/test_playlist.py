import pytest
from funplayer.core.playlist import Playlist, Track

P = ["C:/m/01 a.mp3", "C:/m/02 b.mp3", "C:/m/03 c.mp3"]

def test_track_title():
    assert Track("C:/m/01 a.mp3").title == "01 a"

def test_replace_and_clear():
    pl = Playlist(); pl.replace(P)
    assert len(pl) == 3 and pl.index == 0 and pl.current.path == P[0]
    pl.replace([]); assert pl.index is None and pl.current is None
    pl.replace(P); pl.clear(); assert len(pl) == 0 and pl.index is None

def test_add_returns_first_new_index_and_keeps_current():
    pl = Playlist()
    assert pl.add(P[:1]) == 0 and pl.index is None
    pl.set_current(0)
    assert pl.add(P[1:]) == 1 and pl.index == 0
    assert pl.add([]) is None

def test_next_index():
    pl = Playlist(); assert pl.next_index() is None
    pl.replace(P); assert pl.next_index() == 1
    pl.set_current(2); assert pl.next_index() is None

@pytest.mark.parametrize("idx,pos,expected", [
    (1, 2.9, ("prev", 0)), (1, 3.0, ("restart", 1)), (0, 1.0, ("restart", 0))])
def test_prev_target(idx, pos, expected):
    pl = Playlist(); pl.replace(P); pl.set_current(idx)
    assert pl.prev_target(pos) == expected

def test_mark_failed_and_version_bumps():
    pl = Playlist(); v = pl.version
    pl.replace(P); pl.set_current(1); pl.mark_failed(2)
    assert pl.tracks[2].failed and not pl.tracks[1].failed
    pl.add(P[:1]); pl.clear()
    assert pl.version == v + 5

def test_set_current_out_of_range():
    pl = Playlist(); pl.replace(P)
    with pytest.raises(IndexError):
        pl.set_current(3)


from fakes import FakeRng

P5 = [f"C:/m/0{i} {c}.mp3" for i, c in enumerate("abcde")]

def titles(pl):
    return [t.title for t in pl.tracks]

def test_layout_version_only_on_structure():
    pl = Playlist(); pl.replace(P); lv, v = pl.layout_version, pl.version
    pl.set_current(1); pl.mark_failed(2); pl.set_shuffle(True)
    assert pl.layout_version == lv and pl.version == v + 2
    pl.add(P[:1]); pl.sort("name"); pl.move([0], 2); pl.remove([0]); pl.clear()
    assert pl.layout_version == lv + 5

def test_wrap_navigation():
    pl = Playlist(); pl.replace(P)
    pl.set_current(2); assert pl.next_index() is None and pl.next_index(wrap=True) == 0
    pl.set_current(0)
    assert pl.prev_target(1.0, wrap=True) == ("prev", 2) and pl.prev_target(1.0) == ("restart", 0)

def test_shuffle_replace_and_add():
    pl = Playlist(FakeRng()); pl.set_shuffle(True); pl.replace(P)        # order [2, 1, 0]
    assert pl.shuffle and pl.index == 2 and pl.next_index() == 1 and pl.order == [2, 1, 0]
    pl2 = Playlist(FakeRng()); pl2.replace(P); pl2.set_shuffle(True)     # order [0, 2, 1]
    assert pl2.add(["C:/m/x.mp3", "C:/m/y.mp3"]) == 3 and pl2.order == [0, 3, 4, 2, 1]

@pytest.mark.parametrize("rows,wrap,result,cur,left", [
    ([0], False, "kept", "02 c", "01 b,02 c,03 d,04 e"),
    ([2], False, "next", "03 d", "00 a,01 b,03 d,04 e"),
    ([2, 3], False, "next", "04 e", "00 a,01 b,04 e"),
    ([2, 3, 4], False, "stop", "01 b", "00 a,01 b"),
    ([4, 3, 2], True, "next", "00 a", "00 a,01 b"),
    ([0, 1, 2, 3, 4], False, "stop", None, ""),
    ([9], False, "kept", "02 c", "00 a,01 b,02 c,03 d,04 e"),
])
def test_remove(rows, wrap, result, cur, left):
    pl = Playlist(); pl.replace(P5); pl.set_current(2)
    assert pl.remove(rows, wrap=wrap) == result
    assert (pl.current.title if pl.current else None) == cur and ",".join(titles(pl)) == left

def test_remove_in_shuffle_follows_play_order():
    pl = Playlist(FakeRng()); pl.replace(P5); pl.set_current(2); pl.set_shuffle(True)  # [2,4,3,1,0]
    assert pl.remove([2]) == "next" and pl.current.title == "04 e"
    assert [pl.tracks[i].title for i in pl.order] == ["04 e", "03 d", "01 b", "00 a"]

def test_duplicate_indices_keep_current_or_first():
    pl = Playlist(); pl.replace(["C:/m/a.mp3", "C:/M/A.MP3", "C:/m/b.mp3", "C:/m/./a.mp3"])
    assert pl.duplicate_indices() == [1, 3]
    pl.set_current(3); assert pl.duplicate_indices() == [0, 1]

def test_unplayable_indices(tmp_path):
    real = tmp_path / "a.mp3"; real.write_bytes(b"")
    pl = Playlist(); pl.replace([str(real), str(tmp_path / "ghost.mp3"), str(real)]); pl.mark_failed(2)
    assert pl.unplayable_indices() == [1, 2]

def test_sort_keeps_current():
    pl = Playlist(); pl.replace(["C:/b/2 x.mp3", "C:/a/10 y.mp3", "C:/a/9 z.mp3"]); pl.set_current(1)
    pl.sort("path"); assert titles(pl) == ["9 z", "10 y", "2 x"] and pl.current.title == "10 y"
    assert pl.next_index() == 2
    pl.sort("name"); assert titles(pl) == ["2 x", "9 z", "10 y"] and pl.index == 2
    with pytest.raises(ValueError):
        pl.sort("size")

@pytest.mark.parametrize("rows,before,new_rows,left", [
    ([4], 0, [0], "04 e,00 a,01 b,02 c,03 d"),
    ([0, 1], 5, [3, 4], "02 c,03 d,04 e,00 a,01 b"),
    ([1, 3], 3, [2, 3], "00 a,02 c,01 b,03 d,04 e"),
    ([2], 2, [2], "00 a,01 b,02 c,03 d,04 e"),
])
def test_move(rows, before, new_rows, left):
    pl = Playlist(); pl.replace(P5); pl.set_current(2)
    assert pl.move(rows, before) == new_rows
    assert ",".join(titles(pl)) == left and pl.current.title == "02 c"

def test_remove_last_in_shuffle_with_wrap_picks_new_lap_head():
    pl = Playlist(FakeRng()); pl.set_shuffle(True); pl.replace(P5)       # order [4,3,2,1,0]
    for i in (3, 2, 1, 0): pl.set_current(i)
    assert pl.remove([0], wrap=True) == "next" and pl.current.title == "04 e"

def test_mark_ok_clears_flags_and_bumps_version_once():
    pl = Playlist(); pl.replace(P); pl.mark_failed(0); pl.mark_missing(0)
    assert pl.tracks[0].failed and pl.tracks[0].missing
    v = pl.version; pl.mark_ok(0)
    assert not pl.tracks[0].failed and not pl.tracks[0].missing and pl.version == v + 1
    pl.mark_ok(0); assert pl.version == v + 1

def test_rename_path_all_rows_casefold():
    pl = Playlist(); pl.replace([r"C:\a\x.mp3", r"c:\A\X.mp3", r"C:\a\y.mp3"])
    v, lv = pl.version, pl.layout_version
    assert pl.rename_path(r"C:\a\x.mp3", r"C:\a\new.mp3") == 2
    assert [t.path for t in pl.tracks] == [r"C:\a\new.mp3", r"C:\a\new.mp3", r"C:\a\y.mp3"]
    assert pl.version == v + 1 and pl.layout_version == lv

def test_rename_path_no_match_changes_nothing():
    pl = Playlist(); pl.replace(P)
    v = pl.version
    assert pl.rename_path(r"C:\zzz.mp3", r"C:\q.mp3") == 0 and pl.version == v


# ---- 즐겨찾기 묶음 (5-B) ----
def test_arrange_puts_favorites_on_top_in_favorite_order():
    pl = Playlist(); pl.replace(P5); pl.set_current(2)
    pl.arrange([P5[4], P5[1]])
    assert titles(pl) == ["04 e", "01 b", "00 a", "02 c", "03 d"]
    assert pl.current.title == "02 c"   # 지금 곡은 그대로


def test_arrange_matches_case_and_ignores_unknown_favorites():
    pl = Playlist(); pl.replace(P5)
    pl.arrange(["c:/M/03 D.mp3", "C:/m/zz.mp3"])
    assert titles(pl)[0] == "03 d"


def test_arrange_dropped_goes_to_name_position():
    pl = Playlist(); pl.replace(P5)
    pl.arrange([P5[3], P5[0]])                 # d, a, b, c, e
    pl.arrange([P5[0]], dropped=[P5[3]])       # d를 해제 -> 나머지 사이 이름순 자리
    assert titles(pl) == ["00 a", "01 b", "02 c", "03 d", "04 e"]


def test_arrange_dropped_korean_after_english_and_numbers():
    paths = ["C:/m/가 노래.mp3", "C:/m/1 one.mp3", "C:/m/b song.mp3", "C:/m/나 노래.mp3"]
    pl = Playlist(); pl.replace(paths); pl.sort("name")
    order = titles(pl)
    pl.arrange([paths[3]])
    pl.arrange([], dropped=[paths[3]])
    assert titles(pl) == order
