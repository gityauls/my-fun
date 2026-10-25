# my-fun 2-B단계 편의 기능 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2-A 플레이어에 이어 듣기(K-2), 곡 정보(H-1), 앨범 그림(H-2), 작게 보기(I-2), 멀티미디어 키(J-3)와 그 단축키를 더한다.

**Architecture:**
- **태그:** Qt 없는 `core/taginfo.py`가 `TrackInfo`와 순수 함수(한글 되살리기, 표지 파일 고르기, 표시 문자열)를 맡는다. PyAV로 파일을 읽는 일은 `engine/tags.py`의 `read_info`가 한다.
- **규칙:** 이어 듣기(저장·복원·"멈춰 있는 이어 듣기" 상태)와 지금 곡 정보는 `controller.py`가 정한다.
- **화면:** `ui/cover.py`(그림 고르기·줄이기), `ui/info_dialog.py`(곡 정보 창), `ui/player_panel.py`(머리 줄, [보기 ▾], 작게 보기), `ui/media_keys.py`(전역 단축키), `ui/window_keeper.py`(독립 실행 창의 위치·항상 위)가 맡는다.

**Tech Stack:** Python 3.14(3.13 호환), PyQt5 5.15.11, PyAV 19.0.2, pytest 9.1.1. 새 의존성은 없다.

**Spec:** `docs/stage2b_design.md` (시안 `docs/images/stage2b_mockup.png`, 2-A spec `docs/stage2a_design.md`, 로드맵 `docs/개발로드맵.md`)

## Global Constraints

- **Python 버전:** 3.13에서도 돌아야 한다. `funplayer`의 모든 비어 있지 않은 `.py`는 `from __future__ import annotations`로 시작한다.
- **의존성:** `requirements*.txt`는 바꾸지 않는다. 새 패키지는 넣지 않는다. 태그와 그림은 PyAV로 읽는다.
- **Qt 사용 범위:**
  - PySide6는 import하지 않는다.
  - `core/`, `engine/`, `controller.py`는 PyQt5를 import하지 않는다(`tests/test_layering.py`).
  - `core/taginfo.py`는 PyAV도 import하지 않는다.
- **이전 단계 규칙 유지:**
  - 곡 끝 알림은 플레이어가 STOPPED일 때만 받는다.
  - 단축키는 `Qt.WidgetWithChildrenShortcut`이다.
  - 화면 갱신은 200ms마다 한다.
  - 2-A의 문구·메뉴·단축키는 아래에 적은 것 말고는 그대로 둔다.
- **화면 문구(정확히 이대로):**
  - 상태 안내(회색): `이어 듣기: {m:ss}부터` (시간은 `core.timefmt.format_time`), `멀티미디어 키를 다른 프로그램이 쓰고 있습니다`
  - 아래 줄 단추: `열기`, `추가`, `목록`, `보기`
  - [보기] 메뉴(빈 칸은 구분선): `곡 정보…\tCtrl+I`, `작게 보기\tCtrl+M`(체크), —, `작게 볼 때 항상 위`(체크), `멀티미디어 키 사용`(체크)
  - 오른쪽 클릭 메뉴: `재생\tEnter`, `곡 정보…`, `선택한 곡 지우기\tDel`, —, `전체 선택\tCtrl+A`
  - 풍선 도움말: 그림 `곡 정보`, 작게 보기 단추 `작게 보기` / `보통 보기`
  - 곡 정보 창: 창 제목 `곡 정보`, 칸 이름 `제목` `가수` `앨범` `년도` `장르` `트랙` `길이` `형식` `크기` `경로`, 단추 `폴더 열기` `닫기`, 빈 칸 `—`
  - 가수·앨범 줄의 구분: ` · `
  - 형식 줄: `{코덱} · {N} kbps · {N.N} kHz · {채널}`. 채널은 `모노`, `스테레오`, `{n}채널`. 없는 부분은 빼고 잇는다.
  - 크기: 1 MiB 이상은 `{x.x} MB`(1024 기준), 그보다 작으면 `{n} KB`(반올림, 최소 1), 0이면 빈 문자열
- **그림 크기:** 보통 보기 56×56, 작게 보기 40×40, 곡 정보 창 160×160. 원본은 긴 변 320으로 줄여 둔다.
- **이어 듣기:**
  - 목록 파일 이름 `last.m3u8`, 위치는 `%APPDATA%\my-fun\`. 쓰기는 2-A의 `write_playlist`를 쓴다.
  - 남은 시간이 5.0초보다 짧으면 처음부터.
- **설정 키(기본값):**
  - `player_last_track` (`""`), `player_last_position` (`0.0`, 0 이상 유한한 수)
  - `player_mini` (false), `player_mini_on_top` (true), `player_media_keys` (true)
  - `player_geometry`, `player_mini_geometry` (`[x, y, 폭, 높이]` 정수 네 개이고 폭·높이 > 0, 아니면 없음)
  - 다른 키는 건드리지 않는다.
- **멀티미디어 키:**
  - 가상 키는 재생/일시정지 `0xB3`, 다음 `0xB0`, 이전 `0xB1`, 정지 `0xB2`다.
  - 등록 번호는 `0xA000 + 가상 키`다. `RegisterHotKey(NULL, id, MOD_NOREPEAT=0x4000, vk)`로 스레드에 등록한다(창 핸들 없음). 메시지는 `WM_HOTKEY = 0x0312`다.
  - Qt 네이티브 필터의 이벤트 종류는 `b"windows_generic_MSG"`다. 2026-10-25에 확인했다.
- **테스트:**
  - 실제 소리 장치, 네트워크, 실제 전역 단축키 등록을 쓰지 않는다. `MediaKeys`는 가짜 API로 시험한다. 패널 기본값은 아무것도 등록하지 않는 `MediaKeys`다.
  - Qt 테스트는 offscreen에서 돈다.
  - 태그가 든 MP3는 테스트가 직접 만든다(`tests/tagfiles.py`). 이진 파일을 커밋하지 않는다.
- **git:** 작업마다 커밋한다. 로컬만 쓰고 push하지 않는다. `Test-mp3/`와 저장소 맨 위의 `*.m3u8`는 커밋하지 않는다.

## Review Focus

1. **이어 듣기 목록의 곡이 전부 없어졌다(USB를 뺐다):** 회색 목록으로 켜지고, 오류 문구나 곡 넘김 반복 없이 조용히 멈춰 있어야 한다 → Task 5 `test_restore_with_all_files_missing_is_quiet`
2. **서양 이름 태그(Beyoncé, Größe, Café):** 한글 되살리기가 이것을 한자로 바꾸면 안 된다 → Task 2 `test_fix_text_keeps_western_names`
3. **저장한 창 위치가 지금 화면 밖이다(모니터를 뗐다):** 화면 가운데에 크기를 지켜 놓아야 한다 → Task 10 `test_offscreen_geometry_is_centered`
4. **태그 속 그림이 아주 크거나 깨졌다:** 줄여서 보이거나 폴더 그림·기본 그림으로 넘어가야 하고, 멈추면 안 된다 → Task 6 `test_big_picture_scaled_down`, `test_corrupt_picture_falls_back`
5. **다른 프로그램이 멀티미디어 키 일부를 먼저 쓰고 있다:** 안내를 한 번 보이고, 등록된 나머지 키는 동작하고, 끌 때 모두 풀어야 한다 → Task 11 `test_busy_key_returns_false_and_keeps_others`, `test_panel_media_keys_busy_notice`

## 계획에서 정한 것

spec이 열어 둔 부분을 이렇게 정한다. 구현자는 이대로 따른다.

1. **한글 되살리기 2번 규칙:** CP949 결과에 한글 음절(U+AC00~U+D7A3)이 있을 때만 쓴다(spec §4.2에 반영함).
2. **곡 정보 읽기:** 컨트롤러의 `info`는 처음 물을 때 읽고 경로별로 한 칸 캐시한다. `read_info`는 생성자로 바꿔 넣을 수 있다.
3. **이어 듣기 상태:**
   - "멈춰 있는 이어 듣기"(`cued`)는 곡을 load하고 위치로 seek한 STOPPED 상태다.
   - 이때 [재생]은 다시 load하지 않고 `play()`만 한다.
   - 탐색은 `can_seek`로 허용한다.
4. **지난 곡이 목록에 없으면** 재생 순서의 첫 곡을 고르고, 저장한 위치는 쓰지 않는다.
5. **복원 실패는 조용하다:** 회색 표시만 하고 상태 줄에는 아무것도 쓰지 않는다.
6. **저장 시점:** 목록이나 지금 곡을 바꾸는 공개 함수(`open`, `add`, `remove`, `sort`, `move`, `clear`, `play_index`)가 끝날 때 `_remember()`를 부른다. 쓰기 오류는 로그만 남긴다.
7. **패널과 이어 듣기:** `session_path`를 받으면 생성자에서 복원하고 `shutdown()`에서 저장한다. 테스트 기본값은 None이라 아무것도 쓰지 않는다.
8. **작게 보기:**
   - [이전]·[재생]·[다음] 단추를 머리 줄로 옮긴다.
   - 패널은 `settings.mini`를 스스로 적용하지 않는다. 켤 때의 모양, 창 위치, 항상 위는 새 파일 `ui/window_keeper.py`가 한다. spec은 `__main__.py`라고 했는데, 시험할 수 있게 떼어 냈다(spec §5에 반영함).
9. **`MediaKeys(api=None)`는 아무것도 하지 않는다.** 실제 Windows API는 `__main__`만 넘긴다.
10. **전역 단축키는 스레드에 등록한다.** 항상 위를 바꾸면 창 핸들이 다시 만들어지는데, 스레드 등록은 그래도 풀리지 않는다.
11. **창이 앞에 있을 때 쓰는 멀티미디어 키 대체 단축키는 늘 둔다.** 전역 등록이 되면 Windows가 키를 먼저 가져가므로 두 번 동작하지 않는다.
12. **그림 크기:** 그림 pixmap은 배율 1로 만든다. High-DPI는 이미 미뤄 둔 일이다.
13. **트랙 칸:** 저장된 값 그대로 보인다(예: `3/12`).
14. **FakePlayer의 `missing_fails`:** 켜면 없는 파일을 load할 때 실제 플레이어처럼 `DecodeError`를 낸다.

---

### Task 1: 설정 키

**Files:**
- Modify: `funplayer/core/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `Settings.last_track: str`, `last_position: float`, `mini: bool`, `mini_on_top: bool`, `media_keys: bool`, `geometry: list[int] | None`, `mini_geometry: list[int] | None` — 모두 읽기·쓰기 속성. 쓰면 store에 넣고 save를 한 번 부른다(기존 `_set`).

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`tests/test_settings.py` 끝에)

