from __future__ import annotations

from PyQt5.QtCore import QObject, QRect, QSize, Qt
from PyQt5.QtGui import QGuiApplication

DEFAULT_SIZE = (380, 620)
# 높이: 지금 재생 탭 + 안내 줄이 실제로 603 (상단바 44, 탭 64, 페이지 470, 안내 23, 테두리 2). 글꼴 차이 몫을 조금 더한다
MIN_SIZE = (340, 610)
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
        g = panel.normalGeometry() if panel.isMaximized() else panel.geometry()
        rect = [g.x(), g.y(), g.width(), g.height()]
        if mini:
            self._settings.mini_geometry = rect
        else:
            self._settings.geometry = rect

    def _on_mini(self, on: bool) -> None:
        self._store(not on)
        if on and self._panel.isMaximized():
            self._panel.showNormal()
        self._apply(on)
        self._apply_on_top()

    def _apply(self, mini: bool) -> None:
        panel = self._panel
        # 앞 모드의 고정 크기를 풀고 배치를 다시 계산해야 sizeHint와 최소 크기가 지금 모드를 따른다
        panel.setMinimumSize(0, 0)
        panel.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
        panel.layout().activate()
        if mini:
            panel.setFixedHeight(panel.sizeHint().height())
            saved = self._settings.mini_geometry or self._settings.geometry
            if saved:
                rect = QRect(saved[0], saved[1], saved[2], panel.height())
            else:
                rect = QRect(0, 0, DEFAULT_SIZE[0], panel.height())
                self._center(rect)
        else:
            saved = self._settings.geometry
            if saved:
                rect = QRect(*saved)
                rect.setSize(rect.size().expandedTo(QSize(*MIN_SIZE)))   # 옛 버전이 저장한 작은 창
            else:
                rect = QRect(0, 0, *DEFAULT_SIZE)
                self._center(rect)
            panel.setMinimumSize(*MIN_SIZE)
        if QGuiApplication.screenAt(rect.center()) is None:
            self._center(rect)
        panel.setGeometry(rect)

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
