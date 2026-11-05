from __future__ import annotations

import os
import time
from contextlib import contextmanager

import numpy as np

from PyQt5.QtCore import QEvent, QItemSelectionModel, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QApplication, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
    QListWidgetItem, QMenu, QPushButton, QShortcut, QSizePolicy, QStackedWidget, QStyle,
    QVBoxLayout, QWidget,
)

from funplayer import coverfind, musicbrainz
from funplayer.controller import PlayerController
from funplayer.core.contrast import error_color
from funplayer.core.renamer import RenameError, RenameLog
from funplayer.core.settings import Settings
from funplayer.core.spectrum import Decay, band_levels
from funplayer.core.stations import StationList, load_stations, save_stations
from funplayer.core.taginfo import TrackInfo
from funplayer.core.themes import Theme, accent_from_pixels, album_theme, get_theme
from funplayer.core.tracks import SUPPORTED_EXTS
from funplayer.core.timefmt import format_time
from funplayer.engine.decoder import SAMPLE_RATE
from funplayer.engine import tags, tagwrite
from funplayer.engine.player import AudioPlayer, State
from funplayer.engine.tagwrite import TagWriteError
from funplayer.radio import DUP_STATION_MSG, RadioController, RadioState
from funplayer.ui.bridge import PlayerBridge
from funplayer.core.playlist import path_key
from funplayer.ui.colors import ERROR_COLOR, FAVORITE_COLOR
from funplayer.ui.cover import load_cover, radio_art_for, rounded_art
from funplayer.ui.fx_strip import BARS, FxStrip
from funplayer.ui.glyphs import glyph, glyph_pixmap
from funplayer.ui.icon_tabs import IconTabs
from funplayer.ui.icons import radio_art
from funplayer.ui.settings_dialog import SettingsDialog
from funplayer.ui.bulk_dialog import TAB_COVERS, TAB_NAMES, BulkTagDialog
from funplayer.ui.info_dialog import ART_SIZE as INFO_ART_SIZE, TrackInfoDialog
from funplayer.ui.jump_slider import JumpSlider
from funplayer.ui.media_keys import MEDIA_KEYS_BUSY_MSG, MediaKeys
from funplayer.ui.now_strip import ART_RADIUS as STRIP_RADIUS, ART_SIZE as STRIP_ART, ClickLabel, NowStrip
from funplayer.ui.playlist_view import (ROLE_CURRENT, ROLE_FAVORITE, ROLE_NUMBER, ROLE_TITLE,
                                        PlaylistView)
from funplayer.ui.radio_dialogs import AddUrlDialog
from funplayer.ui.station_view import StationView
from funplayer.ui.style import EDGE, MINI_RADIUS, WINDOW_RADIUS, hero_theme, mini_theme, stylesheet
from funplayer.ui.title_bar import EdgeGrips, TitleBar, WindowDragArea
from funplayer.ui.window_keeper import MINI_SIZE
from funplayer.ui.worker import QtRunner

REFRESH_MS = 200
SPECTRUM_MS = 40
SPECTRUM_MAX_DT = 0.2
VOLUME_STEP = 5
_QWIDGETSIZE_MAX = 16777215
REPEAT_TIPS = {"off": "반복: 끔", "all": "반복: 전체", "one": "반복: 한 곡"}
SHUFFLE_TIPS = {False: "무작위: 끔", True: "무작위: 켬"}
ART_NORMAL = 216
ART_MINI = 80
ART_RADIUS = 28
ART_MINI_RADIUS = 14
PLAY_SIZE = 60
NOW_MARGINS = (26, 18, 26, 16)
TITLE_PX = 19
# 시안의 미니 칸 (폭은 테두리 1px 안쪽부터 잰다. 그림 80 + 곡 정보 206 + 조작 172 + 소리 92 + 목록 26)
MINI_MARGINS = (13, 0, 17, 0)
MINI_GAP = 12
MINI_INFO_WIDTH = 206
MINI_VOLUME_WIDTH = 92
MINI_LIFT = 8   # 조작부는 창 버튼 자리를 비우려고 살짝 아래에 놓는다
# 공용 위젯의 보기별 치수: (이름, 보통 크기, 미니 크기, 보통 그림, 미니 그림)
MODE_BUTTONS = (
    ("heart_button", (34, 34), (22, 22), 23, 17),
    ("shuffle_button", (34, 34), (30, 34), 19, 17),
    ("prev_button", (34, 34), (30, 34), 21, 19),
    ("play_button", (PLAY_SIZE, PLAY_SIZE), (46, 46), 28, 22),
    ("next_button", (34, 34), (30, 34), 21, 19),
    ("repeat_button", (34, 34), (30, 34), 19, 17),
    ("mute_button", (26, 26), (24, 24), 19, 17),
)
# (이름, 보통 글자, 미니 글자)
MODE_FONTS = (
    ("title_label", TITLE_PX, 14), ("artist_label", 13, 12), ("elapsed_label", 12, 11),
    ("total_label", 12, 11), ("live_label", 13, 11), ("listened_label", 13, 11),
)
TABS = ("now", "playlist", "radio", "fx")
TAB_TITLES = ("지금 재생", "재생목록", "라디오", "음향 효과")
TAB_ICONS = ("music", "list", "radio", "sliders")
LIVE_TEXT = "● LIVE"
LISTENED_PREFIX = "들은 시간 "
DOMESTIC_INFO_PATH = "방송사 웹 재생 주소 (들을 때마다 새로 받음)"

BULK_TEXT = "여러 곡 태그 고치기…\tCtrl+T"
COVER_SCAN_MSG = "그림 없는 곡 찾는 중… ({n}곡)"
COVER_FOUND_MSG = "그림 없는 곡 {n}곡 (붉은 글) · 목록 → 그림 없는 곡 → 붉은 곡 그림 자동으로 찾기"
COVER_NONE_MSG = "그림 없는 곡이 없습니다"
COVER_SCAN_FAIL_MSG = "그림 없는 곡을 찾지 못했습니다"
FAV_ON_TEXT = "즐겨찾기 (맨 위로)\tCtrl+D"
FAV_OFF_TEXT = "즐겨찾기 해제\tCtrl+D"

SHORTCUTS: list[tuple[str, str]] = [
    ("Space", "toggle"), ("X", "toggle"), ("V", "stop"), ("Z", "prev"), ("B", "next"),
    ("Left", "seek_back"), ("Right", "seek_forward"), ("Up", "volume_up"),
    ("Down", "volume_down"), ("M", "toggle_mute"), ("L", "open_files"),
    ("R", "cycle_repeat"), ("S", "toggle_shuffle"),
    ("Delete", "remove_selected"), ("Return", "play_selected"), ("Enter", "play_selected"),
    ("Ctrl+A", "select_all"), ("Ctrl+S", "save_playlist"), ("Ctrl+O", "open_playlist"),
    ("Ctrl+I", "show_track_info"), ("Ctrl+M", "toggle_mini"), ("Ctrl+Tab", "next_tab"),
    ("Ctrl+Left", "prev"), ("Ctrl+Right", "next"), ("Ctrl+E", "toggle_fx_visible"),
    ("Ctrl+D", "toggle_favorite"), ("Ctrl+T", "show_bulk_tags"),
]


