"""음향 효과 탭의 움짤."""
from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QApplication

from funplayer.core.settings import Settings
from funplayer.ui.fx_stage import MIN_HEIGHT, FxStage
from funplayer.ui.player_panel import PlayerPanel
from fakes import FakePlayer


def test_gif_can_be_read(qapp):
    assert FxStage().movie.isValid()


def test_moves_only_while_dancing(qapp):
    s = FxStage()
    s.set_dancing(True)
    assert s.movie.state() == QMovie.Running
    s.set_dancing(False)
    assert s.movie.state() == QMovie.Paused
    s.set_dancing(True)
    assert s.movie.state() == QMovie.Running
    s.set_dancing(False)


def test_missing_gif_stays_quiet(qapp, tmp_path):
    s = FxStage(path=tmp_path / "none.gif")
    s.resize(300, 150)
    s.set_dancing(True)
    assert not s.dancing
    s.grab()


def test_picture_keeps_its_shape_and_fits(qapp):
    s = FxStage()
    s.resize(300, 100)
    r = s.picture_rect()
    assert abs(r.width() / r.height() - 800 / 450) < .01 and r.height() == 100


def test_card_stays_light_on_dark_accents(qapp):
    s = FxStage()
    s.set_accent("#102030")
    assert s._card.lightness() > 200


def test_panel_shows_it_always_on_the_effects_tab(qapp):
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer())
    p.resize(380, 680)
    p.show()
    p.set_tab("now")
    assert not p.fx_strip.stage.dancing
    p.set_tab("fx")   # 곡을 틀지 않아도 움직인다
    QApplication.processEvents()
    assert p.fx_strip.stage.dancing and p.fx_strip.stage.height() > MIN_HEIGHT
    p.set_tab("now")
    assert not p.fx_strip.stage.dancing
    p.shutdown()
    p.deleteLater()
