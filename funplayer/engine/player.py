from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from enum import Enum
from typing import Callable

import numpy as np

from funplayer.engine.decoder import SAMPLE_RATE, open_decoder
from funplayer.engine.sink import SinkError, SoundDeviceSink

logger = logging.getLogger(__name__)

DEVICE_ERROR_MSG = "소리 장치를 열 수 없습니다"
IDLE_WAIT = 0.01
JOIN_TIMEOUT = 1.0
LIVE_START_CAP = 3.0  # 라이브: 버퍼가 덜 찼어도 이만큼 기다렸으면 소리를 낸다(첫 소리 1~3초)


class State(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class AudioPlayer:
    """디코더 → 버퍼 → 출력. 잠금 규칙:

    - `_lock`(RLock): 디코더, 상태, 출력, 끝·끊김 표시. 순서는 항상 `_lock` → `_buf_lock`.
    - `_buf_lock`: 버퍼, 기준점, 센 프레임, gain. 출력 콜백은 이것만 잡는다.
    - `on_end`/`on_error`/`on_lost`는 모든 잠금을 놓은 뒤에 부른다.
    - 라이브 디코더의 read()(네트워크, 최대 15초 막힘)는 `_lock` 밖에서 부른다.
      읽는 동안 그 디코더는 `_reading`에 있고, 그새 빠진 디코더는 읽기가 끝난 뒤
      읽던 쪽이 닫는다(다른 스레드가 읽는 중인 컨테이너를 닫지 않는다).
    - threaded일 때 라이브 디코더마다 `_live_loop` 스레드가 따로 읽는다. 막힌 방송이
      디코드 스레드를 붙잡지 않으므로 다음 방송·파일은 바로 채워진다.
    """

    def __init__(
        self,
        sink_factory: Callable = SoundDeviceSink,
        open_decoder: Callable = open_decoder,
        threaded: bool = True,
        buffer_seconds: float = 2.0,
        live_buffer_seconds: float = 8.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.on_end: Callable[[], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_lost: Callable[[], None] | None = None
        self._sink_factory = sink_factory
        self._open_decoder = open_decoder
        self._target_frames = int(buffer_seconds * SAMPLE_RATE)
        self._live_target_frames = int(live_buffer_seconds * SAMPLE_RATE)
        self._clock = clock
        # 라이브 미리 받기: 출력을 켜기 전 기다리는 마감 시각(None이면 기다리지 않음)
        self._start_by: float | None = None

        self._lock = threading.RLock()
        self._decoder = None
        self._state = State.STOPPED
        self._sink = None
        self._ended = False
        self._closed = False
        self._live = False
        self._lost = False  # 라이브 읽기가 끝났거나 오류를 냈다
        self._reading: set = set()  # _lock 밖에서 read() 중인 라이브 디코더들
        self._threaded = threaded

        self._buf_lock = threading.Lock()
        self._blocks: deque[np.ndarray] = deque()
        self._head = 0  # 첫 블록에서 이미 내보낸 프레임 수
        self._buffered = 0
        self._base = 0.0
        self._played = 0
        self._gain = 1.0

        self._quit = threading.Event()
        self._thread: threading.Thread | None = None
        if threaded:
            self._thread = threading.Thread(
                target=self._run, name="funplayer-decode", daemon=True)
            self._thread.start()

    # ---- 읽기 전용 ----

    @property
    def state(self) -> State:
        with self._lock:
            return self._state

    @property
    def duration(self) -> float:
        with self._lock:
            return self._decoder.duration if self._decoder is not None else 0.0

    @property
    def has_track(self) -> bool:
        with self._lock:
            return self._decoder is not None

    @property
    def position(self) -> float:
        with self._buf_lock:
            return self._base + self._played / SAMPLE_RATE

    @property
    def buffered_frames(self) -> int:
        with self._buf_lock:
            return self._buffered

    @property
    def is_live(self) -> bool:
        with self._lock:
            return self._live

    @property
    def stream_lost(self) -> bool:
        """지금 라이브 디코더가 끊김으로 알려졌는가."""
        with self._lock:
            return self._live and self._lost and self._decoder is not None

    @property
    def stream_title(self) -> str:
        with self._lock:
            if not self._live or self._decoder is None:
                return ""
            return getattr(self._decoder, "title", "") or ""

    # ---- 조작 ----

    def load(self, path: str) -> None:
        # 느린 드라이브에서도 화면이 멈추지 않게 잠금 밖에서 연다
        try:
            decoder = self._open_decoder(path)
        except Exception:
            with self._lock:
                self._reset()
            raise
        with self._lock:
            self._reset()
            if self._closed:
                self._drop_decoder(decoder)
                return
            self._decoder = decoder

    def unload(self) -> None:
        with self._lock:
            self._reset()

    def play_stream(self, decoder) -> None:
        """열린 라이브 디코더로 바꿔 끼우고 PLAYING으로 시작한다.

        출력은 바로 켜지 않는다: 버퍼가 live_buffer_seconds만큼 차거나 LIVE_START_CAP초가
        지나거나 끊기면 `_live_step`이 켠다.
        """
        with self._lock:
            self._reset()
            if self._closed:
                self._drop_decoder(decoder)
                return
            self._decoder = decoder
            self._live = True
            self._state = State.PLAYING
            self._start_by = self._clock() + LIVE_START_CAP
        self._start_live_thread(decoder)

    def continue_stream(self, decoder) -> None:
        """다시 연결: 버퍼·출력·센 시간은 두고 디코더만 바꾼다.

        라이브가 아니거나(정지됨) 받은 디코더가 라이브가 아니면 그 디코더를 닫고 버린다.
        """
        with self._lock:
            if (self._closed or not self._live or self._decoder is decoder
                    or not getattr(decoder, "live", False)):
                if self._decoder is not decoder:
                    self._drop_decoder(decoder)
                return
            old, self._decoder = self._decoder, decoder
            self._lost = False
            if old is not None:
                self._drop_decoder(old)
        self._start_live_thread(decoder)

    def play(self) -> None:
        with self._lock:
            if self._closed or self._decoder is None or self._state is State.PLAYING:
                return
            failed = self._start_sink()
        if failed and self.on_error is not None:
            self.on_error(DEVICE_ERROR_MSG)

    def pause(self) -> None:
        with self._lock:
            if self._live:
                self._reset()  # 라디오에는 멈춤이 없다: stop과 같다
                return
            if self._state is not State.PLAYING:
                return
            self._halt_sink()
            self._state = State.PAUSED

    def stop(self) -> None:
        with self._lock:
            if self._live:
                self._reset()
            else:
                self._rewind()

    def seek(self, sec: float) -> None:
        with self._lock:
            if self._decoder is None or self._live:
                return
            sec = float(sec)
            if not math.isfinite(sec):
                return
            sec = max(0.0, sec)
            duration = self._decoder.duration
            if duration > 0:
                sec = min(sec, duration)
            self._clear_buffer()
            self._seek_decoder(sec)
            with self._buf_lock:
                self._base = sec
                self._played = 0

    def set_gain(self, g: float) -> None:
        with self._buf_lock:
            self._gain = float(g)

    def pump(self) -> bool:
        with self._lock:
            decoder = self._decoder
            if decoder is None:
                return False
            live = self._live
            if live:
                if self._threaded:
                    return False  # 라이브는 디코더마다 따로 도는 _live_loop가 읽는다
            else:
                worked, ended_now = self._pump_file()
        if live:
            return self._live_step(decoder) == "read"
        if ended_now and self.on_end is not None:
            self.on_end()
        return worked

    def _live_step(self, decoder) -> str:
        """라이브 디코더에서 한 블록을 잠금 없이 읽는다.

        "gone"(더는 지금 디코더가 아님), "idle"(끊김·버퍼 가득·이미 읽는 중), "read"를 돌려준다.
        읽은 뒤 그 디코더가 빠졌으면 블록은 버리고 여기서 닫는다.
        """
        with self._lock:
            if self._closed or self._decoder is not decoder:
                return "gone"
            # buffered_frames는 _lock 안에서 _buf_lock을 잡는다(순서 _lock → _buf_lock)
            if (self._lost or decoder in self._reading
                    or self.buffered_frames >= self._live_target_frames):
                return "idle"  # 끊겼으면 continue_stream/play_stream/stop까지 쉰다
            self._reading.add(decoder)
        try:
            block = decoder.read()
        except Exception:
            logger.warning("live read failed; stream lost", exc_info=True)
            block = None
        lost_now = stale = failed = False
        with self._lock:
            self._reading.discard(decoder)
            if self._decoder is not decoder:
                stale = True  # 읽는 사이 빠졌다: 닫기는 여기 몫이다
            else:
                if block is None:
                    if not self._lost:
                        self._lost = True
                        lost_now = True
                else:
                    with self._buf_lock:
                        self._blocks.append(block)
                        self._buffered += len(block)
                failed = self._maybe_start_live_output(lost_now)
        if stale:
            _close_quietly(decoder)
            return "gone"
        if failed and self.on_error is not None:
            self.on_error(DEVICE_ERROR_MSG)
        if lost_now and self.on_lost is not None:
            self.on_lost()
        return "read"

    def _maybe_start_live_output(self, lost_now: bool) -> bool:
        """_lock 안: 미리 받기가 끝났으면(가득·상한·끊김) 출력을 켠다. 장치 실패면 True."""
        if self._start_by is None:
            return False
        if not (lost_now or self.buffered_frames >= self._live_target_frames
                or self._clock() >= self._start_by):
            return False
        self._start_by = None
        return self._start_sink()

    def _live_loop(self, decoder) -> None:
        """threaded일 때 라이브 디코더 하나를 맡는 스레드. 막혀도 이 스레드만 막힌다."""
        while not self._quit.is_set():
            try:
                step = self._live_step(decoder)
            except Exception:
                logger.exception("live loop error")
                step = "idle"
            if step == "gone":
                return
            if step == "idle":
                self._quit.wait(IDLE_WAIT)

    def _start_live_thread(self, decoder) -> None:
        if self._threaded:
            threading.Thread(target=self._live_loop, args=(decoder,),
                             name="funplayer-live", daemon=True).start()

    def _pump_file(self) -> tuple[bool, bool]:
        """파일: 잠금 안에서 읽는다(로컬 읽기는 짧다). (일함, 방금 끝남)을 돌려준다."""
        ended_now = False
        worked = False
        if not self._ended and self.buffered_frames < self._target_frames:
            try:
                block = self._decoder.read()
            except Exception:
                logger.warning("decode failed mid-track; treating as end", exc_info=True)
                block = None
            if block is None:
                self._ended = True
            else:
                with self._buf_lock:
                    self._blocks.append(block)
                    self._buffered += len(block)
            worked = True
        if self._state is State.PLAYING and self._ended and self.buffered_frames == 0:
            self._rewind()
            ended_now = True
            worked = True
        return worked, ended_now

    def close(self) -> None:
        """디코드 스레드는 JOIN_TIMEOUT까지만 기다린다. 라이브 읽기 스레드는 기다리지 않는다:
        막힌 read가 풀리면(최대 15초) 그 스레드가 자기 디코더를 닫고 콜백 없이 끝난다."""
        self._quit.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(JOIN_TIMEOUT)
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._reset()
            self._discard_sink()

    # ---- 내부 (호출자가 _lock을 쥐고 있다) ----

    def _reset(self) -> None:
        """출력을 멈추고 디코더를 닫고 버퍼·기준점·센 프레임·끝 표시를 비운다."""
        self._halt_sink()
        if self._decoder is not None:
            decoder, self._decoder = self._decoder, None
            self._drop_decoder(decoder)
        self._clear_buffer()
        with self._buf_lock:
            self._base = 0.0
            self._played = 0
        self._ended = False
        self._live = False
        self._lost = False
        self._start_by = None
        self._state = State.STOPPED

    def _drop_decoder(self, decoder) -> None:
        """빠진 디코더를 닫는다. 다른 스레드가 읽는 중이면 그 스레드가 읽기 뒤에 닫는다."""
        if decoder not in self._reading:
            _close_quietly(decoder)

    def _start_sink(self) -> bool:
        """출력을 (만들어) 켠다. 실패하면 STOPPED로 두고 True를 돌려준다."""
        try:
            if self._sink is None:
                self._sink = self._sink_factory(self._callback)
            self._sink.start()
        except SinkError:
            logger.warning("audio device failed to start", exc_info=True)
            self._discard_sink()
            self._state = State.STOPPED
            return True
        self._state = State.PLAYING
        return False

    def _rewind(self) -> None:
        """stop()과 같은 처리: 출력 정지, 버퍼 비움, 디코더를 0으로."""
        self._halt_sink()
        self._clear_buffer()
        if self._decoder is not None:
            self._seek_decoder(0.0)
        with self._buf_lock:
            self._base = 0.0
            self._played = 0
        self._state = State.STOPPED

    def _seek_decoder(self, sec: float) -> None:
        self._ended = False
        try:
            self._decoder.seek(sec)
        except Exception:
            logger.warning("decoder seek failed; treating as end", exc_info=True)
            self._ended = True

    def _clear_buffer(self) -> None:
        with self._buf_lock:
            self._blocks.clear()
            self._head = 0
            self._buffered = 0

    def _halt_sink(self) -> None:
        if self._sink is None:
            return
        try:
            self._sink.stop()
        except SinkError:
            logger.warning("audio device failed to stop; discarding it", exc_info=True)
            self._discard_sink()

    def _discard_sink(self) -> None:
        sink, self._sink = self._sink, None
        if sink is None:
            return
        try:
            sink.close()
        except Exception:
            logger.warning("audio device close failed", exc_info=True)

    # ---- 스레드 ----

    def _run(self) -> None:
        while not self._quit.is_set():
            try:
                worked = self.pump()
            except Exception:
                logger.exception("decode loop error")
                worked = False
            if not worked:
                self._quit.wait(IDLE_WAIT)

    # ---- 출력 콜백 (오디오 스레드: _buf_lock만, 로그 없음) ----

    def _callback(self, outdata: np.ndarray) -> None:
        wanted = len(outdata)
        with self._buf_lock:
            filled = 0
            blocks = self._blocks
            while filled < wanted and blocks:
                block = blocks[0]
                avail = len(block) - self._head
                take = min(avail, wanted - filled)
                outdata[filled:filled + take] = block[self._head:self._head + take]
                filled += take
                if take == avail:
                    blocks.popleft()
                    self._head = 0
                else:
                    self._head += take
            if filled < wanted:
                outdata[filled:] = 0
            outdata *= self._gain
            self._buffered -= filled
            self._played += filled


def _close_quietly(decoder) -> None:
    try:
        decoder.close()
    except Exception:
        logger.warning("decoder close failed", exc_info=True)
