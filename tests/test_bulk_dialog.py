import os

import pytest
from PyQt5.QtGui import QColor

from fakes import FakePlayer, FakeRunner, make_songs
from funplayer.controller import BulkOutcome
from funplayer.core.settings import Settings
from funplayer.core.taginfo import TrackInfo
from funplayer.engine.tagwrite import KEEP
from funplayer.ui.bulk_dialog import (
    COL_ARTIST, COL_COVER, COL_NEW, COL_NOTE, COL_TITLE, TAB_COMMON, TAB_COVERS, TAB_NAMES, UNSURE_BG, BulkTagDialog,
)
from funplayer.coverfind import Hit
from funplayer.ui.colors import CHANGED_BG, ERROR_COLOR
from funplayer.ui.player_panel import PlayerPanel

NAMES = ["멜로망스 - 선물.mp3", "[015B] 텅빈 거리에서.mp3", "벚꽃엔딩-버스커버스커.mp3", "희야.mp3"]


class Files:
    """가짜 태그 저장소 + 진짜 이름 바꾸기(사본 폴더)."""
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

    def rename_many(self, pairs):
        out = BulkOutcome()
        for old, new in pairs:
            os.rename(old, new)
            self.tags[new] = self.tags.pop(old, {})
            out.done.append((old, new))
        return out

    def undo_many(self, pairs):
        return self.rename_many([(n, o) for o, n in reversed(pairs)])


@pytest.fixture
def rig(qapp, tmp_path):
    folder = make_songs(tmp_path, NAMES)
    files = Files()
    paths = [str(folder / n) for n in NAMES]
    files.tags[paths[3]] = {"artist": "이승철,이승철"}
    covers = {paths[0]}
    d = BulkTagDialog([files.read(p) for p in paths], save_many=files.save_many, rename_many=files.rename_many,
                      undo_many=files.undo_many, read_info=files.read, has_cover=lambda p: p in covers)
    d.show()
    yield d, files, folder
    d.close()


def cell(d, r, c):
    return d.table.item(r, c).text()


def bg(d, r, c):
    return d.table.item(r, c).background().color()


def test_names_tab_preview(rig):
    d, _, _ = rig
    assert d.tabs.currentIndex() == TAB_NAMES
    assert [cell(d, 1, c) for c in (COL_ARTIST, COL_TITLE, COL_NEW)] == ["015B", "텅빈 거리에서", "015B - 텅빈 거리에서.mp3"]
    assert bg(d, 1, COL_ARTIST) == QColor(CHANGED_BG)
    assert cell(d, 0, COL_NEW) == "(지금 이름과 같음)"
    assert bg(d, 2, COL_ARTIST) == QColor(UNSURE_BG) and "확인" in cell(d, 2, COL_NOTE)     # 벚꽃엔딩-버스커버스커
    assert cell(d, 3, COL_ARTIST) == "이승철" and "하나로" in cell(d, 3, COL_NOTE)
    assert cell(d, 0, COL_COVER) == "있음" and cell(d, 1, COL_COVER) == "없음"
    assert d.table.item(1, COL_COVER).foreground().color() == QColor(ERROR_COLOR)
    assert d.go_button.text() == "태그 저장 + 이름 바꾸기 (3곡)"   # 주황 줄은 빼고 (선물은 태그만)
    assert "확인할 곡 1곡" in d.head.text()


def test_apply_names_saves_and_renames(rig):
    d, files, folder = rig
    d.go_button.click()
    assert (folder / "015B - 텅빈 거리에서.mp3").exists() and (folder / "이승철 - 희야.mp3").exists()
    assert (folder / "벚꽃엔딩-버스커버스커.mp3").exists()          # 확인 안 한 주황 줄은 그대로
    assert files.tags[str(folder / "이승철 - 희야.mp3")]["artist"] == "이승철"
    assert all("track" not in f for items, _ in files.calls for _, f in items)
    assert d.message_label.text() == "태그 3곡 저장, 파일 이름 2곡 바꿈"
    assert not d.undo_button.isHidden()
    d.undo_button.click()
    assert (folder / "[015B] 텅빈 거리에서.mp3").exists() and (folder / "희야.mp3").exists()


def test_swap_and_confirm_unsure_rows(rig):
    d, _, folder = rig
    d.table.selectRow(2)
    d.swap_button.click()
    assert [cell(d, 2, c) for c in (COL_ARTIST, COL_TITLE)] == ["벚꽃엔딩", "버스커버스커"]
    assert bg(d, 2, COL_ARTIST) != QColor(UNSURE_BG)
    d.swap_button.click()   # 다시 누르면 처음대로, 확인한 상태는 그대로
    d.table.selectRow(2)
    d.ok_button.click()
    assert d.go_button.text() == "태그 저장 + 이름 바꾸기 (4곡)"
    d.go_button.click()
    assert (folder / "버스커버스커 - 벚꽃엔딩.mp3").exists()


