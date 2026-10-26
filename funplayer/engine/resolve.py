from __future__ import annotations

import http.client
import json
import urllib.request
from collections.abc import Callable
from urllib.parse import urlsplit

from funplayer.core.stations import Station

APP_UA = "my-fun/0.3 (+local player)"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

KBS_URL = "https://cfpwwwapi.kbs.co.kr/api/v1/landing/live/channel_code/{key}"
MBC_URL = "https://sminiplay.imbc.com/aacplay.ashx?agent=webapp&channel={key}"
MBC_REFERER = "https://mini.imbc.com/"
SBS_URL = "https://apis.sbs.co.kr/play-api/1.0/livestream/{key}?protocol=hls&ssl=Y"

FETCH_TIMEOUT = 10
MAX_BYTES = 1_000_000

Fetch = Callable[[str, dict[str, str]], bytes]


class ResolveError(Exception):
    pass


def default_fetch(url: str, headers: dict[str, str]) -> bytes:
    if not _is_text_url(url):
        raise ValueError("http(s) 주소만 받을 수 있습니다")
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        return resp.read(MAX_BYTES)


def resolve(station: Station, fetch: Fetch = default_fetch) -> str:
    """재생할 주소를 돌려준다. 방송사 주소와 목록 파일만 받아 보고, 나머지는 그대로 쓴다."""
    if station.kind == "kbs":
        return _resolve_kbs(station.key, fetch)
    if station.kind == "mbc":
        return _resolve_mbc(station.key, fetch)
    if station.kind == "sbs":
        return _resolve_sbs(station.key, fetch)
    if station.kind == "url":
        ext = _extension(station.key)
        if ext in (".m3u", ".pls"):
            return _resolve_playlist(station.key, ext, fetch)
        return station.key
    raise ResolveError(f"알 수 없는 방송 종류: {station.kind}")


def _call(fetch: Fetch, url: str, headers: dict[str, str]) -> bytes:
    # TimeoutError도 OSError의 하위 클래스다. IncompleteRead 등은 HTTPException이다.
    try:
        return fetch(url, headers)
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise ResolveError(f"주소를 받지 못했습니다: {e}") from e


def _resolve_kbs(key: str, fetch: Fetch) -> str:
    url = KBS_URL.format(key=key)
    body = _call(fetch, url, {"User-Agent": BROWSER_UA})
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, RecursionError) as e:
        raise ResolveError("KBS 응답을 읽지 못했습니다") from e
    items = data.get("channel_item") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ResolveError("KBS 응답에 방송 주소가 없습니다")
    usable = [i for i in items if isinstance(i, dict) and _is_text_url(i.get("service_url"))]
    usable.sort(key=lambda i: i.get("media_type") != "radio")  # radio 항목을 먼저 본다
    if not usable:
        raise ResolveError("KBS 응답에 방송 주소가 없습니다")
    return usable[0]["service_url"].strip()


def _resolve_mbc(key: str, fetch: Fetch) -> str:
    url = MBC_URL.format(key=key)
    body = _call(fetch, url, {"User-Agent": BROWSER_UA, "Referer": MBC_REFERER})
    lines = body.decode("utf-8", "replace").strip().splitlines()
    text = lines[0].strip() if lines else ""
    if not _is_text_url(text):
        raise ResolveError("MBC 응답이 주소가 아닙니다")
    return text


def _resolve_sbs(key: str, fetch: Fetch) -> str:
    # 앱 이름(APP_UA)만 보낸다. 브라우저 흉내나 Referer 같은 머리말은 쓰지 않는다.
    url = SBS_URL.format(key=key)
    body = _call(fetch, url, {"User-Agent": APP_UA})
    lines = body.decode("utf-8", "replace").strip().splitlines()
    text = lines[0].strip() if lines else ""
    if not _is_text_url(text):
        raise ResolveError("SBS 응답이 주소가 아닙니다")
    return text


def _resolve_playlist(url: str, ext: str, fetch: Fetch) -> str:
    body = _call(fetch, url, {"User-Agent": APP_UA})
    lines = body.decode("utf-8", "replace").splitlines()
    for line in lines:
        line = line.strip()
        if ext == ".pls":
            name, sep, value = line.partition("=")
            if not sep or not name.lower().startswith("file"):
                continue
            line = value.strip()
        elif not line or line.startswith("#"):
            continue
        if _is_text_url(line):
            return line
    raise ResolveError("목록 파일에 재생할 주소가 없습니다")


def _extension(url: str) -> str:
    """주소 경로의 확장자를 소문자로 돌려준다 (질의 문자열 제외)."""
    try:
        path = urlsplit(url.strip()).path
    except ValueError:
        return ""
    dot = path.rfind(".")
    return path[dot:].lower() if dot != -1 and "/" not in path[dot:] else ""


def _is_text_url(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith(("http://", "https://"))
