from __future__ import annotations

from PyQt5.QtCore import QObject, QPoint, QRect, QSize, Qt
from PyQt5.QtGui import QGuiApplication

DEFAULT_SIZE = (380, 680)
# 높이: 맑은 고딕으로 잰 지금 재생 탭 + 안내 줄은 643이다. 몇 픽셀 여유를 둔다
MIN_SIZE = (340, 650)
MAX_SIZE = (460, 780)   # 보통 창은 이 안에서만 늘어난다. 작게 보기의 폭은 묶지 않는다
MINI_SIZE = (830, 104)
_QWIDGETSIZE_MAX = 16777215


class WindowKeeper(QObject):
    """Remembers the window place per mode and keeps it on top in mini mode."""

    def __init__(self, panel, settings) -> None:
        super().__init__(panel)
        self._panel = panel
        self._settings = settings

    def start(self) -> None:
        panel = self._panel
        if self._settings.mini:
            panel.set_mini(True)
        # 항상 위 플래그를 먼저: 자리를 잡은 뒤 플래그를 바꾸면 Qt가 숨은 창을 move해 자리가 틀 기준이 된다
        self._apply_on_top()
        self._apply(panel.is_mini)
        panel.miniChanged.connect(self._on_mini)
        panel.miniOnTopChanged.connect(self._apply_on_top)

    def save(self) -> None:
        self._store(self._panel.is_mini)

    def _store(self, mini: bool) -> None:
        panel = self._panel
        g = panel.geometry()
        rect = [g.x(), g.y(), g.width(), g.height()]
        if mini:
            self._settings.mini_geometry = rect
        else:
            self._settings.geometry = rect

    def _on_mini(self, on: bool) -> None:
        self._store(not on)
        self._apply(on)
        self._apply_on_top()

    def _apply(self, mini: bool) -> None:
        panel = self._panel
        # 앞 모드의 고정 크기를 풀고 배치를 다시 계산해야 sizeHint와 최소 크기가 지금 모드를 따른다
        panel.setMinimumSize(0, 0)
        panel.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
        panel.layout().activate()
        if mini:
            panel.setFixedHeight(MINI_SIZE[1])
            panel.setMinimumWidth(MINI_SIZE[0])
            saved = self._settings.mini_geometry or self._settings.geometry
            if saved:   # 폭만 기억한다. 옛 버전이 저장한 작은 막대는 늘린다
                rect = QRect(saved[0], saved[1], max(saved[2], MINI_SIZE[0]), MINI_SIZE[1])
            else:
                rect = QRect(0, 0, *MINI_SIZE)
                self._center(rect)
        else:
            saved = self._settings.geometry
            if saved:
                rect = QRect(*saved)
                # 옛 버전이 저장한 작거나 큰 창
                rect.setSize(rect.size().expandedTo(QSize(*MIN_SIZE)).boundedTo(QSize(*MAX_SIZE)))
            else:
                rect = QRect(0, 0, *DEFAULT_SIZE)
                self._center(rect)
            panel.setMinimumSize(*MIN_SIZE)
            panel.setMaximumSize(*MAX_SIZE)
        if QGuiApplication.screenAt(rect.center()) is None:
            self._center(rect)
        if mini:
            self._fit_width(rect)
        self._fit_height(rect)
        panel.setGeometry(rect)

    @staticmethod
    def _fit_width(rect: QRect) -> None:
        """막대 양 끝이 화면 밖이면 들어오게 민다 (옛 작은 창 자리에서 늘어났을 때). 두 화면에 걸친 것은 둔다."""
        if QGuiApplication.screenAt(rect.topLeft()) and QGuiApplication.screenAt(rect.topRight()):
            return
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        rect.moveLeft(max(area.left(), min(rect.left(), area.right() + 1 - rect.width())))

    @staticmethod
    def _fit_height(rect: QRect) -> None:
        """아래쪽이 작업 영역 밖이면 들어오게 민다 (옛 작은 창 자리에서 늘어났을 때).
        위아래 두 화면에 걸친 창과 작업 영역보다 큰 창은 둔다."""
        x = rect.center().x()
        top = QGuiApplication.screenAt(QPoint(x, rect.top()))
        bottom = QGuiApplication.screenAt(QPoint(x, rect.bottom()))
        if top is not None and bottom is not None and top != bottom:
            return
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        if rect.height() <= area.height():
            rect.moveTop(max(area.top(), min(rect.top(), area.bottom() + 1 - rect.height())))

    @staticmethod
    def _center(rect: QRect) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            rect.moveCenter(screen.availableGeometry().center())

    def _apply_on_top(self, *_args) -> None:
        panel = self._panel
        want = panel.is_mini and self._settings.mini_on_top
        if bool(panel.windowFlags() & Qt.WindowStaysOnTopHint) == want:
            return
        was = panel.isVisible()
        panel.setWindowFlag(Qt.WindowStaysOnTopHint, want)
        if was:
            panel.show()
