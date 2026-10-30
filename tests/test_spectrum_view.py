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
