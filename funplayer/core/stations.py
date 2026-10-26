from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, replace
from urllib.parse import urlsplit, urlunsplit

log = logging.getLogger(__name__)

USER_SOURCE = "직접 넣음"
FAVORITES_TITLE = "★ 즐겨찾기"
DOMESTIC_TITLE = "국내 방송"
USER_TITLE = "직접 넣은 방송"


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    kind: str      # "kbs" | "mbc" | "url"
    key: str       # kbs 채널 코드, mbc 채널, 또는 url
    source: str    # "KBS" | "MBC" | 나라 이름 | "직접 넣음"
    group: str     # 원래 묶음 키
    builtin: bool


def _domestic() -> list[Station]:
    rows = [
        ("kbs-21", "KBS 1라디오", "kbs", "21", "KBS"),
        ("kbs-22", "KBS 해피FM", "kbs", "22", "KBS"),
        ("kbs-24", "KBS 클래식FM", "kbs", "24", "KBS"),
        ("kbs-25", "KBS 쿨FM", "kbs", "25", "KBS"),
        ("mbc-sfm", "MBC 표준FM", "mbc", "sfm", "MBC"),
        ("mbc-mfm", "MBC FM4U", "mbc", "mfm", "MBC"),
    ]
    return [Station(i, n, k, key, src, "domestic", True) for i, n, k, key, src in rows]


