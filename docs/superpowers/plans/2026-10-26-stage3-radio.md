# 3단계 인터넷 라디오 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 국내 방송(KBS 4, MBC 2), 해외 장르별 추천(장르마다 2개 이하), 직접 넣은 주소를 [라디오] 탭에서 한 번 클릭으로 듣고, 끊기면 다시 연결한다.

**Architecture:**
- 지금 재생 엔진(`AudioPlayer`)에 라이브 모드를 더한다. 네트워크 읽기는 엔진 잠금 밖에서 한다.
- 방송 주소 받기(`engine/resolve.py`)와 방송국 목록(`core/stations.py`)은 Qt가 없는 작은 부품이다.
- 연결·다시 연결 상태는 Qt 없는 `RadioController`(`funplayer/radio.py`)가 맡는다.
- `PlayerController`는 곡과 라디오 중 지금 나오는 쪽으로 재생·이전·다음을 보낸다.
- 화면은 목록 위 탭, 방송국 묶음 목록, [주소 넣기…] 창이다.

**Tech Stack:** Python 3.14 venv(3.13 호환), PyQt5 5.15.11, PyAV 19.0.2, 표준 라이브러리 `urllib`, pytest(offscreen).

**Spec:** `docs/stage3_design.md` (사용자 승인 2026-10-26, `3cf6d59`)

## Global Constraints

### 기술 규칙

- PyQt5만 쓴다. PySide6를 import하지 않는다.
- 모든 funplayer 모듈은 `from __future__ import annotations`로 시작한다. Python 3.13에서 돌아야 한다.
- `core/`, `engine/`, `controller.py`, `radio.py`는 Qt를 import하지 않는다. `tests/test_layering.py`에 `radio.py`를 더한다.
- 새 라이브러리를 넣지 않는다. 네트워크는 `urllib.request`와 PyAV(FFmpeg)만 쓴다.
- 자동 테스트는 인터넷에 접속하지 않는다.
  - 네트워크는 넘겨받은 `fetch`/`open_stream`으로만 한다.
  - 엔진 테스트는 테스트 안에서 띄운 `127.0.0.1` HTTP 서버만 쓴다.

### 네트워크 규칙

- 켤 때와 탭을 바꿀 때는 접속하지 않는다.
- 방송국 줄 클릭, `Enter`, 라디오를 멈춘 뒤 [재생], 라디오 중 이전·다음 때만 접속한다.
- radio-browser에 접속하지 않는다. 클릭 수 세기도 하지 않는다.
- SBS는 넣지 않는다. 접근 제한을 우회하는 코드도 넣지 않는다.
- User-Agent는 `my-fun/0.3 (+local player)`다.
  - KBS·MBC 주소 받기에만 `Mozilla/5.0 (Windows NT 10.0; Win64; x64)`를 쓴다.
  - MBC는 `Referer: https://mini.imbc.com/`도 보낸다.
- 시간 제한: 주소 받기 10초, 연결과 읽기 15초.
- 라디오는 8초를 모아 두고, 파일은 지금처럼 2초다.
- 다시 연결은 2, 4, 8초 뒤에 3번까지 한다. 국내 방송은 매번 주소를 새로 받는다.

### 문구

빈칸 없이 그대로 쓴다.

- 상태 줄 안내(회색):
  - `CONNECTING_MSG = "연결 중…"`
  - `CONNECTED_MSG = "{name}에 연결했습니다"`
  - `RETRY_MSG = "다시 연결하는 중… ({n}/3)"`
  - `UNAVAILABLE_MSG = "지금은 이 방송을 들을 수 없습니다. 다른 방송을 골라 보세요"` (빨간 오류로 쓰지 않는다)
  - `RESUME_RADIO_MSG = "이어 듣기: {name}"`
  - `DUP_STATION_MSG = "이미 목록에 있습니다"`
- [주소 넣기…] 창 안의 빨간 글씨: `BAD_URL_MSG = "주소가 올바르지 않습니다"`
- 탭: `재생목록`, `라디오`
- 라이브 줄:
  - 왼쪽은 `● LIVE`. 나올 때는 `#C5221F`, 멈추면 `INFO_COLOR`로 칠한다.
  - 오른쪽은 `들은 시간 {m:ss}`(`format_time`)다.
- 묶음 제목:
  - `★ 즐겨찾기`
  - `국내 방송`
  - `해외 추천 · {장르} ({n})`
  - `직접 넣은 방송`
- 아래 줄(라디오 탭): `주소 넣기…`, `보기`, `방송 {n}개`
- 오른쪽 클릭: `듣기`, `즐겨찾기`(체크), `이름 바꾸기…`, `지우기`, 구분선, `기본 방송 다시 보이기`
- [주소 넣기…] 창:
  - 제목 `주소 넣기`, 칸 `이름`·`주소`, 단추 `넣기`·`취소`
  - 안내: `http·https 방송 주소, .m3u·.pls·.m3u8 주소를 넣을 수 있습니다.`
- 국내 방송의 [곡 정보] 경로 칸: `방송사 웹 재생 주소 (들을 때마다 새로 받음)`

### 설정과 파일

- 새 설정 키와 기본값:
  - `player_last_source`: `"file"`이고, `"file"`과 `"radio"`만 받는다.
  - `player_last_station`: `""`
  - `player_tab`: `"playlist"`이고, `"playlist"`와 `"radio"`만 받는다.
  - `player_radio_open`: `["favorites", "domestic", "user"]` (펼친 묶음 키 목록)
- 방송국 파일은 `%APPDATA%\my-fun\stations.json`(UTF-8)이다. 깨졌으면 `stations.json.bak`으로 옮긴다.

## Review Focus

1. 방송이 멈춰 네트워크 읽기가 15초 동안 막혀도 화면(200ms 새로고침)은 멈추지 않아야 한다. Task 4의 `test_stalled_read_does_not_block_state`가 확인한다.
2. A 방송이 연결되는 중에 B를 누르면 A의 늦은 결과는 버려야 한다. 소리가 둘 섞이거나 A로 돌아가면 안 된다. Task 5의 `test_late_result_of_previous_station_is_ignored`가 확인한다.
3. 주소가 HTML 페이지, 404, 소리 없는 파일이면 회색 안내만 나오고 앱은 그대로여야 한다. Task 3의 `test_resolve_rejects_non_audio_playlist`와 Task 5의 `test_open_failure_shows_unavailable`이 확인한다.
4. `stations.json`이 깨졌거나 모르는 칸·없는 기본 방송 id를 담고 있어도, 기본 방송으로 켜져야 하고 사용자 방송은 살릴 수 있는 만큼 살려야 한다. Task 2의 `test_load_tolerates_unknown_and_stale_ids`, `test_corrupt_file_moved_to_bak`이 확인한다.
5. 연결 중이거나 다시 연결을 기다리는 중에 앱을 끄면, 끈 뒤에 콜백이 돌거나 소리가 나면 안 된다. Task 5의 `test_shutdown_cancels_pending_work`가 확인한다.

## 계획에서 정한 것 (spec이 열어 둔 것)

1. **방송국 id:**
   - 국내: `kbs-21`, `kbs-22`, `kbs-24`, `kbs-25`, `mbc-sfm`, `mbc-mfm`
   - 해외 추천: `net-` + 이름을 소문자로 바꾸고 영숫자 아닌 글자를 `-`로 바꾼 것. 표의 id 열을 그대로 쓴다.
   - 사용자: `url-` + 처음 넣은 시각의 정수 밀리초.
2. **묶음 키:** `favorites`, `domestic`, `genre:{장르}`, `user`. ★ 방송은 원래 묶음에서 빠져 `favorites`에만 보인다.
3. **같은 주소인지:** 앞뒤 공백을 지우고, 스킴과 호스트를 소문자로 바꾸고, 끝의 `/`를 지운 뒤 비교한다.
4. **엔진 라이브 모드:**
   - 디코더는 작업 스레드에서 연다(`open_stream`).
   - 엔진은 열린 디코더를 받는다: `play_stream(decoder)`, 다시 연결 때는 `continue_stream(decoder)`.
   - 라이브에서 버퍼가 비면 끝내지 않고 조용함을 낸다.
5. **"지금:" 곡 이름:** Task 4에서 ICY를 시험한다. PyAV에서 곡 이름을 받을 수 없으면 `Decoder.title`은 늘 `""`이다. 완료 기준이 아니다.
6. **라디오 중 [정지]:** 연결을 끊고 들은 시간을 0으로 한다. 방송국 선택은 남는다.
7. **곡 → 라디오 → 곡:**
   - 라디오로 갈 때 곡의 위치를 `_return_position`에 둔다.
   - 곡 쪽에서 [재생]하면 그 곡을 다시 열고 그 위치로 간 뒤 재생한다.
