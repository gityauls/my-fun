import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from fakes import FakePlayer, make_songs
from funplayer.core.settings import Settings
from funplayer.ui.colors import FAVORITE_COLOR
from funplayer.ui.player_panel import FAV_OFF_TEXT, FAV_ON_TEXT, PlayerPanel

ABCD = ["01 a.mp3", "02 b.mp3", "03 c.mp3", "04 d.mp3"]


@pytest.fixture
def panel(qapp, tmp_path):
    store = {}
    fake = FakePlayer()
    p = PlayerPanel(Settings(store, lambda: None), player=fake)
    p.resize(380, 480); p.show()
    p.controller.open([str(make_songs(tmp_path, ABCD))]); p.refresh()
    p.set_tab("playlist")
    yield p, fake, store
    p.shutdown(); p.deleteLater()


def texts(p):
    return [p.playlist_view.item(i).text().rsplit("   ", 1)[1] for i in range(p.playlist_view.count())]


def is_blue(p, row):
    return p.playlist_view.item(row).foreground().color() == QColor(FAVORITE_COLOR)


def test_context_favorite_moves_up_blue_and_selected(panel):
    p, fake, _ = panel
    calls = len(fake.calls)
    p.playlist_view.setCurrentRow(2)
    p._update_actions()
    assert p.actions["favorite"].text() == FAV_ON_TEXT
    p.actions["favorite"].trigger()
    assert texts(p) == ["03 c", "01 a", "02 b", "04 d"]
    assert is_blue(p, 0) and not is_blue(p, 1)
    assert p.selected_rows() == [0] and len(fake.calls) == calls   # 재생은 그대로
    p._update_actions()
    assert p.actions["favorite"].text() == FAV_OFF_TEXT


def test_ctrl_d_unfavorites_back_to_name_position(panel):
    p, _, _ = panel
    p.select_rows([1, 3]); p.shortcuts["Ctrl+D"].activated.emit()
    assert texts(p) == ["02 b", "04 d", "01 a", "03 c"] and is_blue(p, 0) and is_blue(p, 1)
    p.select_rows([0]); p.shortcuts["Ctrl+D"].activated.emit()
    assert texts(p) == ["04 d", "01 a", "02 b", "03 c"] and not is_blue(p, 2)


def test_ctrl_d_ignored_on_radio_tab(panel):
    p, _, store = panel
    p.select_rows([2]); p._tab = "radio"
    p.shortcuts["Ctrl+D"].activated.emit()
    assert not store.get("player_favorites")


def test_missing_favorite_stays_gray(panel, tmp_path):
    p, _, _ = panel
    p.select_rows([0]); p.toggle_favorite()
    p.controller.playlist.mark_missing(0); p.refresh()
    assert p.playlist_view.item(0).foreground().color() == QColor(Qt.gray)


def test_save_favorites_menu_enabled_only_with_favorites(panel, tmp_path, monkeypatch):
    p, _, _ = panel
    p._update_actions()
    assert not p.actions["save_favorites"].isEnabled()
    p.select_rows([0]); p.toggle_favorite(); p._update_actions()
    assert p.actions["save_favorites"].isEnabled()
    out = tmp_path / "fav.m3u8"
    monkeypatch.setattr("funplayer.ui.player_panel.QFileDialog.getSaveFileName", lambda *a, **k: (str(out), ""))
    p.actions["save_favorites"].trigger()
    assert out.exists() and "01 a.mp3" in out.read_text(encoding="utf-8")
