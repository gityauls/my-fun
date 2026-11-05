"""Tab bar with an icon above each title (stage 5.5). Same small API as QTabBar."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QButtonGroup, QHBoxLayout, QSizePolicy, QToolButton, QWidget

from funplayer.core.themes import DEFAULT_THEME, Theme, get_theme
from funplayer.ui.glyphs import glyph_pixmap

TAB_HEIGHT = 64
ICON_SIZE = 20


class IconTabs(QWidget):
    currentChanged = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tabs")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFixedHeight(TAB_HEIGHT)
        self._theme = get_theme(DEFAULT_THEME)
        self._buttons: list[QToolButton] = []
        self._names: list[str] = []
        self._current = -1
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(10, 0, 10, 0)
        self._row.setSpacing(0)

    def addTab(self, icon_name: str, title: str) -> int:
        i = len(self._buttons)
        b = QToolButton()
        b.setText(title)
        b.setCheckable(True)
        b.setFocusPolicy(Qt.NoFocus)   # 탭을 눌러도 키보드 초점은 그대로
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        b.setIcon(self._icon(icon_name))
        self._buttons.append(b)
        self._names.append(icon_name)
        self._group.addButton(b, i)
        self._row.addWidget(b)
        if i == 0:
            self._current = 0
            b.setChecked(True)
        b.toggled.connect(lambda on, n=i: self._toggled(n, on))
        return i

    def count(self) -> int:
        return len(self._buttons)

    def tabText(self, i: int) -> str:
        return self._buttons[i].text()

    def currentIndex(self) -> int:
        return self._current

    def setCurrentIndex(self, i: int) -> None:
        if 0 <= i < len(self._buttons):
            self._buttons[i].setChecked(True)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        for b, name in zip(self._buttons, self._names):
            b.setIcon(self._icon(name))

    def _icon(self, name: str) -> QIcon:
        t = self._theme
        icon = QIcon()
        icon.addPixmap(glyph_pixmap(name, t.tab_fg, ICON_SIZE), QIcon.Normal, QIcon.Off)
        icon.addPixmap(glyph_pixmap(name, t.tab_on, ICON_SIZE), QIcon.Normal, QIcon.On)
        return icon

    def _toggled(self, i: int, on: bool) -> None:
        if on and i != self._current:
            self._current = i
            self.currentChanged.emit(i)
