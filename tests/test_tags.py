import os
import pytest
from tagfiles import noise_png, png_1x1, write_tagged
from funplayer.engine.tags import read_info

cp = lambda s: s.encode("cp949")

def test_reads_id3v2_tags_and_picture(tmp_path, tone_mp3):
    p = write_tagged(tmp_path / "a.mp3", tone_mp3, picture=png_1x1(), v2={
        "TIT2": cp("천상천하"), "TPE1": b"Ami", "TALB": b"1st", "TYER": b"2000",
        "TCON": b"Ballad", "TRCK": b"3/12"})
    info = read_info(str(p))
    assert (info.title, info.artist, info.album, info.year, info.genre, info.track) == (
        "천상천하", "Ami", "1st", "2000", "Ballad", "3/12")
    assert info.picture == png_1x1() and info.codec in ("mp3", "mp3float")
    assert info.channels == 2 and info.sample_rate == 44100 and info.bitrate > 0
    assert 2.5 < info.duration < 3.5 and info.size == p.stat().st_size and info.path == str(p)

def test_reads_id3v1_cp949(tmp_path, tone_mp3):
    p = write_tagged(tmp_path / "b.mp3", tone_mp3, v1=(cp("천상천하"), cp("투투"), b"1st"))
    info = read_info(str(p))
    assert (info.title, info.artist, info.album) == ("천상천하", "투투", "1st") and info.picture is None

def test_wav_without_tags(tone_wav):
    info = read_info(tone_wav)
    assert (info.title, info.artist, info.album, info.picture) == ("", "", "", None)
    assert info.codec.startswith("pcm") and 2.5 < info.duration < 3.5

def test_unreadable_file_gives_path_and_size(broken_mp3):
    info = read_info(broken_mp3)
    assert info.path == broken_mp3 and info.size == os.path.getsize(broken_mp3)
    assert (info.title, info.duration, info.codec) == ("", 0.0, "")

def test_missing_file(tmp_path):
    info = read_info(str(tmp_path / "nope.mp3"))
    assert info.size == 0 and info.title == ""

def write_flac(path, metadata):
    import av
    import numpy as np
    with av.open(str(path), "w") as out:
        out.metadata.update(metadata)
        st = out.add_stream("flac", rate=44100); st.layout = "stereo"
        frame = av.AudioFrame.from_ndarray(np.zeros((1, 2 * 4410), dtype=np.int16), format="s16", layout="stereo")
        frame.sample_rate = 44100; frame.pts = 0
        for p in st.encode(frame): out.mux(p)
        for p in st.encode(None): out.mux(p)
    return path

def test_upper_case_vorbis_comment_keys(tmp_path):
    import av
    p = write_flac(tmp_path / "u.flac", {"TITLE": "Morning Coffee", "ARTIST": "Lo-Fi Band", "ALBUM": "Sunday",
                                         "DATE": "2019-05-01", "GENRE": "Jazz", "TRACKNUMBER": "3"})
    with av.open(str(p)) as c:
        assert "TITLE" in c.metadata and "title" not in c.metadata   # 대문자 키가 그대로 온다
    info = read_info(str(p))
    assert (info.title, info.artist, info.album, info.year, info.genre, info.track) == (
        "Morning Coffee", "Lo-Fi Band", "Sunday", "2019", "Jazz", "3") and info.codec == "flac"

def test_year_key_used_when_date_missing(tmp_path):
    p = write_flac(tmp_path / "y.flac", {"TITLE": "x", "YEAR": "2003"})
    assert read_info(str(p)).year == "2003"

@pytest.fixture(scope="module")
def mp3_192k(tmp_path_factory):
    import math
    import av
    import numpy as np
    path = tmp_path_factory.mktemp("audio") / "tone192.mp3"
    t = np.arange(3 * 44100) / 44100
    planar = np.ascontiguousarray(np.stack([0.5 * np.sin(2 * math.pi * 440 * t)] * 2).astype(np.float32))
    with av.open(str(path), "w") as out:
        st = out.add_stream("libmp3lame", rate=44100); st.layout = "stereo"; st.bit_rate = 192000
        for pos in range(0, planar.shape[1], 1152):
            frame = av.AudioFrame.from_ndarray(planar[:, pos:pos + 1152], format="fltp", layout="stereo")
            frame.sample_rate = 44100; frame.pts = pos
            for p in st.encode(frame): out.mux(p)
        for p in st.encode(None): out.mux(p)
    return str(path)

def test_bitrate_ignores_big_cover_picture(tmp_path, mp3_192k):
    pic = noise_png(320)
    assert len(pic) > 250_000
    p = write_tagged(tmp_path / "big.mp3", mp3_192k, picture=pic, v2={"TIT2": b"x"})
    info = read_info(str(p))
    assert info.picture == pic and abs(info.bitrate - 192000) < 20000
