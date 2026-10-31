"""Browser search URLs and single-image download (Qt-free, stdlib only)."""
from __future__ import annotations

import http.client
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from funplayer import musicbrainz
from funplayer.core import tagguess

GENIE_URL = "https://www.genie.co.kr/search/searchMain?query={q}"
MELON_URL = "https://www.melon.com/search/total/index.htm?q={q}"
SITES = {"genie": GENIE_URL, "melon": MELON_URL}
MAX_IMAGE = 10 * 1024 * 1024
TIMEOUT = 10


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


def _default_fetch(url: str, headers: dict, limit: int) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        # 큰 파일은 limit까지만 읽고 멈춘다
        return resp.read(limit)


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
