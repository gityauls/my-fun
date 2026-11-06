import pytest
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QContextMenuEvent
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication, QWidget
from fakes import FakePlayer, FakeRunner
from funplayer.core.settings import Settings
from funplayer.core.themes import THEMES, get_theme
from funplayer.ui.player_panel import PlayerPanel
from funplayer.ui.style import stylesheet
from funplayer.ui.title_bar import TITLE_HEIGHT, EdgeGrips, TitleBar


class FakeHandle:
    def __init__(self):
        self.moves = 0
        self.resizes = []

    def startSystemMove(self):
        self.moves += 1
        return True

    def startSystemResize(self, edges):
        self.resizes.append(int(edges))
        return True


@pytest.fixture
def panel(qapp):
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), runner=FakeRunner())
    p.resize(380, 620)
    yield p
    p.shutdown(); p.deleteLater()


@pytest.fixture
def host(qapp):
    """TitleBar를 얹은 빈 창. windowHandle은 가짜."""
    win = QWidget()
    win.resize(300, 100)
    bar = TitleBar(win)
    bar.resize(300, TITLE_HEIGHT)
    handle = FakeHandle()
    win.windowHandle = lambda: handle
    yield win, bar, handle
    win.deleteLater()


def move(w, pos, buttons=Qt.LeftButton):
    QApplication.sendEvent(w, QMouseEvent(QEvent.MouseMove, QPointF(pos), QPointF(pos),
                                          Qt.NoButton, buttons, Qt.NoModifier))


# ---- 상단바 ----

@pytest.mark.parametrize("name,signal", [("settings_btn", "settingsClicked"), ("mini_btn", "miniClicked"),
                                         ("min_btn", "minimizeClicked"), ("close_btn", "closeClicked")])
def test_titlebar_buttons_emit(host, name, signal):
    _, bar, _ = host
    spy = QSignalSpy(getattr(bar, signal))
    getattr(bar, name).click()
    assert len(spy) == 1


def test_titlebar_shape_and_tips(host):
    _, bar, _ = host
    assert bar.objectName() == "titleBar" and bar.height() == TITLE_HEIGHT == 44
    assert bar.title_label.text() == "my-fun"
    assert bar.mini_btn.toolTip() == "작게 보기" and bar.settings_btn.toolTip() == "설정"
    assert (bar.close_btn.width(), bar.close_btn.height()) == (30, 28)
    assert not hasattr(bar, "max_btn")   # 창은 정해진 크기 안에서만 늘어난다


def test_titlebar_theme_changes_icons(host):
    _, bar, _ = host
    before = bar.close_btn.icon().pixmap(16, 16).toImage()
    bar.set_theme(get_theme("dark"))
    assert before != bar.close_btn.icon().pixmap(16, 16).toImage()


def test_titlebar_drag_starts_system_move_once(host):
    _, bar, handle = host
    QTest.mousePress(bar, Qt.LeftButton, pos=QPoint(100, 20))
    assert handle.moves == 0   # 누르기만 하면 움직이지 않는다: 더블클릭이 살아야 한다
    move(bar, QPoint(103 + QApplication.startDragDistance(), 20))
    move(bar, QPoint(140, 20))
    assert handle.moves == 1


def test_titlebar_small_move_or_other_button_does_not_drag(host):
    _, bar, handle = host
    QTest.mousePress(bar, Qt.LeftButton, pos=QPoint(100, 20))
    move(bar, QPoint(101, 20))
    QTest.mouseRelease(bar, Qt.LeftButton, pos=QPoint(101, 20))
    move(bar, QPoint(150, 20))
    QTest.mousePress(bar, Qt.RightButton, pos=QPoint(100, 20))
    move(bar, QPoint(150, 20), Qt.RightButton)
    assert handle.moves == 0


def test_titlebar_right_click_requests_menu(host):
    _, bar, _ = host
    seen = []
    bar.menu_requested.connect(seen.append)
    QApplication.sendEvent(bar, QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(5, 6), QPoint(55, 66)))
    assert seen == [QPoint(55, 66)]


# ---- 가장자리 ----

@pytest.fixture
def grips(qapp):
    win = QWidget()
    win.resize(300, 400)
    handle = FakeHandle()
    win.windowHandle = lambda: handle
    g = EdgeGrips(win)
    yield win, g, handle
    win.deleteLater()


def test_grips_cover_eight_edges_and_follow_resize(grips):
    win, g, _ = grips
    assert len(g.grips) == 8
    win.show()
    win.resize(500, 450)
    r = g.grips[Qt.RightEdge].geometry()
    assert r.right() == 499 and r.width() == 6
    b = g.grips[Qt.BottomEdge | Qt.RightEdge].geometry()
    assert b.right() == 499 and b.bottom() == 449


def test_grip_press_starts_system_resize(grips):
    _, g, handle = grips
    corner = Qt.TopEdge | Qt.LeftEdge
    QTest.mousePress(g.grips[corner], Qt.LeftButton, pos=QPoint(1, 1))
    QTest.mousePress(g.grips[Qt.BottomEdge], Qt.LeftButton, pos=QPoint(1, 1))
    QTest.mousePress(g.grips[Qt.LeftEdge], Qt.RightButton, pos=QPoint(1, 1))
    assert handle.resizes == [int(corner), int(Qt.BottomEdge)]


