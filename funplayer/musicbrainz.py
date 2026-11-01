"""MusicBrainz / Cover Art Archive client (Qt-free, stdlib only)."""
from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

USER_AGENT = "my-fun/0.5 ( personal music player )"
TIMEOUT = 10
MIN_SPACING = 1.0
BUSY_RETRY_WAITS = (2.0, 4.0)
SEARCH_URL = "https://musicbrainz.org/ws/2/recording"
COVER_URL = "https://coverartarchive.org/release/{}/front-500"

MSG_NETWORK = "인터넷에 연결하지 못했습니다"
MSG_BUSY = "MusicBrainz가 바쁩니다. 잠시 뒤 다시 눌러 보세요"


class MusicBrainzError(Exception):
    pass


@dataclass(frozen=True)
class Candidate:
    title: str
    artist: str
    album: str
    year: str
    track: str
    genre: str
    release_id: str

    def label(self) -> str:
        return " · ".join(p for p in (self.title, self.artist, self.album, self.year) if p)


def _default_fetch(url: str, headers: dict) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _artist(rec: dict) -> str:
    return "".join(
        (c.get("name") or "") + (c.get("joinphrase") or "")
        for c in rec.get("artist-credit") or []
    ).strip()


def _genre(rec: dict) -> str:
    tags = rec.get("tags") or []
    if not tags:
        return ""
    return max(tags, key=lambda t: t.get("count", 0)).get("name") or ""


def _track(rel: dict) -> str:
    for m in rel.get("media") or []:
        for t in m.get("track") or []:
            # number는 "1-9", "A1" 같은 표시 글자일 수 있어 디스크 안 순번(position)을 먼저 쓴다
            if isinstance(t.get("position"), int) and t["position"] > 0:
                return str(t["position"])
            number = str(t.get("number") or "")
            if number.isdigit():
                return number
            tail = number.rsplit("-", 1)[-1]
            return tail if tail.isdigit() else ""
    return ""


class Client:
    def __init__(
        self,
        fetch: Callable[[str, dict], bytes] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._fetch = fetch or _default_fetch
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last: float | None = None

    def _wait(self) -> None:
        with self._lock:
            if self._last is not None:
                gap = MIN_SPACING - (self._clock() - self._last)
                if gap > 0:
                    self._sleep(gap)
            self._last = self._clock()

    def _get(self, url: str, headers: dict) -> bytes:
        try:
            return self._fetch(url, headers)
        except urllib.error.HTTPError as e:
            raise MusicBrainzError(MSG_BUSY if e.code == 503 else MSG_NETWORK) from e
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
            raise MusicBrainzError(MSG_NETWORK) from e

    def search(self, title: str, artist: str, limit: int = 10) -> list[Candidate]:
        query = f'recording:"{_esc(title)}"'
        if artist:
            query += f' AND artist:"{_esc(artist)}"'
        url = (
            f"{SEARCH_URL}?query={urllib.parse.quote(query)}&fmt=json&limit={limit}"
        )
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        for attempt in range(len(BUSY_RETRY_WAITS) + 1):
            self._wait()
            try:
                raw = self._get(url, headers)
                break
            except MusicBrainzError as e:
                # 503은 잠깐 몰린 것: 조금 기다렸다 다시 묻는다(MusicBrainz 권장)
                if str(e) != MSG_BUSY or attempt == len(BUSY_RETRY_WAITS):
                    raise
                self._sleep(BUSY_RETRY_WAITS[attempt])
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise MusicBrainzError(MSG_NETWORK) from e
        if not isinstance(data, dict):
            raise MusicBrainzError(MSG_NETWORK)
        out: list[Candidate] = []
        for rec in data.get("recordings") or []:
            base = (rec.get("title") or "", _artist(rec))
            genre = _genre(rec)
            releases = rec.get("releases") or [{}]
            for rel in releases:
                date = rel.get("date") or ""
                year = date[:4] if date[:4].isdigit() else ""
                out.append(Candidate(
                    base[0], base[1], rel.get("title") or "", year,
                    _track(rel), genre, rel.get("id") or "",
                ))
                if len(out) >= limit:
                    return out
        return out

    def cover(self, release_id: str) -> bytes | None:
        try:
            return self._get(COVER_URL.format(urllib.parse.quote(release_id)),
                             {"User-Agent": USER_AGENT})
        except MusicBrainzError as e:
            cause = e.__cause__
            if isinstance(cause, urllib.error.HTTPError) and cause.code == 404:
                return None
            raise


_default: Client | None = None
_default_lock = threading.Lock()


def default_client() -> Client:
    global _default
    with _default_lock:
        if _default is None:
            _default = Client()
        return _default
