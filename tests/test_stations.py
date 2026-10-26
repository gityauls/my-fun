import json
import pytest
from funplayer.core.stations import BUILTIN_STATIONS, GENRES, StationList, load_stations, same_url, save_stations

KR_KEYS = ["kr:big3", "kr:more", "kr:faith", "kr:community"]

def test_builtins_shape():
    ids = [s.id for s in BUILTIN_STATIONS]
    assert {"kbs-21", "kbs-22", "kbs-24", "kbs-25", "mbc-sfm", "mbc-mfm"} <= set(ids)
    assert len(ids) == len(set(ids)) == 72
    for g in GENRES:
        n = sum(1 for s in BUILTIN_STATIONS if s.group == f"genre:{g}")
        assert 1 <= n <= 2
    assert all(s.key.startswith(("http://", "https://")) for s in BUILTIN_STATIONS if s.kind == "url")

def test_groups_order_titles_and_favorites():
    sl = StationList()
    sl.set_favorite("kbs-25", True)
    keys = [k for k, _, _ in sl.groups()]
    assert keys[0] == "favorites" and keys[1:5] == KR_KEYS and keys[5] == f"genre:{GENRES[0]}"
    titles = {k: t for k, t, _ in sl.groups()}
    assert titles["favorites"] == "★ 즐겨찾기" and titles["kr:big3"] == "국내 · KBS·MBC·SBS (11)"
    assert titles[f"genre:{GENRES[0]}"] == f"해외 추천 · {GENRES[0]} (2)"
    domestic = dict((k, v) for k, _, v in sl.groups())["kr:big3"]
    assert "kbs-25" not in [s.id for s in domestic]

def test_add_url_dedupes_and_names_from_host():
    sl = StationList()
    st, new = sl.add_url("", " HTTPS://Stream.Example.org/live.mp3/ ")
    assert new and st.name == "stream.example.org" and st.group == "user" and st.source == "직접 넣음"
    again, new2 = sl.add_url("다른 이름", "https://stream.example.org/live.mp3")
    assert not new2 and again.id == st.id
    titles = [t for _, t, _ in sl.groups()]
    assert titles[-1] == "직접 넣은 방송"

def test_remove_hides_builtin_and_restore():
    sl = StationList(); sl.set_favorite("kbs-21", True); sl.remove("kbs-21")
    assert sl.get("kbs-21") is None and not sl.is_favorite("kbs-21")
    sl.restore_builtins(); assert sl.get("kbs-21") is not None

def test_readding_hidden_builtin_url_shows_it_again():
    sl = StationList(); sl.remove("net-somafm-groove-salad")
    st, new = sl.add_url("x", "https://ice6.somafm.com/groovesalad-128-mp3")
    assert not new and st.id == "net-somafm-groove-salad" and sl.get(st.id) is not None

def test_rename_move_neighbor():
    sl = StationList(); sl.rename("kbs-25", "쿨"); assert sl.get("kbs-25").name == "쿨"
    sl.rename("kbs-25", "  "); assert sl.get("kbs-25").name == "KBS 쿨FM"
    sl.move("mbc-mfm", "kbs-21")
    dom = [s.id for k, _, v in sl.groups() if k == "kr:big3" for s in v]
    assert dom[0] == "mbc-mfm"
    sl.move("mbc-mfm", "net-moe-lofi"); assert [s.id for k, _, v in sl.groups() if k == "kr:big3" for s in v][0] == "mbc-mfm"
    vis = sl.visible()
    assert sl.neighbor(vis[-1].id, 1).id == vis[0].id and sl.neighbor(vis[0].id, -1).id == vis[-1].id

def test_json_round_trip(tmp_path):
    sl = StationList(); st, _ = sl.add_url("우리 동네", "https://a.example/x.mp3")
    sl.set_favorite(st.id, True); sl.rename("kbs-21", "1R"); sl.remove("mbc-sfm"); sl.move("kbs-25", "kbs-21")
    p = tmp_path / "stations.json"; save_stations(str(p), sl)
    back = load_stations(str(p))
    assert back.to_json() == sl.to_json() and back.get(st.id).name == "우리 동네"

def test_load_tolerates_unknown_and_stale_ids(tmp_path):
    p = tmp_path / "stations.json"
    p.write_text(json.dumps({"version": 9, "zzz": 1, "favorites": ["gone", "kbs-25"], "hidden": ["nope"],
                             "renamed": {"gone": "x"}, "order": {"domestic": ["gone", "mbc-mfm"]},
                             "user": [{"id": "url-1", "name": "ok", "url": "https://ok.example/s"},
                                      {"id": "url-2", "name": "bad"}]}), encoding="utf-8")
    sl = load_stations(str(p))
    assert sl.is_favorite("kbs-25") and sl.get("url-1").name == "ok" and sl.get("url-2") is None
    assert [s.id for k, _, v in sl.groups() if k == "kr:big3" for s in v][0] == "mbc-mfm"

