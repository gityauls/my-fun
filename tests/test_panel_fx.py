import pytest
from fakes import FakePlayer, FakeRunner
from funplayer.core.effects import FxSettings
from funplayer.core.settings import Settings
from funplayer.ui.player_panel import PlayerPanel


def make_panel(store=None, **kw):
    fake, runner = FakePlayer(), FakeRunner()
    p = PlayerPanel(Settings({} if store is None else store, lambda: None),
                    player=fake, runner=runner, **kw)
    p.resize(380, 560); p.show()
    return p, fake, runner


@pytest.fixture
def fpanel(qapp):
    store = {}
    p, fake, runner = make_panel(store)
    yield p, fake, store
    p.shutdown(); p.deleteLater()


def test_fx_hidden_by_default_and_menu_toggles(fpanel):
    p, _, store = fpanel
    assert not p.fx_strip.isVisible() and not p.fx_separator.isVisible()
    act = p.actions["fx_visible"]
    assert act.isCheckable() and act.text() == "음향 효과 칸 보이기\tCtrl+E"
    act.trigger()
    assert p.fx_strip.isVisible() and p.fx_separator.isVisible()
    assert p.settings.fx_visible is True and store["player_fx_visible"] is True
    p.view_menu.aboutToShow.emit()
    assert act.isChecked()
    p.shortcuts["Ctrl+E"].activated.emit()
    assert not p.fx_strip.isVisible() and not p.fx_separator.isVisible()
    assert p.settings.fx_visible is False
    p.view_menu.aboutToShow.emit()
    assert not act.isChecked()


def test_fx_strip_sits_between_controls_and_tabs(fpanel):
    p, *_ = fpanel
    lay = p.layout()
    idx = {w: lay.indexOf(w) for w in (p.separator, p.fx_strip, p.fx_separator, p.tab_bar)}
    assert idx[p.separator] < idx[p.fx_strip] < idx[p.fx_separator] < idx[p.tab_bar]
    assert p.fx_separator.frameShape() == p.separator.frameShape()
    assert p.fx_separator.frameShadow() == p.separator.frameShadow()


def test_fx_hidden_in_mini_and_back(fpanel):
    p, *_ = fpanel
    p.toggle_fx_visible()
    assert p.fx_strip.isVisible()
    p.set_mini(True)
    assert not p.fx_strip.isVisible() and not p.fx_separator.isVisible()
    assert p.settings.fx_visible is True
    p.set_mini(False)
    assert p.fx_strip.isVisible() and p.fx_separator.isVisible()


def test_fx_changes_reach_player_and_save_on_final(fpanel):
    p, fake, store = fpanel
    fx = FxSettings.from_dict({"enabled": True, "preset": "발라드"})
    store.pop("player_fx", None)
    p.fx_strip.changed.emit(fx, False)
    assert fake.effects == fx and "player_fx" not in store
    p.fx_strip.changed.emit(fx, True)
    assert store["player_fx"] == fx.to_dict()


def test_fx_open_state_saved(fpanel):
    p, _, store = fpanel
    p.fx_strip.set_open(False, notify=True)
    assert store["player_fx_open"] is False


def test_fx_state_survives_restart(qapp):
    fx = FxSettings.from_dict({"enabled": True, "preset": "발라드"})
    store = {"player_fx": fx.to_dict(), "player_fx_visible": True, "player_fx_open": False}
    p, fake, _ = make_panel(store)
    try:
        assert p.fx_strip.isVisible() and not p.fx_strip.is_open
        assert p.fx_strip.summary_label.text() == "켜짐 · 발라드"
        assert fake.effects.preset == "발라드"
        p.view_menu.aboutToShow.emit()
        assert p.actions["fx_visible"].isChecked()
    finally:
        p.shutdown(); p.deleteLater()
