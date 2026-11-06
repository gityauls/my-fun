import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication
from fakes import FakePlayer, make_songs
from funplayer.core.settings import Settings
from funplayer.core.contrast import error_color
from funplayer.ui.player_panel import ART_NORMAL, PlayerPanel

ABC = ["01 a.mp3", "02 bad.mp3", "03 c.mp3"]

@pytest.fixture
def panel(qapp):
    fake = FakePlayer(); p = PlayerPanel(Settings({}, lambda: None), player=fake)
    yield p, fake
    p.shutdown(); p.deleteLater()

def test_initial_state(panel):
    p, _ = panel
    assert p.title_label.text() == "곡을 추가하세요" and p.count_label.text() == "0곡"
    assert (p.elapsed_label.text(), p.total_label.text()) == ("0:00", "0:00")
    assert not p.seek_slider.isEnabled() and p.play_button.toolTip() == "재생"
    assert p.volume_slider.value() == 70 and p.mute_button.toolTip() == "음소거"

def test_refresh_shows_playlist(panel, tmp_path):
    p, _ = panel; p.controller.open([str(make_songs(tmp_path, ABC))]); p.refresh()
    v = p.playlist_view
    assert v.count() == 3 and v.item(0).text().startswith("▶") and v.item(0).font().bold()
    assert not v.item(2).font().bold()
    assert p.count_label.text() == "3곡" and p.title_label.text() == "01 a"
    assert p.play_button.toolTip() == "일시정지" and p.seek_slider.isEnabled()
    assert p.total_label.text() == "3:00"

def test_failed_row_gray_and_status(panel, tmp_path):
    p, _ = panel; p.controller.open([str(make_songs(tmp_path, ABC))])
    p.controller.play_index(1); p.refresh()
    assert p.playlist_view.item(1).foreground().color() == QColor(Qt.gray)
    assert p.status_label.text() == "열 수 없음: 02 bad.mp3"

def test_list_not_rebuilt_without_change(panel, tmp_path):
    p, _ = panel; p.controller.open([str(make_songs(tmp_path, ABC))]); p.refresh()
    p.playlist_view.item(0).setData(Qt.UserRole + 1, "marker"); p.refresh()
    assert p.playlist_view.item(0).data(Qt.UserRole + 1) == "marker"

def test_scroll_kept_on_rebuild(panel, tmp_path):
    p, _ = panel; p.resize(380, 480); p.show()
    p.controller.open([str(make_songs(tmp_path, [f"{i:02} s.mp3" for i in range(50)]))]); p.refresh()
    bar = p.playlist_view.verticalScrollBar(); bar.setValue(10)
    p.controller.playlist.layout_version += 1; p.refresh()   # 같은 곡에서 목록만 다시 그림
    assert bar.value() == 10

def test_list_follows_current_track(panel, tmp_path):
    p, _ = panel; p.resize(380, 480); p.show()
    p.controller.open([str(make_songs(tmp_path, [f"{i:02} s.mp3" for i in range(50)]))]); p.refresh()
    v = p.playlist_view; bar = v.verticalScrollBar()
    p.controller.play_index(45); p.refresh()   # 무작위로 먼 곡이 골라진 경우와 같다
    assert v.visualItemRect(v.item(45)).intersects(v.viewport().rect())
    shown = bar.value()
    p.controller.play_index(44); p.refresh()   # 이미 보이는 줄이면 움직이지 않는다
    assert bar.value() == shown
    bar.setValue(0); p.refresh()                # 같은 곡에서 사용자가 굴린 위치는 그대로
    assert bar.value() == 0

def test_track_end_signal_advances(panel, tmp_path):
    p, fake = panel; p.controller.open([str(make_songs(tmp_path, ["01 a.mp3", "03 c.mp3"]))])
    fake.finish(); QApplication.processEvents()
    assert p.controller.playlist.index == 1

def test_shutdown_closes_player(qapp):
    fake = FakePlayer(); p = PlayerPanel(Settings({}, lambda: None), player=fake)
    p.shutdown(); assert fake.closed

def test_long_title_does_not_widen_panel(panel, tmp_path):
    p, _ = panel; p.resize(380, 480); p.show()
    stem = "x" * 150
    p.controller.open([str(make_songs(tmp_path, [stem + ".mp3"]))]); p.refresh()
    assert p.minimumSizeHint().width() < 380 and p.width() == 380
    assert p.title_label.text() == stem and p.title_label.overflowing and p.title_label.toolTip() == stem

