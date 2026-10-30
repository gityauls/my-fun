from funplayer.core.effects import CUSTOM, PRESETS, FxSettings


def test_defaults_and_presets():
    fx = FxSettings()
    assert (fx.enabled, fx.preset, fx.bands, fx.mode, fx.width, fx.depth, fx.bass) == (False, "기본", (0,) * 10, "off", 40, 40, 30)
    assert list(PRESETS) == ["기본", "발라드", "팝", "록", "재즈", "클래식", "댄스", "보컬", "베이스 강하게", "고음 강하게"]
    assert PRESETS["발라드"] == (3, 2, 1, 0, -1, 0, 1, 2, 3, 2) and PRESETS["고음 강하게"] == (0, 0, 0, 0, 0, 1, 3, 5, 6, 7)
    assert FxSettings().with_preset("록").bands == PRESETS["록"]


def test_band_move_becomes_custom_and_is_remembered():
    fx = FxSettings().with_preset("팝").with_band(0, 20)
    assert fx.preset == CUSTOM and fx.bands[0] == 12 and fx.custom == fx.bands
    back = fx.with_preset("기본").with_preset(CUSTOM)
    assert back.bands == fx.bands


def test_reset_keeps_enabled_and_custom():
    fx = FxSettings().with_enabled(True).with_band(3, 5).with_mode("earphone").with_level("bass", 90).reset()
    assert fx.enabled and fx.preset == "기본" and fx.bands == (0,) * 10 and fx.mode == "off" and fx.bass == 30
    assert fx.custom[3] == 5


def test_summary():
    assert FxSettings().summary() == "꺼짐"
    on = FxSettings().with_enabled(True).with_preset("발라드")
    assert on.summary() == "켜짐 · 발라드"
    assert on.with_mode("earphone").summary() == "켜짐 · 발라드 · 이어폰"
    assert on.with_mode("speaker").summary() == "켜짐 · 발라드 · 스피커"


def test_dict_round_trip():
    fx = FxSettings().with_enabled(True).with_preset("재즈").with_mode("speaker").with_level("width", 77)
    assert FxSettings.from_dict(fx.to_dict()) == fx


def test_from_dict_garbage():
    assert FxSettings.from_dict("x") == FxSettings()
    fx = FxSettings.from_dict({"enabled": "yes", "preset": "없음", "bands": [1, "a", 99, -99], "mode": "tv",
                               "width": 500, "depth": -3, "bass": "z", "custom": None})
    assert fx.enabled is False and fx.preset == "기본" and fx.bands == (0,) * 10 and fx.mode == "off"
    assert (fx.width, fx.depth, fx.bass) == (100, 0, 30) and fx.custom == (0,) * 10
    ok = FxSettings.from_dict({"bands": [1, 2, 3, 4, 5, 6, 7, 8, 99, -99], "preset": CUSTOM})
    assert ok.bands == (1, 2, 3, 4, 5, 6, 7, 8, 12, -12) and ok.preset == CUSTOM


def test_small_edges():
    fx = FxSettings()
    assert fx.with_preset("없음") == fx
    assert fx.with_band(99, 3) == fx and fx.with_band(-1, 3) == fx
    assert fx.with_mode("tv").mode == "off"
    assert fx.with_level("nope", 5) == fx
    assert fx.with_level("depth", -5).depth == 0
    nan = FxSettings.from_dict({"bands": [float("nan")] * 10, "width": float("inf")})
    assert nan.bands == (0,) * 10 and nan.width == 100


def test_from_dict_unhashable_and_huge_values_do_not_crash():
    fx = FxSettings.from_dict({"preset": [], "mode": {}, "bands": [10 ** 400] * 10, "width": 10 ** 400,
                               "depth": -(10 ** 400), "custom": [10 ** 400] * 10})
    assert fx.preset == "기본" and fx.mode == "off" and fx.bands == (12,) * 10
    assert (fx.width, fx.depth) == (100, 0) and fx.custom == (12,) * 10
