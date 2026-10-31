from __future__ import annotations

import pytest

from funplayer import musicbrainz, websearch


def test_search_url_korean():
    assert websearch.search_url("genie", "서지원 I Miss You") == (
        "https://www.genie.co.kr/search/searchMain?query=%EC%84%9C%EC%A7%80%EC%9B%90%20I%20Miss%20You")


def test_search_url_melon():
    assert websearch.search_url("melon", "a&b c") == (
        "https://www.melon.com/search/total/index.htm?q=a%26b%20c")


def test_search_terms_fields():
    assert websearch.search_terms(" 서지원 ", " I Miss You ", r"C:\m\x.mp3") == "서지원 I Miss You"
    assert websearch.search_terms("", "Only Title", r"C:\m\x.mp3") == "Only Title"


def test_search_terms_from_filename():
    assert websearch.search_terms("", "", r"C:\m\02. I Miss You.mp3") == "I Miss You"


def test_search_terms_empty():
    assert websearch.search_terms("", "", "") == ""


def test_fetch_image_headers():
    seen = {}

    def fake(url, headers, limit):
        seen.update(url=url, headers=headers, limit=limit)
        return b"IMG"

    assert websearch.fetch_image("https://x.com/a.jpg", fetch=fake) == b"IMG"
    assert seen["headers"]["User-Agent"] == musicbrainz.USER_AGENT
    assert seen["limit"] == websearch.MAX_IMAGE + 1


def test_fetch_image_too_big():
    with pytest.raises(websearch.ImageFetchError):
        websearch.fetch_image("http://x.com/a.jpg",
                              fetch=lambda u, h, l: b"0" * (websearch.MAX_IMAGE + 1))


def test_fetch_image_bad_scheme():
    def fake(u, h, l):
        raise AssertionError("must not fetch")

    for url in ("file:///c:/x.jpg", "ftp://x.com/a.jpg", ""):
        with pytest.raises(websearch.ImageFetchError):
            websearch.fetch_image(url, fetch=fake)


def test_fetch_image_oserror_wrapped():
    import http.client
    import urllib.error

    for exc in (OSError("x"), ValueError("x"), http.client.IncompleteRead(b""),
                urllib.error.URLError("x")):
        def fake(u, h, l, exc=exc):
            raise exc

        with pytest.raises(websearch.ImageFetchError) as ei:
            websearch.fetch_image("https://x.com/a.jpg", fetch=fake)
        assert ei.value.__cause__ is exc
