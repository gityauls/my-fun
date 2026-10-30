from __future__ import annotations

import os
import shutil
import stat

import pytest
from mutagen.id3 import ID3, ID3NoHeaderError

from funplayer.engine.tags import read_info
from funplayer.engine.tagwrite import (KEEP, REMOVE, TagWriteError, clear_tags, picture_mime, write_tags)
from tests.tagfiles import noise_png, png_1x1, write_tagged

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20


@pytest.fixture
def mp3(tone_mp3, tmp_path):
    dest = tmp_path / "a.mp3"
    shutil.copyfile(tone_mp3, dest)
    return str(dest)


def _id3(path):
    return ID3(path)


def _tmpfiles(path):
    return [n for n in os.listdir(os.path.dirname(path)) if n.endswith(".myfun-tmp")]


def test_korean_roundtrip(mp3):
    write_tags(mp3, {"title": "그대향기", "artist": "유영진"})
    info = read_info(mp3)
    assert (info.title, info.artist) == ("그대향기", "유영진")
    assert info.duration > 0
    with open(mp3, "rb") as f:
        f.seek(-128, 2)
        assert f.read(3) != b"TAG"
    assert _id3(mp3).version == (2, 3, 0)
    assert _tmpfiles(mp3) == []


def test_all_fields(mp3):
    write_tags(mp3, {"title": "t", "artist": "a", "album": "al", "year": "1999", "genre": "Rock", "track": "3"})
    info = read_info(mp3)
    assert (info.album, info.year, info.genre, info.track) == ("al", "1999", "Rock", "3")


def test_empty_deletes_and_missing_kept(mp3):
    write_tags(mp3, {"title": "t", "artist": "a"})
    write_tags(mp3, {"artist": ""})
    tags = _id3(mp3)
    assert "TPE1" not in tags
    assert str(tags["TIT2"]) == "t"


def test_picture_add_keep_remove(mp3):
    write_tags(mp3, {"title": "t"}, picture=png_1x1())
    assert _id3(mp3).getall("APIC")[0].type == 3
    assert _id3(mp3).getall("APIC")[0].mime == "image/png"
    write_tags(mp3, {"title": "u"})  # KEEP
    assert len(_id3(mp3).getall("APIC")) == 1
    write_tags(mp3, {}, picture=REMOVE)
    assert _id3(mp3).getall("APIC") == []


def test_unknown_frame_kept(tone_mp3, tmp_path):
    from mutagen.id3 import USLT
    path = str(tmp_path / "b.mp3")
    write_tagged(path, tone_mp3, v2={"TIT2": b"old"})
    tags = ID3(path)
    tags.add(USLT(encoding=1, lang="kor", desc="", text="가사"))
    tags.save(path, v2_version=3)
    write_tags(path, {"title": "new"})
    got = ID3(path)
    assert str(got["TIT2"]) == "new"
    assert got.getall("USLT")[0].text == "가사"


def test_id3v1_removed(tone_mp3, tmp_path):
    path = str(tmp_path / "c.mp3")
    write_tagged(path, tone_mp3, v2={"TIT2": b"x"}, v1=(b"abc", b"def", b"ghi"))
    write_tags(path, {"title": "y"})
    with open(path, "rb") as f:
        f.seek(-128, 2)
        assert f.read(3) != b"TAG"


def test_not_mp3(tmp_path):
    import wave
    path = str(tmp_path / "a.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 800)
    with pytest.raises(TagWriteError, match="MP3만 고칠 수 있습니다"):
        write_tags(path, {"title": "t"})
    with pytest.raises(TagWriteError, match="MP3만 고칠 수 있습니다"):
        clear_tags(path)


def test_missing_file(tmp_path):
    with pytest.raises(TagWriteError):
        write_tags(str(tmp_path / "nope.mp3"), {"title": "t"})


def test_readonly_untouched(mp3):
    before = open(mp3, "rb").read()
    os.chmod(mp3, stat.S_IREAD)
    try:
        with pytest.raises(TagWriteError, match="파일에 쓸 수 없습니다 \(읽기 전용이거나 다른 프로그램이 쓰는 중\)"):
            write_tags(mp3, {"title": "t"})
        assert open(mp3, "rb").read() == before
        assert _tmpfiles(mp3) == []
    finally:
        os.chmod(mp3, stat.S_IWRITE | stat.S_IREAD)


def test_verify_failure_untouched(mp3):
    before = open(mp3, "rb").read()
    with pytest.raises(TagWriteError, match="저장한 파일을 다시 읽지 못해 원래대로 두었습니다"):
        write_tags(mp3, {"title": "t"}, verify=lambda p: False)
    assert open(mp3, "rb").read() == before
    assert _tmpfiles(mp3) == []


def test_verify_exception_maps_to_generic(mp3):
    def boom(p):
        raise RuntimeError("x")
    with pytest.raises(TagWriteError, match="저장하지 못했습니다"):
        write_tags(mp3, {"title": "t"}, verify=boom)
    assert _tmpfiles(mp3) == []


def test_clear_tags(tone_mp3, tmp_path):
    path = str(tmp_path / "d.mp3")
    write_tagged(path, tone_mp3, v2={"TIT2": b"x"}, picture=png_1x1(), v1=(b"abc", b"def", b"ghi"))
    clear_tags(path)
    with pytest.raises(ID3NoHeaderError):
        ID3(path)
    with open(path, "rb") as f:
        f.seek(-128, 2)
        assert f.read(3) != b"TAG"
    assert read_info(path).duration > 0
    assert _tmpfiles(path) == []


def test_clear_tags_verify_failure(tone_mp3, tmp_path):
    path = str(tmp_path / "e.mp3")
    write_tagged(path, tone_mp3, v2={"TIT2": b"x"})
    before = open(path, "rb").read()
    with pytest.raises(TagWriteError):
        clear_tags(path, verify=lambda p: False)
    assert open(path, "rb").read() == before


def test_picture_mime():
    assert picture_mime(JPEG) == "image/jpeg"
    assert picture_mime(png_1x1()) == "image/png"
    assert picture_mime(b"GIF89a....") is None
    assert picture_mime(b"") is None


def test_bad_or_big_picture(mp3):
    with pytest.raises(TagWriteError):
        write_tags(mp3, {}, picture=b"GIF89a....")
    with pytest.raises(TagWriteError):
        write_tags(mp3, {}, picture=b"\xff\xd8\xff" + b"\x00" * (10 * 1024 * 1024))
    assert noise_png(8)  # helper sanity
