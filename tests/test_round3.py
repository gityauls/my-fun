"""Stage 5.5 round 3: ticker, theme flip, equalizer on the now tab, window limits."""
import numpy as np
import pytest
from PyQt5.QtCore import QEvent, QSize, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from funplayer.core.contrast import contrast
from funplayer.core.settings import Settings
from funplayer.core.themes import THEMES
from funplayer.ui.hover_arrow import HoverArrow
from funplayer.ui.player_panel import NOW_BARS, PlayerPanel
from funplayer.ui.style import strip_surface
from funplayer.ui.ticker_label import GAP, HOLD_TICKS, TickerLabel
from funplayer.ui.window_keeper import DEFAULT_SIZE, MAX_SIZE, MIN_SIZE, MINI_SIZE, WindowKeeper
from fakes import FakePlayer


@pytest.fixture
def make(qapp):
    made = []

    def build(store=None, keeper=True):
        store = {} if store is None else store
        p = PlayerPanel(Settings(store, lambda: None), player=FakePlayer())
        if keeper:
            WindowKeeper(p, p.settings).start()
        made.append(p)
        return p, store

    yield build
    for p in made:
        p.shutdown(); p.deleteLater()


# ---- 흐르는 글자 ----

def test_short_text_never_moves(qapp):
    t = TickerLabel("짧다"); t.resize(300, 24); t.show(); qapp.processEvents()
    assert not t.overflowing and not t.moving
    t.deleteLater()


def test_long_text_holds_then_moves_then_loops(qapp):
    t = TickerLabel(); t.resize(60, 24); t.show(); t.setText("아주 긴 제목 " * 8); qapp.processEvents()
    assert t.moving and t.offset == 0
    for _ in range(HOLD_TICKS):
        t.advance()
    assert t.offset == 0
    t.advance(); assert t.offset == 1
    lap = t.fontMetrics().horizontalAdvance(t.text()) + GAP
    for _ in range(lap - 1):
        t.advance()
    assert t.offset == 0   # 한 바퀴 돌면 처음 자리에서 다시 멈춘다
    t.advance(); assert t.offset == 0
    t.deleteLater()


def test_same_text_does_not_restart_and_new_text_does(qapp):
    t = TickerLabel(); t.resize(60, 24); t.show(); t.setText("아주 긴 제목 " * 8)
    for _ in range(HOLD_TICKS + 5):
        t.advance()
    t.setText(t.text()); assert t.offset == 5
    t.setText("또 다른 아주 긴 제목 " * 8); assert t.offset == 0
    t.deleteLater()


def test_stops_when_hidden_or_when_it_fits(qapp):
    t = TickerLabel(); t.resize(60, 24); t.show(); t.setText("아주 긴 제목 " * 8); qapp.processEvents()
    t.hide(); assert not t.moving
    t.show(); qapp.processEvents(); assert t.moving
    t.resize(3000, 24); qapp.processEvents(); assert not t.moving and t.offset == 0
    t.deleteLater()


def test_strip_labels_tick_with_full_text(make, qapp):
    p, _ = make(keeper=False)
    p.resize(*DEFAULT_SIZE); p.show(); p.set_tab("playlist"); qapp.processEvents()
    long = "아주 긴 제목 " * 10
    p.now_strip._set_text(p.now_strip.title_label, long); qapp.processEvents()
    assert p.now_strip.title_label.text() == long and p.now_strip.title_label.moving


# ---- 테마 넘기기 ----

def test_step_theme_walks_all_themes_wraps_and_saves(make):
    p, store = make()
    ids = [t.id for t in THEMES]
    assert p.theme.id == ids[0]
    p.step_theme(-1); assert p.theme.id == ids[-1] and store["player_theme"] == ids[-1]
    p.step_theme(1); assert p.theme.id == ids[0]
    for want in ids[1:]:
        p.step_theme(1); assert p.theme.id == want


@pytest.mark.parametrize("prev,next_", [("theme_prev_button", "theme_next_button"),
                                        ("mini_theme_prev_button", "mini_theme_next_button")])
def test_arrow_buttons_flip_the_theme(make, prev, next_):
    p, _ = make()
    start = p.theme.id
    getattr(p, next_).click(); assert p.theme.id != start
    getattr(p, prev).click(); assert p.theme.id == start


def test_arrow_is_invisible_until_the_mouse_is_over_it(qapp):
    b = HoverArrow("chevR", "다음 테마"); b.set_color("#112233")
    assert b.icon().isNull()
    QApplication.sendEvent(b, QEvent(QEvent.Enter)); assert not b.icon().isNull()
    QApplication.sendEvent(b, QEvent(QEvent.Leave)); assert b.icon().isNull()
    b.deleteLater()