class PlayerPanel(QWidget):
    miniChanged = pyqtSignal(bool)
    miniOnTopChanged = pyqtSignal(bool)

    def __init__(self, settings: Settings, player=None, parent=None, *,
                 session_path: str | None = None, read_info=None, media_keys=None,
                 stations_path: str | None = None, runner=None, write_tags=None, clear_tags=None,
                 rename_log_path: str | None = None, has_cover=None, find_cover=None,
                 font_family: str = "Malgun Gothic") -> None:
        super().__init__(parent)
        self._font_family = font_family
        self._player = player if player is not None else AudioPlayer()
        self.controller = PlayerController(
            self._player, settings, session_path=session_path, read_info=read_info,
            write_tags=write_tags, clear_tags=clear_tags, rename_log=RenameLog(rename_log_path))
        # 라디오: 경로가 없으면(테스트) 저장하지 않는 메모리 목록이다
        self._stations_path = stations_path
        self.stations = load_stations(stations_path) if stations_path else StationList()
        self.runner = runner if runner is not None else QtRunner(self)
        self.radio = RadioController(
            self._player, self.stations, self.runner.run_async, self.runner.call_later,
            time.monotonic, notify=self.controller.radio_notify)
        self.controller.attach_radio(self.radio)
        self._tab = "now"
        self.theme = get_theme(settings.theme)   # 고른 테마 (앨범 색이어도 id는 "c")
        self._applied_theme = self.theme          # 실제로 입힌 색 (앨범 색이면 곡마다 album_theme)
        self._album_accent: str | None = None
        self.settings_dialog = None
        self._sheet_set = False
        self._restyle_on_show = False
        self._hero = hero_theme(self.theme)
        self._live_color: str | None = None
        self._marked_station: object = object()
        self._closed = False   # shutdown 뒤 큐에 남은 신호를 버린다
        self._cover_key: object = object()
        self._cover_src = None
        self._art_radio = False
        self._strip_art = QPixmap()
        self._dragging = False
        self._list_version = -1
        self._layout_version = -1
        self._followed_index = None   # 목록이 마지막으로 따라가 보여 준 현재 곡 줄
        self.actions: dict[str, QAction] = {}
        self.info_dialog: TrackInfoDialog | None = None
        self.bulk_dialog: BulkTagDialog | None = None
        self._no_cover: dict[int, object] = {}   # 그림 없는 곡: id(Track) -> Track (줄이 옮겨지거나 이름이 바뀌어도 따라감)
        self._cover_scan = False
        self._has_cover = has_cover or tagwrite.has_cover
        self._find_cover = find_cover or (lambda artist, title: coverfind.default_finder().find(artist, title))
        self._icon_key: tuple[str, bool] | None = None
        self._play_key: bool | None = None
        self._mute_key: bool | None = None
        self._heart_key: bool | None = None
        self._track_fav_key: tuple | None = None
        self._track_fav = False
        self._status_error: bool | None = None
        self._settings = settings
        self.settings = settings   # 공개 이름(같은 객체)
        self.is_mini = False   # settings.mini는 창(Task 10)이 적용한다
        self.chrome = False    # 테두리 없는 창인가 (__main__이 켠다. 6단계에서 끼울 때는 그대로 둔다)
        self.grips: EdgeGrips | None = None
        self._maximized = False
        self._pages_min_key: tuple | None = None

        self._bridge = PlayerBridge(self._player, self)
        self._bridge.ended.connect(self._on_ended, Qt.QueuedConnection)
        self._bridge.error.connect(self._on_error, Qt.QueuedConnection)
        self._bridge.lost.connect(self._on_lost, Qt.QueuedConnection)

        self.media_keys = media_keys if media_keys is not None else MediaKeys(self)
        # 스펙트럼: 음향 효과 탭이 보일 때만 도는 별도 타이머 (_apply_visibility가 켜고 끈다)
        self._spectrum_timer = QTimer(self)
        self._spectrum_timer.setInterval(SPECTRUM_MS)
        self._spectrum_timer.timeout.connect(self._spectrum_tick)
        self._big_decay = Decay(BARS)
        self._spectrum_last: float | None = None
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
        self.fx_strip.set_genre_preset(self.controller.genre_preset)
        self.refresh()
        # 이어 듣기 안내가 떠 있으면 키 안내로 가리지 않는다 (시작할 때 상태 글은 그것뿐이다)
        if self._settings.media_keys and not self.media_keys.enable() and not self.controller.status:
            self.controller.notify(MEDIA_KEYS_BUSY_MSG)
            self.refresh()
        self.apply_theme(self.theme)

    # ---- 테마 ----

    def apply_theme(self, theme: Theme) -> None:
        """테마를 입힌다. 비싼 일이라 테마가 바뀔 때만 부른다 (refresh에서 부르지 않는다)."""
        self.theme = theme
        applied = self._applied_theme = album_theme(self._album_accent) if theme.id == "c" else theme
        # 아직 보이지 않는 창에 두 번째로 입힌 규칙은 Qt가 이미 만든 자식 위젯에 닿지 않는다
        # (제목줄이 처음 색 그대로 남는다). 보일 때 한 번 더 입힌다 (showEvent)
        self._restyle_on_show = self._restyle_on_show or (self._sheet_set and not self.isVisible())
        self._sheet_set = True
        self.setStyleSheet(stylesheet(applied, self._font_family))
        self.title_bar.set_theme(applied)
        self.tab_bar.set_theme(applied)
        self.now_strip.set_theme(applied)
        self.playlist_view.set_theme(applied)
        self.station_view.set_theme(applied)
        self.fx_strip.set_theme(applied)   # 음향 효과 쪽은 hero가 아니라 기본 색이다
        self._apply_icons()
        self._render_art()
        self._live_color = self._status_error = None   # 색이 테마를 따르니 기억을 비우고 새로 입힌다
        self._refresh_live(self.controller.source == "radio")
        self._refresh_status_color()
        self._sync_pages_min(force=True)

    def set_theme_id(self, id: str) -> None:
        """테마를 바꿔 입힌다. 저장하지 않는다 (저장은 설정 창의 [확인])."""
        self._album_accent = None
        if id == "c":
            self._album_accent = self._accent_of(None if self._art_radio else self._cover_src)
        self.apply_theme(get_theme(id))

    @staticmethod
    def _accent_of(cover: QPixmap | None) -> str | None:
        """표지를 32x32로 줄여 대표색을 뽑는다. 표지가 없으면 None (기본 보라)."""
        if cover is None or cover.isNull():
            return None
        img = cover.toImage().scaled(32, 32, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        img = img.convertToFormat(QImage.Format_RGB32)
        pixels = []
        for y in range(img.height()):
            for x in range(img.width()):
                c = QColor(img.pixel(x, y))
                pixels.append((c.red(), c.green(), c.blue()))
        return accent_from_pixels(pixels)

    def _accent_changed(self) -> bool:
        """앨범 색 테마일 때 지금 곡의 대표색이 바뀌었는가 (바뀌었으면 기억해 둔다)."""
        if self.theme.id != "c":
            return False
        accent = None if self._art_radio else self._accent_of(self._cover_src)
        if accent == self._album_accent:
            return False
        self._album_accent = accent
        return True

    def show_settings(self, modal: bool = True) -> SettingsDialog:
        dialog = self.settings_dialog = SettingsDialog(self.theme.id, self)
        original = self.theme.id
        dialog.themePicked.connect(self.set_theme_id)

        def accepted() -> None:
            chosen = dialog.selected_id()
            self.set_theme_id(chosen)
            self.settings.theme = chosen

        dialog.accepted.connect(accepted)
        dialog.rejected.connect(lambda: self.set_theme_id(original))   # X로 닫아도 취소다
        dialog.finished.connect(lambda _=0: setattr(self, "settings_dialog", None))
        dialog.finished.connect(dialog.deleteLater)
        if modal:
            dialog.open()
        else:
            dialog.show()
        return dialog

    def _apply_icons(self) -> None:
        """공용 위젯은 지금 놓인 면(지금 재생 또는 미니 막대)의 색과 크기로 그린다."""
        theme = self._applied_theme
        hero = self._hero = mini_theme(theme) if self.is_mini else hero_theme(theme)
        self._set_glyph(self.prev_button, "prev", hero.icon)
        self._set_glyph(self.next_button, "next", hero.icon)
        self.vol_max_label.setPixmap(glyph_pixmap("volH", hero.icon, 19))
        self.mini_button.setIcon(glyph("shrink", hero_theme(theme).icon, 16))
        icon = mini_theme(theme).icon
        for b, name in ((self.mini_min_button, "min"), (self.mini_normal_button, "max"),
                        (self.mini_close_button, "x"), (self.list_button_mini, "list")):
            self._set_glyph(b, name, icon)
        self._icon_key = self._play_key = self._mute_key = self._heart_key = None
        self._refresh_icons()

    @staticmethod
    def _set_glyph(button: QPushButton, name: str, color: str) -> None:
        button.setIcon(glyph(name, color, button.iconSize().width()))

    def _render_art(self) -> None:
        """지금 그림(_cover_src)을 지금 크기와 테마로 다시 그린다. 곡·방송·테마·크기가 바뀔 때만."""
        size = self.art_label.width()
        radius = ART_MINI_RADIUS if self.is_mini else ART_RADIUS
        theme = self._applied_theme
        if self._art_radio:
            art = radio_art_for(theme, size, radius)
            self._strip_art = radio_art_for(theme, STRIP_ART, STRIP_RADIUS)
        else:
            art = rounded_art(self._cover_src, size, radius, theme)
            self._strip_art = rounded_art(self._cover_src, STRIP_ART, STRIP_RADIUS, theme)
        self.art_label.setPixmap(art)

    def _art_changed(self) -> None:
        """곡·방송이 바뀌었다: 앨범 색이 달라지면 테마를 새로 입히고(그림도 다시 그린다), 아니면 그림만."""
        if self._accent_changed():
            self.apply_theme(self.theme)
        else:
            self._render_art()

    @staticmethod
    def _repolish(w: QWidget) -> None:
        w.style().unpolish(w)
        w.style().polish(w)

    # ---- 만들기 ----

    def _tool(self, tip: str = "", size: int = 34, icon_size: int = 21, kind: str = "") -> QPushButton:
        b = QPushButton()
        b.setIconSize(QSize(icon_size, icon_size))
        b.setFixedSize(size, size)
        b.setFocusPolicy(Qt.TabFocus)   # 눌러도 키보드 초점을 뺏지 않는다
        if kind:
            b.setProperty("kind", kind)
        if tip:
            b.setToolTip(tip)
        return b

    @staticmethod
    def _page(name: str) -> QWidget:
        page = QWidget()
        page.setObjectName(name)
        page.setAttribute(Qt.WA_StyledBackground)
        return page

    @staticmethod
    def _label(text: str = "", px: int = 12, role: str = "") -> QLabel:
        label = QLabel(text)
        font = QFont(label.font())
        font.setPixelSize(px)
        label.setFont(font)
        if role:
            label.setProperty("role", role)
        return label

    def _build(self) -> None:
        self.setFocusPolicy(Qt.StrongFocus)   # 초점 받을 위젯이 없는 페이지에서도 단축키가 듣게
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.root = QWidget()   # 둥근 배경. 패널 자체는 테두리 없는 창에서 투명이다
        self.root.setObjectName("root")
        self.root.setAttribute(Qt.WA_StyledBackground)
        outer.addWidget(self.root)
        root = self._body = QVBoxLayout(self.root)
        root.setContentsMargins(EDGE, EDGE, EDGE, EDGE)
        root.setSpacing(0)

        self.title_bar = TitleBar()
        root.addWidget(self.title_bar)

        self.tab_bar = IconTabs()
        for name, title in zip(TAB_ICONS, TAB_TITLES):
            self.tab_bar.addTab(name, title)
        root.addWidget(self.tab_bar)

        self.pages = QStackedWidget()
        # 쌓인 페이지 중 가장 큰 것이 창 최소 크기를 정하지 않게 한다 (숨은 음향 효과 칸이 창을 넓히면 안 된다)
        self.pages.setMinimumSize(1, 1)
        for page in (self._build_now_page(), self._build_list_page(), self._build_radio_page(),
                     self._build_fx_page()):
            self.pages.addWidget(page)
        root.addWidget(self.pages, 1)
        self._foot_row: QHBoxLayout | None = None
        self.view_button = QPushButton("보기")
        self.count_label = self._label("0곡", 12, "mute")
        self._setup_foot_button(self.view_button)
        self._place_foot()

        # 모든 탭이 같이 쓰는 안내 줄: 글이 있을 때만 보인다
        self.status_label = self._label(px=12)
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.status_label.setMinimumWidth(0)
        self.status_label.setContentsMargins(14, 3, 14, 3)
        self.status_label.hide()
        root.addWidget(self.status_label)

        self.now_strip = NowStrip()
        self.now_strip.hide()
        root.addWidget(self.now_strip)

        outer.addWidget(self._build_mini_bar())

    def _build_now_page(self) -> QWidget:
        page = self.page_now = self._page("pageNow")
        lay = self._now_layout = QVBoxLayout(page)
        lay.setContentsMargins(*NOW_MARGINS)
        lay.setSpacing(0)

        self.art_label = ClickLabel()
        self.art_label.setFixedSize(ART_NORMAL, ART_NORMAL)
        self.art_label.setToolTip("곡 정보")
        self.art_label.setCursor(Qt.PointingHandCursor)
        self.art_row = QHBoxLayout()
        self.art_row.addWidget(self.art_label, 0, Qt.AlignCenter)
        lay.addLayout(self.art_row)
        lay.addSpacing(18)

        self.title_label = self._label(px=TITLE_PX)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.title_label.setMinimumWidth(0)
        self.artist_label = self._label(px=13, role="mute")
        self.artist_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.artist_label.setMinimumWidth(0)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(self.title_label)
        titles.addWidget(self.artist_label)
        self.head_row = QHBoxLayout()
        self.head_row.setSpacing(10)
        self.head_row.addLayout(titles, 1)
        self.heart_button = self._tool("즐겨찾기", 34, 23, "fav")
        self.heart_button.setCheckable(True)
        self.head_row.addWidget(self.heart_button)
        self.mini_button = self._tool("작게 보기", 26, 16)
        self.head_row.addWidget(self.mini_button, 0, Qt.AlignVCenter)
        lay.addLayout(self.head_row)
        lay.addSpacing(16)

        self.seek_slider = JumpSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        lay.addWidget(self.seek_slider)
        lay.addSpacing(8)

        # 시간 줄. 라디오일 때는 막대 대신 라이브 줄: 왼쪽 "● LIVE", 오른쪽 들은 시간
        self.elapsed_label = self._label("0:00", 12, "mute")
        self.total_label = self._label("0:00", 12, "mute")
        self.live_label = self._label(LIVE_TEXT, 13)
        font = self.live_label.font()
        font.setBold(True)
        self.live_label.setFont(font)
        self.listened_label = self._label(LISTENED_PREFIX + format_time(0), 13, "mute")
        self.live_label.hide()
        self.listened_label.hide()
        row = QHBoxLayout()
        row.addWidget(self.elapsed_label)
        row.addWidget(self.live_label)
        row.addStretch(1)
        row.addWidget(self.listened_label)
        row.addWidget(self.total_label)
        lay.addLayout(row)
        lay.addSpacing(10)

        ctl = self.control_row = QHBoxLayout()
        self.shuffle_button = self._tool(icon_size=19)
        self.prev_button = self._tool("이전 곡")
        self.play_button = self._tool("재생", PLAY_SIZE, 28, "play")
        self.next_button = self._tool("다음 곡")
        self.repeat_button = self._tool(icon_size=19)
        for b in (self.repeat_button, self.shuffle_button):
            b.setCheckable(True)
        ctl.addWidget(self.shuffle_button)
        for w in (self.prev_button, self.play_button, self.next_button, self.repeat_button):
            ctl.addStretch(1)
            ctl.addWidget(w)
        lay.addLayout(ctl)
        lay.addStretch(1)

        self.mute_button = self._tool("음소거", 26, 19)
        self.volume_slider = JumpSlider(Qt.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.vol_max_label = QLabel()
        self.vol_max_label.setFixedSize(19, 19)
        vol = QHBoxLayout()
        vol.setSpacing(8)
        vol.addWidget(self.mute_button)
        vol.addWidget(self.volume_slider, 1)
        vol.addWidget(self.vol_max_label)
        lay.addLayout(vol)

        # 미니에서 돌아올 자리: (위젯, 배치, 순서, 늘림, 정렬)
        self._now_slots = [
            slot for box, widgets in (
                (self.art_row, (self.art_label,)),
                (titles, (self.title_label, self.artist_label)),
                (self.head_row, (self.heart_button,)),
                (lay, (self.seek_slider,)),
                (row, (self.elapsed_label, self.live_label, self.listened_label, self.total_label)),
                (ctl, (self.shuffle_button, self.prev_button, self.play_button, self.next_button,
                       self.repeat_button)),
                (vol, (self.mute_button, self.volume_slider)),
            ) for slot in self._slots_in(box, widgets)]
        return page

    @staticmethod
    def _slots_in(box, widgets) -> list[tuple]:
        slots = []
        for w in widgets:
            i = box.indexOf(w)
            slots.append((w, box, i, box.stretch(i), box.itemAt(i).alignment()))
        return slots

    def _mini_line(self, height: int) -> QWidget:
        line = QWidget()
        line.setObjectName("miniLine")
        line.setAttribute(Qt.WA_StyledBackground)
        line.setFixedSize(1, height)
        return line

    def _mini_lowered(self, *widgets: QWidget) -> QHBoxLayout:
        box = QHBoxLayout()
        box.setContentsMargins(0, MINI_LIFT, 0, 0)
        box.setSpacing(0)
        for w in widgets:
            box.addWidget(w)
        return box

    def _build_mini_bar(self) -> QWidget:
        """긴 막대. 그림·제목·조작은 지금 재생 페이지의 위젯을 _place_shared가 옮겨 온다."""
        bar = self.mini_bar = WindowDragArea()
        bar.setObjectName("miniBar")
        bar.setAttribute(Qt.WA_StyledBackground)
        bar.setFixedHeight(MINI_SIZE[1])
        bar.hide()
        row = QHBoxLayout()
        row.setContentsMargins(*MINI_MARGINS)
        row.setSpacing(MINI_GAP)
        row.addWidget(self._mini_line(62))

        info = self.mini_info = QWidget()
        info.setMinimumWidth(MINI_INFO_WIDTH)   # 막대를 늘리면 이 칸이 넓어진다
        col = QVBoxLayout(info)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        seek_row = QHBoxLayout()
        seek_row.setSpacing(7)
        seek_row.addStretch()   # 라디오일 때 LIVE와 들은 시간을 양 끝으로 민다
        col.addStretch(1)
        col.addLayout(title_row)
        col.addSpacing(7)
        col.addLayout(seek_row)
        col.addStretch(1)
        row.addWidget(info, 1)

        ctl = QHBoxLayout()
        ctl.setContentsMargins(0, MINI_LIFT, 0, 0)
        ctl.setSpacing(0)
        ctl.addSpacing(3)
        ctl.addSpacing(3)
        row.addLayout(ctl)
        row.addLayout(self._mini_lowered(self._mini_line(40)))

        volume = self.mini_volume = QWidget()
        volume.setFixedWidth(MINI_VOLUME_WIDTH)
        vol = QHBoxLayout(volume)
        vol.setContentsMargins(0, MINI_LIFT, 0, 0)
        vol.setSpacing(4)
        row.addWidget(volume)
        self.list_button_mini = self._tool("재생목록", 26, 20)
        self.list_button_mini.setFocusPolicy(Qt.NoFocus)
        row.addLayout(self._mini_lowered(self.list_button_mini))

        controls = self.mini_controls = QWidget()
        controls.setObjectName("miniControls")
        win = QHBoxLayout(controls)
        win.setContentsMargins(0, 4, 10, 0)
        win.setSpacing(0)
        self.mini_min_button = self._mini_window_button(win, "최소화", 14)
        self.mini_normal_button = self._mini_window_button(win, "보통 보기", 12)
        self.mini_close_button = self._mini_window_button(win, "닫기", 14)

        stack = QGridLayout(bar)   # 창 버튼은 줄 위 오른쪽 구석에 겹쳐 놓는다
        stack.setContentsMargins(0, 0, 0, 0)
        stack.addLayout(row, 0, 0)
        stack.addWidget(controls, 0, 0, Qt.AlignTop | Qt.AlignRight)

        plain = Qt.Alignment()
        self._mini_slots = [
            (self.art_label, row, 0, 0, plain),
            (self.title_label, title_row, 0, 1, plain),
            (self.heart_button, title_row, 1, 0, plain),
            (self.artist_label, col, 2, 0, plain),
            (self.elapsed_label, seek_row, 0, 0, plain),
            (self.live_label, seek_row, 1, 0, plain),
            (self.seek_slider, seek_row, 2, 1, plain),
            (self.listened_label, seek_row, 4, 0, plain),
            (self.total_label, seek_row, 5, 0, plain),
            (self.shuffle_button, ctl, 0, 0, plain),
            (self.prev_button, ctl, 1, 0, plain),
            (self.play_button, ctl, 3, 0, plain),
            (self.next_button, ctl, 5, 0, plain),
            (self.repeat_button, ctl, 6, 0, plain),
            (self.mute_button, vol, 0, 0, plain),
            (self.volume_slider, vol, 1, 1, plain),
        ]
        return bar

    def _mini_window_button(self, row: QHBoxLayout, tip: str, icon_size: int) -> QPushButton:
        b = self._tool(tip, 24, icon_size)
        b.setFixedSize(24, 20)
        b.setFocusPolicy(Qt.NoFocus)
        row.addWidget(b)
        return b

    def _setup_foot_button(self, b: QPushButton) -> None:
        b.setProperty("kind", "btn")
        b.setFocusPolicy(Qt.TabFocus)
        b.setSizePolicy(QSizePolicy.Preferred, b.sizePolicy().verticalPolicy())

    def _foot(self, page_layout: QVBoxLayout, buttons: tuple[QPushButton, ...]) -> QHBoxLayout:
        bar = QWidget()
        bar.setObjectName("footBar")
        bar.setAttribute(Qt.WA_StyledBackground)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(6)
        for b in buttons:
            self._setup_foot_button(b)
            row.addWidget(b)
        row.addStretch(1)
        page_layout.addWidget(bar)
        return row

    def _build_list_page(self) -> QWidget:
        page = self._page("pagePlaylist")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.playlist_view = PlaylistView()
        box = QVBoxLayout()
        box.setContentsMargins(8, 6, 8, 6)
        box.addWidget(self.playlist_view)
        lay.addLayout(box, 1)
        self.open_button = QPushButton("열기")
        self.add_button = QPushButton("추가")
        self.list_button = QPushButton("목록")
        self._list_foot = self._foot(lay, (self.open_button, self.add_button, self.list_button))
        return page

    def _build_radio_page(self) -> QWidget:
        page = self._page("pageRadio")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.station_view = StationView()
        self.station_view.set_stations(self.stations, self._settings.radio_open)
        box = QVBoxLayout()
        box.setContentsMargins(8, 6, 8, 6)
        box.addWidget(self.station_view)
        lay.addLayout(box, 1)
        self.add_url_button = QPushButton("주소 넣기…")
        self._radio_foot = self._foot(lay, (self.add_url_button,))
        return page

    def _build_fx_page(self) -> QWidget:
        page = self._page("pageFx")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 12, 18, 12)
        self.fx_strip = FxStrip()
        self.fx_strip.set_value(self.controller.effects)
        lay.addWidget(self.fx_strip)
        lay.addStretch(1)
        return page

    def _place_foot(self) -> None:
        """[보기]와 개수 글은 하나뿐이라 보이는 페이지의 아래 줄로 옮긴다."""
        target = self._radio_foot if self._tab == "radio" else self._list_foot
        if self._foot_row is target:
            return
        if self._foot_row is not None:
            self._foot_row.removeWidget(self.view_button)
            self._foot_row.removeWidget(self.count_label)
        target.insertWidget(target.count() - 1, self.view_button)   # 늘이개 앞
        target.addWidget(self.count_label)
        self._foot_row = target
        self.view_button.show()    # 부모가 바뀌면 숨겨진다
        self.count_label.show()

    def _wire(self) -> None:
        c = self.controller
        self.prev_button.clicked.connect(self.prev)
        self.play_button.clicked.connect(self.toggle)
        self.next_button.clicked.connect(self.next)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.repeat_button.clicked.connect(self.cycle_repeat)
        self.shuffle_button.clicked.connect(self.toggle_shuffle)
        self.heart_button.clicked.connect(self.toggle_current_favorite)
        strip = self.now_strip
        strip.prevClicked.connect(self.prev)
        strip.toggleClicked.connect(self.media_toggle)   # 띠는 지금 나오는 쪽을 보여 준다
        strip.nextClicked.connect(self.next)
        strip.openClicked.connect(self.show_track_info)

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
        self._make_source_menu()
        for menu in self.findChildren(QMenu):
            menu.setObjectName("themed")
        for b in (self.open_button, self.add_button, self.list_button, self.add_url_button,
                  self.view_button):
            self._fit_min_width(b)
        self.tab_bar.currentChanged.connect(self._tab_changed)
        self.fx_strip.changed.connect(self._fx_changed)
        sv = self.station_view
        sv.station_activated.connect(self._play_station)
        sv.changed.connect(self._stations_changed)
        sv.open_groups_changed.connect(self._open_groups_changed)
        self.add_url_button.clicked.connect(self.add_url)
        self.art_label.clicked.connect(self.show_track_info)
        self.mini_button.clicked.connect(self.toggle_mini)
        self.list_button_mini.clicked.connect(self._open_list_from_mini)
        self.mini_min_button.clicked.connect(lambda _=False: self.showMinimized())
        self.mini_normal_button.clicked.connect(lambda _=False: self.set_mini(False))
        self.mini_close_button.clicked.connect(lambda _=False: self.close())
        self.title_label.installEventFilter(self)
        bar = self.title_bar
        bar.miniClicked.connect(self.toggle_mini)
        bar.minimizeClicked.connect(self.showMinimized)
        bar.maximizeClicked.connect(self.toggle_maximize)
        bar.closeClicked.connect(self.close)
        # 지금 재생·음향 효과 탭에는 [보기] 버튼이 없어 상단바에서도 연다
        bar.menu_requested.connect(lambda pos: self.view_menu.exec_(pos))

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
                 ("info_row", "곡 정보 고치기…", self.show_row_info),
                 ("bulk_tags", BULK_TEXT, self.show_bulk_tags),
                 ("favorite", FAV_ON_TEXT, self.toggle_favorite),
                 ("undo_rename", "이름 되돌리기", self.undo_rename_from_menu),
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
        self._add_action(menu, "save_favorites", "즐겨찾기 저장…", self.save_favorites)
        self._add_action(menu, "load_favorites", "즐겨찾기 불러오기…", self.load_favorites)
        menu.addSeparator()
        cover = menu.addMenu("그림 없는 곡")
        self._add_action(cover, "find_covers", "찾아서 붉은 글로 표시", self.find_missing_covers)
        self._add_action(cover, "select_covers", "붉은 곡만 고르기", self.select_missing_covers)
        self._add_action(cover, "add_covers", "붉은 곡 그림 자동으로 찾기…", self.add_missing_covers)
        self._add_action(cover, "clear_covers", "붉은 표시 지우기", self.clear_cover_marks)
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
        self._add_action(menu, "settings", "설정…", self.show_settings)
        menu.addSeparator()
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

    def _make_source_menu(self) -> None:
        """재생 버튼·제목·미니 막대를 오른쪽 클릭한 메뉴: 정지, 라디오로/MP3로."""
        menu = self.source_menu = QMenu(self)
        self._add_action(menu, "stop", "정지", self.stop)
        self._add_action(menu, "switch", "라디오로", self._switch_source)
        for w in (self.play_button, self.title_label, self.mini_bar):
            w.setContextMenuPolicy(Qt.CustomContextMenu)
            w.customContextMenuRequested.connect(
                lambda pos, w=w: self.source_menu.exec_(w.mapToGlobal(pos)))

    def toggle_fx_visible(self) -> None:
        """Ctrl+E: 음향 효과 탭과 지금 재생 탭을 오간다."""
        self.set_tab("now" if self._tab == "fx" else "fx")

    def _fx_changed(self, fx, final: bool) -> None:
        self.controller.set_effects(fx, save=bool(final))
        self.fx_strip.set_genre_preset(self.controller.genre_preset)

    def _spectrum_playing(self) -> bool:
        c = self.controller
        if c.source == "radio":
            return self.radio.state is RadioState.LIVE
        return c.state is State.PLAYING

    def _spectrum_wanted(self) -> bool:
        # 음향 효과 탭이 실제로 보일 때만 (패널·창이 숨겨졌거나 최소화되면 계산하지 않는다)
        return (self._tab == "fx" and not self.is_mini and self.isVisible()
                and not self.window().isMinimized())

    def _sync_spectrum_timer(self) -> None:
        self._set_spectrum_running(self._spectrum_wanted())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._restyle_on_show:
            self._restyle_on_show = False
            self.setStyleSheet(self.styleSheet())
        self._sync_spectrum_timer()
        self._sync_pages_min(force=True)   # QSS가 입혀진 글자 높이는 보일 때에야 정해진다

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._sync_spectrum_timer()

    def _spectrum_tick(self) -> None:
        if not self._spectrum_wanted():   # 안전망: 숨겨졌는데 타이머가 남았다면 멈추고 끝낸다
            self._spectrum_last = None
            self._set_spectrum_running(False)
            return
        now = time.monotonic()
        last, self._spectrum_last = self._spectrum_last, now
        dt = 0.0 if last is None else min(max(now - last, 0.0), SPECTRUM_MAX_DT)
        block = self._player.latest_block() if self._spectrum_playing() else None
        strip = self.fx_strip
        view, decay, bars = strip.spectrum, self._big_decay, BARS
        if block is None or len(block) == 0:
            levels = np.zeros(bars)
        else:
            levels = band_levels(block, SAMPLE_RATE, bars)
        shown, peaks = decay.update(levels, dt)
        if not (any(shown) or any(peaks) or any(view.levels) or any(view.peaks)):
            return   # 이미 0이고 그대로 0이면 다시 그리지 않는다
        view.set_levels(shown, peaks)

    def _set_spectrum_running(self, on: bool) -> None:
        t = self._spectrum_timer
        if on and not t.isActive():
            self._spectrum_last = None
            t.start()
        elif not on and t.isActive():
            t.stop()

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
        if event.type() == QEvent.WindowStateChange:
            self._sync_spectrum_timer()
            self._sync_maximized()
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self._retry_media_keys()

    # ---- 창 ----

    def use_window_chrome(self) -> None:
        """테두리 없는 둥근 창으로 바꾼다. 안 부르면 보통 창이다 (6단계에서 캘린더에 끼울 때)."""
        if self.chrome:
            return
        shown = self.isVisible()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.chrome = True
        self.grips = EdgeGrips(self)
        self.grips.set_suspended(self._maximized)
        self.grips.set_enabled_edges(self.is_mini)
        if shown:
            self.show()

    def corner_radius(self) -> int:
        if self.is_mini:
            return MINI_RADIUS
        return 0 if self.isMaximized() else WINDOW_RADIUS

    def toggle_maximize(self) -> None:
        if self.is_mini:
            return
        if self.isMaximized():
            self.showNormal()
        else:
            self._limit_to_work_area()
            self.showMaximized()

    def _limit_to_work_area(self) -> None:
        # 테두리 없는 창은 최대화할 때 작업 표시줄을 덮을 수 있다
        self.setMaximumSize(self.screen().availableGeometry().size())

    def _check_work_area(self) -> None:
        """Win+위 화살표처럼 toggle_maximize를 거치지 않은 최대화도 작업 표시줄을 덮지 않게."""
        if (self.isMaximized() and not self.is_mini
                and not self.screen().availableGeometry().contains(self.frameGeometry())):
            self._limit_to_work_area()

    def _sync_maximized(self) -> None:
        """최대화가 어디서 왔든 (상단바, Win+위 화살표) 여기를 지난다. 상태가 바뀔 때만 다시 칠한다."""
        on = self.isMaximized()
        if on == self._maximized:
            return
        self._maximized = on
        if not self.is_mini:   # 작게 보기의 고정 높이는 WindowKeeper가 맡는다
            if not on:
                self.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
            else:
                QTimer.singleShot(0, self._check_work_area)   # 최대화한 자리가 정해진 뒤에 본다
        self.title_bar.set_maximized(on)
        if self.grips is not None:
            self.grips.set_suspended(on)
        edge = 0 if on else EDGE
        self._body.setContentsMargins(edge, edge, edge, edge)
        self.root.setProperty("square", "true" if on else "false")   # "maximized"는 QWidget이 이미 쓰는 이름이다
        pages = [self.pages.widget(i) for i in range(self.pages.count())]
        for w in (self.root, self.title_bar, *pages, self.now_strip,
                  *self.findChildren(QWidget, "footBar")):
            self._repolish(w)

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
        self._place_shared(on)
        self._apply_icons()
        if self.grips is not None:
            self.grips.set_enabled_edges(on)
        self._apply_visibility()   # 라디오에 따라 다시 숨길 것을 숨긴다
        self._render_art()
        self._now_layout.invalidate()
        self._now_layout.activate()   # 창 크기를 정하는 sizeHint가 옛 값을 내지 않게
        self._sync_pages_min(force=True)   # 그림 크기가 돌아온 뒤에 잰다
        self.pages.updateGeometry()
        self.root.updateGeometry()   # 패널 배치는 root 속이 바뀐 걸 스스로 모른다
        self.actions["mini"].setChecked(on)
        self._settings.mini = on
        self.setFocus()   # 초점이 있던 위젯이 숨어도 단축키가 듣게
        self.miniChanged.emit(on)
        self.refresh()    # 창 크기가 정해진 뒤 제목을 새 폭에 맞춘다

    def _open_list_from_mini(self) -> None:
        self.set_mini(False)
        self.set_tab("playlist")

    def _place_shared(self, mini: bool) -> None:
        """공용 위젯을 지금 재생 페이지와 미니 막대 사이로 옮기고 크기를 그 자리에 맞춘다."""
        away, slots = (self._now_slots, self._mini_slots) if mini else (self._mini_slots, self._now_slots)
        for w, box, *_ in away:
            box.removeWidget(w)
        for w, box, index, stretch, align in slots:   # 순서가 오름차순이라 늘이개 자리가 지켜진다
            box.insertWidget(index, w, stretch, align)
        size = ART_MINI if mini else ART_NORMAL
        self.art_label.setFixedSize(size, size)
        for name, normal, small, icon, icon_small in MODE_BUTTONS:
            b = getattr(self, name)
            b.setFixedSize(*(small if mini else normal))
            px = icon_small if mini else icon
            b.setIconSize(QSize(px, px))
        for name, normal, small in MODE_FONTS:
            label = getattr(self, name)
            font = label.font()
            font.setPixelSize(small if mini else normal)
            label.setFont(font)
        self.play_button.setProperty("kind", "playMd" if mini else "play")
        for w, *_ in slots:
            w.show()            # 부모가 바뀌면 숨겨진다. 라디오에 따른 것은 _apply_visibility가 맡는다
            self._repolish(w)   # 스타일 규칙이 조상 이름을 따르므로 새 자리 규칙을 받게 한다
        self.mini_controls.raise_()   # 옮겨 온 위젯이 창 버튼을 덮지 않게

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
        bulk_rows = self._favorite_rows()
        self.actions["bulk_tags"].setEnabled(bool(bulk_rows))
        self.actions["bulk_tags"].setText(
            BULK_TEXT.replace("…", f"… ({len(bulk_rows)}곡)") if len(bulk_rows) > 1 else BULK_TEXT)
        fav_rows = bulk_rows
        tracks = self.controller.playlist.tracks
        all_fav = bool(fav_rows) and all(self.controller.is_favorite(tracks[r].path) for r in fav_rows)
        self.actions["favorite"].setEnabled(bool(fav_rows))
        self.actions["favorite"].setText(FAV_OFF_TEXT if all_fav else FAV_ON_TEXT)
        self.actions["save_favorites"].setEnabled(bool(self._settings.favorites))
        self.actions["find_covers"].setEnabled(len(self.controller.playlist) > 0 and not self._cover_scan)
        marked = bool(self.no_cover_rows())
        for key in ("select_covers", "add_covers", "clear_covers"):
            self.actions[key].setEnabled(marked)
        # 이름 되돌리기는 방금 이름을 바꾼 그 곡을 우클릭했을 때만 보인다 (다른 곡에서 실수로 누르지 않게)
        last = self.controller.last_rename()
        tracks = self.controller.playlist.tracks
        if last is not None and not (
                0 <= row < len(tracks) and os.path.normcase(tracks[row].path) == os.path.normcase(last[1])):
            last = None
        self.actions["undo_rename"].setVisible(last is not None)
        if last is not None:
            old, new = (self._elide(os.path.basename(x)) for x in last)
            self.actions["undo_rename"].setText(f"이름 되돌리기: {new} → {old}")
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
        i = TABS.index(name) if name in TABS else 0   # 없는 이름은 지금 재생
        if self.tab_bar.currentIndex() != i:
            self.tab_bar.setCurrentIndex(i)   # → _tab_changed
        else:
            self._tab_changed(i)

    def next_tab(self) -> None:
        self.set_tab(TABS[(TABS.index(self._tab) + 1) % len(TABS)])

    def _tab_changed(self, index: int) -> None:
        # 보이는 것만 바꾼다: 플레이어·라디오·작업 실행기는 부르지 않는다 (접속하지 않는다)
        self._tab = TABS[index] if 0 <= index < len(TABS) else "now"
        if self._settings.tab != self._tab:
            self._settings.tab = self._tab
        self._place_foot()
        self._apply_visibility()
        self._update_count()

    def _apply_visibility(self) -> None:
        mini = self.is_mini
        on_radio = self.controller.source == "radio"
        self.root.setVisible(not mini)
        self.mini_bar.setVisible(mini)
        self.title_bar.setVisible(not mini)
        self.tab_bar.setVisible(not mini)
        # 작게 볼 때는 어느 탭이든 지금 재생 페이지의 위젯을 쓴다
        self.pages.setCurrentIndex(0 if mini else TABS.index(self._tab))
        self.now_strip.setVisible(not mini and self._tab != "now")
        self._sync_spectrum_timer()
        self.actions["switch"].setText("MP3로" if on_radio else "라디오로")
        self.actions["switch"].setEnabled(self.controller.can_switch_source)
        # 탐색 줄: 라디오면 막대와 시간 대신 라이브 줄이다
        for w in (self.seek_slider, self.elapsed_label, self.total_label):
            w.setVisible(not on_radio)
        for w in (self.live_label, self.listened_label):
            w.setVisible(on_radio)
        show_status = not mini and bool(self.controller.status)
        if show_status == self.status_label.isHidden():
            self.status_label.setVisible(show_status)
            # 안내 줄이 창 맨 아래를 차지하면 지금 재생 면의 둥근 아래 모서리가 줄 위에 떠 보인다
            self.page_now.setProperty("flush", "true" if show_status else "false")
            self._repolish(self.page_now)
            self._body.activate()   # 글자를 줄이기 전에 폭을 맞춘다
        self._sync_pages_min()

    def _sync_pages_min(self, force: bool = False) -> None:
        """쌓인 페이지 칸의 최소 높이는 보이는 페이지의 실제 최소 높이다 (창이 줄어도 겹치지 않게)."""
        key = (self.is_mini, self._tab, self.controller.source)
        if key == self._pages_min_key and not force:
            return
        self._pages_min_key = key
        page = self.pages.currentWidget()
        self.pages.setMinimumHeight(1 if self.is_mini else page.minimumSizeHint().height())

    def _update_count(self) -> None:
        if self._tab == "radio":
            self.count_label.setText(f"방송 {self.station_view.count()}개")
        else:
            self.count_label.setText(f"{len(self.controller.playlist)}곡")

    # ---- 라디오 ----

    def _switch_source(self) -> None:
        self.controller.switch_source()
        # 목록을 보고 있었으면 지금 나오는 쪽 목록이 보이게 (지금 재생·음향 효과 탭은 그대로)
        if self._tab in ("playlist", "radio"):
            self.set_tab("radio" if self.controller.source == "radio" else "playlist")
        self.refresh()

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

    def _favorite_rows(self) -> list[int]:
        """즐겨찾기 넣기·빼기 대상: 고른 줄들, 없으면 커서 줄."""
        rows = self.selected_rows()
        if not rows:
            row = self.playlist_view.currentRow()
            rows = [row] if 0 <= row < len(self.controller.playlist) else []
        return rows

    def toggle_favorite(self) -> None:
        if self._tab == "now":
            self.toggle_current_favorite()
            return
        if self._tab != "playlist":
            return   # 다른 탭에서 Ctrl+D는 재생목록을 건드리지 않는다
        rows = self._favorite_rows()
        if not rows:
            return
        new = self.controller.toggle_favorite(rows)
        self.refresh()
        self.select_rows(new)

    def toggle_current_favorite(self) -> None:
        """하트: 지금 나오는 곡(또는 방송)의 즐겨찾기를 켜고 끈다. 곡은 맨 위로 올라갈 수 있다."""
        c = self.controller
        if c.source == "radio":
            station = self.radio.current
            if station is None:
                return
            self.stations.set_favorite(station.id, not self.stations.is_favorite(station.id))
            self.station_view.rebuild()   # changed → 저장
        else:
            row = c.playlist.index
            if row is None:
                return
            c.toggle_favorite([row])
        self.refresh()

    def show_bulk_tags(self, rows: list[int] | None = None, tab: int = TAB_NAMES) -> None:
        """고른 곡(없으면 커서 줄)으로 여러 곡 태그 창을 연다. 창이 떠 있는 동안 목록은 막는다(창 모달)."""
        if self._tab != "playlist":
            return
        rows = rows if rows is not None else self._favorite_rows()
        if not rows:
            return
        c = self.controller
        with self._busy_cursor():
            infos = [c.info_for(r) for r in rows]
            dialog = self.bulk_dialog = BulkTagDialog(
                infos, self, save_many=c.save_many, rename_many=c.rename_many, undo_many=c.undo_many,
                read_info=tags.read_info, has_cover=self._has_cover, after_change=self._after_file_edit,
                start_tab=tab, find_cover=self._find_cover, run_async=self.runner.run_async)
        dialog.setWindowModality(Qt.WindowModal)
        dialog.show()

    # ---- 커버 없는 곡 ----
    def find_missing_covers(self) -> None:
        """재생목록에서 그림이 없는 곡을 찾아 붉은 글로 표시한다 (뒤에서 찾고, 끝나면 알린다)."""
        tracks = list(self.controller.playlist.tracks)
        if not tracks or self._cover_scan:
            return
        self._cover_scan = True
        self.controller.notify(COVER_SCAN_MSG.format(n=len(tracks)))
        self.refresh()
        check = self._has_cover

        def work():
            return [t for t in tracks if not check(t.path)]

        def done(result, error) -> None:
            self._cover_scan = False
            if error is not None:
                self.controller.notify(COVER_SCAN_FAIL_MSG)
            else:
                self._no_cover = {id(t): t for t in result}
                self.controller.notify(COVER_FOUND_MSG.format(n=len(result)) if result else COVER_NONE_MSG)
            self._list_version = -1   # 줄 색을 다시 칠한다
            self.refresh()

        self.runner.run_async(work, done)

    def no_cover_rows(self) -> list[int]:
        return [i for i, t in enumerate(self.controller.playlist.tracks) if id(t) in self._no_cover]

    def select_missing_covers(self) -> None:
        rows = self.no_cover_rows()
        if rows:
            self.select_rows(rows)

    def add_missing_covers(self) -> None:
        rows = self.no_cover_rows()
        if rows:
            self.select_rows(rows)
            self.show_bulk_tags(rows, TAB_COVERS)

    def clear_cover_marks(self) -> None:
        self._no_cover = {}
        self._list_version = -1
        self.refresh()

    def _recheck_covers(self) -> None:
        """그림을 넣었을 수 있으니 붉은 곡만 다시 본다. 목록에서 빠진 곡은 표시도 뺀다."""
        if not self._no_cover:
            return
        alive = {id(t) for t in self.controller.playlist.tracks}
        self._no_cover = {k: t for k, t in self._no_cover.items() if k in alive and not self._has_cover(t.path)}
        self._list_version = -1

    def save_favorites(self) -> None:
        if not self._settings.favorites:
            return
        path = QFileDialog.getSaveFileName(self, "즐겨찾기 저장", "즐겨찾기.m3u8", "재생목록 (*.m3u8)")[0]
        if path:
            self.controller.save_favorites(path)
            self.refresh()

    def load_favorites(self) -> None:
        path = QFileDialog.getOpenFileName(self, "즐겨찾기 불러오기", "", "재생목록 (*.m3u8 *.m3u)")[0]
        if path:
            self.controller.load_favorites(path)
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
        if self._tab != "playlist":   # 보이지 않는 재생목록 줄을 지우지 않게
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
        if self._tab != "playlist":
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
        editable, note = self._edit_state(info.path)
        self._show_info(info, load_cover(info), editable, note)

    @staticmethod
    def _edit_state(path: str) -> tuple[bool, str]:
        if not path.lower().endswith(".mp3"):
            return False, "MP3만 고칠 수 있습니다"
        if not os.path.isfile(path):
            return False, "파일이 없습니다"
        return True, ""

    def _station_info(self) -> TrackInfo:
        # 형식 칸(codec·sample_rate·channels)은 디코더가 밖으로 내주지 않아 비워 둔다
        s = self.radio.current
        path = DOMESTIC_INFO_PATH if s.kind in ("kbs", "mbc", "sbs") else s.key
        return TrackInfo(path=path, title=s.name, artist=s.source)

    def _show_info(self, info: TrackInfo, cover, editable: bool = False, note: str = "") -> None:
        if self.info_dialog is None:
            dialog = TrackInfoDialog(self)
            dialog.set_services(self.runner.run_async, musicbrainz.default_client)
            dialog.set_rename_checked(self._settings.rename_on_save)
            dialog.rename_toggled.connect(lambda on: setattr(self._settings, "rename_on_save", on))
            dialog.undo_rename_requested.connect(self._undo_from_dialog)
            dialog.save_requested.connect(self._save_tags)
            dialog.clear_requested.connect(self._clear_tags)
            self.info_dialog = dialog
        if not self.info_dialog.show_info(info, cover, editable, note):
            return
        self.info_dialog.show()
        self.info_dialog.raise_()
        self.info_dialog.activateWindow()

    @staticmethod
    def _elide(name: str, limit: int = 40) -> str:
        return name if len(name) <= limit else name[:limit - 1] + "…"

    def _save_tags(self, path: str, fields: dict, picture) -> None:
        target = self.info_dialog.rename_target()
        if target is None:
            self._edit_tags(lambda: self.controller.save_tags(path, fields, picture))
            return
        self._edit_tags(lambda: self.controller.save_and_rename(path, fields, picture, target))

    def undo_rename_from_menu(self) -> None:
        self._undo_rename(from_menu=True)

    def _undo_from_dialog(self, old: str, new: str) -> None:
        if self.controller.last_rename() != (old, new):   # 그 사이 다른 이름 바꾸기가 있었다
            self.info_dialog.clear_undo()
            return
        self._undo_rename()

    def _undo_rename(self, from_menu: bool = False) -> None:
        last = self.controller.last_rename()
        if last is None:
            return
        shown_new = last[1]
        dialog = self.info_dialog
        with self._busy_cursor():
            old, text = self.controller.undo_rename()
        if dialog is not None:
            showing = (dialog.isVisible()
                       and os.path.normcase(dialog.path) == os.path.normcase(shown_new))
            if old is not None and showing:
                info = self._info_for_path(old)
                dialog.renamed_back(info, load_cover(info))   # 고치던 칸이 있으면 renamed_back이 지킨다
            elif old is None and showing:   # 다른 곡을 보고 있으면 상태 줄 알림만
                dialog.failed(text)
            if from_menu:
                dialog.clear_undo()
        self._after_file_edit()

    def _info_for_path(self, path: str) -> TrackInfo:
        for i, t in enumerate(self.controller.playlist.tracks):
            if os.path.normcase(t.path) == os.path.normcase(path):
                return self.controller.info_for(i)
        return tags.read_info(path)

    def _clear_tags(self, path: str) -> None:
        self._edit_tags(lambda: self.controller.clear_tags(path))

    def _edit_tags(self, write) -> None:
        dialog = self.info_dialog
        try:
            with self._busy_cursor():
                result = write()
        except (TagWriteError, RenameError) as e:
            dialog.failed(str(e))
            return
        if isinstance(result, TrackInfo):
            dialog.saved(result, load_cover(result))
        else:   # 저장+이름 바꾸기 결과
            dialog.saved(result.info, load_cover(result.info), result.renamed_from, result.warning)
        self._after_file_edit()

    @staticmethod
    @contextmanager
    def _busy_cursor():
        QApplication.setOverrideCursor(Qt.WaitCursor)   # 큰 파일·느린 드라이브에서 멈춘 게 아님을 보인다
        try:
            yield
        finally:
            QApplication.restoreOverrideCursor()

    def _after_file_edit(self) -> None:
        self._cover_key = object()   # 큰 앨범 그림을 다시 읽게 한다
        self._recheck_covers()
        self.refresh()

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
                self._art_radio = True
                self._art_changed()
        else:
            key = c.info.path if c.info else None
            if key != self._cover_key:
                self._cover_key = key
                self._cover_src = load_cover(c.info) if c.info else None
                self._art_radio = False
                self._art_changed()
        self._refresh_live(on_radio)
        shown = self.seek_slider.value() / 1000 if self._dragging else position
        self.elapsed_label.setText(format_time(shown))
        self.total_label.setText(format_time(duration))

        seek = self.seek_slider
        seek.setRange(0, int(duration * 1000))
        if not self._dragging:
            seek.setValue(int(position * 1000))
        seek.setEnabled(c.can_seek and duration > 0)

        # 컨트롤러가 곡을 바꾸며 이미 효과를 맞췄을 수도 있어(sync가 False) 장르 표시는 매번 맞춘다 (같으면 아무 일 없음)
        c.sync_effects()
        self.fx_strip.set_genre_preset(c.genre_preset)

        playing = self._refresh_icons()
        ratio = 1.0 if on_radio else (position / duration if duration > 0 else 0.0)
        self.now_strip.set_track(self._strip_art, c.title, LIVE_TEXT if on_radio else c.subtitle,
                                 playing, ratio)

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
        if pl.index != self._followed_index:
            # 곡이 바뀌면(무작위 포함) 그 줄이 보이게 굴린다. 이미 보이면 움직이지 않는다
            self._followed_index = pl.index
            item = self.playlist_view.item(pl.index) if pl.index is not None else None
            if item is not None:
                self.playlist_view.scrollToItem(item, QAbstractItemView.EnsureVisible)

        self.repeat_button.setEnabled(not on_radio)
        self.shuffle_button.setEnabled(not on_radio)
        if self._tab != "radio":
            self._update_count()   # 방송 수는 탭 바꿀 때와 목록이 바뀔 때만 센다
        self._refresh_status_color()
        self._set_elided(self.status_label, c.status)

    def _refresh_status_color(self) -> None:
        """안내 줄은 창 바탕(bg) 위에 놓인다. 오류는 색이 비슷해 보여도 구분되게 굵게 쓴다."""
        error = self.controller.status_error
        if error == self._status_error:
            return
        self._status_error = error
        theme = self._applied_theme
        look = f"color: {error_color(theme.bg)}; font-weight: 700;" if error else f"color: {theme.mute};"
        self.status_label.setStyleSheet(look)

    def _refresh_icons(self) -> bool:
        """재생·소리·하트·반복 그림을 상태에 맞춘다 (바뀔 때만 다시 그린다). 재생 중인지 돌려준다."""
        c = self.controller
        hero = self._hero
        on_radio = c.source == "radio"
        playing = self.radio.state is not RadioState.IDLE if on_radio else c.state is State.PLAYING
        if playing != self._play_key:
            self._play_key = playing
            self._set_glyph(self.play_button, "pause" if playing else "play", hero.on_acc)
            self.play_button.setToolTip("일시정지" if playing else "재생")
        if c.muted != self._mute_key:
            self._mute_key = c.muted
            self._set_glyph(self.mute_button, "volX" if c.muted else "volL", hero.icon)
            self.mute_button.setToolTip("음소거 해제" if c.muted else "음소거")
        if on_radio:
            station = self.radio.current
            known = station is not None
            favorite = known and self.stations.is_favorite(station.id)
        else:
            track = c.playlist.current
            known = track is not None
            favorite = known and self._track_is_favorite(track.path)
        self.heart_button.setEnabled(known)
        self.heart_button.setChecked(favorite)
        if favorite != self._heart_key:
            self._heart_key = favorite
            self._set_glyph(self.heart_button, "heartOn" if favorite else "heart",
                            hero.fav if favorite else hero.icon)
        self._refresh_modes()
        return playing

    def _track_is_favorite(self, path: str) -> bool:
        # refresh가 200ms마다 부른다: 곡이나 즐겨찾기가 바뀔 때만 긴 목록을 다시 본다
        key = (path, self._settings.favorites_version)
        if key != self._track_fav_key:
            self._track_fav_key = key
            self._track_fav = self.controller.is_favorite(path)
        return self._track_fav

    def _refresh_live(self, on_radio: bool) -> None:
        r = self.radio
        marked = r.current.id if on_radio and r.current is not None else None
        if marked != self._marked_station:
            self._marked_station = marked
            self.station_view.set_current(marked)
        if not on_radio:
            return
        # 색은 라디오 상태를 따른다 (B에 연결하는 동안 플레이어는 아직 라이브다)
        hero = self._hero   # 지금 놓인 면(지금 재생 또는 미니 막대)의 색
        color = hero.acc_t if r.state in (RadioState.LIVE, RadioState.RETRYING) else hero.mute
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
            hero = self._hero
            self._set_glyph(self.repeat_button, "repeat1" if mode == "one" else "repeat",
                            hero.ic2 if mode == "off" else hero.acc_t)
            self._set_glyph(self.shuffle_button, "shuffle", hero.acc_t if shuffle else hero.ic2)
            for b, on in ((self.repeat_button, mode != "off"), (self.shuffle_button, shuffle)):
                b.setProperty("active", "true" if on else "false")
                self._repolish(b)

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
        favs = self.controller.favorite_keys()
        for i, track in enumerate(pl.tracks):
            item = QListWidgetItem()
            self._style_item(item, i, track, i == pl.index, path_key(track.path) in favs,
                             id(track) in self._no_cover)
            view.addItem(item)
        view.doItemsLayout()
        bar.setValue(scroll)
        view.setUpdatesEnabled(True)

    def _repaint_rows(self) -> None:
        pl = self.controller.playlist
        favs = self.controller.favorite_keys()
        for i, track in enumerate(pl.tracks):
            item = self.playlist_view.item(i)
            if item is not None:
                self._style_item(item, i, track, i == pl.index, path_key(track.path) in favs,
                                 id(track) in self._no_cover)

    @staticmethod
    def _style_item(item: QListWidgetItem, i: int, track, current: bool, favorite: bool = False,
                    no_cover: bool = False) -> None:
        mark = "▶" if current else "  "
        item.setText(f"{mark} {i + 1:>2}   {track.title}")
        item.setData(ROLE_NUMBER, i + 1)
        item.setData(ROLE_TITLE, track.title)
        item.setData(ROLE_CURRENT, current)
        item.setData(ROLE_FAVORITE, favorite)
        font = item.font()
        font.setBold(current)
        item.setFont(font)
        if track.failed or track.missing:
            color = QColor(Qt.gray)
        elif no_cover:
            color = QColor(ERROR_COLOR)   # '그림 없는 곡 찾기'로 표시한 곡 (임시)
        else:
            color = QColor(FAVORITE_COLOR) if favorite else None
        item.setData(Qt.ForegroundRole, color)

    # ---- 끝내기 ----

    def closeEvent(self, event) -> None:
        # 곡 정보 창에 저장 안 한 내용이 있으면 끝내기 전에 묻는다 (아니라고 하면 창을 닫지 않는다)
        dialog = self.info_dialog
        if dialog is not None and dialog.is_dirty() and not dialog.confirm_discard():
            event.ignore()
            return
        super().closeEvent(event)

    def shutdown(self) -> None:
        self._closed = True
        self.controller.save_session()
        # 기다리던 연결·다시 연결이 끈 뒤에 돌지 않게 먼저 멈춘다 (라디오는 플레이어를 닫지 않는다)
        self.radio.shutdown()
        self.runner.shutdown()
        self.media_keys.disable()
        self._timer.stop()
        self._spectrum_timer.stop()
        self._player.close()
