from __future__ import annotations

from PyQt5.QtCore import QObject, QRect, Qt
from PyQt5.QtGui import QGuiApplication

DEFAULT_SIZE = (380, 480)
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
        self._apply(panel.is_mini)
        self._apply_on_top()
        panel.miniChanged.connect(self._on_mini)
        panel.miniOnTopChanged.connect(self._apply_on_top)

    def save(self) -> None:
        self._store(self._panel.is_mini)

    def _store(self, mini: bool) -> None:
        g = self._panel.geometry()
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
        if mini:
            panel.setFixedHeight(panel.sizeHint().height())
            saved = self._settings.mini_geometry
            x, y, w = (saved[0], saved[1], saved[2]) if saved else (panel.x(), panel.y(), panel.width())
            rect = QRect(x, y, w, panel.height())
        else:
            panel.setMinimumHeight(0)
            panel.setMaximumHeight(_QWIDGETSIZE_MAX)
            saved = self._settings.geometry
            if saved:
                rect = QRect(*saved)
            else:
                rect = QRect(0, 0, *DEFAULT_SIZE)
                self._center(rect)
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