def test_manual_edit_confirms_row(rig):
    d, _, _ = rig
    d.table.item(2, COL_ARTIST).setText("버스커 버스커")
    assert cell(d, 2, COL_NEW) == "버스커 버스커 - 벚꽃엔딩.mp3" and bg(d, 2, COL_ARTIST) != QColor(UNSURE_BG)


def test_no_artist_row_waits_for_input(qapp, tmp_path):
    folder = make_songs(tmp_path, ["그냥제목.mp3"])
    d = BulkTagDialog([TrackInfo(str(folder / "그냥제목.mp3"))])
    assert "직접 입력" in cell(d, 0, COL_NOTE) and not d.go_button.isEnabled()
    d.table.item(0, COL_ARTIST).setText("가수")
    assert d.go_button.isEnabled() and cell(d, 0, COL_NEW) == "가수 - 그냥제목.mp3"


def test_common_tab_picture_for_all(rig):
    d, files, _ = rig
    d.tabs.setCurrentIndex(TAB_COMMON)
    assert d.table.isColumnHidden(COL_NEW) and d.go_button.text() == "저장 (0곡)"
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    assert d.set_picture(png)
    assert cell(d, 1, COL_COVER) == "넣음" and d.go_button.text() == "저장 (4곡)"
    d.go_button.click()
    assert files.calls[-1][1] == png and len(files.calls[-1][0]) == 4
    assert not d.picture_box.isChecked()


def test_common_album(rig):
    d, files, _ = rig
    d.tabs.setCurrentIndex(TAB_COMMON)
    d.common_edits["album"].textEdited.emit("앨범")
    d.common_edits["album"].setText("앨범")
    assert d.common_boxes["album"].isChecked() and d.go_button.text() == "저장 (4곡)"
    d.go_button.click()
    assert all(f == {"album": "앨범"} for _, f in files.calls[-1][0])


def test_non_mp3_skipped(qapp, tmp_path):
    d = BulkTagDialog([TrackInfo(str(tmp_path / "a.mp3")), TrackInfo(str(tmp_path / "b.flac"))])
    assert len(d.rows) == 1 and "MP3가 아닌 1곡" in d.head.text()


# ---- 패널: Ctrl+T, 그림 없는 곡 ----
@pytest.fixture
def panel(qapp, tmp_path):
    folder = make_songs(tmp_path, ["01 a.mp3", "02 b.mp3", "03 c.mp3"])
    with_cover = {str(folder / "02 b.mp3")}
    runner = FakeRunner()
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), runner=runner,
                    has_cover=lambda path: path in with_cover)
    p.controller.open([str(folder)]); p.refresh()
    yield p, runner, with_cover, folder
    if p.bulk_dialog is not None:
        p.bulk_dialog.close()
    p.shutdown(); p.deleteLater()


def red(p, row):
    return p.playlist_view.item(row).foreground().color() == QColor(ERROR_COLOR)


def test_ctrl_t_opens_with_selected(panel):
    p, *_ = panel
    p.select_rows([0, 2]); p._update_actions()
    assert p.actions["bulk_tags"].text() == "여러 곡 태그 고치기… (2곡)\tCtrl+T"
    p.shortcuts["Ctrl+T"].activated.emit()
    assert [os.path.basename(r.path) for r in p.bulk_dialog.rows] == ["01 a.mp3", "03 c.mp3"]


def test_find_missing_covers_marks_red_and_clears_after_cover(panel):
    p, runner, with_cover, folder = panel
    p._update_actions()
    assert p.actions["find_covers"].isEnabled() and not p.actions["select_covers"].isEnabled()
    p.actions["find_covers"].trigger()
    assert "찾는 중" in p.status_label.text()
    work, done = runner.calls[-1]
    done(work(), None); p.refresh()
    assert [red(p, r) for r in range(3)] == [True, False, True]
    assert "그림 없는 곡 2곡" in p.status_label.text()
    p._update_actions()
    p.actions["select_covers"].trigger()
    assert p.selected_rows() == [0, 2]
    assert p.actions["add_covers"].text() == "붉은 곡 그림 자동으로 찾기…"
    before = len(runner.calls)
    p.actions["add_covers"].trigger()
    assert p.bulk_dialog.tabs.currentIndex() == TAB_COVERS and len(p.bulk_dialog.rows) == 2
    assert len(runner.calls) == before + 1          # 첫 곡을 찾기 시작함
    with_cover.add(str(folder / "01 a.mp3"))     # 그림을 넣었다고 치고
    p._after_file_edit()
    assert [red(p, r) for r in range(3)] == [False, False, True]
    p.clear_cover_marks()
    assert not any(red(p, r) for r in range(3))


