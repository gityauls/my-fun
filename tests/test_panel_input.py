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
    p.actions["clear"].trigger()
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
    assert set(p.shortcuts) == {"Space", "X", "V", "Z", "B", "Left", "Right", "Up", "Down", "M", "L",
                                "R", "S", "Ctrl+S", "Ctrl+O", "Delete", "Return", "Enter", "Ctrl+A", "Ctrl+I", "Ctrl+M", "Ctrl+Tab",
                                "Ctrl+Left", "Ctrl+Right", "Ctrl+E", "Ctrl+D", "Ctrl+T"}
    assert dict(SHORTCUTS)["Ctrl+E"] == "toggle_fx_visible"
    assert dict(SHORTCUTS)["Ctrl+Left"] == "prev" and dict(SHORTCUTS)["Ctrl+Right"] == "next"
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
    assert [a.text() for a in p.open_button.menu().actions()][:2] == ["파일…\tL", "폴더…"]
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


def test_selection_survives_track_change(rig):
    p, *_ = rig; v = p.playlist_view
    v.item(2).setSelected(True); p.controller.next(); p.refresh()
    assert v.item(2).isSelected() and v.item(1).text().startswith("▶") and v.item(1).font().bold()
    assert not v.item(0).font().bold() and not v.item(0).text().startswith("▶")

def test_delete_removes_selected_and_selects_same_row(rig):
    p, fake, *_ = rig; v = p.playlist_view
    v.item(0).setSelected(True); v.item(1).setSelected(True)
    p.shortcuts["Delete"].activated.emit()
    assert [t.title for t in p.controller.playlist.tracks] == ["03 c"] and fake.loaded[-1].endswith("03 c.mp3")
    assert p.selected_rows() == [0]

def test_real_keys_in_list(rig):
    p, fake, *_ = rig; v = p.playlist_view; p.activateWindow()
    assert QTest.qWaitForWindowActive(p)
    v.setFocus(); v.setCurrentRow(2)
    QTest.keyClick(v, Qt.Key_Return); assert fake.loaded[-1].endswith("03 c.mp3")
    QTest.keyClick(v, Qt.Key_Delete); assert len(p.controller.playlist) == 2

def test_enter_and_select_all(rig):
    p, fake, *_ = rig; p.playlist_view.setCurrentRow(1)
    p.shortcuts["Return"].activated.emit(); assert fake.loaded[-1].endswith("02 b.mp3")
    p.shortcuts["Ctrl+A"].activated.emit(); assert p.selected_rows() == [0, 1, 2]

def test_context_menu(rig):
    p, fake, *_ = rig
    assert [a.text() for a in p.context_menu.actions()] == [
        "재생\tEnter", "곡 정보 고치기…", "여러 곡 태그 고치기…\tCtrl+T", "즐겨찾기 (맨 위로)\tCtrl+D", "이름 되돌리기", "선택한 곡 지우기\tDel", "", "전체 선택\tCtrl+A"]
    p.playlist_view.clearSelection(); p.context_menu.aboutToShow.emit()
    assert not p.actions["remove"].isEnabled()
    p.playlist_view.setCurrentRow(1); p.context_menu.aboutToShow.emit()
    assert p.actions["remove"].isEnabled() and p.actions["play_selected"].isEnabled()
    p.actions["play_selected"].trigger(); assert fake.loaded[-1].endswith("02 b.mp3")

def test_drag_rows_reorders_and_keeps_selection(rig):
    p, fake, *_ = rig; v = p.playlist_view
    at = v.visualItemRect(v.item(0)).topLeft() + QPoint(5, 2)
    md = v.mimeData([v.item(2)])  # QDropEvent doesn't own the mime data; keep it alive
    v.dropEvent(QDropEvent(QPointF(at), Qt.MoveAction, md, Qt.LeftButton, Qt.NoModifier))
    assert [t.title for t in p.controller.playlist.tracks] == ["03 c", "01 a", "02 b"]
    assert p.controller.playlist.index == 1 and p.selected_rows() == [0] and len(fake.loaded) == 1

