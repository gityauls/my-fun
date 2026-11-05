"""Panel stylesheet (stage 5.5). Only object-name / property selectors under the panel
objects, so dialogs are never styled by accident."""
from __future__ import annotations

import math
import re
from dataclasses import replace

from PyQt5.QtGui import QColor

from funplayer.core.themes import Theme

_RGBA = re.compile(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)")
_GRAD = re.compile(r"^linear-gradient\((.*)\)$", re.S)


def _rgba(m: re.Match) -> str:
    a = max(0, min(255, round(float(m.group(4)) * 255)))
    return f"rgba({m.group(1)},{m.group(2)},{m.group(3)},{a})"


def _split_top(s: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    return parts


def qcolor_gradient(css: str) -> str:
    """CSS 색, rgba(...) 또는 linear-gradient(...)를 QSS 값으로 바꾼다."""
    css = css.strip()
    m = _GRAD.match(css)
    if not m:
        return _RGBA.sub(_rgba, css)
    parts = _split_top(m.group(1))
    angle = 180.0
    if re.fullmatch(r"-?[\d.]+deg", parts[0]):
        angle = float(parts[0][:-3])
        parts = parts[1:]
    stops = []
    for p in parts:
        pm = re.match(r"^(.*?)\s+([\d.]+)%$", p)
        stops.append((pm.group(1), float(pm.group(2)) / 100) if pm else (p, None))
    n = len(stops)
    out = []
    for i, (col, pos) in enumerate(stops):
        pos = pos if pos is not None else (i / (n - 1) if n > 1 else 0.0)
        out.append(f"stop:{pos:g} {_RGBA.sub(_rgba, col)}")
    rad = math.radians(angle)
    dx, dy = math.sin(rad), -math.cos(rad)
    x1, y1 = 0.5 - dx / 2, 0.5 - dy / 2
    x2, y2 = 0.5 + dx / 2, 0.5 + dy / 2
    return f"qlineargradient(x1:{x1:g}, y1:{y1:g}, x2:{x2:g}, y2:{y2:g}, {', '.join(out)})"


def css_color(css: str) -> QColor:
    """테마의 색 문자열(#RRGGBB 또는 rgba(...))을 QColor로."""
    m = _RGBA.search(css)
    if m:
        c = QColor(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        c.setAlphaF(float(m.group(4)))
        return c
    return QColor(css)


def hero_theme(theme: Theme) -> Theme:
    """지금 재생 페이지에 쓰는 색 (hero 덮어쓰기가 있으면 적용)."""
    return replace(theme, **theme.hero) if theme.hero else theme


def _block(s: str, c: Theme) -> str:
    """Rules for the widgets inside one themed surface (page, strip, mini bar...)."""
    q = qcolor_gradient
    return f"""
{s} QLabel {{ color: {q(c.ink)}; background: transparent; }}
{s} QLabel[role="mute"] {{ color: {q(c.mute)}; }}
{s} QLabel[role="accent"] {{ color: {q(c.acc_t)}; font-weight: 700; }}
{s} QPushButton {{ background: transparent; border: none; color: {q(c.icon)}; padding: 0; }}
{s} QPushButton[kind="btn"] {{ background: {q(c.ctrl_bg)}; color: {q(c.ink)}; border-radius: 8px; padding: 5px 12px; font-size: 12px; font-weight: 500; }}
{s} QPushButton[kind="btn"]:checked {{ background: {q(c.acc)}; color: {q(c.on_acc)}; font-weight: 700; }}
{s} QPushButton[kind="btn"]::menu-indicator {{ image: none; width: 0; }}
{s} QPushButton[kind="play"], {s} QPushButton[kind="playMd"], {s} QPushButton[kind="playSm"] {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {q(c.g1)}, stop:1 {q(c.g2)}); color: {q(c.on_acc)}; }}
{s} QPushButton[kind="play"] {{ border-radius: 30px; }}
{s} QPushButton[kind="playMd"] {{ border-radius: 23px; }}
{s} QPushButton[kind="playSm"] {{ border-radius: 18px; }}
{s} QPushButton[kind="fav"] {{ color: {q(c.fav)}; }}
{s} QPushButton[active="true"] {{ color: {q(c.acc_t)}; }}
{s} QSlider::groove:horizontal {{ height: 5px; border-radius: 2px; background: {q(c.track)}; }}
{s} QSlider::sub-page:horizontal {{ border-radius: 2px; background: {q(c.acc)}; }}
{s} QSlider::handle:horizontal {{ width: 13px; height: 13px; margin: -4px 0; border-radius: 6px; background: {q(c.acc)}; }}
{s} QSlider#volumeSlider::groove:horizontal {{ height: 4px; }}
{s} QSlider#volumeSlider::sub-page:horizontal {{ background: {q(c.acc2)}; }}
{s} QSlider#volumeSlider::handle:horizontal {{ width: 12px; height: 12px; background: {q(c.acc2)}; }}
{s} QSlider::groove:vertical {{ width: 4px; border-radius: 2px; background: {q(c.track)}; }}
{s} QSlider::add-page:vertical {{ border-radius: 2px; background: {q(c.acc)}; }}
{s} QSlider::handle:vertical {{ width: 12px; height: 12px; margin: 0 -4px; border-radius: 6px; background: {q(c.acc)}; }}
{s} QAbstractItemView {{ background: transparent; border: none; color: {q(c.ink)}; outline: 0; }}
{s} QAbstractItemView::item:selected {{ background: {q(c.tint)}; color: {q(c.row_fg)}; border-radius: 9px; }}
{s} QLineEdit {{ background: {q(c.ctrl_bg)}; color: {q(c.ink)}; border: none; border-radius: 8px; padding: 5px 10px; }}
{s} QComboBox {{ background: {q(c.ctrl_bg)}; color: {q(c.ink)}; border: none; border-radius: 8px; padding: 5px 10px; }}
{s} QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
{s} QScrollBar::handle:vertical {{ background: {q(c.track)}; border-radius: 4px; min-height: 24px; }}
{s} QScrollBar::add-line:vertical, {s} QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def stylesheet(theme: Theme, family: str) -> str:
    q = qcolor_gradient
    t = theme
    hero = hero_theme(t)
    mini_over = t.mini or t.hero
    mini = replace(t, **mini_over) if mini_over else t
    fam = family.replace('"', "")
    out = [f"""
#root {{ background: {q(t.bg)}; color: {q(t.ink)}; font-family: "{fam}"; }}
#titleBar {{ background: {q(t.bar)}; color: {q(t.bar_fg)}; }}
#titleBar QLabel {{ color: {q(t.bar_fg)}; background: transparent; font-size: 14px; }}
#titleBar QPushButton {{ background: transparent; border: none; color: {q(t.bar_fg)}; padding: 0; }}
#titleBar QPushButton:hover {{ background: rgba(255,255,255,30); border-radius: 6px; }}
#tabs {{ background: {q(t.tabs)}; border-bottom: 1px solid {q(t.line)}; }}
#tabs QToolButton {{ background: transparent; border: none; border-bottom: 3px solid transparent; color: {q(t.tab_fg)}; font-size: 12px; padding: 0 4px; }}
#tabs QToolButton:checked {{ color: {q(t.tab_on)}; font-weight: 700; border-bottom: 3px solid {q(t.tab_line)}; }}
#pill {{ font-size: 10px; font-weight: 700; color: {q(t.on_acc)}; background: {q(t.acc)}; padding: 1px 6px; border-radius: 5px; }}
#footBar {{ background: {q(t.bg)}; border-top: 1px solid {q(t.line)}; }}
#nowStrip {{ background: {q(t.strip_bg)}; border-top: 1px solid {q(t.line)}; }}
#miniBar {{ background: {q(mini.bg)}; border: 1px solid {q(t.mini_edge)}; border-radius: 24px; }}
QMenu#themed {{ background: {q(t.bar)}; color: {q(t.bar_fg)}; border: 1px solid {q(t.line)}; }}
QMenu#themed::item {{ padding: 6px 22px; }}
QMenu#themed::item:selected {{ background: {q(t.tint)}; color: {q(t.row_fg)}; }}
"""]
    foot = list(t.foot) + [(t.ctrl_bg, t.ink)] * 4
    for i in range(4):
        bg, fg = foot[i]
        out.append(f"#foot{i}, #foot{i} QLabel {{ background: {q(bg)}; color: {q(fg)}; }}\n")
    out.append(f"#pageNow {{ background: {q(hero.bg)}; color: {q(hero.ink)}; }}\n")
    out.append(_block("#pageNow", hero))
    for name in ("pagePlaylist", "pageRadio", "pageFx"):
        out.append(f"#{name} {{ background: {q(t.bg)}; color: {q(t.ink)}; }}\n")
        out.append(_block(f"#{name}", t))
    out.append(_block("#footBar", t))
    out.append(_block("#nowStrip", t))
    out.append(_block("#miniBar", mini))
    return "".join(out)
