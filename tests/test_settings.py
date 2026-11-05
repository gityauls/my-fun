import json, logging
import pytest
from funplayer.core.settings import DEFAULTS, JsonStore, Settings

def make(store=None):
    saves = []
    store = {} if store is None else store
    return Settings(store, lambda: saves.append(1)), store, saves

def test_defaults():
    s, _, _ = make()
    assert (s.volume, s.muted, s.seek_step) == (70, False, 5)
    assert DEFAULTS == {"player_volume": 70, "player_muted": False, "player_seek_step": 5,
                        "player_repeat": "off", "player_shuffle": False,
                        "player_last_track": "", "player_last_position": 0.0, "player_mini": False,
                        "player_mini_on_top": True, "player_media_keys": True,
                        "player_geometry": None, "player_mini_geometry": None,
                        "player_last_source": "file", "player_last_station": "",
                        "player_tab": "now", "player_theme": "light",
                        "player_radio_open": ["favorites", "kr:big3", "user"],
                        "player_fx": {}, "player_fx_visible": False, "player_fx_open": True,
                        "player_rename_on_save": False, "player_favorites": []}

def test_repeat_and_shuffle():
    s, store, saves = make()
    assert (s.repeat, s.shuffle) == ("off", False)
    s.repeat = "one"; s.shuffle = True
    assert store["player_repeat"] == "one" and store["player_shuffle"] is True and len(saves) == 2
    s.repeat = "loop"; assert store["player_repeat"] == "off"
    s2, _, _ = make({"player_repeat": "ALL", "player_shuffle": 1})
    assert (s2.repeat, s2.shuffle) == ("off", False)

def test_setters_clamp_and_save():
    s, store, saves = make()
    s.volume = 150; assert s.volume == 100 and store["player_volume"] == 100
    s.volume = -3; assert s.volume == 0
    s.seek_step = 0; assert s.seek_step == 1
    s.seek_step = 500; assert s.seek_step == 100
    s.muted = True; assert store["player_muted"] is True
    assert len(saves) == 5

def test_getters_tolerate_junk():
    s, _, _ = make({"player_volume": "큰소리", "player_muted": "yes", "player_seek_step": None})
    assert (s.volume, s.muted, s.seek_step) == (70, False, 5)
    s2, _, _ = make({"player_volume": 500, "player_seek_step": 2.7})
    assert (s2.volume, s2.seek_step) == (100, 2)

def test_other_keys_untouched():
    s, store, _ = make({"ticker_enabled": True})
    s.volume = 10
    assert store == {"ticker_enabled": True, "player_volume": 10}

def test_jsonstore_round_trip(tmp_path):
    path = tmp_path / "deep" / "settings.json"
    js = JsonStore(path); assert js.data == {}
    s = Settings(js.data, js.save); s.volume = 33
    assert JsonStore(path).data["player_volume"] == 33
    assert not path.with_suffix(".tmp").exists()

def test_corrupt_json(tmp_path):
    p = tmp_path / "s.json"; p.write_text("{not json", encoding="utf-8")
    assert JsonStore(p).data == {}

def test_non_dict_json(tmp_path):
    p = tmp_path / "s.json"; p.write_text(json.dumps([1, 2]), encoding="utf-8")
    assert JsonStore(p).data == {}

def test_save_failure_is_logged(tmp_path, caplog):
    blocker = tmp_path / "file"; blocker.write_text("x")
    js = JsonStore(blocker / "settings.json")
    js.data["player_volume"] = 1
    with caplog.at_level(logging.WARNING):
        js.save()
    assert caplog.records

def test_stage2b_defaults():
    s = Settings({}, lambda: None)
    assert (s.last_track, s.last_position, s.mini, s.mini_on_top, s.media_keys) == ("", 0.0, False, True, True)
    assert s.geometry is None and s.mini_geometry is None

@pytest.mark.parametrize("raw", [None, "x", True, -3, float("nan"), float("inf"), [1]])
def test_bad_last_position_is_zero(raw):
    assert Settings({"player_last_position": raw}, lambda: None).last_position == 0.0

@pytest.mark.parametrize("raw", [None, "1,2,3,4", [1, 2, 3], [1, 2, 0, 4], [1, 2, 3, -4],
                                 [1, "2", 3, 4], [1, 2, True, 4], [1.5, 2, 3, 4], {"x": 1}])
def test_bad_geometry_is_none(raw):
    s = Settings({"player_geometry": raw, "player_mini_geometry": raw}, lambda: None)
    assert s.geometry is None and s.mini_geometry is None

def test_bool_and_text_keys_ignore_wrong_types():
    s = Settings({"player_mini": 1, "player_mini_on_top": "no", "player_media_keys": 0,
                  "player_last_track": 5}, lambda: None)
    assert (s.mini, s.mini_on_top, s.media_keys, s.last_track) == (False, True, True, "")

