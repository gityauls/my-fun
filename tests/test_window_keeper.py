import pytest
from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtGui import QGuiApplication
from fakes import FakePlayer
from funplayer.core.settings import Settings
from funplayer.ui.player_panel import PlayerPanel
from funplayer.ui.player_panel import TABS
from funplayer.ui import window_keeper
from funplayer.ui.window_keeper import DEFAULT_SIZE, MIN_SIZE, MINI_SIZE, WindowKeeper

@pytest.fixture
def make(qapp):
    made = []
    def build(store):
        s = Settings(store, lambda: None)
        p = PlayerPanel(s, player=FakePlayer()); k = WindowKeeper(p, s); k.start(); p.show()
        qapp.processEvents()
        made.append(p); return p, k
    yield build
    for p in made:
        p.shutdown(); p.deleteLater()

on_top = lambda p: bool(p.windowFlags() & Qt.WindowStaysOnTopHint)

WIDE = QRect(0, 0, 1600, 900)


@pytest.fixture
def wide(monkeypatch):
    """offscreen 화면(800x600)은 미니 막대(830)보다 좁아서, 보통 모니터 크기로 바꿔 놓고 잰다."""
    import funplayer.ui.window_keeper as wk
    screen = FakeScreen(WIDE)

    class Gui:
        primaryScreen = staticmethod(lambda: screen)
        screenAt = staticmethod(lambda pt: screen if WIDE.contains(pt) else None)

    monkeypatch.setattr(wk, "QGuiApplication", Gui)

def test_first_start_uses_default_size(make):
    p, _ = make({})
    assert p.size() == QSize(380, 680) == QSize(*DEFAULT_SIZE) and not p.is_mini and not on_top(p)

def test_restores_saved_normal_geometry(make):
    p, _ = make({"player_geometry": [50, 60, 400, 660]})
    assert p.geometry() == QRect(50, 60, 400, 660)

def test_old_saved_size_is_raised_to_minimum(make):
    p, _ = make({"player_geometry": [10, 10, 300, 480]})
    assert p.size() == QSize(*MIN_SIZE) and abs(p.x() - 10) <= 2 and p.height() >= 560   # offscreen은 틀 몫만큼 민다

def test_window_cannot_shrink_below_minimum(make):
    p, _ = make({})
    assert p.minimumSize() == QSize(*MIN_SIZE)
    p.resize(100, 100); assert p.size() == QSize(*MIN_SIZE)

@pytest.mark.parametrize("tab", TABS)
def test_minimum_size_holds_a_status_line_without_overlap(make, qapp, tab):
    p, _ = make({})
    p.controller.notify("안내"); p.refresh(); p.set_tab(tab)
    p.resize(*MIN_SIZE); qapp.processEvents()
    assert p.size() == QSize(*MIN_SIZE) and p.status_label.isVisible()
    assert p.layout().totalMinimumSize().height() <= MIN_SIZE[1]
    assert p.pages.height() >= p.pages.currentWidget().minimumSizeHint().height()
    if tab == "now":
        assert p.title_label.y() >= p.art_label.geometry().bottom()

def test_stack_minimum_follows_the_shown_page(make, qapp):
    p, _ = make({})
    assert p.pages.minimumHeight() == p.page_now.minimumSizeHint().height() > 400
    p.set_tab("playlist")
    assert p.pages.minimumHeight() < 200
    p.set_mini(True); assert p.pages.minimumHeight() == 1
    p.set_mini(False); p.set_tab("now")
    assert p.pages.minimumHeight() == p.page_now.minimumSizeHint().height() > 400

def test_on_top_toggle_keeps_chrome_flags(qapp):
    s = Settings({"player_mini": True, "player_mini_on_top": True}, lambda: None)
    p = PlayerPanel(s, player=FakePlayer()); p.use_window_chrome()
    k = WindowKeeper(p, s); k.start(); p.show(); qapp.processEvents()
    try:
        assert on_top(p) and p.windowFlags() & Qt.FramelessWindowHint
        p.set_mini(False)
        assert not on_top(p) and p.windowFlags() & Qt.FramelessWindowHint
        assert p.windowFlags() & Qt.WindowMinimizeButtonHint and p.testAttribute(Qt.WA_TranslucentBackground)
    finally:
        p.shutdown(); p.deleteLater()

