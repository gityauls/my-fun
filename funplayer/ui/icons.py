from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

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


def mini_icon(color: QColor) -> QIcon:
    pm, p = _begin(color)
    p.drawRoundedRect(QRectF(2.5, 3.5, 13, 11), 1.5, 1.5)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(QRectF(8.6, 8.8, 5.4, 4.2), 0.8, 0.8)
    p.end()
    return QIcon(pm)


def full_icon(color: QColor) -> QIcon:
    pm, p = _begin(color)
    p.drawRoundedRect(QRectF(3.5, 2.5, 11, 13), 1.5, 1.5)
    p.drawLine(QPointF(3.5, 6), QPointF(14.5, 6))
    p.end()
    return QIcon(pm)


def note_art(size: int) -> QPixmap:
    # 기본 앨범 그림: 배율 1, 정확히 size×size, 투명 바탕 (_begin 쓰지 않는다)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#E3E6EA"))
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.08, size * 0.08)
    s = size / 56
    ink = QColor("#9AA1AB")
    p.setBrush(ink)
    p.drawEllipse(QRectF(17 * s, 33 * s, 11 * s, 9 * s))
    p.drawEllipse(QRectF(31 * s, 29 * s, 11 * s, 9 * s))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(ink, 2.6 * s, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin))
    path = QPainterPath()
    path.moveTo(27 * s, 37 * s); path.lineTo(27 * s, 16 * s); path.lineTo(41 * s, 12 * s); path.lineTo(41 * s, 33 * s)
    p.drawPath(path)
    p.end()
    return pm


def radio_art(size: int) -> QPixmap:
    # 라디오 기본 그림: 배율 1, 정확히 size×size, 투명 바탕
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0, QColor("#DCE6F5"))
    grad.setColorAt(1, QColor("#C3D3EC"))
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.08, size * 0.08)
    s = size / 56
    ink = QColor("#4A6FA5")
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(ink, 2.4 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawRoundedRect(QRectF(12 * s, 22 * s, 32 * s, 22 * s), 3 * s, 3 * s)
    p.drawLine(QPointF(18 * s, 22 * s), QPointF(36 * s, 12 * s))
    p.setBrush(ink)
    p.drawEllipse(QPointF(35 * s, 33 * s), 4.5 * s, 4.5 * s)
    p.setPen(QPen(ink, 1.6 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    for y in (28, 33, 38):
        p.drawLine(QPointF(17 * s, y * s), QPointF(26 * s, y * s))
    p.end()
    return pm
