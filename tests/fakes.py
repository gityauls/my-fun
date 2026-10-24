from __future__ import annotations

import os
from pathlib import Path

from funplayer.engine.decoder import DecodeError
from funplayer.engine.player import State


class FakePlayer:
    def __init__(self) -> None:
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
        if "bad" in os.path.splitext(os.path.basename(path))[0]:
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
