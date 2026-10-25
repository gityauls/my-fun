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
