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
