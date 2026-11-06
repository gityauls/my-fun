"""숨은 장면을 창 위에 겹쳐 튼다. 마우스는 통과하고, 음악은 건드리지 않고, 끝나면 저절로 사라진다."""
from __future__ import annotations

import time
from typing import Callable

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFontMetrics, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QWidget

from funplayer.ui.egg_sprites import GRID, INK, SCENES, draw_ufo, lift

TICK_MS = 33
SPRITE = 192         # 보통 창에서 캐릭터 크기 (격자의 3배)
SPRITE_WIDE = 256    # 배경까지 있는 장면과 UFO (4배)
SPRITE_MINI = 96     # 미니 막대 (1.5배)
MINI_SPOT = 300      # 미니 막대에서 캐릭터의 왼쪽 끝: 이퀄라이저 위
COVER_UP, COVER_SHRINK = -140, .3
MINI_COVER_UP, MINI_COVER_SHRINK = -24, .45
BUBBLE_PAD = (10, 4)
BUBBLE_EDGE = 6


class EggOverlay(QWidget):
    def __init__(self, parent: QWidget, art: QWidget, is_mini: Callable[[], bool],
                 clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__(parent)
        self._art = art
        self._is_mini = is_mini
        self._clock = clock
        self.key: str | None = None
        self._start = 0.0
        self._cover: QPixmap | None = None
        self._frame = QImage(GRID, GRID, QImage.Format_ARGB32_Premultiplied)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self.tick)
        self.hide()

    def play(self, key: str) -> bool:
        """틀었으면 True. 이미 트는 중이거나 창이 안 보이면 틀지 않는다."""
        parent = self.parentWidget()
        if self.key is not None or not parent.isVisible() or parent.isMinimized():
            return False
        self.key = key
        self._start = self._clock()
        self.setGeometry(parent.rect())
        if key == "ufo" and self._art.isVisible():
            self._cover = QPixmap(self._art.pixmap())
            hidden = QGraphicsOpacityEffect(self._art)
            hidden.setOpacity(0)
            self._art.setGraphicsEffect(hidden)   # 진짜 표지를 비우고 그 사본을 끌어올린다
        self.raise_()
        self.show()
        self._timer.start()
        return True

    def stop(self) -> None:
        self._timer.stop()
        self.key = None
        self._cover = None
        if self._art.graphicsEffect() is not None:
            self._art.setGraphicsEffect(None)
        self.hide()

    def tick(self) -> None:
        if self.key is None:
            return
        if self._clock() - self._start >= SCENES[self.key].length:
            self.stop()
            return
        self.setGeometry(self.parentWidget().rect())   # 창 크기를 바꿔도, 미니로 가도 따라간다
        self.update()

    # ---- 자리 ----

    def _art_rect(self) -> QRect | None:
        if not self._art.isVisible():
            return None
        return QRect(self._art.mapTo(self.parentWidget(), QPoint(0, 0)), self._art.size())

    def sprite_rect(self) -> QRect:
        w, h = self.width(), self.height()
        art = self._art_rect()
        if self._is_mini():
            x = art.center().x() - SPRITE_MINI // 2 if self.key == "ufo" and art else min(MINI_SPOT, w - SPRITE_MINI)
            return QRect(max(0, x), (h - SPRITE_MINI) // 2, SPRITE_MINI, SPRITE_MINI)
        if self.key == "ufo":
            x = (art.center().x() if art else w // 2) - SPRITE_WIDE // 2
            return QRect(x, max(0, art.top() - 107) if art else 20, SPRITE_WIDE, SPRITE_WIDE)
        if self.key == "fuzz":
            return QRect((w - SPRITE_WIDE) // 2, round(h * .28), SPRITE_WIDE, SPRITE_WIDE)
        return QRect((w - SPRITE) // 2, round(h * .37), SPRITE, SPRITE)

    def _bubble_font(self):
        font = self.font()
        font.setBold(True)
        font.setPixelSize(14)
        return font

    def bubble_rect(self) -> QRect:
        fm = QFontMetrics(self._bubble_font())
        pad_x, pad_y = BUBBLE_PAD
        bw = fm.horizontalAdvance(SCENES[self.key].say) + pad_x * 2
        bh = fm.height() + pad_y * 2
        s = self.sprite_rect()
        if self._is_mini():
            x, y = s.right() + 8, (self.height() - bh) // 2
        else:
            x = s.center().x() - bw // 2
            y = s.top() + (280 if self.key == "ufo" else -24 if self.key != "fuzz" else -10)
        x = min(max(BUBBLE_EDGE, x), self.width() - bw - BUBBLE_EDGE)
        return QRect(x, y, bw, bh)

    # ---- 그리기 ----

    def paintEvent(self, event) -> None:
        if self.key is None:
            return
        scene = SCENES[self.key]
        t = min(self._clock() - self._start, scene.length - .01)
        self._frame.fill(Qt.transparent)
        grid = QPainter(self._frame)
        cover = self._cover if self._art.isVisible() else None
        if self.key == "ufo":
            draw_ufo(grid, t, with_cover=self._cover is None)
        else:
            scene.draw(grid, t)
        grid.end()

        p = QPainter(self)
        if self.key == "ufo" and cover is not None:
            self._paint_cover(p, cover, lift(t))
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(self.sprite_rect(), self._frame)
        if t >= scene.say_at:
            self._paint_bubble(p, scene.say)
        p.end()

    def _paint_cover(self, p: QPainter, cover: QPixmap, up: float) -> None:
        art = self._art_rect()
        mini = self._is_mini()
        rise, shrink = (MINI_COVER_UP, MINI_COVER_SHRINK) if mini else (COVER_UP, COVER_SHRINK)
        scale = 1 - up * (1 - shrink)
        w, h = art.width() * scale, art.height() * scale
        target = QRectF(art.center().x() - w / 2, art.center().y() - h / 2 + rise * up, w, h)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(target, cover, QRectF(cover.rect()))

    def _paint_bubble(self, p: QPainter, text: str) -> None:
        rect = self.bubble_rect()
        p.setPen(QPen(QColor(INK), 2))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
        p.setFont(self._bubble_font())
        p.drawText(rect, Qt.AlignCenter, text)