def test_repeat_and_shuffle_buttons(panel):
    p, _ = panel
    assert p.repeat_button.toolTip() == "반복: 끔" and not p.repeat_button.isChecked()
    p.repeat_button.click(); assert p.repeat_button.toolTip() == "반복: 전체" and p.repeat_button.isChecked()
    p.repeat_button.click(); assert p.repeat_button.toolTip() == "반복: 한 곡" and p.repeat_button.isChecked()
    p.repeat_button.click(); assert p.repeat_button.toolTip() == "반복: 끔" and not p.repeat_button.isChecked()
    p.shuffle_button.click()
    assert p.controller.shuffle and p.shuffle_button.isChecked() and p.shuffle_button.toolTip() == "무작위: 켬"
    p.shuffle_button.click(); assert not p.shuffle_button.isChecked()

def test_buttons_follow_saved_settings(qapp):
    p = PlayerPanel(Settings({"player_repeat": "one", "player_shuffle": True}, lambda: None), player=FakePlayer())
    try:
        assert p.repeat_button.toolTip() == "반복: 한 곡" and p.shuffle_button.isChecked()
    finally:
        p.shutdown(); p.deleteLater()

def test_status_color(panel, tmp_path):
    p, _ = panel
    p.controller.on_player_error("소리 장치를 열 수 없습니다"); p.refresh()
    assert error_color(p.theme.bg) in p.status_label.styleSheet()
    assert "font-weight: 700" in p.status_label.styleSheet()
    p.controller.open([str(make_songs(tmp_path, ["01 a.mp3"]))]); p.controller.remove_duplicates(); p.refresh()
    assert p.status_label.text() == "중복 곡이 없습니다" and p.theme.mute in p.status_label.styleSheet()

def test_gray_row_returns_to_default_in_place_after_playing(panel, tmp_path):
    from funplayer.engine.decoder import DecodeError
    p, fake = panel; m = make_songs(tmp_path, ["01 a.mp3", "02 b.mp3"]); broken = [True]
    orig = fake.load
    def load(path):
        if broken[0] and path.endswith("02 b.mp3"):
            fake.has_track = False; raise DecodeError(path)
        orig(path)
    fake.load = load
    p.controller.open([str(m)]); p.controller.play_index(1); p.refresh()
    item = p.playlist_view.item(1)
    assert item.foreground().color() == QColor(Qt.gray)
    broken[0] = False; p.controller.play_index(1); p.refresh()
    assert p.playlist_view.item(1) is item and item.data(Qt.ForegroundRole) is None


from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QImage
from funplayer.core.m3u import write_playlist
from funplayer.core.taginfo import TrackInfo

def red_png():
    img = QImage(8, 8, QImage.Format_ARGB32); img.fill(QColor("#ff0000"))
    data = QByteArray(); buf = QBuffer(data); buf.open(QIODevice.WriteOnly); img.save(buf, "PNG")
    return bytes(data)

def test_header_shows_subtitle_and_tag_art(qapp, tmp_path):
    reader = lambda path: TrackInfo(path, artist="Lo-Fi Band", album="Sunday Mornings", picture=red_png())
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), read_info=reader)
    try:
        p.controller.open([str(make_songs(tmp_path, ["01 a.mp3"]))]); p.refresh()
        assert p.artist_label.toolTip() == "Lo-Fi Band · Sunday Mornings"
        assert p.art_label.toolTip() == "곡 정보" and p.art_label.width() == ART_NORMAL
        assert p.art_label.pixmap().toImage().pixelColor(ART_NORMAL // 2, ART_NORMAL // 2) == QColor("#ff0000")
    finally:
        p.shutdown(); p.deleteLater()

def test_default_art_and_empty_subtitle(panel):
    p, _ = panel
    pm = p.art_label.pixmap()
    assert pm is not None and (pm.width(), pm.height()) == (ART_NORMAL, ART_NORMAL) and p.artist_label.text() == ""

def test_cover_loaded_once_per_track(qapp, tmp_path, monkeypatch):
    import funplayer.ui.player_panel as pp
    calls = []; real = pp.load_cover
    monkeypatch.setattr(pp, "load_cover", lambda info, *a: calls.append(info.path) or real(info, *a))
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer())
    try:
        p.controller.open([str(make_songs(tmp_path, ABC))]); p.refresh(); p.refresh(); p.refresh()
        assert len(calls) == 1
        p.controller.next(); p.refresh()
        assert len(calls) == 2
    finally:
        p.shutdown(); p.deleteLater()