```python
def test_stage2b_defaults():
    s = Settings({}, lambda: None)
    assert (s.last_track, s.last_position, s.mini, s.mini_on_top, s.media_keys) == ("", 0.0, False, True, True)
    assert s.geometry is None and s.mini_geometry is None

@pytest.mark.parametrize("raw", [None, "x", True, -3, float("nan"), float("inf"), [1]])
def test_bad_last_position_is_zero(raw):
    assert Settings({"player_last_position": raw}, lambda: None).last_position == 0.0

@pytest.mark.parametrize("raw", [None, "1,2,3,4", [1, 2, 3], [1, 2, 0, 4], [1, 2, 3, -4],
                                 [1, "2", 3, 4], [1, 2, True, 4], [1.5, 2, 3, 4], {"x": 1}])
def test_bad_geometry_is_none(raw):
    s = Settings({"player_geometry": raw, "player_mini_geometry": raw}, lambda: None)
    assert s.geometry is None and s.mini_geometry is None

def test_bool_and_text_keys_ignore_wrong_types():
    s = Settings({"player_mini": 1, "player_mini_on_top": "no", "player_media_keys": 0,
                  "player_last_track": 5}, lambda: None)
    assert (s.mini, s.mini_on_top, s.media_keys, s.last_track) == (False, True, True, "")

def test_stage2b_round_trip():
    store, saves = {}, []
    s = Settings(store, lambda: saves.append(1))
    s.last_track = "C:/m/a.mp3"; s.last_position = 72.5; s.mini = True
    s.mini_on_top = False; s.media_keys = False
    s.geometry = (10, 20, 380, 480); s.mini_geometry = [5, 6, 380, 92]
    assert store == {"player_last_track": "C:/m/a.mp3", "player_last_position": 72.5,
                     "player_mini": True, "player_mini_on_top": False, "player_media_keys": False,
                     "player_geometry": [10, 20, 380, 480], "player_mini_geometry": [5, 6, 380, 92]}
    assert len(saves) == 7 and s.geometry == [10, 20, 380, 480]
    s.geometry = None
    assert store["player_geometry"] is None and s.geometry is None
```

- [ ] **Step 2: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_settings.py`
Expected: 새 테스트들이 `AttributeError`로 FAIL

- [ ] **Step 3: `funplayer/core/settings.py`에 일곱 속성을 만든다**

- `DEFAULTS`에 위 Global Constraints의 기본값을 더한다(geometry 두 개는 None).
- 읽기 규칙:
  - bool 키는 `isinstance(value, bool)`일 때만 그 값을 쓴다(`shuffle`과 같다).
  - `last_track`은 str만 받는다.
  - `last_position`은 bool이 아닌 int·float이면서 유한하고 0 이상일 때만 `float(value)`다.
  - geometry는 길이 4인 list이고, 원소가 모두 bool이 아닌 int이며, 폭·높이 > 0일 때만 `list(value)`다.
- 쓰기: geometry setter는 None이나 정수 네 개짜리 list·tuple을 받아 list나 None으로 저장한다.

- [ ] **Step 4: 실행해서 통과를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_settings.py`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add funplayer/core/settings.py tests/test_settings.py
git commit -m "Add stage 2-B settings keys"
```

---

### Task 2: `core/taginfo.py` — TrackInfo와 순수 함수

**Files:**
- Create: `funplayer/core/taginfo.py`
- Test: `tests/test_taginfo.py`

**Interfaces:**
- Produces:
  - `@dataclass class TrackInfo`: `path: str`; `title`, `artist`, `album`, `year`, `genre`, `track`, `codec`은 `str = ""`; `duration: float = 0.0`; `bitrate`, `sample_rate`, `channels`, `size`는 `int = 0`; `picture: bytes | None = None`
  - `fix_text(s: str) -> str`
  - `pick_cover(names: list[str], album: str) -> str | None`
  - `codec_label(name: str) -> str`
  - `format_line(info: TrackInfo) -> str`
  - `format_size(n: int) -> str`
  - `subtitle(info: TrackInfo | None) -> str`

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`tests/test_taginfo.py`)

```python
import pytest
from funplayer.core.taginfo import (TrackInfo, codec_label, fix_text, format_line, format_size,
                                    pick_cover, subtitle)

def test_fix_text_surrogate_cp949():
    s = "천상천하".encode("cp949").decode("utf-8", "surrogateescape")
    assert fix_text(s) == "천상천하"

def test_fix_text_latin1_cp949():
    assert fix_text("투투".encode("cp949").decode("latin-1")) == "투투"

@pytest.mark.parametrize("s", ["", "Britney Spears", "너만은 모르길", "Café del Mar", "Beyoncé", "Größe", "naïve"])
def test_fix_text_keeps_western_names(s):
    assert fix_text(s) == s

def test_fix_text_undecodable_bytes_become_replacement():
    out = fix_text(b"ab\xff\xfe".decode("utf-8", "surrogateescape"))
    assert out.startswith("ab") and "\ufffd" in out and not any(0xDC80 <= ord(c) <= 0xDCFF for c in out)

@pytest.mark.parametrize("names,album,want", [
    (["a.mp3", "Folder.JPG", "cover.png"], "", "cover.png"),
    (["album.jpg", "front.jpg", "folder.jpg"], "", "folder.jpg"),
    (["front.jpeg", "x.mp3"], "", "front.jpeg"),
    (["Day By Day.jpg", "scan1.jpg"], "Day By Day", "Day By Day.jpg"),
    (["only.png", "a.mp3"], "", "only.png"),
    (["a.jpg", "b.jpg"], "", None),
    (["cover.gif", "a.mp3"], "", None),
    ([], "x", None)])
def test_pick_cover(names, album, want):
    assert pick_cover(names, album) == want

def test_codec_label():
    assert [codec_label(n) for n in ("mp3float", "mp3", "aac", "flac", "vorbis", "opus", "wmav2",
                                      "alac", "pcm_s16le", "ape", "")] == [
        "MP3", "MP3", "AAC", "FLAC", "Vorbis", "Opus", "WMA", "ALAC", "PCM", "APE", ""]

def test_format_line():
    assert format_line(TrackInfo("x", codec="mp3float", bitrate=192000, sample_rate=44100, channels=2)) \
        == "MP3 · 192 kbps · 44.1 kHz · 스테레오"
    assert format_line(TrackInfo("x", codec="pcm_s16le", sample_rate=48000, channels=1)) == "PCM · 48 kHz · 모노"
    assert format_line(TrackInfo("x", codec="flac", channels=6)) == "FLAC · 6채널"
    assert format_line(TrackInfo("x")) == ""

def test_format_size():
    assert [format_size(n) for n in (5_452_595, 1_048_576, 2048, 100, 0)] == ["5.2 MB", "1.0 MB", "2 KB", "1 KB", ""]

def test_subtitle():
    assert subtitle(TrackInfo("x", artist="Lo-Fi Band", album="Sunday Mornings")) == "Lo-Fi Band · Sunday Mornings"
    assert subtitle(TrackInfo("x", artist="Lo-Fi Band")) == "Lo-Fi Band"
    assert subtitle(TrackInfo("x", album="Al")) == "Al"
    assert subtitle(TrackInfo("x")) == "" and subtitle(None) == ""
```

- [ ] **Step 2: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_taginfo.py`
Expected: FAIL (`ModuleNotFoundError: funplayer.core.taginfo`)

- [ ] **Step 3: `funplayer/core/taginfo.py`를 만든다**

- `fix_text`의 규칙(spec §4.2):

```python
def fix_text(s: str) -> str:
    if any(0xDC80 <= ord(c) <= 0xDCFF for c in s):        # 1. 깨진 바이트가 섞였다
        return s.encode("utf-8", "surrogateescape").decode("cp949", "replace")
    if any(ord(c) >= 0x80 for c in s) and all(ord(c) <= 0xFF for c in s):   # 2. Latin-1로 읽혔다
        try:
            fixed = s.encode("latin-1").decode("cp949")
        except UnicodeDecodeError:
            return s
        if any("\uac00" <= c <= "\ud7a3" for c in fixed):
            return fixed
    return s
```

- `pick_cover`:
  - 확장자는 `.jpg` `.jpeg` `.png`이고, 대소문자를 가리지 않는다.
  - 이름(확장자 뺀 부분, 소문자) 후보를 `cover`, `folder`, `front`, `album`, `album.lower()`(비어 있지 않을 때) 순서로 찾는다. 각 후보마다 `names` 순서대로 처음 맞는 것을 고른다.
  - 없으면, 그림 파일이 딱 하나일 때 그것이다.
- `codec_label`의 이름 표:
  - `{"mp3": "MP3", "mp3float": "MP3", "aac": "AAC", "flac": "FLAC", "vorbis": "Vorbis", "opus": "Opus", "wmav1": "WMA", "wmav2": "WMA", "alac": "ALAC"}`
  - `pcm_`로 시작하면 `"PCM"`, 그 밖은 `name.upper()`다.
- `format_line`:
  - kHz는 `f"{sample_rate / 1000:g} kHz"`다.
  - kbps는 `round(bitrate / 1000)`이다.
  - 0이나 빈 값인 부분은 뺀다.

- [ ] **Step 4: 실행해서 통과를 본다** — 위 명령, Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add funplayer/core/taginfo.py tests/test_taginfo.py
git commit -m "Add TrackInfo and Korean tag text recovery"
```

---

### Task 3: `engine/tags.py` — PyAV로 곡 정보 읽기

**Files:**
- Create: `funplayer/engine/tags.py`, `tests/tagfiles.py`
- Test: `tests/test_tags.py`

**Interfaces:**
- Consumes: Task 2 `TrackInfo`, `fix_text`; `funplayer.engine.decoder._duration(container, stream) -> float`
- Produces:
  - `read_info(path: str) -> TrackInfo` — 예외를 밖으로 내지 않는다.
  - 테스트 도우미 `tests/tagfiles.py`: `png_1x1() -> bytes`, `write_tagged(dest, source_mp3, v2=None, picture=None, v1=None) -> Path`

- [ ] **Step 1: 테스트 도우미를 만든다** (`tests/tagfiles.py`, 이대로)

```python
"""테스트용 태그 파일 만들기: 손으로 쓴 ID3v2.3(글자 인코딩 0)·ID3v1 태그를 MP3 앞뒤에 붙인다."""
import struct
import zlib
from pathlib import Path


def png_1x1() -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


def _frame(fid: str, data: bytes) -> bytes:
    return fid.encode() + struct.pack(">I", len(data)) + b"\x00\x00" + data


def _syncsafe(n: int) -> bytes:
    return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])


def _strip_v2(data: bytes) -> bytes:
    if data[:3] == b"ID3":
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        return data[10 + size:]
    return data


def write_tagged(dest, source_mp3, v2=None, picture=None, v1=None) -> Path:
    """v2: {"TIT2": 바이트, ...} (글자 인코딩 0 바이트 그대로), picture: PNG 바이트,
    v1: (제목, 가수, 앨범) 바이트 — 각각 30바이트로 자른다."""
    audio = _strip_v2(Path(source_mp3).read_bytes())
    head = b""
    if v2 or picture:
        body = b"".join(_frame(k, b"\x00" + v) for k, v in (v2 or {}).items())
        if picture:
            body += _frame("APIC", b"\x00image/png\x00\x03\x00" + picture)
        head = b"ID3\x03\x00\x00" + _syncsafe(len(body)) + body
    tail = b""
    if v1:
        pad = lambda b: b[:30].ljust(30, b"\x00")
        tail = b"TAG" + pad(v1[0]) + pad(v1[1]) + pad(v1[2]) + b"2000" + b"\x00" * 30 + b"\xff"
    Path(dest).write_bytes(head + audio + tail)
    return Path(dest)
```

- [ ] **Step 2: 실패하는 테스트를 쓴다** (`tests/test_tags.py`)

```python
import os
from tagfiles import png_1x1, write_tagged
from funplayer.engine.tags import read_info

