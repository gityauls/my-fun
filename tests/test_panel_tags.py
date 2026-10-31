from __future__ import annotations

import os

import pytest
from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QColor, QImage, QPixmap
from fakes import FakePlayer, FakeRunner, make_songs
from funplayer.core.settings import Settings
from funplayer.core.taginfo import TrackInfo
from funplayer.engine.tagwrite import KEEP, TagWriteError
from funplayer.ui.player_panel import PlayerPanel


def real_png(color: str = "#336699") -> bytes:
    img = QImage(8, 8, QImage.Format_RGB32); img.fill(QColor(color))
    ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly); img.save(buf, "PNG")
    return bytes(ba)


class Disk:
    """가짜 파일 태그: read_info와 write_tags가 같은 값을 본다."""

    def __init__(self):
        self.tags: dict[str, dict] = {}
        self.fail: str | None = None

    def read(self, path):
        t = self.tags.get(path, {})
        return TrackInfo(path, title=t.get("title", ""), artist=t.get("artist", ""), album=t.get("album", ""),
                         picture=t.get("picture"))

    def write(self, path, fields, picture=KEEP):
        if self.fail:
            raise TagWriteError(self.fail)
        t = self.tags.setdefault(path, {})
        t.update(fields)
        if isinstance(picture, bytes):
            t["picture"] = picture

    def clear(self, path):
        self.tags.pop(path, None)


@pytest.fixture
def rig(qapp, tmp_path):
    disk, fake, runner = Disk(), FakePlayer(), FakeRunner()
    p = PlayerPanel(Settings({}, lambda: None), player=fake, runner=runner, read_info=disk.read,
                    write_tags=disk.write, clear_tags=disk.clear)
    p.resize(380, 480); p.show()
    p.controller.open([str(make_songs(tmp_path / "m", ["01 a.mp3", "02 b.txt.mp3"]))]); p.refresh()
    yield p, disk, runner, tmp_path
    p.shutdown(); p.deleteLater()


def test_menu_text(rig):
    p, *_ = rig
    assert p.actions["info_row"].text() == "곡 정보 고치기…"
    assert "곡 정보 고치기…" in [a.text() for a in p.context_menu.actions()]


def test_row_info_is_editable_for_existing_mp3(rig):
    p, disk, runner, tmp = rig
    p.playlist_view.setCurrentRow(1); p.show_row_info()
    d = p.info_dialog
    assert d._editable and d.path_label.text().endswith("02 b.txt.mp3")
    assert not d.search_section.isHidden()   # 서비스가 이어져 있다


def test_missing_and_non_mp3_are_readonly_with_note(rig):
    p, disk, runner, tmp = rig
    p.playlist_view.setCurrentRow(0)
    os.remove(p.controller.playlist.tracks[0].path)
    p.show_row_info()
    d = p.info_dialog
    assert not d._editable and d.message_label.text() == "파일이 없습니다"
    assert PlayerPanel._edit_state("x.flac") == (False, "MP3만 고칠 수 있습니다")
    assert PlayerPanel._edit_state("X.MP3") == (False, "파일이 없습니다")


def test_save_updates_subtitle_and_cover(rig):
    p, disk, runner, tmp = rig
    path = p.controller.playlist.tracks[0].path
    old = QPixmap(8, 8); old.fill(QColor("#ff0000"))
    p._cover_src, p._cover_key = old, path   # 이 곡의 큰 그림을 이미 읽어 둔 상태
    p.show_track_info(); d = p.info_dialog
    assert d._editable
    d.edits["artist"].setText("Singer"); d.edits["album"].setText("Rec")
    d.set_picture_bytes(real_png("#0000ff"))
    d.save_button.click()
    assert disk.tags[path]["artist"] == "Singer"
    assert d.message_label.text() == "저장했습니다" and not d.is_dirty()
    assert d.edits["artist"].text() == "Singer"
    assert "Singer" in p.controller.subtitle and "Singer" in p.artist_label.toolTip() + p.artist_label.text()
    # 큰 그림도 새로 읽혔다 (표시 열쇠를 되돌리지 않으면 옛 빨강이 남는다)
    assert QColor(p._cover_src.toImage().pixel(2, 2)) == QColor("#0000ff")


def test_save_failure_shows_reason_and_keeps_values(rig):
    p, disk, runner, tmp = rig
    p.show_track_info(); d = p.info_dialog
    disk.fail = "저장하지 못했습니다"
    d.edits["title"].setText("New"); d.save_button.click()
    assert d.message_label.text() == "저장하지 못했습니다" and d.edits["title"].text() == "New" and d.is_dirty()


def test_clear_tags(rig):
    p, disk, runner, tmp = rig
    path = p.controller.playlist.tracks[0].path
    disk.tags[path] = {"title": "T", "artist": "Singer"}
    p._cover_key = object(); p.refresh()
    p.show_track_info(); d = p.info_dialog
    d.clear_button.click(); d.confirm_button.click()
    assert path not in disk.tags and d.edits["title"].text() == "" and d.message_label.text() == "저장했습니다"


def test_radio_info_readonly(rig):
    p, disk, runner, tmp = rig
    from test_panel_radio import connect
    connect(p, runner)
    p.show_track_info(); d = p.info_dialog
    assert not d._editable and d.search_section.isHidden() and d.save_button.isHidden()
    assert d.message_label.isHidden()


