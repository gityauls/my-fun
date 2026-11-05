import colorsys

import pytest

from funplayer.core.themes import (DEFAULT_THEME, THEME_IDS, THEMES, accent_from_pixels,
                                   album_theme, get_theme)


def solid(c: str) -> bool:
    return isinstance(c, str) and len(c) == 7 and c.startswith("#")


def _lin(v: float) -> float:
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _lum(c: str) -> float:
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hsl_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h / 360, l, s)
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def test_twelve_themes_without_j():
    assert THEME_IDS == ("light", "dark", "mid", "c", "d", "f", "g", "h", "i", "k", "l", "m")
    assert tuple(t.id for t in THEMES) == THEME_IDS
    assert DEFAULT_THEME == "light"


def test_unknown_theme_falls_back():
    assert get_theme("j").id == "light"
    assert get_theme("dark").id == "dark"


def test_defaults_rule():
    light, h, i, l = get_theme("light"), get_theme("h"), get_theme("i"), get_theme("l")
    assert light.tab_fg == light.mute and light.tab_on == light.acc_t and light.tab_line == light.acc
    assert light.row_fg == light.acc_t and light.strip_bg == light.tabs
    assert light.ic2 == light.icon and light.acc2 == light.acc
    assert light.art == ("#C9B8F0", "#FBD9E6", "#A98FE0", "#6C3DCB")
    assert get_theme("mid").bar == "#657A90"
    assert i.row_fg == "#FBF7EF" and i.strip_bg == "#FBF7EF" and i.acc2 == "#1F4D3A"
    assert len(i.foot) == 4 and light.foot == ()
    assert h.hero["bg"] == "#2C2F4D" and h.mini == {}
    assert l.mini["bg"].startswith("linear-gradient")


@pytest.mark.parametrize("t", THEMES, ids=lambda t: t.id)
def test_text_contrast(t):
    pairs = ((t.ink, t.bg), (t.mute, t.bg), (t.tab_fg, t.tabs), (t.row_fg, t.tint))
    for fg, bg in pairs:
        if solid(fg) and solid(bg):
            assert contrast(fg, bg) >= 4.4


@pytest.mark.parametrize("hue", range(0, 360, 30))
def test_album_theme_readable_for_any_hue(hue):
    t = album_theme(hsl_hex(hue, .7, .5))
    assert contrast(t.ink, t.bg) >= 7 and contrast(t.acc, t.bg) >= 4.5


def test_album_theme_none_is_default_purple():
    t = album_theme(None)
    c = get_theme("c")
    assert c.id == "c" and c.acc == t.acc and c.bg == t.bg


def test_accent_ignores_gray_and_empty():
    assert accent_from_pixels([(128, 128, 128)] * 50) is None
    assert accent_from_pixels([]) is None


def test_accent_averages_saturated_pixels():
    acc = accent_from_pixels([(200, 40, 40)] * 10 + [(0, 0, 0)] * 5 + [(255, 255, 255)] * 5)
    assert acc == "#C82828"