cp = lambda s: s.encode("cp949")

def test_reads_id3v2_tags_and_picture(tmp_path, tone_mp3):
    p = write_tagged(tmp_path / "a.mp3", tone_mp3, picture=png_1x1(), v2={
        "TIT2": cp("천상천하"), "TPE1": b"Ami", "TALB": b"1st", "TYER": b"2000",
        "TCON": b"Ballad", "TRCK": b"3/12"})
    info = read_info(str(p))
    assert (info.title, info.artist, info.album, info.year, info.genre, info.track) == (
        "천상천하", "Ami", "1st", "2000", "Ballad", "3/12")
    assert info.picture == png_1x1() and info.codec in ("mp3", "mp3float")
    assert info.channels == 2 and info.sample_rate == 44100 and info.bitrate > 0
    assert 2.5 < info.duration < 3.5 and info.size == p.stat().st_size and info.path == str(p)

def test_reads_id3v1_cp949(tmp_path, tone_mp3):
    p = write_tagged(tmp_path / "b.mp3", tone_mp3, v1=(cp("천상천하"), cp("투투"), b"1st"))
    info = read_info(str(p))
    assert (info.title, info.artist, info.album) == ("천상천하", "투투", "1st") and info.picture is None

def test_wav_without_tags(tone_wav):
    info = read_info(tone_wav)
    assert (info.title, info.artist, info.album, info.picture) == ("", "", "", None)
    assert info.codec.startswith("pcm") and 2.5 < info.duration < 3.5

def test_unreadable_file_gives_path_and_size(broken_mp3):
    info = read_info(broken_mp3)
    assert info.path == broken_mp3 and info.size == os.path.getsize(broken_mp3)
    assert (info.title, info.duration, info.codec) == ("", 0.0, "")

def test_missing_file(tmp_path):
    info = read_info(str(tmp_path / "nope.mp3"))
    assert info.size == 0 and info.title == ""
```

- [ ] **Step 3: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tags.py`
Expected: FAIL (`ModuleNotFoundError: funplayer.engine.tags`)

- [ ] **Step 4: `read_info(path) -> TrackInfo`를 만든다**

- **크기:** 먼저 `os.path.getsize`로 잰다. OSError면 0이다.
- **열기:** `av.open(path)`로 연다. 열기나 읽기에서 나는 모든 예외는 debug 로그만 남기고 `TrackInfo(path, size=size)`를 돌려준다.
- **태그:**
  - `container.metadata`를 쓰고, 빠진 키는 첫 오디오 스트림의 `metadata`로 채운다.
  - 키는 `title`, `artist`, `album`, `date`, `genre`, `track`이고, 값마다 `fix_text`를 거친다.
  - `year`는 `date`의 앞 4글자가 숫자면 그 4글자, 아니면 `date` 그대로다.
- **형식:** `codec = stream.codec_context.name`, `sample_rate = codec_context.sample_rate`, `channels = codec_context.channels`, `bitrate = container.bit_rate or 0`, `duration = _duration(container, stream)`이다.
- **그림:**
  - `container.streams.video` 중 `stream.disposition & av.stream.Disposition.attached_pic`인 첫 스트림을 고른다.
  - `next(container.demux(that_stream), None)` 패킷의 `bytes(...)`를 쓰고, 패킷이 없으면 None이다.

- [ ] **Step 5: 실행해서 통과를 본다** — 위 명령, Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add funplayer/engine/tags.py tests/tagfiles.py tests/test_tags.py
git commit -m "Read tags, format and embedded picture with PyAV"
```

---

### Task 4: 컨트롤러 — 지금 곡 정보와 안내

**Files:**
- Modify: `funplayer/controller.py`
- Test: `tests/test_controller.py`

**Interfaces:**
- Consumes: Task 2 `TrackInfo`, `subtitle`; Task 3 `read_info`
- Produces:
  - `PlayerController(player, settings, rng=None, session_path=None, read_info=None)`. `session_path`는 Task 5에서 쓴다. 이 작업에서는 받아 두기만 한다.
  - `info: TrackInfo | None` (속성), `info_for(index: int) -> TrackInfo`, `subtitle: str` (속성), `notify(msg: str) -> None`

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`tests/test_controller.py` 끝에)

```python
from funplayer.core.taginfo import TrackInfo

def counting_reader(calls):
    def read(path):
        calls.append(path)
        return TrackInfo(path, artist="Band", album=os.path.basename(path))
    return read

def info_ctl(calls):
    return PlayerController(FakePlayer(), Settings({}, lambda: None), read_info=counting_reader(calls))

def test_info_follows_current_track_and_reads_once(tmp_path):
    calls = []; c = info_ctl(calls)
    assert c.info is None and c.subtitle == "" and calls == []
    c.open([str(make_songs(tmp_path, ABC))])
    assert c.subtitle == "Band · 01 a.mp3"; c.info; c.info
    assert len(calls) == 1
    c.next()
    assert c.info.album == "02 b.mp3" and len(calls) == 2

def test_info_for_other_row_keeps_current_cache(tmp_path):
    calls = []; c = info_ctl(calls); c.open([str(make_songs(tmp_path, ABC))]); c.info
    assert c.info_for(2).album == "03 c.mp3" and len(calls) == 2
    assert c.info.album == "01 a.mp3" and c.info_for(0).album == "01 a.mp3" and len(calls) == 2

def test_info_cleared_with_list(tmp_path):
    calls = []; c = info_ctl(calls); c.open([str(make_songs(tmp_path, ABC))]); c.clear()
    assert c.info is None and c.subtitle == ""

def test_default_reader_handles_empty_files(ctl, tmp_path):
    c, *_ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    assert c.info.path.endswith("01 a.mp3") and c.info.title == "" and c.subtitle == ""

def test_notify_sets_info_status(ctl):
    c, *_ = ctl; c.notify("안내")
    assert (c.status, c.status_error) == ("안내", False)
```

- [ ] **Step 2: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_controller.py -k "info or notify"`
Expected: FAIL (`TypeError: unexpected keyword argument 'read_info'`)

- [ ] **Step 3: 구현한다**

- 생성자: `self._read_info = read_info or engine.tags.read_info`, `self._session_path = session_path`, `self._info_cache: TrackInfo | None = None`.
- `info`: 지금 곡이 없으면 None이다. 캐시의 `path`가 지금 곡 경로와 다르면 읽어서 캐시를 바꾼다.
- `info_for(i)`: 경로가 캐시와 같으면 캐시를 돌려주고, 아니면 읽기만 한다(캐시는 그대로).
- `subtitle`은 `taginfo.subtitle(self.info)`다. `notify`는 `self._info(msg)`다.

- [ ] **Step 4: 실행해서 통과를 본다** — 전체 `tests/test_controller.py`, Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add funplayer/controller.py tests/test_controller.py
git commit -m "Expose current track info and subtitle from the controller"
```

---

### Task 5: 컨트롤러 — 이어 듣기

**Files:**
- Modify: `funplayer/controller.py`, `tests/fakes.py`
- Test: `tests/test_controller.py`

**Interfaces:**
- Consumes: Task 1 `Settings.last_track`, `last_position`; 2-A `read_playlist`, `write_playlist`; `core.timefmt.format_time`
- Produces:
  - 상수 `RESUME_MSG = "이어 듣기: {time}부터"`, `RESUME_TAIL = 5.0`
  - `cued: bool`, `can_seek: bool` (속성)
  - `save_session() -> None`, `restore_session() -> None`
  - `FakePlayer(missing_fails: bool = False)`

- [ ] **Step 1: `tests/fakes.py`의 `FakePlayer`에 `missing_fails`를 더한다**

`__init__(self, missing_fails: bool = False)`. 켜져 있고 `os.path.exists(path)`가 아니면 `load`는 "bad"와 같은 길로(경로를 `loaded`에 넣은 뒤) `DecodeError`를 낸다.

- [ ] **Step 2: 실패하는 테스트를 쓴다** (`tests/test_controller.py` 끝에)

```python
from funplayer.core.m3u import read_playlist, write_playlist

def session_ctl(tmp_path, store=None, **kw):
    store = {} if store is None else store
    fake = FakePlayer(**kw)
    c = PlayerController(fake, Settings(store, lambda: None), session_path=str(tmp_path / "last.m3u8"))
    return c, fake, store

def saved_session(tmp_path, names, last, position, **store_extra):
    songs = make_songs(tmp_path / "m", names)
    paths = [str(songs / n) for n in names]
    write_playlist(str(tmp_path / "last.m3u8"), paths)
    store = {"player_last_track": str(songs / last), "player_last_position": position, **store_extra}
    return store, paths

def test_save_then_restore_cues_without_playing(tmp_path):
    c, fake, store = session_ctl(tmp_path); c.open([str(make_songs(tmp_path / "m", ABC))]); c.next()
    fake.position = 72.0; c.save_session()
    assert store["player_last_track"].endswith("02 b.mp3") and store["player_last_position"] == 72.0
    c2, fake2, _ = session_ctl(tmp_path, store); c2.restore_session()
    assert [os.path.basename(t.path) for t in c2.playlist.tracks] == ABC and c2.playlist.index == 1
    assert fake2.state is State.STOPPED and names(fake2) == ["02 b.mp3"] and fake2.seeks == [72.0]
    assert c2.cued and c2.can_seek and (c2.status, c2.status_error) == ("이어 듣기: 1:12부터", False)
    c2.toggle()
    assert fake2.state is State.PLAYING and len(fake2.loaded) == 1 and fake2.position == 72.0 and not c2.cued

