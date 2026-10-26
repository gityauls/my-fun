from __future__ import annotations

import time

from PyQt5.QtCore import QEvent, QItemSelectionModel, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QKeySequence, QPalette
from PyQt5.QtWidgets import (
    QAction, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidgetItem,
    QMenu, QPushButton, QShortcut, QSizePolicy, QStyle, QTabBar, QToolButton, QVBoxLayout, QWidget,
)

from funplayer.controller import PlayerController
from funplayer.core.settings import Settings
from funplayer.core.stations import StationList, load_stations, save_stations
from funplayer.core.taginfo import TrackInfo
from funplayer.core.tracks import SUPPORTED_EXTS
from funplayer.core.timefmt import format_time
from funplayer.engine.player import AudioPlayer, State
from funplayer.radio import DUP_STATION_MSG, RadioController, RadioState
from funplayer.ui.bridge import PlayerBridge
from funplayer.ui.colors import ERROR_COLOR, INFO_COLOR
from funplayer.ui.cover import art_pixmap, load_cover
from funplayer.ui.icons import OFF_COLOR, full_icon, mini_icon, radio_art, repeat_icon, shuffle_icon
from funplayer.ui.info_dialog import ART_SIZE as INFO_ART_SIZE, TrackInfoDialog
from funplayer.ui.jump_slider import JumpSlider
from funplayer.ui.media_keys import MEDIA_KEYS_BUSY_MSG, MediaKeys
from funplayer.ui.playlist_view import PlaylistView
from funplayer.ui.radio_dialogs import AddUrlDialog
from funplayer.ui.station_view import StationView
from funplayer.ui.worker import QtRunner

REFRESH_MS = 200
VOLUME_STEP = 5
REPEAT_TIPS = {"off": "반복: 끔", "all": "반복: 전체", "one": "반복: 한 곡"}
SHUFFLE_TIPS = {False: "무작위: 끔", True: "무작위: 켬"}
ART_NORMAL = 56
ART_MINI = 40
TABS = ("playlist", "radio")
TAB_TITLES = ("재생목록", "라디오")
LIVE_TEXT = "● LIVE"
LIVE_COLOR = "#C5221F"
LISTENED_PREFIX = "들은 시간 "
DOMESTIC_INFO_PATH = "방송사 웹 재생 주소 (들을 때마다 새로 받음)"

SHORTCUTS: list[tuple[str, str]] = [
    ("Space", "toggle"), ("X", "toggle"), ("V", "stop"), ("Z", "prev"), ("B", "next"),
    ("Left", "seek_back"), ("Right", "seek_forward"), ("Up", "volume_up"),
    ("Down", "volume_down"), ("M", "toggle_mute"), ("L", "open_files"),
    ("R", "cycle_repeat"), ("S", "toggle_shuffle"),
    ("Delete", "remove_selected"), ("Return", "play_selected"), ("Enter", "play_selected"),
    ("Ctrl+A", "select_all"), ("Ctrl+S", "save_playlist"), ("Ctrl+O", "open_playlist"),
    ("Ctrl+I", "show_track_info"), ("Ctrl+M", "toggle_mini"), ("Ctrl+Tab", "next_tab"),
    ("Ctrl+Left", "prev"), ("Ctrl+Right", "next"),
]

# 작게 볼 때 숨기는 위젯 (이름). 탭·라디오에 따라 바뀌는 위젯은 _apply_visibility가 맡는다
HIDDEN_IN_MINI = (
    "elapsed_label", "total_label", "stop_button", "repeat_button", "shuffle_button",
    "mute_button", "volume_slider", "separator", "playlist_view", "open_button",
    "add_button", "list_button", "view_button", "count_label", "status_label",
)


