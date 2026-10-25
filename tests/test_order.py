# tests/test_order.py
import random
from fakes import FakeRng
from funplayer.core.order import PlayOrder

def walk(o, start, wrap=False, limit=50):
    seen, cur = [start], start
    while len(seen) < limit and (cur := o.next(cur, wrap)) is not None:
        seen.append(cur)
    return seen

def shuffled5():
    o = PlayOrder(FakeRng()); o.rebuild(5, 2); o.set_shuffle(True, 2)
    return o                                          # order [2, 4, 3, 1, 0]

def test_sequential():
    o = PlayOrder(); o.rebuild(3, None)
    assert o.order == [0, 1, 2] and o.first() == 0 and not o.shuffle
    assert (o.next(0, False), o.next(2, False), o.next(2, True)) == (1, None, 0)
    assert (o.prev(1, False), o.prev(0, False), o.prev(0, True)) == (0, None, 2)
    assert o.next(None, True) is None and o.prev(None, True) is None

def test_shuffle_on_puts_current_first_and_off_restores():
    o = shuffled5()
    assert o.order == [2, 4, 3, 1, 0] and o.shuffle
    o.set_shuffle(False, 2); assert o.order == [0, 1, 2, 3, 4]

def test_shuffle_one_pass_then_stop_or_wrap():
    o = PlayOrder(FakeRng()); o.set_shuffle(True, None); o.rebuild(5, None)
    assert o.order == [4, 3, 2, 1, 0] and walk(o, 4) == [4, 3, 2, 1, 0]
    assert o.next(0, True) == 4

def test_real_rng_visits_every_track_once():
    o = PlayOrder(random.Random(7)); o.set_shuffle(True, None); o.rebuild(20, None)
    assert sorted(walk(o, o.first())) == list(range(20))

def test_shuffle_prev_goes_back_and_never_wraps():
    o = shuffled5()
    assert o.prev(3, True) == 4 and o.prev(2, True) is None

def test_wrap_reshuffles_with_chosen_first():
    o = shuffled5()
    o.moved_to(0, o.next(0, True))
    assert o.order == [2, 0, 1, 3, 4]

def test_pick_later_track_goes_next():
    o = shuffled5(); o.moved_to(4, 0)
    assert o.order == [2, 4, 0, 3, 1] and o.prev(0, False) == 4

def test_pick_earlier_track_goes_next():
    o = shuffled5(); o.moved_to(1, 2)
    assert o.order == [4, 3, 1, 2, 0] and o.prev(2, False) == 1

def test_adjacent_moves_change_nothing():
    o = shuffled5(); o.moved_to(4, 3); o.moved_to(3, 4); o.moved_to(4, 4)
    assert o.order == [2, 4, 3, 1, 0]

def test_first_pick_without_current_moves_to_front():
    o = PlayOrder(FakeRng()); o.set_shuffle(True, None); o.rebuild(3, None)   # [2, 1, 0]
    o.moved_to(None, 0); assert o.order == [0, 2, 1]

def test_extend():
    s = PlayOrder(); s.rebuild(2, None); s.extend(4, 0)
    assert s.order == [0, 1, 2, 3] and s.first_of([3, 2]) == 2
    o = shuffled5(); o.extend(7, 4)
    assert o.order == [2, 4, 5, 6, 3, 1, 0] and o.first_of([6, 5]) == 5

def test_remap():
    s = PlayOrder(); s.rebuild(4, None); s.remap([0, None, 1, 2]); assert s.order == [0, 1, 2]
    o = shuffled5(); o.remap([None, 0, 1, None, 2]); assert o.order == [1, 2, 0]
    o.remap([2, 0, 1]); assert o.order == [0, 1, 2]
