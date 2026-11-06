"""A label that scrolls sideways when its text does not fit (round 3 of stage 5.5)."""
from __future__ import annotations

from PyQt5.QtCore import QEvent, QRectF, Qt, QTimer
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QLabel

TICK_MS = 28       # 한 칸(1px)을 움직이는 간격: 초당 약 36px
HOLD_TICKS = 72    # 처음 글자를 읽을 시간 (약 2초)
GAP = 48           # 글 끝과 다시 시작하는 글 사이


class TickerLabel(QLabel):
    """text()는 언제나 전체 글이다. 칸에 다 들어가면 보통 라벨과 똑같다."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.offset = 0
        self._hold = HOLD_TICKS
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)

    @property
    def overflowing(self) -> bool:
        return self.fontMetrics().horizontalAdvance(self.text()) > self.width()

    @property
    def moving(self) -> bool:
        return self._timer.isActive()

    def setText(self, text: str) -> None:
        if text == self.text():   # refresh가 200ms마다 부른다: 같은 글이면 흐름을 끊지 않는다
            return
        super().setText(text)
        self.offset = 0
        self._hold = HOLD_TICKS
        self._sync()
        self.update()

    def _sync(self) -> None:
        run = self.isVisible() and self.overflowing
        if run and not self._timer.isActive():
            self._timer.start()
        elif not run and self._timer.isActive():
            self._timer.stop()
            self.offset = 0
            self._hold = HOLD_TICKS
            self.update()

    def _tick(self) -> None:
        if not self.window().isMinimized():
            self.advance()

    def advance(self) -> None:
        """한 칸 움직인다. 한 바퀴를 돌면 처음 자리에서 다시 멈춘다."""
        if self._hold > 0:
            self._hold -= 1
            return
        self.offset += 1
        if self.offset >= self.fontMetrics().horizontalAdvance(self.text()) + GAP:
            self.offset = 0
            self._hold = HOLD_TICKS
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._sync()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.FontChange:
            self._sync()

    def paintEvent(self, event) -> None:
        if not self.overflowing:
            super().paintEvent(event)
            return
        text = self.text()
        width = self.fontMetrics().horizontalAdvance(text)
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        rect = QRectF(self.rect())
        rect.setWidth(width + 2)
        rect.moveLeft(-self.offset)
        p.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        if self.offset:   # 글 끝이 지나가면 뒤따라오는 같은 글
            rect.moveLeft(width + GAP - self.offset)
            p.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        p.end()
