from __future__ import annotations

import os
from pathlib import Path

from funplayer.engine.decoder import DecodeError
from funplayer.engine.player import State


class FakePlayer:
    def __init__(self, missing_fails: bool = False) -> None:
        self.missing_fails = missing_fails
        self.loaded: list[str] = []
        self.seeks: list[float] = []
        self.gain = 1.0
        self.closed = False
        self.state = State.STOPPED
        self.position = 0.0
        self.duration = 0.0
        self.has_track = False
        self.on_end = None
        self.on_error = None

    def load(self, path: str) -> None:
        self.loaded.append(path)
        self.state = State.STOPPED
        self.position = 0.0
        bad = "bad" in os.path.splitext(os.path.basename(path))[0]
        if bad or (self.missing_fails and not os.path.exists(path)):
            self.has_track = False
            self.duration = 0.0
            raise DecodeError(path)
        self.has_track = True
        self.duration = 180.0

    def unload(self) -> None:
        self.has_track = False
        self.duration = 0.0
        self.position = 0.0
        self.state = State.STOPPED

    def play(self) -> None:
        if self.has_track:
            self.state = State.PLAYING

    def pause(self) -> None:
        if self.state is State.PLAYING:
            self.state = State.PAUSED

    def stop(self) -> None:
        self.state = State.STOPPED
        self.position = 0.0

    def seek(self, sec: float) -> None:
        self.seeks.append(sec)
        self.position = sec

    def set_gain(self, g: float) -> None:
        self.gain = g

    def close(self) -> None:
        self.closed = True

    def finish(self) -> None:
        self.state = State.STOPPED
        self.position = 0.0
        if self.on_end is not None:
            self.on_end()


class FakeLivePlayer:
    def __init__(self) -> None:
        self.streams: list = []
        self.continued: list = []
        self.unloaded = False
        self.is_live = False
        self.title = ""
        self.on_lost = None

    @property
    def stream_title(self) -> str:
        return self.title

    def play_stream(self, dec) -> None:
        self.streams.append(dec)
        self.is_live = True
        self.unloaded = False

    def continue_stream(self, dec) -> None:
        self.continued.append(dec)

    def unload(self) -> None:
        self.unloaded = True
        self.is_live = False


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list = []
        self.pending: list = []

    def run_async(self, work, done) -> None:
        call = (work, done)
        self.calls.append(call)
        self.pending.append(call)

    def finish(self, i: int, result=None, error=None) -> None:
        call = self.calls[i]
        if call in self.pending:
            self.pending.remove(call)
        call[1](result, error)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.timers: list = []   # [due, seq, fn]
        self._seq = 0

    def now(self) -> float:
        return self.t

    def call_later(self, sec: float, fn):
        self._seq += 1
        entry = [self.t + sec, self._seq, fn]
        self.timers.append(entry)

        def cancel() -> None:
            if entry in self.timers:
                self.timers.remove(entry)
        return cancel

    def advance(self, sec: float) -> None:
        end = self.t + sec
        while True:
            due = [e for e in self.timers if e[0] <= end]
            if not due:
                break
            entry = min(due, key=lambda e: (e[0], e[1]))
            self.timers.remove(entry)
            self.t = max(self.t, entry[0])
            entry[2]()
        self.t = end


class Closeable:
    def __init__(self, sink: list) -> None:
        self._sink = sink

    def close(self) -> None:
        self._sink.append(1)


def make_songs(folder: Path, names: list[str]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"")
    return folder


class FakeRng:
    """random.Random 대신 쓰는 결정적 난수: shuffle은 뒤집고, randint는 가장 작은 값을 고른다."""

    def shuffle(self, xs: list) -> None:
        xs.reverse()

    def randint(self, a: int, b: int) -> int:
        return a


class FakeApi:
    """MediaKeys용 가짜 단축키 API: busy에 든 가상 키는 등록에 실패한다."""

    def __init__(self, busy=()):
        self.busy, self.registered, self.calls = set(busy), {}, []

    def register(self, hid: int, vk: int) -> bool:
        self.calls.append(("reg", hid, vk))
        ok = vk not in self.busy
        if ok:
            self.registered[hid] = vk
        return ok

    def unregister(self, hid: int) -> None:
        self.calls.append(("unreg", hid))
        self.registered.pop(hid, None)
