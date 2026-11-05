from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QToolButton

from funplayer.core.themes import THEMES, get_theme
from funplayer.ui.icon_tabs import IconTabs


def make():
    t = IconTabs()
    for icon, title in (("music", "하나"), ("list", "둘"), ("radio", "셋")):
        t.addTab(icon, title)
    return t


def test_add_and_first_selected(qapp):
    t = make()
    assert t.count() == 3 and t.currentIndex() == 0 and t.objectName() == "tabs"
    assert [t.tabText(i) for i in range(3)] == ["하나", "둘", "셋"]
    b = t.findChildren(QToolButton)
    assert len(b) == 3 and all(x.toolButtonStyle() == Qt.ToolButtonTextUnderIcon for x in b)
    assert all(x.focusPolicy() == Qt.NoFocus for x in b)
    assert t.minimumHeight() == 64


def test_exclusive_click_emits_once(qapp):
    t = make(); t.resize(300, 64); t.show()
    seen = []; t.currentChanged.connect(seen.append)
    b = t.findChildren(QToolButton)
    QTest.mouseClick(b[2], Qt.LeftButton)
    assert t.currentIndex() == 2 and seen == [2]
    assert [x.isChecked() for x in b] == [False, False, True]
    QTest.mouseClick(b[2], Qt.LeftButton)     # 고른 탭을 다시 눌러도 그대로
    assert t.currentIndex() == 2 and seen == [2] and b[2].isChecked()


def test_set_current_index(qapp):
    t = make(); seen = []; t.currentChanged.connect(seen.append)
    t.setCurrentIndex(1); t.setCurrentIndex(1); t.setCurrentIndex(9)
    assert t.currentIndex() == 1 and seen == [1]


def test_set_theme_changes_icons(qapp):
    t = make(); b = t.findChildren(QToolButton)[1]
    before = b.icon().pixmap(20, 20).toImage()
    t.set_theme(get_theme("dark"))
    assert b.icon().pixmap(20, 20).toImage() != before
    for th in THEMES:
        t.set_theme(th)
