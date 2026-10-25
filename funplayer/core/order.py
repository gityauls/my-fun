from __future__ import annotations

import random
from typing import Iterable


class PlayOrder:
    """곡 번호 0..n-1의 재생 순서. 순서대로면 목록 순서, 무작위면 한 바퀴짜리 섞은 순서다."""

    def __init__(self, rng=None) -> None:
        self._rng = rng if rng is not None else random.Random()
        self._shuffle = False
        self._order: list[int] = []
        self._pending: list[int] | None = None   # 무작위일 때 미리 정한 다음 한 바퀴

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @property
    def order(self) -> list[int]:
        return list(self._order)

    def _next_lap(self) -> list[int]:
        """다음 한 바퀴(전체를 새로 섞음). 지우기 전까지 같은 목록을 돌려준다."""
        if self._pending is None:
            lap = list(range(len(self._order)))
            self._rng.shuffle(lap)
            if len(lap) > 1 and lap[0] == self._order[-1]:   # 같은 곡이 이어서 나오지 않게
                j = self._rng.randint(1, len(lap) - 1)
                lap[0], lap[j] = lap[j], lap[0]
            self._pending = lap
        return self._pending

    def rebuild(self, n: int, current: int | None) -> None:
        self._pending = None
        if not self._shuffle:
            self._order = list(range(n))
            return
        head = [current] if current is not None and 0 <= current < n else []
        rest = [i for i in range(n) if i not in head]
        self._rng.shuffle(rest)
        self._order = head + rest

    def set_shuffle(self, on: bool, current: int | None) -> None:
        self._shuffle = bool(on)
        self.rebuild(len(self._order), current)

    def extend(self, n: int, current: int | None) -> None:
        self._pending = None
        new = list(range(len(self._order), n))
        if not self._shuffle:
            self._order.extend(new)
            return
        lo = self._order.index(current) + 1 if current is not None else 0
        self._rng.shuffle(new)
        for x in new:
            self._order.insert(self._rng.randint(lo, len(self._order)), x)

    def first(self) -> int | None:
        return self._order[0] if self._order else None

    def first_of(self, indices: Iterable[int]) -> int | None:
        wanted = set(indices)
        return next((i for i in self._order if i in wanted), None)

    def next(self, current: int | None, wrap: bool) -> int | None:
        if current is None or not self._order:
            return None
        p = self._order.index(current)
        if p + 1 < len(self._order):
            return self._order[p + 1]
        if not wrap:
            return None
        return self._next_lap()[0] if self._shuffle else self._order[0]

    def upcoming(self, current: int | None, wrap: bool) -> list[int]:
        """current 다음부터 재생 순서대로 이어질 곡들 (current는 넣지 않는다)."""
        if current is None or not self._order:
            return []
        p = self._order.index(current)
        out = self._order[p + 1:]
        if wrap:
            if self._shuffle:
                out += [i for i in self._next_lap() if i not in out and i != current]
            else:
                out += self._order[:p]
        return out

    def prev(self, current: int | None, wrap: bool) -> int | None:
        if current is None or not self._order:
            return None
        p = self._order.index(current)
        if p > 0:
            return self._order[p - 1]
        if wrap and not self._shuffle and len(self._order) > 1:
            return self._order[-1]
        return None

    def moved_to(self, old: int | None, new: int) -> None:
        """지금 곡이 old에서 new로 바뀌었다. 무작위면 new가 old 바로 다음 순서가 되게 한다."""
        if not self._shuffle:
            return
        order = self._order
        pending, self._pending = self._pending, None
        if old is not None and order[-1] == old and pending is not None and new == pending[0]:
            self._order = pending   # 한 바퀴를 다 돌고 다음 바퀴로
            return
        q = order.index(new)
        if old is None:
            order.insert(0, order.pop(q))
            return
        p = order.index(old)
        if q in (p - 1, p, p + 1):
            return
        order.pop(q)
        if q < p:
            p -= 1
        order.insert(p + 1, new)

    def remap(self, mapping: list[int | None]) -> None:
        """mapping[옛 번호] = 새 번호 (지운 곡은 None)."""
        self._pending = None
        n = sum(1 for m in mapping if m is not None)
        if not self._shuffle:
            self._order = list(range(n))
            return
        self._order = [mapping[i] for i in self._order if mapping[i] is not None]
