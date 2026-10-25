import pytest
from funplayer.core.taginfo import (TrackInfo, codec_label, fix_text, format_line, format_size,
                                    pick_cover, subtitle)

def test_fix_text_surrogate_cp949():
    s = "천상천하".encode("cp949").decode("utf-8", "surrogateescape")
    assert fix_text(s) == "천상천하"

def test_fix_text_latin1_cp949():
    assert fix_text("투투".encode("cp949").decode("latin-1")) == "투투"

@pytest.mark.parametrize("s", ["", "Britney Spears", "너만은 모르길", "Café del Mar", "Beyoncé", "Größe", "naïve"])
def test_fix_text_keeps_western_names(s):
    assert fix_text(s) == s

def test_fix_text_undecodable_bytes_become_replacement():
    out = fix_text(b"ab\xff\xfe".decode("utf-8", "surrogateescape"))
    assert out.startswith("ab") and "�" in out and not any(0xDC80 <= ord(c) <= 0xDCFF for c in out)

@pytest.mark.parametrize("names,album,want", [
    (["a.mp3", "Folder.JPG", "cover.png"], "", "cover.png"),
    (["album.jpg", "front.jpg", "folder.jpg"], "", "folder.jpg"),
    (["front.jpeg", "x.mp3"], "", "front.jpeg"),
    (["Day By Day.jpg", "scan1.jpg"], "Day By Day", "Day By Day.jpg"),
    (["only.png", "a.mp3"], "", "only.png"),
    (["a.jpg", "b.jpg"], "", None),
    (["cover.gif", "a.mp3"], "", None),
    ([], "x", None)])
def test_pick_cover(names, album, want):
    assert pick_cover(names, album) == want

def test_codec_label():
    assert [codec_label(n) for n in ("mp3float", "mp3", "aac", "flac", "vorbis", "opus", "wmav2",
                                      "alac", "pcm_s16le", "ape", "")] == [
        "MP3", "MP3", "AAC", "FLAC", "Vorbis", "Opus", "WMA", "ALAC", "PCM", "APE", ""]

def test_format_line():
    assert format_line(TrackInfo("x", codec="mp3float", bitrate=192000, sample_rate=44100, channels=2)) \
        == "MP3 · 192 kbps · 44.1 kHz · 스테레오"
    assert format_line(TrackInfo("x", codec="pcm_s16le", sample_rate=48000, channels=1)) == "PCM · 48 kHz · 모노"
    assert format_line(TrackInfo("x", codec="flac", channels=6)) == "FLAC · 6채널"
    assert format_line(TrackInfo("x")) == ""

def test_format_size():
    assert [format_size(n) for n in (5_452_595, 1_048_576, 2048, 100, 0)] == ["5.2 MB", "1.0 MB", "2 KB", "1 KB", ""]

def test_subtitle():
    assert subtitle(TrackInfo("x", artist="Lo-Fi Band", album="Sunday Mornings")) == "Lo-Fi Band · Sunday Mornings"
    assert subtitle(TrackInfo("x", artist="Lo-Fi Band")) == "Lo-Fi Band"
    assert subtitle(TrackInfo("x", album="Al")) == "Al"
    assert subtitle(TrackInfo("x")) == "" and subtitle(None) == ""
