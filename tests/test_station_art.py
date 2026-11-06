"""방송 그림, 미니 막대의 곡·라디오 단추, 삼선 단추, 미니 간격."""
import pytest
from PyQt5.QtCore import QMimeData, Qt, QUrl
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication

from funplayer.core.settings import Settings
from funplayer.core.stations import BUILTIN_STATIONS
from funplayer.ui.player_panel import PlayerPanel
from funplayer.ui.station_art import CARD_SIZE, LOGO_DIR, StationArt, square_card
from funplayer.ui.station_art_dialog import StationArtDialog, search_url
from fakes import FakePlayer, FakeRunner, FakeStream, make_songs

WITH_LOGO = ("kbs-21", "kbs-22", "kbs-23", "kbs-24", "kbs-25", "kbs-26", "mbc-sfm", "mbc-mfm", "mbc-chm",
             "sbs-lovefm", "sbs-powerfm", "sbs-dmb", "kr-ebs-fm", "kr-ebs-bandi", "kr-cbs-sfm", "kr-cbs-mfm",
             "kr-cbs-joy4u", "kr-ytn", "kr-tbs-fm", "kr-tbs-efm", "kr-tbn-gyeongin", "kr-ifm", "kr-kookbang",
             "kr-kugak", "kr-febc", "kr-bbs", "kr-cpbc", "kr-wbs")


def picture(w=40, h=40, color="#123456"):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(color))
    return img


# ---- 그림 저장소 ----

def test_logo_files_match_real_stations():
    ids = {s.id for s in BUILTIN_STATIONS}
    files = {p.stem for p in LOGO_DIR.glob("*.png")}
    assert files == set(WITH_LOGO) and files <= ids


@pytest.mark.parametrize("sid", WITH_LOGO)
def test_every_logo_is_a_square_card(qapp, sid):
    pm = StationArt().pixmap(sid)
    assert pm.width() == pm.height() == CARD_SIZE


def test_station_without_logo_keeps_the_default(qapp):
    art = StationArt()
    assert art.pixmap("kr-obs") is None and art.pixmap("net-frisky") is None and art.pixmap(None) is None


