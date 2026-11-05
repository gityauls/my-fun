import pytest

from funplayer.ui.glyphs import GLYPHS, glyph, glyph_pixmap


def test_all_glyphs_render(qapp):
    for name in GLYPHS:
        assert not glyph_pixmap(name, "#112233", 24).toImage().isNull()
    assert not glyph("heart", "#fff").isNull()
    with pytest.raises(KeyError):
        glyph_pixmap("nope", "#fff")