def test_file_drop_on_list_adds(rig):
    p, _, _, tmp = rig; v = p.playlist_view
    song = make_songs(tmp / "d", ["05 d.mp3"]) / "05 d.mp3"
    mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(song))])
    v.dropEvent(QDropEvent(QPointF(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert len(p.controller.playlist) == 4

def test_bottom_row_and_menus(rig):
    p, *_ = rig
    assert not hasattr(p, "clear_button") and p.list_button.text() == "목록"
    assert [a.text() for a in p.open_button.menu().actions()] == ["파일…\tL", "폴더…", "재생목록…\tCtrl+O"]
    assert [a.text() for a in p.add_button.menu().actions()] == ["파일…", "폴더…", "재생목록…"]
    assert [a.text() for a in p.list_menu.actions()] == [
        "재생목록 저장…\tCtrl+S", "즐겨찾기 저장…", "즐겨찾기 불러오기…", "", "그림 없는 곡", "", "선택한 곡 지우기\tDel", "중복 곡 지우기", "없는·깨진 파일 지우기", "정렬", "", "목록 비우기"]
    assert [a.text() for a in p.list_menu.actions()[9].menu().actions()] == ["이름순", "폴더·이름순"]

def test_save_and_open_playlist_with_keys(rig, monkeypatch):
    p, fake, _, tmp = rig
    monkeypatch.setattr(p, "ask_playlist_save", lambda: str(tmp / "목록"))
    p.shortcuts["Ctrl+S"].activated.emit()
    assert (tmp / "목록.m3u8").exists() and p.status_label.text() == "저장했습니다: 목록.m3u8"
    p.actions["clear"].trigger(); assert len(p.controller.playlist) == 0
    monkeypatch.setattr(p, "ask_playlist_open", lambda: str(tmp / "목록.m3u8"))
    p.shortcuts["Ctrl+O"].activated.emit()
    assert [t.title for t in p.controller.playlist.tracks] == ["01 a", "02 b", "03 c"]

def test_add_playlist_menu(rig, monkeypatch):
    p, _, _, tmp = rig
    p.controller.save_playlist(str(tmp / "l.m3u8"))
    monkeypatch.setattr(p, "ask_playlist_open", lambda: str(tmp / "l.m3u8"))
    p.add_button.menu().actions()[2].trigger(); assert len(p.controller.playlist) == 6

def test_save_skipped_when_cancelled_or_empty(rig, monkeypatch):
    p, *_ = rig; asked = []
    monkeypatch.setattr(p, "ask_playlist_save", lambda: asked.append(1) or "")
    p.save_playlist(); assert asked == [1] and p.controller.status == ""
    p.actions["clear"].trigger(); p.save_playlist(); assert asked == [1]
    p.list_menu.aboutToShow.emit(); assert not p.actions["save"].isEnabled()

def test_list_menu_edit_actions(rig):
    p, *_ = rig
    p.playlist_view.clearSelection(); p.list_menu.aboutToShow.emit()
    assert p.actions["save"].isEnabled() and not p.actions["remove"].isEnabled()
    p.actions["sort_path"].trigger(); p.actions["dedupe"].trigger()
    assert p.status_label.text() == "중복 곡이 없습니다"
    p.actions["remove_unplayable"].trigger(); assert p.status_label.text() == "지울 곡이 없습니다"

def test_file_drops_are_always_copies(rig):
    from PyQt5.QtGui import QDragEnterEvent
    p, _, _, tmp = rig
    mime = QMimeData()   # QDropEvent doesn't own the mime data; keep it alive
    mime.setUrls([QUrl.fromLocalFile(str(make_songs(tmp / "x", ["09 z.mp3"]) / "09 z.mp3"))])
    both = Qt.CopyAction | Qt.MoveAction
    enter = QDragEnterEvent(QPoint(10, 10), both, mime, Qt.LeftButton, Qt.ShiftModifier)
    assert enter.proposedAction() == Qt.MoveAction
    p.dragEnterEvent(enter); assert enter.isAccepted() and enter.dropAction() == Qt.CopyAction
    drop = QDropEvent(QPointF(10, 10), both, mime, Qt.LeftButton, Qt.ShiftModifier)
    assert drop.proposedAction() == Qt.MoveAction
    p.dropEvent(drop); assert drop.isAccepted() and drop.dropAction() == Qt.CopyAction


def test_ctrl_i_opens_current_and_reuses_dialog(rig):
    p, *_ = rig
    p.shortcuts["Ctrl+I"].activated.emit(); d = p.info_dialog
    assert d.isVisible() and d.path_label.text().endswith("01 a.mp3")
    p.art_label.clicked.emit()
    assert p.info_dialog is d

def test_context_info_uses_row_and_does_not_follow(rig):
    p, *_ = rig
    p.playlist_view.setCurrentRow(2); p.context_menu.aboutToShow.emit()
    assert p.actions["info_row"].isEnabled()
    p.actions["info_row"].trigger()
    assert p.info_dialog.path_label.text().endswith("03 c.mp3")
    p.next(); assert p.info_dialog.path_label.text().endswith("03 c.mp3")

def test_view_button_and_info_action(rig):
    p, *_ = rig
    assert p.view_button.text() == "보기" and p.view_menu.actions()[0].text() == "곡 정보…\tCtrl+I"
    p.controller.clear(); p.refresh(); p.playlist_view.setCurrentRow(-1); p.view_menu.aboutToShow.emit()
    assert not p.actions["info"].isEnabled()

def test_info_action_enabled_with_current_track(rig):
    p, *_ = rig
    p.view_menu.aboutToShow.emit()
    assert p.actions["info"].isEnabled()

def test_show_track_info_falls_back_to_selected_row(rig):
    # state with rows but no current track, reached through the Playlist API (clear, then add)
    p, *_ = rig
    pl = p.controller.playlist
    paths = [t.path for t in pl.tracks]
    pl.clear(); pl.add(paths); p.refresh()
    assert pl.index is None and p.playlist_view.count() == 3
    p.playlist_view.setCurrentRow(1); p.view_menu.aboutToShow.emit()
    assert p.actions["info"].isEnabled()
    p.show_track_info()
    assert p.info_dialog.path_label.text().endswith("02 b.mp3")


HIDDEN_IN_MINI = ("elapsed_label", "total_label", "stop_button", "repeat_button", "shuffle_button",
                  "mute_button", "volume_slider", "separator", "playlist_view", "open_button",
                  "add_button", "list_button", "view_button", "count_label", "status_label")
SHOWN_IN_MINI = ("art_label", "title_label", "artist_label", "prev_button", "play_button",
                 "next_button", "seek_slider", "mini_button")

def test_set_mini_hides_moves_and_restores(rig):
    p, _, store, _ = rig; seen = []; p.miniChanged.connect(seen.append)
    assert p.mini_button.toolTip() == "작게 보기"
    p.set_mini(True)
    assert p.is_mini and store["player_mini"] is True and seen == [True]
    assert not any(getattr(p, n).isVisible() for n in HIDDEN_IN_MINI)
    assert all(getattr(p, n).isVisible() for n in SHOWN_IN_MINI)
    assert p.art_label.width() == 40 and p.mini_button.toolTip() == "보통 보기"
    assert all(p.head_row.indexOf(b) >= 0 for b in (p.prev_button, p.play_button, p.next_button))
    p.set_mini(True); assert seen == [True]
    p.set_mini(False)
    assert not p.is_mini and store["player_mini"] is False and seen == [True, False]
    assert all(getattr(p, n).isVisible() for n in HIDDEN_IN_MINI)
    assert p.art_label.width() == 56 and p.mini_button.toolTip() == "작게 보기"
    assert [p.control_row.indexOf(b) for b in
            (p.prev_button, p.play_button, p.stop_button, p.next_button)] == [0, 1, 2, 3]

def test_mini_is_short(rig):
    p, *_ = rig; p.set_mini(True); p.layout().activate()
    assert p.sizeHint().height() < 100

def test_mini_toggles_by_key_button_and_title_double_click(rig):
    p, *_ = rig
    QTest.mouseDClick(p.title_label, Qt.LeftButton); assert not p.is_mini
    p.shortcuts["Ctrl+M"].activated.emit(); assert p.is_mini
    QTest.mouseDClick(p.title_label, Qt.LeftButton); assert not p.is_mini
    p.mini_button.click(); assert p.is_mini
    p.mini_button.click(); assert not p.is_mini

def test_view_menu_mini_items(rig):
    p, _, store, _ = rig; seen = []; p.miniOnTopChanged.connect(seen.append)
    assert [a.text() for a in p.view_menu.actions()] == [
        "곡 정보…\tCtrl+I", "작게 보기\tCtrl+M", "음향 효과 칸 보이기\tCtrl+E", "",
        "작게 볼 때 항상 위", "멀티미디어 키 사용"]
    p.view_menu.aboutToShow.emit()
    assert not p.actions["mini"].isChecked() and p.actions["mini_on_top"].isChecked()
    p.actions["mini"].trigger(); assert p.is_mini
    p.view_menu.aboutToShow.emit(); assert p.actions["mini"].isChecked()
    p.actions["mini_on_top"].trigger()
    assert store["player_mini_on_top"] is False and seen == [False]

def test_shortcuts_still_work_in_mini(rig):
    p, fake, *_ = rig; p.set_mini(True)
    p.shortcuts["Space"].activated.emit()
    assert fake.state is State.PAUSED


from fakes import FakeApi
from funplayer.ui.media_keys import HOTKEY_ID_BASE, MediaKeys

def keys_panel(qapp, tmp_path, store, api):
    fake = FakePlayer()
    p = PlayerPanel(Settings(store, lambda: None), player=fake, media_keys=MediaKeys(api=api))
    p.controller.open([str(make_songs(tmp_path / "m", ABC))]); p.refresh()
    return p, fake

def test_panel_media_keys_wiring(qapp, tmp_path):
    api = FakeApi(); p, fake = keys_panel(qapp, tmp_path, {}, api)
    k = p.media_keys
    k.handle_hotkey(HOTKEY_ID_BASE + 0xB3); assert fake.state is State.PAUSED
    k.handle_hotkey(HOTKEY_ID_BASE + 0xB0); assert p.controller.playlist.index == 1
    k.handle_hotkey(HOTKEY_ID_BASE + 0xB2); assert fake.state is State.STOPPED
    p.shutdown(); p.deleteLater()
    assert api.registered == {}

def test_panel_media_keys_busy_notice(qapp):
    api = FakeApi(busy={0xB3})
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), media_keys=MediaKeys(api=api))
    assert (p.controller.status, p.controller.status_error) == ("멀티미디어 키를 다른 프로그램이 쓰고 있습니다", False)
    assert set(api.registered.values()) == {0xB0, 0xB1, 0xB2}
    p.shutdown(); p.deleteLater()
    assert api.registered == {}

def test_media_keys_option(qapp, tmp_path):
    api = FakeApi(); store = {"player_media_keys": False}
    p, _ = keys_panel(qapp, tmp_path, store, api)
    assert api.registered == {}
    p.view_menu.aboutToShow.emit(); act = p.actions["media_keys"]
    assert act.text() == "멀티미디어 키 사용" and not act.isChecked()
    act.trigger(); assert store["player_media_keys"] is True and len(api.registered) == 4
    act.trigger(); assert store["player_media_keys"] is False and api.registered == {}
    p.shutdown(); p.deleteLater()

def test_focused_media_shortcuts(rig):
    p, fake, *_ = rig
    assert len(p.media_shortcuts) == 5
    assert all(sc.context() == Qt.WidgetWithChildrenShortcut for sc in p.media_shortcuts)
    p.media_shortcuts[0].activated.emit(); assert fake.state is State.PAUSED

def test_fallback_media_shortcuts_do_not_auto_repeat(rig):
    p, *_ = rig
    assert p.media_shortcuts and all(not sc.autoRepeat() for sc in p.media_shortcuts)

def test_media_keys_silently_retried_when_window_becomes_active(qapp):
    from PyQt5.QtCore import QEvent
    api = FakeApi(busy={0xB3})
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), media_keys=MediaKeys(api=api))
    try:
        assert len(api.registered) == 3
        api.busy.clear(); p.controller.notify("안내")
        p.show(); p.activateWindow()
        assert QTest.qWaitForWindowActive(p, 1000) and p.isActiveWindow()
        assert len(api.registered) == 4 and p.controller.status == "안내"   # 알림 없이 다시 건다
        api.busy.add(0xB3); p.media_keys.disable(); p.media_keys.enable(); assert len(api.registered) == 3
        api.busy.clear(); QApplication.sendEvent(p, QEvent(QEvent.ActivationChange))
        assert len(api.registered) == 4
    finally:
        p.shutdown(); p.deleteLater()

