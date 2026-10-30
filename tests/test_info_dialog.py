import os
from PyQt5.QtCore import Qt
import funplayer.ui.info_dialog as dlg
from funplayer.core.taginfo import TrackInfo
from funplayer.ui.info_dialog import TrackInfoDialog

KEYS = ["제목", "가수", "앨범", "년도", "장르", "트랙", "길이", "형식", "크기"]

def test_fields(qapp, tmp_path):
    f = tmp_path / "x.mp3"; f.write_bytes(b"1")
    d = TrackInfoDialog()
    d.show_info(TrackInfo(str(f), title="Morning Coffee", artist="Lo-Fi Band", year="2019", track="3/12",
                          duration=225, codec="mp3float", bitrate=192000, sample_rate=44100, channels=2,
                          size=5_452_595), None)
    v = d.value_labels
    assert d.windowTitle() == "곡 정보" and list(v) == KEYS
    assert [v[k].text() for k in KEYS] == ["Morning Coffee", "Lo-Fi Band", "—", "2019", "—", "3/12",
                                           "3:45", "MP3 · 192 kbps · 44.1 kHz · 스테레오", "5.2 MB"]
    assert d.path_label.text() == str(f) and d.folder_button.isEnabled()
    assert (d.folder_button.text(), d.close_button.text()) == ("폴더 열기", "닫기")
    assert all(l.textInteractionFlags() & Qt.TextSelectableByMouse for l in [*v.values(), d.path_label])

def shown(qapp, info):
    d = TrackInfoDialog(); d.show_info(info, None); d.show(); qapp.processEvents()
    return d

def fully_shown(label):
    return label.height() >= label.heightForWidth(label.width())

def test_format_line_fits_on_one_line(qapp, tmp_path):
    d = shown(qapp, TrackInfo(str(tmp_path / "x.mp3"), title="Morning Coffee", duration=225, codec="mp3float",
                              bitrate=192000, sample_rate=44100, channels=2, size=5_452_595))
    fmt = d.value_labels["형식"]
    assert fmt.text() == "MP3 · 192 kbps · 44.1 kHz · 스테레오"
    assert fmt.fontMetrics().horizontalAdvance(fmt.text()) <= fmt.width() and fully_shown(fmt)
    widest = dlg.WIDEST_FORMAT
    assert fmt.fontMetrics().horizontalAdvance(widest) <= fmt.width()

def test_long_wrapped_title_is_fully_visible(qapp, tmp_path):
    title = " ".join(["Morning Coffee Lo-Fi"] * 6)[:120]
    d = shown(qapp, TrackInfo(str(tmp_path / "x.mp3"), title=title, artist="Band"))
    label = d.value_labels["제목"]
    assert len(title) == 120 and label.text() == title
    assert label.heightForWidth(label.width()) > label.fontMetrics().lineSpacing() and fully_shown(label)
    assert all(fully_shown(l) for l in d.value_labels.values())

def test_long_path_without_spaces_is_fully_visible(qapp):
    path = "D:\\" + "\\".join(["음악모음_2003년_발라드_베스트"] * 5) + "\\01-가수이름-노래제목_리마스터.mp3"
    path = path + "x" * (125 - len(path) - 4) + ".mp3"
    d = shown(qapp, TrackInfo(path))
    box = d.path_label
    assert len(path) == 125 and " " not in path and box.text() == path
    lines = box.document().size().height()   # QPlainTextEdit: 줄 수
    assert lines > 1 and box.verticalScrollBar().maximum() == 0
    assert lines * box.fontMetrics().lineSpacing() <= box.viewport().height()
    assert box.isReadOnly() and box.textInteractionFlags() & Qt.TextSelectableByMouse

def test_empty_info_shows_dashes(qapp, tmp_path):
    d = TrackInfoDialog(); d.show_info(TrackInfo(str(tmp_path / "gone" / "x.mp3")), None)
    assert all(d.value_labels[k].text() == "—" for k in KEYS) and not d.folder_button.isEnabled()

def test_folder_button_calls_reveal(qapp, tmp_path, monkeypatch):
    calls = []; monkeypatch.setattr(dlg, "reveal_in_explorer", calls.append)
    f = tmp_path / "x.mp3"; f.write_bytes(b"1")
    d = TrackInfoDialog(); d.show_info(TrackInfo(str(f)), None); d.folder_button.click()
    assert calls == [str(f)]