def test_grips_horizontal_only(grips):
    win, g, _ = grips
    win.show()
    g.set_enabled_edges(horizontal_only=True)
    shown = [e for e, w in g.grips.items() if not w.isHidden()]
    assert sorted(int(e) for e in shown) == sorted((int(Qt.LeftEdge), int(Qt.RightEdge)))
    g.set_enabled_edges(horizontal_only=False)
    assert all(not w.isHidden() for w in g.grips.values())


def test_grips_are_hit_testable_on_a_clear_window(grips, qapp):
    # 둥근 모서리 바깥은 투명이라 알파가 0이면 Windows가 누르기를 뒤 창으로 넘긴다
    _, g, _ = grips
    w = g.grips[Qt.TopEdge | Qt.LeftEdge]
    img = w.grab().toImage()
    from PyQt5.QtGui import QPixmap
    pm = QPixmap(w.size()); pm.fill(Qt.transparent)
    w.render(pm, flags=QWidget.DrawChildren)
    assert pm.toImage().pixelColor(0, 0).alpha() > 0 and not img.isNull()


# ---- 패널 ----

def test_chrome_keeps_flags_minimizable(panel):
    panel.use_window_chrome()
    assert panel.chrome and panel.windowFlags() & Qt.FramelessWindowHint
    assert panel.windowFlags() & Qt.WindowMinimizeButtonHint
    assert panel.testAttribute(Qt.WA_TranslucentBackground)
    assert isinstance(panel.grips, EdgeGrips)


def test_panel_without_chrome_stays_plain(panel):      # 6단계 캘린더용
    assert not panel.windowFlags() & Qt.FramelessWindowHint
    assert not panel.testAttribute(Qt.WA_TranslucentBackground)
    assert not panel.chrome and panel.grips is None
    assert panel.title_bar.objectName() == "titleBar" and panel.title_bar.height() == 44


def test_grips_sit_above_content(panel):
    panel.use_window_chrome(); panel.show(); QApplication.processEvents()
    x, y = panel.width() - 1, panel.height() // 2
    assert panel.childAt(x, y) is panel.grips.grips[Qt.RightEdge]


def test_root_wraps_everything(panel):
    root = panel.root
    assert root.objectName() == "root" and root.parent() is panel
    for w in (panel.title_bar, panel.tab_bar, panel.pages, panel.status_label, panel.now_strip):
        assert root.isAncestorOf(w)


def test_titlebar_buttons_act_on_panel_without_chrome(panel):
    seen = []
    panel.show(); QApplication.processEvents()
    def on_close(event):
        seen.append("close")
        event.accept()
    panel.closeEvent = on_close
    assert not panel.is_mini
    panel.title_bar.mini_btn.click()
    assert panel.is_mini
    panel.set_mini(False)
    panel.title_bar.min_btn.click()
    assert panel.isMinimized()
    panel.showNormal()
    panel.title_bar.close_btn.click()
    assert seen == ["close"]


def test_right_click_opens_view_menu(panel):
    seen = []
    panel.view_menu.exec_ = seen.append
    panel.title_bar.menu_requested.emit(QPoint(7, 8))
    assert seen == [QPoint(7, 8)]


def test_theme_reaches_title_bar(panel):
    before = panel.title_bar.close_btn.icon().pixmap(16, 16).toImage()
    panel.apply_theme(get_theme("dark"))
    assert before != panel.title_bar.close_btn.icon().pixmap(16, 16).toImage()


def test_mini_hides_title_bar(panel):
    panel.show()
    panel.set_mini(True); assert panel.title_bar.isHidden() and panel.corner_radius() == 24
    panel.set_mini(False); assert not panel.title_bar.isHidden() and panel.corner_radius() == 20


def test_hero_meets_status_line_with_square_bottom(panel):
    page = panel.page_now
    panel.show()
    panel.controller.notify("안내"); panel.refresh()
    assert page.property("flush") == "true"
    panel.controller.notify(""); panel.refresh()
    assert page.property("flush") == "false"


def test_refresh_does_not_repolish(panel, monkeypatch):
    panel.show(); panel.refresh()
    calls = []
    monkeypatch.setattr(panel, "_repolish", calls.append)
    panel.refresh(); panel.refresh()
    assert calls == []


@pytest.mark.parametrize("t", THEMES, ids=lambda t: t.id)
def test_stylesheet_rounds_and_squares(t):
    css = stylesheet(t)
    assert "border-top-left-radius: 19px" in css and "border-bottom-right-radius: 19px" in css
    assert "border-radius: 20px" in css


def test_settings_button_sits_left_of_mini_with_its_icon(host):
    _, bar, _ = host
    bar.resize(500, TITLE_HEIGHT); bar.layout().activate()
    assert bar.settings_btn.x() + bar.settings_btn.width() <= bar.mini_btn.x()
    assert not bar.settings_btn.icon().isNull()


def test_settings_button_opens_settings(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(PlayerPanel, "show_settings", lambda self, modal=True: calls.append(modal))
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), runner=FakeRunner())
    p.title_bar.settings_btn.click()
    assert calls == [True]
    p.shutdown(); p.deleteLater()


def test_kept_small_mini_button_on_the_now_page(panel):
    assert panel.mini_button.toolTip() == "작게 보기" and panel.mini_button.parent() is not panel.title_bar