# (장르, id, 이름, 나라, 주소) -- 2026-10-26에 소리를 확인한 목록
_OVERSEAS = [
    ("Lo-fi", "net-lofi-24-7", "Lofi 24/7", "미국", "http://usa9.fastcast4u.com/proxy/jamz?mp=/1"),
    ("Lo-fi", "net-moe-lofi", "MoE Lofi", "영국", "http://stream.zeno.fm/3u1qndyk8rhvv"),
    ("재즈", "net-adroit-jazz-underground", "Adroit Jazz Underground", "미국", "https://icecast.walmradio.com:8443/jazz"),
    ("재즈", "net-classic-vinyl-hd", "Classic Vinyl HD", "미국", "https://icecast.walmradio.com:8443/classic"),
    ("클래식", "net-classic-fm-uk", "Classic FM UK", "영국", "http://ice-the.musicradio.com/ClassicFMMP3"),
    ("클래식", "net-your-classical-relax", "Your Classical - Relax", "미국", "http://relax.stream.publicradio.org/relax.mp3"),
    ("팝", "net-hit-fm", "Hit FM", "우크라이나", "http://195.95.206.17/HitFM"),
    ("팝", "net-europa-plus", "Europa Plus", "러시아", "http://ep256.hostingradio.ru:8052/europaplus256.mp3"),
    ("록", "net-rock-fm", "ROCK FM", "러시아", "http://nashe1.hostingradio.ru/rock-128.mp3"),
    ("록", "net-rockabilly-radio", "Rockabilly Radio", "미국", "http://lin3.ash.fast-serv.com:6026/stream_96"),
    ("일렉트로닉", "net-dance-wave", "Dance Wave!", "헝가리", "https://dancewave.online/dance.mp3"),
    ("일렉트로닉", "net-frisky", "Frisky", "미국", "http://stream2.friskyradio.com/frisky_mp3_hi"),
    ("앰비언트", "net-ambient-sleeping-pill", "Ambient Sleeping Pill", "미국", "http://radio.stereoscenic.com/asp-h"),
    ("앰비언트", "net-somafm-groove-salad", "SomaFM Groove Salad", "미국", "https://ice6.somafm.com/groovesalad-128-mp3"),
    ("라운지·칠아웃", "net-antenne-bayern-chillout", "Antenne Bayern Chillout", "독일", "http://mp3channels.webradio.antenne.de/chillout"),
    ("라운지·칠아웃", "net-somafm-secret-agent", "SomaFM Secret Agent", "미국", "https://ice6.somafm.com/secretagent-128-mp3"),
    ("피아노", "net-jazz-radio-piano-jazz", "Jazz Radio Piano Jazz", "프랑스", "http://jzr-piano.ice.infomaniak.ch/jzr-piano.mp3"),
    ("피아노", "net-radio-caprice-classical-piano", "Radio Caprice Classical Piano", "러시아", "http://79.120.39.202:9069/;"),
    ("영화음악", "net-1fm-movie-soundtrack", "1.FM Movie Soundtrack", "스위스", "http://strm112.1.fm/moviesoundtracks_mobile_mp3"),
    ("영화음악", "net-ffh-soundtrack", "Hit Radio FFH Soundtrack", "독일", "http://mp3.ffh.de/ffhchannels/hqsoundtrack.mp3"),
    ("라틴", "net-chocolate-fm", "Chocolate FM", "스페인", "http://streaming5.elitecomunicacion.es:8082/live.mp3"),
    ("라틴", "net-latina-salsa", "Latina Salsa", "프랑스", "http://latinasalsa.ice.infomaniak.ch/latinasalsa.mp3"),
    ("레게", "net-la-grosse-radio-reggae", "La Grosse Radio Reggae", "프랑스", "http://hd.lagrosseradio.info/lagrosseradio-reggae-192.mp3"),
    ("레게", "net-latina-reggaeton", "Latina Reggaeton", "프랑스", "http://latinareggaeton.ice.infomaniak.ch/latinareggaeton.mp3"),
    ("블루스", "net-jazz-radio-blues", "Jazz Radio Blues", "프랑스", "http://jazzblues.ice.infomaniak.ch/jazzblues-high.mp3"),
    ("블루스", "net-blues-radio", "Blues Radio", "그리스", "http://cast3.radiohost.ovh:8352/"),
    ("컨트리", "net-977-country", ".977 Country", "미국", "http://26343.live.streamtheworld.com:3690/977_COUNTRY_SC"),
    ("컨트리", "net-181fm-highway-181", "181.FM Highway 181", "미국", "https://listen.181fm.com/181-highway_128k.mp3"),
    ("힙합", "net-color-music-radio", "Color Music Radio", "체코", "http://icecast6.play.cz/color192.mp3"),
    ("힙합", "net-radio-caprice-instrumental-hip-hop", "Radio Caprice Instrumental Hip-hop", "러시아", "http://79.120.77.11:8000/instrumentalhiphop"),
    ("K-pop", "net-0n-k-pop", "0N K-Pop on Radio", "독일", "https://0n-kpop.radionetz.de/0n-kpop.mp3"),
    ("K-pop", "net-exclusively-bts", "Exclusively BTS", "아랍에미리트", "https://streaming.exclusive.radio/er/bts/icecast.audio"),
    ("80년대", "net-977-80s", ".977 80s", "미국", "http://17573.live.streamtheworld.com:3690/977_80_SC"),
    ("80년대", "net-classic-hits-70-80", "Classic Hits 70·80", "미국", "https://radiopanther.radiolebowski.com/play"),
    ("보사노바", "net-radio-bossa-nova-brazil", "Rádio Bossa Nova Brazil", "브라질", "http://54.38.43.201:8009/stream-128kmp3-BossaNovaBrazil"),
    ("보사노바", "net-radio-art-bossa-nova", "Radio Art Bossa Nova", "그리스", "http://air-tunein.radioart.com/fBosa_nova.mp3"),
]

BUILTIN_STATIONS: tuple[Station, ...] = tuple(
    _domestic()
    + [Station(i, n, "url", url, country, f"genre:{g}", True) for g, i, n, country, url in _OVERSEAS]
)

GENRES: tuple[str, ...] = tuple(dict.fromkeys(row[0] for row in _OVERSEAS))


def _normalize(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, parts.fragment)).rstrip("/")


def same_url(a: str, b: str) -> bool:
    """공백, 스킴·호스트 대소문자, 끝의 `/`를 무시하고 같은 주소인지 본다."""
    return _normalize(a) == _normalize(b)


