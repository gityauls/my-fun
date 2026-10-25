from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QColor, QImage
from funplayer.core.taginfo import TrackInfo
from funplayer.ui.cover import art_pixmap, load_cover

RED, BLUE = QColor("#ff0000"), QColor("#0000ff")

def png(w, h, color):
    img = QImage(w, h, QImage.Format_ARGB32); img.fill(color)
    data = QByteArray(); buf = QBuffer(data); buf.open(QIODevice.WriteOnly); img.save(buf, "PNG")
    return bytes(data)

def center(pm):
    img = pm.toImage(); return img.pixelColor(img.width() // 2, img.height() // 2)

def test_tag_picture_wins_over_folder(qapp, tmp_path):
    (tmp_path / "cover.jpg").write_bytes(png(8, 8, BLUE))
    pm = load_cover(TrackInfo(str(tmp_path / "a.mp3"), picture=png(8, 8, RED)))
    assert center(pm) == RED

def test_folder_cover_when_no_tag_picture(qapp, tmp_path):
    (tmp_path / "Folder.PNG").write_bytes(png(8, 8, BLUE))
    assert center(load_cover(TrackInfo(str(tmp_path / "a.mp3"), album=""))) == BLUE

def test_album_named_image(qapp, tmp_path):
    (tmp_path / "Day By Day.jpg").write_bytes(png(8, 8, BLUE)); (tmp_path / "scan.jpg").write_bytes(png(8, 8, RED))
    assert center(load_cover(TrackInfo(str(tmp_path / "a.mp3"), album="Day By Day"))) == BLUE

def test_none_when_nothing(qapp, tmp_path):
    assert load_cover(TrackInfo(str(tmp_path / "a.mp3"))) is None
    assert load_cover(TrackInfo(str(tmp_path / "no" / "dir" / "a.mp3"))) is None

def test_corrupt_picture_falls_back(qapp, tmp_path):
    info = TrackInfo(str(tmp_path / "a.mp3"), picture=b"not an image")
    assert load_cover(info) is None
    (tmp_path / "cover.png").write_bytes(png(8, 8, BLUE))
    assert center(load_cover(info)) == BLUE
    (tmp_path / "cover.png").write_bytes(b"broken")
    assert load_cover(info) is None

def test_big_picture_scaled_down(qapp, tmp_path):
    pm = load_cover(TrackInfo(str(tmp_path / "a.mp3"), picture=png(2000, 1000, RED)))
    assert (pm.width(), pm.height()) == (320, 160)

def test_art_pixmap_letterboxes_and_falls_back(qapp, tmp_path):
    src = load_cover(TrackInfo(str(tmp_path / "a.mp3"), picture=png(320, 160, RED)))
    pm = art_pixmap(src, 56); img = pm.toImage()
    assert (pm.width(), pm.height()) == (56, 56)
    assert img.pixelColor(28, 28) == RED and img.pixelColor(28, 2).alpha() == 0
    note = art_pixmap(None, 40)
    assert (note.width(), note.height()) == (40, 40)
