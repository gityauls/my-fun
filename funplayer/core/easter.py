"""숨은 장면의 발동 조건. 화면을 몰라서 테스트가 쉽다."""
from __future__ import annotations

from collections import deque
from datetime import date, datetime


class TapCounter:
    """within초 안에 need번 눌렀는가. 발동하면 처음부터 다시 센다."""

    def __init__(self, need: int, within: float) -> None:
        self.need = need
        self.within = within
        self._taps: deque[float] = deque()

    def tap(self, now: float) -> bool:
        self._taps.append(now)
        while now - self._taps[0] > self.within:
            self._taps.popleft()
        if len(self._taps) < self.need:
            return False
        self._taps.clear()
        return True


class DanceDay:
    """하루 댄스곡 재생 횟수. 껐다 켜도 이어지도록 저장할 값을 내준다."""

    NEED = 5

    def __init__(self, saved: dict) -> None:
        day, count = saved.get("day"), saved.get("count")
        self.day = day if isinstance(day, str) else ""
        self.count = count if isinstance(count, int) and not isinstance(count, bool) else 0
        self.shown = saved.get("shown") is True

    def add(self, today: date, plays: int = 1) -> None:
        if self.day != today.isoformat():
            self.day, self.count, self.shown = today.isoformat(), 0, False
        self.count += plays

    def due(self, today: date) -> bool:
        return self.day == today.isoformat() and self.count >= self.NEED and not self.shown

    def done(self) -> None:
        self.shown = True

    def saved(self) -> dict:
        return {"day": self.day, "count": self.count, "shown": self.shown}


class MidnightOnce:
    """자정 정각의 1분 동안 재생 중이면 하루 한 번 때가 된다."""

    def __init__(self) -> None:
        self._last: date | None = None

    def due(self, now: datetime, playing: bool) -> bool:
        return playing and now.hour == 0 and now.minute == 0 and now.date() != self._last

    def done(self, now: datetime) -> None:
        self._last = now.date()