def _host_name(url: str) -> str:
    try:
        host = urlsplit(url.strip()).hostname
    except ValueError:
        host = None
    return host or url.strip()


class StationList:
    def __init__(self, builtins: tuple[Station, ...] | list[Station] = BUILTIN_STATIONS) -> None:
        self._builtins: list[Station] = list(builtins)
        self._builtin_ids = {s.id for s in self._builtins}
        self._user: list[Station] = []
        self._favorites: list[str] = []
        self._renamed: dict[str, str] = {}
        self._hidden: list[str] = []
        self._order: dict[str, list[str]] = {}

    # --- 조회 ---

    def _all(self) -> list[Station]:
        return self._builtins + self._user

    def _display(self, s: Station) -> Station:
        name = self._renamed.get(s.id)
        return replace(s, name=name) if name else s

    def get(self, id: str) -> Station | None:
        if id in self._hidden:
            return None
        for s in self._all():
            if s.id == id:
                return self._display(s)
        return None

    def is_favorite(self, id: str) -> bool:
        return id in self._favorites

    def _group_key(self, s: Station) -> str:
        return "favorites" if s.id in self._favorites else s.group

    def _members(self, key: str) -> list[Station]:
        """key 묶음의 방송을 보이는 순서로 돌려준다 (이름 바꾸기 반영)."""
        if key == "favorites":
            by_id = {s.id: s for s in self._all() if s.id not in self._hidden}
            base = [by_id[i] for i in self._favorites if i in by_id]
        else:
            base = [s for s in self._all()
                    if s.group == key and s.id not in self._hidden and s.id not in self._favorites]
        rank = {i: n for n, i in enumerate(self._order.get(key, []))}
        # sorted는 안정 정렬이라 order에 없는 방송은 원래 순서대로 뒤에 붙는다.
        base.sort(key=lambda s: rank.get(s.id, len(rank)))
        return [self._display(s) for s in base]

    def groups(self) -> list[tuple[str, str, list[Station]]]:
        result: list[tuple[str, str, list[Station]]] = []
        for key, title in (("favorites", FAVORITES_TITLE), ("domestic", DOMESTIC_TITLE)):
            members = self._members(key)
            if members:
                result.append((key, title, members))
        for genre in GENRES:
            key = f"genre:{genre}"
            members = self._members(key)
            if members:
                result.append((key, f"해외 추천 · {genre} ({len(members)})", members))
        members = self._members("user")
        if members:
            result.append(("user", USER_TITLE, members))
        return result

    def visible(self) -> list[Station]:
        return [s for _, _, members in self.groups() for s in members]

    def neighbor(self, id: str, step: int) -> Station | None:
        vis = self.visible()
        if not vis:
            return None
        for n, s in enumerate(vis):
            if s.id == id:
                return vis[(n + step) % len(vis)]
        return None

    # --- 변경 ---

    def set_favorite(self, id: str, on: bool) -> None:
        if on:
            if id not in self._favorites and any(s.id == id for s in self._all()):
                self._favorites.append(id)
        elif id in self._favorites:
            self._favorites.remove(id)
            self._drop_order("favorites", id)

    def rename(self, id: str, name: str) -> None:
        name = name.strip()
        for n, s in enumerate(self._user):
            if s.id == id:
                self._user[n] = replace(s, name=name or _host_name(s.key))
                return
        if id not in self._builtin_ids:
            return
        original = next(s.name for s in self._builtins if s.id == id)
        if name and name != original:
            self._renamed[id] = name
        else:
            self._renamed.pop(id, None)

    def add_url(self, name: str, url: str) -> tuple[Station, bool]:
        url = url.strip()
        for s in self._all():
            if s.kind == "url" and same_url(s.key, url):
                if s.id in self._hidden:
                    self._hidden.remove(s.id)
                return self._display(s), False
        stamp = int(time.time() * 1000)
        while any(s.id == f"url-{stamp}" for s in self._user):
            stamp += 1
        station = Station(f"url-{stamp}", name.strip() or _host_name(url), "url", url, USER_SOURCE, "user", False)
        self._user.append(station)
        return station, True

    def remove(self, id: str) -> None:
        self.set_favorite(id, False)
        if id in self._builtin_ids:
            if id not in self._hidden:
                self._hidden.append(id)
            return
        self._user = [s for s in self._user if s.id != id]
        self._drop_order("user", id)

    def restore_builtins(self) -> None:
        self._hidden.clear()

    def move(self, id: str, before_id: str | None) -> None:
        src = next((s for s in self._all() if s.id == id and id not in self._hidden), None)
        if src is None:
            return
        key = self._group_key(src)
        ids = [s.id for s in self._members(key)]
        if before_id is not None and before_id not in ids:
            return
        if id == before_id:
            return
        ids.remove(id)
        ids.insert(ids.index(before_id) if before_id is not None else len(ids), id)
        self._order[key] = ids

    def _drop_order(self, key: str, id: str) -> None:
        ids = self._order.get(key)
        if ids and id in ids:
            ids.remove(id)
            if not ids:
                del self._order[key]

    # --- 저장 모양 ---

    def to_json(self) -> dict:
        return {
            "version": 1,
            "user": [{"id": s.id, "name": s.name, "url": s.key} for s in self._user],
            "favorites": list(self._favorites),
            "renamed": dict(self._renamed),
            "hidden": list(self._hidden),
            "order": {k: list(v) for k, v in self._order.items()},
        }

    @classmethod
    def from_json(cls, data: dict, builtins: tuple[Station, ...] | list[Station] = BUILTIN_STATIONS) -> StationList:
        """모르는 칸과 없는 id는 건너뛰고 읽을 수 있는 만큼만 살린다."""
        sl = cls(builtins)
        known = set(sl._builtin_ids)
        for item in _as_list(data.get("user")):
            if not isinstance(item, dict):
                continue
            id_, url = item.get("id"), item.get("url")
            if not (isinstance(id_, str) and id_ and isinstance(url, str) and url.strip()) or id_ in known:
                continue
            name = item.get("name")
            name = name.strip() if isinstance(name, str) else ""
            sl._user.append(Station(id_, name or _host_name(url), "url", url.strip(), USER_SOURCE, "user", False))
            known.add(id_)
        sl._favorites = _unique_known(_as_list(data.get("favorites")), known)
        sl._hidden = _unique_known(_as_list(data.get("hidden")), sl._builtin_ids)
        renamed = data.get("renamed")
        if isinstance(renamed, dict):
            sl._renamed = {k: v.strip() for k, v in renamed.items()
                           if k in sl._builtin_ids and isinstance(v, str) and v.strip()}
        order = data.get("order")
        if isinstance(order, dict):
            for key, ids in order.items():
                kept = _unique_known(_as_list(ids), known)
                if isinstance(key, str) and kept:
                    sl._order[key] = kept
        return sl


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _unique_known(values: list, known: set[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        if isinstance(v, str) and v in known and v not in out:
            out.append(v)
    return out


def load_stations(path: str) -> StationList:
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return StationList()
    except OSError as e:
        log.warning("방송국 파일을 읽지 못했습니다: %s", e)
        return StationList()
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except ValueError as e:  # JSONDecodeError와 UnicodeDecodeError 모두 ValueError다
        log.warning("방송국 파일이 깨져 .bak으로 옮깁니다: %s", e)
        try:
            os.replace(path, path + ".bak")
        except OSError as e2:
            log.warning("방송국 파일을 옮기지 못했습니다: %s", e2)
        return StationList()
    return StationList.from_json(data)


def save_stations(path: str, stations: StationList) -> None:
    tmp = path + ".tmp"
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(stations.to_json(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError as e:
        log.warning("방송국 파일을 저장하지 못했습니다: %s", e)