8. **라디오로 끈 뒤 켤 때:**
   - 재생목록은 불러오되 곡을 열지 않는다. 위치는 `_return_position`에 둔다.
   - 라디오는 방송국만 고른 채(cue) 접속하지 않는다.

## 해외 추천 목록 (2026-10-26에 이 PC에서 소리 확인)

| 장르 | id | 이름 | 나라 | 주소 |
|---|---|---|---|---|
| Lo-fi | net-lofi-24-7 | Lofi 24/7 | 미국 | `http://usa9.fastcast4u.com/proxy/jamz?mp=/1` |
| Lo-fi | net-moe-lofi | MoE Lofi | 영국 | `http://stream.zeno.fm/3u1qndyk8rhvv` |
| 재즈 | net-adroit-jazz-underground | Adroit Jazz Underground | 미국 | `https://icecast.walmradio.com:8443/jazz` |
| 재즈 | net-classic-vinyl-hd | Classic Vinyl HD | 미국 | `https://icecast.walmradio.com:8443/classic` |
| 클래식 | net-classic-fm-uk | Classic FM UK | 영국 | `http://ice-the.musicradio.com/ClassicFMMP3` |
| 클래식 | net-your-classical-relax | Your Classical - Relax | 미국 | `http://relax.stream.publicradio.org/relax.mp3` |
| 팝 | net-hit-fm | Hit FM | 우크라이나 | `http://195.95.206.17/HitFM` |
| 팝 | net-europa-plus | Europa Plus | 러시아 | `http://ep256.hostingradio.ru:8052/europaplus256.mp3` |
| 록 | net-rock-fm | ROCK FM | 러시아 | `http://nashe1.hostingradio.ru/rock-128.mp3` |
| 록 | net-rockabilly-radio | Rockabilly Radio | 미국 | `http://lin3.ash.fast-serv.com:6026/stream_96` |
| 일렉트로닉 | net-dance-wave | Dance Wave! | 헝가리 | `https://dancewave.online/dance.mp3` |
| 일렉트로닉 | net-frisky | Frisky | 미국 | `http://stream2.friskyradio.com/frisky_mp3_hi` |
| 앰비언트 | net-ambient-sleeping-pill | Ambient Sleeping Pill | 미국 | `http://radio.stereoscenic.com/asp-h` |
| 앰비언트 | net-somafm-groove-salad | SomaFM Groove Salad | 미국 | `https://ice6.somafm.com/groovesalad-128-mp3` |
| 라운지·칠아웃 | net-antenne-bayern-chillout | Antenne Bayern Chillout | 독일 | `http://mp3channels.webradio.antenne.de/chillout` |
| 라운지·칠아웃 | net-somafm-secret-agent | SomaFM Secret Agent | 미국 | `https://ice6.somafm.com/secretagent-128-mp3` |
| 피아노 | net-jazz-radio-piano-jazz | Jazz Radio Piano Jazz | 프랑스 | `http://jzr-piano.ice.infomaniak.ch/jzr-piano.mp3` |
| 피아노 | net-radio-caprice-classical-piano | Radio Caprice Classical Piano | 러시아 | `http://79.120.39.202:9069/;` |
| 영화음악 | net-1fm-movie-soundtrack | 1.FM Movie Soundtrack | 스위스 | `http://strm112.1.fm/moviesoundtracks_mobile_mp3` |
| 영화음악 | net-ffh-soundtrack | Hit Radio FFH Soundtrack | 독일 | `http://mp3.ffh.de/ffhchannels/hqsoundtrack.mp3` |
| 라틴 | net-chocolate-fm | Chocolate FM | 스페인 | `http://streaming5.elitecomunicacion.es:8082/live.mp3` |
| 라틴 | net-latina-salsa | Latina Salsa | 프랑스 | `http://latinasalsa.ice.infomaniak.ch/latinasalsa.mp3` |
| 레게 | net-la-grosse-radio-reggae | La Grosse Radio Reggae | 프랑스 | `http://hd.lagrosseradio.info/lagrosseradio-reggae-192.mp3` |
| 레게 | net-latina-reggaeton | Latina Reggaeton | 프랑스 | `http://latinareggaeton.ice.infomaniak.ch/latinareggaeton.mp3` |
| 블루스 | net-jazz-radio-blues | Jazz Radio Blues | 프랑스 | `http://jazzblues.ice.infomaniak.ch/jazzblues-high.mp3` |
| 블루스 | net-blues-radio | Blues Radio | 그리스 | `http://cast3.radiohost.ovh:8352/` |
| 컨트리 | net-977-country | .977 Country | 미국 | `http://26343.live.streamtheworld.com:3690/977_COUNTRY_SC` |
| 컨트리 | net-181fm-highway-181 | 181.FM Highway 181 | 미국 | `https://listen.181fm.com/181-highway_128k.mp3` |
| 힙합 | net-color-music-radio | Color Music Radio | 체코 | `http://icecast6.play.cz/color192.mp3` |
| 힙합 | net-radio-caprice-instrumental-hip-hop | Radio Caprice Instrumental Hip-hop | 러시아 | `http://79.120.77.11:8000/instrumentalhiphop` |
| K-pop | net-0n-k-pop | 0N K-Pop on Radio | 독일 | `https://0n-kpop.radionetz.de/0n-kpop.mp3` |
| K-pop | net-exclusively-bts | Exclusively BTS | 아랍에미리트 | `https://streaming.exclusive.radio/er/bts/icecast.audio` |
| 80년대 | net-977-80s | .977 80s | 미국 | `http://17573.live.streamtheworld.com:3690/977_80_SC` |
| 80년대 | net-classic-hits-70-80 | Classic Hits 70·80 | 미국 | `https://radiopanther.radiolebowski.com/play` |
| 보사노바 | net-radio-bossa-nova-brazil | Rádio Bossa Nova Brazil | 브라질 | `http://54.38.43.201:8009/stream-128kmp3-BossaNovaBrazil` |
| 보사노바 | net-radio-art-bossa-nova | Radio Art Bossa Nova | 그리스 | `http://air-tunein.radioart.com/fBosa_nova.mp3` |

---

### Task 1: 설정 키

**Files:**
- Modify: `funplayer/core/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `Settings.last_source: str`, `last_station: str`, `tab: str`, `radio_open: list[str]` (모두 getter·setter)

- [ ] **Step 1: 실패하는 테스트**

```python
def test_radio_keys_defaults_and_sanitising():
    s = Settings({}, lambda: None)
    assert (s.last_source, s.last_station, s.tab) == ("file", "", "playlist")
    assert s.radio_open == ["favorites", "domestic", "user"]
    bad = Settings({"player_last_source": "tv", "player_last_station": 5, "player_tab": 1,
                    "player_radio_open": "x"}, lambda: None)
    assert (bad.last_source, bad.last_station, bad.tab) == ("file", "", "playlist")
    assert bad.radio_open == ["favorites", "domestic", "user"]
    mixed = Settings({"player_radio_open": ["user", 3, "genre:재즈"]}, lambda: None)
    assert mixed.radio_open == ["user", "genre:재즈"]

def test_radio_keys_round_trip():
    store, saves = {}, []
    s = Settings(store, lambda: saves.append(1))
    s.last_source = "radio"; s.last_station = "kbs-25"; s.tab = "radio"; s.radio_open = ["genre:Lo-fi"]
    assert store["player_last_source"] == "radio" and store["player_last_station"] == "kbs-25"
    assert store["player_tab"] == "radio" and store["player_radio_open"] == ["genre:Lo-fi"] and len(saves) == 4
```

`test_defaults`의 DEFAULTS 사전에 새 키 네 개를 더한다.

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_settings.py`
- [ ] **Step 3: 구현**
  - 기존 패턴을 따른다. 잘못된 값은 기본값으로 읽는다.
  - `radio_open`은 문자열만 남긴 리스트다. 리스트가 아니면 기본값이다.
- [ ] **Step 4: 전체 스위트 통과**
- [ ] **Step 5: 커밋** — `git commit -m "Add radio settings keys"`

---

### Task 2: 방송국 목록 (`core/stations.py`)

