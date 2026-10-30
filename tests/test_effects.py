from funplayer.core.effects import AUTO, CUSTOM, PRESETS, FxSettings


def test_defaults_and_presets():
    fx = FxSettings()
    assert (fx.enabled, fx.preset, fx.bands, fx.mode, fx.width, fx.depth, fx.bass) == (False, "기본", (0,) * 10, "off", 40, 40, 30)
    assert list(PRESETS)[:10] == ["기본", "발라드", "팝", "록", "재즈", "클래식", "댄스", "보컬", "베이스 강하게", "고음 강하게"]
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
    assert FxSettings().summary() == "꺼짐 · 기본"
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


def test_new_presets():
    assert list(PRESETS)[10:] == ["알앤비", "힙합", "일렉트로닉", "어쿠스틱", "블루스", "트로트", "라운지", "라이브"]
    assert len(PRESETS) == 18 and AUTO not in PRESETS and CUSTOM not in PRESETS
    assert PRESETS["알앤비"] == (5, 6, 3, 0, -1, 1, 2, 2, 3, 2)
    assert PRESETS["힙합"] == (6, 6, 3, 1, -1, -1, 1, 1, 2, 3)
    assert PRESETS["일렉트로닉"] == (5, 4, 1, 0, -2, 1, 0, 2, 4, 5)
    assert PRESETS["어쿠스틱"] == (2, 2, 1, 1, 2, 2, 3, 3, 2, 1)
    assert PRESETS["블루스"] == (2, 3, 2, 1, 0, 1, 2, 1, 0, 0)
    assert PRESETS["트로트"] == (1, 2, 2, 1, 2, 3, 3, 2, 1, 0)
    assert PRESETS["라운지"] == (2, 1, 1, 0, -1, -1, 0, 1, 1, 1)
    assert PRESETS["라이브"] == (-1, 1, 2, 3, 2, 2, 3, 3, 2, 1)


def test_auto_applied():
    fx = FxSettings().with_preset("발라드").with_auto(True)
    assert fx.auto and fx.preset == "발라드" and fx.bands == PRESETS["발라드"]
    a = fx.applied("록")
    assert a.bands == PRESETS["록"] and a.preset == "발라드" and a.auto and a.custom == fx.custom
    assert fx.applied_name("록") == "록"
    assert fx.applied(None) == fx and fx.applied_name(None) == "발라드"
    assert fx.applied("레게") == fx and fx.applied_name("레게") == "발라드"
    manual = FxSettings().with_preset("발라드")
    assert manual.applied("록") == manual and manual.applied_name("록") == "발라드"


def test_with_preset_auto_and_other():
    fx = FxSettings().with_preset("팝")
    auto = fx.with_preset(AUTO)
    assert auto == fx.with_auto(True) and auto.preset == "팝" and auto.bands == PRESETS["팝"]
    assert auto.with_preset("록").auto is False
    assert auto.with_preset(CUSTOM).auto is False
    assert auto.with_auto(False).auto is False


def test_band_while_auto_turns_auto_off():
    fx = FxSettings().with_preset("발라드").with_auto(True)
    moved = fx.applied("록").with_band(0, 9)
    expected = (9,) + PRESETS["록"][1:]
    assert moved.auto is False and moved.preset == CUSTOM
    assert moved.bands == expected and moved.custom == expected


def test_summary_forms():
    assert FxSettings().summary() == "꺼짐 · 기본"
    assert FxSettings().with_enabled(True).with_mode("speaker").summary() == "켜짐 · 기본 · 스피커"
    auto = FxSettings().with_enabled(True).with_auto(True).with_mode("earphone")
    assert auto.summary("록") == "켜짐 · 자동: 록 · 이어폰"
    auto = FxSettings().with_enabled(True).with_preset("발라드").with_auto(True)
    assert auto.summary() == "켜짐 · 자동: 발라드"
    assert auto.summary("없는 프리셋") == "켜짐 · 자동: 발라드"


def test_next_choice_order():
    fx = FxSettings().with_auto(True)
    nxt = fx.next_choice()
    assert nxt.preset == "기본" and nxt.auto is False
    last = FxSettings().with_preset("라이브")
    assert last.next_choice().auto and last.next_choice().preset == "라이브"
    with_custom = FxSettings().with_band(2, 4).with_preset("라이브")
    to_custom = with_custom.next_choice()
    assert to_custom.preset == CUSTOM and not to_custom.auto
    assert to_custom.next_choice().auto
    # 순환: 자동 -> 기본 -> ... -> 라이브 -> 자동
    seen, cur = [], FxSettings().with_auto(True)
    for _ in range(len(PRESETS) + 1):
        cur = cur.next_choice()
        seen.append(AUTO if cur.auto else cur.preset)
    assert seen == [*PRESETS, AUTO]


def test_reset_turns_auto_off():
    fx = FxSettings().with_preset("록").with_auto(True).reset()
    assert fx.auto is False and fx.preset == "기본"


def test_auto_dict_round_trip():
    fx = FxSettings().with_enabled(True).with_preset("재즈").with_auto(True)
    assert fx.to_dict()["auto"] is True
    assert FxSettings.from_dict(fx.to_dict()) == fx
    assert FxSettings.from_dict({"auto": "yes"}).auto is False
    assert FxSettings.from_dict({}).auto is False
