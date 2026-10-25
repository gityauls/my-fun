import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication
from fakes import FakePlayer, make_songs
from funplayer.core.settings import Settings
from funplayer.ui.player_panel import ERROR_COLOR, INFO_COLOR, PlayerPanel

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
    p.controller.next(); p.refresh()
    assert bar.value() == 10

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
    assert p.title_label.text().endswith("…") and p.title_label.toolTip() == stem

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
    assert ERROR_COLOR in p.status_label.styleSheet()
    p.controller.open([str(make_songs(tmp_path, ["01 a.mp3"]))]); p.controller.remove_duplicates(); p.refresh()
    assert p.status_label.text() == "중복 곡이 없습니다" and INFO_COLOR in p.status_label.styleSheet()

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
        assert p.art_label.toolTip() == "곡 정보" and p.art_label.width() == 56
        assert p.art_label.pixmap().toImage().pixelColor(28, 28) == QColor("#ff0000")
    finally:
        p.shutdown(); p.deleteLater()

def test_default_art_and_empty_subtitle(panel):
    p, _ = panel
    pm = p.art_label.pixmap()
    assert pm is not None and (pm.width(), pm.height()) == (56, 56) and p.artist_label.text() == ""

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
