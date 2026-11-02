"""Browser search URLs and single-image download (Qt-free, stdlib only)."""
from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from funplayer import musicbrainz
from funplayer.core import tagguess

GENIE_URL = "https://www.genie.co.kr/search/searchMain?query={q}"
MELON_URL = "https://www.melon.com/search/total/index.htm?q={q}"
GOOGLE_IMAGES_URL = "https://www.google.com/search?tbm=isch&q={q}"
APPLE_MUSIC_URL = "https://music.apple.com/kr/search?term={q}"
SITES = {"genie": GENIE_URL, "melon": MELON_URL, "google_images": GOOGLE_IMAGES_URL, "apple": APPLE_MUSIC_URL}
# 여러 곡 태그 표의 우클릭 메뉴 (차례대로)
SITE_LABELS = [("genie", "지니에서 찾기"), ("melon", "멜론에서 찾기"),
               ("google_images", "해외: 구글 이미지에서 찾기"), ("apple", "해외: 애플 뮤직에서 찾기")]
MAX_IMAGE = 10 * 1024 * 1024
TIMEOUT = 10
CHUNK = 64 * 1024


class ImageFetchError(Exception):
    pass


def search_terms(artist: str, title: str, path: str) -> str:
    artist, title = artist.strip(), title.strip()
    if not artist and not title:
        # 태그가 비면 파일명에서 추정
        artist, title = tagguess.guess_from_filename(path)
        title = tagguess.clean_search_title(title)
    return f"{artist.strip()} {title.strip()}".strip()


def search_url(site: str, terms: str) -> str:
    return SITES[site].format(q=urllib.parse.quote(terms, safe=""))


class _HttpOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # http/https가 아닌 곳(file:, ftp: 등)으로 가는 리다이렉트는 따라가지 않는다
        if urllib.parse.urlparse(newurl).scheme.lower() not in ("http", "https"):
            raise ImageFetchError("http/https 주소만 받을 수 있습니다")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(req, timeout):
    return urllib.request.build_opener(_HttpOnlyRedirect).open(req, timeout=timeout)


def _default_fetch(url: str, headers: dict, limit: int, opener=None, clock=time.monotonic) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    deadline = clock() + TIMEOUT   # 소켓 제한 시간과 별개로, 전체 받기에 거는 마감
    with (opener or _open)(req, TIMEOUT) as resp:
        if urllib.parse.urlparse(resp.geturl()).scheme.lower() not in ("http", "https"):
            raise ImageFetchError("http/https 주소만 받을 수 있습니다")
        parts: list[bytes] = []
        got = 0
        while got < limit:   # 큰 파일은 limit까지만 읽고 멈춘다
            chunk = resp.read(min(CHUNK, limit - got))
            if not chunk:
                break
            parts.append(chunk)
            got += len(chunk)
            if clock() > deadline:
                raise ImageFetchError("그림을 받는 데 너무 오래 걸립니다")
        return b"".join(parts)


def fetch_image(url: str, fetch: Callable[[str, dict, int], bytes] | None = None) -> bytes:
    if urllib.parse.urlparse(url).scheme.lower() not in ("http", "https"):
        raise ImageFetchError("http/https 주소만 받을 수 있습니다")
    try:
        data = (fetch or _default_fetch)(url, {"User-Agent": musicbrainz.USER_AGENT}, MAX_IMAGE + 1)
    except (OSError, ValueError, http.client.HTTPException, urllib.error.URLError) as e:
        raise ImageFetchError(str(e)) from e
    if len(data) > MAX_IMAGE:
        raise ImageFetchError("이미지가 너무 큽니다")
    return data
