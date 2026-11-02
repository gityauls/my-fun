import os

import pytest
from PyQt5.QtGui import QColor

from fakes import FakePlayer, make_songs
from funplayer.controller import BulkOutcome
from funplayer.core.settings import Settings
from funplayer.core.taginfo import TrackInfo
from funplayer.engine.tagwrite import KEEP
from funplayer.ui.bulk_dialog import TAB_NAME, TAB_PASTE, TAB_RENAME, TAB_TRACK, BulkTagDialog
from funplayer.ui.colors import CHANGED_BG
from funplayer.ui.player_panel import PlayerPanel

NAMES = ["[As_One]05.Day By Day.mp3", "[As_ One]02.그녀의 게임.mp3", "DJDOC - remember.mp3"]


class Store:
    """가짜 파일 태그 저장소: save_many가 쓰면 read_info가 그 값을 읽는다."""
    def __init__(self):
        self.tags: dict[str, dict] = {}
        self.calls = []

    def read(self, path):
        return TrackInfo(path, **self.tags.get(path, {}))

    def save_many(self, items, picture=KEEP):
        self.calls.append((items, picture))
        out = BulkOutcome()
        for path, fields in items:
            self.tags.setdefault(path, {}).update(fields)
            out.done.append((path, path))
        return out


@pytest.fixture
def rig(qapp, tmp_path):
    folder = make_songs(tmp_path, NAMES)
    store = Store()
    paths = [str(folder / n) for n in NAMES]
    store.tags[paths[2]] = {"artist": "DJDOC", "title": "remember"}
    d = BulkTagDialog([store.read(p) for p in paths], save_many=store.save_many, read_info=store.read)
    d.show()
    yield d, store, paths
    d.close()


def cell(d, r, c):
    return d.table.item(r, c).text()


def yellow(d, r, c):
    return d.table.item(r, c).background().color() == QColor(CHANGED_BG)


def test_opens_without_changes(rig):
    d, store, _ = rig
    assert d.save_button.text() == "저장 (0곡)" and not d.save_button.isEnabled()
    assert cell(d, 2, 1) == "DJDOC" and not yellow(d, 2, 1)
    assert d.table.isColumnHidden(5)


def test_name_tab_guesses_and_saves(rig):
    d, store, paths = rig
    d.tabs.setCurrentIndex(TAB_NAME)
    assert d.name_on.isChecked()
    assert [cell(d, 0, c) for c in (1, 2, 4)] == ["As One", "Day By Day", "5"] and yellow(d, 0, 1)
    assert cell(d, 1, 2) == "그녀의 게임" and cell(d, 1, 4) == "2"
    assert not yellow(d, 2, 1)                       # 이미 같은 값
    assert d.save_button.text() == "저장 (2곡)"
    d.save_button.click()
    items, picture = store.calls[0]
    assert picture is KEEP and [os.path.basename(p) for p, _ in items] == NAMES[:2]
    assert items[0][1] == {"artist": "As One", "title": "Day By Day", "track": "5"}
    assert not d.name_on.isChecked() and d.save_button.text() == "저장 (0곡)"
    assert cell(d, 0, 2) == "Day By Day" and not yellow(d, 0, 2)
    assert d.message_label.text() == "2곡 저장했습니다"


def test_only_empty_keeps_existing(rig):
    d, _, _ = rig
    d.only_empty.setChecked(True)
    d.tabs.setCurrentIndex(TAB_NAME)
    assert cell(d, 2, 1) == "DJDOC"


def test_bad_pattern_blocks_save(rig):
    d, _, _ = rig
    d.tabs.setCurrentIndex(TAB_NAME)
    d.name_pattern.setEditText("%모름%")
    assert not d.save_button.isEnabled() and "모르는 낱말" in d.message_label.text()


def test_paste_lines_count_and_order(rig):
    d, store, _ = rig
    d.tabs.setCurrentIndex(TAB_PASTE)
    d.paste_text.setPlainText("1. 하나\n2. 둘")
    assert d.paste_on.isChecked() and not d.save_button.isEnabled()
    assert "2줄 · 3곡" in d.message_label.text()
    d.paste_text.setPlainText("1. 하나\n2. 둘\n3. 셋")
    assert [cell(d, r, 2) for r in range(3)] == ["하나", "둘", "셋"] and cell(d, 2, 4) == "3"
    d.table.setCurrentCell(2, 0); d.move_row(-1)          # 셋째 곡을 위로
    assert os.path.basename(d.rows[1].path) == NAMES[2] and cell(d, 1, 2) == "둘"


