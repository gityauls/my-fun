"""숨은 장면: 발동 조건, 그림, 덮개, 패널 연결."""
from datetime import datetime

import pytest
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QImage, QMouseEvent, QPainter, QPixmap
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QWidget

from funplayer.core.easter import MidnightOnce, TapCounter
from funplayer.core.settings import Settings
from funplayer.ui.egg_overlay import EggOverlay
from funplayer.ui.egg_sprites import GRID, SCENES
from funplayer.ui.player_panel import PlayerPanel
from fakes import FakePlayer


# ---- 조건 ----

def test_tap_counter_fires_on_the_last_tap_and_starts_over():
    c = TapCounter(3, 2.0)
    assert [c.tap(t) for t in (0, .5, 1)] == [False, False, True]
    assert [c.tap(t) for t in (1.1, 1.2, 1.3)] == [False, False, True]


def test_tap_counter_forgets_old_taps():
    c = TapCounter(3, 2.0)
    assert [c.tap(t) for t in (0, .5, 2.6, 3)] == [False, False, False, False]
    assert c.tap(3.1) is True


@pytest.mark.parametrize("now, playing, want", [
    (datetime(2026, 11, 7, 0, 0, 0), True, True),
    (datetime(2026, 11, 7, 0, 0, 59), True, True),
    (datetime(2026, 11, 7, 0, 1, 0), True, False),
    (datetime(2026, 11, 7, 12, 0, 0), True, False),
    (datetime(2026, 11, 7, 0, 0, 0), False, False),
])
def test_midnight_window(now, playing, want):
    assert MidnightOnce().due(now, playing) is want


def test_midnight_is_once_a_day():
    m = MidnightOnce()
    m.done(datetime(2026, 11, 7, 0, 0, 1))
    assert not m.due(datetime(2026, 11, 7, 0, 0, 2), True)
    assert m.due(datetime(2026, 11, 8, 0, 0, 2), True)


# ---- 그림 ----