**Files:**
- Create: `funplayer/core/stations.py`, `tools/check_stations.py`
- Test: `tests/test_stations.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Station`: `id: str`, `name: str`, `kind: str`(`"kbs"|"mbc"|"url"`), `key: str`, `source: str`, `group: str`, `builtin: bool`
    - `key`는 kbs 채널 코드, mbc 채널, 또는 url이다.
    - `source`는 `"KBS"`, `"MBC"`, 나라 이름, 또는 `"직접 넣음"`이다.
    - `group`은 원래 묶음 키다.
  - `BUILTIN_STATIONS: tuple[Station, ...]`: 국내 6개 + 위 표 36개, 표 순서대로.
  - `GENRES: tuple[str, ...]`: 표의 장르를 나온 순서대로 담는다.
  - `same_url(a: str, b: str) -> bool` (계획 결정 3)
  - `class StationList`:
    - `__init__(builtins=BUILTIN_STATIONS)`
    - `groups() -> list[tuple[str, str, list[Station]]]`: (키, 제목, 방송들). 비어 있는 묶음은 뺀다.
      - 순서: favorites → domestic → `GENRES` 순서의 genre 묶음 → user.
      - 제목 문구는 Global Constraints대로 쓴다.
    - `visible() -> list[Station]`: `groups()` 순서대로 펼친 것.
    - `get(id) -> Station | None`
    - `is_favorite(id) -> bool`, `set_favorite(id, on: bool)`
    - `rename(id, name)`: 빈 이름이면 원래 이름으로 돌린다. `name`이 바뀐 Station을 돌려주는 방식으로, `get`이 바뀐 이름을 준다.
    - `add_url(name: str, url: str) -> tuple[Station, bool]`: (방송, 새로 넣었나).
      - 같은 주소면 그 방송을 돌려주고 `False`다. 숨긴 기본 방송과 같은 주소면 다시 보이게 한 뒤 그것을 돌려준다.
      - 이름이 비면 호스트 이름을 쓴다.
      - kind는 `"url"`, source는 `"직접 넣음"`, group은 `"user"`다.
    - `remove(id)`: 사용자 방송은 지우고, 기본 방송은 숨긴다. ★도 지운다.
    - `restore_builtins()`: 숨긴 것을 모두 되살린다.
    - `move(id, before_id: str | None)`: 같은 묶음 안에서만 옮긴다. 다른 묶음 id면 아무것도 하지 않는다. `before_id`가 None이면 묶음 끝으로 간다.
    - `neighbor(id, step: int) -> Station | None`: `visible()`에서 ±1이다. 끝에서는 반대 끝으로 돈다. 목록이 비면 None이다.
    - `to_json() -> dict`, `@classmethod from_json(data, builtins=...) -> StationList`
  - `load_stations(path: str) -> StationList`, `save_stations(path: str, stations: StationList) -> None`
- JSON 모양: `{"version": 1, "user": [{"id","name","url"}...], "favorites": [ids], "renamed": {id: name}, "hidden": [ids], "order": {group_key: [ids]}}`

- [ ] **Step 1: 실패하는 테스트** (`tests/test_stations.py`)

```python
import json
import pytest
from funplayer.core.stations import BUILTIN_STATIONS, GENRES, StationList, load_stations, same_url, save_stations

def test_builtins_shape():
    ids = [s.id for s in BUILTIN_STATIONS]
    assert ids[:6] == ["kbs-21", "kbs-22", "kbs-24", "kbs-25", "mbc-sfm", "mbc-mfm"]
    assert len(ids) == len(set(ids)) == 42
    for g in GENRES:
        n = sum(1 for s in BUILTIN_STATIONS if s.group == f"genre:{g}")
        assert 1 <= n <= 2
    assert all(s.key.startswith(("http://", "https://")) for s in BUILTIN_STATIONS if s.kind == "url")
    assert not any("sbs" in s.key.lower() for s in BUILTIN_STATIONS)

def test_groups_order_titles_and_favorites():
    sl = StationList()
    sl.set_favorite("kbs-25", True)
    keys = [k for k, _, _ in sl.groups()]
    assert keys[0] == "favorites" and keys[1] == "domestic" and keys[2] == f"genre:{GENRES[0]}"
    titles = {k: t for k, t, _ in sl.groups()}
    assert titles["favorites"] == "★ 즐겨찾기" and titles["domestic"] == "국내 방송"
    assert titles[f"genre:{GENRES[0]}"] == f"해외 추천 · {GENRES[0]} (2)"
    domestic = dict((k, v) for k, _, v in sl.groups())["domestic"]
    assert "kbs-25" not in [s.id for s in domestic]

def test_add_url_dedupes_and_names_from_host():
    sl = StationList()
    st, new = sl.add_url("", " HTTPS://Stream.Example.org/live.mp3/ ")
    assert new and st.name == "stream.example.org" and st.group == "user" and st.source == "직접 넣음"
    again, new2 = sl.add_url("다른 이름", "https://stream.example.org/live.mp3")
    assert not new2 and again.id == st.id
    titles = [t for _, t, _ in sl.groups()]
    assert titles[-1] == "직접 넣은 방송"

def test_remove_hides_builtin_and_restore():
    sl = StationList(); sl.set_favorite("kbs-21", True); sl.remove("kbs-21")
    assert sl.get("kbs-21") is None and not sl.is_favorite("kbs-21")
    sl.restore_builtins(); assert sl.get("kbs-21") is not None

def test_readding_hidden_builtin_url_shows_it_again():
    sl = StationList(); sl.remove("net-somafm-groove-salad")
    st, new = sl.add_url("x", "https://ice6.somafm.com/groovesalad-128-mp3")
    assert not new and st.id == "net-somafm-groove-salad" and sl.get(st.id) is not None

def test_rename_move_neighbor():
    sl = StationList(); sl.rename("kbs-25", "쿨"); assert sl.get("kbs-25").name == "쿨"
    sl.rename("kbs-25", "  "); assert sl.get("kbs-25").name == "KBS 쿨FM"
    sl.move("mbc-mfm", "kbs-21")
    dom = [s.id for k, _, v in sl.groups() if k == "domestic" for s in v]
    assert dom[0] == "mbc-mfm"
    sl.move("mbc-mfm", "net-moe-lofi"); assert [s.id for k, _, v in sl.groups() if k == "domestic" for s in v][0] == "mbc-mfm"
    vis = sl.visible()
    assert sl.neighbor(vis[-1].id, 1).id == vis[0].id and sl.neighbor(vis[0].id, -1).id == vis[-1].id

def test_json_round_trip(tmp_path):
    sl = StationList(); st, _ = sl.add_url("우리 동네", "https://a.example/x.mp3")
    sl.set_favorite(st.id, True); sl.rename("kbs-21", "1R"); sl.remove("mbc-sfm"); sl.move("kbs-25", "kbs-21")
    p = tmp_path / "stations.json"; save_stations(str(p), sl)
    back = load_stations(str(p))
    assert back.to_json() == sl.to_json() and back.get(st.id).name == "우리 동네"

def test_load_tolerates_unknown_and_stale_ids(tmp_path):
    p = tmp_path / "stations.json"
    p.write_text(json.dumps({"version": 9, "zzz": 1, "favorites": ["gone", "kbs-25"], "hidden": ["nope"],
                             "renamed": {"gone": "x"}, "order": {"domestic": ["gone", "mbc-mfm"]},
                             "user": [{"id": "url-1", "name": "ok", "url": "https://ok.example/s"},
                                      {"id": "url-2", "name": "bad"}]}), encoding="utf-8")
    sl = load_stations(str(p))
    assert sl.is_favorite("kbs-25") and sl.get("url-1").name == "ok" and sl.get("url-2") is None
    assert [s.id for k, _, v in sl.groups() if k == "domestic" for s in v][0] == "mbc-mfm"

@pytest.mark.parametrize("content", [b"{not json", b"[1, 2]", b"\xff\xfe"])
def test_corrupt_file_moved_to_bak(tmp_path, content):
    p = tmp_path / "stations.json"; p.write_bytes(content)
    sl = load_stations(str(p))
    assert len(sl.visible()) == 42 and (tmp_path / "stations.json.bak").read_bytes() == content and not p.exists()

def test_missing_file_gives_builtins(tmp_path):
    assert len(load_stations(str(tmp_path / "none.json")).visible()) == 42

def test_same_url():
    assert same_url("HTTP://A.b/x/", "http://a.b/x") and not same_url("http://a.b/x", "http://a.b/y")
```

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_stations.py`
- [ ] **Step 3: 구현**
  - `BUILTIN_STATIONS`의 국내 6개는 이렇다.
    - KBS 1라디오(`kbs`, `"21"`), KBS 해피FM(`"22"`), KBS 클래식FM(`"24"`), KBS 쿨FM(`"25"`)
    - MBC 표준FM(`mbc`, `"sfm"`), MBC FM4U(`"mfm"`)
    - 모두 group은 `"domestic"`, source는 `"KBS"`/`"MBC"`이다.
  - 해외 36개는 위 표를 그대로 옮긴다. kind는 `"url"`, source는 나라, group은 `"genre:{장르}"`이다.
  - 저장은 임시 파일에 쓴 뒤 `os.replace`한다. 실패는 warning 로그만 남긴다.
  - 읽기 오류의 종류에 따라 이렇게 한다.
    - JSON이 아니거나, dict가 아니거나, UTF-8로 읽히지 않으면 `.bak`으로 옮기고 기본 상태로 둔다. `.bak`이 이미 있으면 덮어쓴다.
    - 파일을 읽는 중 OSError가 나면 기본 상태로 둔다.
- [ ] **Step 4: `tools/check_stations.py` 작성**
  - 인터넷을 쓰는 수동 확인 도구이고, 자동 테스트가 아니다.
  - `BUILTIN_STATIONS` 각각을 `engine.resolve.resolve`와 `engine.decoder.open_stream`(Task 3·4)으로 열어 3초 풀어 보고, `OK`/`FAIL 이유`를 한 줄씩 UTF-8 파일(첫 인자)에 쓴다.
  - Task 4 전에는 import가 실패하므로, 파일만 만들고 실행은 Task 12에서 한다.
- [ ] **Step 5: 전체 스위트 통과 후 커밋** — `git commit -m "Add the station list with built-in Korean and genre picks"`

---

### Task 3: 주소 받기 (`engine/resolve.py`)

**Files:**
- Create: `funplayer/engine/resolve.py`
- Test: `tests/test_resolve.py`

**Interfaces:**
- Consumes: Task 2 `Station`
- Produces:
  - `class ResolveError(Exception)`
  - `Fetch = Callable[[str, dict[str, str]], bytes]`
  - `default_fetch(url, headers) -> bytes`: urllib, 시간 제한 10초, 1 MB까지만 읽는다.
  - `resolve(station: Station, fetch: Fetch = default_fetch) -> str`: 재생할 주소를 돌려준다.
  - 상수 `APP_UA = "my-fun/0.3 (+local player)"`, `BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"`

