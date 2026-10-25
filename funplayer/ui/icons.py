from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

OFF_COLOR = QColor("#5F6368")


def _begin(color: QColor) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(36, 36)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    return pm, p


def _arrow(path: QPainterPath, x: float, y: float, dx: int) -> None:
    path.moveTo(x - dx * 2.5, y - 2.5)
    path.lineTo(x, y)
    path.lineTo(x - dx * 2.5, y + 2.5)


def repeat_icon(mode: str, color: QColor) -> QIcon:
    pm, p = _begin(color)
    path = QPainterPath()
    path.moveTo(3.5, 10.5); path.lineTo(3.5, 7.5); path.quadTo(3.5, 5, 6, 5); path.lineTo(14, 5)
    _arrow(path, 14, 5, 1)
    path.moveTo(14.5, 7.5); path.lineTo(14.5, 10.5); path.quadTo(14.5, 13, 12, 13); path.lineTo(4, 13)
    _arrow(path, 4, 13, -1)
    p.drawPath(path)
    if mode == "one":
        # 글꼴 없이도 그려지도록 "1"을 선으로 그린다(글꼴이 없는 환경에서도 같은 그림).
        p.setPen(QPen(color, 1.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        one = QPainterPath()
        one.moveTo(7.6, 7.8); one.lineTo(9.2, 6.4); one.lineTo(9.2, 11.6)
        p.drawPath(one)
    p.end()
    return QIcon(pm)


def shuffle_icon(color: QColor) -> QIcon:
    pm, p = _begin(color)
    path = QPainterPath()
    path.moveTo(2, 5); path.lineTo(5, 5); path.cubicTo(9, 5, 9, 13, 13, 13); path.lineTo(16, 13)
    _arrow(path, 16, 13, 1)
    path.moveTo(2, 13); path.lineTo(5, 13); path.cubicTo(9, 13, 9, 5, 13, 5); path.lineTo(16, 5)
    _arrow(path, 16, 5, 1)
    p.drawPath(path)
    p.end()
    return QIcon(pm)
