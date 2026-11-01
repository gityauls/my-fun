import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "funplayer"
QT_IMPORT = re.compile(r"^\s*(from|import)\s+(PyQt5|PySide6)\b", re.M)

def _sources():
    return [p for p in PKG.rglob("*.py") if p.read_text(encoding="utf-8").strip()]

def test_qt_free_layers():
    files = [p for p in _sources() if p.parent.name in ("core", "engine") or p.name in ("controller.py", "radio.py", "musicbrainz.py", "websearch.py")]
    assert files
    for p in files:
        assert not QT_IMPORT.search(p.read_text(encoding="utf-8")), p

def test_no_pyside6():
    for p in _sources():
        assert "PySide6" not in p.read_text(encoding="utf-8"), p

def test_future_annotations_everywhere():
    for p in _sources():
        assert "from __future__ import annotations" in p.read_text(encoding="utf-8"), p
