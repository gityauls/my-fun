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

def test_bad_year_and_track_not_saved(qapp, tmp_path):
    d, info = editor(qapp, tmp_path); got = []
    d.save_requested.connect(lambda *a: got.append(a))
    set_text(d.edits["year"], "이천"); d.save_button.click()
    assert got == [] and "년도" in d.message_label.text() and d.is_dirty()
    set_text(d.edits["year"], "1999"); set_text(d.edits["track"], "A1"); d.save_button.click()
    assert got == [] and "트랙" in d.message_label.text()
    set_text(d.edits["track"], "3/12"); d.save_button.click()
    assert len(got) == 1 and got[0][1] == {"year": "1999", "track": "3/12"}
    set_text(d.edits["year"], ""); set_text(d.edits["track"], ""); d.save_button.click()
    assert len(got) == 2   # 비우는 것은 된다


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


# ---- 인터넷에서 찾기 ----
from PyQt5.QtTest import QTest
from funplayer.musicbrainz import Candidate, MusicBrainzError


def inline(work, done):
    try:
        result = work()
    except Exception as e:  # noqa: BLE001
        done(None, e)
    else:
        done(result, None)


class FakeClient:
    def __init__(self, cands=(), cover=None, error=None):
        self.cands, self.cover_bytes, self.error = list(cands), cover, error
        self.searches, self.covers = [], []

    def search(self, title, artist, limit=10):
        self.searches.append((title, artist))
        if self.error:
            raise self.error
        return self.cands

    def cover(self, release_id):
        self.covers.append(release_id)
        if self.error:
            raise self.error
        return self.cover_bytes


CAND = Candidate("Song", "Singer", "Album", "2001", "5", "록", "rel-1")


def searcher(qapp, tmp_path, client, run=inline, info_kw=None, **kw):
    d, info = editor(qapp, tmp_path, **kw)
    if info_kw is not None:
        info = TrackInfo(info.path, **info_kw)
        d.show_info(info, None, editable=True)
    d.set_services(run, lambda: client)
    d.search_toggle.click()
    return d, info


def test_search_section_hidden_until_editable_with_services(qapp, tmp_path):
    d, info = editor(qapp, tmp_path)
    assert d.search_section.isHidden()   # 서비스 없음
    d.set_services(inline, lambda: None)
    assert not d.search_section.isHidden() and d.search_body.isHidden()   # 접힌 채
    d.show_info(info, None, editable=False)
    assert d.search_section.isHidden()


def test_open_search_grows_dialog_not_squeezes_fields(qapp, tmp_path):
    d, _ = searcher(qapp, tmp_path, FakeClient([CAND] * 10))
    d.search_button.click()
    assert d.height() >= d.layout().totalHeightForWidth(d.width())
    title = d.edits["title"]
    assert title.height() >= title.sizeHint().height()


def test_prefill_from_tags_then_filename(qapp, tmp_path):
    d, _ = searcher(qapp, tmp_path, FakeClient())
    assert (d.search_title.text(), d.search_artist.text()) == ("Old", "A")
    d2, _ = searcher(qapp, tmp_path, FakeClient())
    f = tmp_path / "가수 - 노래.mp3"; f.write_bytes(b"1")
    d2.show_info(TrackInfo(str(f)), None, editable=True)   # 태그가 없으면 파일 이름에서
    assert (d2.search_title.text(), d2.search_artist.text()) == ("노래", "가수")
    d2.search_toggle.click(); d2.search_toggle.click()   # 접었다 펴도 그대로
    assert (d2.search_title.text(), d2.search_artist.text()) == ("노래", "가수")


def test_search_lists_and_fills_empty_only(qapp, tmp_path):
    c = FakeClient([CAND, Candidate("Other", "", "", "", "", "", "")])
    d, _ = searcher(qapp, tmp_path, c, info_kw=dict(title="Mine"))
    assert d.search_button.isEnabled()
    d.search_button.click()
    assert c.searches == [("Mine", "")] and d.search_status.text() == "2곡 찾음"
    assert [d.result_list.item(i).text() for i in range(2)] == ["Song · Singer · Album · 2001", "Other"]
    assert d.result_list.currentRow() == 0 and d.fill_button.isEnabled()
    d.fill_button.click()
    got = {k: (e.currentText() if isinstance(e, QComboBox) else e.text()) for k, e in d.edits.items()}
    assert got == {"title": "Mine", "artist": "Singer", "album": "Album", "year": "2001", "genre": "록", "track": "5"}
    assert d.is_dirty() and YELLOW.lower() in d.edits["artist"].styleSheet().lower()


