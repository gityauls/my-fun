import pytest

from funplayer.ui.glyphs import GLYPHS, glyph, glyph_pixmap


def test_all_glyphs_render(qapp):
    for name in GLYPHS:
        assert not glyph_pixmap(name, "#112233", 24).toImage().isNull()
    assert not glyph("heart", "#fff").isNull()
    with pytest.raises(KeyError):
        glyph_pixmap("nope", "#fff")


def test_play_is_filled_triangle(qapp):
    img = glyph_pixmap("play", "#ff0000", 24).toImage()
    assert img.pixelColor(11, 12).red() > 200 and img.pixelColor(2, 2).alpha() == 0
