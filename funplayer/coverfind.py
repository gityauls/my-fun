"""그림 없는 곡의 앨범 그림 찾기 (5-D, Qt-free).

가요(한글이 든 곡)는 애플 뮤직(iTunes 검색 API) → MusicBrainz, 해외 곡은 거꾸로 찾는다.
iTunes 검색 API의 한국 스토어(KR)는 음악 결과가 비어 와서, 가요도 들어 있는 미국 스토어를 쓴다.
지니·멜론은 robots.txt가 자동 수집을 막아 두어 여기서 쓰지 않는다(브라우저로 여는 것만).
"""
from __future__ import annotations

import http.client
import json
import re
import threading
import time
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import Callable

from funplayer import musicbrainz, websearch
from funplayer.core import bulktag
from funplayer.engine.tagwrite import picture_mime

ITUNES_URL = "https://itunes.apple.com/search?term={q}&country=US&media=music&entity=song&limit=10"
ITUNES_SPACING = 3.0   # 애플 검색 API는 1분에 20번쯤까지
ITUNES_ART = "600x600bb"
MAX_REPLY = 2 * 1024 * 1024
MAX_COVER_TRIES = 3    # MusicBrainz 후보마다 그림이 없을 수 있어 몇 개까지 받아 본다

SRC_APPLE = "애플 뮤직"
SRC_MB = "MusicBrainz"
MSG_NETWORK = "인터넷에 연결하지 못했습니다"

_PUNCT = re.compile(r"[\W_]+")
_ART_SIZE = re.compile(r"\d+x\d+bb")
_KARAOKE = re.compile(r"karaoke|\[mr\]|\(mr\)|반주|노래방|originally performed|instrumental", re.IGNORECASE)


class CoverFindError(Exception):
    pass


@dataclass(frozen=True)
class Found:
    """검색 결과 한 곡. art는 애플이면 그림 주소, MusicBrainz면 release id."""
    source: str
    artist: str
    title: str
    album: str
    year: str
    art: str


@dataclass(frozen=True)
class Hit:
    source: str
    artist: str
    title: str
    album: str
    year: str
    image: bytes
    sure: bool   # 가수·제목이 딱 맞음 (아니면 비슷하기만 함)


def _key(text: str) -> str:
    return _PUNCT.sub("", bulktag.clean_title(text or "").casefold())


def _artist_keys(name: str) -> set[str]:
    keys: set[str] = set()
    for piece in bulktag._ARTIST_SEP.split(name or ""):
        ko, en = bulktag.split_alias(piece)
        keys |= {_PUNCT.sub("", x.casefold()) for x in (ko, en) if x}
    return keys - {""}


def judge(artist: str, title: str, found: Found) -> bool | None:
    """True = 딱 맞음, False = 비슷함(확인 필요), None = 다른 곡."""
    want, got = _key(title), _key(found.title)
    if not want or not got:
        return None
    same_title = want == got
    same_artist = bool(_artist_keys(artist) & _artist_keys(found.artist))
    if same_title and same_artist:
        return True
    if same_title or (same_artist and (want in got or got in want)):
        return False
    return None


class ITunes:
    def __init__(self, fetch: Callable[[str], bytes] | None = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self._fetch = fetch or (lambda url: websearch._default_fetch(
            url, {"User-Agent": musicbrainz.USER_AGENT, "Accept": "application/json"}, MAX_REPLY))
        self._clock, self._sleep = clock, sleep
        self._lock = threading.Lock()
        self._last: float | None = None

    def _wait(self) -> None:
        with self._lock:
            if self._last is not None:
                gap = ITUNES_SPACING - (self._clock() - self._last)
                if gap > 0:
                    self._sleep(gap)
            self._last = self._clock()

    def search(self, artist: str, title: str) -> list[Found]:
        terms = f"{artist} {bulktag.clean_title(title)}".strip()
        self._wait()
        try:
            raw = self._fetch(ITUNES_URL.format(q=urllib.parse.quote(terms, safe="")))
            data = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError, http.client.HTTPException, urllib.error.URLError) as e:
            raise CoverFindError(MSG_NETWORK) from e
        out = []
        for r in (data.get("results") or []) if isinstance(data, dict) else []:
            art = r.get("artworkUrl100") or ""
            if not art:
                continue
            date = r.get("releaseDate") or ""
            out.append(Found(SRC_APPLE, r.get("artistName") or "", r.get("trackName") or "",
                             r.get("collectionName") or "", date[:4] if date[:4].isdigit() else "",
                             _ART_SIZE.sub(ITUNES_ART, art)))
        return out


class CoverFinder:
    def __init__(self, itunes: ITunes | None = None, mb: musicbrainz.Client | None = None,
                 fetch_image: Callable[[str], bytes] | None = None) -> None:
        self._itunes = itunes or ITunes()
        self._mb = mb
        self._fetch_image = fetch_image or websearch.fetch_image

    def _mb_client(self) -> musicbrainz.Client:
        return self._mb or musicbrainz.default_client()

    def _search(self, source: str, artist: str, title: str) -> list[Found]:
        if source == SRC_APPLE:
            return self._itunes.search(artist, title)
        try:
            cands = self._mb_client().search(bulktag.clean_title(title), artist)
        except musicbrainz.MusicBrainzError as e:
            raise CoverFindError(str(e)) from e
        return [Found(SRC_MB, c.artist, c.title, c.album, c.year, c.release_id) for c in cands if c.release_id]

    def _image(self, found: Found) -> bytes | None:
        try:
            if found.source == SRC_APPLE:
                data = self._fetch_image(found.art)
            else:
                data = self._mb_client().cover(found.art)
        except (websearch.ImageFetchError, musicbrainz.MusicBrainzError):
            return None
        return data if data and picture_mime(data) else None

    def _best(self, source: str, artist: str, title: str) -> Hit | None:
        """딱 맞는 곡을 먼저, 없으면 비슷한 곡. 그림을 못 받으면 다음 후보."""
        found = [f for f in self._search(source, artist, title) if not _KARAOKE.search(f"{f.title} {f.album}")]
        graded = [(j, f) for f in found if (j := judge(artist, title, f)) is not None]
        graded.sort(key=lambda jf: not jf[0])
        if not graded and source == SRC_APPLE and len(found) >= 2 and found[0].artist == found[1].artist:
            # 가요는 영어 이름으로 오기도 한다(멜로망스 선물 → MeloMance Gift). 위 결과가 한 가수면 첫 곡을 '확인'으로
            graded = [(False, found[0])]
        for sure, f in graded[:MAX_COVER_TRIES]:
            image = self._image(f)
            if image is not None:
                return Hit(f.source, f.artist, f.title, f.album, f.year, image, sure)
        return None

    def find(self, artist: str, title: str) -> Hit | None:
        """None = 못 찾음. 두 곳 모두 인터넷에 막히면 CoverFindError."""
        if not title.strip():
            return None
        order = [SRC_APPLE, SRC_MB] if bulktag._is_korean(artist + title) else [SRC_MB, SRC_APPLE]
        maybe: Hit | None = None
        errors = 0
        for source in order:
            try:
                hit = self._best(source, artist, title)
            except CoverFindError:
                errors += 1
                continue
            if hit is not None and hit.sure:
                return hit
            maybe = maybe or hit
        if maybe is None and errors == len(order):
            raise CoverFindError(MSG_NETWORK)
        return maybe


_default: CoverFinder | None = None
_default_lock = threading.Lock()


def default_finder() -> CoverFinder:
    global _default
    with _default_lock:
        if _default is None:
            _default = CoverFinder()
        return _default