def test_fill_overwrites_when_box_off(qapp, tmp_path):
    cand = Candidate("Song", "Singer", "", "2001", "", "", "")   # 앨범·트랙·장르는 없음 -> 비우지 않는다
    d, _ = searcher(qapp, tmp_path, FakeClient([cand]))
    d.only_empty_box.setChecked(False)
    d.search_button.click(); d.fill_button.click()
    assert d.edits["title"].text() == "Song" and d.edits["artist"].text() == "Singer"
    assert d.edits["album"].text() == "B" and d.edits["track"].text() == "3" and d.edits["genre"].currentText() == "Pop"


def test_cover_fetched_only_when_missing(qapp, tmp_path):
    c = FakeClient([CAND], cover=PNG)
    d, _ = searcher(qapp, tmp_path, c)   # 그림 없음 -> 받는다
    d.search_button.click(); d.fill_button.click()
    assert c.covers == ["rel-1"] and d._picture == PNG and d.search_status.text() == "앨범 그림 받음"
    c2 = FakeClient([CAND], cover=PNG)
    d2, _ = searcher(qapp, tmp_path, c2, picture=JPG)   # 그림 있음 + 켬 -> 안 받는다
    d2.search_button.click(); d2.fill_button.click()
    assert c2.covers == [] and d2._picture is KEEP
    d2.only_empty_box.setChecked(False); d2.fill_button.click()   # 끄면 받는다
    assert c2.covers == ["rel-1"] and d2._picture == PNG
    c3 = FakeClient([CAND], cover=PNG)
    d3, _ = searcher(qapp, tmp_path, c3)
    d3.set_picture_bytes(JPG)   # 이미 넣은 그림이 있으면 켠 채로는 안 받는다
    d3.search_button.click(); d3.fill_button.click()
    assert c3.covers == [] and d3._picture == JPG
    c4 = FakeClient([CAND], cover=None)
    d4, _ = searcher(qapp, tmp_path, c4)
    d4.search_button.click(); d4.fill_button.click()
    assert d4.search_status.text() == "앨범 그림 없음" and d4._picture is KEEP


def test_candidate_without_release_skips_cover(qapp, tmp_path):
    c = FakeClient([Candidate("S", "", "", "", "", "", "")], cover=PNG)
    d, _ = searcher(qapp, tmp_path, c)
    d.search_button.click(); d.fill_button.click()
    assert c.covers == []


def test_late_reply_ignored(qapp, tmp_path):
    pending = []
    c = FakeClient([CAND], cover=PNG)
    d, info = searcher(qapp, tmp_path, c, run=lambda work, done: pending.append((work, done)))
    d.search_button.click()
    (w1, d1), = pending
    d1(w1(), None)
    assert d.result_list.count() == 1 and d.result_list.item(0).text().startswith("Song")
    d.fill_button.click()   # 그림 요청 대기
    other = tmp_path / "y.mp3"; other.write_bytes(b"1")
    assert d.show_info(TrackInfo(str(other), title="Y"), None, editable=True)   # 다른 곡으로
    assert d.result_list.count() == 0 and d.search_title.text() == "Y"
    work, done = pending[-1]
    done(work(), None)
    assert d._picture is KEEP and not d.search_status.isVisible()


def test_late_search_reply_after_track_change_ignored(qapp, tmp_path):
    pending = []
    d, _ = searcher(qapp, tmp_path, FakeClient([CAND]), run=lambda w, dn: pending.append((w, dn)))
    d.search_button.click()
    other = tmp_path / "y.mp3"; other.write_bytes(b"1")
    d.show_info(TrackInfo(str(other), title="Y"), None, editable=True)
    work, done = pending[0]; done(work(), None)
    assert d.result_list.count() == 0


