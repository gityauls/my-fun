from __future__ import annotations

import os
from dataclasses import dataclass

PREV_THRESHOLD = 3.0


@dataclass
class Track:
    path: str
    failed: bool = False

    @property
    def title(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0]


class Playlist:
    def __init__(self) -> None:
        self.tracks: list[Track] = []
        self.index: int | None = None
        self.version = 0

    def __len__(self) -> int:
        return len(self.tracks)

    def replace(self, paths: list[str]) -> None:
        self.tracks = [Track(p) for p in paths]
        self.index = 0 if self.tracks else None
        self.version += 1

    def add(self, paths: list[str]) -> int | None:
        if not paths:
            return None
        first = len(self.tracks)
        self.tracks.extend(Track(p) for p in paths)
        self.version += 1
        return first

    def clear(self) -> None:
        self.tracks = []
        self.index = None
        self.version += 1

    @property
    def current(self) -> Track | None:
        return None if self.index is None else self.tracks[self.index]

    def set_current(self, i: int) -> None:
        if not 0 <= i < len(self.tracks):
            raise IndexError(i)
        self.index = i
        self.version += 1

    def next_index(self) -> int | None:
        if self.index is None or self.index + 1 >= len(self.tracks):
            return None
        return self.index + 1

    def prev_target(self, position: float) -> tuple[str, int]:
        if position < PREV_THRESHOLD and self.index > 0:
            return ("prev", self.index - 1)
        return ("restart", self.index)

    def mark_failed(self, i: int) -> None:
        self.tracks[i].failed = True
        self.version += 1