def render(scene, t):
    img = QImage(GRID, GRID, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    scene.draw(p, t)
    p.end()
    return img


@pytest.mark.parametrize("key", SCENES)
def test_every_scene_draws_through_its_whole_length(qapp, key):
    scene = SCENES[key]
    seen = set()
    t = 0.0
    while t < scene.length:
        img = render(scene, t)
        ink = sum(img.pixelColor(x, y).alpha() > 0 for y in range(GRID) for x in range(GRID))
        assert ink > 10, (key, t)
        seen.add(img.bits().asstring(img.byteCount()))
        t += 0.25
    assert len(seen) > 8   # 움직인다


def test_every_scene_leaves_the_corners_see_through(qapp):
    for key, scene in SCENES.items():
        assert render(scene, 1.0).pixelColor(0, 0).alpha() < 255, key


# ---- 덮개 ----

class Clock:
    now = 100.0

    def __call__(self):
        return self.now


class FakeArt(QWidget):
    def pixmap(self):
        return QPixmap(self.size())


def make_stage(size, art_rect, mini):
    parent = QWidget()
    parent.resize(*size)
    art = FakeArt(parent)
    art.setGeometry(*art_rect)
    clock = Clock()
    over = EggOverlay(parent, art, lambda: mini, clock)
    parent.show()
    return parent, art, over, clock


@pytest.fixture
def stage(qapp):
    made = make_stage((380, 680), (82, 127, 216, 216), False)
    yield made
    made[2].stop()
    made[0].deleteLater()


def test_overlay_never_takes_the_mouse(stage):
    assert stage[2].testAttribute(Qt.WA_TransparentForMouseEvents)


def test_overlay_plays_then_leaves_by_itself(stage):
    parent, _, over, clock = stage
    assert over.play("fuzz") is True
    assert over.isVisible() and over.key == "fuzz" and over.geometry() == parent.rect()
    clock.now += SCENES["fuzz"].length + .1
    over.tick()
    assert not over.isVisible() and over.key is None


def test_overlay_does_not_stack_scenes(stage):
    _, _, over, _ = stage
    assert over.play("tape") and over.play("ham") is False and over.key == "tape"


def test_overlay_waits_while_the_window_is_hidden(stage):
    parent, _, over, _ = stage
    parent.hide()
    assert over.play("tape") is False and over.key is None


def test_ufo_hides_the_real_cover_and_gives_it_back(stage):
    _, art, over, clock = stage
    over.play("ufo")
    assert art.graphicsEffect() is not None
    over.grab()
    clock.now += SCENES["ufo"].length + .1
    over.tick()
    assert art.graphicsEffect() is None


@pytest.mark.parametrize("key", SCENES)
@pytest.mark.parametrize("size", [(340, 650), (380, 680), (460, 780)])
def test_scene_and_speech_stay_inside_the_window(stage, key, size):
    parent, art, over, clock = stage
    parent.resize(*size)
    art.move((size[0] - 216) // 2, 127)
    over.play(key)
    assert over.sprite_rect().left() >= 0 and over.sprite_rect().right() < size[0]
    assert parent.rect().contains(over.bubble_rect())


def test_mini_scene_fits_the_bar(qapp):
    parent, art, over, _ = make_stage((830, 104), (28, 12, 80, 80), True)
    for key in SCENES:
        over.play(key)
        assert parent.rect().contains(over.sprite_rect()) and parent.rect().contains(over.bubble_rect())
        over.stop()
    assert art.graphicsEffect() is None
    parent.deleteLater()


# ---- 패널 ----

@pytest.fixture
def panel(qapp):
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer())
    p.resize(380, 680)
    p.show()
    opened = []
    p._art_tap_timer.timeout.disconnect()
    p._art_tap_timer.timeout.connect(lambda: opened.append(1))
    p.opened = opened
    yield p
    p.shutdown()
    p.deleteLater()


def test_one_cover_click_opens_info_after_a_short_wait(panel):
    panel.art_label.clicked.emit()
    assert panel.opened == [] and panel._art_tap_timer.isActive()
    panel._art_tap_timer.timeout.emit()
    assert panel.opened == [1]


def test_five_cover_clicks_call_the_cassette_and_no_info(panel):
    for _ in range(5):
        panel.art_label.clicked.emit()
    assert panel.egg_overlay.key == "tape" and not panel._art_tap_timer.isActive()


def test_real_rapid_cover_clicks_count_double_clicks_too(panel):
    # 빠르게 누르면 Windows는 짝수 번째 누름을 더블클릭으로 보낸다
    label = panel.art_label
    at = QPointF(label.rect().center())

    def send(kind, buttons):
        QApplication.sendEvent(label, QMouseEvent(kind, at, Qt.LeftButton, buttons, Qt.NoModifier))

    for i in range(5):
        send(QEvent.MouseButtonDblClick if i % 2 else QEvent.MouseButtonPress, Qt.LeftButton)
        send(QEvent.MouseButtonRelease, Qt.NoButton)
    assert panel.egg_overlay.key == "tape"


def test_seven_title_taps_call_the_fuzzball(panel):
    label = panel.title_bar.title_label
    for _ in range(6):
        QTest.mouseClick(panel.title_bar, Qt.LeftButton, pos=label.geometry().center())
    assert panel.egg_overlay.key is None
    QTest.mouseClick(panel.title_bar, Qt.LeftButton, pos=label.geometry().center())
    assert panel.egg_overlay.key == "fuzz"


def test_clicks_beside_the_title_do_not_count(panel):
    bar = panel.title_bar
    for _ in range(7):
        QTest.mouseClick(bar, Qt.LeftButton, pos=QPoint(bar.title_label.geometry().right() + 20, 10))
    assert panel.egg_overlay.key is None


def test_seven_next_presses_call_the_hamster(panel):
    for _ in range(7):
        panel.next()
    assert panel.egg_overlay.key == "ham"


def test_midnight_calls_the_ufo_once_while_playing(panel):
    panel._now = lambda: datetime(2026, 11, 7, 0, 0, 5)
    panel._spectrum_playing = lambda: True
    panel.refresh()
    assert panel.egg_overlay.key == "ufo"
    panel.egg_overlay.stop()
    panel.refresh()
    assert panel.egg_overlay.key is None


def test_midnight_waits_for_a_window_that_can_show_it(panel):
    panel._now = lambda: datetime(2026, 11, 7, 0, 0, 5)
    panel._spectrum_playing = lambda: True
    panel.hide()
    panel.refresh()
    assert panel.egg_overlay.key is None
    panel.show()
    panel.refresh()
    assert panel.egg_overlay.key == "ufo"


def test_shutdown_ends_a_scene(qapp):
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer())
    p.show()
    p.egg_overlay.play("ham")
    p.shutdown()
    assert p.egg_overlay.key is None
    p.deleteLater()
