from __future__ import annotations

import os

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath,
                         QPixmap)

from funplayer.core.taginfo import TrackInfo, pick_cover
from funplayer.core.themes import Theme
from funplayer.ui.glyphs import glyph_pixmap
from funplayer.ui.icons import note_art


# 곡의 앨범 그림: 태그 그림 우선, 없으면 폴더 안의 그림. 못 열면 None.
def load_cover(info: TrackInfo, max_size: int = 320) -> QPixmap | None:
    img = None
    if info.picture:
        opened = QImage.fromData(info.picture)
        if not opened.isNull():
            img = opened
    if img is None:
        folder = os.path.dirname(info.path)
        try:
            names = os.listdir(folder)
        except OSError:
            names = []
        name = pick_cover(names, info.album)
        if name:
            opened = QImage(os.path.join(folder, name))
            if not opened.isNull():
                img = opened
    if img is None:
        return None
    if max(img.width(), img.height()) > max_size:
        img = img.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return QPixmap.fromImage(img)


# size×size 투명 바탕 가운데에 비율을 맞춰 그린다. src가 None이면 기본 그림.
def art_pixmap(src: QPixmap | None, size: int) -> QPixmap:
    if src is None:
        return note_art(size)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    scaled = src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p = QPainter(pm)
    p.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    p.end()
    return pm


# ---- themed art (stage 5.5) --------------------------------------------------------------

def theme_art(theme: Theme, size: int) -> QPixmap:
    """테마 기본 그림: 하늘·해·언덕 두 겹 (themes2.js의 artSvg와 같은 모양)."""
    sky, sun, hill1, hill2 = theme.art
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 64, size / 64)
    p.fillRect(0, 0, 64, 64, QColor(sky))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(sun))
    p.drawEllipse(QPointF(45, 19), 10, 10)
    a = QPainterPath(QPointF(0, 46))
    a.cubicTo(12, 34, 22, 34, 32, 42)
    a.cubicTo(42, 50, 52, 40, 64, 34)
    a.lineTo(64, 64)
    a.lineTo(0, 64)
    a.closeSubpath()
    p.setBrush(QColor(hill1))
    p.drawPath(a)
    b = QPainterPath(QPointF(0, 54))
    b.cubicTo(14, 46, 26, 50, 38, 54)
    b.cubicTo(48, 57, 56, 52, 64, 48)
    b.lineTo(64, 64)
    b.lineTo(0, 64)
    b.closeSubpath()
    p.setBrush(QColor(hill2))
    p.drawPath(b)
    p.end()
    return pm


def _round_clip(src: QPixmap, size: int, radius: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, src)
    p.end()
    return pm


def rounded_art(src: QPixmap | None, size: int, radius: int, theme: Theme) -> QPixmap:
    """src를 가득 채워 자르고 모서리를 둥글게. None이면 테마 기본 그림."""
    if src is None or src.isNull():
        base = theme_art(theme, size)
    else:
        scaled = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        base = scaled.copy((scaled.width() - size) // 2, (scaled.height() - size) // 2, size, size)
    return _round_clip(base, size, radius)


def radio_art_for(theme: Theme, size: int, radius: int) -> QPixmap:
    """라디오 기본 그림: g1→g2 대각선 그라데이션 위에 라디오 글리프."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(theme.g1))
    grad.setColorAt(1, QColor(theme.g2))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.fillPath(path, QBrush(grad))
    g = max(8, int(size * 0.5))
    p.drawPixmap((size - g) // 2, (size - g) // 2, glyph_pixmap("radio", theme.on_acc, g))
    p.end()
    return pm
