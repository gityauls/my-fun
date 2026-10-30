import time
import numpy as np
import pytest
from conftest import read_frames
from funplayer.core.effects import FxSettings
from funplayer.engine.decoder import DecodeError, open_decoder
from funplayer.engine.player import DEVICE_ERROR_MSG, AudioPlayer, State
from funplayer.engine.sink import FakeSink

@pytest.fixture
def rig():
    """AudioPlayer(threaded=False) + 만든 FakeSink 목록 + 콜백 기록."""
    sinks, ends, errors = [], [], []
    def factory(cb):
        sinks.append(FakeSink(cb)); return sinks[-1]
    p = AudioPlayer(sink_factory=factory, threaded=False)
    p.on_end = lambda: ends.append(1); p.on_error = errors.append
    yield p, sinks, ends, errors
    p.close()

def fill(p):
    while p.pump():
        pass

def test_load(rig, tone_wav):
    p, *_ = rig; p.load(tone_wav)
    assert p.has_track and p.state is State.STOPPED and p.position == 0
    assert abs(p.duration - 3.0) < 0.05

def test_play_advances_position(rig, tone_wav):
    p, sinks, *_ = rig; p.load(tone_wav); p.play(); fill(p)
    assert p.state is State.PLAYING and sinks[0].started
    for _ in range(10): sinks[0].pull(2048)
    assert p.position == pytest.approx(20480 / 44100)

def test_pause_freezes(rig, tone_wav):
    p, sinks, *_ = rig; p.load(tone_wav); p.play(); fill(p); sinks[0].pull(2048)
    p.pause(); pos = p.position; fill(p)
    assert p.state is State.PAUSED and not sinks[0].started and p.position == pos

def test_play_without_track_is_noop(rig):
    p, sinks, *_ = rig; p.play()
    assert p.state is State.STOPPED and sinks == []

def test_gain_scales_output(rig, tone_wav):
    ref = read_frames(open_decoder(tone_wav), 2048)
    p, sinks, *_ = rig; p.load(tone_wav); p.set_gain(0.25); p.play(); fill(p)
    assert np.allclose(sinks[0].pull(2048), ref * 0.25, atol=1e-6)

def test_player_effects_toggle(rig, tone_wav):
    n = 2048
    ref = read_frames(open_decoder(tone_wav), 5 * n) * 0.25
    p, sinks, *_ = rig; p.load(tone_wav); p.set_gain(0.25); p.play(); fill(p)
    blocks = [sinks[0].pull(n)]
    assert np.allclose(blocks[0], ref[:n], atol=1e-6)
    p.set_effects(FxSettings().with_enabled(True).with_preset("록"))
    blocks += [sinks[0].pull(n), sinks[0].pull(n)]
    assert not np.allclose(blocks[1], ref[n:2 * n], atol=1e-4)
    p.set_effects(FxSettings())
    blocks += [sinks[0].pull(n), sinks[0].pull(n)]
    assert np.allclose(blocks[4], ref[4 * n:5 * n], atol=1e-6)

