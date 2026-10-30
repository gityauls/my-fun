from __future__ import annotations

from functools import lru_cache

import numpy as np

FFT_SIZE = 2048
FREQ_LOW = 40.0
FREQ_HIGH = 16000.0
DB_FLOOR = -60.0


@lru_cache(maxsize=16)
def _plan(rate: int, bars: int) -> tuple[np.ndarray, tuple[tuple[int, int], ...]]:
    """(Hann 창, 막대별 FFT 칸 범위). 칸이 하나도 없는 막대는 가장 가까운 칸 하나를 쓴다."""
    window = np.hanning(FFT_SIZE + 1)[:-1].astype(np.float32)  # 주기 Hann
    freqs = np.fft.rfftfreq(FFT_SIZE, 1.0 / rate)
    edges = np.geomspace(FREQ_LOW, min(FREQ_HIGH, rate / 2.0), bars + 1)
    spans = []
    for i in range(bars):
        lo = int(np.searchsorted(freqs, edges[i], side="left"))
        hi = int(np.searchsorted(freqs, edges[i + 1], side="left"))
        if hi <= lo:
            center = float(np.sqrt(edges[i] * edges[i + 1]))
            lo = int(np.argmin(np.abs(freqs - center)))
            hi = lo + 1
        spans.append((lo, hi))
    return window, tuple(spans)


def band_levels(block: np.ndarray, rate: int, bars: int) -> np.ndarray:
    """블록 끝 2048프레임의 막대별 크기(float32, 0..1). 0 dB(풀스케일 사인)가 1, -60 dB 이하가 0."""
    window, spans = _plan(int(rate), int(bars))
    mono = np.asarray(block, dtype=np.float32)
    if mono.ndim == 2:
        mono = mono.mean(axis=1)
    mono = mono[-FFT_SIZE:]
    if len(mono) < FFT_SIZE:
        mono = np.pad(mono, (0, FFT_SIZE - len(mono)))
    mag = np.abs(np.fft.rfft(mono * window))
    mag *= 4.0 / FFT_SIZE  # 풀스케일 사인 = 진폭 1 (Hann 합 = N/2)
    out = np.zeros(bars, dtype=np.float32)
    for i, (lo, hi) in enumerate(spans):
        out[i] = mag[lo:hi].max()
    with np.errstate(divide="ignore"):
        db = 20.0 * np.log10(np.maximum(out, 1e-12))
    out = np.clip((db - DB_FLOOR) / -DB_FLOOR, 0.0, 1.0)
    return np.nan_to_num(out).astype(np.float32)


class Decay:
    """막대는 바로 오르고 천천히 내려온다. 최고점 표시는 더 천천히 내려온다."""

    def __init__(self, bars: int, fall_per_sec: float = 1.5,
                 peak_fall_per_sec: float = 0.5) -> None:
        self._fall = float(fall_per_sec)
        self._peak_fall = float(peak_fall_per_sec)
        self._shown = np.zeros(bars, dtype=np.float32)
        self._peaks = np.zeros(bars, dtype=np.float32)

    def update(self, levels: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
        dt = max(0.0, float(dt))
        self._shown = np.maximum(levels, self._shown - self._fall * dt).astype(np.float32)
        self._peaks = np.maximum(self._shown, self._peaks - self._peak_fall * dt).astype(np.float32)
        return self._shown.copy(), self._peaks.copy()