def test_reveal_in_explorer_commands(tmp_path, monkeypatch):
    runs, starts = [], []
    monkeypatch.setattr(dlg.subprocess, "Popen", lambda args, **kw: runs.append(args))
    monkeypatch.setattr(dlg.os, "startfile", starts.append, raising=False)
    f = tmp_path / "x.mp3"; f.write_bytes(b"1")
    dlg.reveal_in_explorer(str(f))
    dlg.reveal_in_explorer(str(tmp_path / "gone.mp3"))
    dlg.reveal_in_explorer(str(tmp_path / "no" / "dir" / "x.mp3"))
    assert runs == [["explorer", "/select,", os.path.normpath(str(f))]] and starts == [str(tmp_path)]
    def boom(*a, **k): raise OSError("no explorer")
    monkeypatch.setattr(dlg.subprocess, "Popen", boom)
    dlg.reveal_in_explorer(str(f))   # 예외가 나오지 않는다


# ---- 5-A: 고칠 수 있는 창 ----
from PyQt5.QtWidgets import QComboBox, QMessageBox
from funplayer.engine.tagwrite import KEEP, REMOVE

JPG = b"\xff\xd8\xff\xe0" + b"0" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20
YELLOW = "#FFF6D6"

def editor(qapp, tmp_path, picture=None, **kw):
    f = tmp_path / "x.mp3"; f.write_bytes(b"1")
    info = TrackInfo(str(f), title="Old", artist="A", album="B", year="2019", genre="Pop", track="3",
                     picture=picture, **kw)
    d = TrackInfoDialog(); d.show_info(info, None, editable=True); d.show(); qapp.processEvents()
    return d, info

def set_text(edit, text):
    if isinstance(edit, QComboBox): edit.setEditText(text)
    else: edit.setText(text)

def test_changed_field_yellow_and_save_enabled(qapp, tmp_path):
    d, _ = editor(qapp, tmp_path)
    assert list(d.edits) == ["title", "artist", "album", "year", "genre", "track"]
    assert isinstance(d.edits["genre"], QComboBox) and d.edits["genre"].count() == 14
    assert not d.save_button.isEnabled() and d.message_label.isHidden()
    assert YELLOW not in d.edits["title"].styleSheet()
    set_text(d.edits["title"], "New")
    assert YELLOW in d.edits["title"].styleSheet() and YELLOW not in d.edits["artist"].styleSheet()
    assert d.save_button.isEnabled() and d.is_dirty()
    assert d.message_label.text() == "노란 칸 = 바뀐 값 (아직 저장 안 됨)" and "#8A6D00" in d.message_label.styleSheet()
    set_text(d.edits["genre"], "Rock")
    assert YELLOW in d.edits["genre"].lineEdit().styleSheet()

def test_revert_disables_save(qapp, tmp_path):
    d, _ = editor(qapp, tmp_path)
    set_text(d.edits["title"], "New"); set_text(d.edits["title"], "Old")
    assert not d.save_button.isEnabled() and not d.is_dirty() and YELLOW not in d.edits["title"].styleSheet()
    set_text(d.edits["title"], "  Old  ")   # 앞뒤 빈칸만 다르면 바뀐 게 아니다
    assert not d.is_dirty()

def test_save_emits_changed_only(qapp, tmp_path):
    d, info = editor(qapp, tmp_path); got = []
    d.save_requested.connect(lambda *a: got.append(a))
    set_text(d.edits["title"], "  New Title ")
    set_text(d.edits["genre"], " 록 ")
    d.save_button.click()
    assert got == [(info.path, {"title": "New Title", "genre": "록"}, KEEP)]

def test_picture_bytes_checked(qapp, tmp_path):
    d, _ = editor(qapp, tmp_path)
    assert not d.set_picture_bytes(b"GIF89a" + b"0" * 20)
    assert d.message_label.text() == "jpg·png 그림만 넣을 수 있습니다" and "#B3261E" in d.message_label.styleSheet()
    assert not d.is_dirty()
    assert not d.set_picture_bytes(JPG + b"0" * (10 * 1024 * 1024))
    assert d.message_label.text() == "그림이 너무 큽니다 (10 MB까지)" and "#B3261E" in d.message_label.styleSheet()
    assert d.set_picture_bytes(PNG) and d.is_dirty() and d.save_button.isEnabled()
    assert "#E8B400" in d.art_label.styleSheet() and "2px" in d.art_label.styleSheet()
    got = []; d.save_requested.connect(lambda *a: got.append(a)); d.save_button.click()
    assert got[0][1] == {} and got[0][2] == PNG

