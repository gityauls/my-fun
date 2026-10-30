import numpy as np
import pytest
from funplayer.core.spectrum import Decay, band_levels

RATE = 44100


def _edges(bars):
    return np.geomspace(40.0, 16000.0, bars + 1)


def _sine(freq, n=2048, amp=1.0):
    t = np.arange(n) / RATE
    mono = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return np.stack([mono, mono], axis=1)


def test_sine_peaks_in_its_bar():
    bars = 24
    lv = band_levels(_sine(1000.0), RATE, bars)
    expected = int(np.searchsorted(_edges(bars), 1000.0, side="right") - 1)
    assert lv.dtype == np.float32 and len(lv) == bars
    assert int(np.argmax(lv)) == expected
    assert lv[expected] > 0.9
    assert lv.min() >= 0.0 and lv.max() <= 1.0


def test_silence_is_zero():
    lv = band_levels(np.zeros((2048, 2), dtype=np.float32), RATE, 24)
    assert len(lv) == 24 and not lv.any()


@pytest.mark.parametrize("n", [100, 4096])
@pytest.mark.parametrize("bars", [12, 24])
def test_short_and_long_blocks(n, bars):
    block = np.random.default_rng(0).uniform(-1, 1, (n, 2)).astype(np.float32)
    lv = band_levels(block, RATE, bars)
    assert len(lv) == bars and np.isfinite(lv).all()
    assert lv.min() >= 0.0 and lv.max() <= 1.0


def test_no_empty_bars_with_low_resolution():
    # 짧은 블록은 해상도가 낮아 저음 막대에 FFT 칸이 없다: 가까운 칸을 쓴다
    lv = band_levels(_sine(100.0, n=100), RATE, 24)
    assert np.isfinite(lv).all()
    assert lv.max() > 0.0


def test_decay_falls_slowly():
    d = Decay(4)
    shown, peaks = d.update(np.ones(4, dtype=np.float32), 0.04)
    assert np.allclose(shown, 1.0) and np.allclose(peaks, 1.0)
    shown, peaks = d.update(np.zeros(4, dtype=np.float32), 0.04)
    assert np.allclose(shown, 0.94)
    assert np.allclose(peaks, 0.98)
    for _ in range(100):
        shown, peaks = d.update(np.zeros(4, dtype=np.float32), 0.04)
    assert np.allclose(shown, 0.0) and np.allclose(peaks, 0.0)


def test_decay_rises_immediately():
    d = Decay(2)
    shown, _ = d.update(np.array([0.2, 0.9], dtype=np.float32), 0.04)
    assert np.allclose(shown, [0.2, 0.9])
