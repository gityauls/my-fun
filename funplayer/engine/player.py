from __future__ import annotations

import logging
import math
import threading
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


class State(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class AudioPlayer:
    """디코더 → 버퍼 → 출력. 잠금 규칙:

    - `_lock`(RLock): 디코더, 상태, 출력, 끝 표시. 순서는 항상 `_lock` → `_buf_lock`.
    - `_buf_lock`: 버퍼, 기준점, 센 프레임, gain. 출력 콜백은 이것만 잡는다.
    - `on_end`/`on_error`는 모든 잠금을 놓은 뒤에 부른다.
    """

    def __init__(
        self,
        sink_factory: Callable = SoundDeviceSink,
        open_decoder: Callable = open_decoder,
        threaded: bool = True,
        buffer_seconds: float = 2.0,
    ) -> None:
        self.on_end: Callable[[], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self._sink_factory = sink_factory
        self._open_decoder = open_decoder
        self._target_frames = int(buffer_seconds * SAMPLE_RATE)

        self._lock = threading.RLock()
        self._decoder = None
        self._state = State.STOPPED
        self._sink = None
        self._ended = False
        self._closed = False

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

    # ---- 조작 ----

    def load(self, path: str) -> None:
        with self._lock:
            self._reset()
            self._decoder = self._open_decoder(path)

    def unload(self) -> None:
        with self._lock:
            self._reset()

    def play(self) -> None:
        failed = False
        with self._lock:
            if self._closed or self._decoder is None or self._state is State.PLAYING:
                return
            try:
                if self._sink is None:
                    self._sink = self._sink_factory(self._callback)
                self._sink.start()
            except SinkError:
                logger.warning("audio device failed to start", exc_info=True)
                self._discard_sink()
                self._state = State.STOPPED
                failed = True
            else:
                self._state = State.PLAYING
        if failed and self.on_error is not None:
            self.on_error(DEVICE_ERROR_MSG)

    def pause(self) -> None:
        with self._lock:
            if self._state is not State.PLAYING:
                return
            self._halt_sink()
            self._state = State.PAUSED

    def stop(self) -> None:
        with self._lock:
            self._rewind()

    def seek(self, sec: float) -> None:
        with self._lock:
            if self._decoder is None:
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
        ended_now = False
        with self._lock:
            if self._decoder is None:
                return False
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
        if ended_now and self.on_end is not None:
            self.on_end()
        return worked

    def close(self) -> None:
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
            try:
                decoder.close()
            except Exception:
                logger.warning("decoder close failed", exc_info=True)
        self._clear_buffer()
        with self._buf_lock:
            self._base = 0.0
            self._played = 0
        self._ended = False
        self._state = State.STOPPED

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