def test_pick_button_uses_file_dialog(qapp, tmp_path, monkeypatch):
    d, _ = editor(qapp, tmp_path)
    img = tmp_path / "c.jpg"; img.write_bytes(JPG)
    monkeypatch.setattr(dlg.QFileDialog, "getOpenFileName", lambda *a, **k: (str(img), ""))
    d.pick_button.click()
    assert d._picture == JPG
    monkeypatch.setattr(dlg.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    d.pick_button.click(); assert d._picture == JPG   # 취소하면 그대로

def test_remove_picture_marks_remove(qapp, tmp_path):
    d, _ = editor(qapp, tmp_path, picture=PNG)
    assert d.remove_pic_button.isEnabled()
    d.remove_pic_button.click()
    assert d._picture is REMOVE and d.is_dirty() and not d.remove_pic_button.isEnabled()
    got = []; d.save_requested.connect(lambda *a: got.append(a)); d.save_button.click()
    assert got[0][2] is REMOVE
    d2, _ = editor(qapp, tmp_path)   # 곡에 그림이 없으면 꺼짐
    assert not d2.remove_pic_button.isEnabled()

def test_close_dirty_asks(qapp, tmp_path, monkeypatch):
    d, _ = editor(qapp, tmp_path); answers = [False, True]; asked = []
    monkeypatch.setattr(d, "confirm_discard", lambda: asked.append(1) or answers.pop(0))
    set_text(d.edits["title"], "New")
    d.close_button.click(); assert d.isVisible() and d.edits["title"].text() == "New"
    d.close_button.click(); assert not d.isVisible() and len(asked) == 2
    assert not d.is_dirty()   # 버린 값은 처음대로

def test_confirm_discard_asks_message(qapp, tmp_path, monkeypatch):
    d, _ = editor(qapp, tmp_path); seen = []
    def fake(parent, title, text, *a, **k): seen.append(text); return QMessageBox.Yes
    monkeypatch.setattr(dlg.QMessageBox, "question", fake)
    assert d.confirm_discard() and seen == ["저장 안 한 내용이 있습니다. 버릴까요?"]

def test_clean_close_does_not_ask(qapp, tmp_path, monkeypatch):
    d, _ = editor(qapp, tmp_path)
    monkeypatch.setattr(d, "confirm_discard", lambda: (_ for _ in ()).throw(AssertionError))
    d.close(); assert not d.isVisible()

def test_switching_path_while_dirty_asks(qapp, tmp_path, monkeypatch):
    d, info = editor(qapp, tmp_path); answers = [False, True]
    monkeypatch.setattr(d, "confirm_discard", lambda: answers.pop(0))
    set_text(d.edits["title"], "New")
    other = TrackInfo(str(tmp_path / "y.mp3"), title="Other")
    assert d.show_info(other, None, editable=True) is False
    assert d.edits["title"].text() == "New" and d.path_label.text() == info.path
    assert d.show_info(other, None, editable=True) is True
    assert d.edits["title"].text() == "Other" and not d.is_dirty()

def test_clear_confirm_bar(qapp, tmp_path):
    d, info = editor(qapp, tmp_path); got = []
    d.clear_requested.connect(got.append)
    assert d.confirm_bar.isHidden() and d.clear_button.text() == "태그 모두 지우기…"
    d.clear_button.click(); assert d.confirm_bar.isVisible()
    d.cancel_button.click(); assert d.confirm_bar.isHidden() and got == []
    d.clear_button.click(); d.confirm_button.click()
    assert got == [info.path] and d.confirm_bar.isHidden()
    assert (d.confirm_button.text(), d.cancel_button.text()) == ("지우기", "그만두기")

def test_readonly_modes(qapp, tmp_path):
    for note in ("MP3만 고칠 수 있습니다", "파일이 없습니다", ""):
        d = TrackInfoDialog(); d.show_info(TrackInfo(str(tmp_path / "y.mp3"), title="T"), None, False, note)
        d.show(); qapp.processEvents()
        for e in d.edits.values():
            assert (e.lineEdit() if isinstance(e, QComboBox) else e).isReadOnly()
        assert all(b.isHidden() for b in (d.pick_button, d.remove_pic_button, d.clear_button, d.save_button))
        assert d.close_button.isVisible() and d.folder_button.isVisible()
        assert d.message_label.text() == note and d.message_label.isVisible() == bool(note)
        assert not d.is_dirty() and d.value_labels["제목"].text() == "T"

def test_saved_resets_dirty(qapp, tmp_path):
    d, info = editor(qapp, tmp_path)
    set_text(d.edits["title"], "New"); d.set_picture_bytes(JPG)
    d.saved(TrackInfo(info.path, title="New", artist="A", album="B", year="2019", genre="Pop", track="3"), None)
    assert not d.is_dirty() and not d.save_button.isEnabled() and d._picture is KEEP
    assert d.message_label.text() == "저장했습니다" and "#5F6368" in d.message_label.styleSheet()
    assert YELLOW not in d.edits["title"].styleSheet() and d.art_label.styleSheet() == ""
    set_text(d.edits["title"], "X"); assert d.message_label.text().startswith("노란 칸")

def test_failed_keeps_edits_red(qapp, tmp_path):
    d, _ = editor(qapp, tmp_path)
    set_text(d.edits["title"], "New"); d.failed("저장하지 못했습니다")
    assert d.edits["title"].text() == "New" and d.is_dirty()
    assert d.message_label.text() == "저장하지 못했습니다" and "#B3261E" in d.message_label.styleSheet()

def test_drop_picture_file(qapp, tmp_path):
    from PyQt5.QtCore import QMimeData, QUrl, QPoint
    from PyQt5.QtGui import QDropEvent
    d, _ = editor(qapp, tmp_path)
    img = tmp_path / "c.png"; img.write_bytes(PNG)
    def drop(*paths):
        m = QMimeData(); m.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
        d.dropEvent(QDropEvent(QPoint(5, 5), Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier))
    drop(img, img); assert d._picture is KEEP   # 한 개만
    txt = tmp_path / "a.txt"; txt.write_bytes(b"1"); drop(txt); assert d._picture is KEEP
    drop(img); assert d._picture == PNG


def test_same_path_reshow_keeps_edits(qapp, tmp_path):
    d, info = editor(qapp, tmp_path)
    set_text(d.edits["title"], "New"); d.set_picture_bytes(PNG)
    assert d.show_info(info, None, editable=True, note="n") is True
    assert d.edits["title"].text() == "New" and d._picture == PNG and d.is_dirty()
    assert d.save_button.isEnabled()

def test_same_path_reshow_when_clean_reloads(qapp, tmp_path):
    d, info = editor(qapp, tmp_path)
    import dataclasses
    d.show_info(dataclasses.replace(info, title="Fresh"), None, editable=True)
    assert d.edits["title"].text() == "Fresh" and not d.is_dirty()

def test_esc_reject_dirty_asks(qapp, tmp_path, monkeypatch):
    d, _ = editor(qapp, tmp_path); answers = [False, True]; asked = []
    monkeypatch.setattr(d, "confirm_discard", lambda: asked.append(1) or answers.pop(0))
    set_text(d.edits["title"], "New")
    d.reject(); assert d.isVisible() and d.edits["title"].text() == "New"
    d.reject(); assert not d.isVisible() and len(asked) == 2 and not d.is_dirty()

def test_picture_add_then_remove(qapp, tmp_path):
    d, _ = editor(qapp, tmp_path)   # 곡에 그림 없음: 넣었다 빼면 처음으로
    d.set_picture_bytes(PNG); assert d.remove_pic_button.isEnabled()
    d.remove_pic_button.click()
    assert d._picture is KEEP and not d.is_dirty() and d.art_label.styleSheet() == ""
    d2, _ = editor(qapp, tmp_path, picture=JPG)   # 그림 있음: 넣은 뒤 빼기 = 그림 없음
    d2.set_picture_bytes(PNG); d2.remove_pic_button.click()
    assert d2._picture is REMOVE and d2.is_dirty()

def test_drops_reach_dialog_not_fields(qapp, tmp_path):
    d, _ = editor(qapp, tmp_path)
    kids = [(e.lineEdit() if isinstance(e, QComboBox) else e) for e in d.edits.values()]
    assert d.acceptDrops() and not any(w.acceptDrops() for w in [*kids, d.path_label, d.path_label.viewport()])

def test_cursor_at_start_and_default_button(qapp, tmp_path):
    d, info = editor(qapp, tmp_path)
    long = TrackInfo(info.path, title="T" * 200)
    d.show_info(long, None, editable=True)
    assert d.edits["title"].cursorPosition() == 0 and d.save_button.isDefault() and not d.close_button.isDefault()
    d.show_info(long, None, editable=False)
    assert d.close_button.isDefault() and not d.save_button.isDefault()

def test_edit_clears_failed_text(qapp, tmp_path):
    d, _ = editor(qapp, tmp_path)
    set_text(d.edits["title"], "N"); d.failed("저장하지 못했습니다")
    set_text(d.edits["title"], "NN"); assert d.message_label.text().startswith("노란 칸")
    set_text(d.edits["genre"], "재즈"); assert d.is_dirty()
