import re
from pathlib import Path

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QWidget

from funplayer.core.themes import THEMES, get_theme
from funplayer.ui import fonts
from funplayer.ui.cover import radio_art_for, rounded_art, theme_art
from funplayer.ui.style import qcolor_gradient, stylesheet

NAMES = ("root", "titleBar", "tabs", "pageNow", "pagePlaylist", "pageRadio", "pageFx",
         "footBar", "nowStrip", "miniBar", "pill", "foot0", "foot1", "foot2", "foot3")


def test_gradient_to_qss():
    v = qcolor_gradient("linear-gradient(90deg,#2B3D63,#8A5A7C 55%,#C46A5A)")
    assert v.startswith("qlineargradient(") and "stop:0.55 #8A5A7C" in v


def test_plain_and_rgba_colors():
    assert qcolor_gradient("#123456") == "#123456"
    assert qcolor_gradient("rgba(255,255,255,.12)") == "rgba(255,255,255,31)"
    assert "rgba(255,255,255,89)" in qcolor_gradient(
        "linear-gradient(170deg,#000 0%,rgba(255,255,255,.35) 100%)")


@pytest.mark.parametrize("t", THEMES, ids=lambda t: t.id)
def test_stylesheet_builds_for_all_themes(qapp, t):
    QWidget().setStyleSheet(stylesheet(t, "Noto Sans KR"))
    assert "linear-gradient" not in stylesheet(t, "x")


def test_stylesheet_uses_object_selectors_only():
    # QSS가 대화상자에 번지면 안 된다: 맨몸 위젯 선택자 금지
    for t in THEMES:
        for line in stylesheet(t, "x").splitlines():
            assert not re.match(r"^\s*(Q[A-Za-z]+|\*)\s*[{,:\[.]", line) or line.startswith("QMenu#themed"), line


def test_stylesheet_names_and_hero():
    css = stylesheet(get_theme("l"), "x")
    for n in NAMES:
        assert f"#{n}" in css
    assert "#miniBar" in css and "#pageNow" in css
    # hero 덮어쓰기는 pageNow, mini는 miniBar에만
    assert stylesheet(get_theme("h"), "x") != stylesheet(get_theme("g"), "x")


def test_rounded_art_fills_square_and_clips_corner(qapp):
    src = QPixmap(100, 40)
    src.fill(Qt.red)
    img = rounded_art(src, 64, 12, get_theme("light")).toImage()
    assert img.pixelColor(32, 2).red() > 200
    assert img.pixelColor(0, 0).alpha() == 0


def test_theme_and_radio_art(qapp):
    t = get_theme("light")
    img = theme_art(t, 64).toImage()
    assert img.pixelColor(2, 2).name().upper() == t.art[0]
    assert rounded_art(None, 64, 12, t).size().width() == 64
    assert radio_art_for(t, 64, 12).size().height() == 64


def test_load_fonts_falls_back(monkeypatch, qapp):
    monkeypatch.setattr(fonts, "FONT_DIR", Path("없는곳"))
    assert fonts.load_fonts() == "Malgun Gothic"


def test_load_fonts_real(qapp):
    assert fonts.load_fonts() == "Noto Sans KR"
