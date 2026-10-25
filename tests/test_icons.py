from PyQt5.QtGui import QColor
from funplayer.ui.icons import OFF_COLOR, repeat_icon, shuffle_icon

def test_icons_draw(qapp):
    blue = QColor("#308CC6")
    all_img, one_img = (repeat_icon(m, blue).pixmap(18, 18).toImage() for m in ("all", "one"))
    assert not all_img.isNull() and all_img != one_img
    assert repeat_icon("off", OFF_COLOR).pixmap(18, 18).toImage() != all_img
    assert not shuffle_icon(blue).pixmap(18, 18).isNull()

from funplayer.ui.icons import full_icon, mini_icon, note_art

def _has_ink(img):
    return any(img.pixelColor(x, y).alpha() > 0 for x in range(img.width()) for y in range(img.height()))

def test_mini_full_icons_and_note_art(qapp):
    for icon in (mini_icon(QColor("#5F6368")), full_icon(QColor("#5F6368"))):
        assert not icon.isNull() and _has_ink(icon.pixmap(18, 18).toImage())
    art = note_art(40)
    assert (art.width(), art.height(), art.devicePixelRatio()) == (40, 40, 1.0)
    assert art.toImage().pixelColor(20, 20).alpha() > 0
