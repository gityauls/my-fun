from __future__ import annotations

from PyQt5.QtCore import QMimeData, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QDrag
from PyQt5.QtWidgets import (QAbstractItemView, QAction, QInputDialog, QMenu,
                             QTreeWidget, QTreeWidgetItem)

from funplayer.core.stations import StationList
from funplayer.core.themes import Theme
from funplayer.ui.colors import INFO_COLOR

STATION_MIME = "application/x-myfun-station"
FAVORITES_COLOR = "#E3A008"
KEY_ROLE = Qt.UserRole + 1   # 묶음 줄의 묶음 키


def ask_name(parent, current: str) -> str | None:
    """이름 바꾸기 입력창. 취소하면 None. 테스트가 이 함수를 바꿔 끼운다."""
    text, ok = QInputDialog.getText(parent, "이름 바꾸기", "이름", text=current)
    return text if ok else None


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
        self._group_color = INFO_COLOR
        self._fav_color = FAVORITES_COLOR
        self.setColumnCount(2)
        self.setHeaderHidden(True)
        self.setIndentation(14)
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
        """묶음 글자색을 테마에 맞춘다. 목록 내용은 바뀌지 않으니 changed를 내지 않는다."""
        self._group_color, self._fav_color = theme.mute, theme.fav
        self._fill()

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
            gray = QBrush(QColor(self._group_color))
            for key, title, members in self._stations.groups():
                top = QTreeWidgetItem([title])
                top.setData(0, KEY_ROLE, key)
                top.setFlags(Qt.ItemIsEnabled)
                font = top.font(0)
                font.setBold(True)
                top.setFont(0, font)
                top.setForeground(0, QBrush(QColor(self._fav_color)) if key == "favorites" else gray)
                self.addTopLevelItem(top)
                for s in members:
                    row = QTreeWidgetItem([s.name, s.source])
                    row.setData(0, Qt.UserRole, s.id)
                    row.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
                    row.setForeground(1, gray)
                    top.addChild(row)
                    if s.id == self._playing:
                        self._mark(row, True)
                top.setExpanded(key in self._open)
            self.resizeColumnToContents(1)
            self.header().setStretchLastSection(False)
            self.header().setSectionResizeMode(0, self.header().Stretch)
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
        text = row.text(0)
        if on and not text.startswith("▶ "):
            row.setText(0, "▶ " + text)
        elif not on and text.startswith("▶ "):
            row.setText(0, text[2:])
        font = row.font(0)
        font.setBold(on)
        row.setFont(0, font)

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
        """재생 중인 방송 줄에 ▶와 굵은 글씨를 붙인다. None이면 모두 뗀다."""
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