def test_media_keys_not_retried_when_option_off(qapp):
    from PyQt5.QtCore import QEvent
    api = FakeApi(); store = {"player_media_keys": False}
    p = PlayerPanel(Settings(store, lambda: None), player=FakePlayer(), media_keys=MediaKeys(api=api))
    try:
        p.show(); p.activateWindow(); QTest.qWaitForWindowActive(p, 1000)
        QApplication.sendEvent(p, QEvent(QEvent.ActivationChange))
        assert api.registered == {} and api.calls == []
    finally:
        p.shutdown(); p.deleteLater()

def test_busy_notice_does_not_hide_resume_notice(qapp, tmp_path):
    from funplayer.core.m3u import write_playlist
    songs = make_songs(tmp_path / "m", ABC)
    write_playlist(str(tmp_path / "last.m3u8"), [str(songs / n) for n in ABC])
    store = {"player_last_track": str(songs / "02 b.mp3"), "player_last_position": 72.0}
    api = FakeApi(busy={0xB3})
    p = PlayerPanel(Settings(store, lambda: None), player=FakePlayer(), session_path=str(tmp_path / "last.m3u8"),
                    media_keys=MediaKeys(api=api))
    try:
        assert p.controller.status == "이어 듣기: 1:12부터" and len(api.registered) == 3
    finally:
        p.shutdown(); p.deleteLater()

def test_turning_media_keys_off_clears_busy_notice(qapp):
    api = FakeApi(busy={0xB3})
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), media_keys=MediaKeys(api=api))
    try:
        assert p.controller.status == "멀티미디어 키를 다른 프로그램이 쓰고 있습니다"
        p.set_media_keys(False)
        assert p.controller.status == "" and api.registered == {}
        p.set_media_keys(True); assert p.controller.status == "멀티미디어 키를 다른 프로그램이 쓰고 있습니다"
        p.controller.notify("안내"); p.set_media_keys(False)
        assert p.controller.status == "안내"   # 다른 알림은 그대로
    finally:
        p.shutdown(); p.deleteLater()
