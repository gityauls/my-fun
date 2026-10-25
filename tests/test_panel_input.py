import pytest
from PyQt5.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt5.QtGui import QDropEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QStyle, QStyleOptionSlider
from fakes import FakePlayer, make_songs
from funplayer.core.settings import Settings
from funplayer.engine.player import State
from funplayer.ui.jump_slider import JumpSlider
from funplayer.ui.player_panel import SHORTCUTS, PlayerPanel

ABC = ["01 a.mp3", "02 b.mp3", "03 c.mp3"]

@pytest.fixture
def rig(qapp, tmp_path):
    store, fake = {}, FakePlayer()
    p = PlayerPanel(Settings(store, lambda: None), player=fake); p.show()
    p.controller.open([str(make_songs(tmp_path / "m", ABC))]); p.refresh()
    yield p, fake, store, tmp_path
    p.shutdown(); p.deleteLater()

def test_buttons(rig):
    p, fake, *_ = rig
    QTest.mouseClick(p.next_button, Qt.LeftButton); assert p.controller.playlist.index == 1
    QTest.mouseClick(p.prev_button, Qt.LeftButton); assert p.controller.playlist.index == 0
    QTest.mouseClick(p.play_button, Qt.LeftButton); assert fake.state is State.PAUSED
    QTest.mouseClick(p.stop_button, Qt.LeftButton); assert fake.state is State.STOPPED
    QTest.mouseClick(p.mute_button, Qt.LeftButton); assert fake.gain == 0.0
    QTest.mouseClick(p.clear_button, Qt.LeftButton)
    assert len(p.controller.playlist) == 0 and p.title_label.text() == "곡을 추가하세요"

def test_double_click_plays_row(rig):
    p, fake, *_ = rig
    p.playlist_view.itemDoubleClicked.emit(p.playlist_view.item(2))
    assert fake.loaded[-1].endswith("03 c.mp3")

def test_volume_slider(rig):
    p, fake, store, _ = rig; p.volume_slider.setValue(40)
    assert store["player_volume"] == 40 and fake.gain == pytest.approx(0.16)

def test_seek_drag_seeks_on_release(rig):
    p, fake, *_ = rig; s = p.seek_slider
    s.setSliderDown(True); s.setSliderPosition(60000)
    assert p.elapsed_label.text() == "1:00" and fake.seeks == []
    p.refresh(); assert s.value() == 60000
    assert p.elapsed_label.text() == "1:00"
    s.setSliderDown(False)
    assert fake.seeks == [60.0]

def test_jump_slider_click(qapp):
    s = JumpSlider(Qt.Horizontal); s.setRange(0, 1000); s.resize(200, 20); s.show()
    QTest.mouseClick(s, Qt.LeftButton, Qt.NoModifier, QPoint(150, 10))
    assert abs(s.value() - 750) < 80

def test_shortcut_table(rig):
    p, *_ = rig
    assert set(p.shortcuts) == {"Space", "X", "V", "Z", "B", "Left", "Right", "Up", "Down", "M", "L", "R", "S"}
    assert dict(SHORTCUTS)["Space"] == "toggle"
    assert all(sc.context() == Qt.WidgetWithChildrenShortcut for sc in p.shortcuts.values())

@pytest.mark.parametrize("key,check", [
    ("Space", lambda p, f: f.state is State.PAUSED),
    ("X", lambda p, f: f.state is State.PAUSED),
    ("V", lambda p, f: f.state is State.STOPPED),
    ("B", lambda p, f: p.controller.playlist.index == 1),
    ("Right", lambda p, f: f.seeks == [5.0]),
    ("Up", lambda p, f: p.controller.volume == 75),
    ("Down", lambda p, f: p.controller.volume == 65),
    ("M", lambda p, f: p.controller.muted),
    ("R", lambda p, f: p.controller.repeat == "all"),
    ("S", lambda p, f: p.controller.shuffle)])
def test_shortcuts_trigger(rig, key, check):
    p, fake, *_ = rig
    p.shortcuts[key].activated.emit()
    assert check(p, fake)

def test_left_and_z(rig):
    p, fake, *_ = rig
    fake.position = 10; p.shortcuts["Left"].activated.emit(); assert fake.seeks == [5.0]
    p.controller.play_index(1); fake.position = 0
    p.shortcuts["Z"].activated.emit(); assert p.controller.playlist.index == 0

def test_l_opens_files(rig, monkeypatch):
    p, fake, _, tmp = rig
    song = make_songs(tmp / "n", ["09 z.mp3"]) / "09 z.mp3"
    monkeypatch.setattr(p, "ask_files", lambda: [str(song)])
    p.shortcuts["L"].activated.emit()
    assert len(p.controller.playlist) == 1 and fake.loaded[-1].endswith("09 z.mp3")

def test_real_keypress_reaches_shortcut(rig):
    p, fake, *_ = rig; p.activateWindow()
    assert QTest.qWaitForWindowActive(p)
    QTest.keyClick(p, Qt.Key_V)
    assert fake.state is State.STOPPED

def test_menus(rig, monkeypatch):
    p, fake, _, tmp = rig
    assert [a.text() for a in p.open_button.menu().actions()] == ["파일…", "폴더…"]
    folder = make_songs(tmp / "f", ["01 x.mp3"])
    monkeypatch.setattr(p, "ask_folder", lambda: [str(folder)])
    p.add_button.menu().actions()[1].trigger(); assert len(p.controller.playlist) == 4
    p.open_button.menu().actions()[1].trigger(); assert len(p.controller.playlist) == 1

def test_cancelled_dialog_does_nothing(rig, monkeypatch):
    p, *_ = rig; monkeypatch.setattr(p, "ask_files", lambda: [])
    p.open_files()
    assert len(p.controller.playlist) == 3 and p.controller.status == ""

def test_drop_adds_files(rig):
    p, _, _, tmp = rig
    song = make_songs(tmp / "d", ["05 d.mp3"]) / "05 d.mp3"
    mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(song))])
    p.dropEvent(QDropEvent(QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert len(p.controller.playlist) == 4

def test_jump_slider_handle_edge_click_keeps_value(qapp):
    s = JumpSlider(Qt.Horizontal); s.setRange(0, 180000); s.resize(200, 20); s.show()
    s.setValue(90000)
    opt = QStyleOptionSlider(); s.initStyleOption(opt)
    handle = s.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, s)
    QTest.mouseClick(s, Qt.LeftButton, Qt.NoModifier, QPoint(handle.left() + 1, handle.center().y()))
    assert s.value() == 90000
