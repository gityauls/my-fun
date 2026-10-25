import os
from tagfiles import png_1x1, write_tagged
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
