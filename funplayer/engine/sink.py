from __future__ import annotations

from typing import Callable

import numpy as np

AudioCallback = Callable[[np.ndarray], None]


class SinkError(Exception):
    pass


class SoundDeviceSink:
    """sounddevice 출력 스트림. callback(outdata)이 (frames, channels) float32를 채운다."""

    def __init__(
        self,
        callback: AudioCallback,
        samplerate: int = 44100,
        channels: int = 2,
        blocksize: int = 2048,
    ) -> None:
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            raise SinkError(str(exc)) from exc
        self._errors = (sd.PortAudioError, OSError)
        self._closed = False

        def _on_audio(outdata, frames, time, status) -> None:
            callback(outdata)

        try:
            self._stream = sd.OutputStream(
                samplerate=samplerate,
                channels=channels,
                dtype="float32",
                blocksize=blocksize,
                callback=_on_audio,
            )
        except self._errors as exc:
            raise SinkError(str(exc)) from exc

    def start(self) -> None:
        try:
            self._stream.start()
        except self._errors as exc:
            raise SinkError(str(exc)) from exc

    def stop(self) -> None:
        if self._closed:
            return
        try:
            self._stream.stop()
        except self._errors as exc:
            raise SinkError(str(exc)) from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._stream.close()
        except self._errors as exc:
            raise SinkError(str(exc)) from exc


class FakeSink:
    """테스트용 출력. pull()이 장치 대신 콜백을 부른다."""

    def __init__(self, callback: AudioCallback, fail_on_start: bool = False) -> None:
        self._callback = callback
        self._fail_on_start = fail_on_start
        self.started = False
        self.closed = False

    def start(self) -> None:
        if self._fail_on_start:
            raise SinkError("fake device failure")
        self.started = True

    def stop(self) -> None:
        self.started = False

    def close(self) -> None:
        self.started = False
        self.closed = True

    def pull(self, frames: int = 2048) -> np.ndarray:
        if not self.started:
            raise AssertionError("FakeSink is not started")
        out = np.zeros((frames, 2), dtype=np.float32)
        self._callback(out)
        return out