- [ ] **Step 1: 실패하는 테스트**

```python
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
```

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_resolve.py`
- [ ] **Step 3: 구현**
  - KBS JSON에서 `channel_item` 중 `service_url`이 있는 첫 항목을 고른다. `media_type == "radio"`인 항목을 먼저 본다.
  - MBC 응답 글자는 `strip()`하고, http(s)로 시작해야 한다.
  - `.m3u`/`.pls`는 주소 경로의 확장자를 소문자로 봐서 고른다(질의 문자열 제외). 둘 다 UTF-8로 읽고, 못 읽는 글자는 `replace`한다.
  - 그 밖의 OSError, ValueError, `TimeoutError`, JSON 오류는 모두 `ResolveError`로 바꾼다.
- [ ] **Step 4: 통과 확인, 전체 스위트**
- [ ] **Step 5: 커밋** — `git commit -m "Resolve station stream URLs"`

---

### Task 4: 엔진 라이브 모드

**Files:**
- Modify: `funplayer/engine/decoder.py`, `funplayer/engine/player.py`, `funplayer/ui/bridge.py`
- Test: `tests/test_live.py`(새 파일), 기존 `tests/test_player.py`가 그대로 통과해야 한다.

**Interfaces:**
- Produces:
  - 디코더 쪽:
    - `open_stream(url: str, headers: dict[str, str] | None = None) -> Decoder`
      - `av.open(url, timeout=15, options={"user_agent": APP_UA, "icy": "1", ...})`. headers가 있으면 `"headers"` 옵션에 `"K: V\r\n"`을 이어 붙여 넘긴다.
      - 실패는 `DecodeError`다.
    - `Decoder.live: bool` (open_stream이면 True), `Decoder.title -> str` (계획 결정 5)
  - `AudioPlayer` 쪽:
    - `__init__(..., live_buffer_seconds: float = 8.0)`
    - `play_stream(decoder) -> None`: 지금 것을 비우고, 라이브로 시작한다. 상태는 PLAYING이다.
    - `continue_stream(decoder) -> None`: 버퍼와 출력은 두고 디코더만 바꾼다. 끊김 표시를 지운다.
    - `is_live: bool`(속성)
    - `stream_title: str`(속성): 디코더의 title. 라이브가 아니면 `""`.
    - `on_lost: Callable[[], None] | None`: 라이브 읽기가 끝나거나(None) 오류를 낼 때 한 번 부른다. 잠금을 놓은 뒤에 부른다.
  - `PlayerBridge.lost = pyqtSignal()`, `player.on_lost = self.lost.emit`

- [ ] **Step 1: 지금 동작을 지키는 실패 테스트** (`tests/test_live.py`)
  - 내장 HTTP 서버 fixture `slow_mp3_server(tone_mp3)`:
    - `http.server.ThreadingHTTPServer`를 `127.0.0.1:0`에 띄우고 `/live.mp3`를 내보낸다.
    - 파일 바이트를 4 KB씩 `time.sleep(0.01)` 간격으로 흘린다. `/close-after/{n}` 경로는 n바이트 뒤 연결을 끊는다.
    - fixture는 기본 주소를 돌려주고, 끝나면 `shutdown()`한다.

```python
def test_open_stream_live_decoder(slow_mp3_server):
    d = open_stream(slow_mp3_server + "/live.mp3")
    try:
        assert d.live and d.duration == 0.0 and d.read() is not None and d.title == ""
    finally:
        d.close()

def test_open_stream_bad_url_raises(slow_mp3_server):
    with pytest.raises(DecodeError):
        open_stream(slow_mp3_server + "/nothing-here")

def test_play_stream_plays_and_reports_lost(slow_mp3_server):
    p = AudioPlayer(sink_factory=FakeSink, threaded=False, live_buffer_seconds=1.0)
    lost = []; p.on_lost = lambda: lost.append(1)
    p.play_stream(open_stream(slow_mp3_server + "/close-after/20000"))
    assert p.is_live and p.state is State.PLAYING and p.duration == 0.0
    for _ in range(400):
        p.pump()
    assert lost == [1] and p.state is State.PLAYING      # 끊겨도 바로 멈추지 않는다
    p.close()

def test_live_empty_buffer_outputs_silence_not_end():
    # 가짜 디코더: read()가 블록 하나 뒤 None
    ...  # FakeLiveDecoder(live=True, blocks=[ones(441,2)]) → pump 여러 번 → on_end 불리지 않음, 출력 콜백은 0을 채움

def test_continue_stream_keeps_buffer_and_clears_lost():
    ...  # play_stream(A) → 블록 쌓기 → A가 끝나 on_lost → continue_stream(B) → buffered_frames 그대로, 다시 끝나면 on_lost 한 번 더

def test_seek_is_noop_when_live():
    ...  # play_stream 후 seek(10) → position 그대로, 오류 없음

def test_stalled_read_does_not_block_state():
    # 가짜 디코더의 read()가 threading.Event를 기다린다(막힘). threaded=True 플레이어
    # play_stream → 디코드 스레드가 read에서 막힌 동안 메인 스레드의 p.state, p.position, p.buffered_frames가 0.2초 안에 돌아온다
    ...

def test_file_playback_unchanged(tone_mp3):
    p = AudioPlayer(sink_factory=FakeSink, threaded=False)
    p.load(tone_mp3); assert not p.is_live and p.duration > 0
    p.close()
```

  - `...`로 적은 테스트는 주석에 적은 대로 가짜 디코더를 써서 완성한다.
  - 가짜 디코더는 `read()`, `seek()`, `close()`, `duration=0.0`, `live=True`, `title=""`을 가진 작은 클래스다.

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_live.py`
- [ ] **Step 3: ICY 곡 이름 확인 (조사 단계)**
  - 스크래치 스크립트(저장소 밖)로 `open_stream("https://ice6.somafm.com/groovesalad-128-mp3")`를 연다. 이 단계만 인터넷을 쓴다.
  - 30초 동안 블록을 읽으며 `container.metadata`에 `StreamTitle`/`icy-title` 같은 값이 생기는지 본다. `container.streams.audio[0].metadata`도 본다.
  - 값이 생기면 `Decoder.title`이 그 값을 돌려준다. 안 생기면 늘 `""`이다.
  - 결과를 보고서에 적는다.
- [ ] **Step 4: 구현**
  - **`load(path)`:** `self._open_decoder(path)`를 잠금 밖에서 부르고, 그 뒤 잠금을 쥐고 `_reset()`한 다음 바꿔 끼운다. 파일이 느린 드라이브에 있어도 화면이 멈추지 않게 하려는 것이다. 열기가 실패하면 지금 것을 비우는 지금 동작을 그대로 지킨다.
  - **`pump()` (라이브 디코더일 때):**
    - 잠금 안에서 `decoder`와 `need`를 읽고, 잠금 밖에서 `decoder.read()`를 부른다.
    - 다시 잠금을 쥐었을 때 `self._decoder is decoder`인 경우에만 블록을 넣는다.
    - 파일은 지금처럼 잠금 안에서 읽어도 된다. 둘을 같은 방식으로 바꿔도 된다. 기존 테스트는 그대로 통과해야 한다.
  - **라이브 끝·오류:** `_lost = True`로 표시하고, 잠금을 놓은 뒤 `on_lost`를 한 번 부른다.
    - 버퍼가 비어도 rewind·on_end를 하지 않는다. 출력 콜백은 이미 모자라면 0을 채우므로 조용함이 나온다.
  - **라이브의 목표 버퍼**는 `live_buffer_seconds`다.
  - **라이브의 `seek`**는 아무것도 하지 않는다.
  - **라이브의 `pause()`·`stop()`:** stop은 `_reset()`과 같다(디코더 닫기). pause는 컨트롤러가 쓰지 않는다(라디오 멈춤 = stop). 그래도 부르면 stop처럼 한다.
