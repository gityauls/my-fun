"""Readable text colours: WCAG contrast and the themed error colour. Pure maths; no Qt here."""
from __future__ import annotations

import colorsys
import re

MIN_TEXT = 4.5
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
_ERROR_HUE = 4 / 360   # 붉은색
_ERROR_SAT = 0.75
_ERROR_ON_LIGHT = 0.42   # 밝은 바탕에서 시작할 밝기 (안 되면 더 어둡게)
_ERROR_ON_DARK = 0.72    # 어두운 바탕에서 시작할 밝기 (안 되면 더 밝게)


def _rgb(color: str) -> tuple[float, float, float]:
    return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def luminance(color: str) -> float:
    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(c) for c in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def surface_colors(css: str) -> list[str]:
    """글자가 놓이는 면의 색. 그라데이션은 양 끝을 뺀 가운데 색들로 잰다 (글자는 양 끝에 놓이지 않는다)."""
    colors = _HEX.findall(css)
    return colors[1:-1] or colors


def error_color(surface: str) -> str:
    """이 면(CSS 색 또는 그라데이션)의 모든 색과 대비가 MIN_TEXT 이상인 붉은색. 가장 덜 바래는 값을 고른다."""
    colors = surface_colors(surface)
    light = sum(luminance(c) for c in colors) / len(colors) > 0.18
    steps = 101
    start, end = (_ERROR_ON_LIGHT, 0.0) if light else (_ERROR_ON_DARK, 1.0)
    for i in range(steps):
        lightness = start + (end - start) * i / (steps - 1)
        r, g, b = colorsys.hls_to_rgb(_ERROR_HUE, lightness, _ERROR_SAT)
        color = "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))
        if all(contrast(color, c) >= MIN_TEXT for c in colors):
            return color
    return "#000000" if light else "#FFFFFF"
