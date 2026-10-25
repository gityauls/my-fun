import pytest
from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtGui import QGuiApplication
from fakes import FakePlayer
from funplayer.core.settings import Settings
from funplayer.ui.player_panel import PlayerPanel
from funplayer.ui.window_keeper import WindowKeeper

@pytest.fixture
def make(qapp):
    made = []
    def build(store):
        s = Settings(store, lambda: None)
        p = PlayerPanel(s, player=FakePlayer()); k = WindowKeeper(p, s); k.start()
        made.append(p); return p, k
    yield build
    for p in made:
        p.shutdown(); p.deleteLater()

on_top = lambda p: bool(p.windowFlags() & Qt.WindowStaysOnTopHint)

def test_first_start_uses_default_size(make):
    p, _ = make({})
    assert p.size() == QSize(380, 480) and not p.is_mini and not on_top(p)

def test_restores_saved_normal_geometry(make):
    p, _ = make({"player_geometry": [50, 60, 400, 500]})
    assert p.geometry() == QRect(50, 60, 400, 500)

def test_offscreen_geometry_is_centered(make):
    p, _ = make({"player_geometry": [5000, 5000, 380, 480]})
    assert QGuiApplication.screenAt(p.geometry().center()) is not None and p.size() == QSize(380, 480)

def test_starts_in_mini_on_top_at_saved_place(make):
    p, _ = make({"player_mini": True, "player_mini_geometry": [30, 40, 380, 92]})
    assert p.is_mini and on_top(p) and (p.x(), p.y(), p.width()) == (30, 40, 380)
    assert p.minimumHeight() == p.maximumHeight() == p.sizeHint().height()

def test_toggle_saves_each_mode_and_restores_other(make):
    store = {"player_geometry": [50, 60, 400, 500]}; p, _ = make(store)
    p.set_mini(True)
    assert store["player_geometry"] == [50, 60, 400, 500] and on_top(p)
    p.move(70, 80); p.set_mini(False)
    assert store["player_mini_geometry"][:2] == [70, 80] and p.geometry() == QRect(50, 60, 400, 500)
    assert not on_top(p) and p.maximumHeight() == 16777215

def test_on_top_option(make):
    p, _ = make({"player_mini": True}); assert on_top(p)
    p.actions["mini_on_top"].trigger(); assert p.is_mini and not on_top(p)
    p.actions["mini_on_top"].trigger(); assert on_top(p)
    p.set_mini(False); assert not on_top(p)

def test_save_writes_current_mode(make):
    store = {}; p, k = make(store); p.setGeometry(20, 30, 390, 470); k.save()
    assert store["player_geometry"] == [20, 30, 390, 470]