- [ ] **Step 5: 통과 확인, 전체 스위트**
- [ ] **Step 6: 커밋** — `git commit -m "Add a live stream mode to the audio engine"`

---

### Task 5: `RadioController` (`funplayer/radio.py`)

**Files:**
- Create: `funplayer/radio.py`
- Modify: `tests/test_layering.py`(radio.py 더하기), `tests/fakes.py`(`FakeLivePlayer`, `FakeRunner`, `FakeClock`)
- Test: `tests/test_radio.py`

**Interfaces:**
- Consumes: Task 2 `StationList`, `Station`. Task 3 `resolve`, `ResolveError`. Task 4 `open_stream`, `DecodeError`, `play_stream`, `continue_stream`, `is_live`, `stream_title`, `on_lost`.
- Produces:
  - `class RadioState(Enum)`: `IDLE`, `CONNECTING`, `LIVE`, `RETRYING`
  - `class RadioController`:
    - 생성자: `__init__(player, stations: StationList, run_async, call_later, clock, resolve=resolve, open_stream=open_stream, notify=None)`
      - `run_async(work: Callable[[], T], done: Callable[[T | None, Exception | None], None]) -> None`
        - `work`는 작업 스레드에서 돌고, `done`은 UI 스레드에서 돈다.
      - `call_later(seconds: float, fn: Callable[[], None]) -> Callable[[], None]`
        - 돌려준 함수를 부르면 취소된다.
      - `clock() -> float`: 단조 시계(초)
      - `notify(msg: str, error: bool) -> None`: 상태 줄. error는 늘 False로 부른다.
    - 속성:
      - `state: RadioState`
      - `current: Station | None`: 고른 방송. 멈춰도 남는다.
      - `elapsed: float`
      - `now_title: str` (`player.stream_title`)
    - `play(station_id: str) -> None`
    - `cue(station_id: str) -> None`: 고르기만 한다. 접속하지 않는다.
    - `toggle() -> None`: LIVE·CONNECTING·RETRYING이면 stop, IDLE이면 current를 play한다.
    - `stop() -> None`: `player.unload()`, 들은 시간 0, 대기 작업 취소, 상태는 IDLE.
    - `step(direction: int) -> None`: `stations.neighbor`로 옮겨 play한다.
    - `on_lost() -> None`: UI 스레드에서 불린다(브리지 경유).
    - `shutdown() -> None`: 대기 작업을 취소하고, 늦은 결과는 버린다.
  - 상수: `CONNECTING_MSG`, `CONNECTED_MSG`, `RETRY_MSG`, `UNAVAILABLE_MSG`, `RETRY_DELAYS = (2.0, 4.0, 8.0)`
- 규칙:
  - **연결 시도 번호(token):** `play`·`stop`·`shutdown`마다 번호를 올린다. `done`에서 번호가 다르면 열린 디코더를 닫고 무시한다.
  - **작업:** `work = lambda: open_stream(resolve(station))`이다. 국내 방송은 resolve가 매번 주소를 새로 받는다.
  - **연결 성공:** `player.play_stream(decoder)`, 상태 LIVE, `notify(CONNECTED_MSG.format(name=...))`. 이때 들은 시간 시계를 시작한다.
  - **연결 실패:** `player.unload()`, 상태 IDLE, `notify(UNAVAILABLE_MSG)`.
  - **끊김:** LIVE에서 `on_lost`가 오면 상태 RETRYING, `notify(RETRY_MSG.format(n=1))`, `call_later(2.0, 시도)`를 한다.
    - 시도가 성공하면 `player.continue_stream(dec)`, LIVE가 되고 안내를 지운다(`notify("")`).
    - 시도가 실패하면 다음 지연으로 넘어간다. 3번째도 실패하면 `stop()` 뒤 `notify(UNAVAILABLE_MSG)`.
  - **들은 시간:** LIVE와 RETRYING 동안 센다. 다시 연결해도 이어서 세고, `stop`과 다른 방송을 `play`하면 0이 된다.

- [ ] **Step 1: 실패하는 테스트** (가짜들: `FakeLivePlayer`는 `play_stream`/`continue_stream`/`unload` 기록과 `is_live`·`stream_title`을 가진다. `FakeRunner`는 `run_async`를 모아 두었다가 `finish(i, result=..., error=...)`로 끝낸다. `FakeClock`은 `now`와 `call_later` 목록, `advance(sec)`를 가진다.)

```python
def test_play_connects_and_reports(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25")
    assert r.state is RadioState.CONNECTING and notes[-1] == "연결 중…"
    runner.finish(0, result="DEC")
    assert player.streams == ["DEC"] and r.state is RadioState.LIVE and notes[-1] == "KBS 쿨FM에 연결했습니다"

def test_open_failure_shows_unavailable(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, error=DecodeError("x"))
    assert r.state is RadioState.IDLE and notes[-1] == "지금은 이 방송을 들을 수 없습니다. 다른 방송을 골라 보세요"
    assert r.current.id == "kbs-25"

def test_late_result_of_previous_station_is_ignored(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); r.play("mbc-mfm")
    closed = []; dec_a = Closeable(closed)
    runner.finish(0, result=dec_a)
    assert player.streams == [] and closed == [1] and r.current.id == "mbc-mfm"
    runner.finish(1, result="B"); assert player.streams == ["B"]

def test_reconnect_delays_and_success(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); clock.advance(30)
    r.on_lost()
    assert r.state is RadioState.RETRYING and notes[-1] == "다시 연결하는 중… (1/3)"
    assert len(runner.pending) == 0; clock.advance(2.0); assert len(runner.pending) == 1
    runner.finish(1, error=ResolveError("x")); assert notes[-1] == "다시 연결하는 중… (2/3)"
    clock.advance(4.0); runner.finish(2, result="B")
    assert player.continued == ["B"] and r.state is RadioState.LIVE and notes[-1] == "" and r.elapsed >= 36

def test_three_failures_give_up(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); r.on_lost()
    for i, d in enumerate((2.0, 4.0, 8.0), start=1):
        clock.advance(d); runner.finish(i, error=DecodeError("x"))
    assert r.state is RadioState.IDLE and player.unloaded and notes[-1].startswith("지금은 이 방송을")

def test_toggle_stop_resets_elapsed_and_reconnects_fresh(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); clock.advance(10)
    r.toggle(); assert r.state is RadioState.IDLE and r.elapsed == 0 and player.unloaded
    r.toggle(); assert r.state is RadioState.CONNECTING and len(runner.pending) == 1

def test_cue_never_touches_network(radio):
    r, player, runner, clock, notes = radio
    r.cue("mbc-sfm"); assert r.current.id == "mbc-sfm" and runner.pending == [] and r.state is RadioState.IDLE

def test_step_moves_through_visible_list(radio):
    r, *_ = radio
    r.play("kbs-21"); r.step(1); assert r.current.id == "kbs-22"
    r.step(-1); r.step(-1); assert r.current.id == r._stations.visible()[-1].id

def test_shutdown_cancels_pending_work(radio):
    r, player, runner, clock, notes = radio
    r.play("kbs-25"); runner.finish(0, result="A"); r.on_lost(); r.shutdown()
    clock.advance(20)
    assert runner.pending == [] and player.continued == []
    r.play("kbs-21"); r.shutdown(); runner.finish(1, result="Z") if runner.pending else None
    assert player.streams == ["A"]
```