def test_stop_after_restore_goes_back_to_start(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session(); c.stop()
    assert not c.cued and not c.can_seek and fake.position == 0.0
    c.toggle()
    assert len(fake.loaded) == 2 and fake.state is State.PLAYING

def test_seek_allowed_while_cued(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    c.seek_to(30.0); c.seek_by(1)
    assert fake.seeks == [72.0, 30.0, 35.0] and c.cued

@pytest.mark.parametrize("pos", [0.0, 176.0])
def test_zero_or_near_end_position_starts_from_beginning(tmp_path, pos):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", pos)   # FakePlayer 길이 180초
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    assert fake.seeks == [] and c.status == "" and c.cued and c.playlist.index == 1

def test_last_track_not_in_list_uses_first_without_position(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    store["player_last_track"] = str(tmp_path / "elsewhere" / "x.mp3")
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    assert c.playlist.index == 0 and fake.seeks == [] and c.status == ""

def test_duplicate_paths_pick_first_row(tmp_path):
    songs = make_songs(tmp_path / "m", ABC); a = str(songs / "01 a.mp3")
    write_playlist(str(tmp_path / "last.m3u8"), [a, str(songs / "02 b.mp3"), a])
    c, _, _ = session_ctl(tmp_path, {"player_last_track": a, "player_last_position": 10.0})
    c.restore_session()
    assert c.playlist.index == 0

def test_unplayable_last_track_is_marked_and_not_cued(tmp_path):
    store, _ = saved_session(tmp_path, ["01 a.mp3", "02 bad.mp3"], "02 bad.mp3", 30.0)
    c, fake, _ = session_ctl(tmp_path, store); c.restore_session()
    assert c.playlist.index == 1 and c.playlist.tracks[1].failed and not c.cued
    assert c.status == "" and len(fake.loaded) == 1

def test_restore_with_all_files_missing_is_quiet(tmp_path):
    store, paths = saved_session(tmp_path, ABC, "02 b.mp3", 72.0)
    for p in paths:
        os.remove(p)
    c, fake, _ = session_ctl(tmp_path, store, missing_fails=True); c.restore_session()
    assert len(c.playlist) == 3 and all(t.missing for t in c.playlist.tracks)
    assert c.playlist.index == 1 and not c.cued and c.status == "" and len(fake.loaded) == 1

def test_shuffle_restore_starts_lap_at_last_track(tmp_path):
    store, _ = saved_session(tmp_path, ABC, "03 c.mp3", 0.0, player_shuffle=True)
    c, _, _ = session_ctl(tmp_path, store); c.restore_session()
    assert c.playlist.index == 2 and c.playlist.order[0] == 2

@pytest.mark.parametrize("make", ["none", "dir", "garbage"])
def test_missing_or_broken_session_file(tmp_path, make):
    target = tmp_path / "last.m3u8"
    if make == "dir":
        target.mkdir()
    elif make == "garbage":
        target.write_bytes(b"\x00\xff\xfe junk")
    c, fake, _ = session_ctl(tmp_path, {"player_last_track": "x", "player_last_position": 5.0})
    c.restore_session()
    assert len(c.playlist) == 0 and fake.loaded == [] and c.status == "" and not c.cued

def test_list_and_track_changes_are_saved(tmp_path):
    c, fake, store = session_ctl(tmp_path); f = str(tmp_path / "last.m3u8")
    c.open([str(make_songs(tmp_path / "m", ABC))])
    assert [os.path.basename(p) for p in read_playlist(f)] == ABC
    assert store["player_last_track"].endswith("01 a.mp3") and store["player_last_position"] == 0.0
    c.next(); assert store["player_last_track"].endswith("02 b.mp3")
    c.remove([0]); assert len(read_playlist(f)) == 2
    c.sort("name"); c.move([1], 0)
    assert read_playlist(f) == [t.path for t in c.playlist.tracks]
    c.add([str(make_songs(tmp_path / "n", ["09 z.mp3"]))]); assert len(read_playlist(f)) == 3
    c.clear()
    assert not os.path.exists(f) and store["player_last_track"] == "" and store["player_last_position"] == 0.0

@pytest.mark.parametrize("prep,want", [("play", 50.0), ("pause", 50.0), ("stop", 0.0)])
def test_save_session_position(tmp_path, prep, want):
    c, fake, store = session_ctl(tmp_path); c.open([str(make_songs(tmp_path / "m", ABC))])
    fake.position = 50.0
    if prep == "pause": c.toggle()
    if prep == "stop": c.stop()
    c.save_session()
    assert store["player_last_position"] == want

def test_no_session_path_writes_nothing(ctl, tmp_path):
    c, _, store = ctl; c.open([str(make_songs(tmp_path / "m", ABC))]); c.save_session(); c.restore_session()
    assert "player_last_track" not in store and not list(tmp_path.glob("*.m3u8"))

def test_session_write_failure_is_silent(tmp_path, monkeypatch):
    import funplayer.controller as ctrl
    def boom(*a): raise OSError("disk full")
    monkeypatch.setattr(ctrl, "write_playlist", boom)
    c, fake, _ = session_ctl(tmp_path); c.open([str(make_songs(tmp_path / "m", ABC))])
    assert fake.state is State.PLAYING and not c.status_error
```

- [ ] **Step 3: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_controller.py -k "session or restore or cued or saved or resume"`
Expected: FAIL (`AttributeError: ... 'restore_session'` 등)

- [ ] **Step 4: 구현한다** (`funplayer/controller.py`)

- **`self._cued = False`:**
  - `cued` 속성은 이 값이다.
  - `can_seek`는 `state is not State.STOPPED or (self._cued and self._player.duration > 0)`이다.
- **`toggle()`:** STOPPED이고 `_cued`면 `_cued = False` 뒤 `self._player.play()`만 한다. load하지 않는다.
- **`_cued = False`로 되돌리는 곳:** `play_index` 시작, `stop`, `clear`, `open`, 그리고 `remove`에서 결과가 `"kept"`가 아닐 때.
- **탐색 막기:** `seek_by`와 `seek_to`는 `state is STOPPED` 대신 `not self.can_seek`일 때 아무것도 하지 않는다.
- **`_remember(position: float = 0.0)`:**
  - `_session_path`가 없으면 아무것도 하지 않는다.
  - 목록이 비었으면 파일을 지우고(OSError는 무시), `last_track = ""`, `last_position = 0.0`이다.
  - 아니면 `write_playlist(session_path, 모든 경로)`를 한다. 실패하면(OSError·ValueError) warning 로그만 남긴다. 그다음 `last_track = 지금 곡 경로 or ""`, `last_position = position`이다.
  - `open`, `add`, `remove`, `sort`, `move`, `clear`, `play_index`(어떻게 끝나든)의 끝에서 부른다. `play_index`를 거치는 `next`·`prev`·곡 끝은 따로 부르지 않아도 된다.
- **`save_session()`:**
  - 위치는 `self._player.position`이다. 단 STOPPED이고 `_cued`가 아니면 0.0이다.
  - 그 위치로 `_remember(위치)`를 한다.
- **`restore_session()`** — 순서와 규칙:
  1. `_session_path`가 없거나 파일이 아니면 끝낸다.
  2. `read_playlist`에서 OSError·ValueError가 나면 warning 로그 뒤 끝낸다. 경로가 없으면 끝낸다.
  3. `self.playlist.replace(paths)` 뒤 `self._mark_missing(0)`을 한다.
  4. 지난 곡을 고른다. `os.path.normcase(os.path.abspath(p))`로 견주어 처음 맞는 줄이 `i`다. 없으면 `i = self.playlist.index`(첫 곡)이고 `position = 0.0`이다.
  5. `self.playlist.set_current(i)` 뒤 `self.playlist.set_shuffle(self.shuffle)`을 한다. 무작위면 이 곡이 바퀴의 처음이 된다.
  6. `self._player.load(path)`를 한다. `DecodeError`면 `play_index`와 같이 `mark_failed`나 `mark_missing`을 하고 끝낸다. 상태 문구는 쓰지 않는다.
  7. 성공하면 `mark_ok(i)`를 한다.
  8. `duration > 0`이고 `duration - position < RESUME_TAIL`이면 `position = 0.0`이다.
  9. `position > 0`이면 `seek(position)`을 하고, `self._info(RESUME_MSG.format(time=format_time(position)))`를 쓴다.
  10. `_cued = True`. 복원 중에는 `_remember`를 부르지 않는다.

- [ ] **Step 5: 실행해서 통과를 본다** — 전체 스위트, Expected: PASS

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`

- [ ] **Step 6: 커밋**

```bash
git add funplayer/controller.py tests/fakes.py tests/test_controller.py
git commit -m "Save and restore the list, track and position"
```

---

### Task 6: 아이콘과 앨범 그림

**Files:**
- Modify: `funplayer/ui/icons.py`
- Create: `funplayer/ui/cover.py`
- Test: `tests/test_icons.py`, `tests/test_cover.py`

**Interfaces:**
- Consumes: Task 2 `TrackInfo`, `pick_cover`
- Produces:
  - `icons.mini_icon(color: QColor) -> QIcon`, `icons.full_icon(color: QColor) -> QIcon`, `icons.note_art(size: int) -> QPixmap`(배율 1, 정확히 size×size)
  - `cover.load_cover(info: TrackInfo, max_size: int = 320) -> QPixmap | None`
  - `cover.art_pixmap(src: QPixmap | None, size: int) -> QPixmap`(정확히 size×size, 투명 바탕 가운데에 비율 맞춰 놓음. src가 None이면 `note_art(size)`)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/test_icons.py` 끝에:

```python
from funplayer.ui.icons import full_icon, mini_icon, note_art

def _has_ink(img):
    return any(img.pixelColor(x, y).alpha() > 0 for x in range(img.width()) for y in range(img.height()))

def test_mini_full_icons_and_note_art(qapp):
    for icon in (mini_icon(QColor("#5F6368")), full_icon(QColor("#5F6368"))):
        assert not icon.isNull() and _has_ink(icon.pixmap(18, 18).toImage())
    art = note_art(40)
    assert (art.width(), art.height(), art.devicePixelRatio()) == (40, 40, 1.0)
    assert art.toImage().pixelColor(20, 20).alpha() > 0
```

(`QColor`를 아직 import하지 않았다면 `from PyQt5.QtGui import QColor`를 더한다.)

`tests/test_cover.py`:

```python
from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QColor, QImage
from funplayer.core.taginfo import TrackInfo
from funplayer.ui.cover import art_pixmap, load_cover

RED, BLUE = QColor("#ff0000"), QColor("#0000ff")

def png(w, h, color):
    img = QImage(w, h, QImage.Format_ARGB32); img.fill(color)
    data = QByteArray(); buf = QBuffer(data); buf.open(QIODevice.WriteOnly); img.save(buf, "PNG")
    return bytes(data)

def center(pm):
    img = pm.toImage(); return img.pixelColor(img.width() // 2, img.height() // 2)

def test_tag_picture_wins_over_folder(qapp, tmp_path):
    (tmp_path / "cover.jpg").write_bytes(png(8, 8, BLUE))
    pm = load_cover(TrackInfo(str(tmp_path / "a.mp3"), picture=png(8, 8, RED)))
    assert center(pm) == RED

def test_folder_cover_when_no_tag_picture(qapp, tmp_path):
    (tmp_path / "Folder.PNG").write_bytes(png(8, 8, BLUE))
    assert center(load_cover(TrackInfo(str(tmp_path / "a.mp3"), album=""))) == BLUE

def test_album_named_image(qapp, tmp_path):
    (tmp_path / "Day By Day.jpg").write_bytes(png(8, 8, BLUE)); (tmp_path / "scan.jpg").write_bytes(png(8, 8, RED))
    assert center(load_cover(TrackInfo(str(tmp_path / "a.mp3"), album="Day By Day"))) == BLUE

def test_none_when_nothing(qapp, tmp_path):
    assert load_cover(TrackInfo(str(tmp_path / "a.mp3"))) is None
    assert load_cover(TrackInfo(str(tmp_path / "no" / "dir" / "a.mp3"))) is None

def test_corrupt_picture_falls_back(qapp, tmp_path):
    info = TrackInfo(str(tmp_path / "a.mp3"), picture=b"not an image")
    assert load_cover(info) is None
    (tmp_path / "cover.png").write_bytes(png(8, 8, BLUE))
    assert center(load_cover(info)) == BLUE
    (tmp_path / "cover.png").write_bytes(b"broken")
    assert load_cover(info) is None

def test_big_picture_scaled_down(qapp, tmp_path):
    pm = load_cover(TrackInfo(str(tmp_path / "a.mp3"), picture=png(2000, 1000, RED)))
    assert (pm.width(), pm.height()) == (320, 160)

def test_art_pixmap_letterboxes_and_falls_back(qapp, tmp_path):
    src = load_cover(TrackInfo(str(tmp_path / "a.mp3"), picture=png(320, 160, RED)))
    pm = art_pixmap(src, 56); img = pm.toImage()
    assert (pm.width(), pm.height()) == (56, 56)
    assert img.pixelColor(28, 28) == RED and img.pixelColor(28, 2).alpha() == 0
    note = art_pixmap(None, 40)
    assert (note.width(), note.height()) == (40, 40)
```

- [ ] **Step 2: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_icons.py tests/test_cover.py`
Expected: FAIL (ImportError)

- [ ] **Step 3: `icons.py`에 세 함수를 더한다** — 승인된 시안의 모양이다. 18 단위 좌표, `_begin(color)`을 쓴다.
  - `mini_icon`:
    - 테두리 `drawRoundedRect(QRectF(2.5, 3.5, 13, 11), 1.5, 1.5)`
    - 펜 없이 `color` 채움 `drawRoundedRect(QRectF(8.6, 8.8, 5.4, 4.2), 0.8, 0.8)`
  - `full_icon`: `drawRoundedRect(QRectF(3.5, 2.5, 11, 13), 1.5, 1.5)`와 `drawLine(QPointF(3.5, 6), QPointF(14.5, 6))`.
  - `note_art(size)`:
    - 배율 1, `size×size`, 투명 바탕이다.
    - `#E3E6EA` 둥근 사각형(반지름 `size*0.08`).
    - `s = size/56`일 때 `#9AA1AB`로 그린다:
      - 타원 `QRectF(17s, 33s, 11s, 9s)`, `QRectF(31s, 29s, 11s, 9s)`
      - 굵기 `2.6s`, FlatCap 선 `(27s,37s)→(27s,16s)→(41s,12s)→(41s,33s)`
- [ ] **Step 4: `funplayer/ui/cover.py`를 만든다**
  - `load_cover`:
    1. `info.picture`가 있으면 `QImage.fromData`로 연다.
    2. 그림이 없거나 열리지 않으면 폴더로 간다: `os.listdir(dirname(info.path))`(OSError면 `[]`), `pick_cover(names, info.album)`. 고른 파일을 `QImage(path)`로 연다.
    3. 열린 그림이 없으면 None이다.
    4. 긴 변이 `max_size`보다 크면 `scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)`이다.
    5. `QPixmap.fromImage`를 돌려준다.
  - `art_pixmap`:
    - 투명 `size×size` QPixmap에 `src.scaled(size, size, KeepAspectRatio, SmoothTransformation)`을 가운데에 그린다.
    - src가 None이면 `note_art(size)`다.
- [ ] **Step 5: 실행해서 통과를 본다** — 위 명령, Expected: PASS
- [ ] **Step 6: 커밋**

```bash
git add funplayer/ui/icons.py funplayer/ui/cover.py tests/test_icons.py tests/test_cover.py
git commit -m "Add mini/full icons, default art and album cover loading"
```

---

### Task 7: 패널 머리 줄과 이어 듣기 연결

**Files:**
- Modify: `funplayer/ui/player_panel.py`
- Test: `tests/test_panel_view.py`

**Interfaces:**
- Consumes:
  - Task 4 `controller.info`, `subtitle`
  - Task 5 `restore_session`, `save_session`, `can_seek`
  - Task 6 `load_cover`, `art_pixmap`
- Produces:
  - `PlayerPanel(settings, player=None, parent=None, *, session_path=None, read_info=None)`
  - 속성: `art_label`(56×56, 풍선 도움말 `곡 정보`, `clicked` 신호), `artist_label`, `head_row`(QHBoxLayout: 그림, 제목 묶음), 상수 `ART_NORMAL = 56`, `ART_MINI = 40`

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`tests/test_panel_view.py` 끝에)

```python
from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QImage
from funplayer.core.m3u import write_playlist
from funplayer.core.taginfo import TrackInfo

def red_png():
    img = QImage(8, 8, QImage.Format_ARGB32); img.fill(QColor("#ff0000"))
    data = QByteArray(); buf = QBuffer(data); buf.open(QIODevice.WriteOnly); img.save(buf, "PNG")
    return bytes(data)

def test_header_shows_subtitle_and_tag_art(qapp, tmp_path):
    reader = lambda path: TrackInfo(path, artist="Lo-Fi Band", album="Sunday Mornings", picture=red_png())
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), read_info=reader)
    try:
        p.controller.open([str(make_songs(tmp_path, ["01 a.mp3"]))]); p.refresh()
        assert p.artist_label.toolTip() == "Lo-Fi Band · Sunday Mornings"
        assert p.art_label.toolTip() == "곡 정보" and p.art_label.width() == 56
        assert p.art_label.pixmap().toImage().pixelColor(28, 28) == QColor("#ff0000")
    finally:
        p.shutdown(); p.deleteLater()

def test_default_art_and_empty_subtitle(panel):
    p, _ = panel
    pm = p.art_label.pixmap()
    assert pm is not None and (pm.width(), pm.height()) == (56, 56) and p.artist_label.text() == ""

def test_cover_loaded_once_per_track(qapp, tmp_path, monkeypatch):
    import funplayer.ui.player_panel as pp
    calls = []; real = pp.load_cover
    monkeypatch.setattr(pp, "load_cover", lambda info, *a: calls.append(info.path) or real(info, *a))
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer())
    try:
        p.controller.open([str(make_songs(tmp_path, ABC))]); p.refresh(); p.refresh(); p.refresh()
        assert len(calls) == 1
        p.controller.next(); p.refresh()
        assert len(calls) == 2
    finally:
        p.shutdown(); p.deleteLater()

def test_panel_restores_cued_session_and_saves_on_shutdown(qapp, tmp_path):
    songs = make_songs(tmp_path / "m", ["01 a.mp3", "03 c.mp3"])
    write_playlist(str(tmp_path / "last.m3u8"), [str(songs / "01 a.mp3"), str(songs / "03 c.mp3")])
    store = {"player_last_track": str(songs / "03 c.mp3"), "player_last_position": 72.0}
    fake = FakePlayer()
    p = PlayerPanel(Settings(store, lambda: None), player=fake, session_path=str(tmp_path / "last.m3u8"))
    p.refresh()
    assert p.controller.playlist.index == 1 and p.seek_slider.isEnabled()
    assert p.elapsed_label.text() == "1:12" and p.play_button.toolTip() == "재생"
    assert p.status_label.toolTip() == "이어 듣기: 1:12부터"
    fake.position = 80.0; p.shutdown(); p.deleteLater()
    assert store["player_last_position"] == 80.0
```

- [ ] **Step 2: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_panel_view.py`
Expected: FAIL

- [ ] **Step 3: 구현한다**
  - **생성자:**
    - `session_path`와 `read_info`를 컨트롤러에 넘긴다.
    - `session_path`가 있으면 `_build()` 뒤 첫 `refresh()` 전에 `self.controller.restore_session()`을 한다.
  - **머리 줄:** 1·2-A의 `title_label`을 `self.head_row`(QHBoxLayout, 간격 10)로 감싼다.
    - 맨 앞은 `art_label`이다. 작은 QLabel 하위 클래스 `_ArtLabel`이고 `clicked = pyqtSignal()`을 왼쪽 누름에 낸다. `setFixedSize(56, 56)`, 풍선 도움말 `곡 정보`.
    - 다음은 제목 묶음(QVBoxLayout, 간격 0)이다. `title_label`과 그 아래 `artist_label`이 들어가고, `artist_label`은 `color: {INFO_COLOR}`에 `QSizePolicy.Ignored`다. 묶음의 stretch는 1이다.
    - 그림은 `Qt.AlignTop`이다.
  - **`refresh()`:**
    - `self._set_elided(self.artist_label, c.subtitle)`를 한다.
    - 그림 열쇠(지금 곡 경로 또는 None)가 바뀌었을 때만 다시 그린다. `self._cover_src = load_cover(c.info) if c.info else None` 뒤 `art_label.setPixmap(art_pixmap(self._cover_src, self.art_label.width()))`다.
    - 열쇠의 처음 값은 어떤 경로와도 다른 표지(`object()`)로 둔다. 그래야 첫 `refresh()`에서 기본 그림이 그려진다.
    - `load_cover`는 모듈 전역 이름으로 부른다. 테스트가 `funplayer.ui.player_panel.load_cover`를 바꿔 끼운다.
    - 탐색바는 `seek.setEnabled(c.can_seek and duration > 0)`이다.
  - **`shutdown()`:** 맨 앞에서 `self.controller.save_session()`을 한다.
- [ ] **Step 4: 실행해서 통과를 본다** — 전체 스위트, Expected: PASS
- [ ] **Step 5: 커밋**

```bash
git add funplayer/ui/player_panel.py tests/test_panel_view.py
git commit -m "Show album art and artist line; resume the last session in the panel"
```

---

### Task 8: 곡 정보 창과 여는 길

**Files:**
- Create: `funplayer/ui/info_dialog.py`
- Modify: `funplayer/ui/player_panel.py`
- Test: `tests/test_info_dialog.py`, `tests/test_panel_input.py`

**Interfaces:**
- Consumes:
  - Task 2 `format_line`, `format_size`
  - Task 4 `info_for`
  - Task 6 `load_cover`, `art_pixmap`
  - `core.timefmt.format_time`
- Produces:
  - `info_dialog.reveal_in_explorer(path: str) -> None`
  - `TrackInfoDialog(parent=None)`: `show_info(info: TrackInfo, cover: QPixmap | None) -> None`, 속성 `value_labels: dict[str, QLabel]`(키는 칸 이름), `path_label`, `folder_button`, `close_button`
  - 패널: `view_button`(`보기`), `view_menu`, `info_dialog: TrackInfoDialog | None`, `show_track_info() -> None`(지금 곡, 없으면 고른 줄), `show_row_info() -> None`(고른 줄), 단축키 `("Ctrl+I", "show_track_info")`, actions `"info"`, `"info_row"`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/test_info_dialog.py`:

```python
import os
from PyQt5.QtCore import Qt
import funplayer.ui.info_dialog as dlg
from funplayer.core.taginfo import TrackInfo
from funplayer.ui.info_dialog import TrackInfoDialog

KEYS = ["제목", "가수", "앨범", "년도", "장르", "트랙", "길이", "형식", "크기"]

def test_fields(qapp, tmp_path):
    f = tmp_path / "x.mp3"; f.write_bytes(b"1")
    d = TrackInfoDialog()
    d.show_info(TrackInfo(str(f), title="Morning Coffee", artist="Lo-Fi Band", year="2019", track="3/12",
                          duration=225, codec="mp3float", bitrate=192000, sample_rate=44100, channels=2,
                          size=5_452_595), None)
    v = d.value_labels
    assert d.windowTitle() == "곡 정보" and list(v) == KEYS
    assert [v[k].text() for k in KEYS] == ["Morning Coffee", "Lo-Fi Band", "—", "2019", "—", "3/12",
                                           "3:45", "MP3 · 192 kbps · 44.1 kHz · 스테레오", "5.2 MB"]
    assert d.path_label.text() == str(f) and d.folder_button.isEnabled()
    assert (d.folder_button.text(), d.close_button.text()) == ("폴더 열기", "닫기")
    assert all(l.textInteractionFlags() & Qt.TextSelectableByMouse for l in [*v.values(), d.path_label])

def test_empty_info_shows_dashes(qapp, tmp_path):
    d = TrackInfoDialog(); d.show_info(TrackInfo(str(tmp_path / "gone" / "x.mp3")), None)
    assert all(d.value_labels[k].text() == "—" for k in KEYS) and not d.folder_button.isEnabled()

def test_folder_button_calls_reveal(qapp, tmp_path, monkeypatch):
    calls = []; monkeypatch.setattr(dlg, "reveal_in_explorer", calls.append)
    f = tmp_path / "x.mp3"; f.write_bytes(b"1")
    d = TrackInfoDialog(); d.show_info(TrackInfo(str(f)), None); d.folder_button.click()
    assert calls == [str(f)]

def test_reveal_in_explorer_commands(tmp_path, monkeypatch):
    runs, starts = [], []
    monkeypatch.setattr(dlg.subprocess, "Popen", lambda args, **kw: runs.append(args))
    monkeypatch.setattr(dlg.os, "startfile", starts.append, raising=False)
    f = tmp_path / "x.mp3"; f.write_bytes(b"1")
    dlg.reveal_in_explorer(str(f))
    dlg.reveal_in_explorer(str(tmp_path / "gone.mp3"))
    dlg.reveal_in_explorer(str(tmp_path / "no" / "dir" / "x.mp3"))
    assert runs == [["explorer", "/select,", os.path.normpath(str(f))]] and starts == [str(tmp_path)]
    def boom(*a, **k): raise OSError("no explorer")
    monkeypatch.setattr(dlg.subprocess, "Popen", boom)
    dlg.reveal_in_explorer(str(f))   # 예외가 나오지 않는다
```

`tests/test_panel_input.py` — 바꿀 것과 더할 것:
- `test_shortcut_table`의 집합에 `"Ctrl+I"`를 더한다.
- `test_context_menu`의 목록을 `["재생\tEnter", "곡 정보…", "선택한 곡 지우기\tDel", "", "전체 선택\tCtrl+A"]`로 바꾼다.
- 다음 테스트를 더한다.

```python
def test_ctrl_i_opens_current_and_reuses_dialog(rig):
    p, *_ = rig
    p.shortcuts["Ctrl+I"].activated.emit(); d = p.info_dialog
    assert d.isVisible() and d.path_label.text().endswith("01 a.mp3")
    p.art_label.clicked.emit()
    assert p.info_dialog is d

def test_context_info_uses_row_and_does_not_follow(rig):
    p, *_ = rig
    p.playlist_view.setCurrentRow(2); p.context_menu.aboutToShow.emit()
    assert p.actions["info_row"].isEnabled()
    p.actions["info_row"].trigger()
    assert p.info_dialog.path_label.text().endswith("03 c.mp3")
    p.next(); assert p.info_dialog.path_label.text().endswith("03 c.mp3")

def test_view_button_and_info_action(rig):
    p, *_ = rig
    assert p.view_button.text() == "보기" and [a.text() for a in p.view_menu.actions()] == ["곡 정보…\tCtrl+I"]
    p.controller.clear(); p.refresh(); p.playlist_view.setCurrentRow(-1); p.view_menu.aboutToShow.emit()
    assert not p.actions["info"].isEnabled()
```

- [ ] **Step 2: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_info_dialog.py tests/test_panel_input.py`
Expected: FAIL

- [ ] **Step 3: `funplayer/ui/info_dialog.py`를 만든다**
  - **`reveal_in_explorer(path)`:**
    - 파일이 있으면 `subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])`를 한다.
    - 파일이 없고 폴더가 있으면 `os.startfile(폴더)`를 한다.
    - 둘 다 없으면 아무것도 하지 않는다.
    - OSError는 warning 로그만 남긴다.
  - **`TrackInfoDialog(QDialog)`:**
    - 모달이 아니다.
    - 왼쪽 160×160 그림 QLabel에 `art_pixmap(cover, 160)`을 둔다.
    - 오른쪽 QGridLayout에 회색 칸 이름과 값 QLabel을 둔다. 값은 `TextSelectableByMouse`다.
    - 그 아래 `경로` 줄(값도 고를 수 있음), 단추 줄 `[폴더 열기] [닫기]`가 온다. `닫기`는 기본 단추이고 `close()`다.
  - **값:**
    - 글자 칸은 비었으면 `—`다.
    - `길이`는 `duration > 0`이면 `format_time`, 아니면 `—`다.
    - `형식`·`크기`는 비었으면 `—`다.
  - **`folder_button`:** 파일이나 그 폴더가 있을 때만 켠다. 누르면 모듈 함수 `reveal_in_explorer`를 부른다(테스트가 바꿔 끼울 수 있게 모듈 이름으로 찾는다).
- [ ] **Step 4: 패널을 고친다**
  - **아래 줄:** `열기` `추가` `목록` 뒤에 `self.view_button = QPushButton("보기")`를 둔다. 메뉴는 `self.view_menu`다.
  - **`view_menu`:** `_add_action(view_menu, "info", "곡 정보…\tCtrl+I", self.show_track_info)`. `aboutToShow`에 `_update_actions`를 연결한다.
  - **오른쪽 클릭 메뉴:** `재생` 다음에 `info_row`(`곡 정보…`, `self.show_row_info`)를 넣는다.
  - **`_update_actions`:**
    - `info`는 지금 곡이 있거나 고른 줄이 있을 때 켠다.
    - `info_row`는 `currentRow() >= 0`일 때 켠다.
  - **`show_track_info()`:** `controller.playlist.index`를 쓰고, None이면 `playlist_view.currentRow()`(0 이상일 때)를 쓴다. 둘 다 없으면 아무것도 하지 않는다.
  - **`show_row_info()`:** `currentRow()`를 쓴다.
  - **창 띄우기(공통):**
    - 창은 하나만 만들어 다시 쓴다: `self.info_dialog = self.info_dialog or TrackInfoDialog(self)`.
    - `info = controller.info_for(i)` 뒤 `show_info(info, load_cover(info))`, `show()`, `raise_()`, `activateWindow()`를 한다.
  - **연결과 단축키:** `art_label.clicked`를 `show_track_info`에 잇는다. `SHORTCUTS`에 `("Ctrl+I", "show_track_info")`를 더한다.
- [ ] **Step 5: 실행해서 통과를 본다** — 전체 스위트, Expected: PASS
- [ ] **Step 6: 커밋**

```bash
git add funplayer/ui/info_dialog.py funplayer/ui/player_panel.py tests/test_info_dialog.py tests/test_panel_input.py
git commit -m "Add the track info dialog with Ctrl+I, art click and context menu"
```

---

### Task 9: 작게 보기 (패널)

**Files:**
- Modify: `funplayer/ui/player_panel.py`
- Test: `tests/test_panel_input.py`

**Interfaces:**
- Consumes:
  - Task 1 `Settings.mini`, `mini_on_top`
  - Task 6 `mini_icon`, `full_icon`
  - Task 7 `head_row`, `art_label`
- Produces:
  - 신호 `miniChanged = pyqtSignal(bool)`, `miniOnTopChanged = pyqtSignal(bool)`
  - `mini_button`(26×26, 아이콘 18), `is_mini: bool` (속성), `set_mini(on: bool) -> None`, `toggle_mini() -> None`
  - 속성 `control_row`(재생 단추 줄 QHBoxLayout), `separator`(가로 선 QFrame)
  - 단축키 `("Ctrl+M", "toggle_mini")`, actions `"mini"`, `"mini_on_top"`

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`tests/test_panel_input.py`)

`test_shortcut_table`의 집합에 `"Ctrl+M"`를 더한다. 그리고:

```python
HIDDEN_IN_MINI = ("elapsed_label", "total_label", "stop_button", "repeat_button", "shuffle_button",
                  "mute_button", "volume_slider", "separator", "playlist_view", "open_button",
                  "add_button", "list_button", "view_button", "count_label", "status_label")