def test_offscreen_geometry_is_centered(make):
    p, _ = make({"player_geometry": [5000, 5000, 380, 660]})
    assert QGuiApplication.screenAt(p.geometry().center()) is not None and p.size() == QSize(380, 660)

def test_starts_in_mini_on_top_at_saved_place(make, wide):
    p, _ = make({"player_mini": True, "player_mini_on_top": True, "player_mini_geometry": [30, 40, 850, 104]}); g = p.geometry()
    assert p.is_mini and on_top(p) and (g.x(), g.y(), g.width()) == (30, 40, 850)
    assert p.minimumHeight() == p.maximumHeight() == p.sizeHint().height() == 104

def test_old_mini_geometry_raised(make, wide):
    p, _ = make({"player_mini": True, "player_mini_geometry": [5, 5, 304, 100]})
    g = p.geometry()
    assert (g.x(), g.y(), g.width(), g.height()) == (5, 5, 830, 104) and (830, 104) == MINI_SIZE
    assert p.minimumWidth() == 830

def test_mini_width_is_kept_per_mode(make, wide):
    store = {"player_mini_geometry": [5, 5, 870, 104]}; p, k = make(store)
    p.set_mini(True); assert p.width() == 870
    p.resize(890, 104); p.set_mini(False); assert store["player_mini_geometry"][2] == 890
    p.set_mini(True); assert p.width() == 890

def test_offscreen_mini_recentres(make):
    p, _ = make({"player_mini": True, "player_mini_geometry": [5000, 5000, 304, 100]})
    assert QGuiApplication.screenAt(p.geometry().center()) is not None and p.size() == QSize(830, 104)

@pytest.mark.parametrize("x", [-200, 500])
def test_full_mini_width_lies_on_the_screen(make, wide, x):
    area = WIDE
    p, _ = make({"player_mini": True, "player_mini_geometry": [area.left() + x, 40, 304, 100]})
    g = p.geometry()
    assert area.left() <= g.left() and g.right() <= area.right() and g.width() == 830

def test_chrome_survives_on_top_toggle(qapp):
    s = Settings({"player_mini_on_top": True}, lambda: None)
    p = PlayerPanel(s, player=FakePlayer()); p.use_window_chrome()
    WindowKeeper(p, s).start(); p.show(); qapp.processEvents()
    try:
        p.set_mini(True); qapp.processEvents()
        assert on_top(p) and p.isVisible() and p.size() == QSize(830, 104)
        assert p.windowFlags() & Qt.FramelessWindowHint and p.windowFlags() & Qt.WindowMinimizeButtonHint
        assert p.testAttribute(Qt.WA_TranslucentBackground)
    finally:
        p.shutdown(); p.deleteLater()

def test_toggle_saves_each_mode_and_restores_other(make):
    store = {"player_geometry": [50, 60, 400, 660], "player_mini_on_top": True}; p, _ = make(store)
    p.set_mini(True)
    assert store["player_geometry"] == [50, 60, 400, 660] and on_top(p)
    p.move(70, 80); g = p.geometry(); p.set_mini(False)   # 보이는 창의 move는 틀 기준이라 안쪽 자리로 비교
    assert store["player_mini_geometry"][:2] == [g.x(), g.y()] and g.x() >= 70
    assert p.geometry() == QRect(50, 60, 400, 660)
    assert not on_top(p) and p.maximumHeight() == 780

def test_on_top_option(make):
    p, _ = make({"player_mini": True}); assert not on_top(p)   # 기본은 다른 창 아래로 내려간다
    p.actions["mini_on_top"].trigger(); assert on_top(p)
    p.actions["mini_on_top"].trigger(); assert p.is_mini and not on_top(p)
    p.actions["mini_on_top"].trigger(); assert on_top(p)
    p.set_mini(False); assert not on_top(p)

