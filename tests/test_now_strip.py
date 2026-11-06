from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QPixmap
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from funplayer.core.themes import THEMES, get_theme
from funplayer.ui.now_strip import ClickLabel, NowStrip


def art():
    pm = QPixmap(40, 40); pm.fill(Qt.red); return pm


def test_shape_and_set_track(qapp):
    s = NowStrip()
    assert s.objectName() == "nowStrip" and s.minimumHeight() == 86
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


def _mouse(widget, kind, x, y, button=Qt.LeftButton, buttons=Qt.LeftButton):
    pos = QPoint(x, y)
    event = QMouseEvent(kind, QPointF(pos), QPointF(widget.mapToGlobal(pos)), button, buttons, Qt.NoModifier)
    QApplication.sendEvent(widget, event)   # 무시하면 notify가 부모로 올려 보낸다


def _press(w, x=5, y=5):
    _mouse(w, QEvent.MouseButtonPress, x, y)


def _move(w, x, y):
    _mouse(w, QEvent.MouseMove, x, y, Qt.NoButton)


def _release(w, x=5, y=5):
    _mouse(w, QEvent.MouseButtonRelease, x, y, Qt.LeftButton, Qt.NoButton)


def _label(qapp):
    label = ClickLabel(); label.resize(40, 40)
    seen = []
    label.clicked.connect(lambda: seen.append(1))
    return label, seen


def test_click_fires_on_release_not_press(qapp):
    label, seen = _label(qapp)
    _press(label); assert seen == []
    _release(label); assert seen == [1]


def test_small_jitter_is_still_a_click(qapp):
    label, seen = _label(qapp)
    _press(label); _move(label, 6, 5); _release(label, 6, 5)
    assert seen == [1]


def test_drag_is_not_a_click(qapp):
    label, seen = _label(qapp)
    _press(label); _move(label, 30, 5); _move(label, 6, 5); _release(label, 6, 5)
    assert seen == []


def test_release_outside_is_not_a_click(qapp):
    label, seen = _label(qapp)
    _press(label); _release(label, 200, 5)
    assert seen == []


def test_right_button_is_not_a_click(qapp):
    label, seen = _label(qapp)
    _mouse(label, QEvent.MouseButtonPress, 5, 5, Qt.RightButton, Qt.RightButton)
    _mouse(label, QEvent.MouseButtonRelease, 5, 5, Qt.RightButton, Qt.NoButton)
    assert seen == []
