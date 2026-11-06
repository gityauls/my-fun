"""Clear side buttons that appear only under the mouse (theme flip beside the cover)."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QPushButton

from funplayer.ui.glyphs import glyph_pixmap

ICON_SIZE = 36   # 표지 216의 6분의 1
OPACITY = 0.6


class HoverArrow(QPushButton):
    def __init__(self, name: str, tip: str, icon_size: int = ICON_SIZE, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("themeArrow")
        self._name = name
        self._icon = QIcon()
        self.setToolTip(tip)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self._size = icon_size
        self.setIconSize(QSize(icon_size, icon_size))

    def set_color(self, color: str) -> None:
        pm = QPixmap(self._size, self._size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setOpacity(OPACITY)
        p.drawPixmap(0, 0, glyph_pixmap(self._name, color, self._size))
        p.end()
        self._icon = QIcon(pm)
        self.setIcon(self._icon if self.underMouse() else QIcon())

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self.setIcon(self._icon)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.setIcon(QIcon())
