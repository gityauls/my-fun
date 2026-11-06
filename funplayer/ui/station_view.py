from __future__ import annotations

from PyQt5.QtCore import QMimeData, QModelIndex, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QDrag, QFont, QFontMetrics, QPainter, QPainterPath
from PyQt5.QtWidgets import (QAbstractItemView, QAction, QInputDialog, QMenu, QStyle,
                             QTreeWidget, QTreeWidgetItem)

from funplayer.core.stations import StationList
from funplayer.core.themes import Theme
from funplayer.ui.glyphs import glyph_pixmap
from funplayer.ui.playlist_view import ROLE_CURRENT, ROLE_TITLE, ROW_HEIGHT, RowDelegate
from funplayer.ui.style import css_color

STATION_MIME = "application/x-myfun-station"
KEY_ROLE = Qt.UserRole + 1   # 묶음 줄의 묶음 키
ROLE_COUNT = Qt.UserRole + 14   # 묶음 줄의 방송 수
GROUP_HEIGHT = 32
LIVE_CHIP = "LIVE"
_RADIUS = 9
_PAD = 10
_GROUP_PAD = 8
_GROUP_GAP = 6
_CHEVRON = 14
_MARK_WIDTH = 14   # 지금 방송의 막대 표시 칸. 다른 줄도 비워 둬 이름이 나란하다
_GAP = 8
_CHIP_PAD = 6
_CHIP_RADIUS = 5


def ask_name(parent, current: str) -> str | None:
    """이름 바꾸기 입력창. 취소하면 None. 테스트가 이 함수를 바꿔 끼운다."""
    text, ok = QInputDialog.getText(parent, "이름 바꾸기", "이름", text=current)
    return text if ok else None


