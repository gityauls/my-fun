import os
from pathlib import Path

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QPixmap
from PyQt5.QtWidgets import QApplication, QWidget

from fakes import FakePlayer, FakeRunner
from funplayer.core.contrast import MIN_TEXT, contrast, error_color, surface_colors
from funplayer.core.settings import Settings
from funplayer.core.themes import THEME_IDS, album_theme, get_theme
from funplayer.ui import player_panel
from funplayer.ui.cover import rounded_art
from funplayer.ui.player_panel import PlayerPanel
from funplayer.ui.settings_dialog import SettingsDialog
from funplayer.ui.style import hero_theme, mini_theme
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


def _count(image, color: str) -> int:
    want = QColor(color).rgb()
    return sum(image.pixel(x, y) == want for x in range(image.width()) for y in range(image.height()))


@pytest.fixture
def seg_font(panel):
    # offscreen 플랫폼에는 한글 글꼴이 없어 글자가 그려지지 않는다: 시스템의 맑은 고딕을 등록해 입힌다
    fid = QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / "malgun.ttf"))
    family = QFontDatabase.applicationFontFamilies(fid)[0]
    for b in panel.fx_strip.mode_buttons.values():
        font = QFont(b.font()); font.setFamily(family); font.setPixelSize(16); b.setFont(font)
    yield panel
    QFontDatabase.removeApplicationFont(fid)   # 뒤 테스트의 글꼴 크기 재기에 번지지 않게


@pytest.mark.parametrize("theme_id", THEME_IDS)
def test_selected_listen_segment_uses_on_acc(seg_font, theme_id):
    panel = seg_font
    panel.set_theme_id(theme_id); panel.set_tab("fx")
    t = panel._applied_theme
    buttons = panel.fx_strip.mode_buttons
    buttons["off"].setChecked(True); QApplication.processEvents()
    on = buttons["off"].grab().toImage(); off = buttons["speaker"].grab().toImage()
    assert _count(on, t.on_acc) > 3     # 고른 칸 글자는 강조색 위 글자색이다
    assert _count(off, t.ink) > 3       # 나머지 칸은 본문 글자색
    if QColor(t.on_acc) != QColor(t.ink):
        assert _count(on, t.ink) == 0


def test_selected_listen_segment_is_bold(seg_font):
    panel = seg_font
    panel.set_tab("fx")
    b = panel.fx_strip.mode_buttons["speaker"]
    t = panel._applied_theme
    b.setChecked(False); QApplication.processEvents()
    thin = _count(b.grab().toImage(), t.ink)
    b.setChecked(True); QApplication.processEvents()
    assert _count(b.grab().toImage(), t.on_acc) > thin


# ---- 라이브·안내 글자색은 테마를 따른다 ----

ALL_THEMES = [get_theme(i) for i in THEME_IDS]
ALBUMS = [album_theme(a) for a in ("#E02020", "#20C040", "#2040FF", None)]
MARK_MIN = 3.0     # 굵은 상태 표시. 시안의 강조색을 그대로 쓴다
SURFACES = (lambda t: t, hero_theme, mini_theme)


def _worst(color: str, surface: str) -> float:
    return min(contrast(color, c) for c in surface_colors(surface))


@pytest.mark.parametrize("theme", ALL_THEMES + ALBUMS, ids=lambda t: t.id + t.bg[:7])
def test_status_colors_readable_on_status_background(theme):
    assert _worst(theme.mute, theme.bg) >= MIN_TEXT
    assert _worst(error_color(theme.bg), theme.bg) >= MIN_TEXT


@pytest.mark.parametrize("theme", ALL_THEMES + ALBUMS, ids=lambda t: t.id + t.bg[:7])
@pytest.mark.parametrize("face", SURFACES, ids=("base", "hero", "mini"))
def test_error_color_readable_on_every_surface(theme, face):
    bg = face(theme).bg
    assert _worst(error_color(bg), bg) >= MIN_TEXT


