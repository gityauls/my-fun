"""Title bar and resize grips for the frameless window (stage 5.5).

The panel keeps the bar even without a frame; only `EdgeGrips` belongs to the frameless window.
Moving and resizing go through QWindow so Windows does the work (snap, multi monitor).
"""
from __future__ import annotations

from PyQt5.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QWidget

from funplayer.core.themes import DEFAULT_THEME, Theme, get_theme
from funplayer.ui.glyphs import glyph, glyph_pixmap

TITLE_HEIGHT = 44
APP_ICON_SIZE = 18
BUTTON_SIZE = (30, 28)
MAX_TIPS = {False: "최대화", True: "이전 크기로"}
_ICONS = (("mini_btn", "shrink", 15), ("min_btn", "min", 16), ("max_btn", "max", 14), ("close_btn", "x", 16))


class TitleBar(QWidget):
    miniClicked = pyqtSignal()
    minimizeClicked = pyqtSignal()
    maximizeClicked = pyqtSignal()
    closeClicked = pyqtSignal()
    menu_requested = pyqtSignal(QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFixedHeight(TITLE_HEIGHT)
        self._press: QPoint | None = None
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(8)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(APP_ICON_SIZE, APP_ICON_SIZE)
        self.title_label = QLabel("my-fun")
        for w in (self.icon_label, self.title_label):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)   # 글자 위에서도 창을 끈다
        row.addWidget(self.icon_label)
        row.addWidget(self.title_label)
        row.addStretch(1)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        row.addLayout(buttons)
        self.mini_btn = self._button(buttons, "작게 보기", self.miniClicked)
        self.min_btn = self._button(buttons, "최소화", self.minimizeClicked)
        self.max_btn = self._button(buttons, MAX_TIPS[False], self.maximizeClicked)
        self.close_btn = self._button(buttons, "닫기", self.closeClicked)
        self.set_theme(get_theme(DEFAULT_THEME))

    @staticmethod
    def _button(row: QHBoxLayout, tip: str, signal) -> QPushButton:
        b = QPushButton()
        b.setFixedSize(*BUTTON_SIZE)
        b.setFocusPolicy(Qt.NoFocus)   # 눌러도 키보드 초점을 뺏지 않는다
        b.setToolTip(tip)
        b.clicked.connect(lambda _=False: signal.emit())
        row.addWidget(b)
        return b

    def set_theme(self, theme: Theme) -> None:
        self.icon_label.setPixmap(glyph_pixmap("head", theme.bar_fg, APP_ICON_SIZE))
        for attr, name, size in _ICONS:
            b = getattr(self, attr)
            b.setIcon(glyph(name, theme.bar_fg, size))
            b.setIconSize(QSize(size, size))

    def set_maximized(self, on: bool) -> None:
        self.max_btn.setToolTip(MAX_TIPS[bool(on)])

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        # 누르는 순간이 아니라 끌기 시작할 때 맡긴다: 누를 때 맡기면 Windows가 더블클릭을 삼킨다
        press = self._press
        if (press is not None and event.buttons() & Qt.LeftButton
                and (event.pos() - press).manhattanLength() >= QApplication.startDragDistance()):
            self._press = None
            window = self.window()
            handle = window.windowHandle()
            if handle is not None and not window.isMaximized():
                handle.startSystemMove()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press = None
            self.maximizeClicked.emit()
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.menu_requested.emit(event.globalPos())


class _Grip(QWidget):
    def __init__(self, parent: QWidget, edges, cursor) -> None:
        super().__init__(parent)
        self.edges = edges
        self.setCursor(cursor)

    def paintEvent(self, event) -> None:
        # 둥근 모서리 바깥은 완전 투명이라 그대로 두면 누르기가 뒤 창으로 빠진다: 눈에 안 보이는 알파 1을 칠한다
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 1))
        p.end()

    def mousePressEvent(self, event) -> None:
        handle = self.window().windowHandle()
        if event.button() == Qt.LeftButton and handle is not None:
            handle.startSystemResize(self.edges)


class EdgeGrips(QObject):
    """Eight clear widgets over the window edges. Corners are twice as long as the edges are thick."""

    def __init__(self, window: QWidget, thickness: int = 6) -> None:
        super().__init__(window)
        self._window = window
        self._thick = thickness
        self._horizontal_only = False
        self._suspended = False
        top, bottom, left, right = Qt.TopEdge, Qt.BottomEdge, Qt.LeftEdge, Qt.RightEdge
        specs = ((top, Qt.SizeVerCursor), (bottom, Qt.SizeVerCursor),
                 (left, Qt.SizeHorCursor), (right, Qt.SizeHorCursor),
                 (top | left, Qt.SizeFDiagCursor), (bottom | right, Qt.SizeFDiagCursor),
                 (top | right, Qt.SizeBDiagCursor), (bottom | left, Qt.SizeBDiagCursor))
        self.grips = {edges: _Grip(window, edges, cursor) for edges, cursor in specs}
        window.installEventFilter(self)
        self._place()

    def set_enabled_edges(self, horizontal_only: bool) -> None:
        self._horizontal_only = bool(horizontal_only)
        self._sync_visible()

    def set_suspended(self, on: bool) -> None:
        """최대화한 창은 크기를 끌어 바꾸지 않는다."""
        self._suspended = bool(on)
        self._sync_visible()

    def _sync_visible(self) -> None:
        sides = (Qt.LeftEdge, Qt.RightEdge)
        for edges, grip in self.grips.items():
            grip.setVisible(not self._suspended and (not self._horizontal_only or edges in sides))

    def eventFilter(self, obj, event) -> bool:
        if obj is self._window and event.type() == QEvent.Resize:
            self._place()
        return False

    def _place(self) -> None:
        w, h, t = self._window.width(), self._window.height(), self._thick
        c = t * 2
        for edges, grip in self.grips.items():
            top, bottom = bool(edges & Qt.TopEdge), bool(edges & Qt.BottomEdge)
            left, right = bool(edges & Qt.LeftEdge), bool(edges & Qt.RightEdge)
            if (top or bottom) and (left or right):
                rect = QRect(w - c if right else 0, h - c if bottom else 0, c, c)
            elif top or bottom:
                rect = QRect(c, h - t if bottom else 0, w - 2 * c, t)
            else:
                rect = QRect(w - t if right else 0, c, t, h - 2 * c)
            grip.setGeometry(rect)
            grip.raise_()
