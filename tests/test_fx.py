from __future__ import annotations

import numpy as np

from funplayer.core.effects import FxSettings
from funplayer.engine.decoder import SAMPLE_RATE
from funplayer.engine.fx import FxProcessor, build_chain


def tone(hz: float, n: int, amp: float) -> np.ndarray:
    t = np.arange(n) / SAMPLE_RATE
    wave = (amp * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    return np.ascontiguousarray(np.column_stack([wave, wave]))


class IdentityGraph:
    # 그래프 흉내: 받은 블록을 그대로 돌려준다
    def run(self, block: np.ndarray) -> np.ndarray:
        return block


def test_chain_off_is_empty():
    assert build_chain(FxSettings()) == []


def test_chain_eq_preamp_and_limiter_last():
    fx = FxSettings().with_enabled(True).with_preset("발라드")
    chain = build_chain(fx)
    assert chain[0] == ("volume", "volume=-1.5dB")
    eq = [a for n, a in chain if n == "equalizer"]
    assert "f=31:t=o:w=1:g=3" in eq and not any("f=250:" in a for a in eq)   # 0 dB 밴드는 없다
    assert chain[-1] == ("alimiter", "limit=0.98:level=disabled")


def test_chain_modes():
    on = FxSettings().with_enabled(True)
    assert ("extrastereo", "m=1.4") in build_chain(on.with_mode("speaker"))
    ear = build_chain(on.with_mode("earphone"))
    assert ("crossfeed", "strength=0.24") in ear and ("bass", "g=2.7:f=100") in ear
    assert not any(n == "crossfeed" for n, _ in build_chain(on.with_mode("earphone").with_level("depth", 0)))
    assert build_chain(on) == [("alimiter", "limit=0.98:level=disabled")]


def test_bypass_returns_input():
    p = FxProcessor()
    b = tone(440, 2048, 0.3)
    assert np.array_equal(p.process(b), b) and not p.active


def test_varying_block_sizes():
    p = FxProcessor()
    p.update(FxSettings().with_enabled(True).with_preset("록").with_mode("earphone"))
    for n in (1, 7, 2048, 4096, 300):
        out = p.process(tone(1000, n, 0.3))
        assert out.shape == (n, 2) and out.dtype == np.float32 and np.isfinite(out).all()


def test_all_bands_max_never_clips():
    p = FxProcessor()
    fx = FxSettings().with_enabled(True)
    for i in range(10):
        fx = fx.with_band(i, 12)
    p.update(fx.with_mode("earphone").with_level("bass", 100))
    peak = max(np.abs(p.process(tone(60, 2048, 0.95))).max() for _ in range(20))
    assert peak <= 1.0


def test_bass_preset_boosts_low_not_high():
    def gain(hz):
        p = FxProcessor()
        p.update(FxSettings().with_enabled(True).with_preset("베이스 강하게"))
        outs = [p.process(tone(hz, 2048, 0.1)) for _ in range(10)]
        return np.abs(outs[-1]).max() / 0.1
    assert gain(62) > 1.8 * gain(8000)   # 미리 낮춤(-3.5 dB) 때문에 절대값이 아니라 비율로 본다


class Stream:
    """위상이 이어지는 100 Hz 사인을 2048 프레임씩 흘리고, 블록마다 최대 |2차 차분|을 잰다."""
    N = 2048

    def __init__(self, p: FxProcessor) -> None:
        self.p = p
        self.pos = 0
        self.prev = np.zeros((2, 2), dtype=np.float32)

    def step(self) -> float:
        t = (self.pos + np.arange(self.N)) / SAMPLE_RATE
        self.pos += self.N
        wave = (0.3 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)
        out = self.p.process(np.ascontiguousarray(np.column_stack([wave, wave])))
        joined = np.concatenate([self.prev, out])[:, 0].astype(np.float64)
        self.prev = out[-2:].copy()
        return float(np.abs(np.diff(joined, 2)).max())


def _swap_ratio(before: FxSettings, after: FxSettings) -> float:
    p = FxProcessor()
    p.update(before)
    s = Stream(p)
    steady = [s.step() for _ in range(6)][-1]
    p.update(after)
    swap = s.step()
    later = [s.step() for _ in range(3)][-1]
    return swap / max(steady, later)


ROCK = FxSettings().with_enabled(True).with_preset("록")


def test_swap_has_no_jump():
    # 새 그래프의 리미터가 앞을 0으로 채우면 섞는 블록에 계단이 생긴다 (예전 약 150배)
    assert _swap_ratio(ROCK, ROCK.with_band(0, ROCK.bands[0] + 1)) <= 3


def test_swap_from_bypass_has_no_jump():
    assert _swap_ratio(FxSettings(), ROCK) <= 3


def test_swap_to_bypass_has_no_jump():
    assert _swap_ratio(ROCK, FxSettings()) <= 3


def test_remember_keeps_sound_and_handles_big_blocks():
    p = FxProcessor()
    big = tone(440, 9000, 0.3)
    p.remember(big)
    assert p._last_n == 9000 and np.array_equal(p._last[:9000], big)
    small = tone(440, 64, 0.3)
    assert np.array_equal(p.process(small), small) and p._last_n == 64


def test_off_returns_raw_after_crossfade():
    p = FxProcessor()
    p.update(FxSettings().with_enabled(True).with_preset("록"))
    p.process(tone(500, 2048, 0.3))
    p.update(FxSettings())
    p.process(tone(500, 2048, 0.3))            # 섞는 블록
    b = tone(500, 2048, 0.3)
    assert np.array_equal(p.process(b), b) and not p.active


def test_many_updates_one_swap():
    built = []

    def fake_build(chain):
        built.append(chain)
        return IdentityGraph()
    p = FxProcessor(build_graph=fake_build)
    for i in range(300):
        p.update(FxSettings().with_enabled(True).with_band(0, i % 12))
    p.process(tone(100, 64, 0.1))
    assert p._pending is None
    assert len(built) == 300 and p.active


def test_build_failure_is_bypass():
    def boom(chain):
        raise ValueError("no filter")
    p = FxProcessor(build_graph=boom)
    p.update(FxSettings().with_enabled(True))
    b = tone(300, 512, 0.2)
    assert np.array_equal(p.process(b), b)


def test_run_failure_drops_graph():
    class Broken:
        def run(self, block):
            raise RuntimeError("bad")
    p = FxProcessor(build_graph=lambda chain: Broken())
    p.update(FxSettings().with_enabled(True))
    b = tone(300, 256, 0.2)
    p.process(b)                                # 섞는 블록에서 실패
    assert np.array_equal(p.process(b), b) and not p.active