SHOWN_IN_MINI = ("art_label", "title_label", "artist_label", "prev_button", "play_button",
                 "next_button", "seek_slider", "mini_button")

def test_set_mini_hides_moves_and_restores(rig):
    p, _, store, _ = rig; seen = []; p.miniChanged.connect(seen.append)
    assert p.mini_button.toolTip() == "작게 보기"
    p.set_mini(True)
    assert p.is_mini and store["player_mini"] is True and seen == [True]
    assert not any(getattr(p, n).isVisible() for n in HIDDEN_IN_MINI)
    assert all(getattr(p, n).isVisible() for n in SHOWN_IN_MINI)
    assert p.art_label.width() == 40 and p.mini_button.toolTip() == "보통 보기"
    assert all(p.head_row.indexOf(b) >= 0 for b in (p.prev_button, p.play_button, p.next_button))
    p.set_mini(True); assert seen == [True]
    p.set_mini(False)
    assert not p.is_mini and store["player_mini"] is False and seen == [True, False]
    assert all(getattr(p, n).isVisible() for n in HIDDEN_IN_MINI)
    assert p.art_label.width() == 56 and p.mini_button.toolTip() == "작게 보기"
    assert [p.control_row.indexOf(b) for b in
            (p.prev_button, p.play_button, p.stop_button, p.next_button)] == [0, 1, 2, 3]

