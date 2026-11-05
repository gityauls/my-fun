from PyQt5.QtCore import Qt

from funplayer.core.themes import THEMES, get_theme
from funplayer.ui.settings_dialog import SettingsDialog, solid_colors


def test_settings_lists_twelve(qapp):
    d = SettingsDialog("light")
    assert d.theme_list.count() == 12 == len(THEMES)
    assert [d.theme_list.item(i).text() for i in range(12)] == [t.name for t in THEMES]


def test_current_row_is_selected(qapp):
    assert SettingsDialog("dark").selected_id() == "dark"


def test_pick_emits(qapp):
    d = SettingsDialog("light")
    got = []
    d.themePicked.connect(got.append)
    d.theme_list.setCurrentRow(1)
    assert got == ["dark"]


def test_select_is_silent(qapp):
    d = SettingsDialog("light")
    got = []
    d.themePicked.connect(got.append)
    d.select("mid")
    assert got == [] and d.selected_id() == "mid"


def test_dots_skip_non_solid(qapp):
    assert len(solid_colors(get_theme("light"))) == 5
    # album colour: track is translucent, so only four dots
    assert len(solid_colors(get_theme("c"))) == 4
    d = SettingsDialog("light")
    assert not d.theme_list.item(0).icon().isNull()
    assert d.theme_list.item(0).icon().pixmap(100, 14).width() == 5 * 14 + 4 * 4


def test_buttons_are_korean(qapp):
    d = SettingsDialog("light")
    assert (d.ok_button.text(), d.cancel_button.text()) == ("확인", "취소")


def test_all_themes_fit_without_scrolling(qapp):
    d = SettingsDialog("light"); d.show(); qapp.processEvents()
    assert d.theme_list.verticalScrollBar().maximum() == 0
    d.close(); d.deleteLater()
