from PyQt5.QtGui import QColor
from funplayer.ui.icons import OFF_COLOR, repeat_icon, shuffle_icon

def test_icons_draw(qapp):
    blue = QColor("#308CC6")
    all_img, one_img = (repeat_icon(m, blue).pixmap(18, 18).toImage() for m in ("all", "one"))
    assert not all_img.isNull() and all_img != one_img
    assert repeat_icon("off", OFF_COLOR).pixmap(18, 18).toImage() != all_img
    assert not shuffle_icon(blue).pixmap(18, 18).isNull()