`radio` fixture는 `RadioController(FakeLivePlayer(), StationList(), runner.run_async, clock.call_later, clock.now, resolve=lambda st: st.key, open_stream=lambda url: url, notify=lambda m, e: notes.append(m))`로 만든다. `Closeable`은 `close()`가 불리면 리스트에 1을 넣는 작은 클래스다.

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_radio.py tests/test_layering.py`
- [ ] **Step 3: 구현** — 위 규칙대로 한다. `notify`가 None이면 아무것도 하지 않는다.
- [ ] **Step 4: 통과 확인, 전체 스위트**
- [ ] **Step 5: 커밋** — `git commit -m "Add the radio controller with reconnects"`

---

### Task 6: `PlayerController`에 라디오 잇기

**Files:**
- Modify: `funplayer/controller.py`
- Test: `tests/test_controller.py`

**Interfaces:**
- Consumes: Task 1 설정 키, Task 5 `RadioController`
- Produces:
  - `PlayerController.attach_radio(radio: RadioController) -> None`
  - `source: str`: `"file"` 또는 `"radio"`
  - `play_station(station_id: str) -> None`
  - 상수 `RESUME_RADIO_MSG = "이어 듣기: {name}"`
  - 바뀌는 것:
    - `title`, `subtitle`: 라디오면 방송 이름과 `"지금: " + now_title`이다. now_title이 비면 `""`.
    - `can_seek`: 라디오면 False.
    - `toggle`, `stop`, `next`, `prev`, `seek_by`, `seek_to`, `save_session`, `restore_session`
  - `radio_live: bool`: 라디오 상태가 IDLE이 아니면 True.
- 규칙:
  - **`play_station(id)`:**
    - source가 file이고 곡이 열려 있으면 `_return_position = _resume_position()`을 둔다.
    - 그다음 `_end_cue()`, source = radio, `radio.play(id)`, `_remember_source()`.
  - **곡 쪽 동작이 하나라도 시작되면** radio.stop()을 하고 source = file로 둔다. 곡 쪽 동작은 `play_index`, `open`, `add`로 재생을 시작할 때, 그리고 source가 file일 때의 `toggle`이다.
  - **source가 radio일 때:**
    - `toggle` → `radio.toggle()`
    - `stop` → `radio.stop()`
    - `next`/`prev` → `radio.step(±1)`
    - `seek_*`는 아무것도 하지 않는다.
  - **file 쪽 `toggle`에서 플레이어에 곡이 없고(`not has_track` 또는 `is_live`) `_return_position`이 있으면:** `play_index(index)` 뒤 `seek(_return_position)`을 하고, `_return_position = None`으로 둔다.
  - **재생목록 탭에서 [재생]:** 패널은 탭과 상관없이 `toggle`을 부른다. 곡으로 돌아가려면 사용자가 곡을 고르거나 두 번 클릭해야 한다(`play_index`).
    - 이 점은 spec §4.4 "지금 나오는 쪽 기준"과 같다. Task 10에서는 재생목록 탭이 보일 때 `toggle`이 곡으로 돌아가게 한다. 아래 결정을 따른다.
  - **결정:** `toggle_for_tab(tab: str)`을 따로 둔다.
    - 탭이 `"playlist"`이고 source가 radio이며 라디오가 IDLE이면, 곡 쪽 [재생]으로 본다. 위의 file toggle 규칙대로 돌아간다.
    - 그 밖에는 `toggle()`이다.
    - 이유: 사용자가 라디오를 멈추고 재생목록 탭에서 [재생]을 누르면 곡이 나오는 게 자연스럽다.
  - **세션 저장:**
    - `save_session`은 `settings.last_source = source`, `last_station = radio.current.id or ""`를 쓰고, 지금처럼 목록을 저장한다.
    - 위치는 이렇게 고른다. source가 radio면 `_return_position`이고, None이면 `last_position`을 그대로 둔다. source가 file이면 지금 규칙이다.
  - **`restore_session`:**
    - `last_source == "radio"`이고 그 방송이 목록에 있으면 이렇게 한다.
      - 목록을 불러오고 지난 곡을 고르되, 곡을 열지 않는다.
      - `_return_position = last_position`, source = radio, `radio.cue(id)`, `notify(RESUME_RADIO_MSG)`.
    - 방송이 없으면 지금 2-B 복원을 그대로 한다.
- 다른 동작은 바꾸지 않는다. `attach_radio`가 없으면 라디오 관련 동작은 모두 아무것도 하지 않는다. 기존 테스트는 그대로 통과해야 한다.

- [ ] **Step 1: 실패하는 테스트** (라디오는 `RadioController`에 Task 5의 가짜들을 붙여 쓴다. fixture `radio_ctl`)

```python
def test_file_to_radio_and_back_resumes_position(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))]); fake.position = 50.0
    c.play_station("kbs-25"); runner.finish(0, result="A")
    assert c.source == "radio" and c.title == "KBS 쿨FM" and not c.can_seek
    c.play_index(0)
    assert c.source == "file" and r.state is RadioState.IDLE

def test_playlist_tab_play_returns_to_track_at_position(radio_ctl, tmp_path):
    c, fake, r, runner = radio_ctl
    c.open([str(make_songs(tmp_path / "m", ABC))]); fake.position = 50.0
    c.play_station("kbs-25"); runner.finish(0, result="A"); c.toggle()      # 라디오 멈춤
    c.toggle_for_tab("playlist")
    assert c.source == "file" and fake.state is State.PLAYING and fake.seeks[-1] == 50.0

def test_radio_tab_toggle_reconnects(radio_ctl):
    c, fake, r, runner = radio_ctl
    c.play_station("kbs-25"); runner.finish(0, result="A"); c.toggle(); c.toggle_for_tab("radio")
    assert r.state is RadioState.CONNECTING

def test_next_prev_step_stations_while_radio(radio_ctl):
    c, fake, r, runner = radio_ctl
    c.play_station("kbs-21"); c.next(); assert r.current.id == "kbs-22"; c.prev(); assert r.current.id == "kbs-21"

def test_subtitle_shows_now_title(radio_ctl):
    c, fake, r, runner = radio_ctl
    c.play_station("kbs-25"); runner.finish(0, result="A")
    r._player.title = "곡"; assert c.subtitle == "지금: 곡"
    r._player.title = ""; assert c.subtitle == ""

def test_session_radio_round_trip_without_network(tmp_path):
    ...  # 1) 곡 50초 → play_station("mbc-mfm") 연결 → save_session → store: last_source "radio", last_station "mbc-mfm", last_position 50.0
         # 2) 새 컨트롤러+라디오로 restore_session → source "radio", r.current.id "mbc-mfm", runner.pending == [], fake.loaded == []
         #    status "이어 듣기: MBC FM4U"; 그 뒤 toggle_for_tab("playlist") → 곡을 열고 seeks[-1] == 50.0

def test_restore_with_unknown_station_falls_back_to_file(tmp_path):
    ...  # last_source "radio", last_station "gone" → 2-B 복원 그대로 (곡 대기, source "file")
```

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_controller.py`
- [ ] **Step 3: 구현**
- [ ] **Step 4: 전체 스위트 통과**
- [ ] **Step 5: 커밋** — `git commit -m "Route playback between tracks and radio"`

---

### Task 7: Qt 작업 실행기, 라디오 그림

**Files:**
- Create: `funplayer/ui/worker.py`
- Modify: `funplayer/ui/icons.py`
- Test: `tests/test_worker.py`, `tests/test_icons.py`

**Interfaces:**
- Produces:
  - `class QtRunner(QObject)`:
    - `run_async(work, done)`: `QThreadPool.globalInstance()`에서 `work`를 돌리고, 결과와 예외를 신호로 UI 스레드에 넘겨 `done(result, error)`를 부른다.
    - `call_later(seconds, fn) -> cancel`: 단발 `QTimer`를 쓴다.
    - `shutdown()`: 이후 도착하는 결과와 타이머를 버린다.
  - `icons.radio_art(size: int) -> QPixmap`
    - 배율 1, 정확히 size×size, 투명 바탕이다.
    - 시안의 라디오 그림 좌표를 쓴다. 56 단위 `s = size/56`:
      - 둥근 바탕은 `#DCE6F5`→`#C3D3EC` 세로 그라데이션, 반지름 `size*0.08`.
      - 선 `#4A6FA5`, 굵기 `2.4s`, RoundCap.
      - 몸통 `QRectF(12s,22s,32s,22s)` 반지름 `3s`.
      - 안테나 `(18s,22s)→(36s,12s)`.
      - 스피커 채운 원 중심 `(35s,33s)` 반지름 `4.5s`.
      - 눈금 3줄 `y=28,33,38`, `x 17s→26s`, 굵기 `1.6s`.

- [ ] **Step 1: 실패하는 테스트**

```python
def test_run_async_delivers_on_ui_thread(qapp):
    r = QtRunner(); got = []; main = threading.get_ident()
    r.run_async(lambda: threading.get_ident(), lambda res, err: got.append((res != main, err, threading.get_ident() == main)))
    QTest.qWaitFor(lambda: got, 2000)
    assert got == [(True, None, True)]

def test_run_async_passes_exception(qapp):
    r = QtRunner(); got = []
    def boom(): raise ValueError("x")
    r.run_async(boom, lambda res, err: got.append((res, type(err))))
    QTest.qWaitFor(lambda: got, 2000); assert got == [(None, ValueError)]

def test_call_later_and_cancel(qapp):
    r = QtRunner(); hits = []
    r.call_later(0.01, lambda: hits.append(1)); cancel = r.call_later(0.01, lambda: hits.append(2)); cancel()
    QTest.qWait(80); assert hits == [1]

def test_shutdown_drops_late_results(qapp):
    r = QtRunner(); got = []; gate = threading.Event()
    r.run_async(lambda: gate.wait(1) or 1, lambda res, err: got.append(res)); r.call_later(0.01, lambda: got.append("t"))
    r.shutdown(); gate.set(); QTest.qWait(150); assert got == []
```

