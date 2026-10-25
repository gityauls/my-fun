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
