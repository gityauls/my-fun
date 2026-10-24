import json, logging
from funplayer.core.settings import DEFAULTS, JsonStore, Settings

def make(store=None):
    saves = []
    store = {} if store is None else store
    return Settings(store, lambda: saves.append(1)), store, saves

def test_defaults():
    s, _, _ = make()
    assert (s.volume, s.muted, s.seek_step) == (70, False, 5)
    assert DEFAULTS == {"player_volume": 70, "player_muted": False, "player_seek_step": 5}

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
