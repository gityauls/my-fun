"""Now-playing strip at the bottom of the non-now tabs (stage 5.5)."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPainter, QPixmap
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from funplayer.core.themes import DEFAULT_THEME, Theme, get_theme
from funplayer.ui.glyphs import glyph
from funplayer.ui.style import css_color

ART_SIZE = 40
ART_RADIUS = 9
BAR_HEIGHT = 3
ROW_HEIGHT = 58
ICON_SIZE = 18
PLAY_SIZE = 36


class _ClickLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _Progress(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(BAR_HEIGHT)
        self.ratio = 0.0
        self.set_theme(get_theme(DEFAULT_THEME))

    def set_theme(self, theme: Theme) -> None:
        self._track = css_color(theme.track)
        self._fill = css_color(theme.acc)
        self.update()

    def set_ratio(self, ratio: float) -> None:
        ratio = max(0.0, min(1.0, ratio))
        moved = int(ratio * self.width()) != int(self.ratio * self.width())
        self.ratio = ratio
        if moved:
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), self._track)
        p.fillRect(0, 0, int(self.ratio * self.width()), self.height(), self._fill)
        p.end()


class NowStrip(QWidget):
    prevClicked = pyqtSignal()
    toggleClicked = pyqtSignal()
    nextClicked = pyqtSignal()
    openClicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("nowStrip")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFixedHeight(BAR_HEIGHT + ROW_HEIGHT)
        self._theme = get_theme(DEFAULT_THEME)
        self._art_key: int | None = None
        self._playing: bool | None = None
        self._title = self._sub = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.progress = _Progress()
        root.addWidget(self.progress)
        row = QHBoxLayout()
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)
        root.addLayout(row, 1)

        self.art_label = _ClickLabel()
        self.art_label.setFixedSize(ART_SIZE, ART_SIZE)
        self.art_label.setToolTip("곡 정보")
        self.art_label.setCursor(Qt.PointingHandCursor)
        self.art_label.clicked.connect(self.openClicked)
        row.addWidget(self.art_label)

        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.setAlignment(Qt.AlignVCenter)
        self.title_label = self._text_label(13, True)
        self.sub_label = self._text_label(11, False)
        self.sub_label.setProperty("role", "mute")
        texts.addWidget(self.title_label)
        texts.addWidget(self.sub_label)
        row.addLayout(texts, 1)

        self.prev_button = self._button("이전 곡", 34)
        self.toggle_button = self._button("재생", PLAY_SIZE, "playSm")
        self.next_button = self._button("다음 곡", 34)
        for b in (self.prev_button, self.toggle_button, self.next_button):
            row.addWidget(b)
        self.prev_button.clicked.connect(self.prevClicked)
        self.toggle_button.clicked.connect(self.toggleClicked)
        self.next_button.clicked.connect(self.nextClicked)
        self._icons()

    @staticmethod
    def _text_label(px: int, bold: bool) -> QLabel:
        label = QLabel()
        font = QFont(label.font())
        font.setPixelSize(px)
        font.setBold(bold)
        label.setFont(font)
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        label.setMinimumWidth(0)
        return label

    @staticmethod
    def _button(tip: str, size: int, kind: str = "") -> QPushButton:
        b = QPushButton()
        b.setToolTip(tip)
        b.setFixedSize(size, size)
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        b.setFocusPolicy(Qt.TabFocus)
        if kind:
            b.setProperty("kind", kind)
        return b

    def _icons(self) -> None:
        t = self._theme
        self.prev_button.setIcon(glyph("prev", t.icon, ICON_SIZE))
        self.next_button.setIcon(glyph("next", t.icon, ICON_SIZE))
        self._toggle_icon()

    def _toggle_icon(self) -> None:
        name = "pause" if self._playing else "play"
        self.toggle_button.setIcon(glyph(name, self._theme.on_acc, ICON_SIZE))
        self.toggle_button.setToolTip("일시정지" if self._playing else "재생")

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.progress.set_theme(theme)
        self._icons()

    def set_track(self, pixmap: QPixmap, title: str, subtitle: str, playing: bool,
                  ratio: float) -> None:
        # refresh가 200ms마다 부른다: 바뀐 것만 다시 넣는다
        key = pixmap.cacheKey()
        if key != self._art_key:
            self._art_key = key
            self.art_label.setPixmap(pixmap)
        self._set_text(self.title_label, title)
        self._set_text(self.sub_label, subtitle)
        if bool(playing) != self._playing:
            self._playing = bool(playing)
            self._toggle_icon()
        self.progress.set_ratio(ratio)

    @staticmethod
    def _set_text(label: QLabel, text: str) -> None:
        if label.toolTip() != text:
            label.setToolTip(text)
        shown = text
        if label.isVisible():
            shown = label.fontMetrics().elidedText(text, Qt.ElideRight, label.width())
        if label.text() != shown:
            label.setText(shown)
