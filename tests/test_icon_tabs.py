from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QToolButton

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


def shown(theme="light"):
    t = make(); t.set_theme(get_theme(theme)); t.resize(300, 64)
    t.setStyleSheet("QToolButton { background: transparent; border: none; }"); t.show(); QApplication.processEvents()
    return t, QColor(get_theme(theme).tab_line).name()


def test_underline_is_inset_three_high_on_the_current_tab(qapp):
    t, _ = shown()
    b = t.findChildren(QToolButton)[1]; t.setCurrentIndex(1); QApplication.processEvents()
    r = t.underline_rect()
    assert (r.left(), r.right() + 1) == (b.x() + 12, b.x() + b.width() - 12)
    assert r.height() == 3 and r.bottom() == t.height() - 2      # 아래 테두리 1px 위


def test_underline_paints_with_rounded_top_corners(qapp):
    t, line = shown()
    img = t.grab().toImage(); r = t.underline_rect()
    mid = r.center().x()
    assert all(img.pixelColor(mid, y).name() == line for y in range(r.top(), r.bottom() + 1))
    assert img.pixelColor(r.left(), r.top()).name() != line     # 위 모서리는 둥글다
    assert img.pixelColor(r.left() + 1, r.bottom()).name() == line
    assert img.pixelColor(r.left() - 2, r.bottom()).name() != line   # 양옆은 띄운다
    assert img.pixelColor(r.right() + 2, r.bottom()).name() != line


def test_underline_moves_with_the_tab(qapp):
    t, line = shown()
    before = t.underline_rect()
    t.setCurrentIndex(2); QApplication.processEvents()
    img = t.grab().toImage(); after = t.underline_rect()
    assert after.left() > before.left()
    assert img.pixelColor(after.center()).name() == line and img.pixelColor(before.center()).name() != line
