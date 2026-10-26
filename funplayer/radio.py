from __future__ import annotations

import logging
from enum import Enum

from funplayer.core.stations import Station, StationList
from funplayer.engine.decoder import open_stream
from funplayer.engine.resolve import resolve

CONNECTING_MSG = "연결 중…"
CONNECTED_MSG = "{name}에 연결했습니다"
RETRY_MSG = "다시 연결하는 중… ({n}/3)"
UNAVAILABLE_MSG = "지금은 이 방송을 들을 수 없습니다. 다른 방송을 골라 보세요"
RESUME_RADIO_MSG = "이어 듣기: {name}"
DUP_STATION_MSG = "이미 목록에 있습니다"
RETRY_DELAYS = (2.0, 4.0, 8.0)
STABLE_SECONDS = 30.0  # 이만큼 LIVE로 이어졌으면 다시 연결 횟수를 처음부터 센다

logger = logging.getLogger(__name__)


class RadioState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    LIVE = "live"
    RETRYING = "retrying"


class RadioController:
    def __init__(self, player, stations: StationList, run_async, call_later, clock,
                 resolve=resolve, open_stream=open_stream, notify=None) -> None:
        self._player = player
        self._stations = stations
        self._run_async = run_async
        self._call_later = call_later
        self._clock = clock
        self._resolve = resolve
        self._open_stream = open_stream
        self._notify = notify
        self._token = 0                 # 연결 시도 번호: 올 때마다 이전 시도의 결과는 버린다
        self._cancel_timer = None       # 다시 연결 대기를 취소하는 함수
        self._attempt = 0               # 마지막으로 30초 이어진 뒤 해 본 다시 연결 수
        self._live_since: float | None = None   # 마지막으로 LIVE가 된 시각
        self._since: float | None = None   # 들은 시간을 센 시작 시각
        self._kept = 0.0                # 멈춘 동안 붙들어 둔 들은 시간
        self.state = RadioState.IDLE
        self.current: Station | None = None

    @property
    def elapsed(self) -> float:
        if self._since is None:
            return self._kept
        return self._clock() - self._since

    @property
    def now_title(self) -> str:
        return self._player.stream_title

    def _say(self, msg: str) -> None:
        if self._notify is not None:
            self._notify(msg, False)

    def _cancel_wait(self) -> None:
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    def _discard(self, result) -> None:
        close = getattr(result, "close", None)
        if close is not None:
            close()

    def has_station(self, station_id: str) -> bool:
        return self._stations.get(station_id) is not None

    def refresh_current(self) -> None:
        """목록이 바뀐 뒤(이름 바꾸기 등) 고른 방송의 표시를 새로 읽는다. 지워졌으면 그대로 둔다."""
        if self.current is not None:
            station = self._stations.get(self.current.id)
            if station is not None:
                self.current = station

    def cue(self, station_id: str) -> None:
        station = self._stations.get(station_id)
        if station is not None:
            self.current = station

    def play(self, station_id: str) -> None:
        station = self._stations.get(station_id)
        if station is None:
            return
        self._cancel_wait()
        # 같은 방송을 다시 들으면(멈춤 뒤 [재생]) 들은 시간을 잇고, 다른 방송이면 0부터
        same = self.current is not None and self.current.id == station.id
        self._kept = self.elapsed if same else 0.0
        self.current = station
        self._since = None
        self._attempt = 0
        self._live_since = None
        self.state = RadioState.CONNECTING
        self._say(CONNECTING_MSG)
        self._token += 1
        self._connect(station, self._token, self._on_opened)

    def _connect(self, station: Station, token: int, handler) -> None:
        def work():
            return self._open_stream(self._resolve(station))

        self._run_async(work, lambda result, error: handler(token, station, result, error))

    def _on_opened(self, token: int, station: Station, result, error) -> None:
        if token != self._token:
            self._discard(result)
            return
        if error is not None or result is None:
            logger.info("radio connect failed: %s", station.id, exc_info=error)
            self._player.unload()
            self.state = RadioState.IDLE
            self._say(UNAVAILABLE_MSG)
            return
        self._player.play_stream(result)
        self.state = RadioState.LIVE
        self._live_since = self._clock()
        self._since = self._live_since - self._kept
        self._say(CONNECTED_MSG.format(name=station.name))

    def toggle(self) -> None:
        if self.state is RadioState.IDLE:
            if self.current is not None:
                self.play(self.current.id)
        else:
            self.pause()

    def pause(self) -> None:
        """연결을 끊는다. 들은 시간은 멈춘 자리에 둔다(다시 [재생]하면 이어 센다)."""
        self._disconnect(self.elapsed)

    def stop(self) -> None:
        """연결을 끊고 들은 시간을 0으로 한다. 방송국 선택은 남는다."""
        self._disconnect(0.0)

    def _disconnect(self, kept: float) -> None:
        was_busy = self.state is not RadioState.IDLE
        self._token += 1
        self._cancel_wait()
        self._player.unload()
        self._since = None
        self._kept = kept
        self._attempt = 0
        self._live_since = None
        self.state = RadioState.IDLE
        if was_busy:
            self._say("")  # "연결 중…"·"다시 연결하는 중…" 같은 안내를 지운다

    def step(self, direction: int) -> None:
        target = None
        if self.current is not None:
            target = self._stations.neighbor(self.current.id, direction)
        if target is None:
            visible = self._stations.visible()
            target = visible[0] if visible else None
        if target is not None:
            self.play(target.id)

    def on_lost(self) -> None:
        # 큐로 오는 신호라 A의 늦은 lost가 B 연결 뒤나 정지 뒤에 올 수 있다: 지금 디코더로 확인한다
        if self.state is not RadioState.LIVE or not self._player.stream_lost:
            return
        # 붙자마자 다시 끊기는 방송이 끝없이 돌지 않게: 30초 이어졌을 때만 처음부터 센다
        if self._live_since is not None and self._clock() - self._live_since >= STABLE_SECONDS:
            self._attempt = 0
        if self._attempt >= len(RETRY_DELAYS):
            self._give_up()
            return
        self.state = RadioState.RETRYING
        self._schedule_retry()

    def _give_up(self) -> None:
        self.stop()
        self._say(UNAVAILABLE_MSG)

    def _schedule_retry(self) -> None:
        self._say(RETRY_MSG.format(n=self._attempt + 1))
        self._cancel_timer = self._call_later(RETRY_DELAYS[self._attempt], self._retry)

    def _retry(self) -> None:
        self._cancel_timer = None
        station = self.current
        if self.state is not RadioState.RETRYING or station is None:
            return
        self._token += 1
        self._connect(station, self._token, self._on_retried)

    def _on_retried(self, token: int, station: Station, result, error) -> None:
        if token != self._token or self.state is not RadioState.RETRYING:
            self._discard(result)
            return
        self._attempt += 1
        if error is None and result is not None:
            self._player.continue_stream(result)
            self.state = RadioState.LIVE
            self._live_since = self._clock()
            self._say("")
            return
        if self._attempt < len(RETRY_DELAYS):
            self._schedule_retry()
        else:
            self._give_up()

    def shutdown(self) -> None:
        self._token += 1
        self._cancel_wait()
        self.state = RadioState.IDLE
