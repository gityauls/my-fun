import pytest
import os
from PyQt5.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt5.QtGui import QDropEvent
from PyQt5.QtWidgets import QAbstractItemView
from funplayer.ui.playlist_view import ROWS_MIME, PlaylistView

def make_view():
    v = PlaylistView(); v.resize(300, 200)
    for t in ["a", "b", "c"]:
        v.addItem(t)
    v.show(); return v

def drop(v, pos, mime, action=Qt.MoveAction):
    v.dropEvent(QDropEvent(QPointF(pos), action, mime, Qt.LeftButton, Qt.NoModifier))

def test_view_setup(qapp):
    v = PlaylistView()
    assert v.selectionMode() == QAbstractItemView.ExtendedSelection
    assert v.dragDropMode() == QAbstractItemView.DragDrop and v.dragEnabled() and v.acceptDrops()

def test_mime_carries_sorted_rows(qapp):
    v = make_view(); md = v.mimeData([v.item(2), v.item(0)])
    assert md.hasFormat(ROWS_MIME) and bytes(md.data(ROWS_MIME)).decode() == "0,2"

def test_drop_row(qapp):
    v = make_view(); r1 = v.visualItemRect(v.item(1))
    assert v.drop_row(r1.topLeft() + QPoint(3, 1)) == 1
    assert v.drop_row(QPoint(3, r1.bottom())) == 2
    assert v.drop_row(QPoint(3, 190)) == 3

def test_drop_emits_rows_moved_and_leaves_items(qapp):
    v = make_view(); got = []
    v.rowsMoved.connect(lambda rows, before: got.append((rows, before)))
    drop(v, v.visualItemRect(v.item(0)).topLeft() + QPoint(3, 1), v.mimeData([v.item(2)]))
    assert got == [([2], 0)] and [v.item(i).text() for i in range(v.count())] == ["a", "b", "c"]

def test_drop_files_emits_local_paths(qapp, tmp_path):
    v = make_view(); got = []
    v.filesDropped.connect(got.append)
    md = QMimeData(); md.setUrls([QUrl.fromLocalFile(str(tmp_path / "x.mp3")), QUrl("http://e.com/a.mp3")])
    drop(v, QPoint(5, 5), md, Qt.CopyAction)
    assert [[os.path.normpath(p) for p in paths] for paths in got] == [[str(tmp_path / "x.mp3")]]
    assert v.count() == 3


# ---- 줄 그리기 (5.5) ----

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QListWidgetItem
from funplayer.core.contrast import MIN_TEXT, contrast, error_color
from funplayer.core.themes import THEMES, get_theme
from funplayer.ui.colors import ERROR_COLOR, FAVORITE_COLOR
from funplayer.ui.playlist_view import ROLE_CURRENT, ROLE_FAVORITE, ROLE_NUMBER, ROLE_TITLE, ROW_HEIGHT


def rows_view():
    v = PlaylistView(); v.resize(300, 200); v.set_theme(get_theme("light"))
    for n, (title, cur, fav, color) in enumerate((
            ("AAA", True, False, None), ("BBB", False, True, QColor(FAVORITE_COLOR)),
            ("MMMMMM", False, False, QColor(ERROR_COLOR)), ("DDD", False, False, QColor(Qt.gray)))):
        item = QListWidgetItem("  원문 그대로")
        item.setData(ROLE_NUMBER, n + 1); item.setData(ROLE_TITLE, title)
        item.setData(ROLE_CURRENT, cur); item.setData(ROLE_FAVORITE, fav)
        item.setData(Qt.ForegroundRole, color)
        v.addItem(item)
    v.show(); return v


def colors_in(img, rect):
    return {img.pixelColor(x, y).name() for x in range(rect.left(), rect.right())
            for y in range(rect.top(), rect.bottom())}


def test_row_height_and_text_kept(qapp):
    v = rows_view()
    assert v.visualItemRect(v.item(0)).height() == ROW_HEIGHT == 34
    assert v.item(1).text() == "  원문 그대로"


def test_foreground_role_shows_in_row(qapp):
    v = rows_view(); d = v.itemDelegate(); t = get_theme("light")
    index = v.model().index
    assert d.text_color(index(2, 0), False) == QColor(error_color(t.bg))
    assert d.text_color(index(3, 0), False) == QColor(t.mute)    # 없는 곡도 테마에서 읽혀야 한다
    assert d.text_color(index(1, 0), False) == QColor(t.fav)     # 즐겨찾기 색은 테마를 따른다
    assert d.text_color(index(1, 0), True) == QColor(t.row_fg)
    assert d.text_color(index(0, 0), False) == QColor(t.ink)
    seen = []; real = d.text_color                # offscreen에는 글꼴이 없어 픽셀로 확인할 수 없다
    d.text_color = lambda i, h: seen.append(i.row()) or real(i, h)
    v.viewport().grab()
    assert sorted(set(seen)) == [0, 1, 2, 3]


def test_current_row_has_tint_and_favorite_heart(qapp):
    v = rows_view(); t = get_theme("light")
    img = v.viewport().grab().toImage()
    assert QColor(t.tint).name() in colors_in(img, v.visualItemRect(v.item(0)))
    r = v.visualItemRect(v.item(1))
    assert QColor(t.fav).name() in colors_in(img, r.adjusted(r.width() - 30, 0, 0, 0))


def test_current_row_title_is_bold(qapp):
    v = rows_view(); d = v.itemDelegate(); seen = {}; real = d.title_font
    d.title_font = lambda base, cur: seen.setdefault(cur, real(base, cur))   # offscreen은 글꼴을 픽셀로 못 잰다
    v.viewport().grab()
    assert seen[True].bold() and not seen[False].bold() and seen[True].pixelSize() == 13


def test_rows_never_wider_than_the_view(qapp):
    v = rows_view()
    v.resize(900, 200); QApplication.processEvents()
    v.resize(200, 200); QApplication.processEvents()
    assert v.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert v.visualItemRect(v.item(0)).width() <= v.viewport().width()    # 오른쪽 하트가 잘리지 않는다


def test_paints_in_all_themes(qapp):
    v = rows_view()
    for t in THEMES:
        v.set_theme(t); v.viewport().grab()


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_red_row_is_readable_on_every_theme(qapp, theme):
    v = rows_view(); v.set_theme(theme)
    d = v.itemDelegate(); index = v.model().index(2, 0)
    assert contrast(d.text_color(index, False).name(), theme.bg) >= MIN_TEXT
    assert contrast(d.text_color(index, True).name(), theme.tint) >= MIN_TEXT