def test_red_mark_follows_rename(panel):
    p, runner, _, folder = panel
    p.find_missing_covers()
    work, done = runner.calls[-1]
    done(work(), None)
    p.controller._rename_everywhere(str(folder / "01 a.mp3"), str(folder / "가수 - a.mp3"))
    p.refresh()
    row = [t.title for t in p.controller.playlist.tracks].index("가수 - a")
    assert red(p, row)


def test_file_name_can_be_selected_and_copied(rig):
    from PyQt5.QtWidgets import QApplication, QLineEdit
    from funplayer.ui.bulk_dialog import COL_FILE
    d, _, _ = rig
    item = d.table.item(1, COL_FILE)
    d.table.setCurrentItem(item)
    d.table.editItem(item)
    editor = d.table.findChild(QLineEdit)
    assert editor is not None and editor.isReadOnly() and editor.text() == "[015B] 텅빈 거리에서.mp3"
    editor.setText("바꿔 봄")          # 읽기 전용이라 실제로는 못 치지만, 넣어도 값은 그대로
    d.table.closePersistentEditor(item)
    d.table.setFocus()
    assert cell(d, 1, COL_FILE) == "[015B] 텅빈 거리에서.mp3"
    d.copy_cell()
    assert QApplication.clipboard().text() == "[015B] 텅빈 거리에서.mp3"


def test_row_menu_searches_sites(qapp, tmp_path):
    folder = make_songs(tmp_path, ["멜로망스 - 선물.mp3"])
    opened = []
    d = BulkTagDialog([TrackInfo(str(folder / "멜로망스 - 선물.mp3"))], open_url=opened.append)
    labels = [a.text() for a in d.row_menu(0).actions() if a.text()]
    assert labels[:4] == ["지니에서 찾기", "멜론에서 찾기", "해외: 구글 이미지에서 찾기", "해외: 애플 뮤직에서 찾기"]
    for site in ("genie", "melon", "google_images", "apple"):
        d.search(0, site)
    assert opened[0].startswith("https://www.genie.co.kr/") and "%EB%A9%9C%EB%A1%9C%EB%A7%9D%EC%8A%A4" in opened[0]
    assert opened[2].startswith("https://www.google.com/search?tbm=isch&q=")
    assert opened[3].startswith("https://music.apple.com/kr/search?term=")


def test_picture_to_one_row_only(rig):
    d, files, _ = rig
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    d.save_picture_to(1, png)
    items, picture = files.calls[-1]
    assert picture == png and [os.path.basename(p) for p, _ in items] == ["[015B] 텅빈 거리에서.mp3"]
    assert "그림을 넣었습니다" in d.message_label.text()
    d.save_picture_to(1, b"nope")
    assert "jpg·png" in d.message_label.text()


def test_paste_picture_to_row_needs_image(rig):
    from PyQt5.QtWidgets import QApplication
    d, files, _ = rig
    QApplication.clipboard().setText("글자")
    d.paste_picture_to(0)
    assert "복사한 그림이 없습니다" in d.message_label.text() and not files.calls


# ---- 그림 찾기 탭 (곡마다 따로) ----
def hit(title, sure=True, image=None):
    return Hit("애플 뮤직", "가수", title, f"{title} 앨범", "2010", image or f"img-{title}".encode(), sure)


@pytest.fixture
def covers(qapp, tmp_path):
    folder = make_songs(tmp_path, NAMES)
    files = Files()
    paths = [str(folder / n) for n in NAMES]
    files.tags[paths[3]] = {"artist": "이승철", "title": "희야"}
    have = {paths[0]}
    runner = FakeRunner()
    asked = []
    found = {"텅빈 거리에서": hit("텅빈 거리에서"), "희야": hit("희야 (Live)", sure=False)}

    def find(artist, title):
        asked.append((artist, title))
        return found.get(title)

    changed = []
    d = BulkTagDialog([files.read(p) for p in paths], save_many=files.save_many, read_info=files.read,
                      has_cover=lambda p: p in have, after_change=lambda: changed.append(1),
                      start_tab=TAB_COVERS, find_cover=find, run_async=runner.run_async)
    d.show()
    yield d, files, runner, asked, have, changed
    d.close()


def finish_all(runner):
    while runner.pending:
        work, done = runner.pending.pop(0)
        try:
            done(work(), None)
        except Exception as e:  # noqa: BLE001
            done(None, e)


def cv(d, r, c):
    from funplayer.ui.bulk_dialog import CV_CHECK
    item = d.cover_table.item(r, c)
    return item.checkState() if c == CV_CHECK else item.text()


