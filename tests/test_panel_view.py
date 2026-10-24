import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication
from fakes import FakePlayer, make_songs
from funplayer.core.settings import Settings
from funplayer.ui.player_panel import PlayerPanel

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