`test_icons.py`에 더한다: `radio_art(40)`의 크기·배율이 `(40, 40, 1.0)`이고, 가운데 픽셀이 불투명하다.

- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현** — `QRunnable` + 신호를 가진 `QObject`로 결과를 넘긴다. 결과 신호의 연결은 `Qt.QueuedConnection`이다.
- [ ] **Step 4: 통과 확인, 전체 스위트**
- [ ] **Step 5: 커밋** — `git commit -m "Add a Qt background runner and radio art"`

---

### Task 8: 방송국 목록 위젯 (`ui/station_view.py`)

**Files:**
- Create: `funplayer/ui/station_view.py`
- Test: `tests/test_station_view.py`

**Interfaces:**
- Consumes: Task 2 `StationList`
- Produces:
  - `class StationView(QTreeWidget)`:
    - 신호:
      - `station_activated = pyqtSignal(str)`: 방송국 줄 한 번 클릭, 또는 `Enter`
      - `changed = pyqtSignal()`: 목록을 고쳤을 때(저장용)
      - `open_groups_changed = pyqtSignal(list)`
    - `set_stations(stations: StationList, open_groups: list[str]) -> None`
    - `rebuild()`
    - `set_current(station_id: str | None)`: ▶와 굵은 글씨를 붙인다.
    - `count() -> int`: 보이는 방송 수.
    - `context_menu: QMenu`
    - `actions: dict[str, QAction]`: 키는 `play`, `favorite`, `rename`, `remove`, `restore`.
- 규칙:
  - 열은 2개(이름, 출처)이고 머리는 숨긴다. 출처는 회색(`INFO_COLOR`)이다.
  - 묶음 줄은 굵게 쓰고 회색이다. `★ 즐겨찾기`만 `#E3A008`이다.
  - 묶음 줄을 누르면 접고 펴기만 한다(`setExpanded(not ...)`). 방송을 시작하지 않는다.
  - 방송국 줄 데이터는 `Qt.UserRole`에 station id를 넣는다.
  - 오른쪽 클릭 메뉴의 문구는 Global Constraints대로다. `favorite`는 체크 가능이다.
    - `rename`: `QInputDialog.getText(self, "이름 바꾸기", "이름", text=지금 이름)`. 모듈 함수 `ask_name`으로 감싸서 테스트가 바꿔 끼운다.
    - `remove`: 확인 없이 바로 지운다(기본 방송은 숨기기).
  - 끌어 옮기기는 같은 묶음 안에서만 된다. `dropEvent`에서 `stations.move`를 부르고 `rebuild`한다. 다른 묶음 위로 놓으면 무시한다.
  - 펼침 상태가 바뀌면 `open_groups_changed`에 지금 펼친 키 목록을 낸다.

- [ ] **Step 1: 실패하는 테스트**

```python
def test_groups_and_one_click_plays(qapp):
    v = StationView(); sl = StationList(); v.set_stations(sl, ["favorites", "domestic", "user"])
    top = [v.topLevelItem(i).text(0) for i in range(v.topLevelItemCount())]
    assert top[0] == "국내 방송" and top[1].startswith("해외 추천 · ")
    hits = []; v.station_activated.connect(hits.append)
    dom = v.topLevelItem(0); assert dom.isExpanded() and not v.topLevelItem(1).isExpanded()
    rect = v.visualItemRect(dom.child(3)); QTest.mouseClick(v.viewport(), Qt.LeftButton, pos=rect.center())
    assert hits == ["kbs-25"]

def test_group_row_click_only_toggles(qapp):
    v = StationView(); v.set_stations(StationList(), []); hits = []; v.station_activated.connect(hits.append)
    g = v.topLevelItem(1); QTest.mouseClick(v.viewport(), Qt.LeftButton, pos=v.visualItemRect(g).center())
    assert g.isExpanded() and hits == []

def test_enter_plays_current(qapp):
    ...  # setCurrentItem(방송 줄) → Enter 키 → station_activated(id)

def test_context_menu_favorite_rename_remove_restore(qapp, monkeypatch):
    import funplayer.ui.station_view as sv
    v = StationView(); sl = StationList(); v.set_stations(sl, ["favorites", "domestic"]); changed = []
    v.changed.connect(lambda: changed.append(1))
    v.setCurrentItem(v.topLevelItem(0).child(0)); v.context_menu.aboutToShow.emit()
    assert [a.text() for a in v.context_menu.actions()] == ["듣기", "즐겨찾기", "이름 바꾸기…", "지우기", "", "기본 방송 다시 보이기"]
    v.actions["favorite"].trigger(); assert v.topLevelItem(0).text(0) == "★ 즐겨찾기" and sl.is_favorite("kbs-21")
    monkeypatch.setattr(sv, "ask_name", lambda parent, current: "1R")
    v.setCurrentItem(v.topLevelItem(0).child(0)); v.actions["rename"].trigger(); assert sl.get("kbs-21").name == "1R"
    v.setCurrentItem(v.topLevelItem(0).child(0)); v.actions["remove"].trigger(); assert sl.get("kbs-21") is None
    v.actions["restore"].trigger(); assert sl.get("kbs-21") is not None and len(changed) == 4

def test_set_current_marks_row(qapp):
    ...  # set_current("kbs-25") → 그 줄 글자가 "▶ "로 시작하고 굵게

def test_open_groups_reported(qapp):
    ...  # 해외 묶음 하나를 펼치면 open_groups_changed가 그 키를 담은 목록을 낸다
```

- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인, 전체 스위트**
- [ ] **Step 5: 커밋** — `git commit -m "Add the station list view"`

---

### Task 9: [주소 넣기…] 창 (`ui/radio_dialogs.py`)

**Files:**
- Create: `funplayer/ui/radio_dialogs.py`
- Test: `tests/test_radio_dialogs.py`

**Interfaces:**
- Produces:
  - `class AddUrlDialog(QDialog)`:
    - 칸: `name_edit`, `url_edit`
    - 라벨: `error_label`(빨간 글씨, 처음엔 빈칸), `hint_label`
    - 단추: `add_button`(기본 단추), `cancel_button`
    - `result_value() -> tuple[str, str] | None`: (이름, 주소). 넣기 전이면 None이다.
  - `valid_url(text: str) -> bool`: 앞뒤 공백을 지운 뒤 `http://` 또는 `https://`로 시작하고, 호스트가 있어야 한다.
- 규칙:
  - [넣기]를 눌렀을 때 주소가 올바르지 않으면 `error_label`에 `"주소가 올바르지 않습니다"`를 보이고 창을 닫지 않는다.
  - 주소가 올바르면 `accept()`한다.
  - 모달 창이다(`exec_`). 제목과 문구는 Global Constraints대로 쓴다.

- [ ] **Step 1: 실패하는 테스트**

```python
def test_add_url_dialog_validates(qapp):
    d = AddUrlDialog(); d.url_edit.setText("ftp://x"); d.add_button.click()
    assert d.error_label.text() == "주소가 올바르지 않습니다" and d.result() == 0 and d.result_value() is None
    d.name_edit.setText(" 우리 동네 "); d.url_edit.setText(" https://s.example/live.mp3 "); d.add_button.click()
    assert d.result() == QDialog.Accepted and d.result_value() == ("우리 동네", "https://s.example/live.mp3")

def test_dialog_texts(qapp):
    d = AddUrlDialog()
    assert d.windowTitle() == "주소 넣기" and (d.add_button.text(), d.cancel_button.text()) == ("넣기", "취소")
    assert d.hint_label.text() == "http·https 방송 주소, .m3u·.pls·.m3u8 주소를 넣을 수 있습니다."

@pytest.mark.parametrize("u,ok", [("http://a", True), ("https://a.b/c", True), ("http://", False), ("a.b", False), ("", False)])
def test_valid_url(u, ok):
    assert valid_url(u) is ok
```

- [ ] **Step 2–4: 실패 확인 → 구현 → 통과·전체 스위트**
- [ ] **Step 5: 커밋** — `git commit -m "Add the add-URL dialog"`

---

### Task 10: 패널에 라디오 붙이기

**Files:**
- Modify: `funplayer/ui/player_panel.py`, `funplayer/__main__.py`
- Test: `tests/test_panel_radio.py`(새 파일), `tests/test_panel_input.py`(단축키 표), `tests/test_main.py`

**Interfaces:**
- Consumes: Task 5–9 전부, 그리고 `PlayerBridge.lost`
- Produces:
  - 생성자: `PlayerPanel(..., stations_path: str | None = None, runner=None)`
    - runner가 None이면 `QtRunner(self)`다.
    - stations_path가 None이면 저장하지 않는다(테스트용 메모리 목록).
  - 위젯:
    - `tab_bar: QTabBar` (`재생목록`, `라디오`)
    - `station_view: StationView`
    - `add_url_button`
    - `live_label`, `listened_label`
  - 그 밖: `radio: RadioController`, `set_tab(name: str)`, 단축키 `("Ctrl+Tab", "next_tab")`
