from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMenu, QPushButton, QShortcut, QSizePolicy, QStyle, QToolButton, QVBoxLayout, QWidget,
)

from funplayer.controller import PlayerController
from funplayer.core.settings import Settings
from funplayer.core.tracks import SUPPORTED_EXTS
from funplayer.core.timefmt import format_time
from funplayer.engine.player import AudioPlayer, State
from funplayer.ui.bridge import PlayerBridge
from funplayer.ui.jump_slider import JumpSlider

REFRESH_MS = 200
VOLUME_STEP = 5

SHORTCUTS: list[tuple[str, str]] = [
    ("Space", "toggle"), ("X", "toggle"), ("V", "stop"), ("Z", "prev"), ("B", "next"),
    ("Left", "seek_back"), ("Right", "seek_forward"), ("Up", "volume_up"),
    ("Down", "volume_down"), ("M", "toggle_mute"), ("L", "open_files"),
]


class PlayerPanel(QWidget):
    def __init__(self, settings: Settings, player=None, parent=None) -> None:
        super().__init__(parent)
        self._player = player if player is not None else AudioPlayer()
        self.controller = PlayerController(self._player, settings)
        self._dragging = False
        self._list_version = -1

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
        self.mute_button = self._tool(QStyle.SP_MediaVolume, "음소거")
        self.volume_slider = JumpSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(90)
        for w in (self.prev_button, self.play_button, self.stop_button, self.next_button):
            ctl.addWidget(w)
        ctl.addStretch(1)
        ctl.addWidget(self.mute_button)
        ctl.addWidget(self.volume_slider)
        root.addLayout(ctl)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        self.playlist_view = QListWidget()
        root.addWidget(self.playlist_view, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        self.open_button = QPushButton("열기")
        self.add_button = QPushButton("추가")
        self.clear_button = QPushButton("비우기")
        self.count_label = QLabel("0곡")
        bottom.addWidget(self.open_button)
        bottom.addWidget(self.add_button)
        bottom.addWidget(self.clear_button)
        bottom.addStretch(1)
        bottom.addWidget(self.count_label)
        root.addLayout(bottom)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #B3261E;")
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
        self.clear_button.clicked.connect(self._clear)

        self._open_menu = self._make_menu(self.open_button, self.open_files, self.open_folder)
        self._add_menu = self._make_menu(self.add_button, self.add_files, self.add_folder)

        self.volume_slider.valueChanged.connect(c.set_volume)
        self.seek_slider.sliderPressed.connect(self._seek_pressed)
        self.seek_slider.sliderMoved.connect(self._seek_moved)
        self.seek_slider.sliderReleased.connect(self._seek_released)
        self.playlist_view.itemDoubleClicked.connect(self._item_double_clicked)

        self.shortcuts: dict[str, QShortcut] = {}
        for key, name in SHORTCUTS:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(getattr(self, name))
            self.shortcuts[key] = sc

    def _make_menu(self, button: QPushButton, files_slot, folder_slot) -> QMenu:
        menu = QMenu(button)
        a_files = QAction("파일…", menu)
        a_files.triggered.connect(lambda _=False: files_slot())
        a_folder = QAction("폴더…", menu)
        a_folder.triggered.connect(lambda _=False: folder_slot())
        menu.addAction(a_files)
        menu.addAction(a_folder)
        button.setMenu(menu)
        return menu

    # ---- 입력 ----

    def _clear(self) -> None:
        self.controller.clear()
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

        if c.playlist.version != self._list_version:
            self._rebuild_list()
            self._list_version = c.playlist.version

        self.count_label.setText(f"{len(c.playlist)}곡")
        self._set_elided(self.status_label, c.status)

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
            mark = "▶" if i == pl.index else "  "
            item = QListWidgetItem(f"{mark} {i + 1:>2}   {track.title}")
            if i == pl.index:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            if track.failed:
                item.setForeground(QColor(Qt.gray))
            view.addItem(item)
        view.doItemsLayout()
        bar.setValue(scroll)
        view.setUpdatesEnabled(True)

    # ---- 끝내기 ----

    def shutdown(self) -> None:
        self._timer.stop()
        self._player.close()