def test_buttons_disabled_while_request_runs(qapp, tmp_path):
    pending = []
    c = FakeClient([CAND], cover=PNG)
    d, _ = searcher(qapp, tmp_path, c, run=lambda w, dn: pending.append((w, dn)))
    d.search_button.click()
    assert not d.search_button.isEnabled() and d.search_status.text() == "찾는 중…"
    d.search_button.click(); QTest.keyClick(d.search_title, Qt.Key_Return)   # 두 번째 요청은 가지 않는다
    assert len(pending) == 1
    w, dn = pending[0]; dn(w(), None)
    assert d.search_button.isEnabled() and d.fill_button.isEnabled()
    d.fill_button.click()   # 그림 요청이 가는 동안은 둘 다 잠긴다
    assert len(pending) == 2 and not d.fill_button.isEnabled() and not d.search_button.isEnabled()
    w, dn = pending[1]; dn(w(), None)
    assert d.search_button.isEnabled() and d.fill_button.isEnabled() and d._picture == PNG


def test_buttons_reenabled_after_error(qapp, tmp_path):
    d, _ = searcher(qapp, tmp_path, FakeClient(error=OSError("x")))
    d.search_button.click()
    assert d.search_button.isEnabled()


def test_saved_drops_late_cover(qapp, tmp_path):
    pending = []
    d, info = searcher(qapp, tmp_path, FakeClient([CAND], cover=PNG),
                       run=lambda w, dn: pending.append((w, dn)))
    d.search_button.click(); w, dn = pending[0]; dn(w(), None)
    d.fill_button.click()   # 그림 요청 대기
    d.saved(TrackInfo(info.path, title="Song"), None)
    assert d.search_button.isEnabled() and not d.search_status.isVisible()
    w, dn = pending[1]; dn(w(), None)
    assert d._picture is KEEP and not d.is_dirty()


def test_failed_drops_late_search(qapp, tmp_path):
    pending = []
    d, _ = searcher(qapp, tmp_path, FakeClient([CAND]), run=lambda w, dn: pending.append((w, dn)))
    d.search_button.click()
    d.failed("저장하지 못했습니다")
    assert d.search_button.isEnabled()
    w, dn = pending[0]; dn(w(), None)
    assert d.result_list.count() == 0


def test_client_factory_error_shows_red_text(qapp, tmp_path):
    d, _ = searcher(qapp, tmp_path, FakeClient([CAND]))
    d.set_services(inline, lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    d.search_button.click()
    assert d.search_status.text() == "인터넷에 연결하지 못했습니다"
    assert "#b3261e" in d.search_status.styleSheet().lower() and d.search_button.isEnabled()
    d._candidates = [CAND]; d.result_list.addItem("x"); d.result_list.setCurrentRow(0)
    d.fill_button.click()
    assert d.search_status.text() == "인터넷에 연결하지 못했습니다" and d.fill_button.isEnabled()


def test_search_error_text(qapp, tmp_path):
    busy = "MusicBrainz가 바쁩니다. 잠시 뒤 다시 눌러 보세요"
    d, _ = searcher(qapp, tmp_path, FakeClient(error=MusicBrainzError(busy)))
    d.search_button.click()
    assert d.search_status.text() == busy
    assert "#b3261e" in d.search_status.styleSheet().lower() and not d.fill_button.isEnabled()
    d2, _ = searcher(qapp, tmp_path, FakeClient(error=OSError("x")))
    d2.search_button.click(); assert d2.search_status.text() == "인터넷에 연결하지 못했습니다"
    d3, _ = searcher(qapp, tmp_path, FakeClient([]))
    d3.search_button.click(); assert d3.search_status.text() == "찾은 곡이 없습니다"


def test_empty_title_disables_search_and_enter_searches(qapp, tmp_path):
    c = FakeClient([CAND])
    d, _ = searcher(qapp, tmp_path, c)
    saves = []
    d.save_requested.connect(lambda *a: saves.append(a))
    d.search_title.setText("  ")
    assert not d.search_button.isEnabled()
    QTest.keyClick(d.search_title, Qt.Key_Return); assert c.searches == []
    d.search_title.setText("abc")
    QTest.keyClick(d.search_artist, Qt.Key_Return)
    assert c.searches == [("abc", "A")] and saves == []   # Enter가 저장으로 새지 않는다


def test_genre_pick_marks_changed(qapp, tmp_path):
    d, _ = editor(qapp, tmp_path)
    combo = d.edits["genre"]; combo.setCurrentIndex(combo.findText("재즈"))
    assert combo.currentText() == "재즈" and d.is_dirty() and d._changed_fields() == {"genre": "재즈"}
    assert YELLOW.lower() in combo.lineEdit().styleSheet().lower()
