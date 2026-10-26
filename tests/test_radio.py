from __future__ import annotations

import pytest

from funplayer.core.stations import StationList
from funplayer.engine.decoder import DecodeError
from funplayer.engine.resolve import ResolveError
from funplayer.radio import RadioController, RadioState
from tests.fakes import Closeable, FakeClock, FakeLivePlayer, FakeRunner


@pytest.fixture
def radio():
    player, runner, clock, notes = FakeLivePlayer(), FakeRunner(), FakeClock(), []
    r = RadioController(player, StationList(), runner.run_async, clock.call_later, clock.now,
                        resolve=lambda st: st.key, open_stream=lambda url: url,
                        notify=lambda m, e: notes.append(m))
    return r, player, runner, clock, notes


def test_play_connects_and_reports(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25")
    assert r.state is RadioState.CONNECTING and notes[-1] == "연결 중…"
    runner.finish(0, result="DEC")
    assert player.streams == ["DEC"] and r.state is RadioState.LIVE and notes[-1] == "KBS 쿨FM에 연결했습니다"


def test_open_failure_shows_unavailable(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, error=DecodeError("x"))
    assert r.state is RadioState.IDLE and notes[-1] == "지금은 이 방송을 들을 수 없습니다. 다른 방송을 골라 보세요"
    assert r.current.id == "kbs-25"


def test_late_result_of_previous_station_is_ignored(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); r.play("mbc-mfm")
    closed = []; dec_a = Closeable(closed)
    runner.finish(0, result=dec_a)
    assert player.streams == [] and closed == [1] and r.current.id == "mbc-mfm"
    runner.finish(1, result="B"); assert player.streams == ["B"]


def test_reconnect_delays_and_success(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); clock.advance(30)
    player.stream_lost = True; r.on_lost()
    assert r.state is RadioState.RETRYING and notes[-1] == "다시 연결하는 중… (1/3)"
    assert len(runner.pending) == 0; clock.advance(2.0); assert len(runner.pending) == 1
    runner.finish(1, error=ResolveError("x")); assert notes[-1] == "다시 연결하는 중… (2/3)"
    clock.advance(4.0); runner.finish(2, result="B")
    assert player.continued == ["B"] and r.state is RadioState.LIVE and notes[-1] == "" and r.elapsed >= 36


def test_three_failures_give_up(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); player.stream_lost = True; r.on_lost()
    for i, d in enumerate((2.0, 4.0, 8.0), start=1):
        clock.advance(d); runner.finish(i, error=DecodeError("x"))
    assert r.state is RadioState.IDLE and player.unloaded and notes[-1].startswith("지금은 이 방송을")


def test_late_lost_of_previous_station_is_ignored(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A")
    r.play("mbc-mfm"); runner.finish(1, result="B")
    assert r.state is RadioState.LIVE and not player.stream_lost
    r.on_lost()                                   # A의 늦은 lost
    assert r.state is RadioState.LIVE and runner.pending == [] and clock.timers == []


def test_late_lost_after_stop_is_ignored(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); r.stop()
    r.on_lost()
    assert r.state is RadioState.IDLE and clock.timers == []


def test_stop_clears_status_line(radio):
    r, player, runner, clock, notes = radio
    r.stop(); assert notes == []                  # IDLE에서는 건드리지 않는다
    r.play("kbs-25"); r.stop()
    assert notes == ["연결 중…", ""]
    r.play("kbs-25"); runner.finish(1, result="A"); player.stream_lost = True; r.on_lost()
    r.stop()
    assert r.state is RadioState.IDLE and notes[-1] == ""


def test_toggle_pauses_keeping_elapsed_and_reconnects_fresh(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); clock.advance(10)
    r.toggle(); assert r.state is RadioState.IDLE and r.elapsed == 10 and player.unloaded
    clock.advance(60); assert r.elapsed == 10             # 멈춘 동안은 세지 않는다
    r.toggle(); assert r.state is RadioState.CONNECTING and len(runner.pending) == 1
    assert r.elapsed == 10
    clock.advance(1); runner.finish(1, result="B")       # 새로 연결(뒤처진 데서 잇지 않음)
    assert player.streams == ["A", "B"] and player.continued == []
    clock.advance(5); assert r.elapsed == 15


def test_stop_resets_elapsed(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); clock.advance(10)
    r.stop(); assert r.state is RadioState.IDLE and r.elapsed == 0
    r.toggle(); runner.finish(1, result="B"); clock.advance(3)
    assert r.elapsed == 3


def test_pause_then_other_station_resets_elapsed(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); clock.advance(10)
    r.pause(); assert r.elapsed == 10
    r.play("kbs-21"); assert r.elapsed == 0


def test_quick_drops_do_not_retry_forever(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A")
    n = 1
    for i, d in enumerate((2.0, 4.0, 8.0), start=1):
        clock.advance(5); player.stream_lost = True; r.on_lost()
        assert r.state is RadioState.RETRYING and notes[-1] == f"다시 연결하는 중… ({i}/3)"
        clock.advance(d); runner.finish(n, result=f"R{i}"); n += 1
        assert r.state is RadioState.LIVE
    clock.advance(5); player.stream_lost = True; r.on_lost()
    assert r.state is RadioState.IDLE and player.unloaded and notes[-1].startswith("지금은 이 방송을")
    assert clock.timers == [] and runner.pending == []


def test_stable_live_resets_retry_count(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A")
    clock.advance(5); player.stream_lost = True; r.on_lost()
    clock.advance(2.0); runner.finish(1, result="R1")
    clock.advance(30); player.stream_lost = True; r.on_lost()   # 30초 이어졌으면 처음부터 센다
    assert notes[-1] == "다시 연결하는 중… (1/3)"


def test_cue_never_touches_network(radio):
    r, player, runner, clock, notes = radio
    r.cue("mbc-sfm"); assert r.current.id == "mbc-sfm" and runner.pending == [] and r.state is RadioState.IDLE


def test_step_moves_through_visible_list(radio):
    r, *_ = radio
    r.play("kbs-21"); r.step(1); assert r.current.id == "kbs-22"
    r.step(-1); r.step(-1); assert r.current.id == r._stations.visible()[-1].id


def test_step_without_current_starts_at_first_visible(radio):
    r, *_ = radio
    r.step(1); assert r.current.id == r._stations.visible()[0].id


def test_elapsed_resets_on_playing_another_station(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); clock.advance(10)
    assert r.elapsed == 10
    r.play("kbs-21"); assert r.elapsed == 0


def test_shutdown_cancels_pending_work(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); player.stream_lost = True; r.on_lost()
    r.shutdown()
    clock.advance(20)
    assert runner.pending == [] and player.continued == []
    r.play("kbs-21"); r.shutdown(); runner.finish(1, result="Z") if runner.pending else None
    assert player.streams == ["A"]


def test_late_retry_timer_after_shutdown_does_nothing(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); player.stream_lost = True; r.on_lost()
    retry = clock.timers[0][2]
    r.shutdown(); retry()                          # 취소가 늦어 타이머가 그래도 돌았다
    assert len(runner.calls) == 1 and player.continued == []


def test_on_lost_outside_live_is_ignored(radio):
    r, player, runner, clock, notes = radio
    player.stream_lost = True
    r.on_lost(); assert r.state is RadioState.IDLE
    r.play("kbs-25"); r.on_lost()
    assert r.state is RadioState.CONNECTING and clock.timers == []


def test_each_retry_resolves_again(radio):
    r, player, runner, clock, notes = radio
    seen = []
    r._resolve = lambda st: (seen.append(st.id), st.key)[1]
    r.play("kbs-25"); runner.calls[0][0](); runner.finish(0, result="A")
    player.stream_lost = True; r.on_lost()
    clock.advance(2.0); runner.calls[1][0](); runner.finish(1, error=DecodeError("x"))
    clock.advance(4.0); runner.calls[2][0]()
    assert seen == ["kbs-25"] * 3


def test_refresh_current_picks_up_rename(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); r._stations.rename("kbs-25", "쿨")
    r.refresh_current(); assert r.current.name == "쿨"
    r._stations.remove("kbs-25"); r.refresh_current()
    assert r.current.id == "kbs-25"                 # 지워졌으면 그대로 둔다