- 규칙:
  - **탭 줄:** `separator` 아래, 목록 위에 둔다. 탭을 바꾸면 이렇게 한다.
    - `playlist_view` ↔ `station_view`를 바꿔 보인다.
    - 아래 줄 단추를 바꾼다. 재생목록이면 열기·추가·목록을 보이고 주소 넣기를 숨긴다. 라디오면 그 반대다. 보기 단추는 늘 보인다.
    - `count_label`은 `"{n}곡"` 또는 `"방송 {n}개"`다.
    - `settings.tab`을 저장한다.
    - **탭을 바꿔도 플레이어·라디오를 부르지 않는다.**
  - **시작할 때:** `settings.tab`으로 탭을 고른다. 이어 듣기에서 source가 radio면 라디오 탭이다.
  - **방송국:** `station_view.station_activated(id)` → `controller.play_station(id)`.
    - `station_view.changed` → `save_stations`(경로가 있을 때).
    - `open_groups_changed` → `settings.radio_open`.
  - **[주소 넣기…]:** `AddUrlDialog`를 `exec_`한다. 넣었으면 `stations.add_url`을 하고 `rebuild`한 뒤 그 방송을 `play_station`한다. 이미 있으면 `DUP_STATION_MSG` 안내 뒤 그 방송을 듣는다. 저장도 한다.
  - **`refresh()` (source가 radio일 때):**
    - 그림은 `radio_art(art_label.width())`이고, 방송이 바뀔 때만 다시 그린다.
    - 탐색 줄: `seek_slider`를 숨기고 `live_label`과 `listened_label`을 보인다.
      - `live_label`은 `"● LIVE"`이고, 라디오가 LIVE·RETRYING이면 `#C5221F`, 아니면 `INFO_COLOR`다.
      - `listened_label`은 `"들은 시간 " + format_time(radio.elapsed)`다.
      - `elapsed_label`·`total_label`은 숨긴다.
    - `repeat_button`·`shuffle_button`은 `setEnabled(False)`다.
    - 재생 단추 아이콘은 라디오가 IDLE이면 재생, 아니면 일시정지다.
    - `station_view.set_current(radio.current.id)`.
    - source가 file로 돌아오면 모두 2-B 모습으로 되돌린다.
  - **재생 단추와 `Space`:** `controller.toggle_for_tab(지금 탭)`.
  - **작게 보기:** 라디오일 때 탐색 줄 전체(`live_label`, `listened_label`)를 숨긴다. 탭 줄, `station_view`, `add_url_button`은 `HIDDEN_IN_MINI`처럼 숨긴다.
  - **[곡 정보] (라디오일 때):** `TrackInfo`를 만들어 띄운다.
    - `path`는 사용자·해외 방송이면 주소, 국내 방송이면 `"방송사 웹 재생 주소 (들을 때마다 새로 받음)"`이다.
    - `title`은 이름, `artist`는 출처다.
    - 연결되어 있으면 형식 칸을 위한 codec·sample_rate·channels를 디코더에서 받는다. 받기 어려우면 비운다.
  - **브리지:** `lost` → `radio.on_lost`.
  - **`shutdown()`:** `save_session` 뒤 `radio.shutdown()`, `runner.shutdown()`, 그다음 지금 순서대로 한다.
  - **`__main__`:**
    - `stations_path=str(app_dir() / "stations.json")`를 넘긴다.
    - 방송국은 `load_stations`로 읽는다. 패널 안에서 해도 된다.
- 지키는 것: 2-B의 모든 패널 테스트가 그대로 통과한다(라디오 탭을 보지 않은 상태의 모습은 같다). 탭 줄이 생겨도 패널 최소 폭은 380 미만이다.

- [ ] **Step 1: 실패하는 테스트** (`tests/test_panel_radio.py`, 가짜 runner와 `FakeLivePlayer`는 쓰지 않는다. 패널은 진짜 `AudioPlayer` 대신 `FakePlayer`에 Task 5의 라이브 메서드를 더한 `FakePlayer`를 쓴다 — `tests/fakes.py`의 `FakePlayer`에 `play_stream`/`continue_stream`/`is_live`/`stream_title`/`on_lost`를 더한다.)

```python
def test_tab_switch_never_touches_network(rpanel):
    p, fake, runner = rpanel
    p.tab_bar.setCurrentIndex(1)
    assert p.station_view.isVisible() and not p.playlist_view.isVisible() and runner.pending == []
    assert p.add_url_button.isVisible() and not p.open_button.isVisible() and p.count_label.text() == "방송 42개"
    p.tab_bar.setCurrentIndex(0); assert p.open_button.isVisible() and p.settings.tab == "playlist"

def test_one_click_starts_station_and_live_row(rpanel):
    p, fake, runner = rpanel; p.set_tab("radio")
    p.station_view.station_activated.emit("kbs-25"); assert p.controller.status == "연결 중…"
    runner.finish(0, result=FakeStream()); p.refresh()
    assert p.title_label.toolTip() == "KBS 쿨FM" and p.live_label.text() == "● LIVE"
    assert not p.seek_slider.isVisible() and p.listened_label.text().startswith("들은 시간 ")
    assert not p.repeat_button.isEnabled() and not p.shuffle_button.isEnabled()

def test_failure_is_gray_hint(rpanel):
    p, fake, runner = rpanel; p.station_view.station_activated.emit("kbs-25"); runner.finish(0, error=DecodeError("x")); p.refresh()
    assert p.status_label.toolTip() == "지금은 이 방송을 들을 수 없습니다. 다른 방송을 골라 보세요" and not p.controller.status_error

def test_add_url_flow(rpanel, monkeypatch):
    ...  # AddUrlDialog.exec_ 를 바꿔 끼워 ("우리 동네", "https://s.example/a.mp3") 반환 → 목록 끝 "직접 넣은 방송" 묶음에 생기고 연결 시작;
         # 같은 주소로 한 번 더 → status "이미 목록에 있습니다"였다가 연결 시작

def test_playlist_tab_play_button_returns_to_track(rpanel, tmp_path):
    ...  # 곡 재생 50초 → 방송 연결 → 재생 단추(라디오 탭)로 멈춤 → 재생목록 탭 → 재생 단추 → fake.loaded 마지막이 곡, seeks[-1] == 50.0

def test_mini_hides_radio_rows(rpanel):
    ...  # 방송 연결 뒤 set_mini(True) → tab_bar, station_view, live_label, listened_label 모두 숨김; set_mini(False) → 다시 보임(라디오 탭이면)

def test_stations_saved_on_change(qapp, tmp_path):
    ...  # stations_path=tmp/s.json 으로 패널 → 즐겨찾기 액션 → 파일이 생기고 favorites에 그 id

def test_restore_radio_session_no_network(qapp, tmp_path):
    ...  # store에 last_source "radio", last_station "mbc-mfm" + last.m3u8 → 패널 생성 → 라디오 탭, status "이어 듣기: MBC FM4U", runner.pending == []
```

`test_panel_input.py`의 `test_shortcut_table` 집합에 `"Ctrl+Tab"`을 더한다. `test_main_smoke`에는 `stations.json`이 없어도 켜지고 꺼지는지 확인을 더한다(즐겨찾기 등 바꾼 게 없으면 파일을 만들지 않아도 된다).

- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 전체 스위트 통과** (2-B 테스트 포함)
- [ ] **Step 5: 커밋** — `git commit -m "Add the radio tab to the player panel"`

---

### Task 11: 문서와 정리

**Files:**
- Modify: `CLAUDE.md`(파일 구조표에 새 파일), `docs/개발로드맵.md` §5 구조(radio.py, resolve.py, stations.py 한 줄씩)

- [ ] **Step 1:** 파일 구조표에 새 파일의 역할을 한 줄씩 적는다. 다른 문장은 바꾸지 않는다.
- [ ] **Step 2:** 전체 스위트 통과
- [ ] **Step 3: 커밋** — `git commit -m "Document the radio modules"`

---

### Task 12: 실제 방송 확인과 사용자 체크리스트 (controller가 직접)

- 저장소 밖 스크래치 스크립트로 다음을 한다.
  - `tools/check_stations.py`를 돌려 42개 방송을 확인한다. 실패한 해외 추천은 같은 장르의 다른 방송으로 바꾸거나 빼고, 그 변경은 커밋한다.
  - KBS, MBC, 해외 한 곳씩 실제 연결해 10초 소리를 확인한다.
  - 실제 화면을 offscreen으로 캡처한다(라디오 탭 재생 중, 작게 보기, [주소 넣기…]). 파일은 `docs/images/stage3_real.png`이다.
- 확인 페이지(아티팩트)를 갱신하고, 사용자에게 run.bat과 §7 체크리스트를 안내한 뒤 **멈춘다**. 30분 연속 재생은 사용자가 확인한다.
