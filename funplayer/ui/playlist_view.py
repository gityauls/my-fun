from __future__ import annotations

from PyQt5.QtCore import QMimeData, QModelIndex, QPoint, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QDrag, QFont, QPainter, QPainterPath
from PyQt5.QtWidgets import QAbstractItemView, QListWidget, QStyle, QStyledItemDelegate

from funplayer.core.contrast import error_color
from funplayer.core.themes import DEFAULT_THEME, Theme, get_theme
from funplayer.ui.colors import ERROR_COLOR, FAVORITE_COLOR
from funplayer.ui.glyphs import glyph_pixmap

ROWS_MIME = "application/x-myfun-rows"
ROLE_NUMBER = Qt.UserRole + 10    # 줄 번호
ROLE_CURRENT = Qt.UserRole + 11   # 지금 곡
ROLE_FAVORITE = Qt.UserRole + 12  # 즐겨찾기
ROLE_TITLE = Qt.UserRole + 13     # 번호·표시 없는 제목 (item.text()는 예전 그대로)
ROW_HEIGHT = 34
_RADIUS = 9
_PAD = 10
_NUM_WIDTH = 18
_GAP = 8
_HEART = 13
_EQ_HEIGHTS = (7, 12, 9)


class RowDelegate(QStyledItemDelegate):
    """줄 하나: 번호(지금 곡은 막대 3개), 제목, 즐겨찾기 하트. 글자색은 ForegroundRole을 따른다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.theme = get_theme(DEFAULT_THEME)

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(1, ROW_HEIGHT)   # 폭은 보기 폭을 따른다 (긴 제목은 줄임표)

    def text_color(self, index: QModelIndex, highlighted: bool) -> QColor:
        t = self.theme
        plain = QColor(t.row_fg if highlighted else t.ink)
        fg = index.data(Qt.ForegroundRole)
        if fg is None:
            return plain
        color = fg.color() if hasattr(fg, "color") else QColor(fg)
        # 즐겨찾기는 테마 색으로 (고른 줄에서는 하트가 표시하므로 줄 글자색). 회색 글은 그대로
        if color == QColor(FAVORITE_COLOR):
            return plain if highlighted else QColor(t.fav)
        if color == QColor(ERROR_COLOR):   # 고정 붉은색은 어두운 테마에서 읽히지 않는다
            return QColor(error_color(t.tint if highlighted else t.bg))
        return color

    def paint(self, p: QPainter, option, index: QModelIndex) -> None:
        t = self.theme
        current = bool(index.data(ROLE_CURRENT))
        favorite = bool(index.data(ROLE_FAVORITE))
        highlighted = current or bool(option.state & QStyle.State_Selected)
        fg = self.text_color(index, highlighted)
        rect = option.rect
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if highlighted:
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), _RADIUS, _RADIUS)
            p.fillPath(path, QColor(t.tint))
        p.setPen(QColor(t.row_fg if highlighted else t.mute))
        num = QRect(rect.left() + _PAD, rect.top(), _NUM_WIDTH, rect.height())
        if current:
            self._eq(p, num, p.pen().color())
        else:
            font = QFont(option.font)
            font.setPixelSize(11)
            font.setBold(False)
            p.setFont(font)
            p.drawText(num, Qt.AlignRight | Qt.AlignVCenter, str(index.data(ROLE_NUMBER) or ""))
        left = num.right() + 1 + _GAP
        right = rect.right() - _PAD
        if favorite:
            color = t.row_fg if highlighted else t.fav
            right -= _HEART
            p.drawPixmap(right + 1, rect.top() + (rect.height() - _HEART) // 2,
                         glyph_pixmap("heartOn", color, _HEART))
            right -= _GAP
        font = QFont(option.font)
        font.setPixelSize(13)
        p.setFont(font)
        p.setPen(fg)
        box = QRect(left, rect.top(), max(0, right - left + 1), rect.height())
        title = index.data(ROLE_TITLE)
        title = index.data(Qt.DisplayRole) if title is None else title
        p.drawText(box, Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(title or "", Qt.ElideRight, box.width()))
        p.restore()

    @staticmethod
    def _eq(p: QPainter, box: QRect, color: QColor) -> None:
        x = box.right() + 1 - (3 * 3 + 2 * 2)
        bottom = box.center().y() + 6
        for h in _EQ_HEIGHTS:
            p.fillRect(x, bottom - h, 3, h, color)
            x += 5


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
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._delegate = RowDelegate(self)
        self.setItemDelegate(self._delegate)

    def set_theme(self, theme: Theme) -> None:
        self._delegate.theme = theme
        self.viewport().update()

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
