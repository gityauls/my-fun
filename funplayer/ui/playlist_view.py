from __future__ import annotations

from PyQt5.QtCore import QMimeData, QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QAbstractItemView, QListWidget

ROWS_MIME = "application/x-myfun-rows"


class PlaylistView(QListWidget):
    """여러 줄 선택, 끌어서 옮기기, 파일 놓기. 줄을 직접 옮기지 않고 신호만 보낸다."""

    rowsMoved = pyqtSignal(list, int)   # 옮길 줄(오름차순), 놓을 자리(옛 번호 기준 0..n)
    filesDropped = pyqtSignal(list)     # 로컬 파일 경로

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

    def mimeTypes(self) -> list[str]:
        return [ROWS_MIME, "text/uri-list"]

    def mimeData(self, items) -> QMimeData:
        rows = sorted(self.row(i) for i in items)
        md = QMimeData()
        md.setData(ROWS_MIME, ",".join(map(str, rows)).encode("ascii"))
        return md

    def startDrag(self, supported_actions) -> None:
        # Qt 기본 startDrag는 MoveAction으로 끝나면 원래 줄을 지운다. 그래서 직접 끈다.
        items = self.selectedItems()
        if not items:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(items))
        drag.exec_(Qt.MoveAction)

    def drop_row(self, pos: QPoint) -> int:
        item = self.itemAt(pos)
        if item is None:
            return self.count()
        row = self.row(item)
        return row if pos.y() < self.visualItemRect(item).center().y() else row + 1

    @staticmethod
    def _rows(md) -> list[int]:
        if not md.hasFormat(ROWS_MIME):
            return []
        text = bytes(md.data(ROWS_MIME)).decode("ascii")
        return [int(x) for x in text.split(",") if x]

    @staticmethod
    def _paths(md) -> list[str]:
        return [u.toLocalFile() for u in md.urls() if u.isLocalFile()] if md.hasUrls() else []

    def _wanted(self, md) -> bool:
        return bool(self._rows(md) or self._paths(md))

    def dragEnterEvent(self, event) -> None:
        if self._wanted(event.mimeData()):
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._wanted(event.mimeData()):
            super().dragMoveEvent(event)
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        rows, paths = self._rows(md), self._paths(md)
        before = self.drop_row(event.pos())
        # 모델이 아무것도 넣거나 옮기지 않게 IgnoreAction으로 바꾼 뒤,
        # 끌기 표시와 자동 스크롤 정리만 부모에게 맡긴다.
        event.setDropAction(Qt.IgnoreAction)
        super().dropEvent(event)
        if rows:
            self.rowsMoved.emit(rows, before)
        elif paths:
            self.filesDropped.emit(paths)
