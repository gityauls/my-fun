from __future__ import annotations

import json
import urllib.error
import urllib.parse

import pytest

from funplayer import musicbrainz as mb

UA = "my-fun/0.5 ( personal music player )"

FIXTURE = {
    "recordings": [
        {
            "id": "r1",
            "title": "Song A",
            "artist-credit": [
                {"name": "Alice", "joinphrase": " feat. "},
                {"name": "Bob", "joinphrase": ""},
            ],
            "tags": [{"count": 1, "name": "pop"}, {"count": 5, "name": "rock"}],
            "releases": [
                {"id": "rel1", "title": "Album One", "date": "2001-05-06",
                 "media": [{"track": [{"number": "4"}]}]},
                {"id": "rel2", "title": "Album Two", "date": "1999",
                 "media": [{"track": [{"number": "7"}]}]},
            ],
        },
        {
            "id": "r2",
            "title": "Song B",
            "artist-credit": [{"name": "Carol"}],
            "releases": [{"id": "rel3", "title": "Album Three"}],
        },
    ]
}


class FakeTime:
    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


def make_client(fetch, ft=None):
    ft = ft or FakeTime()
    return mb.Client(fetch=fetch, clock=ft.clock, sleep=ft.sleep), ft


def ok_fetch(calls):
    def fetch(url, headers):
        calls.append((url, headers))
        return json.dumps(FIXTURE).encode()
    return fetch


def test_query_and_headers():
    calls = []
    c, _ = make_client(ok_fetch(calls))
    c.search("Hello", "Adele")
    c.search("Hello", "")
    c.search('a"b\\c', "")
    url1, h1 = calls[0]
    q1 = urllib.parse.parse_qs(urllib.parse.urlsplit(url1).query)
    assert url1.startswith("https://musicbrainz.org/ws/2/recording?query=")
    assert q1["query"] == ['recording:"Hello" AND artist:"Adele"']
    assert q1["fmt"] == ["json"] and q1["limit"] == ["10"]
    assert "%20" in url1 and " " not in url1
    assert h1["User-Agent"] == UA and h1["Accept"] == "application/json"
    q2 = urllib.parse.parse_qs(urllib.parse.urlsplit(calls[1][0]).query)
    assert q2["query"] == ['recording:"Hello"']
    q3 = urllib.parse.parse_qs(urllib.parse.urlsplit(calls[2][0]).query)
    assert q3["query"] == ['recording:"a\\"b\\\\c"']


def test_parse_candidates():
    c, _ = make_client(ok_fetch([]))
    r = c.search("x", "")
    assert len(r) == 3
    assert r[0] == mb.Candidate("Song A", "Alice feat. Bob", "Album One", "2001", "4", "rock", "rel1")
    assert r[1].album == "Album Two" and r[1].year == "1999" and r[1].track == "7"
    assert r[2] == mb.Candidate("Song B", "Carol", "Album Three", "", "", "", "rel3")
    assert len(c.search("x", "", limit=2)) == 2


def test_spacing():
    c, ft = make_client(ok_fetch([]))
    c.search("a", "")
    assert ft.sleeps == []
    ft.now += 0.25
    c.search("a", "")
    assert ft.sleeps == [pytest.approx(0.75)]
    ft.now += 5
    c.search("a", "")
    assert len(ft.sleeps) == 1


def test_errors():
    def net(url, headers):
        raise urllib.error.URLError("down")

    def busy(url, headers):
        raise urllib.error.HTTPError(url, 503, "busy", {}, None)

    def timeout(url, headers):
        raise TimeoutError()

    with pytest.raises(mb.MusicBrainzError, match="인터넷에 연결하지 못했습니다"):
        make_client(net)[0].search("a", "")
    with pytest.raises(mb.MusicBrainzError, match="MusicBrainz가 바쁩니다. 잠시 뒤 다시 눌러 보세요"):
        make_client(busy)[0].search("a", "")
    with pytest.raises(mb.MusicBrainzError, match="인터넷에 연결하지 못했습니다"):
        make_client(timeout)[0].search("a", "")


def test_cover_404_none():
    def f(url, headers):
        raise urllib.error.HTTPError(url, 404, "nf", {}, None)
    assert make_client(f)[0].cover("rel1") is None


def test_cover_bytes():
    calls = []

    def f(url, headers):
        calls.append(url)
        return b"\xff\xd8img"
    c, ft = make_client(f)
    assert c.cover("rel1") == b"\xff\xd8img"
    assert calls == ["https://coverartarchive.org/release/rel1/front-500"]
    c.cover("rel1")
    assert ft.sleeps == []  # no spacing for cover fetches


def test_cover_other_error():
    def f(url, headers):
        raise urllib.error.HTTPError(url, 500, "x", {}, None)
    with pytest.raises(mb.MusicBrainzError, match="인터넷에 연결하지 못했습니다"):
        make_client(f)[0].cover("rel1")


def test_label_skips_empty():
    assert mb.Candidate("T", "A", "", "2001", "", "", "r").label() == "T · A · 2001"
    assert mb.Candidate("T", "", "Al", "", "", "", "r").label() == "T · Al"


def test_default_client_shared():
    assert mb.default_client() is mb.default_client()


def test_odd_responses_become_network_error():
    import http.client

    def incomplete(url, headers):
        raise http.client.IncompleteRead(b"")

    with pytest.raises(mb.MusicBrainzError, match=mb.MSG_NETWORK):
        mb.Client(fetch=incomplete, sleep=lambda s: None).search("a", "b")
    with pytest.raises(mb.MusicBrainzError, match=mb.MSG_NETWORK):
        mb.Client(fetch=lambda u, h: b"[]", sleep=lambda s: None).search("a", "b")


def test_busy_retries_then_succeeds():
    tries = []

    def flaky(url, headers):
        tries.append(url)
        if len(tries) < 3:
            raise urllib.error.HTTPError(url, 503, "busy", {}, None)
        return json.dumps(FIXTURE).encode()

    c, ft = make_client(flaky)
    assert c.search("a", "")
    assert len(tries) == 3
    assert 2.0 in ft.sleeps and 4.0 in ft.sleeps


def test_track_uses_position_over_display_number():
    assert mb._track({"media": [{"track": [{"number": "1-9", "position": 9}]}]}) == "9"
    assert mb._track({"media": [{"track": [{"number": "1-9"}]}]}) == "9"
    assert mb._track({"media": [{"track": [{"number": "A1"}]}]}) == ""
