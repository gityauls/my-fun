from __future__ import annotations

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QSizePolicy, QWidget

from funplayer.ui.colors import SPECTRUM_COLOR, SPECTRUM_PEAK_COLOR
from funplayer.ui.style import css_color

PEAK_HEIGHT = 1.5


class SpectrumView(QWidget):
    """막대 스펙트럼 그림. 스스로 타이머를 갖지 않고, 바깥에서 set_levels로 값을 밀어 넣는다.
    levels/peaks는 0~1."""

    def __init__(self, bars: int = 24, parent=None) -> None:
        super().__init__(parent)
        self.bars = max(1, int(bars))
        self.hint_width = 0   # 0이면 막대 수 x 4
        self.levels = [0.0] * self.bars
        self.peaks = [0.0] * self.bars
        self._colors: tuple[str, ...] = (SPECTRUM_COLOR,)
        self._qcolors = [css_color(SPECTRUM_COLOR)]   # 한 번만 읽어 둔다
        self._peak_color = QColor(SPECTRUM_PEAK_COLOR)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

    def set_colors(self, colors, peak: str) -> None:
        """막대 색들(왼쪽부터 똑같이 나눠 쓴다)과 꼭대기 선 색. 비면 기본 색."""
        self._colors = tuple(colors) or (SPECTRUM_COLOR,)
        self._qcolors = [css_color(c) for c in self._colors]
        self._peak_color = css_color(peak)
        self.update()

    def bar_color(self, i: int, n: int) -> str:
        """n개 막대 중 i번째 막대의 색: 색 수만큼 똑같이 나눈다."""
        k = len(self._colors)
        return self._colors[min(k - 1, i * k // max(1, n))]

    def set_levels(self, levels, peaks) -> None:
        self.levels = [self._clip(v) for v in levels][: self.bars]
        self.peaks = [self._clip(v) for v in peaks][: self.bars]
        self.update()

    @staticmethod
    def _clip(value) -> float:
        v = float(value)
        return 0.0 if v != v else min(1.0, max(0.0, v))   # NaN은 0

    def sizeHint(self) -> QSize:
        return QSize(self.hint_width or self.bars * 4, self.height() or 16)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        w, h = self.width(), self.height()
        gap = 2 if self.bars > 14 else 1
        bw = (w - gap * (self.bars - 1)) / self.bars
        if bw <= 0:
            p.end()
            return
        for i in range(self.bars):
            x = i * (bw + gap)
            level = self.levels[i] if i < len(self.levels) else 0.0
            peak = self.peaks[i] if i < len(self.peaks) else 0.0
            if level > 0:
                bh = max(1.0, level * h)
                p.fillRect(QRectF(x, h - bh, bw, bh), self._qcolors[min(len(self._qcolors) - 1, i * len(self._qcolors) // self.bars)])
            if peak > 0:
                y = min(h - PEAK_HEIGHT, h - peak * h)
                p.fillRect(QRectF(x, y, bw, PEAK_HEIGHT), self._peak_color)
        p.end()
