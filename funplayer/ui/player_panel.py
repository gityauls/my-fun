from __future__ import annotations

from PyQt5.QtCore import QItemSelectionModel, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QKeySequence, QPalette
from PyQt5.QtWidgets import (
    QAction, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidgetItem,
    QMenu, QPushButton, QShortcut, QSizePolicy, QStyle, QToolButton, QVBoxLayout, QWidget,
)

from funplayer.controller import PlayerController
from funplayer.core.settings import Settings
from funplayer.core.tracks import SUPPORTED_EXTS
from funplayer.core.timefmt import format_time
from funplayer.engine.player import AudioPlayer, State
from funplayer.ui.bridge import PlayerBridge
from funplayer.ui.icons import OFF_COLOR, repeat_icon, shuffle_icon
from funplayer.ui.jump_slider import JumpSlider
from funplayer.ui.playlist_view import PlaylistView

REFRESH_MS = 200
VOLUME_STEP = 5
ERROR_COLOR = "#B3261E"
INFO_COLOR = "#5F6368"
REPEAT_TIPS = {"off": "반복: 끔", "all": "반복: 전체", "one": "반복: 한 곡"}
SHUFFLE_TIPS = {False: "무작위: 끔", True: "무작위: 켬"}

SHORTCUTS: list[tuple[str, str]] = [
    ("Space", "toggle"), ("X", "toggle"), ("V", "stop"), ("Z", "prev"), ("B", "next"),
    ("Left", "seek_back"), ("Right", "seek_forward"), ("Up", "volume_up"),
    ("Down", "volume_down"), ("M", "toggle_mute"), ("L", "open_files"),
    ("R", "cycle_repeat"), ("S", "toggle_shuffle"),
    ("Delete", "remove_selected"), ("Return", "play_selected"), ("Enter", "play_selected"),
    ("Ctrl+A", "select_all"), ("Ctrl+S", "save_playlist"), ("Ctrl+O", "open_playlist"),
]


