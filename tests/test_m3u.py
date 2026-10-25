import os
import pytest
from funplayer.core.m3u import is_playlist, read_playlist, write_playlist

def _abs(p):
    return os.path.normpath(os.path.abspath(p))

def test_is_playlist():
    assert is_playlist("a.M3U8") and is_playlist(r"C:\x\b.m3u") and not is_playlist("c.mp3")

def test_round_trip_keeps_order_and_korean_names(tmp_path):
    lists = tmp_path / "목록"; lists.mkdir()
    tracks = [str(lists / "하위" / "02 봄.mp3"), str(tmp_path / "음악" / "01 비 오는 날.flac"),
              str(lists / "00 a.mp3")]
    write_playlist(str(lists / "내 목록.m3u8"), tracks)
    assert read_playlist(str(lists / "내 목록.m3u8")) == [_abs(t) for t in tracks]

def test_write_format_relative_inside_absolute_outside(tmp_path):
    lists = tmp_path / "lists"; lists.mkdir()
    inside, outside = str(lists / "sub" / "a.mp3"), str(tmp_path / "music" / "b.mp3")
    write_playlist(str(lists / "x.m3u8"), [inside, outside])
    raw = (lists / "x.m3u8").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8").split("\r\n") == ["#EXTM3U", os.path.join("sub", "a.mp3"), outside, ""]
    assert not (lists / "x.m3u8.tmp").exists()

def test_write_other_drive_is_absolute(tmp_path):
    write_playlist(str(tmp_path / "x.m3u8"), [r"Z:\m\a.mp3"])
    assert (tmp_path / "x.m3u8").read_text(encoding="utf-8").splitlines()[1] == r"Z:\m\a.mp3"

def test_read_utf8_bom_and_cp949_m3u(tmp_path):
    (tmp_path / "a.m3u8").write_bytes(b"\xef\xbb\xbf#EXTM3U\r\n" + "봄.mp3".encode("utf-8") + b"\r\n")
    assert read_playlist(str(tmp_path / "a.m3u8")) == [_abs(tmp_path / "봄.mp3")]
    (tmp_path / "b.m3u").write_bytes("#EXTM3U\r\n노래 1.mp3\r\n".encode("cp949"))
    assert read_playlist(str(tmp_path / "b.m3u")) == [_abs(tmp_path / "노래 1.mp3")]

def test_read_skips_comments_blank_urls_unsupported(tmp_path):
    text = "\n".join(["#EXTM3U", "#EXTINF:123,가수 - 제목", "", "  a.mp3  ",
                      "http://radio.example/stream.mp3", "notes.txt", "sub/b.FLAC", r"..\up\c.ogg"])
    (tmp_path / "l.m3u8").write_text(text, encoding="utf-8")
    assert read_playlist(str(tmp_path / "l.m3u8")) == [
        _abs(tmp_path / "a.mp3"), _abs(tmp_path / "sub" / "b.FLAC"), _abs(tmp_path.parent / "up" / "c.ogg")]

def test_read_file_uri(tmp_path):
    uri = (tmp_path / "a b.mp3").as_uri()
    (tmp_path / "l.m3u8").write_text("#EXTM3U\n" + uri + "\n", encoding="utf-8")
    assert read_playlist(str(tmp_path / "l.m3u8")) == [_abs(tmp_path / "a b.mp3")]

def test_missing_tracks_are_returned(tmp_path):
    (tmp_path / "l.m3u8").write_text("#EXTM3U\r\nghost.mp3\r\n", encoding="utf-8")
    assert read_playlist(str(tmp_path / "l.m3u8")) == [_abs(tmp_path / "ghost.mp3")]

def test_io_errors_raise(tmp_path):
    with pytest.raises(OSError):
        read_playlist(str(tmp_path / "none.m3u8"))
    with pytest.raises(OSError):
        write_playlist(str(tmp_path / "no" / "dir" / "x.m3u8"), [r"C:\a.mp3"])
