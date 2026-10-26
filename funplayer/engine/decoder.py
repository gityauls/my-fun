from __future__ import annotations

import logging

import av
import numpy as np

from funplayer.engine.resolve import APP_UA

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100
STREAM_TIMEOUT = 15  # 연결과 읽기, 초


class DecodeError(Exception):
    pass


class Decoder:
    def __init__(self, container, stream, live: bool = False) -> None:
        self._container = container
        self._stream = stream
        self.live = live
        # 곡 이름(ICY StreamTitle). PyAV 19는 container.metadata에 icy-* 머리글만 주고
        # StreamTitle은 주지 않는다(Task 4 조사). 그래서 늘 ""이다.
        self.title = ""
        self.duration = 0.0 if live else _duration(container, stream)
        self._prefetched: np.ndarray | None = None
        self._ended = False
        self._blocks = self._iter_blocks(None)

    def _iter_blocks(self, target: float | None):
        resampler = av.AudioResampler(format="flt", layout="stereo", rate=SAMPLE_RATE)
        cut = 0

        def convert(frames):
            nonlocal cut
            for out in frames:
                arr = out.to_ndarray().reshape(-1, 2)
                if cut:
                    drop = min(cut, len(arr))
                    arr = arr[drop:]
                    cut -= drop
                if len(arr):
                    yield np.ascontiguousarray(arr, dtype=np.float32)

        for frame in self._container.decode(self._stream):
            if target is not None:
                start = frame.time
                if start is not None:
                    end = start + frame.samples / frame.sample_rate
                    if end <= target:
                        continue
                    if start < target:
                        cut = round((target - start) * SAMPLE_RATE)
                target = None
            yield from convert(resampler.resample(frame))
        yield from convert(resampler.resample(None))

    def _next_block(self) -> np.ndarray | None:
        return next(self._blocks, None)

    def _prefetch(self) -> None:
        self._prefetched = self._next_block()

    def read(self) -> np.ndarray | None:
        if self._prefetched is not None:
            block, self._prefetched = self._prefetched, None
            return block
        if self._ended:
            return None
        block = self._next_block()
        if block is None:
            self._ended = True
        return block

    def seek(self, sec: float) -> None:
        self._prefetched = None
        self._ended = False
        sec = max(0.0, sec)
        try:
            self._container.seek(int(sec / self._stream.time_base), stream=self._stream)
            self._blocks = self._iter_blocks(sec)
        except av.error.FFmpegError:
            logger.warning("seek failed; treating as end", exc_info=True)
            self._ended = True

    def close(self) -> None:
        self._prefetched = None
        self._ended = True
        self._blocks = iter(())
        self._container.close()


def _duration(container, stream) -> float:
    if container.duration:
        return container.duration / 1_000_000
    if stream.duration and stream.time_base:
        return float(stream.duration * stream.time_base)
    return 0.0


def open_decoder(path: str) -> Decoder:
    return _open(lambda: av.open(path), live=False)


def open_stream(url: str, headers: dict[str, str] | None = None) -> Decoder:
    """인터넷 방송을 연다(네트워크를 쓰므로 작업 스레드에서 부른다). 실패는 DecodeError."""
    options = {"user_agent": APP_UA, "icy": "1"}
    if headers:
        options["headers"] = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    return _open(lambda: av.open(url, timeout=STREAM_TIMEOUT, options=options), live=True)


def _open(opener, live: bool) -> Decoder:
    container = None
    try:
        container = opener()
        if not container.streams.audio:
            raise DecodeError("오디오 트랙이 없습니다")
        decoder = Decoder(container, container.streams.audio[0], live=live)
        decoder._prefetch()
        if decoder._prefetched is None:
            raise DecodeError("디코딩할 소리가 없습니다")
        return decoder
    except Exception as exc:
        if container is not None:
            container.close()
        if isinstance(exc, DecodeError):
            raise
        raise DecodeError(str(exc)) from exc
