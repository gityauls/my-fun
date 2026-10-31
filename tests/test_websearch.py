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


class _Resp:
    def __init__(self, chunks, url="https://x.com/a.jpg", clock=None, step=0.0):
        self._chunks, self._url, self._clock, self._step = list(chunks), url, clock, step

    def geturl(self):
        return self._url

    def read(self, n=-1):
        if self._clock is not None:
            self._clock[0] += self._step
        chunk = self._chunks.pop(0) if self._chunks else b""
        if 0 <= n < len(chunk):
            self._chunks.insert(0, chunk[n:])
            chunk = chunk[:n]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_default_fetch_reads_in_chunks_up_to_limit():
    resp = _Resp([b"a" * 10, b"b" * 10, b"c" * 10])
    data = websearch._default_fetch("https://x.com/a.jpg", {}, 15, opener=lambda req, timeout: resp)
    assert data == b"a" * 10 + b"b" * 5


def test_default_fetch_total_deadline():
    now = [0.0]
    resp = _Resp([b"x"] * 100, clock=now, step=4.0)   # 읽을 때마다 4초: 천천히 흘려 보내는 서버
    with pytest.raises(websearch.ImageFetchError):
        websearch._default_fetch("https://x.com/a.jpg", {}, 1000, opener=lambda req, timeout: resp,
                                 clock=lambda: now[0])


def test_default_fetch_rejects_non_http_final_url():
    resp = _Resp([b"x"], url="file:///c:/secret.jpg")
    with pytest.raises(websearch.ImageFetchError):
        websearch._default_fetch("https://x.com/a.jpg", {}, 10, opener=lambda req, timeout: resp)


def test_redirect_to_non_http_refused():
    import urllib.request
    handler = websearch._HttpOnlyRedirect()
    req = urllib.request.Request("https://x.com/a.jpg")
    with pytest.raises(websearch.ImageFetchError):
        handler.redirect_request(req, None, 302, "Found", {}, "ftp://evil/a.jpg")
