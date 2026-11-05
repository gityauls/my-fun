"""Tab bar with an icon above each title (stage 5.5). Same small API as QTabBar."""
from __future__ import annotations

from PyQt5.QtCore import QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPainter, QPainterPath
from PyQt5.QtWidgets import QButtonGroup, QHBoxLayout, QSizePolicy, QToolButton, QWidget

from funplayer.core.themes import DEFAULT_THEME, Theme, get_theme
from funplayer.ui.glyphs import glyph_pixmap
from funplayer.ui.style import css_color

TAB_HEIGHT = 64
ICON_SIZE = 20
LINE_INSET = 12
LINE_HEIGHT = 3
_BORDER = 1   # #tabs 아래 테두리. 밑줄은 그 위에 얹는다


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
        self.update()

    def _icon(self, name: str) -> QIcon:
        t = self._theme
        icon = QIcon()
        icon.addPixmap(glyph_pixmap(name, t.tab_fg, ICON_SIZE), QIcon.Normal, QIcon.Off)
        icon.addPixmap(glyph_pixmap(name, t.tab_on, ICON_SIZE), QIcon.Normal, QIcon.On)
        return icon

    def _toggled(self, i: int, on: bool) -> None:
        if on and i != self._current:
            self._current = i
            self.update()
            self.currentChanged.emit(i)

    def underline_rect(self) -> QRect:
        b = self._buttons[self._current]
        return QRect(b.x() + LINE_INSET, self.height() - _BORDER - LINE_HEIGHT,
                     b.width() - 2 * LINE_INSET, LINE_HEIGHT)

    def paintEvent(self, event) -> None:
        """고른 탭의 밑줄. 양옆을 띄우고 위쪽 모서리만 둥근 선은 QSS로 그릴 수 없다.
        단추는 배경이 투명해 그 아래에서 그려도 보인다."""
        if not self._buttons:
            return
        rect = self.underline_rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect).adjusted(0, 0, 0, LINE_HEIGHT), LINE_HEIGHT, LINE_HEIGHT)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setClipRect(rect)   # 둥근 사각형의 아래 절반을 잘라 위쪽 모서리만 남긴다
        p.fillPath(path, css_color(self._theme.tab_line))
        p.end()
