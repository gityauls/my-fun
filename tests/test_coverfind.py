import json
import urllib.parse

import pytest

from funplayer import coverfind, musicbrainz
from funplayer.coverfind import SRC_APPLE, SRC_MB, CoverFinder, CoverFindError, Found, ITunes, judge

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20
JPG = b"\xff\xd8\xff\xe0" + b"0" * 20


def apple(*songs):
    return json.dumps({"results": [
        {"artistName": a, "trackName": t, "collectionName": c, "releaseDate": "2017-04-03T07:00:00Z",
         "artworkUrl100": f"https://is1.mzstatic.com/{t}/100x100bb.jpg"} for a, t, c in songs]}).encode()


class FakeMB:
    def __init__(self, cands=(), covers=None, error=None):
        self.cands, self.covers, self.error = list(cands), covers or {}, error
        self.searched = []

    def search(self, title, artist, limit=10):
        self.searched.append((title, artist))
        if self.error:
            raise musicbrainz.MusicBrainzError(self.error)
        return self.cands

    def cover(self, release_id):
        return self.covers.get(release_id)


def cand(title, artist, album="앨범", rid="r1"):
    return musicbrainz.Candidate(title, artist, album, "2000", "", "", rid)


def finder(apple_reply=b'{"results": []}', mb=None, images=None, urls=None):
    def fetch(url):
        if urls is not None:
            urls.append(url)
        if isinstance(apple_reply, Exception):
            raise apple_reply
        return apple_reply
    itunes = ITunes(fetch=fetch, clock=lambda: 0.0, sleep=lambda s: None)
    return CoverFinder(itunes, mb or FakeMB(), fetch_image=lambda url: (images or {}).get(url, JPG))


# ---- 맞는지 보기 ----
@pytest.mark.parametrize("artist,title,f_artist,f_title,want", [
    ("멜로망스", "선물", "멜로망스", "선물", True),
    ("멜로망스", "선물", "MeloMance(멜로망스)", "선물", True),        # 별칭
    ("애즈원(As One)", "Day By Day", "As One", "Day by Day", True),  # 대소문자·별칭
    ("015B", "텅빈 거리에서", "015B", "텅빈 거리에서 (Remastered)", True),   # 괄호는 뺌
    ("015B", "텅빈 거리에서", "015B", "텅빈 거리에서 2", False),     # 제목이 조금 다름
    ("버스커버스커", "벚꽃엔딩", "Busker Busker", "벚꽃 엔딩", False),  # 가수 표기가 다름
    ("멜로망스", "선물", "멜로망스", "부끄러움", None),
    ("", "", "멜로망스", "선물", None),
])
def test_judge(artist, title, f_artist, f_title, want):
    assert judge(artist, title, Found(SRC_APPLE, f_artist, f_title, "", "", "")) is want


# ---- 애플 뮤직 ----
def test_itunes_search_takes_big_art():
    urls = []
    it = ITunes(fetch=lambda u: urls.append(u) or apple(("멜로망스", "선물", "Moonlight")),
                clock=lambda: 0.0, sleep=lambda s: None)
    [f] = it.search("멜로망스", "선물 (Live)")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)
    assert q["term"] == ["멜로망스 선물"] and q["country"] == ["US"] and q["entity"] == ["song"]
    assert f == Found(SRC_APPLE, "멜로망스", "선물", "Moonlight", "2017", "https://is1.mzstatic.com/선물/600x600bb.jpg")


def test_itunes_waits_between_questions():
    t = [0.0]
    slept = []
    it = ITunes(fetch=lambda u: apple(), clock=lambda: t[0], sleep=lambda s: slept.append(s))
    it.search("a", "b")
    t[0] = 1.0
    it.search("a", "c")
    assert slept == [coverfind.ITUNES_SPACING - 1.0]


def test_itunes_network_error():
    it = ITunes(fetch=lambda u: (_ for _ in ()).throw(OSError("x")), clock=lambda: 0.0, sleep=lambda s: None)
    with pytest.raises(CoverFindError):
        it.search("a", "b")