class _ArtLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PlayerPanel(QWidget):
    miniChanged = pyqtSignal(bool)
    miniOnTopChanged = pyqtSignal(bool)

    def __init__(self, settings: Settings, player=None, parent=None, *,
                 session_path: str | None = None, read_info=None, media_keys=None,
                 stations_path: str | None = None, runner=None) -> None:
        super().__init__(parent)
        self._player = player if player is not None else AudioPlayer()
        self.controller = PlayerController(
            self._player, settings, session_path=session_path, read_info=read_info)
        # 라디오: 경로가 없으면(테스트) 저장하지 않는 메모리 목록이다
        self._stations_path = stations_path
        self.stations = load_stations(stations_path) if stations_path else StationList()
        self.runner = runner if runner is not None else QtRunner(self)
        self.radio = RadioController(
            self._player, self.stations, self.runner.run_async, self.runner.call_later,
            time.monotonic, notify=self.controller.radio_notify)
        self.controller.attach_radio(self.radio)
        self._tab = "playlist"
        self._live_color: str | None = None
        self._marked_station: object = object()
        self._closed = False   # shutdown 뒤 큐에 남은 신호를 버린다
        self._cover_key: object = object()
        self._cover_src = None
        self._dragging = False
        self._list_version = -1
        self._layout_version = -1
        self.actions: dict[str, QAction] = {}
        self.info_dialog: TrackInfoDialog | None = None
        self._icon_key: tuple[str, bool] | None = None
        self._status_error: bool | None = None
        self._settings = settings
        self.settings = settings   # 공개 이름(같은 객체)
        self.is_mini = False   # settings.mini는 창(Task 10)이 적용한다

        self._bridge = PlayerBridge(self._player, self)
        self._bridge.ended.connect(self._on_ended, Qt.QueuedConnection)
        self._bridge.error.connect(self._on_error, Qt.QueuedConnection)
        self._bridge.lost.connect(self._on_lost, Qt.QueuedConnection)

        self.media_keys = media_keys if media_keys is not None else MediaKeys(self)
        self._build()
        self._wire()
        self.setAcceptDrops(True)

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        if session_path:
            self.controller.restore_session()
        # 라디오로 끈 뒤 켜면 라디오 탭이다 (방송국만 고르고 접속하지 않는다)
        self.set_tab("radio" if self.controller.source == "radio" else settings.tab)
        self.refresh()
        # 이어 듣기 안내가 떠 있으면 키 안내로 가리지 않는다 (시작할 때 상태 글은 그것뿐이다)
        if self._settings.media_keys and not self.media_keys.enable() and not self.controller.status:
            self.controller.notify(MEDIA_KEYS_BUSY_MSG)
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

        self.head_row = QHBoxLayout()
        self.head_row.setSpacing(10)
        self.art_label = _ArtLabel()
        self.art_label.setFixedSize(ART_NORMAL, ART_NORMAL)
        self.art_label.setToolTip("곡 정보")
        self.head_row.addWidget(self.art_label, 0, Qt.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.artist_label = QLabel()
        self.artist_label.setStyleSheet(f"color: {INFO_COLOR};")
        self.artist_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.artist_label.setMinimumWidth(0)
        titles.addWidget(self.title_label)
        titles.addWidget(self.artist_label)
        self.head_row.addLayout(titles, 1)
        self.mini_button = self._tool(QStyle.SP_MediaPlay, "작게 보기", 26, 18)
        self.mini_button.setIcon(mini_icon(OFF_COLOR))
        self.head_row.addWidget(self.mini_button, 0, Qt.AlignTop)
        root.addLayout(self.head_row)

        row = QHBoxLayout()
        self.elapsed_label = QLabel("0:00")
        self.total_label = QLabel("0:00")
        self.seek_slider = JumpSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        # 라디오일 때는 탐색 막대 대신 라이브 줄: 왼쪽 "● LIVE", 오른쪽 들은 시간
        self.live_label = QLabel(LIVE_TEXT)
        self.listened_label = QLabel(LISTENED_PREFIX + format_time(0))
        self.live_label.hide()
        self.listened_label.hide()
        row.addWidget(self.elapsed_label)
        row.addWidget(self.live_label)
        row.addWidget(self.seek_slider, 1)
        row.addWidget(self.listened_label, 1, Qt.AlignRight)
        row.addWidget(self.total_label)
        root.addLayout(row)

        ctl = self.control_row = QHBoxLayout()
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

        line = self.separator = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        self.tab_bar = QTabBar()
        for title in TAB_TITLES:
            self.tab_bar.addTab(title)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setDrawBase(False)
        root.addWidget(self.tab_bar)

        self.playlist_view = PlaylistView()
        root.addWidget(self.playlist_view, 1)
        self.station_view = StationView()
        self.station_view.set_stations(self.stations, self._settings.radio_open)
        self.station_view.hide()
        root.addWidget(self.station_view, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        self.open_button = QPushButton("열기")
        self.add_button = QPushButton("추가")
        self.list_button = QPushButton("목록")
        self.add_url_button = QPushButton("주소 넣기…")
        self.add_url_button.hide()
        self.view_button = QPushButton("보기")
        self.count_label = QLabel("0곡")
        for b in (self.open_button, self.add_button, self.list_button, self.add_url_button,
                  self.view_button):
            b.setSizePolicy(QSizePolicy.Preferred, b.sizePolicy().verticalPolicy())
        bottom.addWidget(self.open_button)
        bottom.addWidget(self.add_button)
        bottom.addWidget(self.list_button)
        bottom.addWidget(self.add_url_button)
        bottom.addWidget(self.view_button)
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
            ("파일…\tL", self.open_files), ("폴더…", self.open_folder),
            ("재생목록…\tCtrl+O", self.open_playlist)])
        self._add_menu = self._make_menu(self.add_button, [
            ("파일…", self.add_files), ("폴더…", self.add_folder),
            ("재생목록…", self.add_playlist)])
        self._make_list_menu()
        self._make_view_menu()
        for b in (self.open_button, self.add_button, self.list_button, self.add_url_button,
                  self.view_button):
            self._fit_min_width(b)
        self.tab_bar.currentChanged.connect(self._tab_changed)
        sv = self.station_view
        sv.station_activated.connect(self._play_station)
        sv.changed.connect(self._stations_changed)
        sv.open_groups_changed.connect(self._open_groups_changed)
        self.add_url_button.clicked.connect(self.add_url)
        self.art_label.clicked.connect(self.show_track_info)
        self.mini_button.clicked.connect(self.toggle_mini)
        self.title_label.installEventFilter(self)

        self.shortcuts: dict[str, QShortcut] = {}
        for key, name in SHORTCUTS:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(getattr(self, name))
            self.shortcuts[key] = sc

        k = self.media_keys
        # 미디어 ⏯는 창 밖에서도 눌리므로 보고 있는 탭이 아니라 지금 나오는 쪽을 따른다
        k.play_pause_pressed.connect(self.media_toggle)
        k.next_pressed.connect(self.next)
        k.prev_pressed.connect(self.prev)
        k.stop_pressed.connect(self.stop)
        self.media_shortcuts: list[QShortcut] = []
        for key, slot in ((Qt.Key_MediaTogglePlayPause, self.media_toggle),
                          (Qt.Key_MediaPlay, self.media_toggle),
                          (Qt.Key_MediaNext, self.next), (Qt.Key_MediaPrevious, self.prev),
                          (Qt.Key_MediaStop, self.stop)):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.setAutoRepeat(False)   # 누르고 있어도 한 번만
            sc.activated.connect(slot)
            self.media_shortcuts.append(sc)

    # 글자 크기에 맞춘 최소 폭 (스타일의 기본 최소폭 75~80px을 덮어쓴다)
    def _fit_min_width(self, button: QPushButton) -> None:
        st = self.style()
        w = button.fontMetrics().horizontalAdvance(button.text())
        if button.menu() is not None:
            w += st.pixelMetric(QStyle.PM_MenuButtonIndicator, None, button)
        w += 2 * st.pixelMetric(QStyle.PM_ButtonMargin, None, button) + 8
        button.setMinimumWidth(w)

    def _make_context_menu(self) -> None:
        menu = QMenu(self)
        specs = [("play_selected", "재생\tEnter", self.play_selected),
                 ("info_row", "곡 정보…", self.show_row_info),
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
        self._add_action(menu, "save", "재생목록 저장…\tCtrl+S", self.save_playlist)
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

    def _make_view_menu(self) -> None:
        menu = self.view_menu = QMenu(self.view_button)
        self._add_action(menu, "info", "곡 정보…\tCtrl+I", self.show_track_info)
        mini = self._add_action(menu, "mini", "작게 보기\tCtrl+M", self.toggle_mini)
        mini.setCheckable(True)
        mini.setChecked(self._settings.mini)
        menu.addSeparator()
        on_top = self._add_action(menu, "mini_on_top", "작게 볼 때 항상 위", self._mini_on_top_clicked)
        on_top.setCheckable(True)
        on_top.setChecked(self._settings.mini_on_top)
        keys = self._add_action(menu, "media_keys", "멀티미디어 키 사용", self._media_keys_clicked)
        keys.setCheckable(True)
        keys.setChecked(self._settings.media_keys)
        menu.aboutToShow.connect(self._update_actions)
        self.view_button.setMenu(menu)

    def _media_keys_clicked(self) -> None:
        self.set_media_keys(self.actions["media_keys"].isChecked())

    def set_media_keys(self, on: bool) -> None:
        on = bool(on)
        self._settings.media_keys = on
        if on:
            if not self.media_keys.enable():
                self.controller.notify(MEDIA_KEYS_BUSY_MSG)
        else:
            self.media_keys.disable()
            if self.controller.status == MEDIA_KEYS_BUSY_MSG:
                self.controller.notify("")
        self.refresh()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self._retry_media_keys()

    def _retry_media_keys(self) -> None:
        # 다른 프로그램(예: 동영상 재생 중인 Chrome)이 놓아 준 키를 창이 활성화될 때 조용히 다시 건다
        if self._settings.media_keys and not self.media_keys.complete:
            self.media_keys.enable()

    def _mini_on_top_clicked(self) -> None:
        checked = self.actions["mini_on_top"].isChecked()
        self._settings.mini_on_top = checked
        self.miniOnTopChanged.emit(checked)

    # ---- 작게 보기 ----

    def toggle_mini(self) -> None:
        self.set_mini(not self.is_mini)

    def set_mini(self, on: bool) -> None:
        on = bool(on)
        if on == self.is_mini:
            return
        self.is_mini = on
        movers = (self.prev_button, self.play_button, self.next_button)
        for w in movers:
            (self.control_row if on else self.head_row).removeWidget(w)
        if on:
            for w in movers:
                self.head_row.insertWidget(self.head_row.indexOf(self.mini_button), w, 0, Qt.AlignTop)
        else:
            for pos, w in zip((0, 1, 3), movers):
                self.control_row.insertWidget(pos, w)
        for name in HIDDEN_IN_MINI:
            getattr(self, name).setVisible(not on)
        self._apply_visibility()   # 탭·라디오에 따라 다시 숨길 것을 숨긴다
        size = ART_MINI if on else ART_NORMAL
        self.art_label.setFixedSize(size, size)
        if self.controller.source == "radio":
            self.art_label.setPixmap(radio_art(size))
        else:
            self.art_label.setPixmap(art_pixmap(self._cover_src, size))
        font = self.title_label.font()
        font.setPointSize(10 if on else 12)
        self.title_label.setFont(font)
        self.mini_button.setIcon((full_icon if on else mini_icon)(OFF_COLOR))
        self.mini_button.setToolTip("보통 보기" if on else "작게 보기")
        self.actions["mini"].setChecked(on)
        self._settings.mini = on
        self.miniChanged.emit(on)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.title_label and self.is_mini and event.type() == QEvent.MouseButtonDblClick:
            self.set_mini(False)
            return True
        return super().eventFilter(obj, event)

    def _update_actions(self) -> None:
        self.actions["remove"].setEnabled(bool(self.selected_rows()))
        row = self.playlist_view.currentRow()
        self.actions["play_selected"].setEnabled(row >= 0)
        self.actions["info_row"].setEnabled(row >= 0)
        self.actions["mini"].setChecked(self.is_mini)
        self.actions["mini_on_top"].setChecked(self._settings.mini_on_top)
        self.actions["media_keys"].setChecked(self._settings.media_keys)
        on_station = self.controller.source == "radio" and self.radio.current is not None
        self.actions["info"].setEnabled(
            on_station or self.controller.playlist.index is not None or row >= 0)
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

    # ---- 탭 ----

    @property
    def tab(self) -> str:
        return self._tab

    def set_tab(self, name: str) -> None:
        i = TABS.index(name) if name in TABS else 0
        if self.tab_bar.currentIndex() != i:
            self.tab_bar.setCurrentIndex(i)   # → _tab_changed
        else:
            self._tab_changed(i)

    def next_tab(self) -> None:
        self.set_tab("radio" if self._tab == "playlist" else "playlist")

    def _tab_changed(self, index: int) -> None:
        # 보이는 것만 바꾼다: 플레이어·라디오·작업 실행기는 부르지 않는다 (접속하지 않는다)
        self._tab = TABS[index] if 0 <= index < len(TABS) else "playlist"
        if self._settings.tab != self._tab:
            self._settings.tab = self._tab
        self._apply_visibility()
        self._update_count()

    def _apply_visibility(self) -> None:
        mini = self.is_mini
        radio_tab = self._tab == "radio"
        on_radio = self.controller.source == "radio"
        self.tab_bar.setVisible(not mini)
        self.playlist_view.setVisible(not mini and not radio_tab)
        self.station_view.setVisible(not mini and radio_tab)
        for b in (self.open_button, self.add_button, self.list_button):
            b.setVisible(not mini and not radio_tab)
        self.add_url_button.setVisible(not mini and radio_tab)
        # 탐색 줄: 라디오면 막대 대신 라이브 줄이고, 작게 볼 때는 줄 전체를 숨긴다
        self.seek_slider.setVisible(not on_radio)
        for w in (self.elapsed_label, self.total_label):
            w.setVisible(not mini and not on_radio)
        for w in (self.live_label, self.listened_label):
            w.setVisible(not mini and on_radio)

    def _update_count(self) -> None:
        if self._tab == "radio":
            self.count_label.setText(f"방송 {self.station_view.count()}개")
        else:
            self.count_label.setText(f"{len(self.controller.playlist)}곡")

    # ---- 라디오 ----

    def _play_station(self, station_id: str) -> None:
        self.controller.play_station(station_id)
        self.refresh()

    def _stations_changed(self) -> None:
        if self._stations_path:
            save_stations(self._stations_path, self.stations)
        self.radio.refresh_current()   # 듣는 방송 이름을 바꿨으면 제목도 따라 바뀐다
        self._update_count()

    def _open_groups_changed(self, keys: list) -> None:
        self._settings.radio_open = list(keys)

    def add_url(self) -> None:
        dialog = AddUrlDialog(self)
        try:
            value = dialog.result_value() if dialog.exec_() else None
        finally:
            dialog.deleteLater()
        if value is None:
            return
        station, added = self.stations.add_url(*value)
        self.station_view.rebuild()   # changed → 저장
        if not added:
            # 이미 있는 주소: 그 줄을 골라 보여 주고 안내만 한다 (접속하지 않는다)
            self.station_view.select(station.id)
            self.controller.notify(DUP_STATION_MSG)
            self.refresh()
            return
        self._play_station(station.id)

    def _on_lost(self) -> None:
        if self._closed:
            return
        self.radio.on_lost()
        self.refresh()

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
        if self._tab == "radio":   # 보이지 않는 재생목록 줄을 지우지 않게
            return
        rows = self.selected_rows()
        if not rows:
            return
        self.controller.remove(rows)
        self.refresh()
        count = self.playlist_view.count()
        if count:
            self.select_rows([min(rows[0], count - 1)])

    def play_selected(self) -> None:
        if self._tab == "radio":
            # Enter 단축키가 방송국 목록의 키 처리보다 먼저 받으므로 여기서 방송 줄을 듣는다
            item = self.station_view.currentItem()
            sid = item.data(0, Qt.UserRole) if item is not None else None
            if sid:
                self._play_station(sid)
            elif item is not None:
                item.setExpanded(not item.isExpanded())
            return
        row = self.playlist_view.currentRow()
        if row >= 0:
            self.controller.play_index(row)
            self.refresh()

    def show_track_info(self) -> None:
        if self.controller.source == "radio" and self.radio.current is not None:
            self._show_info(self._station_info(), radio_art(INFO_ART_SIZE))
            return
        i = self.controller.playlist.index
        if i is None:
            i = self.playlist_view.currentRow()
        if i is not None and i >= 0:
            self._show_info_for(i)

    def show_row_info(self) -> None:
        row = self.playlist_view.currentRow()
        if row >= 0:
            self._show_info_for(row)

    def _show_info_for(self, i: int) -> None:
        info = self.controller.info_for(i)
        self._show_info(info, load_cover(info))

    def _station_info(self) -> TrackInfo:
        # 형식 칸(codec·sample_rate·channels)은 디코더가 밖으로 내주지 않아 비워 둔다
        s = self.radio.current
        path = DOMESTIC_INFO_PATH if s.kind in ("kbs", "mbc") else s.key
        return TrackInfo(path=path, title=s.name, artist=s.source)

    def _show_info(self, info: TrackInfo, cover) -> None:
        if self.info_dialog is None:
            self.info_dialog = TrackInfoDialog(self)
        self.info_dialog.show_info(info, cover)
        self.info_dialog.show()
        self.info_dialog.raise_()
        self.info_dialog.activateWindow()

    def select_all(self) -> None:
        if self._tab == "playlist":
            self.playlist_view.selectAll()

    def toggle(self) -> None:
        """[재생] 단추·Space: 보이는 탭을 따른다. 작게 볼 때는 탭이 안 보이니 나오는 쪽을 따른다."""
        if self.is_mini:
            self.controller.toggle()
        else:
            self.controller.toggle_for_tab(self._tab)
        self.refresh()

    def media_toggle(self) -> None:
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
            event.setDropAction(Qt.CopyAction)   # Shift로 '이동'이 되어 원본이 지워지지 않게
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = self._local_paths(event.mimeData())
        if not paths:
            event.ignore()
            return
        self.controller.add(paths)
        self.refresh()
        event.setDropAction(Qt.CopyAction)
        event.accept()

    # ---- 엔진 알림 ----

    def _on_ended(self) -> None:
        if self._closed:
            return
        self.controller.on_track_end()
        self.refresh()

    def _on_error(self, msg: str) -> None:
        if self._closed:   # 끈 뒤 큐에 남아 있던 신호
            return
        self.controller.on_player_error(msg)
        self.refresh()

    # ---- 갱신 ----

    def refresh(self) -> None:
        c = self.controller
        st = self.style()
        state = c.state
        duration = c.duration
        position = c.position

        on_radio = c.source == "radio"
        self._apply_visibility()
        self._set_elided(self.title_label, c.title)
        self._set_elided(self.artist_label, c.subtitle)
        if on_radio:
            # 라디오 그림은 방송이 바뀔 때만 다시 그린다
            station = self.radio.current
            key = ("radio", station.id if station is not None else None)
            if key != self._cover_key:
                self._cover_key = key
                self._cover_src = None
                self.art_label.setPixmap(radio_art(self.art_label.width()))
        else:
            key = c.info.path if c.info else None
            if key != self._cover_key:
                self._cover_key = key
                self._cover_src = load_cover(c.info) if c.info else None
                self.art_label.setPixmap(art_pixmap(self._cover_src, self.art_label.width()))
        self._refresh_live(on_radio)
        shown = self.seek_slider.value() / 1000 if self._dragging else position
        self.elapsed_label.setText(format_time(shown))
        self.total_label.setText(format_time(duration))

        seek = self.seek_slider
        seek.setRange(0, int(duration * 1000))
        if not self._dragging:
            seek.setValue(int(position * 1000))
        seek.setEnabled(c.can_seek and duration > 0)

        playing = self.radio.state is not RadioState.IDLE if on_radio else state is State.PLAYING
        if playing:
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
        self.repeat_button.setEnabled(not on_radio)
        self.shuffle_button.setEnabled(not on_radio)
        if self._tab == "playlist":
            self._update_count()   # 방송 수는 탭 바꿀 때와 목록이 바뀔 때만 센다
        if c.status_error != self._status_error:
            self._status_error = c.status_error
            color = ERROR_COLOR if c.status_error else INFO_COLOR
            self.status_label.setStyleSheet(f"color: {color};")
        self._set_elided(self.status_label, c.status)

    def _refresh_live(self, on_radio: bool) -> None:
        r = self.radio
        marked = r.current.id if on_radio and r.current is not None else None
        if marked != self._marked_station:
            self._marked_station = marked
            self.station_view.set_current(marked)
        if not on_radio:
            return
        # 색은 라디오 상태를 따른다 (B에 연결하는 동안 플레이어는 아직 라이브다)
        color = LIVE_COLOR if r.state in (RadioState.LIVE, RadioState.RETRYING) else INFO_COLOR
        if color != self._live_color:
            self._live_color = color
            self.live_label.setStyleSheet(f"color: {color};")
        self.listened_label.setText(LISTENED_PREFIX + format_time(r.elapsed))

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
        item.setData(Qt.ForegroundRole, QColor(Qt.gray) if track.failed or track.missing else None)

    # ---- 끝내기 ----

    def shutdown(self) -> None:
        self._closed = True
        self.controller.save_session()
        # 기다리던 연결·다시 연결이 끈 뒤에 돌지 않게 먼저 멈춘다 (라디오는 플레이어를 닫지 않는다)
        self.radio.shutdown()
        self.runner.shutdown()
        self.media_keys.disable()
        self._timer.stop()
        self._player.close()
