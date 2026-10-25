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