def test_panel_restores_cued_session_and_saves_on_shutdown(qapp, tmp_path):
    songs = make_songs(tmp_path / "m", ["01 a.mp3", "03 c.mp3"])
    write_playlist(str(tmp_path / "last.m3u8"), [str(songs / "01 a.mp3"), str(songs / "03 c.mp3")])
    store = {"player_last_track": str(songs / "03 c.mp3"), "player_last_position": 72.0}
    fake = FakePlayer()
    p = PlayerPanel(Settings(store, lambda: None), player=fake, session_path=str(tmp_path / "last.m3u8"))
    p.refresh()
    assert p.controller.playlist.index == 1 and p.seek_slider.isEnabled()
    assert p.elapsed_label.text() == "1:12" and p.play_button.toolTip() == "재생"
    assert p.status_label.toolTip() == "이어 듣기: 1:12부터"
    fake.position = 80.0; p.shutdown(); p.deleteLater()
    assert store["player_last_position"] == 80.0


def test_bottom_buttons_size_from_font(panel):
    from PyQt5.QtWidgets import QSizePolicy
    p, _ = panel
    for b in (p.open_button, p.add_button, p.list_button, p.view_button):
        assert b.minimumWidth() > b.fontMetrics().horizontalAdvance(b.text())
        assert b.sizePolicy().horizontalPolicy() == QSizePolicy.Preferred


# ---- 긴 막대 미니 ----

SHARED = ("art_label", "title_label", "artist_label", "heart_button", "elapsed_label", "seek_slider",
          "total_label", "shuffle_button", "prev_button", "play_button", "next_button", "repeat_button",
          "mute_button", "volume_slider", "live_label", "listened_label")

def test_mini_size_and_shared_widgets(panel):
    p, _ = panel; p.set_mini(True)
    assert p.art_label.width() == 80 and p.play_button.window() is p
    assert (p.play_button.width(), p.play_button.property("kind")) == (46, "playMd")
    assert all(p.mini_bar.isAncestorOf(getattr(p, n)) for n in SHARED)
    p.set_mini(False)
    assert all(p.pages.widget(0).isAncestorOf(getattr(p, n)) for n in SHARED)
    assert p.art_label.width() == ART_NORMAL
    assert (p.play_button.width(), p.play_button.property("kind")) == (60, "play")

def test_mini_shows_only_the_bar(panel, qapp):
    p, _ = panel; p.show(); assert not p.mini_bar.isVisible() and p.mini_bar.objectName() == "miniBar"
    p.set_tab("playlist"); p.set_mini(True); qapp.processEvents()
    assert p.mini_bar.isVisible()
    assert not any(w.isVisible() for w in (p.title_bar, p.tab_bar, p.pages, p.status_label, p.now_strip))
    assert all(getattr(p, n).isVisible() for n in SHARED if n not in ("live_label", "listened_label"))
    assert p.mini_controls.isVisible() and p.list_button_mini.isVisible()
    p.set_mini(False); qapp.processEvents()
    assert not p.mini_bar.isVisible() and p.tab == "playlist" and p.playlist_view.isVisible()

def test_back_to_normal_restores_every_slot_and_size(panel):
    p, _ = panel
    def snapshot():
        out = {}
        for n in SHARED:
            w = getattr(p, n)
            out[n] = (w.parent(), w.minimumSize(), w.maximumSize(), w.font().pixelSize())
            if hasattr(w, "iconSize"):
                out[n] += (w.iconSize(),)
        out["rows"] = ([p.control_row.indexOf(w) for w in (p.shuffle_button, p.prev_button, p.play_button,
                                                           p.next_button, p.repeat_button)],
                       p.head_row.indexOf(p.heart_button), p.art_row.indexOf(p.art_label),
                       p.page_now.layout().indexOf(p.seek_slider), p.page_now.layout().count())
        return out
    before = snapshot()
    p.set_mini(True); assert snapshot() != before
    p.set_mini(False)
    assert snapshot() == before

def test_mini_layout_follows_the_mockup(panel, qapp):
    p, _ = panel; p.show(); p.set_mini(True); p.resize(830, 104); qapp.processEvents()
    assert (p.mini_bar.width(), p.mini_bar.height()) == (830, 104)
    assert p.layout().totalMinimumSize().width() == 830
    assert (p.art_label.x(), p.art_label.y()) == (28, 12)
    assert p.mini_info.width() == 319 and p.mini_volume.width() == 92 and p.list_button_mini.width() == 26
    assert p.title_label.font().pixelSize() == 14 and p.title_label.font().bold()
    assert p.artist_label.font().pixelSize() == 12 and p.elapsed_label.font().pixelSize() == 11
    assert p.mini_info.x() == 6 + 18 + 4 + 80 + 4 + 18 + 12 + 1 + 12
    right = p.list_button_mini.mapTo(p.mini_bar, p.list_button_mini.rect().topRight()).x()
    assert right == 830 - 17 - 1