def test_user_picture_wins_and_reset_returns_the_logo(qapp, tmp_path):
    art = StationArt(tmp_path)
    assert art.save("kbs-21", picture(color="#FF0000")) and art.has_user("kbs-21")
    assert art.pixmap("kbs-21").toImage().pixelColor(CARD_SIZE // 2, CARD_SIZE // 2).name() == "#ff0000"
    art.clear("kbs-21")
    assert not art.has_user("kbs-21")
    assert art.pixmap("kbs-21").toImage().pixelColor(CARD_SIZE // 2, CARD_SIZE // 2).name() != "#ff0000"


def test_user_picture_survives_a_restart(qapp, tmp_path):
    StationArt(tmp_path).save("net-frisky", picture())
    assert StationArt(tmp_path).pixmap("net-frisky") is not None


def test_odd_station_id_is_safe_for_a_file_name(qapp, tmp_path):
    assert StationArt(tmp_path).save('user:http://a/b?c="d"', picture())
    assert len(list(tmp_path.iterdir())) == 1


def test_save_fails_quietly_when_the_folder_cannot_be_made(qapp, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert StationArt(blocker / "sub").save("a", picture()) is False


def test_broken_user_file_falls_back_to_the_logo(qapp, tmp_path):
    art = StationArt(tmp_path)
    art.save("kbs-21", picture())
    next(tmp_path.iterdir()).write_bytes(b"not a picture")
    assert art.pixmap("kbs-21") is not None


def test_wide_picture_is_not_cropped(qapp):
    card = square_card(picture(400, 100, "#00FF00"))
    assert card.width() == card.height() == CARD_SIZE
    assert card.pixelColor(0, 0).name() == "#ffffff"
    assert card.pixelColor(70, CARD_SIZE // 2).name() == "#00ff00"


def test_square_picture_fills_the_card(qapp):
    assert square_card(picture(300, 300, "#00FF00")).pixelColor(0, 0).name() == "#00ff00"


def test_transparent_picture_sits_on_white(qapp):
    img = QImage(50, 50, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    assert square_card(img).pixelColor(25, 25).name() == "#ffffff"


# ---- 창 ----

@pytest.fixture
def dialog(qapp):
    opened = []
    art = StationArt()
    d = StationArtDialog(art, "kr-obs", "OBS 라디오", open_url=opened.append)
    d.opened = opened
    d.art = art
    fired = []
    d.changed.connect(lambda: fired.append(1))
    d.fired = fired
    yield d
    d.deleteLater()
    QApplication.clipboard().clear()


def test_search_opens_the_browser_with_the_station_name(dialog):
    dialog.search()
    assert dialog.opened[0] == QUrl(search_url("OBS 라디오")) and "OBS" in search_url("OBS 라디오")


def test_paste_puts_a_copied_picture(dialog):
    QApplication.clipboard().setImage(picture())
    assert dialog.paste() and dialog.art.has_user("kr-obs") and dialog.fired == [1]


def test_paste_with_nothing_copied_says_so(dialog):
    QApplication.clipboard().clear()
    assert dialog.paste() is False and "복사한 그림이 없습니다" in dialog.hint.text() and dialog.fired == []


def test_pasted_file_path_works(dialog, tmp_path):
    path = tmp_path / "a.png"
    picture().save(str(path))
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    QApplication.clipboard().setMimeData(mime)
    assert dialog.paste() and dialog.art.has_user("kr-obs")


def test_not_a_picture_is_refused(dialog, tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"nope")
    assert dialog._store_file(str(path)) is False and "읽지 못했습니다" in dialog.hint.text()


def test_too_big_file_is_refused(dialog, tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"0" * (10 * 1024 * 1024 + 1))
    assert dialog._store_file(str(path)) is False and "너무 큽니다" in dialog.hint.text()


def test_reset_button_only_when_there_is_something_to_reset(dialog):
    assert not dialog.reset_button.isEnabled()
    dialog._store(picture())
    assert dialog.reset_button.isEnabled()
    dialog.reset()
    assert not dialog.reset_button.isEnabled() and dialog.fired == [1, 1]


# ---- 패널 ----

@pytest.fixture
def rig(qapp, tmp_path):
    runner = FakeRunner()
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), runner=runner)
    p.resize(380, 680)
    p.show()

    def tune(sid):
        p.station_view.station_activated.emit(sid)
        runner.finish(len(runner.calls) - 1, result=FakeStream())
        p.refresh()

    p.tune = tune
    p.songs = str(make_songs(tmp_path, ["a - b.mp3", "c - d.mp3"]))
    yield p
    p.shutdown()
    p.deleteLater()


def center(label):
    pm = label.pixmap()
    return pm.toImage().pixelColor(pm.width() // 2, pm.height() // 4).name()


def test_station_with_logo_shows_it_on_the_cover(rig):
    rig.tune("kbs-25")
    assert rig._station_src is not None
    assert rig.art_label.pixmap().toImage().pixelColor(30, 30).name() == "#ffffff"


def test_station_without_logo_keeps_the_theme_picture(rig):
    rig.tune("kr-obs")
    assert rig._station_src is None
    assert rig.art_label.pixmap().toImage().pixelColor(30, 30).name() != "#ffffff"


def test_changing_the_picture_shows_at_once(rig):
    rig.tune("kr-obs")
    rig.station_art.save("kr-obs", picture(color="#FF0000"))
    rig._station_art_changed()
    assert rig.art_label.pixmap().toImage().pixelColor(100, 100).name() == "#ff0000"


def test_going_back_to_songs_drops_the_logo(rig):
    rig.tune("kbs-25")
    rig.controller.open([rig.songs])
    rig.refresh()
    assert rig._art_radio is False


def test_station_menu_opens_the_picture_window(rig):
    rig.tune("kbs-25")
    shown = []
    rig._show_station_art = lambda sid: shown.append(sid)
    rig.station_view.art_requested.disconnect()
    rig.station_view.art_requested.connect(rig._show_station_art)
    rig.station_view.select("kr-obs")
    rig.station_view.actions["art"].trigger()
    assert shown == ["kr-obs"]


def test_cover_menu_offers_the_picture_only_on_radio(rig):
    rig.refresh()
    assert not rig.actions["station_art"].isVisible()
    rig.tune("kbs-25")
    assert rig.actions["station_art"].isVisible()


def test_list_button_from_mini_opens_the_radio_tab_on_radio(rig):
    rig.tune("kbs-25")
    rig.set_mini(True)
    rig._open_list_from_mini()
    assert not rig.is_mini and rig.tab == "radio"


def test_list_button_from_mini_opens_the_playlist_on_songs(rig):
    rig.controller.open([rig.songs])
    rig.set_mini(True)
    rig._open_list_from_mini()
    assert not rig.is_mini and rig.tab == "playlist"


def test_source_buttons_sit_left_of_the_window_buttons(rig):
    rig.set_mini(True)
    rig.refresh()
    x = [b.mapTo(rig.mini_controls, b.rect().topLeft()).x() for b in
         (rig.mini_song_button, rig.mini_radio_button, rig.mini_min_button, rig.mini_normal_button,
          rig.mini_close_button)]
    assert x == sorted(x) and rig.mini_song_button.isVisible()


def test_source_buttons_switch_both_ways(rig):
    rig.controller.open([rig.songs])
    rig.tune("kbs-25")
    rig.set_mini(True)
    assert rig.controller.source == "radio"
    rig.mini_radio_button.click()
    assert rig.controller.source == "radio"     # 지금 듣는 쪽은 그대로
    rig.mini_song_button.click()
    assert rig.controller.source != "radio"
    rig.mini_radio_button.click()
    assert rig.controller.source == "radio"


def test_source_button_is_dim_when_there_is_nowhere_to_go(rig):
    rig.set_mini(True)
    rig.refresh()
    assert not rig.mini_radio_button.isEnabled() or rig.controller.can_switch_source


def test_active_source_is_underlined(rig):
    rig.tune("kbs-25")
    assert "border-bottom" in rig.mini_radio_button.styleSheet()
    assert rig.mini_song_button.styleSheet() == ""


def test_mini_radio_closes_the_gap_above_live(rig):
    rig.tune("kbs-25")
    rig.controller_status = None
    rig.set_mini(True)
    rig.refresh()
    assert not rig.artist_label.isVisible() and rig.title_label.maximumHeight() < 40


def test_gap_rule_leaves_the_normal_window_alone(rig):
    rig.tune("kbs-25")
    rig.set_mini(True)
    rig.refresh()
    rig.set_mini(False)
    rig.refresh()
    assert rig.artist_label.isVisible() and rig.title_label.maximumHeight() > 1000


def test_mini_radio_keeps_a_song_name_from_the_station(rig, monkeypatch):
    rig.tune("kbs-25")
    rig.set_mini(True)
    monkeypatch.setattr(type(rig.controller), "subtitle", property(lambda c: "지금 나오는 곡"))
    rig.refresh()
    assert rig.artist_label.isVisible()