def test_mini_is_short(rig):
    p, *_ = rig; p.set_mini(True)
    assert p.sizeHint().height() < 130

def test_mini_toggles_by_key_button_and_title_double_click(rig):
    p, *_ = rig
    QTest.mouseDClick(p.title_label, Qt.LeftButton); assert not p.is_mini
    p.shortcuts["Ctrl+M"].activated.emit(); assert p.is_mini
    QTest.mouseDClick(p.title_label, Qt.LeftButton); assert not p.is_mini
    p.mini_button.click(); assert p.is_mini
    p.mini_button.click(); assert not p.is_mini

def test_view_menu_mini_items(rig):
    p, _, store, _ = rig; seen = []; p.miniOnTopChanged.connect(seen.append)
    assert [a.text() for a in p.view_menu.actions()] == [
        "곡 정보…\tCtrl+I", "작게 보기\tCtrl+M", "", "작게 볼 때 항상 위"]
    p.view_menu.aboutToShow.emit()
    assert not p.actions["mini"].isChecked() and p.actions["mini_on_top"].isChecked()
    p.actions["mini"].trigger(); assert p.is_mini
    p.view_menu.aboutToShow.emit(); assert p.actions["mini"].isChecked()
    p.actions["mini_on_top"].trigger()
    assert store["player_mini_on_top"] is False and seen == [False]

def test_shortcuts_still_work_in_mini(rig):
    p, fake, *_ = rig; p.set_mini(True)
    p.shortcuts["Space"].activated.emit()
    assert fake.state is State.PAUSED
```

- [ ] **Step 2: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_panel_input.py`
Expected: FAIL

