import colorsys

import pytest

from funplayer.core.contrast import MIN_TEXT, contrast, error_color, surface_colors
from funplayer.core.themes import THEMES, album_theme


def test_contrast_known_values():
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast("#777777", "#777777") == 1.0


def test_surface_colors():
    assert surface_colors("#112233") == ["#112233"]
    assert surface_colors("linear-gradient(90deg,#000000 0%,#111111 50%,#222222 70%,#FFFFFF)") == ["#111111", "#222222"]
    assert surface_colors("linear-gradient(#000000,#FFFFFF)") == ["#000000", "#FFFFFF"]


@pytest.mark.parametrize("bg", ["#000000", "#FFFFFF", "#777777", "#808080", "#3A3A5A", "#D0A0A0"])
def test_error_color_meets_minimum_on_any_solid(bg):
    assert contrast(error_color(bg), bg) >= MIN_TEXT


@pytest.mark.parametrize("theme", THEMES + tuple(album_theme(a) for a in ("#FF0000", "#00C040", "#2040FF", None)),
                         ids=lambda t: t.id + t.bg)
def test_error_color_stays_red_on_theme_backgrounds(theme):
    color = error_color(theme.bg)
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hue, _, sat = colorsys.rgb_to_hls(r, g, b)
    assert sat > 0.5 and (hue < 0.05 or hue > 0.95)
    assert r > g and r > b
