import os
import pytest
from funplayer.core import renamer
from funplayer.core.renamer import (MAX_LOG, RenameConflict, RenameError, RenameLog, build_name,
                                    clean_part, conflict, is_reserved, rename_file, target_path)


def test_clean_part_invalid_chars():
    assert clean_part('AC/DC: "Live"?') == "AC_DC_ _Live__"

def test_clean_part_control_and_spaces():
    assert clean_part(" a\t\x01  b. ") == "a__ b"

def test_build_name_basic():
    assert build_name("서지원", "I Miss You", ".mp3") == "서지원 - I Miss You.mp3"

def test_build_name_empty_part():
    assert build_name("", "x", ".mp3") == ""
    assert build_name("a", "  ", ".mp3") == ""
    assert build_name("a", "...", ".mp3") == ""

def test_is_reserved():
    assert is_reserved("nul") and is_reserved("COM3") and is_reserved("lpt9")
    assert not is_reserved("COM10") and not is_reserved("a - b")

def test_build_name_reserved_guard(monkeypatch):
    monkeypatch.setattr(renamer, "is_reserved", lambda s: s == "a - t")
    assert build_name("a", "t", ".mp3") == "a - t_.mp3"

def test_build_name_truncates():
    name = build_name("가수", "t" * 300, ".mp3")
    assert len(name) == 150 and name.endswith(".mp3")
    name = build_name("가수", "t" * 300, ".mp3", dir_len=200)
    assert name and 200 + 1 + len(name) <= 259

def test_build_name_truncation_strips_trailing_dot_and_space():
    # 제목은 142자까지 남는데 140자 뒤가 ". " 이므로 자른 끝의 ". "를 다시 뗀다
    name = build_name("a", "x" * 140 + ". " + "y" * 50, ".mp3")
    assert name == "a - " + "x" * 140 + ".mp3"

def test_clean_part_backslash():
    assert clean_part("a\\b") == "a_b"

def test_backslash_in_parts_stays_in_folder():
    assert build_name("a\\b", "c\\d", ".mp3") == "a_b - c_d.mp3"
    p = target_path(r"C:\m\x.mp3", "a\\b", "c\\d")
    assert os.path.dirname(p) == r"C:\m" and os.path.basename(p) == "a_b - c_d.mp3"

def test_clean_part_unicode_whitespace():
    assert clean_part("a\u3000\xa0 b") == "a b"

def test_log_save_failure_logged_and_tmp_removed(tmp_path, monkeypatch, caplog):
    log = RenameLog(str(tmp_path / "log.txt"))
    def boom(a, b): raise PermissionError("locked")
    monkeypatch.setattr(os, "replace", boom)
    with caplog.at_level("WARNING"):
        log.add("o", "n")
    assert "rename log save failed" in caplog.text
    assert log.last() == ("o", "n") and os.listdir(tmp_path) == []

def test_build_name_no_room_for_title():
    assert build_name("a" * 160, "t", ".mp3") == ""
    assert build_name("a", "t", ".mp3", dir_len=300) == ""

def test_target_path_same_name_returns_path():
    p = r"C:\m\가수 - 제목.mp3"
    assert target_path(p, "가수", "제목") is p

def test_target_path_keeps_ext_case():
    assert target_path(r"C:\m\x.MP3", "a", "b") == os.path.join(r"C:\m", "a - b.MP3")

def test_target_path_none_when_unbuildable():
    assert target_path(r"C:\m\x.mp3", "", "b") is None

def test_target_path_case_only_difference_is_new_path():
    assert target_path(r"C:\m\a - b.mp3", "A", "b") == os.path.join(r"C:\m", "A - b.mp3")

def test_case_only_not_conflict(tmp_path):
    a = tmp_path / "a.mp3"
    a.write_bytes(b"x")
    new = str(tmp_path / "A.mp3")
    assert conflict(str(a), new) is False
    rename_file(str(a), new)
    assert os.listdir(tmp_path) == ["A.mp3"]

def test_conflict_existing_other_file(tmp_path):
    a, b = tmp_path / "a.mp3", tmp_path / "b.mp3"
    a.write_bytes(b"A"); b.write_bytes(b"B")
    assert conflict(str(a), str(b))
    with pytest.raises(RenameConflict):
        rename_file(str(a), str(b))
    assert a.read_bytes() == b"A" and b.read_bytes() == b"B"

def test_rename_oserror_wrapped(tmp_path, monkeypatch):
    a = tmp_path / "a.mp3"; a.write_bytes(b"x")
    def boom(o, n): raise PermissionError("busy")
    monkeypatch.setattr(os, "rename", boom)
    with pytest.raises(RenameError) as ei:
        rename_file(str(a), str(tmp_path / "z.mp3"))
    assert not isinstance(ei.value, RenameConflict)
    assert isinstance(ei.value.__cause__, PermissionError)

def test_log_roundtrip_and_cap(tmp_path):
    p = str(tmp_path / "rename_log.txt")
    log = RenameLog(p, clock=lambda: 0)
    assert log.last() is None
    for i in range(205):
        log.add(f"o{i}", f"n{i}")
    assert log.last() == ("o204", "n204")
    with open(p, encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert len(lines) == MAX_LOG == 200 and lines[0].split("\t")[1:] == ["o5", "n5"]
    again = RenameLog(p)
    assert again.last() == ("o204", "n204")
    again.pop()
    assert again.last() == ("o203", "n203")
    assert RenameLog(p).last() == ("o203", "n203")

def test_log_ignores_bad_lines(tmp_path):
    p = tmp_path / "log.txt"
    p.write_text("junk\n2026-01-01T00:00:00\told\tnew\n\na\tb\n\t\t\n", encoding="utf-8")
    log = RenameLog(str(p))
    assert log.last() == ("old", "new")
    log.pop()
    assert log.last() is None

def test_log_memory_only():
    log = RenameLog(None)
    log.add("a", "b")
    assert log.last() == ("a", "b")
    log.pop(); log.pop()
    assert log.last() is None
