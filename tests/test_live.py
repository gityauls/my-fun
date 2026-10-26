import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
from funplayer.engine.decoder import DecodeError, open_stream
from funplayer.engine.player import AudioPlayer, State
from funplayer.engine.sink import FakeSink

CHUNK = 4096


@pytest.fixture
def slow_mp3_server(tone_mp3):
    """127.0.0.1 HTTP 서버: /live.mp3는 파일 전체, /close-after/{n}은 n바이트 뒤 끊는다."""
    with open(tone_mp3, "rb") as f:
        data = f.read()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/live.mp3":
                body = data
            elif self.path.startswith("/close-after/"):
                try:
                    body = data[:int(self.path.rsplit("/", 1)[1])]
                except ValueError:
                    body = None
            else:
                body = None
            if body is None:
                self.send_error(404)
                return
            # 라이브처럼 Content-Length 없이 보내고 연결을 닫아 끝을 알린다(HTTP/1.0)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.end_headers()
            try:
                for pos in range(0, len(body), CHUNK):
                    self.wfile.write(body[pos:pos + CHUNK])
                    self.wfile.flush()
                    time.sleep(0.01)
            except OSError:
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(5)


class FakeLiveDecoder:
    duration = 0.0
    live = True
    title = ""

    def __init__(self, blocks):
        self._blocks = list(blocks)
        self.closed = False

    def read(self):
        return self._blocks.pop(0) if self._blocks else None

    def seek(self, sec):
        raise AssertionError("live decoder must not be seeked")

    def close(self):
        self.closed = True


class StalledDecoder(FakeLiveDecoder):
    """read()가 release가 켜질 때까지 막힌다(멈춘 방송)."""

    def __init__(self):
        super().__init__([])
        self.entered = threading.Event()
        self.release = threading.Event()

    def read(self):
        self.entered.set()
        self.release.wait(10)
        return None


def block(n=441, value=1.0):
    return np.full((n, 2), value, np.float32)


@pytest.fixture
def rig():
    sinks, ends, lost = [], [], []
    def factory(cb):
        sinks.append(FakeSink(cb)); return sinks[-1]
    p = AudioPlayer(sink_factory=factory, threaded=False, live_buffer_seconds=1.0)
    p.on_end = lambda: ends.append(1); p.on_lost = lambda: lost.append(1)
    yield p, sinks, ends, lost
    p.close()


def test_open_stream_live_decoder(slow_mp3_server):
    d = open_stream(slow_mp3_server + "/live.mp3")
    try:
        assert d.live and d.duration == 0.0 and d.read() is not None and d.title == ""
    finally:
        d.close()


def test_open_stream_bad_url_raises(slow_mp3_server):
    start = time.monotonic()
    with pytest.raises(DecodeError):
        open_stream(slow_mp3_server + "/nothing-here")
    assert time.monotonic() - start < 5


def test_play_stream_plays_and_reports_lost(slow_mp3_server):
    p = AudioPlayer(sink_factory=FakeSink, threaded=False, live_buffer_seconds=1.0)
    lost = []; p.on_lost = lambda: lost.append(1)
    # 8000바이트는 1초 버퍼보다 짧다(20000바이트는 약 1.25초라 버퍼가 차서 끝을 못 본다)
    p.play_stream(open_stream(slow_mp3_server + "/close-after/8000"))
    assert p.is_live and p.state is State.PLAYING and p.duration == 0.0
    for _ in range(400):
        p.pump()
    assert lost == [1] and p.state is State.PLAYING      # 끊겨도 바로 멈추지 않는다
    p.close()


def test_live_empty_buffer_outputs_silence_not_end(rig):
    p, sinks, ends, lost = rig
    p.play_stream(FakeLiveDecoder([block()]))
    for _ in range(5):
        p.pump()
    out = sinks[0].pull(2048)
    assert out[:441].all() and not out[441:].any()      # 모자란 만큼 0
    for _ in range(5):
        p.pump()
    assert not sinks[0].pull(2048).any()
    assert ends == [] and lost == [1] and p.state is State.PLAYING and p.is_live


def test_continue_stream_keeps_buffer_and_clears_lost(rig):
    p, sinks, ends, lost = rig
    a = FakeLiveDecoder([block(), block()])
    p.play_stream(a)
    for _ in range(5):
        p.pump()
    assert lost == [1] and p.buffered_frames == 882
    b = FakeLiveDecoder([])
    p.continue_stream(b)
    assert a.closed and not b.closed and p.buffered_frames == 882
    assert p.state is State.PLAYING and sinks[0].started and len(sinks) == 1
    for _ in range(5):
        p.pump()
    assert lost == [1, 1] and ends == []


def test_continue_stream_after_stop_is_ignored(rig):
    p, sinks, ends, lost = rig
    p.play_stream(FakeLiveDecoder([block()])); p.stop()
    b = FakeLiveDecoder([block()])
    p.continue_stream(b)
    assert b.closed and not p.is_live and p.state is State.STOPPED


