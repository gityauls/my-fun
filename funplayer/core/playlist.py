from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from funplayer.core.order import PlayOrder
from funplayer.core.tracks import name_sort_key, path_sort_key

PREV_THRESHOLD = 3.0


@dataclass
class Track:
    path: str
    failed: bool = False    # 파일은 있는데 열 수 없었다
    missing: bool = False   # 마지막으로 확인했을 때 파일이 없었다

    @property
    def title(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0]


class Playlist:
    def __init__(self, rng=None) -> None:
        self.tracks: list[Track] = []
        self.index: int | None = None
        self.version = 0
        self.layout_version = 0
        self._order = PlayOrder(rng)

    def __len__(self) -> int:
        return len(self.tracks)

    @property
    def shuffle(self) -> bool:
        return self._order.shuffle

    @property
    def order(self) -> list[int]:
        return self._order.order

    def set_shuffle(self, on: bool) -> None:
        self._order.set_shuffle(on, self.index)

    def replace(self, paths: list[str]) -> None:
        self.tracks = [Track(p) for p in paths]
        self._order.rebuild(len(self.tracks), None)
        self.index = self._order.first()
        self.version += 1
        self.layout_version += 1

    def add(self, paths: list[str]) -> int | None:
        if not paths:
            return None
        first = len(self.tracks)
        self.tracks.extend(Track(p) for p in paths)
        self._order.extend(len(self.tracks), self.index)
        self.version += 1
        self.layout_version += 1
        return self._order.first_of(range(first, len(self.tracks)))

    def clear(self) -> None:
        self.tracks = []
        self.index = None
        self._order.rebuild(0, None)
        self.version += 1
        self.layout_version += 1

    @property
    def current(self) -> Track | None:
        return None if self.index is None else self.tracks[self.index]

    def set_current(self, i: int) -> None:
        if not 0 <= i < len(self.tracks):
            raise IndexError(i)
        self._order.moved_to(self.index, i)
        self.index = i
        self.version += 1

    def next_index(self, wrap: bool = False) -> int | None:
        return self._order.next(self.index, wrap)

    def prev_target(self, position: float, wrap: bool = False) -> tuple[str, int]:
        if position < PREV_THRESHOLD:
            prv = self._order.prev(self.index, wrap)
            if prv is not None:
                return ("prev", prv)
        return ("restart", self.index)

    def mark_failed(self, i: int) -> None:
        self.tracks[i].failed = True
        self.version += 1

    def mark_missing(self, i: int) -> None:
        self.tracks[i].missing = True
        self.version += 1

    def mark_ok(self, i: int) -> None:
        t = self.tracks[i]
        if t.failed or t.missing:
            t.failed = t.missing = False
            self.version += 1

    def remove(self, rows: Iterable[int], wrap: bool = False) -> str:
        gone = {r for r in rows if 0 <= r < len(self.tracks)}
        if not gone:
            return "kept"
        cur, result = self.index, "kept"
        if cur in gone:
            cur, result = self._survivor(cur, gone, wrap)
        self._apply([i for i in range(len(self.tracks)) if i not in gone], cur)
        return result

    def _survivor(self, cur: int, gone: set[int], wrap: bool) -> tuple[int | None, str]:
        """지운 지금 곡 대신 지금 곡이 될 곡: [다음]으로 갈 곡, 없으면 순서상 앞의 곡(정지)."""
        for nxt in self._order.upcoming(cur, wrap):
            if nxt not in gone:
                return nxt, "next"
        prv = cur
        while (prv := self._order.prev(prv, False)) is not None:
            if prv not in gone:
                return prv, "stop"
        return None, "stop"

    def _apply(self, keep: list[int], current: int | None) -> None:
        """keep = 새 순서대로 놓은 옛 번호들. 빠진 번호는 지운 곡이다."""
        mapping: list[int | None] = [None] * len(self.tracks)
        for new, old in enumerate(keep):
            mapping[old] = new
        self.tracks = [self.tracks[old] for old in keep]
        self._order.remap(mapping)
        self.index = None if current is None else mapping[current]
        self.version += 1
        self.layout_version += 1

    def duplicate_indices(self) -> list[int]:
        groups: dict[str, list[int]] = {}
        for i, t in enumerate(self.tracks):
            groups.setdefault(os.path.normcase(os.path.abspath(t.path)), []).append(i)
        extra: list[int] = []
        for members in groups.values():
            keep = self.index if self.index in members else members[0]
            extra.extend(i for i in members if i != keep)
        return sorted(extra)

    def rename_path(self, old: str, new: str) -> int:
        """같은 파일(대소문자 무시)인 모든 줄의 경로를 새 경로로 바꾼다. 줄 수는 그대로."""
        key = os.path.normcase(os.path.abspath(old))
        n = 0
        for t in self.tracks:
            if os.path.normcase(os.path.abspath(t.path)) == key:
                t.path = new
                n += 1
        if n:
            self.version += 1
        return n

    def unplayable_indices(self, exists: Callable[[str], bool] = os.path.exists) -> list[int]:
        return [i for i, t in enumerate(self.tracks) if t.failed or not exists(t.path)]

    def sort(self, by: str) -> None:
        if by == "name":
            key = name_sort_key
        elif by == "path":
            key = path_sort_key
        else:
            raise ValueError(by)
        self._apply(sorted(range(len(self.tracks)), key=lambda i: key(self.tracks[i].path)), self.index)

    def move(self, rows: Iterable[int], before: int) -> list[int]:
        n = len(self.tracks)
        sel = sorted({r for r in rows if 0 <= r < n})
        if not sel:
            return []
        before = max(0, min(before, n))
        chosen = set(sel)
        rest = [i for i in range(n) if i not in chosen]
        at = before - sum(1 for r in sel if r < before)
        self._apply(rest[:at] + sel + rest[at:], self.index)
        return list(range(at, at + len(sel)))