class PlayerPanel(QWidget):
    def __init__(self, settings: Settings, player=None, parent=None) -> None:
        super().__init__(parent)
        self._player = player if player is not None else AudioPlayer()
        self.controller = PlayerController(self._player, settings)
        self._dragging = False
        self._list_version = -1
        self._layout_version = -1
        self.actions: dict[str, QAction] = {}
        self._icon_key: tuple[str, bool] | None = None
        self._status_error: bool | None = None

        self._bridge = PlayerBridge(self._player, self)
        self._bridge.ended.connect(self._on_ended, Qt.QueuedConnection)
        self._bridge.error.connect(self._on_error, Qt.QueuedConnection)

        self._build()
        self._wire()
        self.setAcceptDrops(True)

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    # ---- 만들기 ----

    def _tool(self, icon, tip: str = "", size: int = 28, icon_size: int = 18) -> QToolButton:
        b = QToolButton()
        b.setIcon(self.style().standardIcon(icon))
        b.setIconSize(QSize(icon_size, icon_size))
        b.setFixedSize(size, size)
        b.setAutoRaise(False)
        if tip:
            b.setToolTip(tip)
        return b

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(6)

        self.title_label = QLabel()
        font = self.title_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.title_label.setMinimumWidth(0)
        root.addWidget(self.title_label)

        row = QHBoxLayout()
        self.elapsed_label = QLabel("0:00")
        self.total_label = QLabel("0:00")
        self.seek_slider = JumpSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        row.addWidget(self.elapsed_label)
        row.addWidget(self.seek_slider, 1)
        row.addWidget(self.total_label)
        root.addLayout(row)

        ctl = QHBoxLayout()
        ctl.setSpacing(4)
        self.prev_button = self._tool(QStyle.SP_MediaSkipBackward, "이전 곡")
        self.play_button = self._tool(QStyle.SP_MediaPlay, "재생", 34, 22)
        self.stop_button = self._tool(QStyle.SP_MediaStop, "정지")
        self.next_button = self._tool(QStyle.SP_MediaSkipForward, "다음 곡")
        self.repeat_button = self._tool(QStyle.SP_MediaPlay)
        self.shuffle_button = self._tool(QStyle.SP_MediaPlay)
        for b in (self.repeat_button, self.shuffle_button):
            b.setCheckable(True)
        self.mute_button = self._tool(QStyle.SP_MediaVolume, "음소거")
        self.volume_slider = JumpSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(90)
        for w in (self.prev_button, self.play_button, self.stop_button, self.next_button):
            ctl.addWidget(w)
        ctl.addSpacing(8)
        ctl.addWidget(self.repeat_button)
        ctl.addWidget(self.shuffle_button)
        ctl.addStretch(1)
        ctl.addWidget(self.mute_button)
        ctl.addWidget(self.volume_slider)
        root.addLayout(ctl)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        self.playlist_view = PlaylistView()
        root.addWidget(self.playlist_view, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        self.open_button = QPushButton("열기")
        self.add_button = QPushButton("추가")
        self.list_button = QPushButton("목록")
        self.count_label = QLabel("0곡")
        bottom.addWidget(self.open_button)
        bottom.addWidget(self.add_button)
        bottom.addWidget(self.list_button)
        bottom.addStretch(1)
        bottom.addWidget(self.count_label)
        root.addLayout(bottom)

        self.status_label = QLabel()
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.status_label.setMinimumWidth(0)
        root.addWidget(self.status_label)

    def _wire(self) -> None:
        c = self.controller
        self.prev_button.clicked.connect(self.prev)
        self.play_button.clicked.connect(self.toggle)
        self.stop_button.clicked.connect(self.stop)
        self.next_button.clicked.connect(self.next)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.repeat_button.clicked.connect(self.cycle_repeat)
        self.shuffle_button.clicked.connect(self.toggle_shuffle)

        self.volume_slider.valueChanged.connect(c.set_volume)
        self.seek_slider.sliderPressed.connect(self._seek_pressed)
        self.seek_slider.sliderMoved.connect(self._seek_moved)
        self.seek_slider.sliderReleased.connect(self._seek_released)
        self.playlist_view.itemDoubleClicked.connect(self._item_double_clicked)
        self.playlist_view.rowsMoved.connect(self._rows_moved)
        self.playlist_view.filesDropped.connect(self._files_dropped)
        self._make_context_menu()
        self._open_menu = self._make_menu(self.open_button, [
            ("파일…	L", self.open_files), ("폴더…", self.open_folder),
            ("재생목록…	Ctrl+O", self.open_playlist)])
        self._add_menu = self._make_menu(self.add_button, [
            ("파일…", self.add_files), ("폴더…", self.add_folder),
            ("재생목록…", self.add_playlist)])
        self._make_list_menu()

        self.shortcuts: dict[str, QShortcut] = {}
        for key, name in SHORTCUTS:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(getattr(self, name))
            self.shortcuts[key] = sc

    def _make_context_menu(self) -> None:
        menu = QMenu(self)
        specs = [("play_selected", "재생\tEnter", self.play_selected),
                 ("remove", "선택한 곡 지우기\tDel", self.remove_selected),
                 None,
                 ("select_all", "전체 선택\tCtrl+A", self.select_all)]
        for spec in specs:
            if spec is None:
                menu.addSeparator()
                continue
            key, text, slot = spec
            act = QAction(text, menu)
            act.triggered.connect(lambda _=False, f=slot: f())
            menu.addAction(act)
            self.actions[key] = act
        menu.aboutToShow.connect(self._update_actions)
        self.context_menu = menu
        view = self.playlist_view
        view.setContextMenuPolicy(Qt.CustomContextMenu)
        view.customContextMenuRequested.connect(
            lambda pos: self.context_menu.exec_(view.viewport().mapToGlobal(pos)))

    def _add_action(self, menu: QMenu, key: str, text: str, slot) -> QAction:
        act = QAction(text, menu)
        act.triggered.connect(lambda _=False, f=slot: f())
        menu.addAction(act)
        self.actions[key] = act
        return act

    def _make_list_menu(self) -> None:
        menu = self.list_menu = QMenu(self.list_button)
        self._add_action(menu, "save", "저장…	Ctrl+S", self.save_playlist)
        menu.addSeparator()
        menu.addAction(self.actions["remove"])
        self._add_action(menu, "dedupe", "중복 곡 지우기", self.remove_duplicates)
        self._add_action(menu, "remove_unplayable", "없는·깨진 파일 지우기", self.remove_unplayable)
        sort_menu = menu.addMenu("정렬")
        self._add_action(sort_menu, "sort_name", "이름순", lambda: self.sort_by("name"))
        self._add_action(sort_menu, "sort_path", "폴더·이름순", lambda: self.sort_by("path"))
        menu.addSeparator()
        self._add_action(menu, "clear", "목록 비우기", self.clear_list)
        menu.aboutToShow.connect(self._update_actions)
        self.list_button.setMenu(menu)

    def _update_actions(self) -> None:
        self.actions["remove"].setEnabled(bool(self.selected_rows()))
        self.actions["play_selected"].setEnabled(self.playlist_view.currentRow() >= 0)
        has_tracks = len(self.controller.playlist) > 0
        for key in ("save", "dedupe", "remove_unplayable", "sort_name", "sort_path", "clear"):
            self.actions[key].setEnabled(has_tracks)

    def _make_menu(self, button: QPushButton, items: list[tuple[str, object]]) -> QMenu:
        menu = QMenu(button)
        for text, slot in items:
            act = QAction(text, menu)
            act.triggered.connect(lambda _=False, f=slot: f())
            menu.addAction(act)
        button.setMenu(menu)
        return menu

    # ---- 입력 ----

    def clear_list(self) -> None:
        self.controller.clear()
        self.refresh()

    def remove_duplicates(self) -> None:
        self.controller.remove_duplicates()
        self.refresh()

    def remove_unplayable(self) -> None:
        self.controller.remove_unplayable()
        self.refresh()

    def sort_by(self, by: str) -> None:
        self.controller.sort(by)
        self.refresh()

    def ask_playlist_open(self) -> str:
        return QFileDialog.getOpenFileName(
            self, "재생목록 열기", "", "재생목록 (*.m3u8 *.m3u)")[0]

    def ask_playlist_save(self) -> str:
        return QFileDialog.getSaveFileName(
            self, "재생목록 저장", "재생목록.m3u8", "재생목록 (*.m3u8)")[0]

    def open_playlist(self) -> None:
        path = self.ask_playlist_open()
        if path:
            self._load([path], self.controller.open)

    def add_playlist(self) -> None:
        path = self.ask_playlist_open()
        if path:
            self._load([path], self.controller.add)

    def save_playlist(self) -> None:
        if len(self.controller.playlist) == 0:
            return
        path = self.ask_playlist_save()
        if path:
            self.controller.save_playlist(path)
            self.refresh()

    def _seek_pressed(self) -> None:
        self._dragging = True

    def _seek_moved(self, value: int) -> None:
        self.elapsed_label.setText(format_time(value / 1000))

    def _seek_released(self) -> None:
        self.controller.seek_to(self.seek_slider.value() / 1000)
        self._dragging = False
        self.refresh()

    def _item_double_clicked(self, item: QListWidgetItem) -> None:
        self.controller.play_index(self.playlist_view.row(item))
        self.refresh()

    def _rows_moved(self, rows: list[int], before: int) -> None:
        new = self.controller.move(rows, before)
        self.refresh()
        self.select_rows(new)

    def _files_dropped(self, paths: list[str]) -> None:
        self.controller.add(paths)
        self.refresh()

    def selected_rows(self) -> list[int]:
        return sorted(self.playlist_view.row(i) for i in self.playlist_view.selectedItems())

    def select_rows(self, rows: list[int]) -> None:
        view = self.playlist_view
        view.clearSelection()
        if not rows:
            return
        view.setCurrentRow(rows[0], QItemSelectionModel.NoUpdate)
        for r in rows:
            item = view.item(r)
            if item is not None:
                item.setSelected(True)

    def remove_selected(self) -> None:
        rows = self.selected_rows()
        if not rows:
            return
        self.controller.remove(rows)
        self.refresh()
        count = self.playlist_view.count()
        if count:
            self.select_rows([min(rows[0], count - 1)])

    def play_selected(self) -> None:
        row = self.playlist_view.currentRow()
        if row >= 0:
            self.controller.play_index(row)
            self.refresh()

    def select_all(self) -> None:
        self.playlist_view.selectAll()

    def toggle(self) -> None:
        self.controller.toggle()
        self.refresh()

    def stop(self) -> None:
        self.controller.stop()
        self.refresh()

    def prev(self) -> None:
        self.controller.prev()
        self.refresh()

    def next(self) -> None:
        self.controller.next()
        self.refresh()

    def seek_back(self) -> None:
        self.controller.seek_by(-1)
        self.refresh()

    def seek_forward(self) -> None:
        self.controller.seek_by(1)
        self.refresh()

    def volume_up(self) -> None:
        self.controller.set_volume(self.controller.volume + VOLUME_STEP)
        self.refresh()

    def volume_down(self) -> None:
        self.controller.set_volume(self.controller.volume - VOLUME_STEP)
        self.refresh()

    def toggle_mute(self) -> None:
        self.controller.toggle_mute()
        self.refresh()

    def cycle_repeat(self) -> None:
        self.controller.cycle_repeat()
        self.refresh()

    def toggle_shuffle(self) -> None:
        self.controller.toggle_shuffle()
        self.refresh()

    def ask_files(self) -> list[str]:
        exts = " ".join("*" + e for e in sorted(SUPPORTED_EXTS))
        paths, _ = QFileDialog.getOpenFileNames(self, "파일 열기", "", f"음악 파일 ({exts})")
        return list(paths)

    def ask_folder(self) -> list[str]:
        path = QFileDialog.getExistingDirectory(self, "폴더 선택")
        return [path] if path else []

    def open_files(self) -> None:
        self._load(self.ask_files(), self.controller.open)

    def open_folder(self) -> None:
        self._load(self.ask_folder(), self.controller.open)

    def add_files(self) -> None:
        self._load(self.ask_files(), self.controller.add)

    def add_folder(self) -> None:
        self._load(self.ask_folder(), self.controller.add)

    def _load(self, paths: list[str], action) -> None:
        if not paths:
            return
        action(paths)
        self.refresh()

    # ---- 끌어다 놓기 ----

    @staticmethod
    def _local_paths(mime) -> list[str]:
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]

    def dragEnterEvent(self, event) -> None:
        if self._local_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = self._local_paths(event.mimeData())
        if not paths:
            event.ignore()
            return
        self.controller.add(paths)
        self.refresh()
        event.acceptProposedAction()

    # ---- 엔진 알림 ----

    def _on_ended(self) -> None:
        self.controller.on_track_end()
        self.refresh()

    def _on_error(self, msg: str) -> None:
        self.controller.on_player_error(msg)
        self.refresh()

    # ---- 갱신 ----

    def refresh(self) -> None:
        c = self.controller
        st = self.style()
        state = c.state
        duration = c.duration
        position = c.position

        self._set_elided(self.title_label, c.title)
        shown = self.seek_slider.value() / 1000 if self._dragging else position
        self.elapsed_label.setText(format_time(shown))
        self.total_label.setText(format_time(duration))

        seek = self.seek_slider
        seek.setRange(0, int(duration * 1000))
        if not self._dragging:
            seek.setValue(int(position * 1000))
        seek.setEnabled(state is not State.STOPPED and duration > 0)

        if state is State.PLAYING:
            self.play_button.setIcon(st.standardIcon(QStyle.SP_MediaPause))
            self.play_button.setToolTip("일시정지")
        else:
            self.play_button.setIcon(st.standardIcon(QStyle.SP_MediaPlay))
            self.play_button.setToolTip("재생")

        if c.muted:
            self.mute_button.setIcon(st.standardIcon(QStyle.SP_MediaVolumeMuted))
            self.mute_button.setToolTip("음소거 해제")
        else:
            self.mute_button.setIcon(st.standardIcon(QStyle.SP_MediaVolume))
            self.mute_button.setToolTip("음소거")

        if self.volume_slider.value() != c.volume:
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(c.volume)
            self.volume_slider.blockSignals(False)

        pl = c.playlist
        if pl.layout_version != self._layout_version or self.playlist_view.count() != len(pl):
            self._rebuild_list()
            self._layout_version = pl.layout_version
            self._list_version = pl.version
        elif pl.version != self._list_version:
            self._repaint_rows()
            self._list_version = pl.version

        self._refresh_modes()
        self.count_label.setText(f"{len(c.playlist)}곡")
        if c.status_error != self._status_error:
            self._status_error = c.status_error
            color = ERROR_COLOR if c.status_error else INFO_COLOR
            self.status_label.setStyleSheet(f"color: {color};")
        self._set_elided(self.status_label, c.status)

    def _refresh_modes(self) -> None:
        c = self.controller
        mode, shuffle = c.repeat, c.shuffle
        self.repeat_button.setChecked(mode != "off")
        self.shuffle_button.setChecked(shuffle)
        self.repeat_button.setToolTip(REPEAT_TIPS[mode])
        self.shuffle_button.setToolTip(SHUFFLE_TIPS[shuffle])
        if (mode, shuffle) != self._icon_key:
            self._icon_key = (mode, shuffle)
            on = self.palette().color(QPalette.Highlight)
            self.repeat_button.setIcon(repeat_icon(mode, OFF_COLOR if mode == "off" else on))
            self.shuffle_button.setIcon(shuffle_icon(on if shuffle else OFF_COLOR))

    @staticmethod
    def _set_elided(label: QLabel, text: str) -> None:
        label.setToolTip(text)
        if label.isVisible():
            label.setText(label.fontMetrics().elidedText(text, Qt.ElideRight, label.width()))
        else:
            label.setText(text)

    def _rebuild_list(self) -> None:
        pl = self.controller.playlist
        view = self.playlist_view
        bar = view.verticalScrollBar()
        scroll = bar.value()
        view.setUpdatesEnabled(False)
        view.clear()
        for i, track in enumerate(pl.tracks):
            item = QListWidgetItem()
            self._style_item(item, i, track, i == pl.index)
            view.addItem(item)
        view.doItemsLayout()
        bar.setValue(scroll)
        view.setUpdatesEnabled(True)

    def _repaint_rows(self) -> None:
        pl = self.controller.playlist
        for i, track in enumerate(pl.tracks):
            item = self.playlist_view.item(i)
            if item is not None:
                self._style_item(item, i, track, i == pl.index)

    @staticmethod
    def _style_item(item: QListWidgetItem, i: int, track, current: bool) -> None:
        mark = "▶" if current else "  "
        item.setText(f"{mark} {i + 1:>2}   {track.title}")
        font = item.font()
        font.setBold(current)
        item.setFont(font)
        item.setData(Qt.ForegroundRole, QColor(Qt.gray) if track.failed else None)

    # ---- 끝내기 ----

    def shutdown(self) -> None:
        self._timer.stop()
        self._player.close()