def test_seek_is_noop_when_live(rig):
    p, sinks, *_ = rig
    p.play_stream(FakeLiveDecoder([block(), block()]))
    p.pump(); p.pump(); sinks[0].pull(441)
    pos = p.position
    p.seek(10)
    assert p.position == pos and p.buffered_frames == 441


def test_stop_and_pause_end_live(rig):
    p, sinks, *_ = rig
    d = FakeLiveDecoder([block()])
    p.play_stream(d); p.pump(); p.pause()
    assert d.closed and p.state is State.STOPPED and not p.is_live
    assert p.buffered_frames == 0 and p.position == 0 and not p.has_track


def test_stream_title(rig):
    p, *_ = rig
    assert p.stream_title == ""
    d = FakeLiveDecoder([]); d.title = "Artist - Song"
    p.play_stream(d)
    assert p.stream_title == "Artist - Song"


def test_stalled_read_does_not_block_state():
    p = AudioPlayer(sink_factory=FakeSink, threaded=True)
    d = StalledDecoder()
    try:
        p.play_stream(d)
        assert d.entered.wait(2)
        start = time.monotonic()
        assert p.state is State.PLAYING
        p.position; p.buffered_frames; p.duration; p.is_live; p.stream_title
        assert time.monotonic() - start < 0.2
        # 막힌 동안 멈추면 바로 돌아오고, 디코더는 읽기가 끝난 뒤 닫힌다
        p.stop()
        assert p.state is State.STOPPED and not d.closed
        d.release.set()
        deadline = time.monotonic() + 2
        while not d.closed and time.monotonic() < deadline:
            time.sleep(0.01)
        assert d.closed
    finally:
        d.release.set()
        p.close()


def test_lost_in_thread_does_not_spin():
    p = AudioPlayer(sink_factory=FakeSink, threaded=True)
    lost = []; p.on_lost = lambda: lost.append(1)
    reads = []
    d = FakeLiveDecoder([])
    d.read = lambda: reads.append(1)       # 늘 None
    try:
        p.play_stream(d)
        wait_until(lambda: lost)
        time.sleep(0.1)
        assert lost == [1] and len(reads) == 1
    finally:
        p.close()


def wait_until(cond, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not cond() and time.monotonic() < deadline:
        time.sleep(0.01)
    return cond()


def test_stalled_station_does_not_starve_next_station():
    p = AudioPlayer(sink_factory=FakeSink, threaded=True)
    a = StalledDecoder()
    try:
        p.play_stream(a)
        assert a.entered.wait(2)
        p.play_stream(FakeLiveDecoder([block()] * 3))
        assert wait_until(lambda: p.buffered_frames > 0, 0.5)
        assert not a.closed
        a.release.set()
        assert wait_until(lambda: a.closed)      # 막혔던 스레드가 자기 디코더를 닫는다
    finally:
        a.release.set()
        p.close()


def test_stalled_station_does_not_starve_file(tone_mp3):
    p = AudioPlayer(sink_factory=FakeSink, threaded=True)
    a = StalledDecoder()
    lost = []; p.on_lost = lambda: lost.append(1)
    try:
        p.play_stream(a)
        assert a.entered.wait(2)
        p.load(tone_mp3); p.play()
        assert wait_until(lambda: p.buffered_frames > 0, 0.5)
        a.release.set()
        assert wait_until(lambda: a.closed)
        assert lost == []                         # 빠진 디코더는 on_lost를 부르지 않는다
    finally:
        a.release.set()
        p.close()


def test_close_with_stalled_read_does_not_hang():
    p = AudioPlayer(sink_factory=FakeSink, threaded=True)
    a = StalledDecoder()
    lost = []; p.on_lost = lambda: lost.append(1)
    p.play_stream(a)
    assert a.entered.wait(2)
    start = time.monotonic()
    p.close()
    assert time.monotonic() - start < 1.5 and not a.closed
    a.release.set()
    assert wait_until(lambda: a.closed) and lost == []


def test_stream_lost_flag(rig):
    p, sinks, ends, lost = rig
    assert not p.stream_lost
    p.play_stream(FakeLiveDecoder([block()]))
    p.pump(); assert not p.stream_lost
    p.pump(); assert p.stream_lost and lost == [1]
    p.continue_stream(FakeLiveDecoder([])); assert not p.stream_lost
    p.pump(); assert p.stream_lost
    p.play_stream(FakeLiveDecoder([])); assert not p.stream_lost
    p.pump(); assert p.stream_lost
    p.stop(); assert not p.stream_lost
    p.play_stream(FakeLiveDecoder([])); p.pump(); p.unload()
    assert not p.stream_lost


def test_continue_stream_rejects_file_decoder(rig):
    p, *_ = rig
    a = FakeLiveDecoder([block()])
    p.play_stream(a)
    f = FakeLiveDecoder([]); f.live = False
    p.continue_stream(f)
    assert f.closed and not a.closed


def test_file_playback_unchanged(tone_mp3):
    p = AudioPlayer(sink_factory=FakeSink, threaded=False)
    p.load(tone_mp3); assert not p.is_live and p.duration > 0
    p.close()
