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