def test_stage2b_round_trip():
    store, saves = {}, []
    s = Settings(store, lambda: saves.append(1))
    s.last_track = "C:/m/a.mp3"; s.last_position = 72.5; s.mini = True
    s.mini_on_top = False; s.media_keys = False
    s.geometry = (10, 20, 380, 480); s.mini_geometry = [5, 6, 380, 92]
    assert store == {"player_last_track": "C:/m/a.mp3", "player_last_position": 72.5,
                     "player_mini": True, "player_mini_on_top": False, "player_media_keys": False,
                     "player_geometry": [10, 20, 380, 480], "player_mini_geometry": [5, 6, 380, 92]}
    assert len(saves) == 7 and s.geometry == [10, 20, 380, 480]
    s.geometry = None
    assert store["player_geometry"] is None and s.geometry is None

def test_radio_keys_defaults_and_sanitising():
    s = Settings({}, lambda: None)
    assert (s.last_source, s.last_station, s.tab) == ("file", "", "now")
    assert s.radio_open == ["favorites", "kr:big3", "user"]
    bad = Settings({"player_last_source": "tv", "player_last_station": 5, "player_tab": 1,
                    "player_radio_open": "x"}, lambda: None)
    assert (bad.last_source, bad.last_station, bad.tab) == ("file", "", "now")
    assert bad.radio_open == ["favorites", "kr:big3", "user"]
    mixed = Settings({"player_radio_open": ["user", 3, "genre:재즈"]}, lambda: None)
    assert mixed.radio_open == ["user", "genre:재즈"]

def test_radio_keys_round_trip():
    store, saves = {}, []
    s = Settings(store, lambda: saves.append(1))
    s.last_source = "radio"; s.last_station = "kbs-25"; s.tab = "radio"; s.radio_open = ["genre:Lo-fi"]
    assert store["player_last_source"] == "radio" and store["player_last_station"] == "kbs-25"
    assert store["player_tab"] == "radio" and store["player_radio_open"] == ["genre:Lo-fi"] and len(saves) == 4

def test_radio_open_setter_wraps_a_single_string():
    store = {}
    s = Settings(store, lambda: None)
    s.radio_open = "user"
    assert store["player_radio_open"] == ["user"] and s.radio_open == ["user"]


def test_radio_open_migrates_domestic_to_big3():
    s = Settings({"player_radio_open": ["favorites", "domestic", "user"]}, lambda: None)
    assert s.radio_open == ["favorites", "kr:big3", "user"]
    both = Settings({"player_radio_open": ["kr:big3", "domestic", "domestic"]}, lambda: None)
    assert both.radio_open == ["kr:big3"]

def test_fx_keys_defaults_and_sanitising():
    s, store, _ = make()
    assert s.fx == {} and s.fx_visible is False and s.fx_open is True
    store.update({"player_fx": "junk", "player_fx_visible": 1, "player_fx_open": "no"})
    assert s.fx == {} and s.fx_visible is False and s.fx_open is True

def test_fx_keys_round_trip():
    s, store, saves = make()
    s.fx = {"enabled": True}
    s.fx_visible = True
    s.fx_open = False
    assert store["player_fx"] == {"enabled": True} and store["player_fx_visible"] is True
    assert store["player_fx_open"] is False and len(saves) == 3
    assert s.fx == {"enabled": True} and s.fx_visible is True and s.fx_open is False

def test_favorites_default_bad_values_and_set():
    s, store, saves = make()
    assert s.favorites == []
    store["player_favorites"] = "a.mp3"
    assert s.favorites == []
    store["player_favorites"] = ["a.mp3", 3, "", None, "b.mp3"]
    assert s.favorites == ["a.mp3", "b.mp3"]
    s.favorites = ["c.mp3", 1]
    assert store["player_favorites"] == ["c.mp3"] and saves


def test_rename_on_save_default_and_bad_value():
    s, store, saves = make()
    assert s.rename_on_save is False and DEFAULTS["player_rename_on_save"] is False
    for bad in ("yes", 1, None, []):
        store["player_rename_on_save"] = bad
        assert s.rename_on_save is False
    s.rename_on_save = True
    assert store["player_rename_on_save"] is True and s.rename_on_save is True and saves


@pytest.fixture
def settings_factory():
    return lambda store: Settings(store, lambda: None)


def test_settings_theme_default_and_invalid(settings_factory):
    assert settings_factory({}).theme == "light"
    assert settings_factory({"player_theme": "j"}).theme == "light"
    assert settings_factory({"player_theme": 3}).theme == "light"
    assert settings_factory({"player_theme": "dark"}).theme == "dark"


def test_settings_theme_setter(settings_factory):
    store = {}
    s = Settings(store, lambda: None)
    s.theme = "mid"
    assert store["player_theme"] == "mid"
    s.theme = "nope"
    assert store["player_theme"] == "light"


def test_old_tab_values_still_valid(settings_factory):
    assert settings_factory({"player_tab": "radio"}).tab == "radio"
    assert settings_factory({"player_tab": "playlist"}).tab == "playlist"
    assert settings_factory({"player_tab": "fx"}).tab == "fx"
    assert settings_factory({"player_tab": "x"}).tab == "now"