@pytest.mark.parametrize("content", [b"{not json", b"[1, 2]", b"\xff\xfe"])
def test_corrupt_file_moved_to_bak(tmp_path, content):
    p = tmp_path / "stations.json"; p.write_bytes(content)
    sl = load_stations(str(p))
    assert len(sl.visible()) == 72 and (tmp_path / "stations.json.bak").read_bytes() == content and not p.exists()

def test_missing_file_gives_builtins(tmp_path):
    assert len(load_stations(str(tmp_path / "none.json")).visible()) == 72

def test_same_url():
    assert same_url("HTTP://A.b/x/", "http://a.b/x") and not same_url("http://a.b/x", "http://a.b/y")


def test_user_ids_do_not_collide_in_same_millisecond(monkeypatch):
    import funplayer.core.stations as mod
    monkeypatch.setattr(mod.time, "time", lambda: 1000.0)
    sl = StationList()
    a, _ = sl.add_url("a", "https://a.example/1.mp3")
    b, _ = sl.add_url("b", "https://a.example/2.mp3")
    assert a.id == "url-1000000" and b.id == "url-1000001"


def test_hidden_builtin_cannot_be_favorited():
    sl = StationList(); sl.remove("kbs-21")
    sl.set_favorite("kbs-21", True)
    assert not sl.is_favorite("kbs-21")


def test_save_failure_leaves_no_tmp_file(tmp_path, monkeypatch):
    import funplayer.core.stations as mod
    def boom(src, dst):
        raise OSError("locked")
    monkeypatch.setattr(mod.os, "replace", boom)
    p = tmp_path / "stations.json"
    save_stations(str(p), StationList())
    assert not p.exists() and not (tmp_path / "stations.json.tmp").exists()


def test_kr_groups_keys_titles_and_counts():
    groups = StationList().groups()
    kr = [(k, t, len(v)) for k, t, v in groups if k.startswith("kr:")]
    assert kr == [("kr:big3", "국내 · KBS·MBC·SBS (12)", 12),
                  ("kr:more", "국내 · EBS·CBS·YTN 등 (13)", 13),
                  ("kr:faith", "국내 · 종교 방송 (4)", 4),
                  ("kr:community", "국내 · 공동체 라디오 (7)", 7)]
    keys = [k for k, _, _ in groups]
    assert keys[:4] == KR_KEYS and keys[4] == f"genre:{GENRES[0]}" and keys[-1] == "genre:" + GENRES[-1]


def test_kr_builtins_shape():
    kr = [s for s in BUILTIN_STATIONS if s.group in KR_KEYS]
    assert len(kr) == 36 and len({s.id for s in kr}) == 36
    assert [s.id for s in kr if s.group == "kr:big3"][:3] == ["kbs-21", "kbs-22", "kbs-23"]
    assert all(s.key.startswith(("http://", "https://")) for s in kr if s.kind == "url")
    assert {s.kind for s in kr if s.group == "kr:big3"} == {"kbs", "mbc", "sbs"}
    assert {s.kind for s in kr if s.group != "kr:big3"} == {"url"}
    sbs = {s.id: s.key for s in kr if s.kind == "sbs"}
    assert sbs == {"sbs-lovefm": "lovepc/lovefm", "sbs-powerfm": "powerpc/powerfm", "sbs-dmb": "sbsdmbpc/sbsdmb"}
    assert {s.source for s in kr if s.group == "kr:community"} == {"공동체"}
    assert not any(s.group == "domestic" for s in BUILTIN_STATIONS)


def test_old_domestic_order_migrates_to_big3():
    sl = StationList.from_json({"order": {"domestic": ["mbc-mfm", "kbs-25"]}})
    ids = [s.id for k, _, v in sl.groups() if k == "kr:big3" for s in v]
    assert ids[:2] == ["mbc-mfm", "kbs-25"] and "domestic" not in sl.to_json()["order"]
    assert sl.to_json()["order"]["kr:big3"] == ["mbc-mfm", "kbs-25"]


def test_old_domestic_order_does_not_override_big3():
    sl = StationList.from_json({"order": {"domestic": ["mbc-mfm"], "kr:big3": ["kbs-25"]}})
    assert sl.to_json()["order"] == {"kr:big3": ["kbs-25"]}


def test_typed_kr_url_is_duplicate_of_builtin():
    sl = StationList()
    st, new = sl.add_url("x", "https://ebsonair.ebs.co.kr/cloud1/iradio/playlist.m3u8")
    assert not new and st.id == "kr-ebs-bandi"
