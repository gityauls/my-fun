"""음향 효과 탭의 빈 곳을 채우는 움짤. 탭이 보이는 동안 늘 움직인다."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QMovie, QPainter, QPainterPath
from PyQt5.QtWidgets import QSizePolicy, QWidget

GIF = Path(__file__).resolve().parent.parent / "assets" / "eggs" / "fx_moonwalk.gif"
MIN_HEIGHT = 80   # 이보다 작으면 인물이 뭉개져 그리지 않는다
RADIUS = 12
LIGHTEN = .82     # 인물이 검은 옷이라 어떤 테마에서도 카드는 밝게 둔다


class FxStage(QWidget):
    def __init__(self, parent=None, path: Path = GIF) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._card = QColor("#FFFFFF")
        self.movie = QMovie(str(path), parent=self)
        self.movie.frameChanged.connect(self._new_frame)
        self.dancing = False
        if self.movie.isValid():
            self.movie.jumpToFrame(0)

    def _new_frame(self, _number: int) -> None:
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(0, 0)     # 남는 자리만 쓴다

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def showEvent(self, event) -> None:
        self.set_dancing(True)
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self.set_dancing(False)
        super().hideEvent(event)

    def set_accent(self, color: str) -> None:
        base = QColor(color)
        mix = lambda v: round(v + (255 - v) * LIGHTEN)
        self._card = QColor(mix(base.red()), mix(base.green()), mix(base.blue()))
        self.update()

    def set_dancing(self, on: bool) -> None:
        on = on and self.movie.isValid()
        if on == self.dancing:
            return
        self.dancing = on
        if not on:
            self.movie.setPaused(True)
        elif self.movie.state() == QMovie.Paused:
            self.movie.setPaused(False)
        else:
            self.movie.start()

    def picture_rect(self) -> QRectF:
        """그림 비율을 지키며 카드 안에 맞춘다."""
        size = self.movie.currentPixmap().size()
        if size.isEmpty():
            return QRectF()
        scale = min(self.width() / size.width(), self.height() / size.height())
        w, h = size.width() * scale, size.height() * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, event) -> None:
        if self.height() < MIN_HEIGHT or not self.movie.isValid():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), RADIUS, RADIUS)
        p.fillPath(clip, self._card)
        p.setClipPath(clip)
        p.drawPixmap(self.picture_rect(), self.movie.currentPixmap(), QRectF(self.movie.currentPixmap().rect()))
        p.end()
