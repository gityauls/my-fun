import math
import wave

import numpy as np
import pytest

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RATE = 44100


def read_frames(dec, n):
    """dec.read() 블록을 이어 붙여 앞의 n프레임을 float32 (n, 2)로 돌려준다."""
    blocks = []
    total = 0
    while total < n:
        block = dec.read()
        if block is None:
            break
        blocks.append(block)
        total += len(block)
    if not blocks:
        return np.zeros((0, 2), dtype=np.float32)
    return np.concatenate(blocks)[:n].astype(np.float32, copy=False)


def _tone_signal(seconds=3.0):
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    left = 0.5 * np.sin(2 * math.pi * 440 * t)
    right = 0.3 * t
    return np.stack([left, right], axis=1).astype(np.float32)


def _write_wav(path, data, rate, channels):
    pcm = (np.clip(data, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


@pytest.fixture(scope="session")
def tone_wav(tmp_path_factory):
    path = tmp_path_factory.mktemp("audio") / "tone.wav"
    _write_wav(path, _tone_signal(), RATE, 2)
    return str(path)


@pytest.fixture(scope="session")
def mono48k_wav(tmp_path_factory):
    path = tmp_path_factory.mktemp("audio") / "mono48k.wav"
    t = np.arange(3 * 48000) / 48000
    _write_wav(path, 0.5 * np.sin(2 * math.pi * 440 * t), 48000, 1)
    return str(path)


@pytest.fixture(scope="session")
def tone_mp3(tmp_path_factory):
    import av

    try:
        av.codec.Codec("libmp3lame", "w")
    except Exception:
        pytest.skip("MP3 인코더 없음")
    path = tmp_path_factory.mktemp("audio") / "tone.mp3"
    data = _tone_signal()
    planar = np.ascontiguousarray(data.T)  # (2, n) fltp
    with av.open(str(path), "w") as out:
        stream = out.add_stream("libmp3lame", rate=RATE)
        stream.layout = "stereo"
        step = 1152
        for pos in range(0, planar.shape[1], step):
            frame = av.AudioFrame.from_ndarray(
                planar[:, pos:pos + step], format="fltp", layout="stereo")
            frame.sample_rate = RATE
            frame.pts = pos
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)
    return str(path)


@pytest.fixture(scope="session")
def broken_mp3(tmp_path_factory):
    path = tmp_path_factory.mktemp("audio") / "broken.mp3"
    path.write_bytes(b"this is not audio" * 100)
    return str(path)


@pytest.fixture(scope="session")
def empty_wav(tmp_path_factory):
    path = tmp_path_factory.mktemp("audio") / "empty.wav"
    _write_wav(path, np.zeros((0, 2), dtype=np.float32), RATE, 2)
    return str(path)


@pytest.fixture(scope="session")
def short_wav(tmp_path_factory):
    path = tmp_path_factory.mktemp("audio") / "short.wav"
    _write_wav(path, _tone_signal()[:882], RATE, 2)
    return str(path)


@pytest.fixture(scope="session")
def qapp():
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