def test_arrows_sit_on_both_sides_of_the_cover_in_each_view(make, qapp):
    p, _ = make(); p.show(); qapp.processEvents()
    art = p.art_label.geometry()
    assert p.theme_prev_button.geometry().right() < art.left()
    assert p.theme_next_button.geometry().left() > art.right()
    assert p.theme_prev_button.isVisible() and p.theme_next_button.isVisible()

    p.set_mini(True); qapp.processEvents()
    art = p.art_label.geometry()
    assert p.art_label.parent() is p.mini_bar
    assert p.mini_theme_prev_button.isVisible() and p.mini_theme_next_button.isVisible()
    assert p.mini_theme_prev_button.geometry().right() < art.left()
    assert p.mini_theme_next_button.geometry().left() > art.right()
    assert p.mini_theme_prev_button.x() >= 0 and p.width() == MINI_SIZE[0]

    p.set_mini(False); qapp.processEvents()
    assert p.theme_prev_button.geometry().right() < p.art_label.geometry().left()


def test_arrows_fit_at_the_narrowest_window(make, qapp):
    p, _ = make(); p.show(); p.resize(*MIN_SIZE); qapp.processEvents()
    assert p.theme_prev_button.x() >= 0
    assert p.theme_next_button.geometry().right() < p.page_now.width()


# ---- 이퀄라이저 ----

def test_equalizer_sits_between_title_and_seek(make, qapp):
    p, _ = make(); p.show(); qapp.processEvents()
    eq = p.now_spectrum.geometry()
    assert p.artist_label.mapTo(p.page_now, p.artist_label.rect().bottomLeft()).y() < eq.top()
    assert eq.bottom() < p.seek_slider.y() and p.seek_slider.y() < p.play_button.y() < p.mute_button.y()


def test_equalizer_takes_the_extra_height(make, qapp):
    p, _ = make(); p.show(); p.resize(*MIN_SIZE); qapp.processEvents()
    low = p.now_spectrum.height()
    p.resize(MIN_SIZE[0], MAX_SIZE[1]); qapp.processEvents()
    assert p.now_spectrum.height() - low == MAX_SIZE[1] - MIN_SIZE[1]


def test_equalizer_is_fed_on_the_now_tab(make, qapp):
    p, _ = make(); p.show(); qapp.processEvents()
    p._player.latest_block = lambda: np.sin(np.linspace(0, 400, 4096)).reshape(-1, 1).repeat(2, axis=1)
    p._spectrum_playing = lambda: True
    p._spectrum_tick()
    assert len(p.now_spectrum.levels) == NOW_BARS and any(p.now_spectrum.levels)


def test_equalizer_colours_follow_the_theme(make):
    p, _ = make()
    first = p.now_spectrum.bar_color(0, NOW_BARS)
    seen = set()
    for _ in THEMES:
        seen.add(p.now_spectrum.bar_color(0, NOW_BARS)); p.step_theme(1)
    assert first in seen and len(seen) > 3


# ---- 재생 띠 ----

@pytest.mark.parametrize("t", THEMES, ids=lambda t: t.id)
def test_strip_surface_is_readable(t):
    bg = strip_surface(t)
    assert contrast(t.ink, bg) >= 4.5 and contrast(t.mute, bg) >= 3.5


def test_strip_is_140_percent(make, qapp):
    p, _ = make(); p.set_tab("playlist"); p.show(); qapp.processEvents()
    s = p.now_strip
    assert s.height() == 86 and s.art_label.width() == 56 and s.toggle_button.width() == 48
    assert s.y() == p.tab_bar.geometry().bottom() + 1 and s.y() < p.pages.y()
    assert s.progress.y() > s.art_label.y()


# ---- 창 크기 ----

def test_normal_window_stops_at_max_size(make):
    p, _ = make()
    assert p.maximumSize() == QSize(*MAX_SIZE)
    p.resize(2000, 2000); assert p.size() == QSize(*MAX_SIZE)


def test_saved_big_window_is_brought_inside_the_limit(make):
    p, _ = make({"player_geometry": [10, 10, 1500, 1000]})
    assert p.size() == QSize(*MAX_SIZE)


def test_mini_keeps_free_width_and_returns_to_the_limit(make):
    p, store = make()
    p.set_mini(True)
    assert p.maximumWidth() > MAX_SIZE[0] and p.height() == MINI_SIZE[1]
    p.resize(900, MINI_SIZE[1]); assert p.width() == 900
    p.set_mini(False)
    assert p.maximumSize() == QSize(*MAX_SIZE)


def test_maximize_from_outside_is_undone(make, qapp):
    p, _ = make(); p.show(); qapp.processEvents()
    p.showMaximized(); qapp.processEvents(); qapp.processEvents()
    assert not p.isMaximized()
    assert p.width() <= MAX_SIZE[0] and p.height() <= MAX_SIZE[1]


def test_title_double_click_does_nothing(make, qapp):
    p, _ = make(); p.show(); qapp.processEvents()
    size = p.size()
    QTest.mouseDClick(p.title_bar, Qt.LeftButton)
    qapp.processEvents()
    assert p.size() == size and not p.isMaximized()


# ---- 항상 위 ----

def test_mini_is_not_on_top_by_default_but_a_saved_choice_stands(make):
    on_top = lambda p: bool(p.windowFlags() & Qt.WindowStaysOnTopHint)
    p, _ = make({"player_mini": True}); assert not on_top(p)
    q, _ = make({"player_mini": True, "player_mini_on_top": True}); assert on_top(q)
