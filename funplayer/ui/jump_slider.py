from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSlider, QStyle, QStyleOptionSlider


class JumpSlider(QSlider):
    """클릭한 자리로 바로 가고, 이어서 끌 수 있는 슬라이더."""

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.orientation() == Qt.Horizontal:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            handle = self.style().subControlRect(
                QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            groove = self.style().subControlRect(
                QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
            if not handle.contains(event.pos()):
                span = max(1, groove.width() - handle.width())
                pos = int(event.pos().x()) - groove.x() - handle.width() // 2
                value = QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), pos, span, opt.upsideDown)
                self.setValue(value)
        super().mousePressEvent(event)