def test_wider_mini_goes_to_the_info_column(panel, qapp):
    p, _ = panel; p.show(); p.set_mini(True); p.resize(930, 104); qapp.processEvents()
    assert p.mini_info.width() == 419 and p.mini_volume.width() == 92

def test_mini_window_buttons_stay_on_top_at_the_corner(panel, qapp):
    p, _ = panel; p.show(); p.set_mini(True); p.resize(830, 104); qapp.processEvents()
    c = p.mini_controls
    assert c.parent() is p.mini_bar and c.geometry().right() == 829 and c.y() == 0
    for b in (p.mini_min_button, p.mini_normal_button, p.mini_close_button):
        assert p.mini_bar.childAt(b.mapTo(p.mini_bar, b.rect().center())) is b
    assert p.mini_normal_button.toolTip() == "보통 보기"

def test_long_title_scrolls_inside_the_info_column(panel, qapp, tmp_path):
    p, _ = panel; name = "아주 긴 제목 " * 12 + ".mp3"
    p.controller.open([str(make_songs(tmp_path, [name]))]); p.show()
    p.set_mini(True); p.resize(830, 104); qapp.processEvents(); p.refresh()
    assert p.title_label.moving and p.title_label.width() < 319
    assert p.title_label.toolTip().startswith("아주 긴 제목")

def test_title_scrolls_right_after_the_switch(panel, qapp, tmp_path):
    from funplayer.ui.window_keeper import WindowKeeper
    p, _ = panel; p.controller.open([str(make_songs(tmp_path, ["아주 긴 제목 " * 12 + ".mp3"]))])
    WindowKeeper(p, p.settings).start(); p.show(); qapp.processEvents(); p.refresh()
    p.set_mini(True); qapp.processEvents()
    assert p.title_label.moving

def test_art_is_rebuilt_at_each_mode_size(panel, tmp_path, monkeypatch):
    import funplayer.ui.player_panel as pp
    p, _ = panel; p.controller.open([str(make_songs(tmp_path, ABC))]); p.refresh(); calls = []
    real = pp.rounded_art
    monkeypatch.setattr(pp, "rounded_art", lambda *a: calls.append(a[1:3]) or real(*a))
    p.set_mini(True)
    assert (80, 14) in calls and p.art_label.pixmap().width() == 80
    calls.clear(); p.set_mini(False)
    assert (216, 28) in calls and p.art_label.pixmap().width() == 216

@pytest.mark.parametrize("name", ["l", "m"])
def test_mini_icons_use_the_mini_colours(panel, name):
    from funplayer.core.themes import get_theme
    from funplayer.ui.glyphs import glyph
    from funplayer.ui.style import hero_theme, mini_theme
    p, _ = panel; theme = get_theme(name); p.apply_theme(theme)
    image = lambda icon, size: icon.pixmap(size, size).toImage()
    assert image(p.prev_button.icon(), 21) == image(glyph("prev", hero_theme(theme).icon, 21), 21)
    p.set_mini(True)
    assert image(p.prev_button.icon(), 19) == image(glyph("prev", mini_theme(theme).icon, 19), 19)
    assert image(p.list_button_mini.icon(), 20) == image(glyph("list", mini_theme(theme).icon, 20), 20)
    p.apply_theme(theme)   # 미니에서 테마를 바꿔도 미니 색이다
    assert image(p.prev_button.icon(), 19) == image(glyph("prev", mini_theme(theme).icon, 19), 19)
    assert p.art_label.pixmap().width() == 80
    p.set_mini(False)
    assert image(p.prev_button.icon(), 21) == image(glyph("prev", hero_theme(theme).icon, 21), 21)

def test_theme_stylesheet_gives_the_bar_its_shape():
    from funplayer.core.themes import get_theme
    from funplayer.ui.style import MINI_RADIUS, stylesheet
    qss = stylesheet(get_theme("light"))
    assert MINI_RADIUS == 24 and '#miniBar QPushButton[kind="playMd"]' in qss
    assert "#miniLine" in qss and "#miniControls QPushButton:hover" in qss