def test_close_with_unsaved_edits_asks(rig, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox
    import funplayer.ui.info_dialog as dlg
    p, disk, runner, tmp = rig
    p.show_track_info(); d = p.info_dialog
    d.edits["title"].setText("Changed")
    asked, answers = [], [QMessageBox.No, QMessageBox.Yes]
    def fake(parent, title, text, *a, **k):
        asked.append(text); return answers.pop(0)
    monkeypatch.setattr(dlg.QMessageBox, "question", fake)
    assert not p.close() and p.isVisible()   # 아니오 = 닫기 취소
    assert asked == ["저장 안 한 내용이 있습니다. 버릴까요?"]
    assert p.close() and not p.isVisible()   # 예 = 닫힌다
    assert len(asked) == 2


def test_close_without_edits_does_not_ask(rig, monkeypatch):
    import funplayer.ui.info_dialog as dlg
    p, disk, runner, tmp = rig
    monkeypatch.setattr(dlg.QMessageBox, "question",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("물으면 안 됨")))
    p.show_track_info()
    assert p.close()


# ---- 5-C: 파일 이름 바꾸기 ----

@pytest.fixture
def rename_rig(qapp, tmp_path, tone_mp3):
    import shutil
    path = tmp_path / "곡.mp3"
    shutil.copy(tone_mp3, path)
    log = tmp_path / "rename_log.txt"
    settings = Settings({}, lambda: None)
    p = PlayerPanel(settings, player=FakePlayer(), runner=FakeRunner(), rename_log_path=str(log))
    p.resize(380, 480); p.show()
    p.controller.open([str(path)]); p.refresh()
    yield p, settings, path, log
    p.shutdown(); p.deleteLater()


def _rename_save(p, artist="가수", title="제목"):
    p.playlist_view.setCurrentRow(0); p.show_row_info()
    d = p.info_dialog
    d.edits["artist"].setText(artist); d.edits["title"].setText(title)
    d.rename_box.click()
    d.save_button.click()
    return d


def test_save_with_rename_updates_row_text(rename_rig):
    p, settings, path, log = rename_rig
    _rename_save(p)
    new = path.with_name("가수 - 제목.mp3")
    assert new.exists() and not path.exists()
    assert p.playlist_view.item(0).text().endswith("가수 - 제목")
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1


def test_rename_setting_persisted(rename_rig):
    p, settings, path, log = rename_rig
    p.playlist_view.setCurrentRow(0); p.show_row_info()
    assert settings.rename_on_save is False
    p.info_dialog.rename_box.click()
    assert settings.rename_on_save is True
    p.info_dialog.close(); p.info_dialog = None
    p.show_row_info()
    assert p.info_dialog.rename_box.isChecked()


def test_conflict_shows_red_and_writes_nothing(rename_rig):
    p, settings, path, log = rename_rig
    other = path.with_name("가수 - 제목.mp3")
    other.write_bytes(b"x")
    before = path.read_bytes()
    p.playlist_view.setCurrentRow(0); p.show_row_info()
    d = p.info_dialog
    d.edits["artist"].setText("가수"); d.edits["title"].setText("제목")
    d.rename_box.click()
    assert d.rename_preview.text() == "같은 이름의 파일이 이미 있습니다"
    # 미리보기 뒤에 겹친 경우를 흉내 낸다: 저장 경로가 겹침 오류를 받아도 아무것도 쓰지 않는다
    d.rename_target = lambda: str(other)
    d.save_button.click()
    assert path.read_bytes() == before and other.read_bytes() == b"x"
    assert d.message_label.text().startswith("같은 이름의 파일이 이미 있습니다")
    assert p.controller.last_rename() is None


def test_menu_undo_visible_and_text(rename_rig):
    p, settings, path, log = rename_rig
    p._update_actions()
    assert not p.actions["undo_rename"].isVisible()
    _rename_save(p)
    p._update_actions()
    act = p.actions["undo_rename"]
    assert act.isVisible()
    assert act.text() == "이름 되돌리기: 가수 - 제목.mp3 → 곡.mp3"
    act.trigger()
    assert path.exists() and not path.with_name("가수 - 제목.mp3").exists()
    assert p.playlist_view.item(0).text().endswith("곡")
    p._update_actions()
    assert not act.isVisible()
    assert "파일 이름을 되돌렸습니다" in p.status_label.text()
    assert "되돌렸습니다" in p.info_dialog.message_label.text()


def test_menu_undo_hidden_without_log(rename_rig):
    p, settings, path, log = rename_rig
    p._update_actions()
    assert not p.actions["undo_rename"].isVisible()
    keys = list(p.actions)
    assert keys.index("undo_rename") == keys.index("info_row") + 1


def test_dialog_undo_link_restores(rename_rig):
    p, settings, path, log = rename_rig
    d = _rename_save(p)
    new = path.with_name("가수 - 제목.mp3")
    d.undo_rename_requested.emit(str(path), str(new))
    assert path.exists() and not new.exists()
    assert d.message_label.text() == "파일 이름을 되돌렸습니다"
    assert d.path == str(path)
    assert p.controller.last_rename() is None


def test_dialog_undo_stale_pair_ignored(rename_rig):
    p, settings, path, log = rename_rig
    d = _rename_save(p)
    new = path.with_name("가수 - 제목.mp3")
    d.undo_rename_requested.emit(r"C:\no\old.mp3", r"C:\no\new.mp3")
    assert new.exists() and not path.exists()
    assert p.controller.last_rename() == (str(path), str(new))
    assert d.undo_link.isHidden()
