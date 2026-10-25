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

def test_wrap_reshuffles_whole_next_lap():
    o = shuffled5()
    nxt = o.next(0, True)
    assert nxt == 4 and o.next(0, True) == 4
    o.moved_to(0, nxt)
    assert o.order == [4, 3, 2, 1, 0]

def test_two_track_lap_never_repeats_last_track():
    o = PlayOrder(FakeRng()); o.set_shuffle(True, None); o.rebuild(2, 0)
    assert o.order == [0, 1] and o.next(1, True) == 0

def test_pick_first_by_hand_on_last_track_just_goes_next():
    o = shuffled5(); o.moved_to(0, 2)
    assert o.order == [4, 3, 1, 0, 2]

def test_upcoming():
    s = PlayOrder(); s.rebuild(5, None)
    assert s.upcoming(2, False) == [3, 4] and s.upcoming(2, True) == [3, 4, 0, 1]
    o = shuffled5()
    assert o.upcoming(3, False) == [1, 0] and o.upcoming(0, True) == [4, 3, 2, 1]
    assert o.upcoming(None, True) == [] and PlayOrder().upcoming(0, True) == []

def test_empty_and_single_order():
    o = PlayOrder(random.Random(1)); o.set_shuffle(True, None); o.rebuild(0, None)
    assert o.next(0, True) is None and o.upcoming(0, True) == []
    o.rebuild(1, None); assert o.next(0, True) == 0

def test_real_rng_keeps_order_a_permutation():
    rng = random.Random(3); o = PlayOrder(random.Random(3)); n = 12
    o.set_shuffle(True, None); o.rebuild(n, None); cur = o.first()
    for _ in range(200):
        act = rng.choice(["next", "pick", "extend", "remap", "toggle"])
        if act == "next":
            nxt = o.next(cur, True); o.moved_to(cur, nxt); cur = nxt
        elif act == "pick":
            nxt = rng.randrange(n); o.moved_to(cur, nxt); cur = nxt
        elif act == "extend":
            n += 2; o.extend(n, cur)
        elif act == "remap" and n > 3:
            drop = rng.randrange(n); mapping = []
            for i in range(n):
                mapping.append(None if i == drop else i - (i > drop))
            n -= 1; o.remap(mapping); cur = mapping[cur] if mapping[cur] is not None else o.first()
        elif act == "toggle":
            o.set_shuffle(not o.shuffle, cur)
            if not o.shuffle: o.set_shuffle(True, cur)
        assert sorted(o.order) == list(range(n))

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