- [ ] **Step 3: 구현한다**
  - **이름 붙이기:** `_build`의 가로 선을 `self.separator`로, 재생 단추 줄을 `self.control_row`로 둔다.
  - **`mini_button`:**
    - `head_row` 맨 끝에 `Qt.AlignTop`으로 둔다.
    - `QToolButton` 26×26, 아이콘 18이다. 아이콘은 `mini_icon(OFF_COLOR)` / `full_icon(OFF_COLOR)`이다.
    - 누르면 `toggle_mini`다.
  - **`set_mini(on)`:**
    1. 지금과 같으면 아무것도 하지 않는다.
    2. on이면 `prev_button`, `play_button`, `next_button`을 이 순서로 `head_row`의 `mini_button` 앞에 `insertWidget`한다. off면 `control_row`의 0, 1, 3번 자리로 되돌린다(정지 단추는 2번).
    3. `HIDDEN_IN_MINI`의 위젯을 숨기거나 보인다.
    4. 그림 크기 `ART_MINI`/`ART_NORMAL`을 `setFixedSize`하고 그림을 다시 그린다.
    5. 제목 글꼴을 10/12pt로 한다.
    6. 단추 아이콘과 풍선 도움말을 바꾼다.
    7. `settings.mini = on`, `self.miniChanged.emit(on)`.
  - **제목 두 번 클릭:** `title_label`에 이벤트 필터를 달아, 작게 볼 때만 `MouseButtonDblClick`에서 `set_mini(False)`를 한다.
  - **`view_menu`에 더하기:**
    - `"mini"`(`작게 보기\tCtrl+M`, 체크 가능, `toggle_mini`)
    - 구분선
    - `"mini_on_top"`(`작게 볼 때 항상 위`, 체크 가능): 누르면 `checked = self.actions["mini_on_top"].isChecked()`, `settings.mini_on_top = checked`, `miniOnTopChanged.emit(checked)`.
    - 두 체크 상태는 액션을 만들 때 설정값으로 맞춘다. `_update_actions`와 `set_mini`에서도 다시 맞춘다. 처음 상태가 틀리면 첫 클릭이 거꾸로 동작한다.
  - **단축키:** `SHORTCUTS`에 `("Ctrl+M", "toggle_mini")`를 더한다.
  - **패널은 생성자에서 `settings.mini`를 적용하지 않는다**(계획 결정 8).
- [ ] **Step 4: 실행해서 통과를 본다** — 전체 스위트, Expected: PASS
- [ ] **Step 5: 커밋**

```bash
git add funplayer/ui/player_panel.py tests/test_panel_input.py
git commit -m "Add mini mode to the panel"
```

---

### Task 10: 창 지키미와 실행 진입점

**Files:**
- Create: `funplayer/ui/window_keeper.py`
- Modify: `funplayer/__main__.py`
- Test: `tests/test_window_keeper.py`, `tests/test_main.py`

**Interfaces:**
- Consumes:
  - Task 1 `geometry`, `mini_geometry`, `mini`, `mini_on_top`
  - Task 7 `PlayerPanel(..., session_path=...)`
  - Task 9 `set_mini`, `is_mini`, `miniChanged`, `miniOnTopChanged`
- Produces: `WindowKeeper(panel: PlayerPanel, settings: Settings)` with `start() -> None`, `save() -> None`; 상수 `DEFAULT_SIZE = (380, 480)`

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`tests/test_window_keeper.py`)

```python
import pytest
from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtGui import QGuiApplication
from fakes import FakePlayer
from funplayer.core.settings import Settings
from funplayer.ui.player_panel import PlayerPanel
from funplayer.ui.window_keeper import WindowKeeper

@pytest.fixture
def make(qapp):
    made = []
    def build(store):
        s = Settings(store, lambda: None)
        p = PlayerPanel(s, player=FakePlayer()); k = WindowKeeper(p, s); k.start()
        made.append(p); return p, k
    yield build
    for p in made:
        p.shutdown(); p.deleteLater()

on_top = lambda p: bool(p.windowFlags() & Qt.WindowStaysOnTopHint)

def test_first_start_uses_default_size(make):
    p, _ = make({})
    assert p.size() == QSize(380, 480) and not p.is_mini and not on_top(p)

def test_restores_saved_normal_geometry(make):
    p, _ = make({"player_geometry": [50, 60, 400, 500]})
    assert p.geometry() == QRect(50, 60, 400, 500)

def test_offscreen_geometry_is_centered(make):
    p, _ = make({"player_geometry": [5000, 5000, 380, 480]})
    assert QGuiApplication.screenAt(p.geometry().center()) is not None and p.size() == QSize(380, 480)

def test_starts_in_mini_on_top_at_saved_place(make):
    p, _ = make({"player_mini": True, "player_mini_geometry": [30, 40, 380, 92]})
    assert p.is_mini and on_top(p) and (p.x(), p.y(), p.width()) == (30, 40, 380)
    assert p.minimumHeight() == p.maximumHeight() == p.sizeHint().height()

def test_toggle_saves_each_mode_and_restores_other(make):
    store = {"player_geometry": [50, 60, 400, 500]}; p, _ = make(store)
    p.set_mini(True)
    assert store["player_geometry"] == [50, 60, 400, 500] and on_top(p)
    p.move(70, 80); p.set_mini(False)
    assert store["player_mini_geometry"][:2] == [70, 80] and p.geometry() == QRect(50, 60, 400, 500)
    assert not on_top(p) and p.maximumHeight() == 16777215

def test_on_top_option(make):
    p, _ = make({"player_mini": True}); assert on_top(p)
    p.actions["mini_on_top"].trigger(); assert p.is_mini and not on_top(p)
    p.actions["mini_on_top"].trigger(); assert on_top(p)
    p.set_mini(False); assert not on_top(p)

def test_save_writes_current_mode(make):
    store = {}; p, k = make(store); p.setGeometry(20, 30, 390, 470); k.save()
    assert store["player_geometry"] == [20, 30, 390, 470]
```

`tests/test_main.py`의 `test_main_smoke` 끝에 다음 확인을 더한다.

```python
        import json
        data = json.loads((tmp_path / "my-fun" / "settings.json").read_text(encoding="utf-8"))
        assert data["player_geometry"][2:] == [380, 480]
```

- [ ] **Step 2: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_window_keeper.py tests/test_main.py`
Expected: FAIL (`ModuleNotFoundError: funplayer.ui.window_keeper`)

- [ ] **Step 3: `funplayer/ui/window_keeper.py`를 만든다** — `QObject` 하위 클래스이고, 창은 `panel` 자신(최상위)이다.
  - **`start()`:**
    1. `settings.mini`면 `panel.set_mini(True)`를 한다. 이때 이미 저장된 값이라 다시 써도 같다.
    2. 지금 모양의 위치·크기를 적용한다(아래 `_apply`).
    3. 항상 위를 적용한다.
    4. 그다음에 `miniChanged` → `_on_mini`, `miniOnTopChanged` → `_apply_on_top`을 연결한다.
  - **`_apply(mini)`:**
    - 보통 보기:
      1. `setMinimumHeight(0)`, `setMaximumHeight(16777215)`를 한다.
      2. 저장된 `geometry`가 있으면 그것을 쓰고, 없으면 `DEFAULT_SIZE`를 주 화면 가운데에 둔다.
    - 작게 보기:
      1. `setFixedHeight(panel.sizeHint().height())`를 한다.
      2. 저장된 `mini_geometry`가 있으면 x·y·폭을 쓰고, 없으면 지금 x·y·폭을 쓴다.
    - 화면 밖이면 가운데로: 놓을 사각형의 중심에 대해 `QGuiApplication.screenAt(...)`이 None이면, 크기는 지키고 주 화면 `availableGeometry()`의 가운데로 옮긴다.
  - **`_on_mini(on)`:**
    1. 바뀌기 전 모양의 `[x, y, w, h]`(`panel.geometry()`)를 그 모양의 키에 저장한다.
    2. `_apply(on)`을 한다.
    3. 항상 위를 다시 적용한다.
  - **항상 위:**
    - 원하는 값은 `panel.is_mini and settings.mini_on_top`이다.
    - 지금 플래그와 다를 때만 바꾼다: `was = panel.isVisible()`, `panel.setWindowFlag(Qt.WindowStaysOnTopHint, 값)`, `was`면 `panel.show()`.
  - **`save()`:** 지금 모양의 키에 `[x, y, w, h]`를 저장한다.
- [ ] **Step 4: `funplayer/__main__.py`를 고친다**
  - `PlayerPanel(settings, session_path=str(app_dir() / "last.m3u8"))`로 만든다.
  - `panel.resize(380, 480)`를 지운다.
  - `keeper = WindowKeeper(panel, settings); keeper.start(); panel.show()`
  - `code = app.exec_()` 뒤 `keeper.save()`, 그다음 `panel.shutdown()`이다.
- [ ] **Step 5: 실행해서 통과를 본다** — 전체 스위트, Expected: PASS
- [ ] **Step 6: 커밋**

```bash
git add funplayer/ui/window_keeper.py funplayer/__main__.py tests/test_window_keeper.py tests/test_main.py
git commit -m "Keep window place per mode and stay on top in mini mode"
```

---

### Task 11: 멀티미디어 키

**Files:**
- Create: `funplayer/ui/media_keys.py`
- Modify: `funplayer/ui/player_panel.py`, `funplayer/__main__.py`, `tests/fakes.py`
- Test: `tests/test_media_keys.py`, `tests/test_panel_input.py`, `tests/test_main.py`

**Interfaces:**
- Consumes:
  - Task 1 `Settings.media_keys`
  - Task 4 `controller.notify`
  - Task 8 `view_menu`
- Produces:
  - 상수 `WM_HOTKEY = 0x0312`, `MOD_NOREPEAT = 0x4000`, `HOTKEY_ID_BASE = 0xA000`, `KEYS = {0xB3: "play_pause", 0xB0: "next", 0xB1: "prev", 0xB2: "stop"}`, `MEDIA_KEYS_BUSY_MSG = "멀티미디어 키를 다른 프로그램이 쓰고 있습니다"`
  - `Win32HotkeyApi`: `register(hotkey_id: int, vk: int) -> bool`, `unregister(hotkey_id: int) -> None`
  - `default_api() -> Win32HotkeyApi | None`
  - `MediaKeys(parent=None, api=None)`:
    - 신호 `play_pause_pressed`, `next_pressed`, `prev_pressed`, `stop_pressed`
    - `enable() -> bool`, `disable() -> None`, `enabled: bool`, `handle_hotkey(hotkey_id: int) -> bool`
  - 패널: `PlayerPanel(..., media_keys=None)`, `media_keys`, `media_shortcuts: list[QShortcut]`, `set_media_keys(on: bool) -> None`, action `"media_keys"`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/fakes.py` 끝에 가짜 Windows API를 더한다(이대로):

```python
class FakeApi:
    """MediaKeys용 가짜 단축키 API: busy에 든 가상 키는 등록에 실패한다."""

    def __init__(self, busy=()):
        self.busy, self.registered, self.calls = set(busy), {}, []

    def register(self, hid: int, vk: int) -> bool:
        self.calls.append(("reg", hid, vk))
        ok = vk not in self.busy
        if ok:
            self.registered[hid] = vk
        return ok

    def unregister(self, hid: int) -> None:
        self.calls.append(("unreg", hid))
        self.registered.pop(hid, None)
```

`tests/test_media_keys.py`:

