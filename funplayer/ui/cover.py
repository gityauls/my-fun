from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPainter, QPixmap

from funplayer.core.taginfo import TrackInfo, pick_cover
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