class StationDelegate(RowDelegate):
    """묶음 줄(접기 표시, 이름, 방송 수)과 방송 줄(지금 방송은 막대 표시, 이름, LIVE). 시안의 라디오 화면."""

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(1, GROUP_HEIGHT if index.data(KEY_ROLE) else ROW_HEIGHT)

    def paint(self, p: QPainter, option, index: QModelIndex) -> None:
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if index.data(KEY_ROLE):
            self._paint_group(p, option, index)
        else:
            self._paint_station(p, option, index)
        p.restore()

    def _paint_group(self, p: QPainter, option, index: QModelIndex) -> None:
        t, rect = self.theme, option.rect
        name = "chev" if self.parent().isExpanded(index) else "chevR"
        left = rect.left() + _GROUP_PAD
        p.drawPixmap(left, rect.top() + (rect.height() - _CHEVRON) // 2, glyph_pixmap(name, t.mute, _CHEVRON))
        left += _CHEVRON + _GROUP_GAP
        right = rect.right() - _GROUP_PAD
        font = QFont(option.font)
        font.setPixelSize(12)
        p.setFont(font)
        p.setPen(QColor(t.mute))
        count = str(index.data(ROLE_COUNT))
        count_width = p.fontMetrics().horizontalAdvance(count)
        p.drawText(QRect(right + 1 - count_width, rect.top(), count_width, rect.height()),
                   Qt.AlignRight | Qt.AlignVCenter, count)
        right -= count_width + _GAP
        font.setPixelSize(13)
        font.setWeight(QFont.Medium)
        p.setFont(font)
        p.setPen(index.data(Qt.ForegroundRole).color())
        self._title(p, QRect(left, rect.top(), max(0, right - left + 1), rect.height()), index)

    def _paint_station(self, p: QPainter, option, index: QModelIndex) -> None:
        t, rect = self.theme, option.rect
        current = bool(index.data(ROLE_CURRENT))
        highlighted = current or bool(option.state & QStyle.State_Selected)
        if highlighted:
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), _RADIUS, _RADIUS)
            p.fillPath(path, css_color(t.tint))
        mark = QRect(rect.left() + _PAD, rect.top(), _MARK_WIDTH, rect.height())
        right = rect.right() - _PAD
        if current:
            self._eq(p, mark, QColor(t.row_fg))
            right = self._paint_chip(p, option, rect) - _GAP
        left = mark.right() + 1 + _GAP
        p.setFont(self.title_font(option.font, current))
        p.setPen(QColor(t.row_fg if highlighted else t.ink))
        self._title(p, QRect(left, rect.top(), max(0, right - left + 1), rect.height()), index)

    def _paint_chip(self, p: QPainter, option, rect: QRect) -> int:
        """줄 오른쪽 끝의 LIVE 칩을 그리고 칩의 왼쪽 끝을 돌려준다."""
        t = self.theme
        font = QFont(option.font)
        font.setPixelSize(10)
        font.setBold(True)
        metrics = QFontMetrics(font)
        width = metrics.horizontalAdvance(LIVE_CHIP) + 2 * _CHIP_PAD
        height = metrics.height() + 2
        chip = QRect(rect.right() + 1 - _PAD - width, rect.top() + (rect.height() - height) // 2, width, height)
        path = QPainterPath()
        path.addRoundedRect(QRectF(chip), _CHIP_RADIUS, _CHIP_RADIUS)
        p.fillPath(path, css_color(t.acc))
        p.setFont(font)
        p.setPen(QColor(t.on_acc))
        p.drawText(chip, Qt.AlignCenter, LIVE_CHIP)
        return chip.left()

    @staticmethod
    def _title(p: QPainter, box: QRect, index: QModelIndex) -> None:
        text = p.fontMetrics().elidedText(index.data(ROLE_TITLE) or "", Qt.ElideRight, box.width())
        p.drawText(box, Qt.AlignLeft | Qt.AlignVCenter, text)


class StationView(QTreeWidget):
    """방송국 목록: 묶음(접고 펴기)과 방송 줄. 목록은 StationList가 갖고, 여기서는 고친 뒤 신호만 보낸다."""

    station_activated = pyqtSignal(str)
    changed = pyqtSignal()
    open_groups_changed = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._stations: StationList | None = None
        self._open: set[str] = set()
        self._playing: str | None = None
        self._building = False
        self._swallow_click = False
        self._delegate = StationDelegate(self)
        self.setItemDelegate(self._delegate)
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setIndentation(0)   # 펼침 표시와 들여쓰기는 줄 그리기가 맡는다
        self.setRootIsDecorated(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setExpandsOnDoubleClick(False)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.itemClicked.connect(self._clicked)
        self.itemExpanded.connect(lambda item: self._toggled(item, True))
        self.itemCollapsed.connect(lambda item: self._toggled(item, False))
        self.actions: dict[str, QAction] = {}
        self._make_context_menu()

    # --- 내용 ---

    def set_stations(self, stations: StationList, open_groups: list[str]) -> None:
        self._stations = stations
        self._open = set(open_groups)
        self._fill()

    def set_theme(self, theme: Theme) -> None:
        """줄 색을 테마에 맞춘다. 앨범 색은 곡마다 바뀌니 다시 채우지 않고 그 자리에서 칠한다
        (스크롤과 펼침이 그대로다). 목록 내용은 바뀌지 않으니 changed를 내지 않는다."""
        self._delegate.theme = theme
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            top.setForeground(0, self._group_brush(top.data(0, KEY_ROLE)))
        self.viewport().update()

    def _group_brush(self, key: str) -> QBrush:
        t = self._delegate.theme
        return QBrush(QColor(t.fav if key == "favorites" else t.ink))

    def rebuild(self) -> None:
        """목록이 바뀐 뒤 다시 그린다. 펼침과 현재 줄을 지키고 changed를 낸다."""
        self._fill()
        self.changed.emit()

    def count(self) -> int:
        return len(self._stations.visible()) if self._stations else 0

    def _fill(self) -> None:
        keep = self._current_id()
        self._building = True
        self.clear()
        if self._stations is not None:
            for key, title, members in self._stations.groups():
                top = QTreeWidgetItem([title])
                top.setData(0, KEY_ROLE, key)
                top.setData(0, ROLE_TITLE, title.removesuffix(f" ({len(members)})"))   # 수는 오른쪽에 따로
                top.setData(0, ROLE_COUNT, len(members))
                top.setFlags(Qt.ItemIsEnabled)
                top.setForeground(0, self._group_brush(key))
                self.addTopLevelItem(top)
                for s in members:
                    row = QTreeWidgetItem([s.name])
                    row.setData(0, Qt.UserRole, s.id)
                    row.setData(0, ROLE_TITLE, s.name)
                    row.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
                    top.addChild(row)
                    if s.id == self._playing:
                        self._mark(row, True)
                top.setExpanded(key in self._open)
        self._building = False
        if keep:
            item = self._find(keep)
            if item is not None:
                self.setCurrentItem(item)

    def _find(self, station_id: str) -> QTreeWidgetItem | None:
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).data(0, Qt.UserRole) == station_id:
                    return top.child(j)
        return None

    def _current_id(self) -> str | None:
        item = self.currentItem()
        return item.data(0, Qt.UserRole) if item is not None else None

    def _mark(self, row: QTreeWidgetItem, on: bool) -> None:
        row.setData(0, ROLE_CURRENT, on)

    def select(self, station_id: str) -> None:
        """그 방송 줄을 고르고(묶음이 접혀 있으면 펼쳐) 보이게 굴린다. 듣지는 않는다."""
        item = self._find(station_id)
        if item is None:
            return
        parent = item.parent()
        if parent is not None and not parent.isExpanded():
            parent.setExpanded(True)
        self.setCurrentItem(item)
        self.scrollToItem(item)

    def set_current(self, station_id: str | None) -> None:
        """재생 중인 방송 줄을 표시한다 (막대와 LIVE 칩). None이면 모두 뗀다."""
        self._playing = station_id
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            for j in range(top.childCount()):
                row = top.child(j)
                self._mark(row, row.data(0, Qt.UserRole) == station_id)

    # --- 누르기 ---

    def _clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._swallow_click:   # 두 번 누르기에서 시작이 두 번 되지 않게
            return
        sid = item.data(0, Qt.UserRole)
        if sid:
            self.station_activated.emit(sid)
        else:
            item.setExpanded(not item.isExpanded())

    def mousePressEvent(self, event) -> None:
        self._swallow_click = False
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        # 첫 클릭이 이미 처리했다. 두 번째 눌림과 뗌은 버린다.
        self._swallow_click = True
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            item = self.currentItem()
            if item is not None:
                sid = item.data(0, Qt.UserRole)
                if sid:
                    self.station_activated.emit(sid)
                else:
                    item.setExpanded(not item.isExpanded())
            return
        super().keyPressEvent(event)

    def _toggled(self, item: QTreeWidgetItem, opened: bool) -> None:
        if self._building:
            return
        key = item.data(0, KEY_ROLE)
        if not key:
            return
        (self._open.add if opened else self._open.discard)(key)
        self.open_groups_changed.emit(sorted(self._open))

    # --- 오른쪽 클릭 메뉴 ---

    def _make_context_menu(self) -> None:
        menu = QMenu(self)
        menu.setObjectName("themed")   # 패널 스타일시트의 메뉴 규칙을 받는다
        specs = [("play", "듣기", self._play_current),
                 ("favorite", "즐겨찾기", self._toggle_favorite),
                 ("rename", "이름 바꾸기…", self._rename_current),
                 ("remove", "지우기", self._remove_current),
                 None,
                 ("restore", "기본 방송 다시 보이기", self._restore)]
        for spec in specs:
            if spec is None:
                menu.addSeparator()
                continue
            key, text, slot = spec
            act = QAction(text, menu)
            act.triggered.connect(lambda _=False, f=slot: f())
            menu.addAction(act)
            self.actions[key] = act
        self.actions["favorite"].setCheckable(True)
        menu.aboutToShow.connect(self._update_actions)
        self.context_menu = menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def _show_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is not None and item.data(0, Qt.UserRole):
            self.setCurrentItem(item)
        self.context_menu.exec_(self.viewport().mapToGlobal(pos))

    def _update_actions(self) -> None:
        sid = self._current_id()
        for key in ("play", "favorite", "rename", "remove"):
            self.actions[key].setEnabled(bool(sid))
        self.actions["favorite"].setChecked(bool(sid and self._stations and self._stations.is_favorite(sid)))

    def _play_current(self) -> None:
        sid = self._current_id()
        if sid:
            self.station_activated.emit(sid)

    def _toggle_favorite(self) -> None:
        sid = self._current_id()
        if sid and self._stations:
            self._stations.set_favorite(sid, not self._stations.is_favorite(sid))
            self.rebuild()

    def _rename_current(self) -> None:
        sid = self._current_id()
        station = self._stations.get(sid) if sid and self._stations else None
        if station is None:
            return
        name = ask_name(self, station.name)
        if name is not None:
            self._stations.rename(sid, name)
            self.rebuild()

    def _remove_current(self) -> None:
        sid = self._current_id()
        if sid and self._stations:
            self._stations.remove(sid)
            self.rebuild()

    def _restore(self) -> None:
        if self._stations:
            self._stations.restore_builtins()
            self.rebuild()

    # --- 끌어 옮기기: 같은 묶음 안에서만 ---

    def mimeTypes(self) -> list[str]:
        return [STATION_MIME]

    def mimeData(self, items) -> QMimeData:
        md = QMimeData()
        md.setData(STATION_MIME, str(items[0].data(0, Qt.UserRole)).encode("utf-8"))
        return md

    def startDrag(self, supported_actions) -> None:
        items = self.selectedItems()
        if not items or not items[0].data(0, Qt.UserRole):
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(items))
        drag.exec_(Qt.MoveAction)   # 원래 줄은 지우지 않고 목록을 고친 뒤 다시 그린다

    @staticmethod
    def _dragged_id(md) -> str | None:
        if not md.hasFormat(STATION_MIME):
            return None
        return bytes(md.data(STATION_MIME)).decode("utf-8")

    def dragEnterEvent(self, event) -> None:
        if self._dragged_id(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._dragged_id(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        sid = self._dragged_id(event.mimeData())
        event.setDropAction(Qt.IgnoreAction)
        super().dropEvent(event)
        src = self._find(sid) if sid else None
        target = self.itemAt(event.pos())
        if src is None or target is None or self._stations is None:
            return
        parent = src.parent()
        if target is parent or target.parent() is not parent:
            return   # 다른 묶음이나 묶음 줄 위는 무시
        if target is src:
            return
        if event.pos().y() < self.visualItemRect(target).center().y():
            before = target
        else:
            nxt = parent.indexOfChild(target) + 1
            before = parent.child(nxt) if nxt < parent.childCount() else None
        before_id = before.data(0, Qt.UserRole) if before is not None else None
        if before_id == sid:
            return
        self._stations.move(sid, before_id)
        self.rebuild()