def test_cover_tab_searches_one_song_at_a_time_skipping_songs_with_cover(covers):
    d, _, runner, asked, *_ = covers
    assert d.cover_table.isVisible() and not d.table.isVisible()
    assert len(runner.pending) == 1                      # 한 곡씩 차례로
    assert "찾는 중 · 3곡 남음" in d.cover_progress.text()
    finish_all(runner)
    assert len(asked) == 3 and asked[0][1] == "텅빈 거리에서" and asked[2] == ("이승철", "희야")
    assert "선물" not in [t for _, t in asked]           # 그림 있는 멜로망스는 찾지 않음
    assert "다 찾았습니다" in d.cover_progress.text()


def test_cover_states_sure_checked_maybe_orange_none_red(covers):
    from PyQt5.QtCore import Qt
    from funplayer.ui.bulk_dialog import CV_CHECK, CV_NOTE, CV_PIC, CV_SONG, CV_SOURCE
    d, _, runner, *_ = covers
    finish_all(runner)
    assert cv(d, 0, CV_NOTE) == "그림 있음 · 찾지 않음"
    assert cv(d, 1, CV_CHECK) == Qt.Checked and cv(d, 1, CV_SOURCE) == "애플 뮤직"
    assert cv(d, 1, CV_NOTE) == "텅빈 거리에서 앨범 · 2010"
    assert cv(d, 3, CV_CHECK) == Qt.Unchecked and "확인" in cv(d, 3, CV_NOTE)
    assert d.cover_table.item(3, CV_SONG).background().color() == QColor(UNSURE_BG)
    assert cv(d, 2, CV_PIC) == "없음" and "지니·멜론에서 찾기" in cv(d, 2, CV_NOTE)
    assert d.cover_table.item(2, CV_SONG).foreground().color() == QColor(ERROR_COLOR)
    assert d.go_button.text() == "체크한 곡에 그림 넣기 (1곡)"


def test_checking_orange_row_adds_it(covers):
    from PyQt5.QtCore import Qt
    from funplayer.ui.bulk_dialog import CV_CHECK, CV_SONG
    d, _, runner, *_ = covers
    finish_all(runner)
    d.cover_table.item(3, CV_CHECK).setCheckState(Qt.Checked)
    assert d.go_button.text() == "체크한 곡에 그림 넣기 (2곡)"
    assert d.cover_table.item(3, CV_SONG).background().color() != QColor(UNSURE_BG)


def test_apply_covers_puts_each_songs_own_picture(covers):
    from PyQt5.QtCore import Qt
    from funplayer.ui.bulk_dialog import CV_CHECK, CV_NOTE
    d, files, runner, _, have, changed = covers
    finish_all(runner)
    d.cover_table.item(3, CV_CHECK).setCheckState(Qt.Checked)
    d.go()
    put = [(os.path.basename(items[0][0]), picture) for items, picture in files.calls]
    assert put == [("[015B] 텅빈 거리에서.mp3", "img-텅빈 거리에서".encode()), ("희야.mp3", "img-희야 (Live)".encode())]
    assert cv(d, 1, CV_NOTE) == "넣었습니다" and cv(d, 3, CV_NOTE) == "넣었습니다"
    assert "그림 2곡 넣었습니다" in d.message_label.text() and changed == [1]
    assert not d.go_button.isEnabled()


def test_research_only_missing_and_failed(covers):
    from funplayer.ui.bulk_dialog import CV_NOTE
    d, _, runner, asked, *_ = covers
    work, done = runner.pending.pop(0)
    done(None, OSError("down"))                          # 첫 곡은 인터넷이 막힘
    finish_all(runner)
    assert "인터넷" in cv(d, 1, CV_NOTE) and d.research_button.isEnabled()
    asked.clear()
    d.research_covers()
    finish_all(runner)
    assert sorted(t for _, t in asked) == sorted(["텅빈 거리에서", "벚꽃엔딩"])
    assert cv(d, 1, CV_NOTE) == "텅빈 거리에서 앨범 · 2010"


def test_close_stops_searching(covers):
    d, _, runner, asked, *_ = covers
    d.close()
    finish_all(runner)
    assert len(asked) == 1 and not runner.pending


def test_cover_row_menu_searches_with_tag_names_and_manual_picture_marks_done(qapp, tmp_path):
    from funplayer.ui.bulk_dialog import CV_NOTE
    folder = make_songs(tmp_path, ["희야.mp3"])
    files = Files()
    path = str(folder / "희야.mp3")
    files.tags[path] = {"artist": "이승철", "title": "희야"}
    opened, runner = [], FakeRunner()
    d = BulkTagDialog([files.read(path)], save_many=files.save_many, has_cover=lambda p: False,
                      start_tab=TAB_COVERS, find_cover=lambda a, t: None, run_async=runner.run_async,
                      open_url=opened.append)
    finish_all(runner)
    d.search(0, "melon")
    assert opened[0].startswith("https://www.melon.com/") and "%ED%9D%AC%EC%95%BC" in opened[0]
    d.save_picture_to(0, b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    assert cv(d, 0, CV_NOTE) == "넣었습니다"
    d.close()
