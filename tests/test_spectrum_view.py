from __future__ import annotations

import numpy as np
from PyQt5.QtGui import QColor

from funplayer.ui.colors import SPECTRUM_COLOR, SPECTRUM_PEAK_COLOR
from funplayer.ui.spectrum_view import SpectrumView


def test_accepts_numpy_and_clips(qapp):
    v = SpectrumView(12)
    v.set_levels(np.linspace(-0.5, 1.5, 12), np.full(12, 2.0))
    assert all(0.0 <= x <= 1.0 for x in v.levels) and v.peaks == [1.0] * 12


def test_paints_bar_and_peak_colors(qapp):
    v = SpectrumView(2)
    v.resize(21, 40)
    v.set_levels([1.0, 0.0], [1.0, 0.5])
    img = v.grab().toImage()
    assert QColor(img.pixel(3, 30)).name().upper() == SPECTRUM_COLOR
    assert QColor(img.pixel(3, 0)).name().upper() == SPECTRUM_PEAK_COLOR
    assert QColor(img.pixel(15, 30)).alpha() == 0 or QColor(img.pixel(15, 30)).name().upper() != SPECTRUM_COLOR


def test_spectrum_colors_split_evenly(qapp):
    v = SpectrumView(); v.set_colors(("#111111", "#222222", "#333333"), "#444444")
    assert [v.bar_color(i, 24) for i in (0, 8, 16)] == ["#111111", "#222222", "#333333"]
    assert v.bars == 24


def test_spectrum_empty_colors_fall_back(qapp):
    v = SpectrumView(); v.set_colors((), "#444444")
    assert v.bar_color(5, 24) == SPECTRUM_COLOR


def test_spectrum_paints_themed_colors(qapp):
    v = SpectrumView(2)
    v.resize(21, 40)
    v.set_colors(("#112233", "#445566"), "#778899")
    v.set_levels([1.0, 1.0], [0.0, 0.0])
    img = v.grab().toImage()
    assert QColor(img.pixel(3, 30)).name().upper() == "#112233"
    assert QColor(img.pixel(17, 30)).name().upper() == "#445566"