def test_track_numbers_and_common(rig):
    d, store, _ = rig
    d.tabs.setCurrentIndex(TAB_TRACK)
    d.track_start.setValue(3); d.track_total.setChecked(True)
    assert [cell(d, r, 4) for r in range(3)] == ["3/5", "4/5", "5/5"]
    d.common_edits["album"].setText("앨범X")
    d.common_boxes["album"].setChecked(True)
    assert all(cell(d, r, 3) == "앨범X" for r in range(3))
    d.common_boxes["album"].setChecked(False)
    assert cell(d, 0, 3) == ""


def test_common_typing_checks_box(rig):
    d, _, _ = rig
    d.common_edits["year"].textEdited.emit("1999")
    assert d.common_boxes["year"].isChecked()


def test_manual_cell_edit(rig):
    d, store, _ = rig
    d.table.item(0, 2).setText("직접 제목")
    assert yellow(d, 0, 2) and d.save_button.text() == "저장 (1곡)"
    d.save_button.click()
    assert store.calls[0][0][0][1] == {"title": "직접 제목"}


def test_picture_applies_to_all(rig):
    d, store, _ = rig
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    assert d.set_picture(png)
    assert d.picture_box.isChecked() and d.save_button.text() == "저장 (3곡)"
    d.save_button.click()
    assert store.calls[0][1] == png and len(store.calls[0][0]) == 3
    assert not d.set_picture(b"nope") and "jpg·png" in d.message_label.text()


def test_non_mp3_skipped(qapp, tmp_path):
    d = BulkTagDialog([TrackInfo(str(tmp_path / "a.mp3")), TrackInfo(str(tmp_path / "b.flac"))])
    assert len(d.rows) == 1 and "MP3가 아닌 1곡" in d.head.text()


def test_rename_tab_with_real_controller(qapp, tmp_path):
    folder = make_songs(tmp_path, NAMES)
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer())
    try:
        p.controller.open([str(folder)]); p.refresh()
        tags = {str(folder / NAMES[0]): {"artist": "As One", "title": "Day By Day"},
                str(folder / NAMES[2]): {"artist": "DJDOC", "title": "remember"}}
        infos = [TrackInfo(t.path, **tags.get(t.path, {})) for t in p.controller.playlist.tracks]
        c = p.controller
        d = BulkTagDialog(infos, save_many=c.save_many, rename_many=c.rename_many, undo_many=c.undo_many)
        d.tabs.setCurrentIndex(TAB_RENAME)
        assert not d.table.isColumnHidden(5)
        texts = {os.path.basename(r.path): d.table.item(i, 5).text() for i, r in enumerate(d.rows)}
        assert texts[NAMES[0]] == "As One - Day By Day.mp3"
        assert texts[NAMES[1]] == "(가수·제목이 있어야 합니다)"
        assert texts[NAMES[2]] == "(지금 이름과 같음)"
        assert d.rename_button.text() == "파일 이름 바꾸기 (1곡)"
        d.rename_button.click()
        assert (folder / "As One - Day By Day.mp3").exists() and not d.undo_button.isHidden()
        assert "As One - Day By Day" in [t.title for t in c.playlist.tracks]
        d.undo_button.click()
        assert (folder / NAMES[0]).exists() and d.undo_button.isHidden()
        assert d.message_label.text() == "1곡 파일 이름을 되돌렸습니다"
    finally:
        p.shutdown(); p.deleteLater()


def test_rename_waits_for_unsaved_changes(rig):
    d, _, _ = rig
    d.table.item(0, 1).setText("가수")
    d.tabs.setCurrentIndex(TAB_RENAME)
    assert d.rename_button.text() == "먼저 [저장]을 누르세요" and not d.rename_button.isEnabled()


def test_panel_ctrl_t_opens_with_selected(qapp, tmp_path):
    folder = make_songs(tmp_path, ["01 a.mp3", "02 b.mp3", "03 c.mp3"])
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer())
    try:
        p.controller.open([str(folder)]); p.refresh()
        p.select_rows([0, 2]); p._update_actions()
        assert p.actions["bulk_tags"].text() == "여러 곡 태그 고치기… (2곡)\tCtrl+T"
        p.shortcuts["Ctrl+T"].activated.emit()
        assert [os.path.basename(r.path) for r in p.bulk_dialog.rows] == ["01 a.mp3", "03 c.mp3"]
        p.bulk_dialog.close()
    finally:
        p.shutdown(); p.deleteLater()