# ---- 찾는 차례 ----
def test_korean_song_asks_apple_first_and_stops_on_sure_hit():
    mb = FakeMB([cand("선물", "멜로망스")], {"r1": PNG})
    hit = finder(apple(("멜로망스", "선물", "Moonlight")), mb).find("멜로망스", "선물")
    assert hit.source == SRC_APPLE and hit.sure and hit.album == "Moonlight" and hit.image == JPG
    assert mb.searched == []


def test_foreign_song_asks_musicbrainz_first():
    urls = []
    mb = FakeMB([cand("Yellow", "Coldplay", "Parachutes")], {"r1": PNG})
    hit = finder(apple(("Coldplay", "Yellow", "X")), mb, urls=urls).find("Coldplay", "Yellow")
    assert hit.source == SRC_MB and hit.sure and hit.album == "Parachutes" and hit.image == PNG
    assert urls == []


def test_falls_back_to_other_source_when_first_has_nothing():
    mb = FakeMB([cand("선물", "멜로망스")], {"r1": PNG})
    hit = finder(apple(), mb).find("멜로망스", "선물")
    assert hit.source == SRC_MB and hit.sure


def test_similar_hit_kept_but_sure_hit_elsewhere_wins():
    mb = FakeMB([cand("선물", "멜로망스")], {"r1": PNG})
    hit = finder(apple(("멜로망스", "선물 2", "X")), mb).find("멜로망스", "선물")
    assert hit.source == SRC_MB and hit.sure


def test_only_similar_hit_is_not_sure():
    hit = finder(apple(("Busker Busker", "벚꽃 엔딩", "1집"))).find("버스커버스커", "벚꽃엔딩")
    assert hit.source == SRC_APPLE and not hit.sure


def test_musicbrainz_tries_next_candidate_without_cover():
    mb = FakeMB([cand("Yellow", "Coldplay", "A", "r1"), cand("Yellow", "Coldplay", "B", "r2")], {"r2": PNG})
    hit = finder(mb=mb).find("Coldplay", "Yellow")
    assert hit.album == "B"


def test_not_an_image_is_skipped():
    hit = finder(apple(("멜로망스", "선물", "X")), images={"https://is1.mzstatic.com/선물/600x600bb.jpg": b"<html>"}
                 ).find("멜로망스", "선물")
    assert hit is None


def test_nothing_found_and_no_title():
    assert finder().find("멜로망스", "선물") is None
    assert finder(apple(("멜로망스", "선물", "X"))).find("멜로망스", "  ") is None


def test_both_sources_down_raises():
    with pytest.raises(CoverFindError):
        finder(OSError("down"), FakeMB(error="막힘")).find("멜로망스", "선물")


def test_one_source_down_still_uses_other():
    hit = finder(OSError("down"), FakeMB([cand("선물", "멜로망스")], {"r1": PNG})).find("멜로망스", "선물")
    assert hit.source == SRC_MB


def test_apple_uses_us_store_because_korea_store_is_empty():
    urls = []
    finder(apple(), urls=urls).find("멜로망스", "선물")
    assert "country=US" in urls[0]


def test_english_named_korean_song_becomes_check_when_top_results_share_artist():
    hit = finder(apple(("MeloMance", "Gift", "Moonlight - EP"), ("MeloMance", "Tale", "The Fairy Tale"))
                 ).find("멜로망스", "선물")
    assert hit.source == SRC_APPLE and not hit.sure and hit.title == "Gift"


def test_mixed_artists_with_no_match_is_not_found():
    assert finder(apple(("The Chicks", "Sleep at Night", "X"), ("PARCO", "CHUCK", "Y"))).find("Chuck", "사랑") is None


def test_karaoke_versions_are_skipped():
    hit = finder(apple(("코케", "그대 눈물까지도", "그대 눈물까지도 : Originally Performed By 투투 (Karaoke)"),
                       ("Two Two", "그대 눈물까지도", "TWO TWO"))).find("투투", "그대 눈물까지도")
    assert hit.album == "TWO TWO" and not hit.sure


def test_summer_is_not_karaoke():
    hit = finder(apple(("Calvin Harris", "Summer", "Motion"))).find("Calvin Harris", "Summer")
    assert hit is not None and hit.sure