@pytest.mark.parametrize("theme", ALL_THEMES + ALBUMS, ids=lambda t: t.id + t.bg[:7])
def test_error_differs_from_info(theme):
    err, info = QColor(error_color(theme.bg)), QColor(theme.mute)
    assert err.red() - max(err.green(), err.blue()) > 60 > abs(info.red() - max(info.green(), info.blue()))


@pytest.mark.parametrize("theme", ALL_THEMES + ALBUMS, ids=lambda t: t.id + t.bg[:7])
@pytest.mark.parametrize("face", (hero_theme, mini_theme), ids=("hero", "mini"))
def test_live_and_connecting_marks_readable(theme, face):
    c = face(theme)
    assert _worst(c.acc_t, c.bg) >= MARK_MIN and _worst(c.mute, c.bg) >= MARK_MIN


@pytest.mark.parametrize("theme_id", THEME_IDS)
def test_live_mark_follows_theme_and_mode(panel_on_radio, theme_id):
    p = panel_on_radio
    p.set_theme_id(theme_id)
    assert p.live_label.styleSheet() == f"color: {hero_theme(p._applied_theme).acc_t};"
    p.set_mini(True)
    assert p.live_label.styleSheet() == f"color: {mini_theme(p._applied_theme).acc_t};"
    p.set_mini(False)


def test_status_recolours_at_once_on_theme_change(panel):
    panel.controller.on_player_error("소리 장치를 열 수 없습니다"); panel.refresh()
    panel.set_theme_id("dark")
    assert error_color(get_theme("dark").bg) in panel.status_label.styleSheet()
    panel.controller.notify("안내"); panel.refresh()
    panel.set_theme_id("i")
    assert panel.status_label.styleSheet() == f"color: {get_theme('i').mute};"


def test_every_panel_menu_is_themed(panel):
    from PyQt5.QtWidgets import QMenu
    menus = panel.findChildren(QMenu)
    assert panel.station_view.context_menu in menus and panel.context_menu in menus
    assert len(menus) >= 8 and {m.objectName() for m in menus} == {"themed"}


def test_station_menu_paints_with_theme(panel):
    panel.set_theme_id("dark")
    menu = panel.station_view.context_menu
    menu.ensurePolished()
    assert menu.grab().toImage().pixelColor(menu.width() // 2, menu.height() // 2).name().upper() in (
        get_theme("dark").bar.upper(), get_theme("dark").tint.upper())


def test_settings_dialog_is_deleted_after_closing(panel):
    from PyQt5 import sip
    from PyQt5.QtCore import QCoreApplication, QEvent
    for finish in ("accept", "reject", "close"):
        d = panel.show_settings(modal=False)
        getattr(d, finish)()
        assert panel.settings_dialog is None and d.selected_id()   # 닫은 직후에는 아직 읽을 수 있다
        QCoreApplication.sendPostedEvents(d, QEvent.DeferredDelete)
        assert sip.isdeleted(d)
    assert panel.findChildren(SettingsDialog) == []


def test_heart_compares_only_when_track_or_favourites_change(panel_with_tracks):
    p = panel_with_tracks
    p.refresh()
    calls = []; real = p.controller.is_favorite
    p.controller.is_favorite = lambda path: (calls.append(path), real(path))[1]
    for _ in range(5):
        p.refresh()
    assert calls == []
    p.toggle_current_favorite()
    assert p.heart_button.isChecked() and len(calls) == 1
    p.next()
    assert p._player.loaded and len(calls) == 2
    n = len(calls); p.settings.favorites = []; p.refresh()
    assert len(calls) == n + 1 and not p.heart_button.isChecked()


@pytest.mark.parametrize("theme", ALL_THEMES + ALBUMS, ids=lambda t: t.id + t.bg[:7])
@pytest.mark.parametrize("face", (hero_theme, mini_theme), ids=("hero", "mini"))
def test_filled_heart_stands_out_on_hero_and_mini(theme, face):
    c = face(theme)
    assert _worst(c.fav, c.bg) >= MARK_MIN
