from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtTest import QTest

from funplayer.core.themes import THEMES, get_theme
from funplayer.ui.now_strip import NowStrip


def art():
    pm = QPixmap(40, 40); pm.fill(Qt.red); return pm


def test_shape_and_set_track(qapp):
    s = NowStrip()
    assert s.objectName() == "nowStrip" and s.minimumHeight() == 61
    s.set_track(art(), "제목", "가수", True, 0.25)
    assert s.title_label.text() == "제목" and s.sub_label.text() == "가수"
    assert s.toggle_button.toolTip() == "일시정지" and s.toggle_button.property("kind") == "playSm"
    assert s.progress.ratio == 0.25
    assert s.art_label.pixmap().toImage().pixelColor(20, 20).red() > 200
    s.set_track(art(), "제목", "가수", False, 3.0)
    assert s.toggle_button.toolTip() == "재생" and s.progress.ratio == 1.0


def test_same_pixmap_not_set_again(qapp):
    s = NowStrip(); pm = art(); s.set_track(pm, "a", "b", False, 0)
    calls = []; real = s.art_label.setPixmap
    s.art_label.setPixmap = lambda x: (calls.append(1), real(x))
    s.set_track(pm, "a", "b", False, 0.5)
    assert calls == []


def test_signals(qapp):
    s = NowStrip(); s.resize(380, 61); s.show(); seen = []
    s.prevClicked.connect(lambda: seen.append("prev"))
    s.toggleClicked.connect(lambda: seen.append("toggle"))
    s.nextClicked.connect(lambda: seen.append("next"))
    s.openClicked.connect(lambda: seen.append("open"))
    for w in (s.prev_button, s.toggle_button, s.next_button, s.art_label):
        QTest.mouseClick(w, Qt.LeftButton)
    assert seen == ["prev", "toggle", "next", "open"]


def test_set_theme_all(qapp):
    s = NowStrip()
    for t in THEMES:
        s.set_theme(t)
    before = s.toggle_button.icon().pixmap(18, 18).toImage()
    s.set_theme(get_theme("light"))
    assert s.toggle_button.icon().pixmap(18, 18).toImage() != before


def test_progress_paints_all_themes(qapp):
    s = NowStrip(); s.resize(380, 61)
    s.set_track(art(), "a", "b", True, 0.5)
    for t in THEMES:                # album 테마의 rgba(...) 색도 그린다
        s.set_theme(t); s.grab()
