"""숨은 장면의 픽셀 그림. 64칸 격자에 네모만 찍고, 키우는 일은 egg_overlay가 한다."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import QRect
from PyQt5.QtGui import QColor, QImage, QPainter

GRID = 64
INK = "#2A2238"
TILES = ("#FF4FA3", "#7A4BFF", "#2FD6C3", "#FFC83D", "#3AA0FF")

_colors: dict[str, QColor] = {}


def _round(v: float) -> int:
    return math.floor(v + 0.5)


def r(p: QPainter, col: str, x: float, y: float, w: float = 1, h: float = 1) -> None:
    color = _colors.get(col)
    if color is None:
        color = _colors[col] = QColor(col)
    p.fillRect(QRect(_round(x), _round(y), _round(w), _round(h)), color)


def box(p: QPainter, col: str, x: float, y: float, w: int, h: int) -> None:
    r(p, INK, x, y, w, h)
    r(p, col, x + 1, y + 1, w - 2, h - 2)


def disc(p: QPainter, col: str, cx: float, cy: float, rad: int) -> None:
    for y in range(-rad, rad + 1):
        for x in range(-rad, rad + 1):
            if x * x + y * y <= rad * rad + rad * .6:
                r(p, col, cx + x, cy + y)


def star(p: QPainter, col: str, x: float, y: float) -> None:
    r(p, col, x, y - 1, 1, 3)
    r(p, col, x - 1, y, 3, 1)


def note(p: QPainter, col: str, x: float, y: float) -> None:
    r(p, col, x, y, 1, 5)
    r(p, col, x + 1, y, 2, 1)
    r(p, col, x - 2, y + 4, 2, 2)


# ---- 왕년의 카세트 ----

def draw_tape(p: QPainter, t: float) -> None:
    f = int(t * 8)
    climb = (1 - t / .7) * 44 if t < .7 else 0
    tangled = t > 3.7
    b = 0 if tangled else (0, -1, -2, -1)[f % 4]
    side = (1 if f % 2 else -1) if tangled else (-3 if f % 8 < 4 else 3)
    y, x = 20 + b + climb, 14 + side
    # 다리
    kick = not tangled and f % 4 < 2
    r(p, "#F2C230", x + 11, y + 24, 2, 9 if kick else 11)
    r(p, "#F2C230", x + 23, y + 24, 2, 11 if kick else 9)
    if not tangled and f % 8 < 4:
        r(p, "#F2C230", x + 24, y + 30, 9, 2)
        box(p, "#B66BF0", x + 32, y + 28, 6, 5)
    else:
        box(p, "#B66BF0", x + 21, y + 33, 8, 5)
    box(p, "#B66BF0", x + 8, y + 33 - (2 if kick else 0), 8, 5)
    # 몸통
    box(p, "#FFD93B", x, y, 36, 25)
    r(p, "#FF8A3C", x + 33, y + 1, 2, 23)
    r(p, "#B66BF0", x + 6, y + 1, 24, 6)
    r(p, INK, x + 10, y + 3, 5, 1)
    r(p, INK, x + 21, y + 3, 5, 1)
    r(p, "#5CC13A", x + 3, y + 9, 30, 13)
    r(p, "#FFB20A", x + 6, y + 11, 24, 10)
    # 얼굴
    r(p, "#FFFFFF", x + 11, y + 6, 6, 6)
    r(p, "#FFFFFF", x + 20, y + 6, 6, 6)
    if tangled:
        r(p, INK, x + 13, y + 7, 2, 2)
        r(p, INK, x + 22, y + 9, 2, 2)
        r(p, "#7AD7FF", x + 31, y + 5 + f % 6, 2, 3)
    elif f % 20 == 0:
        r(p, INK, x + 11, y + 9, 6, 1)
        r(p, INK, x + 20, y + 9, 6, 1)
    else:
        r(p, INK, x + 14, y + 8, 2, 3)
        r(p, INK, x + 23, y + 8, 2, 3)
    # 입과 릴
    for k in (9, 27):
        disc(p, INK, x + k, y + 17, 3)
        disc(p, "#FF5A36", x + k, y + 17, 2)
        a = f % 4
        r(p, "#FFFFFF", x + k + (1, 0, -1, 0)[a], y + 17 + (0, 1, 0, -1)[a])
    r(p, "#FF5A36", x + 13, y + 15, 10, 3)
    r(p, "#FFD8C8", x + 15, y + 16, 6, 1)
    # 팔
    up = not tangled and f % 4 < 2
    r(p, "#FF8A3C", x - 3, y + (4 if up else 11), 4, 2)
    r(p, "#FF8A3C", x - 4, y - 2 if up else y + 11, 2, 7 if up else 6)
    box(p, "#FFFFFF", x - 6, y - 6 if up else y + 15, 6, 5)
    r(p, "#FF8A3C", x + 35, y + (11 if up else 4), 4, 2)
    r(p, "#FF8A3C", x + 38, y + 11 if up else y - 2, 2, 6 if up else 7)
    box(p, "#FFFFFF", x + 36, y + 15 if up else y - 6, 6, 5)
    # 먼지와 엉킨 테이프
    if .7 < t < 1.2:
        for i in range(6):
            r(p, "#B8A8C8", x - 4 + i * 9, y + 27 - f % 3 - i % 2 * 3)
    if tangled:
        for i in range(int(min(120, (t - 3.7) * 110))):
            r(p, "#6B3A1E", 32 + side + math.sin(i * .42) * (9 + i * .09),
              y + 22 + i * .16 + math.cos(i * .9) * 3)


# ---- 털복숭이 뭉치 ----

def draw_fuzz(p: QPainter, t: float) -> None:
    f = int(t * 8)
    # 미러볼과 빛줄기
    r(p, "#8A85A0", 32, 0, 1, 3)
    p.setOpacity(.35)
    for k in range(6):
        a = .5 + k * .42 + math.sin(t * 1.6 + k) * .25
        for s in range(8, 58):
            r(p, TILES[k % 5], 32 + math.cos(a) * s, 9 + math.sin(a) * s)
    p.setOpacity(1)
    disc(p, "#C9C6DA", 32, 9, 6)
    for y in range(-5, 6, 2):
        for x in range(-5, 6, 2):
            if x * x + y * y < 30:
                r(p, TILES[abs(x + y + f) % 5], 32 + x, 9 + y)
    # 바닥
    for j in range(2):
        for i in range(8):
            p.setOpacity(.55 if ((i + j + f) >> 1) % 3 else 1)
            r(p, TILES[(i * 2 + j * 3 + (f >> 1)) % 5], i * 8, 54 + j * 5, 7, 4)
    p.setOpacity(1)
    # 몸
    b = (0, -2, -3, -2)[f % 4]
    cy = 33 + b
    p.save()
    if f % 16 >= 8:
        p.translate(64, 0)
        p.scale(-1, 1)
    leg = f % 4 < 2
    r(p, "#2E9BE6", 26, cy + 10, 3, (9 if leg else 6) - b)
    r(p, "#2E9BE6", 35, cy + 10, 3, (6 if leg else 9) - b)
    box(p, "#FFFFFF", 23, 51 if leg else 48, 8, 4)
    box(p, "#FFFFFF", 34, 48 if leg else 51, 8, 4)
    r(p, "#2E9BE6", 43, cy - (7 if leg else -3), 3, 9)
    r(p, "#2E9BE6", 18, cy + (3 if leg else -7), 3, 9)
    disc(p, "#52C7FF", 44, cy - (8 if leg else -11), 2)
    disc(p, "#52C7FF", 19, cy + (12 if leg else -8), 2)
    for y in range(-13, 14):
        for x in range(-13, 14):
            n = ((x * 7 + y * 13 + (f >> 2) * 3) & 3) * .8
            if x * x + y * y <= (10.5 + n) ** 2:
                r(p, "#7FDBFF" if y < -5 and x < 2 else "#3DB6F5", 32 + x, cy + y)
    # 조끼
    r(p, "#2B2A63", 21, cy + 1, 5, 9)
    r(p, "#2B2A63", 38, cy + 1, 5, 9)
    r(p, "#FFD93B", 22, cy + 4)
    r(p, "#FFD93B", 40, cy + 6)
    r(p, "#FFFFFF", 23, cy + 7)
    # 얼굴
    for ex in (26, 35):
        r(p, INK, ex, cy - 5)
        r(p, INK, ex + 1, cy - 6, 2, 1)
        r(p, INK, ex + 3, cy - 5)
    r(p, "#FF8FC0", 24, cy - 3, 3, 2)
    r(p, "#FF8FC0", 38, cy - 3, 3, 2)
    r(p, "#7A1F35", 29, cy - 2, 6, 4)
    r(p, "#FF7A90", 30, cy, 4, 2)
    # 더듬이
    sw = -1 if f % 4 < 2 else 1
    r(p, "#3DB6F5", 28 + sw, cy - 16, 1, 5)
    r(p, "#3DB6F5", 36 - sw, cy - 16, 1, 5)
    disc(p, "#7FDBFF", 28 + sw * 2, cy - 17, 1)
    disc(p, "#7FDBFF", 36 - sw * 2, cy - 17, 1)
    p.restore()
    star(p, "#FFD93B", 12 + f % 3 * 2, 26)
    star(p, "#FFFFFF", 52 - f % 3, 34 + (f >> 2) % 4)


# ---- 지친 햄스터 DJ ----

def _hamster(p: QPainter, x: float, y: float, mode: str, f: int) -> None:
    r(p, INK, x - 1, y - 13, 3, 1)
    disc(p, "#2B2A63", x, y, 13)
    disc(p, "#F2A03C", x, y, 12)
    disc(p, "#F2A03C", x - 9, y - 10, 3)
    disc(p, "#F2A03C", x + 9, y - 10, 3)
    disc(p, "#FFB9C6", x - 9, y - 10, 1)
    disc(p, "#FFB9C6", x + 9, y - 10, 1)
    disc(p, "#FFF3E2", x, y + 6, 8)
    disc(p, "#FFF3E2", x - 6, y + 1, 3)
    disc(p, "#FFF3E2", x + 6, y + 1, 3)
    if mode == "spin":
        for k in (-5, 5):
            disc(p, "#FFFFFF", x + k, y - 3, 3)
            a = f % 4
            r(p, INK, x + k + (1, 0, -1, 0)[a], y - 3 + (0, 1, 0, -1)[a])
            r(p, INK, x + k + (-1, 0, 1, 0)[a] * 2, y - 3 + (0, -1, 0, 1)[a] * 2)
    elif mode == "ko":
        for k in (-5, 5):
            r(p, INK, x + k - 2, y - 3, 5, 1)
            r(p, INK, x + k, y - 5, 1, 5)
    else:
        r(p, INK, x - 6, y - 4, 3, 4)
        r(p, INK, x + 4, y - 4, 3, 4)
        r(p, "#FFFFFF", x - 6, y - 4)
        r(p, "#FFFFFF", x + 4, y - 4)
    r(p, "#E85C7A", x - 1, y, 3, 2)
    r(p, INK, x - 1, y + 3, 3, 1)
    # 헤드폰
    r(p, "#2B2A63", x - 10, y - 14, 21, 2)
    box(p, "#FF4FA3", x - 15, y - 5, 5, 9)
    box(p, "#FF4FA3", x + 11, y - 5, 5, 9)


def _deck(p: QPainter, x: float, y: float, f: int) -> None:
    box(p, "#3B3556", x, y, 40, 12)
    disc(p, INK, x + 12, y, 6)
    disc(p, "#4A4560", x + 12, y, 3)
    r(p, "#FFD93B", x + 12 + (2, 0, -2, 0)[f % 4], y + (0, 1, 0, -1)[f % 4])
    r(p, "#2FD6C3", x + 24, y + 3, 2, 6)
    r(p, "#FF4FA3", x + 28, y + 5, 2, 4)
    r(p, "#FFD93B", x + 32, y + 2, 2, 7)


def draw_ham(p: QPainter, t: float) -> None:
    f = int(t * (12 if t < 2.6 else 8))
    if t < 2.6:
        dizzy = t > 1.5
        w = (-2, 0, 2, 0)[f % 4] if dizzy else 0
        _hamster(p, 32 + w, 26, "spin" if dizzy else "ok", f)
        _deck(p, 12, 42, f)
        a = f % 2
        disc(p, "#F2A03C", 23 + a * 2, 41 - a, 2)
        disc(p, "#F2A03C", 42 - a * 2, 41 - (1 - a), 2)
        note(p, "#FF4FA3", 6 + f % 4, 18 - f % 6)
        note(p, "#2FD6C3", 54 - f % 3, 26 - f % 5)
        if dizzy:
            for i in range(3):
                star(p, "#FFD93B", 32 + math.cos(t * 7 + i * 2.1) * 17, 8 + math.sin(t * 7 + i * 2.1) * 3)
    elif t < 3.1:
        q = (t - 2.6) / .5
        _hamster(p, 32, 26 + q * 6, "spin", f)
        p.save()
        p.translate(_round(32 + q * 28), _round(48 - q * 30))
        p.rotate(90 * int(q * 4))
        _deck(p, -20, -6, f)
        p.restore()
    else:
        p.save()
        p.translate(32, 44)
        p.rotate(-90)
        _hamster(p, 0, 0, "ko", f)
        p.restore()
        r(p, "#6A5F85", 4, 58, 56, 1)
        for i in range(3):
            star(p, "#FFD93B", 32 + math.cos(t * 5 + i * 2.1) * 13, 27 + math.sin(t * 5 + i * 2.1) * 3)


# ---- 표지 도둑 UFO ----

def lift(t: float) -> float:
    """표지가 얼마나 올라갔나 (0~1)."""
    if t < 1:
        return 0.0
    if t < 2.8:
        return (t - 1) / 1.8
    if t < 3.4:
        return 1.0
    if t < 4.3:
        return 1 - (t - 3.4) / .9
    return 0.0


def draw_ufo(p: QPainter, t: float, with_cover: bool = True) -> None:
    f = int(t * 8)
    y = -14 + t / .8 * 26 if t < .8 else (12 - (t - 4.4) / .6 * 30 if t > 4.4 else 12)
    y += 0 if f % 8 < 4 else 1
    x = 32 + ((t - 4.4) * 40 if t > 4.4 else 0) + math.sin(t * 2) * 2
    up = lift(t)
    if .9 <= t < 4.4:
        p.setOpacity(.32 + .08 * (f % 2))
        for i in range(44):
            w = 6 + i * .42
            r(p, "#5CFFC0", x - w, y + 6 + i, w * 2, 1)
        p.setOpacity(1)
        for i in range(8):
            r(p, "#D8FFF0", x + math.sin(i * 2.4 + t) * 9, y + 50 - (t * 16 + i * 7) % 42)
    if with_cover:
        s = _round(20 - up * 12)
        cy = 44 - up * 26 + (f % 2 if 0 < up < 1 else 0)
        cx = x - s / 2
        box(p, "#7A4BD0", cx, cy, s, s)
        r(p, "#CDB8F2", cx + 1, cy + 1, s - 2, s * .55)
        disc(p, "#FBDCE6", cx + s * .65, cy + s * .3, max(1, _round(s / 8)))
    # 조종석
    disc(p, "#2FD6C3", x, y - 3, 8)
    disc(p, "#BFFFEA", x, y - 3, 7)
    disc(p, "#7BE04A", x, y - 3, 4)
    r(p, INK, x - 3, y - 4, 2, 3)
    r(p, INK, x + 2, y - 4, 2, 3)
    r(p, "#3C8A20", x - 1, y, 3, 1)
    r(p, "#7BE04A", x - 3, y - 9, 1, 3)
    r(p, "#7BE04A", x + 3, y - 9, 1, 3)
    # 비행접시
    r(p, INK, x - 21, y + 1, 43, 6)
    r(p, "#AAB2C8", x - 20, y + 2, 41, 4)
    r(p, "#DCE2F0", x - 16, y + 2, 33, 1)
    r(p, INK, x - 13, y + 7, 27, 1)
    for i in range(6):
        r(p, TILES[(i + f) % 5], x - 17 + i * 7, y + 4, 2, 2)


# ---- 문워크 ----

MOON_STRIP = Path(__file__).resolve().parent.parent / "assets" / "eggs" / "moonwalk.png"
MOON_FRAMES = 29
MOON_FPS = 28
_moon_strip: QImage | None = None


def moon_source(t: float, strip_width: int, strip_height: int) -> QRect:
    w = strip_width // MOON_FRAMES
    return QRect(int(t * MOON_FPS) % MOON_FRAMES * w, 0, w, strip_height)


def draw_moon(p: QPainter, t: float, target: QRect = QRect(0, 0, GRID, GRID)) -> None:
    """이 장면만 찍은 그림이 아니라 움짤의 프레임 줄이다. 흔들리지 않게 프레임마다 맞춰 두었다."""
    global _moon_strip
    if _moon_strip is None:
        _moon_strip = QImage(str(MOON_STRIP))
    if not _moon_strip.isNull():
        p.drawImage(target, _moon_strip, moon_source(t, _moon_strip.width(), _moon_strip.height()))


@dataclass(frozen=True)
class Scene:
    draw: Callable[[QPainter, float], None]
    length: float
    say: str
    say_at: float = .5


SCENES = {
    "tape": Scene(draw_tape, 5.0, "MP3? 내가 왕년엔 말이야~"),
    "fuzz": Scene(draw_fuzz, 4.0, "GROOVE TIME!"),
    "ham": Scene(draw_ham, 4.0, "한 곡만 끝까지 들어봐!!", 1.5),
    "ufo": Scene(draw_ufo, 5.0, "음악 데이터 절취 중...", 1.0),
    "moon": Scene(draw_moon, 6.0, "오늘 댄스 5곡째! 좀 치는데?", 1.0),
}