class _LiveTone:
    """라이브 디코더 흉내: 1 kHz 블록 몇 개를 주고 끝 (seek 없음)."""
    duration = 0.0
    live = True
    title = ""

    def __init__(self, n_blocks=8, n=2048):
        t = np.arange(n * n_blocks) / 44100
        wave = (0.3 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
        data = np.column_stack([wave, wave])
        self._blocks = [np.ascontiguousarray(data[i * n:(i + 1) * n]) for i in range(n_blocks)]
        self.closed = False

    def read(self):
        return self._blocks.pop(0) if self._blocks else None

    def seek(self, sec):
        raise AssertionError("live decoder must not be seeked")

    def close(self):
        self.closed = True


def test_effects_survive_file_radio_file(rig, tone_wav):
    # 곡 → 라디오 → 곡으로 바꿔도 켠 효과가 그대로 걸린다 (raw와 다르다)
    n = 2048
    p, sinks, *_ = rig
    p.set_effects(FxSettings().with_enabled(True).with_preset("록"))
    p.load(tone_wav); p.play(); fill(p)
    ref = read_frames(open_decoder(tone_wav), 3 * n)
    sinks[-1].pull(n); sinks[-1].pull(n)
    out = sinks[-1].pull(n)
    assert np.abs(out).max() > 0.05 and not np.allclose(out, ref[2 * n:3 * n], atol=1e-3)
    live = _LiveTone()
    raw_live = np.concatenate(list(live._blocks))
    p.play_stream(live); fill(p)
    sinks[-1].pull(n); sinks[-1].pull(n)
    out = sinks[-1].pull(n)
    assert np.abs(out).max() > 0.05 and not np.allclose(out, raw_live[2 * n:3 * n], atol=1e-3)
    p.load(tone_wav); p.play(); fill(p)
    sinks[-1].pull(n); sinks[-1].pull(n)
    out = sinks[-1].pull(n)
    assert np.abs(out).max() > 0.05 and not np.allclose(out, ref[2 * n:3 * n], atol=1e-3)


def test_callback_uses_injected_processor_only_when_active(tone_wav):
    class Fake:
        def __init__(self): self.active = False; self.updates = []; self.calls = 0; self.seen = 0
        def update(self, fx): self.updates.append(fx)
        def remember(self, block): self.seen += 1
        def process(self, block): self.calls += 1; return block * 0.0
    fake, sinks = Fake(), []
    def factory(cb):
        sinks.append(FakeSink(cb)); return sinks[-1]
    p = AudioPlayer(sink_factory=factory, threaded=False, fx_processor=fake)
    p.load(tone_wav); p.play(); fill(p)
    assert sinks[0].pull(256).any() and fake.calls == 0 and fake.seen == 1
    fx = FxSettings().with_enabled(True)
    p.set_effects(fx); fake.active = True
    assert fake.updates == [fx]
    assert not sinks[0].pull(256).any() and fake.calls == 1
    p.close()

def test_zero_gain_is_silent(rig, tone_wav):
    p, sinks, *_ = rig; p.load(tone_wav); p.set_gain(0.0); p.play(); fill(p)
    assert not sinks[0].pull(2048).any()

def test_underflow_is_silence(rig, tone_wav):
    p, sinks, *_ = rig; p.load(tone_wav); p.play()
    assert not sinks[0].pull(2048).any() and p.position == 0

def test_seek_clears_buffer(rig, tone_wav):
    p, sinks, *_ = rig; p.load(tone_wav); p.play(); fill(p)
    p.seek(2.0)
    assert p.buffered_frames == 0 and p.position == 2.0
    fill(p); assert abs(sinks[0].pull(2048)[0, 1] / 0.3 - 2.0) < 0.05

def test_seek_clamps(rig, tone_wav):
    p, *_ = rig; p.load(tone_wav)
    p.seek(-5); assert p.position == 0
    p.seek(99); assert p.position == pytest.approx(p.duration)

def play_to_end(p, sink, limit=500):
    for _ in range(limit):
        p.pump()
        if not sink.started: return
        sink.pull(4096)
    raise AssertionError("곡이 끝나지 않음")

def test_end_fires_once_and_rewinds(rig, tone_wav):
    p, sinks, ends, _ = rig; p.load(tone_wav); p.play()
    play_to_end(p, sinks[0]); fill(p); p.pump()
    assert ends == [1] and p.state is State.STOPPED and p.position == 0

def test_stop_rewinds(rig, tone_wav):
    p, sinks, *_ = rig; p.load(tone_wav); p.play(); fill(p); sinks[0].pull(2048)
    p.stop()
    assert p.state is State.STOPPED and p.position == 0 and p.buffered_frames == 0
    assert not sinks[0].started

def test_device_error_reports_and_stops(tone_wav):
    errors = []
    p = AudioPlayer(sink_factory=lambda cb: FakeSink(cb, fail_on_start=True), threaded=False)
    p.on_error = errors.append; p.load(tone_wav); p.play()
    assert errors == [DEVICE_ERROR_MSG] and p.state is State.STOPPED
    p.close()

def test_device_retry_creates_new_sink(tone_wav):
    made = []
    def factory(cb):
        made.append(FakeSink(cb, fail_on_start=not made)); return made[-1]
    p = AudioPlayer(sink_factory=factory, threaded=False); p.load(tone_wav)
    p.play(); p.play()
    assert len(made) == 2 and p.state is State.PLAYING
    p.close()

class BrokenMidway:
    duration = 3.0
    def __init__(self): self.n = 0
    def read(self):
        self.n += 1
        if self.n > 2: raise RuntimeError("corrupt frame")
        return np.zeros((1024, 2), np.float32)
    def seek(self, sec): pass
    def close(self): pass

def test_mid_decode_error_treated_as_end():
    sinks, ends = [], []
    def factory(cb):
        sinks.append(FakeSink(cb)); return sinks[-1]
    p = AudioPlayer(sink_factory=factory, open_decoder=lambda path: BrokenMidway(), threaded=False)
    p.on_end = lambda: ends.append(1); p.load("x.mp3"); p.play()
    play_to_end(p, sinks[0])
    assert ends == [1]
    p.close()

def test_load_resets_old_track(rig, tone_wav, short_wav):
    p, sinks, ends, _ = rig; p.load(tone_wav); p.play(); fill(p)
    p.load(short_wav)
    assert p.state is State.STOPPED and p.buffered_frames == 0 and p.position == 0
    p.play(); play_to_end(p, sinks[0])
    assert ends == [1]

def test_bad_file_clears_track(rig, tone_wav, broken_mp3):
    p, sinks, *_ = rig; p.load(tone_wav)
    with pytest.raises(DecodeError):
        p.load(broken_mp3)
    p.play()
    assert not p.has_track and p.state is State.STOPPED and sinks == []

def test_threaded_smoke_and_close(tone_wav):
    sinks = []
    def factory(cb):
        sinks.append(FakeSink(cb)); return sinks[-1]
    p = AudioPlayer(sink_factory=factory, threaded=True); p.load(tone_wav); p.play()
    deadline = time.monotonic() + 2
    while p.buffered_frames == 0 and time.monotonic() < deadline: time.sleep(0.01)
    assert p.buffered_frames > 0
    for _ in range(20): p.seek(1.0)
    assert p.position == 1.0
    p.close()
    assert not p._thread.is_alive() and sinks[0].closed
