from __future__ import annotations

import random
from typing import Iterable


class PlayOrder:
    """곡 번호 0..n-1의 재생 순서. 순서대로면 목록 순서, 무작위면 한 바퀴짜리 섞은 순서다."""

    def __init__(self, rng=None) -> None:
        self._rng = rng if rng is not None else random.Random()
        self._shuffle = False
        self._order: list[int] = []

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @property
    def order(self) -> list[int]:
        return list(self._order)

    def rebuild(self, n: int, current: int | None) -> None:
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
        return self._order[0] if wrap else None

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
        q = order.index(new)
        if old is None:
            order.insert(0, order.pop(q))
            return
        p = order.index(old)
        if q in (p - 1, p, p + 1):
            return
        if p == len(order) - 1 and q == 0:  # 한 바퀴를 다 돌고 처음으로: 새로 섞는다
            rest = order[1:]
            self._rng.shuffle(rest)
            self._order = [new] + rest
            return
        order.pop(q)
        if q < p:
            p -= 1
        order.insert(p + 1, new)

    def remap(self, mapping: list[int | None]) -> None:
        """mapping[옛 번호] = 새 번호 (지운 곡은 None)."""
        n = sum(1 for m in mapping if m is not None)
        if not self._shuffle:
            self._order = list(range(n))
            return
        self._order = [mapping[i] for i in self._order if mapping[i] is not None]