```python
import ctypes, sys
import pytest
from PyQt5.QtWidgets import QApplication
from fakes import FakeApi
from funplayer.ui.media_keys import HOTKEY_ID_BASE, WM_HOTKEY, MediaKeys

def test_enable_registers_four_keys_once(qapp):
    api = FakeApi(); k = MediaKeys(api=api)
    assert k.enable() and k.enabled
    assert api.registered == {HOTKEY_ID_BASE + vk: vk for vk in (0xB3, 0xB0, 0xB1, 0xB2)}
    k.enable(); assert len(api.calls) == 4
    k.disable()

def test_busy_key_returns_false_and_keeps_others(qapp):
    api = FakeApi(busy={0xB3}); k = MediaKeys(api=api)
    assert k.enable() is False and set(api.registered.values()) == {0xB0, 0xB1, 0xB2}
    k.disable(); assert api.registered == {}

def test_disable_unregisters_and_is_idempotent(qapp):
    api = FakeApi(); k = MediaKeys(api=api); k.enable(); k.disable(); k.disable()
    assert api.registered == {} and not k.enabled

def test_handle_hotkey_emits(qapp):
    k = MediaKeys(api=FakeApi()); k.enable(); hits = []
    for name in ("play_pause", "next", "prev", "stop"):
        getattr(k, f"{name}_pressed").connect(lambda n=name: hits.append(n))
    for vk in (0xB3, 0xB0, 0xB1, 0xB2):
        assert k.handle_hotkey(HOTKEY_ID_BASE + vk)
    assert hits == ["play_pause", "next", "prev", "stop"] and not k.handle_hotkey(1)
    k.disable(); assert not k.handle_hotkey(HOTKEY_ID_BASE + 0xB3)

def test_no_api_is_noop(qapp):
    k = MediaKeys()
    assert k.enable() is True and not k.handle_hotkey(HOTKEY_ID_BASE + 0xB3)
    k.disable()

@pytest.mark.skipif(sys.platform != "win32", reason="Windows 메시지")
def test_native_filter_routes_thread_hotkey(qapp):
    k = MediaKeys(api=FakeApi()); k.enable(); hits = []
    k.play_pause_pressed.connect(lambda: hits.append(1))
    tid = ctypes.windll.kernel32.GetCurrentThreadId()
    ctypes.windll.user32.PostThreadMessageW(tid, WM_HOTKEY, HOTKEY_ID_BASE + 0xB3, 0)
    QApplication.processEvents()
    assert hits == [1]
    k.disable()
    ctypes.windll.user32.PostThreadMessageW(tid, WM_HOTKEY, HOTKEY_ID_BASE + 0xB3, 0)
    QApplication.processEvents()
    assert hits == [1]
```

`tests/test_panel_input.py` — 고칠 것과 더할 것:
- `test_view_menu_mini_items`의 메뉴 목록 끝에 `"멀티미디어 키 사용"`을 더한다.
- 다음 테스트를 더한다.

```python
from fakes import FakeApi
from funplayer.ui.media_keys import HOTKEY_ID_BASE, MediaKeys

def keys_panel(qapp, tmp_path, store, api):
    fake = FakePlayer()
    p = PlayerPanel(Settings(store, lambda: None), player=fake, media_keys=MediaKeys(api=api))
    p.controller.open([str(make_songs(tmp_path / "m", ABC))]); p.refresh()
    return p, fake

def test_panel_media_keys_wiring(qapp, tmp_path):
    api = FakeApi(); p, fake = keys_panel(qapp, tmp_path, {}, api)
    k = p.media_keys
    k.handle_hotkey(HOTKEY_ID_BASE + 0xB3); assert fake.state is State.PAUSED
    k.handle_hotkey(HOTKEY_ID_BASE + 0xB0); assert p.controller.playlist.index == 1
    k.handle_hotkey(HOTKEY_ID_BASE + 0xB2); assert fake.state is State.STOPPED
    p.shutdown(); p.deleteLater()
    assert api.registered == {}

def test_panel_media_keys_busy_notice(qapp):
    api = FakeApi(busy={0xB3})
    p = PlayerPanel(Settings({}, lambda: None), player=FakePlayer(), media_keys=MediaKeys(api=api))
    assert (p.controller.status, p.controller.status_error) == ("멀티미디어 키를 다른 프로그램이 쓰고 있습니다", False)
    assert set(api.registered.values()) == {0xB0, 0xB1, 0xB2}
    p.shutdown(); p.deleteLater()
    assert api.registered == {}

def test_media_keys_option(qapp, tmp_path):
    api = FakeApi(); store = {"player_media_keys": False}
    p, _ = keys_panel(qapp, tmp_path, store, api)
    assert api.registered == {}
    p.view_menu.aboutToShow.emit(); act = p.actions["media_keys"]
    assert act.text() == "멀티미디어 키 사용" and not act.isChecked()
    act.trigger(); assert store["player_media_keys"] is True and len(api.registered) == 4
    act.trigger(); assert store["player_media_keys"] is False and api.registered == {}
    p.shutdown(); p.deleteLater()

def test_focused_media_shortcuts(rig):
    p, fake, *_ = rig
    assert len(p.media_shortcuts) == 5
    assert all(sc.context() == Qt.WidgetWithChildrenShortcut for sc in p.media_shortcuts)
    p.media_shortcuts[0].activated.emit(); assert fake.state is State.PAUSED
```

`tests/test_main.py`의 `test_main_smoke`에서, `entry.main([])`을 부르기 전에 진짜 등록을 막는다.

```python
    import funplayer.ui.media_keys as mk
    monkeypatch.setattr(mk, "default_api", lambda: None)
```

- [ ] **Step 2: 실행해서 실패를 본다**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_media_keys.py tests/test_panel_input.py tests/test_main.py`
Expected: FAIL

- [ ] **Step 3: `funplayer/ui/media_keys.py`를 만든다**
  - **`Win32HotkeyApi`:**
    - `ctypes.windll.user32.RegisterHotKey(None, hotkey_id, MOD_NOREPEAT, vk)`가 0이 아니면 True다.
    - `UnregisterHotKey(None, hotkey_id)`로 푼다.
  - **`default_api()`:** `sys.platform == "win32"`이면 `Win32HotkeyApi()`, 아니면 None이다.
  - **`MediaKeys(QObject)`:**
    - **`enable()`:**
      - api가 None이면 True를 돌려주고 아무것도 하지 않는다.
      - 이미 등록한 키는 다시 등록하지 않는다.
      - 나머지 키를 등록하고, 성공한 id를 기억한다.
      - 처음 켤 때 네이티브 필터를 `QCoreApplication.instance()`에 설치한다.
      - 네 키가 모두 등록되면 True다.
    - **`disable()`:** 기억한 id를 모두 풀고, 필터를 떼어 낸다.
    - **`enabled`:** 등록된 id가 하나라도 있으면 True다. api가 None이면 마지막으로 `enable()`을 부른 뒤 `disable()`하지 않았을 때 True다.
    - **`handle_hotkey(id)`:** 등록된 id면 맞는 신호를 내고 True다. 아니면 False다.
  - **필터:** `QAbstractNativeEventFilter` 하위 클래스다. `MediaKeys`가 참조를 쥐고 있는다.

```python
    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and self._owner.handle_hotkey(int(msg.wParam)):
                return True, 0
        return False, 0
```

- [ ] **Step 4: 패널과 `__main__`를 고친다**
  - **생성자:** 인자 `media_keys=None`. `self.media_keys = media_keys if media_keys is not None else MediaKeys(self)`.
  - **신호 연결:** `play_pause_pressed` → `self.toggle`, `next_pressed` → `self.next`, `prev_pressed` → `self.prev`, `stop_pressed` → `self.stop`.
  - **생성자 끝(이어 듣기 복원 뒤):** `settings.media_keys`면 `if not self.media_keys.enable(): self.controller.notify(MEDIA_KEYS_BUSY_MSG)`.
  - **`view_menu`:** 맨 끝에 `"media_keys"`(`멀티미디어 키 사용`, 체크 가능) → `set_media_keys(checked)`.
  - **`set_media_keys(on)`:**
    - `settings.media_keys = on`.
    - on이면 `enable()`을 하고, 실패하면 `notify(MEDIA_KEYS_BUSY_MSG)`다. off면 `disable()`이다.
    - 그다음 `refresh()`.
  - **체크 상태:** 액션을 만들 때와 `_update_actions`에서 `settings.media_keys`에 맞춘다.
  - **창이 앞에 있을 때의 대체 단축키 `self.media_shortcuts`:** 이 순서로 `QShortcut(QKeySequence(key), self)`를 만든다. 모두 `WidgetWithChildrenShortcut`이다.
    - `Qt.Key_MediaTogglePlayPause` → toggle
    - `Qt.Key_MediaPlay` → toggle
    - `Qt.Key_MediaNext` → next
    - `Qt.Key_MediaPrevious` → prev
    - `Qt.Key_MediaStop` → stop
  - **`shutdown()`:** `save_session()` 다음에 `self.media_keys.disable()`.
  - **`__main__.py`:**
    - `from funplayer.ui import media_keys as media_keys_mod`.
    - 패널 생성에 `media_keys=media_keys_mod.MediaKeys(api=media_keys_mod.default_api())`를 넘긴다. 테스트가 `default_api`를 바꿔 끼울 수 있게 모듈 이름으로 부른다.
- [ ] **Step 5: 실행해서 통과를 본다** — 전체 스위트, Expected: PASS
- [ ] **Step 6: 커밋**

```bash
git add funplayer/ui/media_keys.py funplayer/ui/player_panel.py funplayer/__main__.py tests/fakes.py tests/test_media_keys.py tests/test_panel_input.py tests/test_main.py
git commit -m "Handle keyboard media keys globally with an off switch"
```

---

### Task 12: 실제 화면 캡처와 사용자 확인 (컨트롤러가 직접)

이 작업은 구현 에이전트에게 맡기지 않는다. 컨트롤러가 직접 하고, 사용자 확인에서 멈춘다.

- [ ] **Step 1: 스크래치 패드의 `real_stage2a.py`를 본떠 `real_stage2b.py`를 만든다**
  - 태그(CP949 한글 제목·가수)와 PNG 그림을 넣은 MP3 몇 곡을 `tests/tagfiles.py`처럼 만든다.
  - `last.m3u8`과 설정으로 이어 듣기 상태를 만든다(위치 1:12, 그림 있는 곡).
  - `PlayerPanel(..., session_path=...)`으로 보통 보기를 찍는다.
  - 같은 패널로 `set_mini(True)` 작게 보기를 찍는다.
  - 곡 정보 창을 찍는다.
  - 세 장을 한 장으로 이어 `docs/images/stage2b_real.png`에 저장한다. 실행: `.venv/Scripts/python.exe -I -B real_stage2b.py <repo> <out.png> <songs_dir>`.
  - PNG를 직접 보고 시안과 견준다.
- [ ] **Step 2: 시안 페이지(같은 아티팩트)를 고친다**
  - 시안과 실제 화면을 나란히 둔다.
  - spec §7 체크리스트를 체크 상자로 둔다(localStorage 키 `myfun-stage2b-checks`, try/catch).
  - 알고 있는 한계와 "대신 정한 것"을 적는다.
- [ ] **Step 3: 사용자에게 한국어로 알린다**
  - 링크, `run.bat`, 확인 목록, 한계, Rulings 전체를 비용과 함께 알린다.
  - 결과를 받을 때까지 다음 단계로 가지 않는다.
- [ ] **Step 4 (사용자 통과 뒤):**
  - 로드맵 §3에서 K-2 H-1 H-2 I-2 J-3에 ☑ 날짜를 찍고, J-1 메모를 "1·2-A·2-B단계분"으로 고친다.
  - §9의 2-B를 "완료 (날짜) · 마지막 커밋 · 테스트 N개"로 고친다.
  - `git add docs/개발로드맵.md docs/images/stage2b_real.png` 후 `git commit -m "Mark stage 2-B complete"`.
  - 그다음 finishing-a-development-branch(로컬 `main`에 합치기, push 없음)를 하고 메모리를 고친다.
