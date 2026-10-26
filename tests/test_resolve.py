import json
import pytest
from funplayer.core.stations import Station
from funplayer.engine.resolve import APP_UA, BROWSER_UA, ResolveError, resolve

def st(kind, key): return Station("x", "X", kind, key, "", "user", False)

class FakeFetch:
    def __init__(self, replies): self.replies, self.calls = replies, []
    def __call__(self, url, headers):
        self.calls.append((url, headers))
        r = self.replies.get(url)
        if isinstance(r, Exception): raise r
        if r is None: raise OSError("404")
        return r

def test_kbs_picks_service_url():
    url = "https://cfpwwwapi.kbs.co.kr/api/v1/landing/live/channel_code/25"
    f = FakeFetch({url: json.dumps({"channel_item": [{"media_type": "radio", "service_url": "https://k/2fm.m3u8?P=1"}]}).encode()})
    assert resolve(st("kbs", "25"), f) == "https://k/2fm.m3u8?P=1"
    assert f.calls[0][1]["User-Agent"] == BROWSER_UA

def test_mbc_reads_text_with_referer():
    url = "https://sminiplay.imbc.com/aacplay.ashx?agent=webapp&channel=mfm"
    f = FakeFetch({url: b"  https://m/mfm/playlist.m3u8?t=1\n"})
    assert resolve(st("mbc", "mfm"), f) == "https://m/mfm/playlist.m3u8?t=1"
    assert f.calls[0][1]["Referer"] == "https://mini.imbc.com/"

@pytest.mark.parametrize("body", [b"{}", b'{"channel_item": []}', b"<html>", b'{"channel_item": [{"x": 1}]}'])
def test_kbs_bad_reply_raises(body):
    f = FakeFetch({"https://cfpwwwapi.kbs.co.kr/api/v1/landing/live/channel_code/21": body})
    with pytest.raises(ResolveError):
        resolve(st("kbs", "21"), f)

def test_mbc_non_url_raises():
    f = FakeFetch({"https://sminiplay.imbc.com/aacplay.ashx?agent=webapp&channel=sfm": b"error"})
    with pytest.raises(ResolveError):
        resolve(st("mbc", "sfm"), f)

def test_plain_and_hls_urls_pass_through_without_fetch():
    f = FakeFetch({})
    assert resolve(st("url", "http://a/live.mp3"), f) == "http://a/live.mp3"
    assert resolve(st("url", "https://a/x.m3u8"), f) == "https://a/x.m3u8" and f.calls == []

def test_m3u_and_pls_take_first_http_entry():
    f = FakeFetch({"http://a/l.m3u": b"#EXTM3U\n#EXTINF:-1,x\nhttp://s/one\nhttp://s/two\n",
                   "http://a/l.pls": b"[playlist]\nNumberOfEntries=1\nFile1=https://s/p\nTitle1=x\n"})
    assert resolve(st("url", "http://a/l.m3u"), f) == "http://s/one"
    assert resolve(st("url", "http://a/l.pls"), f) == "https://s/p"
    assert f.calls[0][1]["User-Agent"] == APP_UA

def test_resolve_rejects_non_audio_playlist():
    f = FakeFetch({"http://a/l.m3u": b"<html><body>not found</body></html>"})
    with pytest.raises(ResolveError):
        resolve(st("url", "http://a/l.m3u"), f)

def test_fetch_errors_become_resolve_error():
    f = FakeFetch({"https://sminiplay.imbc.com/aacplay.ashx?agent=webapp&channel=sfm": TimeoutError()})
    with pytest.raises(ResolveError):
        resolve(st("mbc", "sfm"), f)
