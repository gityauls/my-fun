import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import QWidget

from fakes import FakePlayer, FakeRunner
from funplayer.core.settings import Settings
from funplayer.core.themes import THEME_IDS, album_theme, get_theme
from funplayer.ui import player_panel
from funplayer.ui.cover import rounded_art
from funplayer.ui.player_panel import PlayerPanel
from funplayer.ui.settings_dialog import SettingsDialog
from test_panel_tabs import build  # noqa: F401  (fixtures below reuse it)
from test_panel_tabs import panel, panel_on_radio, panel_with_tracks  # noqa: F401


def pixel(widget: QWidget, x: int, y: int) -> str:
    return widget.grab().toImage().pixelColor(x, y).name().upper()


def solid(color: str) -> QPixmap:
    pm = QPixmap(64, 64)
    pm.fill(QColor(color))
    return pm


@pytest.fixture
def red_cover(monkeypatch):
    monkeypatch.setattr(player_panel, "load_cover", lambda info: solid("#E02020"))


def test_default_theme_is_light(panel):
    assert panel.theme.id == "light"


def test_set_theme_id_applies_without_saving(panel):
    panel.set_theme_id("dark")
    assert panel.theme.id == "dark" and panel.settings.theme == "light"
    assert pixel(panel.title_bar, 200, 22) == get_theme("dark").bar.upper()


def test_menu_has_settings_first(panel):
    assert panel.view_menu.actions()[0] is panel.actions["settings"]
    assert panel.actions["settings"].text() == "설정…"


def test_pick_previews_and_cancel_restores(panel):
    d = panel.show_settings(modal=False)
    d.themePicked.emit("dark")
    assert panel.theme.id == "dark"
    d.reject()
    assert panel.theme.id == "light" and panel.settings.theme == "light"


def test_close_by_x_is_cancel(panel):
    d = panel.show_settings(modal=False)
    d.theme_list.setCurrentRow(1)
    d.close()
    assert panel.theme.id == "light" and panel.settings.theme == "light"


def test_accept_saves(panel):
    d = panel.show_settings(modal=False)
    d.theme_list.setCurrentRow(1)
    d.accept()
    assert panel.theme.id == "dark" and panel.settings.theme == "dark"


def test_dialog_starts_on_current_theme(panel):
    panel.set_theme_id("mid")
    assert panel.show_settings(modal=False).selected_id() == "mid"


def test_album_theme_keeps_id_c(panel):
    panel.set_theme_id("c")
    assert panel.theme.id == "c" and panel._applied_theme.id == "album"


def test_album_accent_from_cover(panel_with_tracks, red_cover):
    p = panel_with_tracks
    p.set_theme_id("c")
    p._cover_key = object()
    p.refresh()
    assert p._album_accent == "#E02020"
    assert p._applied_theme.acc == album_theme("#E02020").acc


def test_album_theme_applies_only_when_accent_changes(panel_with_tracks, monkeypatch):
    p = panel_with_tracks
    calls = []
    p.set_theme_id("c")
    monkeypatch.setattr(p, "setStyleSheet", lambda s: calls.append(s))
    for _ in range(5):
        p.refresh()
    assert calls == []


def test_same_accent_does_not_reapply(panel_with_tracks, red_cover, monkeypatch):
    p = panel_with_tracks
    p.set_theme_id("c")
    p._cover_key = object(); p.refresh()
    calls = []
    monkeypatch.setattr(p, "setStyleSheet", lambda s: calls.append(s))
    p._cover_key = object(); p.refresh()
    assert calls == []


def test_accent_ignored_unless_theme_c(panel_with_tracks, red_cover):
    p = panel_with_tracks
    p._cover_key = object(); p.refresh()
    assert p._album_accent is None and p._applied_theme.id == "light"


def test_album_theme_radio_uses_default_accent(panel_on_radio, red_cover):
    p = panel_on_radio
    p.set_theme_id("c")
    assert p._album_accent is None
    assert p._applied_theme.acc == album_theme(None).acc


def test_cover_less_track_gives_default_accent(panel_with_tracks):
    p = panel_with_tracks
    p.set_theme_id("c")
    assert p._album_accent is None


def test_leaving_c_clears_accent(panel_with_tracks, red_cover):
    p = panel_with_tracks
    p.set_theme_id("c")
    p._cover_key = object(); p.refresh()
    p.set_theme_id("dark")
    assert p._album_accent is None


def test_accent_change_with_dialog_open(panel_with_tracks, red_cover):
    p = panel_with_tracks
    p.set_theme_id("c")
    d = p.show_settings(modal=False)
    p._cover_key = object(); p.refresh()
    assert p._album_accent == "#E02020"
    d.reject()
    assert p.theme.id == "c"


@pytest.mark.parametrize("mini", [False, True])
def test_all_themes_apply_without_error(panel_with_tracks, mini):
    p = panel_with_tracks
    p.set_mini(mini)
    for tid in THEME_IDS:
        p.set_theme_id(tid)
        assert p.theme.id == tid
        p.grab()


def test_theme_change_updates_art_without_cover(panel_with_tracks):
    p = panel_with_tracks
    p.set_theme_id("dark")
    before = p.art_label.pixmap().toImage()
    p.set_theme_id("mid")
    after = p.art_label.pixmap().toImage()
    assert after != before
    want = rounded_art(None, p.art_label.width(), player_panel.ART_RADIUS, get_theme("mid")).toImage()
    assert after == want


def test_theme_change_updates_radio_art(panel_on_radio):
    p = panel_on_radio
    p.set_theme_id("dark")
    before = p.art_label.pixmap().toImage()
    p.set_theme_id("d")
    assert p.art_label.pixmap().toImage() != before


def test_second_apply_before_show_keeps_title_bar_coloured(qapp):
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), runner=FakeRunner())
    p.resize(380, 620)
    p.set_theme_id("dark")
    p.set_theme_id("mid")
    p.show()
    try:
        assert pixel(p.title_bar, 200, 22) == get_theme("mid").bar.upper()
        assert pixel(p.tab_bar, 190, 20) == get_theme("mid").tabs.upper()
    finally:
        p.shutdown(); p.deleteLater()


def test_live_switch_recolours_parts(panel_with_tracks):
    p = panel_with_tracks
    p.set_theme_id("dark")
    t = get_theme("dark")
    assert pixel(p.title_bar, 200, 22) == t.bar.upper()
    assert pixel(p.tab_bar, 190, 20) == t.tabs.upper()
    p.set_theme_id("mid")
    t = get_theme("mid")
    assert pixel(p.title_bar, 200, 22) == t.bar.upper()
    assert pixel(p.tab_bar, 190, 20) == t.tabs.upper()
    p.set_mini(True)
    p.set_theme_id("dark")
    assert pixel(p.mini_bar, 100, 3) != get_theme("mid").bar.upper()