def test_save_writes_current_mode(make):
    store = {}; p, k = make(store); p.setGeometry(20, 30, 390, 660); k.save()
    assert store["player_geometry"] == [20, 30, 390, 660]

def test_runtime_mini_is_as_short_as_its_content(make, qapp):
    p, _ = make({}); p.set_mini(True); qapp.processEvents()
    assert p.height() == p.sizeHint().height() == 104

def test_back_to_normal_keeps_layout_minimum_height(make, qapp):
    p, _ = make({}); p.set_mini(True); qapp.processEvents(); p.set_mini(False); qapp.processEvents()
    assert p.minimumHeight() == MIN_SIZE[1] >= p.layout().totalMinimumSize().height() > 200

def test_mini_start_without_mini_place_uses_normal_place(make, wide):
    p, _ = make({"player_mini": True, "player_geometry": [50, 60, 400, 660]}); g = p.geometry()
    assert p.is_mini and (g.x(), g.y(), g.width()) == (50, 60, 830)

def test_mini_start_without_any_place_uses_default_width_centered(make, wide):
    p, _ = make({"player_mini": True})
    screen = WIDE
    assert p.is_mini and p.width() == 830 and p.geometry().center().x() in (screen.center().x(), screen.center().x() + 1)

class FakeScreen:
    def __init__(self, geometry, available=None):
        self.geometry, self.available = geometry, available or geometry

    def availableGeometry(self):
        return self.available


def screens(monkeypatch, *items):
    class App:
        @staticmethod
        def screenAt(point):
            return next((s for s in items if s.geometry.contains(point)), None)

        @staticmethod
        def primaryScreen():
            return items[0]
    monkeypatch.setattr(window_keeper, "QGuiApplication", App)


FULL_HD = FakeScreen(QRect(0, 0, 1920, 1080), QRect(0, 0, 1920, 1040))   # 작업 표시줄 40


def fit(rect):
    WindowKeeper._fit_height(rect)
    return rect


def test_old_window_near_the_bottom_moves_up(monkeypatch):
    screens(monkeypatch, FULL_HD)
    assert fit(QRect(10, 900, 380, 610)) == QRect(10, 430, 380, 610)


def test_window_behind_the_taskbar_moves_up(monkeypatch):
    screens(monkeypatch, FULL_HD)
    assert fit(QRect(10, 450, 380, 610)).bottom() == 1039


def test_window_inside_the_work_area_stays_put(monkeypatch):
    screens(monkeypatch, FULL_HD)
    assert fit(QRect(10, 430, 380, 610)) == QRect(10, 430, 380, 610)


def test_window_taller_than_the_work_area_stays_put(monkeypatch):
    screens(monkeypatch, FULL_HD)
    assert fit(QRect(10, 20, 380, 1200)) == QRect(10, 20, 380, 1200)


def test_window_across_stacked_screens_stays_put(monkeypatch):
    screens(monkeypatch, FULL_HD, FakeScreen(QRect(0, 1080, 1920, 1080)))
    assert fit(QRect(10, 800, 380, 610)) == QRect(10, 800, 380, 610)


def test_saved_window_passes_through_the_vertical_fit(make, monkeypatch):
    seen = []
    real = WindowKeeper._fit_height
    monkeypatch.setattr(WindowKeeper, "_fit_height", staticmethod(lambda r: (seen.append(QRect(r)), real(r))))
    p, _ = make({"player_geometry": [10, 20, 360, 480]})
    assert seen == [QRect(10, 20, 360, MIN_SIZE[1])]


def test_mini_near_the_bottom_stays_on_screen(make):
    area = QGuiApplication.primaryScreen().availableGeometry()
    p, _ = make({"player_mini": True, "player_mini_geometry": [10, area.bottom() - 20, 680, 104]})
    assert p.geometry().bottom() <= area.bottom()
