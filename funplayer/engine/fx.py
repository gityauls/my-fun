from __future__ import annotations

import logging
import threading
from fractions import Fraction
from typing import Callable

import av
import numpy as np

from funplayer.core.effects import BANDS_HZ, FxSettings
from funplayer.engine.decoder import SAMPLE_RATE

logger = logging.getLogger(__name__)

LIMITER = ("alimiter", "limit=0.98:level=disabled")

_BYPASS = object()  # 대기 중인 "효과 없음"


def build_chain(fx: FxSettings) -> list[tuple[str, str]]:
    if not fx.enabled:
        return []
    chain: list[tuple[str, str]] = []
    # 올리는 밴드가 있으면 그 절반만큼 미리 낮춘다
    pre = max(0, *fx.bands) / 2
    if pre > 0:
        chain.append(("volume", f"volume=-{pre:g}dB"))
    for hz, db in zip(BANDS_HZ, fx.bands):
        if db:
            chain.append(("equalizer", f"f={hz}:t=o:w=1:g={db:g}"))
    if fx.mode == "speaker" and fx.width > 0:
        chain.append(("extrastereo", f"m={1 + fx.width / 100:g}"))
    elif fx.mode == "earphone":
        if fx.depth > 0:
            chain.append(("crossfeed", f"strength={0.6 * fx.depth / 100:g}"))
        if fx.bass > 0:
            chain.append(("bass", f"g={9 * fx.bass / 100:g}:f=100"))
    chain.append(LIMITER)
    return chain


class _AvGraph:
    """FFmpeg 필터 그래프 하나. run()은 받은 만큼의 프레임을 돌려준다."""

    def __init__(self, chain: list[tuple[str, str]], rate: int) -> None:
        self._rate = rate
        self._pts = 0
        self._fifo = np.zeros((0, 2), dtype=np.float32)
        g = av.filter.Graph()
        node = g.add_abuffer(sample_rate=rate, format="flt", layout="stereo", channels=2)
        for name, args in chain:
            nxt = g.add(name, args)
            node.link_to(nxt)
            node = nxt
        sink = g.add("abuffersink")
        node.link_to(sink)
        g.configure()
        self._graph = g

    def run(self, block: np.ndarray) -> np.ndarray:
        n = len(block)
        frame = av.AudioFrame.from_ndarray(
            np.ascontiguousarray(block, dtype=np.float32).reshape(1, -1),
            format="flt", layout="stereo")
        frame.sample_rate = self._rate
        frame.time_base = Fraction(1, self._rate)
        frame.pts = self._pts
        self._pts += n
        self._graph.push(frame)
        parts = [self._fifo]
        while True:
            try:
                out = self._graph.pull()
            except (BlockingIOError, EOFError):
                break
            parts.append(out.to_ndarray().reshape(-1, 2).astype(np.float32, copy=False))
        fifo = np.concatenate(parts) if len(parts) > 1 else self._fifo
        if len(fifo) < n:
            # 리미터가 앞을 내다보느라 붙잡은 만큼은 앞을 0으로 채운다
            fifo = np.concatenate([np.zeros((n - len(fifo), 2), dtype=np.float32), fifo])
        self._fifo = fifo[n:]
        return fifo[:n]


class FxProcessor:
    """출력 블록마다 효과를 건다. update()는 UI 스레드, process()는 출력 콜백 스레드."""

    def __init__(self, rate: int = SAMPLE_RATE,
                 build_graph: Callable[[list[tuple[str, str]]], object] | None = None) -> None:
        self._rate = rate
        self._build = build_graph or (lambda chain: _AvGraph(chain, rate))
        self._lock = threading.Lock()
        self._current = None
        self._pending = None
        # 바로 앞 입력 블록 (출력 스레드만 쓴다). 새 그래프를 미리 길들이는 데 쓴다
        self._last = np.zeros((4096, 2), dtype=np.float32)
        self._last_n = 0
        self._ramp: np.ndarray | None = None   # 섞는 곡선 (블록 길이가 바뀔 때만 새로)

    @property
    def active(self) -> bool:
        return self._current is not None or self._pending is not None

    def update(self, fx: FxSettings) -> None:
        # 그래프는 부른 쪽 스레드에서 만든다. 대기 자리는 늘 최신 하나뿐
        chain = build_chain(fx)
        graph = _BYPASS
        if chain:
            try:
                graph = self._build(chain)
            except Exception as e:
                logger.warning("효과 그래프를 만들지 못함, 효과 없이 재생: %s", e)
                graph = _BYPASS
        with self._lock:
            self._pending = graph

    def remember(self, block: np.ndarray) -> None:
        """효과가 꺼져 있을 때도 출력 블록을 기억해 둔다 (출력 스레드). 소리는 안 바꾼다."""
        n = len(block)
        if n > len(self._last):
            self._last = np.zeros((n, 2), dtype=np.float32)  # 더 큰 블록이 올 때만 한 번
        self._last[:n] = block
        self._last_n = n

    def process(self, block: np.ndarray) -> np.ndarray:
        with self._lock:
            pending, self._pending = self._pending, None
        if pending is None:
            if self._current is None:
                out = block
            else:
                out, self._current = self._run(self._current, block)
            self.remember(block)
            return out
        new = None if pending is _BYPASS else pending
        if new is not None and self._last_n:
            # 새 그래프에 바로 앞 블록을 먼저 흘려 버린다: 필터 상태와 리미터의
            # 내다보기 몫이 옛 그래프와 같은 자리에 맞춰져, 섞을 때 툭 튀지 않는다
            _, new = self._run(new, self._last[:self._last_n])
        old_out, _ = self._run(self._current, block)
        new_out, self._current = self._run(new, block)
        self.remember(block)
        if old_out is new_out:
            return block  # 둘 다 원래 소리
        # 한 블록 동안 옛 소리에서 새 소리로 서서히 넘어간다.
        # 코사인 곡선이라 양 끝에서 기울기가 0: 블록 경계에서 꺾이지 않는다
        ramp = self._ramp_for(len(block))
        return (old_out + (new_out - old_out) * ramp).astype(np.float32, copy=False)

    def _ramp_for(self, n: int) -> np.ndarray:
        if self._ramp is None or len(self._ramp) != n:
            k = np.arange(n, dtype=np.float64)
            r = 0.5 - 0.5 * np.cos(np.pi * k / max(n - 1, 1)) if n > 1 else np.ones(1)
            self._ramp = r.astype(np.float32)[:, None]
        return self._ramp

    def _run(self, graph, block: np.ndarray):
        # (출력, 계속 쓸 그래프). 실패한 그래프는 버리고 원래 소리를 준다
        if graph is None:
            return block, None
        try:
            return graph.run(block), graph
        except Exception as e:
            logger.warning("효과 처리 실패, 효과를 끕니다: %s", e)
            return block, None
