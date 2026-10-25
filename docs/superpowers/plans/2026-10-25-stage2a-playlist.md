# my-fun 2-A단계 재생목록 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 1단계 플레이어에 반복(끔/전체/한 곡), 무작위, 재생목록 저장·불러오기(m3u8), 목록 편집(지우기·중복·없는 파일·정렬·끌어서 옮기기)과 그 단축키를 더한다.

**Architecture:**
- **순서:** 재생 순서는 새 Qt 없는 모듈 `core/order.py`의 `PlayOrder`가 맡는다. 순서대로면 목록 순서, 무작위면 한 바퀴짜리 섞은 순서다.
- **목록:** `Playlist`는 곡 목록과 지금 곡을 들고, 편집할 때 `PlayOrder`의 번호를 다시 맞춘다.
- **파일:** m3u 읽기·쓰기는 `core/m3u.py`가 한다.
- **규칙:** 반복·재생목록·편집 규칙은 `controller.py`가 정한다.
- **화면:** `ui/icons.py`(그린 아이콘), `ui/playlist_view.py`(여러 줄 선택·끌어 옮기기·파일 놓기), `ui/player_panel.py`(단추·메뉴·단축키)가 맡는다.

**Tech Stack:** Python 3.14(3.13 호환), PyQt5 5.15.11, pytest 9.1.1. 새 의존성은 없다.

**Spec:** `docs/stage2a_design.md` (시안 `docs/images/stage2a_mockup.png`, 1단계 spec `docs/stage1_design.md`, 로드맵 `docs/개발로드맵.md`)

## Global Constraints

- **Python 버전:** 3.13에서도 돌아야 한다. `funplayer`의 모든 비어 있지 않은 `.py`는 `from __future__ import annotations`로 시작한다. 3.14 전용 문법은 쓰지 않는다.
- **의존성:** `requirements*.txt`는 바꾸지 않는다. 새 패키지는 넣지 않는다.
- **Qt 사용 범위:**
  - PySide6는 import하지 않는다.
  - `core/`, `engine/`, `controller.py`는 PyQt5를 import하지 않는다. 이것은 `tests/test_layering.py`가 검사한다.
- **1단계 규칙 유지:**
  - 이전 곡 기준은 3.0초다.
  - 곡 끝 알림은 플레이어가 STOPPED일 때만 받는다.
  - 단축키는 `Qt.WidgetWithChildrenShortcut`이다.
  - 화면 갱신은 200ms마다 한다.
  - ←→↑↓ 키는 탐색과 볼륨에 그대로 쓴다.
- **화면 문구(정확히 이대로):**
  - 상태 메시지
    - 오류: `불러올 수 없음: {파일명}`, `저장할 수 없음: {파일명}`
    - 안내: `저장했습니다: {파일명}`, `없는 파일 {N}곡`, `중복 곡 {N}개를 지웠습니다`, `중복 곡이 없습니다`, `{N}곡을 지웠습니다`, `지울 곡이 없습니다`
    - 1단계 메시지는 그대로 둔다.
  - 풍선 도움말: `반복: 끔`, `반복: 전체`, `반복: 한 곡`, `무작위: 끔`, `무작위: 켬`
  - 아래 줄 단추: `열기`, `추가`, `목록`. `비우기` 단추는 없앤다.
  - [열기] 메뉴: `파일…\tL`, `폴더…`, `재생목록…\tCtrl+O`
  - [추가] 메뉴: `파일…`, `폴더…`, `재생목록…`
  - [목록] 메뉴(가운데 빈 칸은 구분선): `저장…\tCtrl+S`, —, `선택한 곡 지우기\tDel`, `중복 곡 지우기`, `없는·깨진 파일 지우기`, `정렬`(하위 메뉴 `이름순`, `폴더·이름순`), —, `목록 비우기`
  - 오른쪽 클릭 메뉴: `재생\tEnter`, `선택한 곡 지우기\tDel`, —, `전체 선택\tCtrl+A`
  - 대화상자:
    - 열기: 제목 `재생목록 열기`, 필터 `재생목록 (*.m3u8 *.m3u)`
    - 저장: 제목 `재생목록 저장`, 기본 이름 `재생목록.m3u8`, 필터 `재생목록 (*.m3u8)`
- **상태 줄 색:** 오류는 `#B3261E`, 안내는 `#5F6368`이다.
- **설정 키:**
  - `player_repeat`: `"off"`, `"all"`, `"one"` 중 하나이고 기본값은 `"off"`다.
  - `player_shuffle`: bool이고 기본값은 false다.
  - 다른 키는 건드리지 않는다.
- **재생목록 파일:**
  - 쓰기:
    - UTF-8(BOM 없음)이고, 줄바꿈은 CRLF, 첫 줄은 `#EXTM3U`다.
    - 목록 파일의 폴더(하위 포함) 안에 있는 곡은 상대 경로로, 그 밖의 곡은 절대 경로로 쓴다.
    - 임시 파일에 쓴 뒤 바꿔친다.
  - 읽기: UTF-8(BOM 허용)로 읽고, 실패하면 CP949로 읽는다.
- **테스트:**
  - 실제 소리 장치와 네트워크를 쓰지 않는다.
  - Qt 테스트는 offscreen에서 돈다.
  - 무작위 테스트는 `random.Random(시드)` 또는 `tests/fakes.py`의 `FakeRng`를 쓴다.
- **git:**
  - 로컬 브랜치 `stage2a-playlist`에서 작업하고 push하지 않는다. Task 하나에 커밋 하나다.
  - 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.
  - `Test-mp3/`는 사용자의 음악 폴더이므로 커밋하지 않는다.
- **실행 명령:** 저장소 루트 `G:\REA-test\my-fun`에서 `.venv/Scripts/python.exe -m pytest ...`로 실행한다.

## 계획에서 정한 것 (spec에 없던 결정)

1. 재생목록 파일은 1단계 `open(paths)`·`add(paths)`가 받는다. 대화상자, 끌어다 놓기, 목록에 놓기가 모두 같은 길을 쓴다. spec §5도 이렇게 맞췄다.
2. `open`·`add`는 시작할 때 상태 줄을 지운다. 그래야 이번 작업의 결과(없는 파일 수 등)만 보인다.
3. 상태 메시지는 하나만 보여준다. 우선순위는 재생 중 건너뛴 파일 오류 > 목록 읽기 오류 > 없는 파일 안내 순서다.
4. 듣던 곡을 지우면 엔진을 정지하고 파일을 놓는다(`stop()` → `unload()`). 재생 중이었을 때만 새 지금 곡을 재생한다. 일시정지 중에 지우고 다시 재생을 누르면 지운 곡이 아니라 새 지금 곡이 처음부터 나온다.
5. "중복 곡 지우기"와 "없는·깨진 파일 지우기"는 상태 줄을 지운 뒤 실행한다. 다른 메시지가 생기지 않았을 때만 결과 안내를 띄운다.
6. 무작위를 끄면 목록 순서로 돌아가고, 지금 곡의 다음 줄부터 이어 간다.
7. `Playlist.version`은 1단계 뜻("무엇이든 바뀜")을 유지한다. 목록 구성이 바뀔 때만 오르는 `layout_version`을 따로 둔다. 화면은 `layout_version`이 바뀌면 목록을 다시 만들고, `version`만 바뀌면 줄 모양만 고친다.
8. Enter는 목록의 현재 줄(마지막으로 클릭한 줄)을 재생한다. 화살표 키는 1단계대로 볼륨·탐색이다.
9. 메뉴 오른쪽의 키 이름은 글자(`\t`)로만 넣는다. 실제 키는 `QShortcut`이 처리한다.
10. 저장할 이름에 `.m3u8`·`.m3u` 확장자가 없으면 `.m3u8`을 붙인다. 없는 폴더는 만들지 않고 저장 실패로 처리한다.
11. [목록] 메뉴와 오른쪽 클릭 메뉴는 열릴 때(`aboutToShow`) 쓸 수 있는 항목만 켠다.
    - 저장·중복·없는 파일·정렬·비우기: 곡이 있을 때만 켠다.
    - 선택한 곡 지우기: 고른 줄이 있을 때만 켠다.
    - 재생: 현재 줄이 있을 때만 켠다.
12. 끌어 옮기기는 자체 MIME 형식 `application/x-myfun-rows`로 줄 번호를 넘긴다.
    - 목록 위젯이 스스로 줄을 옮기거나 지우지 않게 한다. 목록의 원본은 `Playlist` 하나다.
    - 그래서 `startDrag`를 직접 쓰고, `dropEvent`는 `IgnoreAction`으로 바꾼 뒤 부모 처리를 부른다.
13. 반복·무작위 아이콘은 상태가 바뀔 때만 다시 그린다.

## Review Focus

1. **실제 마우스 끌기:**
   - 테스트는 `dropEvent`를 직접 부른다. 실제 끌기에서는 Qt 기본 동작이 끼어든다.
   - Qt 기본 동작이 끌기가 끝난 뒤 원래 줄을 지우거나, 위젯이 줄을 따로 옮겨 `Playlist`와 어긋나면 안 된다.
   - → Task 8 `test_drop_emits_rows_moved_and_leaves_items`. 리뷰에서 `startDrag`/`dropEvent`를 꼭 읽는다.
2. **목록에 포커스가 있을 때의 키:** `QListWidget`이 Delete·Enter를 먼저 먹으면 단축키가 동작하지 않는다.
   - → Task 8 `test_real_keys_in_list`. 실제 키 입력으로 확인한다.
3. **다른 프로그램이 만든 m3u:** CP949, `#EXTINF`, `..\` 상대 경로, `/` 구분자, `file:///`, 인터넷 주소가 섞여 있을 수 있다.
   - → Task 2 `test_read_*`
4. **무작위 + 전체 반복 + 모두 깨진 파일:** 열 수 없는 곡을 건너뛰며 끝없이 돌면 안 된다.
   - → Task 5 `test_repeat_all_with_all_failed_stops`(순서대로·무작위 둘 다)
5. **일시정지 중에 듣던 곡을 지운 뒤 재생:** 지운 곡이 이어서 나오면 안 된다.
   - → Task 6 `test_remove_current`의 pause 경우

## 파일 구조

```
funplayer/
├─ core/
│  ├─ tracks.py     (수정) is_supported, path_sort_key, name_sort_key 공개
│  ├─ settings.py   (수정) REPEAT_MODES, repeat, shuffle
│  ├─ m3u.py        (새)   PLAYLIST_EXTS, is_playlist, read_playlist, write_playlist
│  ├─ order.py      (새)   PlayOrder
│  └─ playlist.py   (수정) PlayOrder 연결, layout_version, remove/sort/move, 중복·재생 불가 찾기
├─ controller.py    (수정) 반복·무작위, 재생목록 파일, 편집, 상태 종류
└─ ui/
   ├─ icons.py         (새)   OFF_COLOR, repeat_icon, shuffle_icon
   ├─ playlist_view.py (새)   ROWS_MIME, PlaylistView
   └─ player_panel.py  (수정) 단추·메뉴·오른쪽 클릭·단축키, 줄 갱신
tests/
├─ fakes.py         (수정) FakeRng
├─ test_m3u.py, test_order.py, test_icons.py, test_playlist_view.py  (새)
└─ test_tracks.py, test_settings.py, test_playlist.py, test_controller.py,
   test_panel_view.py, test_panel_input.py  (수정)
```

---

### Task 1: 공개 정렬 키와 반복·무작위 설정

**Files:**
- Modify: `funplayer/core/tracks.py`, `funplayer/core/settings.py`
- Test: `tests/test_tracks.py`, `tests/test_settings.py`

**Interfaces:**
- Produces (`tracks.py`):
  - `is_supported(path: str) -> bool`: 지금의 `_is_supported`를 이름만 바꾼 것이다.
  - `path_sort_key(path: str) -> tuple`: 지금의 `_sort_key`를 이름만 바꾼 것이다(폴더 → 이름 자연 정렬).
  - `name_sort_key(path: str) -> tuple`: `(natural_key(os.path.basename(path)), path_sort_key(path))`
  - 모듈 안에서 옛 이름을 쓰던 곳도 새 이름으로 바꾼다. 옛 이름은 남기지 않는다.
- Produces (`settings.py`):
  - `REPEAT_MODES = ("off", "all", "one")`
  - `DEFAULTS`에 `"player_repeat": "off"`, `"player_shuffle": False`를 더한다.
  - `Settings.repeat`
    - 읽기: 값이 `REPEAT_MODES` 안에 있으면 그 값, 아니면 `"off"`
    - 쓰기: `REPEAT_MODES` 밖의 값은 `"off"`로 저장한다.
  - `Settings.shuffle`
    - 읽기: bool이면 그 값, 아니면 `False`
    - 쓰기: `bool(value)`로 저장한다.
  - 두 setter 모두 1단계처럼 저장 함수를 부른다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tracks.py`에 더한다.

```python
from funplayer.core.tracks import is_supported, name_sort_key, path_sort_key

def test_public_sort_keys():
    paths = [r"C:\b\2 x.mp3", r"C:\a\10 y.mp3", r"C:\a\9 z.mp3"]
    assert sorted(paths, key=path_sort_key) == [r"C:\a\9 z.mp3", r"C:\a\10 y.mp3", r"C:\b\2 x.mp3"]
    assert sorted(paths, key=name_sort_key) == [r"C:\b\2 x.mp3", r"C:\a\9 z.mp3", r"C:\a\10 y.mp3"]
    assert is_supported("A.MP3") and not is_supported("list.m3u8")
```

`tests/test_settings.py`에서 `test_defaults`의 둘째 assert를 아래로 바꾸고, 테스트 하나를 더한다.

```python
    assert DEFAULTS == {"player_volume": 70, "player_muted": False, "player_seek_step": 5,
                        "player_repeat": "off", "player_shuffle": False}

def test_repeat_and_shuffle():
    s, store, saves = make()
    assert (s.repeat, s.shuffle) == ("off", False)
    s.repeat = "one"; s.shuffle = True
    assert store["player_repeat"] == "one" and store["player_shuffle"] is True and len(saves) == 2
    s.repeat = "loop"; assert store["player_repeat"] == "off"
    s2, _, _ = make({"player_repeat": "ALL", "player_shuffle": 1})
    assert (s2.repeat, s2.shuffle) == ("off", False)
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_tracks.py tests/test_settings.py -v` / Expected: `ImportError: cannot import name 'is_supported'`, `test_repeat_and_shuffle` FAIL

- [ ] **Step 3: 구현** (Interfaces대로)

- [ ] **Step 4: 통과 확인** — Run: `.venv/Scripts/python.exe -m pytest -q` / Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add funplayer/core/tracks.py funplayer/core/settings.py tests/test_tracks.py tests/test_settings.py
git commit -m "Add public sort keys and repeat/shuffle settings"
```

---

### Task 2: 재생목록 파일 (m3u)

**Files:**
- Create: `funplayer/core/m3u.py`
- Test: `tests/test_m3u.py`

**Interfaces:**
- Consumes: `is_supported`(Task 1)
- Produces:
  - `PLAYLIST_EXTS = frozenset({".m3u", ".m3u8"})`
  - `is_playlist(path: str) -> bool`: 확장자로만 판단하고, 대소문자를 가리지 않는다.
  - `read_playlist(path: str) -> list[str]`: 파일을 못 읽으면 `OSError`를 그대로 올린다. 읽는 규칙은 다음과 같다.
    1. bytes로 읽는다. 먼저 `utf-8-sig`(strict)로 풀고, `UnicodeDecodeError`가 나면 `cp949`(`errors="replace"`)로 푼다.
    2. 줄마다 앞뒤 공백을 지운다. 빈 줄과 `#`으로 시작하는 줄은 건너뛴다.
    3. `^[A-Za-z][A-Za-z0-9+.-]+://`에 맞는 줄은 주소로 본다.
       - `file:`이면 `urllib.request.url2pathname(urllib.parse.urlparse(line).path)`로 경로로 바꾼다.
       - 그 밖의 주소는 건너뛴다. `C:\…`는 `://`가 없으므로 여기에 걸리지 않는다.
    4. 경로는 `os.path.abspath(os.path.join(목록 파일의 폴더, 항목))`으로 만든다.
    5. `is_supported`인 것만 파일 순서 그대로 돌려준다. 파일이 실제로 있는지는 보지 않는다.
  - `write_playlist(path: str, tracks: list[str]) -> None`: 실패하면 `OSError`를 올린다. 폴더는 만들지 않는다. 쓰는 규칙은 다음과 같다.
    - base는 `os.path.dirname(os.path.abspath(path))`다.
    - `os.path.commonpath([normcase(base), normcase(track)]) == normcase(base)`이면 `os.path.relpath(track, base)`로 쓰고, 아니면 track을 그대로 쓴다. 드라이브가 달라서 `ValueError`가 나면 그대로 쓴다.
    - 내용은 `"\r\n".join(["#EXTM3U", *entries]) + "\r\n"`을 UTF-8로 인코딩한 것이다.
    - `path + ".tmp"`에 쓴 뒤 `os.replace`로 바꿔친다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_m3u.py
import os
import pytest
from funplayer.core.m3u import is_playlist, read_playlist, write_playlist

def _abs(p):
    return os.path.normpath(os.path.abspath(p))

def test_is_playlist():
    assert is_playlist("a.M3U8") and is_playlist(r"C:\x\b.m3u") and not is_playlist("c.mp3")

def test_round_trip_keeps_order_and_korean_names(tmp_path):
    lists = tmp_path / "목록"; lists.mkdir()
    tracks = [str(lists / "하위" / "02 봄.mp3"), str(tmp_path / "음악" / "01 비 오는 날.flac"),
              str(lists / "00 a.mp3")]
    write_playlist(str(lists / "내 목록.m3u8"), tracks)
    assert read_playlist(str(lists / "내 목록.m3u8")) == [_abs(t) for t in tracks]

def test_write_format_relative_inside_absolute_outside(tmp_path):
    lists = tmp_path / "lists"; lists.mkdir()
    inside, outside = str(lists / "sub" / "a.mp3"), str(tmp_path / "music" / "b.mp3")
    write_playlist(str(lists / "x.m3u8"), [inside, outside])
    raw = (lists / "x.m3u8").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8").split("\r\n") == ["#EXTM3U", os.path.join("sub", "a.mp3"), outside, ""]
    assert not (lists / "x.m3u8.tmp").exists()

def test_write_other_drive_is_absolute(tmp_path):
    write_playlist(str(tmp_path / "x.m3u8"), [r"Z:\m\a.mp3"])
    assert (tmp_path / "x.m3u8").read_text(encoding="utf-8").splitlines()[1] == r"Z:\m\a.mp3"

def test_read_utf8_bom_and_cp949_m3u(tmp_path):
    (tmp_path / "a.m3u8").write_bytes(b"\xef\xbb\xbf#EXTM3U\r\n" + "봄.mp3".encode("utf-8") + b"\r\n")
    assert read_playlist(str(tmp_path / "a.m3u8")) == [_abs(tmp_path / "봄.mp3")]
    (tmp_path / "b.m3u").write_bytes("#EXTM3U\r\n노래 1.mp3\r\n".encode("cp949"))
    assert read_playlist(str(tmp_path / "b.m3u")) == [_abs(tmp_path / "노래 1.mp3")]

def test_read_skips_comments_blank_urls_unsupported(tmp_path):
    text = "\n".join(["#EXTM3U", "#EXTINF:123,가수 - 제목", "", "  a.mp3  ",
                      "http://radio.example/stream.mp3", "notes.txt", "sub/b.FLAC", r"..\up\c.ogg"])
    (tmp_path / "l.m3u8").write_text(text, encoding="utf-8")
    assert read_playlist(str(tmp_path / "l.m3u8")) == [
        _abs(tmp_path / "a.mp3"), _abs(tmp_path / "sub" / "b.FLAC"), _abs(tmp_path.parent / "up" / "c.ogg")]

def test_read_file_uri(tmp_path):
    uri = (tmp_path / "a b.mp3").as_uri()
    (tmp_path / "l.m3u8").write_text("#EXTM3U\n" + uri + "\n", encoding="utf-8")
    assert read_playlist(str(tmp_path / "l.m3u8")) == [_abs(tmp_path / "a b.mp3")]

def test_missing_tracks_are_returned(tmp_path):
    (tmp_path / "l.m3u8").write_text("#EXTM3U\r\nghost.mp3\r\n", encoding="utf-8")
    assert read_playlist(str(tmp_path / "l.m3u8")) == [_abs(tmp_path / "ghost.mp3")]

def test_io_errors_raise(tmp_path):
    with pytest.raises(OSError):
        read_playlist(str(tmp_path / "none.m3u8"))
    with pytest.raises(OSError):
        write_playlist(str(tmp_path / "no" / "dir" / "x.m3u8"), [r"C:\a.mp3"])
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_m3u.py -v` / Expected: `ModuleNotFoundError: funplayer.core.m3u`

- [ ] **Step 3: `funplayer/core/m3u.py` 구현** (Interfaces대로)

- [ ] **Step 4: 통과 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_m3u.py tests/test_layering.py -v` / Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add funplayer/core/m3u.py tests/test_m3u.py
git commit -m "Add m3u8 playlist read/write"
```

---

### Task 3: 재생 순서 (PlayOrder)

**Files:**
- Create: `funplayer/core/order.py`
- Modify: `tests/fakes.py` (`FakeRng` 추가)
- Test: `tests/test_order.py`

**Interfaces:**
- Produces:
  - `PlayOrder(rng=None)`: `rng`가 없으면 `random.Random()`을 쓴다. 쓰는 메서드는 `rng.shuffle(list)`와 `rng.randint(a, b)` 둘뿐이다.
  - 불변식: `order`는 늘 `range(n)`의 순열이다. 순서대로 모드면 `[0, 1, …, n-1]`이다.
  - 지금 곡의 위치는 저장하지 않는다. 메서드가 `current`를 받아서 `order.index(current)`로 찾는다.
  - 메서드: `shuffle`(속성), `order`(복사본), `rebuild`, `set_shuffle`, `extend`, `first`, `first_of`, `next`, `prev`, `moved_to`, `remap`. 동작은 아래 코드와 같다.
- `tests/fakes.py`에 더한다.

```python
class FakeRng:
    """random.Random 대신 쓰는 결정적 난수: shuffle은 뒤집고, randint는 가장 작은 값을 고른다."""

    def shuffle(self, xs: list) -> None:
        xs.reverse()

    def randint(self, a: int, b: int) -> int:
        return a
```

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_order.py
import random
from fakes import FakeRng
from funplayer.core.order import PlayOrder

def walk(o, start, wrap=False, limit=50):
    seen, cur = [start], start
    while len(seen) < limit and (cur := o.next(cur, wrap)) is not None:
        seen.append(cur)
    return seen

def shuffled5():
    o = PlayOrder(FakeRng()); o.rebuild(5, 2); o.set_shuffle(True, 2)
    return o                                          # order [2, 4, 3, 1, 0]

def test_sequential():
    o = PlayOrder(); o.rebuild(3, None)
    assert o.order == [0, 1, 2] and o.first() == 0 and not o.shuffle
    assert (o.next(0, False), o.next(2, False), o.next(2, True)) == (1, None, 0)
    assert (o.prev(1, False), o.prev(0, False), o.prev(0, True)) == (0, None, 2)
    assert o.next(None, True) is None and o.prev(None, True) is None

def test_shuffle_on_puts_current_first_and_off_restores():
    o = shuffled5()
    assert o.order == [2, 4, 3, 1, 0] and o.shuffle
    o.set_shuffle(False, 2); assert o.order == [0, 1, 2, 3, 4]

def test_shuffle_one_pass_then_stop_or_wrap():
    o = PlayOrder(FakeRng()); o.set_shuffle(True, None); o.rebuild(5, None)
    assert o.order == [4, 3, 2, 1, 0] and walk(o, 4) == [4, 3, 2, 1, 0]
    assert o.next(0, True) == 4

def test_real_rng_visits_every_track_once():
    o = PlayOrder(random.Random(7)); o.set_shuffle(True, None); o.rebuild(20, None)
    assert sorted(walk(o, o.first())) == list(range(20))

def test_shuffle_prev_goes_back_and_never_wraps():
    o = shuffled5()
    assert o.prev(3, True) == 4 and o.prev(2, True) is None

def test_wrap_reshuffles_with_chosen_first():
    o = shuffled5()
    o.moved_to(0, o.next(0, True))
    assert o.order == [2, 0, 1, 3, 4]

def test_pick_later_track_goes_next():
    o = shuffled5(); o.moved_to(4, 0)
    assert o.order == [2, 4, 0, 3, 1] and o.prev(0, False) == 4

def test_pick_earlier_track_goes_next():
    o = shuffled5(); o.moved_to(1, 2)
    assert o.order == [4, 3, 1, 2, 0] and o.prev(2, False) == 1

def test_adjacent_moves_change_nothing():
    o = shuffled5(); o.moved_to(4, 3); o.moved_to(3, 4); o.moved_to(4, 4)
    assert o.order == [2, 4, 3, 1, 0]

def test_first_pick_without_current_moves_to_front():
    o = PlayOrder(FakeRng()); o.set_shuffle(True, None); o.rebuild(3, None)   # [2, 1, 0]
    o.moved_to(None, 0); assert o.order == [0, 2, 1]

def test_extend():
    s = PlayOrder(); s.rebuild(2, None); s.extend(4, 0)
    assert s.order == [0, 1, 2, 3] and s.first_of([3, 2]) == 2
    o = shuffled5(); o.extend(7, 4)
    assert o.order == [2, 4, 5, 6, 3, 1, 0] and o.first_of([6, 5]) == 5

def test_remap():
    s = PlayOrder(); s.rebuild(4, None); s.remap([0, None, 1, 2]); assert s.order == [0, 1, 2]
    o = shuffled5(); o.remap([None, 0, 1, None, 2]); assert o.order == [1, 2, 0]
    o.remap([2, 0, 1]); assert o.order == [0, 1, 2]
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_order.py -v` / Expected: `ModuleNotFoundError: funplayer.core.order`

- [ ] **Step 3: `funplayer/core/order.py` 구현** — 아래 코드를 그대로 쓴다. 섞기 규칙이 테스트의 정확한 순서와 맞아야 한다.

```python
from __future__ import annotations

import random
from typing import Iterable


class PlayOrder:
    """곡 번호 0..n-1의 재생 순서. 순서대로면 목록 순서, 무작위면 한 바퀴짜리 섞은 순서다."""

    def __init__(self, rng=None) -> None:
        self._rng = rng if rng is not None else random.Random()
        self._shuffle = False
        self._order: list[int] = []

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @property
    def order(self) -> list[int]:
        return list(self._order)

    def rebuild(self, n: int, current: int | None) -> None:
        if not self._shuffle:
            self._order = list(range(n))
            return
        head = [current] if current is not None and 0 <= current < n else []
        rest = [i for i in range(n) if i not in head]
        self._rng.shuffle(rest)
        self._order = head + rest

    def set_shuffle(self, on: bool, current: int | None) -> None:
        self._shuffle = bool(on)
        self.rebuild(len(self._order), current)

    def extend(self, n: int, current: int | None) -> None:
        new = list(range(len(self._order), n))
        if not self._shuffle:
            self._order.extend(new)
            return
        lo = self._order.index(current) + 1 if current is not None else 0
        self._rng.shuffle(new)
        for x in new:
            self._order.insert(self._rng.randint(lo, len(self._order)), x)

    def first(self) -> int | None:
        return self._order[0] if self._order else None

    def first_of(self, indices: Iterable[int]) -> int | None:
        wanted = set(indices)
        return next((i for i in self._order if i in wanted), None)

    def next(self, current: int | None, wrap: bool) -> int | None:
        if current is None or not self._order:
            return None
        p = self._order.index(current)
        if p + 1 < len(self._order):
            return self._order[p + 1]
        return self._order[0] if wrap else None

    def prev(self, current: int | None, wrap: bool) -> int | None:
        if current is None or not self._order:
            return None
        p = self._order.index(current)
        if p > 0:
            return self._order[p - 1]
        if wrap and not self._shuffle and len(self._order) > 1:
            return self._order[-1]
        return None

    def moved_to(self, old: int | None, new: int) -> None:
        """지금 곡이 old에서 new로 바뀌었다. 무작위면 new가 old 바로 다음 순서가 되게 한다."""
        if not self._shuffle:
            return
        order = self._order
        q = order.index(new)
        if old is None:
            order.insert(0, order.pop(q))
            return
        p = order.index(old)
        if q in (p - 1, p, p + 1):
            return
        if p == len(order) - 1 and q == 0:  # 한 바퀴를 다 돌고 처음으로: 새로 섞는다
            rest = order[1:]
            self._rng.shuffle(rest)
            self._order = [new] + rest
            return
        order.pop(q)
        if q < p:
            p -= 1
        order.insert(p + 1, new)

    def remap(self, mapping: list[int | None]) -> None:
        """mapping[옛 번호] = 새 번호 (지운 곡은 None)."""
        n = sum(1 for m in mapping if m is not None)
        if not self._shuffle:
            self._order = list(range(n))
            return
        self._order = [mapping[i] for i in self._order if mapping[i] is not None]
```

- [ ] **Step 4: 통과 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_order.py tests/test_layering.py -v` / Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add funplayer/core/order.py tests/fakes.py tests/test_order.py
git commit -m "Add PlayOrder for sequential and shuffled play order"
```

---

### Task 4: 재생목록 편집 (Playlist)

**Files:**
- Modify: `funplayer/core/playlist.py`
- Test: `tests/test_playlist.py`

**Interfaces:**
- Consumes: `PlayOrder`(Task 3), `name_sort_key`·`path_sort_key`(Task 1)
- Produces (1단계 API는 그대로 두고 아래를 더하거나 바꾼다):
  - `Playlist(rng=None)`: 안에서 `self._order = PlayOrder(rng)`를 만든다.
  - `version`: 1단계 뜻 그대로다. 아래의 모든 변경에서 1씩 오르고, `set_shuffle`에서는 오르지 않는다.
  - `layout_version`: `replace`, `add`(곡이 있을 때), `clear`, `remove`(실제로 지웠을 때), `sort`, `move`(줄이 있을 때)에서만 1씩 오른다.
  - `shuffle -> bool`(속성), `order -> list[int]`(속성, `self._order.order`)
  - `set_shuffle(on: bool) -> None` → `self._order.set_shuffle(on, self.index)`
  - `replace(paths)`
    - `self._order.rebuild(len, None)`을 부르고, `index = self._order.first()`로 둔다.
    - 순서대로 모드면 1단계처럼 index는 0이다.
  - `add(paths) -> int | None`
    - 곡을 붙인 뒤 `self._order.extend(len, self.index)`를 부른다.
    - `self._order.first_of(새 번호들)`을 돌려준다. 순서대로 모드면 1단계처럼 첫 새 번호다.
  - `clear()`: `self._order.rebuild(0, None)`도 부른다.
  - `set_current(i)`: 범위 검사 뒤 `self._order.moved_to(self.index, i)`를 부르고 나서 index를 바꾼다.
  - `next_index(wrap: bool = False) -> int | None` → `self._order.next(self.index, wrap)`
  - `prev_target(position: float, wrap: bool = False) -> tuple[str, int]`
    - `position < PREV_THRESHOLD`이고 `self._order.prev(self.index, wrap)`가 None이 아니면 `("prev", 그 번호)`
    - 아니면 `("restart", self.index)`
  - `remove(rows: Iterable[int], wrap: bool = False) -> str`: `"kept"`, `"next"`, `"stop"` 중 하나를 돌려준다(코드는 Step 3).
  - `duplicate_indices() -> list[int]`
    - 키는 `os.path.normcase(os.path.abspath(path))`다.
    - 같은 키 묶음마다 하나만 남긴다. 지금 곡이 그 묶음에 있으면 지금 곡을, 없으면 맨 앞의 것을 남긴다.
    - 나머지 번호를 오름차순으로 돌려준다.
  - `unplayable_indices(exists=os.path.exists) -> list[int]`: `failed`이거나 `not exists(path)`인 번호를 오름차순으로 돌려준다.
  - `sort(by: str) -> None`
    - `"name"`이면 `name_sort_key`, `"path"`면 `path_sort_key`로 안정 정렬한다. 그 밖의 값이면 `ValueError`다.
    - 지금 곡은 유지한다.
  - `move(rows: Iterable[int], before: int) -> list[int]`
    - 고른 줄을 옛 번호 기준 `before` 자리(0..n) 앞에 넣는다. 고른 줄끼리의 순서는 유지한다.
    - 옮긴 줄의 새 번호를 돌려준다. 지금 곡은 유지한다.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_playlist.py`에 더한다)

```python
import pytest
from fakes import FakeRng

P5 = [f"C:/m/0{i} {c}.mp3" for i, c in enumerate("abcde")]

def titles(pl):
    return [t.title for t in pl.tracks]

def test_layout_version_only_on_structure():
    pl = Playlist(); pl.replace(P); lv, v = pl.layout_version, pl.version
    pl.set_current(1); pl.mark_failed(2); pl.set_shuffle(True)
    assert pl.layout_version == lv and pl.version == v + 2
    pl.add(P[:1]); pl.sort("name"); pl.move([0], 2); pl.remove([0]); pl.clear()
    assert pl.layout_version == lv + 5

def test_wrap_navigation():
    pl = Playlist(); pl.replace(P)
    pl.set_current(2); assert pl.next_index() is None and pl.next_index(wrap=True) == 0
    pl.set_current(0)
    assert pl.prev_target(1.0, wrap=True) == ("prev", 2) and pl.prev_target(1.0) == ("restart", 0)

def test_shuffle_replace_and_add():
    pl = Playlist(FakeRng()); pl.set_shuffle(True); pl.replace(P)        # order [2, 1, 0]
    assert pl.shuffle and pl.index == 2 and pl.next_index() == 1 and pl.order == [2, 1, 0]
    pl2 = Playlist(FakeRng()); pl2.replace(P); pl2.set_shuffle(True)     # order [0, 2, 1]
    assert pl2.add(["C:/m/x.mp3", "C:/m/y.mp3"]) == 3 and pl2.order == [0, 3, 4, 2, 1]

@pytest.mark.parametrize("rows,wrap,result,cur,left", [
    ([0], False, "kept", "02 c", "01 b,02 c,03 d,04 e"),
    ([2], False, "next", "03 d", "00 a,01 b,03 d,04 e"),
    ([2, 3], False, "next", "04 e", "00 a,01 b,04 e"),
    ([2, 3, 4], False, "stop", "01 b", "00 a,01 b"),
    ([4, 3, 2], True, "next", "00 a", "00 a,01 b"),
    ([0, 1, 2, 3, 4], False, "stop", None, ""),
    ([9], False, "kept", "02 c", "00 a,01 b,02 c,03 d,04 e"),
])
def test_remove(rows, wrap, result, cur, left):
    pl = Playlist(); pl.replace(P5); pl.set_current(2)
    assert pl.remove(rows, wrap=wrap) == result
    assert (pl.current.title if pl.current else None) == cur and ",".join(titles(pl)) == left

def test_remove_in_shuffle_follows_play_order():
    pl = Playlist(FakeRng()); pl.replace(P5); pl.set_current(2); pl.set_shuffle(True)  # [2,4,3,1,0]
    assert pl.remove([2]) == "next" and pl.current.title == "04 e"
    assert [pl.tracks[i].title for i in pl.order] == ["04 e", "03 d", "01 b", "00 a"]

def test_duplicate_indices_keep_current_or_first():
    pl = Playlist(); pl.replace(["C:/m/a.mp3", "C:/M/A.MP3", "C:/m/b.mp3", "C:/m/./a.mp3"])
    assert pl.duplicate_indices() == [1, 3]
    pl.set_current(3); assert pl.duplicate_indices() == [0, 1]

def test_unplayable_indices(tmp_path):
    real = tmp_path / "a.mp3"; real.write_bytes(b"")
    pl = Playlist(); pl.replace([str(real), str(tmp_path / "ghost.mp3"), str(real)]); pl.mark_failed(2)
    assert pl.unplayable_indices() == [1, 2]

def test_sort_keeps_current():
    pl = Playlist(); pl.replace(["C:/b/2 x.mp3", "C:/a/10 y.mp3", "C:/a/9 z.mp3"]); pl.set_current(1)
    pl.sort("path"); assert titles(pl) == ["9 z", "10 y", "2 x"] and pl.current.title == "10 y"
    assert pl.next_index() == 2
    pl.sort("name"); assert titles(pl) == ["2 x", "9 z", "10 y"] and pl.index == 2
    with pytest.raises(ValueError):
        pl.sort("size")

@pytest.mark.parametrize("rows,before,new_rows,left", [
    ([4], 0, [0], "04 e,00 a,01 b,02 c,03 d"),
    ([0, 1], 5, [3, 4], "02 c,03 d,04 e,00 a,01 b"),
    ([1, 3], 3, [2, 3], "00 a,02 c,01 b,03 d,04 e"),
    ([2], 2, [2], "00 a,01 b,02 c,03 d,04 e"),
])
def test_move(rows, before, new_rows, left):
    pl = Playlist(); pl.replace(P5); pl.set_current(2)
    assert pl.move(rows, before) == new_rows
    assert ",".join(titles(pl)) == left and pl.current.title == "02 c"
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_playlist.py -v` / Expected: 새 테스트들 FAIL (`AttributeError: layout_version` 등). 1단계 테스트는 PASS다.

- [ ] **Step 3: 구현** — 편집은 모두 아래의 `_apply` 하나를 거친다. `remove`의 다음 지금 곡 고르기는 다음 코드와 같다.

```python
    def remove(self, rows: Iterable[int], wrap: bool = False) -> str:
        gone = {r for r in rows if 0 <= r < len(self.tracks)}
        if not gone:
            return "kept"
        cur, result = self.index, "kept"
        if cur in gone:
            cur, result = self._survivor(cur, gone, wrap)
        self._apply([i for i in range(len(self.tracks)) if i not in gone], cur)
        return result

    def _survivor(self, cur: int, gone: set[int], wrap: bool) -> tuple[int | None, str]:
        """지운 지금 곡 대신 지금 곡이 될 곡: [다음]으로 갈 곡, 없으면 순서상 앞의 곡(정지)."""
        nxt = cur
        for _ in range(len(self.tracks)):
            nxt = self._order.next(nxt, wrap)
            if nxt is None or nxt == cur:
                break
            if nxt not in gone:
                return nxt, "next"
        prv = cur
        while (prv := self._order.prev(prv, False)) is not None:
            if prv not in gone:
                return prv, "stop"
        return None, "stop"

    def _apply(self, keep: list[int], current: int | None) -> None:
        """keep = 새 순서대로 놓은 옛 번호들. 빠진 번호는 지운 곡이다."""
        mapping: list[int | None] = [None] * len(self.tracks)
        for new, old in enumerate(keep):
            mapping[old] = new
        self.tracks = [self.tracks[old] for old in keep]
        self._order.remap(mapping)
        self.index = None if current is None else mapping[current]
        self.version += 1
        self.layout_version += 1
```

`sort`는 `_apply(sorted(range(n), key=…), self.index)`로 처리한다. `move`는 아래 순서로 처리한다.
1. `rows`를 정렬하고 중복과 범위 밖 번호를 뺀다. 빈 리스트면 바로 `[]`를 돌려준다.
2. `before`를 0..n으로 제한한다.
3. `rest`(고르지 않은 줄)와 `at = before - (rows 중 before보다 작은 것의 수)`를 구한다.
4. `_apply(rest[:at] + rows + rest[at:], self.index)`를 부르고 `list(range(at, at + len(rows)))`를 돌려준다.

- [ ] **Step 4: 통과 확인** — Run: `.venv/Scripts/python.exe -m pytest -q` / Expected: 모두 PASS(1단계 테스트 포함)

- [ ] **Step 5: 커밋**

```bash
git add funplayer/core/playlist.py tests/test_playlist.py
git commit -m "Add play order, remove, dedupe, sort and move to Playlist"
```

---

### Task 5: 컨트롤러 — 반복·무작위와 상태 종류

**Files:**
- Modify: `funplayer/controller.py`
- Test: `tests/test_controller.py`

**Interfaces:**
- Consumes: `Settings.repeat`·`shuffle`·`REPEAT_MODES`(Task 1), `Playlist`(Task 4)
- Produces:
  - `PlayerController(player, settings, rng=None)`
    - 안에서 `Playlist(rng)`를 만들고 `playlist.set_shuffle(settings.shuffle)`을 부른다.
  - 속성:
    - `repeat -> str`: `settings.repeat`
    - `shuffle -> bool`: `settings.shuffle`
    - `status_error: bool`(속성, 처음엔 False)
  - `cycle_repeat()`: off → all → one → off 순서로 `settings.repeat`를 바꾼다.
  - `toggle_shuffle()`: `settings.shuffle`을 뒤집고 `playlist.set_shuffle(...)`를 부른다. 재생은 끊지 않는다.
  - `_wrap`(속성): `settings.repeat != "off"`
  - 바꾸는 곳:
    - `next()`, `prev()`, `play_index()`의 건너뛰기 반복에서 `next_index(self._wrap)`·`prev_target(…, self._wrap)`을 쓴다.
    - `on_track_end()`
      - 1단계의 STOPPED 검사를 먼저 한다.
      - 그다음 `repeat == "one"`이고 지금 곡이 있으면 `play_index(self.playlist.index)`, 아니면 `next()`다.
    - `open()`은 `play_index(0)` 대신 `play_index(self.playlist.index)`를 쓴다.
  - 상태 도우미:
    - `_set_status(msg: str, error: bool = False)`, `_info(msg)`, `_error(msg)`
    - 1단계에서 `self.status = …`로 쓰던 곳을 모두 이것으로 바꾼다.
    - 오류로 쓰는 메시지: `FAIL_MSG`, `NO_FILES_MSG`, `on_player_error`
    - 상태를 지우는 곳: `play_index` 시작, `clear()`

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_controller.py`에 더한다)

```python
import random

def make_ctl(store=None, rng=None):
    fake = FakePlayer(); store = {} if store is None else store
    return PlayerController(fake, Settings(store, lambda: None), rng=rng), fake, store

def test_cycle_repeat_saves(ctl):
    c, _, store = ctl; seen = []
    for _ in range(3):
        c.cycle_repeat(); seen.append(c.repeat)
    assert seen == ["all", "one", "off"] and store["player_repeat"] == "off"

def test_repeat_one_replays_on_end_only(ctl, tmp_path):
    c, fake, store = ctl; c.open([str(make_songs(tmp_path, ABC))]); store["player_repeat"] = "one"
    fake.finish(); c.on_track_end(); assert names(fake) == ["01 a.mp3", "01 a.mp3"]
    c.next(); assert names(fake)[-1] == "02 b.mp3"
    c.play_index(2); c.next(); assert names(fake)[-1] == "01 a.mp3"

def test_stale_end_ignored_with_repeat_one(ctl, tmp_path):
    c, fake, store = ctl; c.open([str(make_songs(tmp_path, ABC))]); store["player_repeat"] = "one"
    c.on_track_end(); assert len(fake.loaded) == 1

def test_repeat_all_wraps_both_ways(ctl, tmp_path):
    c, fake, store = ctl; c.open([str(make_songs(tmp_path, ABC))]); store["player_repeat"] = "all"
    fake.position = 1.0; c.prev(); assert names(fake)[-1] == "03 c.mp3"
    fake.finish(); c.on_track_end(); assert names(fake)[-1] == "01 a.mp3"
    c.play_index(2); c.next(); assert names(fake)[-1] == "01 a.mp3"

@pytest.mark.parametrize("shuffle", [False, True])
def test_repeat_all_with_all_failed_stops(tmp_path, shuffle):
    c, fake, _ = make_ctl({"player_repeat": "all", "player_shuffle": shuffle}, rng=random.Random(1))
    c.open([str(make_songs(tmp_path, ["01 bad.mp3", "02 bad.mp3", "03 bad.mp3"]))])
    assert c.state is State.STOPPED and len(fake.loaded) == 3

def test_shuffle_plays_every_track_once_then_stops(tmp_path):
    c, fake, _ = make_ctl({"player_shuffle": True}, rng=random.Random(5))
    songs = [f"{i:02} s.mp3" for i in range(8)]
    c.open([str(make_songs(tmp_path, songs))])
    for _ in range(7):
        fake.finish(); c.on_track_end()
    assert sorted(names(fake)) == songs and c.state is State.PLAYING
    fake.finish(); c.on_track_end(); assert c.state is State.STOPPED

def test_shuffle_with_repeat_all_starts_new_lap(tmp_path):
    c, fake, _ = make_ctl({"player_shuffle": True, "player_repeat": "all"}, rng=random.Random(5))
    c.open([str(make_songs(tmp_path, [f"{i:02} s.mp3" for i in range(4)]))])
    for _ in range(8):
        fake.finish(); c.on_track_end()
    got = names(fake)
    assert len(got) == 9 and sorted(got[4:8]) == sorted(got[:4]) and c.state is State.PLAYING

def test_shuffle_prev_returns_to_previous(tmp_path):
    c, fake, _ = make_ctl({"player_shuffle": True}, rng=random.Random(3))
    c.open([str(make_songs(tmp_path, [f"{i:02} s.mp3" for i in range(6)]))])
    c.next(); c.next(); fake.position = 1.0; c.prev()
    assert names(fake)[-1] == names(fake)[1]

def test_toggle_shuffle_saves_and_keeps_current(ctl, tmp_path):
    c, fake, store = ctl; c.open([str(make_songs(tmp_path, ABC))]); c.play_index(1)
    c.toggle_shuffle()
    assert store["player_shuffle"] is True and c.shuffle and c.playlist.order[0] == 1
    assert c.state is State.PLAYING and len(fake.loaded) == 2
    c.toggle_shuffle(); assert c.playlist.order == [0, 1, 2]

def test_shuffle_setting_applied_at_start():
    c, *_ = make_ctl({"player_shuffle": True}); assert c.playlist.shuffle

def test_status_kinds(ctl, tmp_path):
    c, *_ = ctl
    c.on_player_error("소리 장치를 열 수 없습니다"); assert c.status_error
    c.open([str(tmp_path / "none")]); assert c.status == NO_FILES_MSG and c.status_error
    c.open([str(make_songs(tmp_path / "m", ABC))]); assert (c.status, c.status_error) == ("", False)
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_controller.py -v` / Expected: 새 테스트 FAIL(`TypeError: unexpected keyword argument 'rng'` 등)

- [ ] **Step 3: 구현** (Interfaces대로)

- [ ] **Step 4: 통과 확인** — Run: `.venv/Scripts/python.exe -m pytest -q` / Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add funplayer/controller.py tests/test_controller.py
git commit -m "Add repeat and shuffle rules to the controller"
```

---

### Task 6: 컨트롤러 — 재생목록 파일과 목록 편집

**Files:**
- Modify: `funplayer/controller.py`
- Test: `tests/test_controller.py`

**Interfaces:**
- Consumes: `is_playlist`, `read_playlist`, `write_playlist`, `PLAYLIST_EXTS`(Task 2), `Playlist` 편집(Task 4)
- Produces:
  - 상수: `LOAD_FAIL_MSG = "불러올 수 없음: {name}"`, `SAVED_MSG = "저장했습니다: {name}"`, `SAVE_FAIL_MSG = "저장할 수 없음: {name}"`, `MISSING_MSG = "없는 파일 {n}곡"`, `DUP_MSG = "중복 곡 {n}개를 지웠습니다"`, `NO_DUP_MSG = "중복 곡이 없습니다"`, `REMOVED_MSG = "{n}곡을 지웠습니다"`, `NOTHING_REMOVED_MSG = "지울 곡이 없습니다"`
  - 모듈 로거: `logger = logging.getLogger(__name__)`
  - `open(paths)`·`add(paths)`: 재생목록 파일도 받는다(코드는 Step 3).
  - `save_playlist(path: str) -> None`
    - 확장자가 `PLAYLIST_EXTS`에 없으면 `.m3u8`을 붙인다.
    - `write_playlist`가 성공하면 `SAVED_MSG`(안내), `OSError`가 나면 로그를 남기고 `SAVE_FAIL_MSG`(오류)를 보여준다. `{name}`은 붙인 뒤의 파일 이름이다.
  - `remove(rows: list[int]) -> None`
    1. 지우기 전에 재생 중이었는지 기억한다.
    2. `result = playlist.remove(rows, wrap=self._wrap)`
    3. `result != "kept"`이면 `player.stop()` → `player.unload()`를 부른다.
    4. `result == "next"`이고 재생 중이었으면 `play_index(playlist.index)`를 부른다.
  - `remove_duplicates() -> None`, `remove_unplayable() -> None`
    1. 상태를 지운다.
    2. 지울 번호가 없으면 `NO_DUP_MSG`/`NOTHING_REMOVED_MSG`(안내)를 보여주고 끝낸다.
    3. 있으면 `remove(번호들)`을 부른다.
    4. 상태가 아직 비어 있으면 `DUP_MSG`/`REMOVED_MSG`(안내)를 보여준다.
  - `sort(by: str) -> None` → `playlist.sort(by)`
  - `move(rows: list[int], before: int) -> list[int]` → `playlist.move(rows, before)`

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_controller.py`에 더한다)

```python
from funplayer.core.m3u import read_playlist, write_playlist

def test_open_playlist_keeps_file_order_and_marks_missing(ctl, tmp_path):
    c, fake, _ = ctl; m = make_songs(tmp_path / "m", ABC); pl = tmp_path / "l.m3u8"
    write_playlist(str(pl), [str(m / "03 c.mp3"), str(m / "ghost.mp3"), str(m / "01 a.mp3")])
    c.open([str(pl)])
    assert [t.title for t in c.playlist.tracks] == ["03 c", "ghost", "01 a"]
    assert c.playlist.tracks[1].failed and names(fake) == ["03 c.mp3"]
    assert (c.status, c.status_error) == ("없는 파일 1곡", False)

def test_add_mixed_drop_music_first_then_playlist(ctl, tmp_path):
    c, *_ = ctl; m = make_songs(tmp_path / "m", ABC); pl = tmp_path / "l.m3u"
    write_playlist(str(pl), [str(m / "02 b.mp3")])
    c.add([str(pl), str(m / "03 c.mp3")])
    assert [t.title for t in c.playlist.tracks] == ["03 c", "02 b"]

def test_folder_scan_ignores_playlist_files(ctl, tmp_path):
    c, *_ = ctl; m = make_songs(tmp_path / "m", ABC); write_playlist(str(m / "l.m3u8"), [str(m / "01 a.mp3")])
    c.open([str(m)]); assert len(c.playlist) == 3

def test_unreadable_and_empty_playlist(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path / "m", ABC))])
    c.open([str(tmp_path / "none.m3u8")])
    assert len(c.playlist) == 3 and (c.status, c.status_error) == ("불러올 수 없음: none.m3u8", True)
    empty = tmp_path / "e.m3u8"; write_playlist(str(empty), [])
    c.add([str(empty)]); assert c.status == NO_FILES_MSG and len(c.playlist) == 3

def test_save_playlist(ctl, tmp_path):
    c, *_ = ctl; m = make_songs(tmp_path / "m", ABC); c.open([str(m)])
    c.save_playlist(str(tmp_path / "내 목록"))
    assert read_playlist(str(tmp_path / "내 목록.m3u8")) == [str(m / n) for n in ABC]
    assert (c.status, c.status_error) == ("저장했습니다: 내 목록.m3u8", False)
    c.save_playlist(str(tmp_path / "no" / "x.m3u8"))
    assert (c.status, c.status_error) == ("저장할 수 없음: x.m3u8", True)

@pytest.mark.parametrize("prep,playing_after", [("play", True), ("pause", False), ("stop", False)])
def test_remove_current(ctl, tmp_path, prep, playing_after):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    if prep == "pause": c.toggle()
    if prep == "stop": c.stop()
    c.remove([0])
    assert c.playlist.current.title == "02 b" and (c.state is State.PLAYING) is playing_after
    if playing_after:
        assert names(fake)[-1] == "02 b.mp3"
    else:
        assert not fake.has_track and names(fake) == ["01 a.mp3"]
        c.toggle(); assert names(fake)[-1] == "02 b.mp3" and c.state is State.PLAYING

def test_remove_other_keeps_playing(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    c.remove([2]); assert c.state is State.PLAYING and len(fake.loaded) == 1 and len(c.playlist) == 2

def test_remove_last_current_stops_on_previous(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))]); c.play_index(2)
    c.remove([2]); assert c.state is State.STOPPED and c.playlist.current.title == "02 b"

def test_remove_all_is_like_clear(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))]); c.remove([0, 1, 2])
    assert len(c.playlist) == 0 and not fake.has_track and c.title == EMPTY_TITLE

def test_remove_duplicates(ctl, tmp_path):
    c, *_ = ctl; m = make_songs(tmp_path, ABC); c.open([str(m)])
    c.add([str(m / "01 a.mp3"), str(m / "02 b.mp3")])
    c.remove_duplicates()
    assert len(c.playlist) == 3 and (c.status, c.status_error) == ("중복 곡 2개를 지웠습니다", False)
    c.remove_duplicates(); assert c.status == "중복 곡이 없습니다"

def test_remove_unplayable(ctl, tmp_path):
    c, fake, _ = ctl; m = make_songs(tmp_path, ["01 a.mp3", "02 bad.mp3", "03 c.mp3"]); c.open([str(m)])
    c.play_index(1)
    os.remove(m / "01 a.mp3")
    c.remove_unplayable()
    assert [t.title for t in c.playlist.tracks] == ["03 c"] and c.state is State.PLAYING
    assert (c.status, c.status_error) == ("2곡을 지웠습니다", False)
    c.remove_unplayable(); assert c.status == "지울 곡이 없습니다"

def test_sort_and_move_keep_playing(ctl, tmp_path):
    c, fake, _ = ctl; c.open([str(make_songs(tmp_path, ABC))])
    assert c.move([0], 3) == [2]
    assert [t.title for t in c.playlist.tracks] == ["02 b", "03 c", "01 a"]
    assert c.playlist.current.title == "01 a"
    c.sort("name"); assert [t.title for t in c.playlist.tracks] == ["01 a", "02 b", "03 c"]
    assert c.state is State.PLAYING and len(fake.loaded) == 1
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_controller.py -v` / Expected: 새 테스트 FAIL

- [ ] **Step 3: 구현** — 모으기와 열기·추가는 다음 코드와 같다.

```python
    def _collect(self, paths: list[str]) -> tuple[list[str], str | None]:
        """음악 파일(폴더 펼침, 1단계 정렬) 뒤에 재생목록 파일의 곡(파일 순서)을 붙인다."""
        found = expand_paths([p for p in paths if not is_playlist(p)])
        error = None
        for p in paths:
            if not is_playlist(p):
                continue
            try:
                found.extend(read_playlist(p))
            except OSError:
                logger.warning("playlist read failed: %s", p, exc_info=True)
                error = error or LOAD_FAIL_MSG.format(name=os.path.basename(p))
        return found, error

    def open(self, paths: list[str]) -> None:
        self._set_status("")
        found, error = self._collect(paths)
        if not found:
            self._error(error or NO_FILES_MSG)
            return
        self._player.stop()
        self.playlist.replace(found)
        missing = self._mark_missing(0)
        self.play_index(self.playlist.index)
        self._report_load(error, missing)

    def add(self, paths: list[str]) -> None:
        self._set_status("")
        found, error = self._collect(paths)
        if not found:
            self._error(error or NO_FILES_MSG)
            return
        was_stopped = self._player.state is State.STOPPED
        start = len(self.playlist)
        first = self.playlist.add(found)
        missing = self._mark_missing(start)
        if was_stopped and first is not None:
            self.play_index(first)
        self._report_load(error, missing)

    def _mark_missing(self, start: int) -> int:
        count = 0
        for i in range(start, len(self.playlist)):
            if not os.path.exists(self.playlist.tracks[i].path):
                self.playlist.mark_failed(i)
                count += 1
        return count

    def _report_load(self, error: str | None, missing: int) -> None:
        if self.status:
            return
        if error:
            self._error(error)
        elif missing:
            self._info(MISSING_MSG.format(n=missing))
```

나머지는 Interfaces대로 구현한다.

- [ ] **Step 4: 통과 확인** — Run: `.venv/Scripts/python.exe -m pytest -q` / Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add funplayer/controller.py tests/test_controller.py
git commit -m "Add playlist files and list editing to the controller"
```

---

### Task 7: 반복·무작위 단추, 아이콘, 상태 줄 색, 손잡이 테스트 보강

**Files:**
- Create: `funplayer/ui/icons.py`
- Test: `tests/test_icons.py`
- Modify: `funplayer/ui/player_panel.py`, `tests/test_panel_view.py`, `tests/test_panel_input.py`

**Interfaces:**
- Consumes: `controller.repeat`·`shuffle`·`cycle_repeat`·`toggle_shuffle`·`status_error`(Task 5)
- Produces (`icons.py`):
  - `OFF_COLOR = QColor("#5F6368")`
  - `repeat_icon(mode: str, color: QColor) -> QIcon`, `shuffle_icon(color: QColor) -> QIcon`
  - 아래 코드를 그대로 쓴다. 승인된 시안의 그림과 같다.

```python
from __future__ import annotations

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

OFF_COLOR = QColor("#5F6368")


def _begin(color: QColor) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(36, 36)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    return pm, p


def _arrow(path: QPainterPath, x: float, y: float, dx: int) -> None:
    path.moveTo(x - dx * 2.5, y - 2.5)
    path.lineTo(x, y)
    path.lineTo(x - dx * 2.5, y + 2.5)


def repeat_icon(mode: str, color: QColor) -> QIcon:
    pm, p = _begin(color)
    path = QPainterPath()
    path.moveTo(3.5, 10.5); path.lineTo(3.5, 7.5); path.quadTo(3.5, 5, 6, 5); path.lineTo(14, 5)
    _arrow(path, 14, 5, 1)
    path.moveTo(14.5, 7.5); path.lineTo(14.5, 10.5); path.quadTo(14.5, 13, 12, 13); path.lineTo(4, 13)
    _arrow(path, 4, 13, -1)
    p.drawPath(path)
    if mode == "one":
        f = QFont(p.font()); f.setPixelSize(7); f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(5, 5, 8, 8), Qt.AlignCenter, "1")
    p.end()
    return QIcon(pm)


def shuffle_icon(color: QColor) -> QIcon:
    pm, p = _begin(color)
    path = QPainterPath()
    path.moveTo(2, 5); path.lineTo(5, 5); path.cubicTo(9, 5, 9, 13, 13, 13); path.lineTo(16, 13)
    _arrow(path, 16, 13, 1)
    path.moveTo(2, 13); path.lineTo(5, 13); path.cubicTo(9, 13, 9, 5, 13, 5); path.lineTo(16, 5)
    _arrow(path, 16, 5, 1)
    p.drawPath(path)
    p.end()
    return QIcon(pm)
```

- Produces (`player_panel.py`):
  - 상수:
    - `ERROR_COLOR = "#B3261E"`, `INFO_COLOR = "#5F6368"`
    - `REPEAT_TIPS = {"off": "반복: 끔", "all": "반복: 전체", "one": "반복: 한 곡"}`
    - `SHUFFLE_TIPS = {False: "무작위: 끔", True: "무작위: 켬"}`
  - 단추:
    - `repeat_button`, `shuffle_button`: `QToolButton`, `setCheckable(True)`, 28×28, 아이콘 18px
    - 컨트롤 줄 순서: `[이전][재생][정지][다음]` + `addSpacing(8)` + `[반복][무작위]` + stretch + `[음소거][볼륨]`
    - `clicked`는 `cycle_repeat`·`toggle_shuffle`에 연결한다.
  - `refresh()`에서 하는 일:
    - 반복 단추: checked는 `mode != "off"`, 아이콘은 `repeat_icon(mode, 켜면 palette Highlight 색, 끄면 OFF_COLOR)`, 풍선 도움말은 `REPEAT_TIPS[mode]`
    - 무작위 단추도 같은 방식이다.
    - 아이콘은 `(mode, shuffle)`이 바뀌었을 때만 새로 만든다.
    - 상태 줄: `status_label.setStyleSheet(f"color: {ERROR_COLOR if c.status_error else INFO_COLOR};")`. 바뀌었을 때만 부른다.
    - 1단계 `_build`의 고정 빨강 스타일은 없앤다.
  - `SHORTCUTS`에 `("R", "cycle_repeat")`, `("S", "toggle_shuffle")`를 더한다. 패널 메서드 `cycle_repeat()`·`toggle_shuffle()`은 컨트롤러를 부른 뒤 `refresh()`한다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_icons.py
from PyQt5.QtGui import QColor
from funplayer.ui.icons import OFF_COLOR, repeat_icon, shuffle_icon

def test_icons_draw(qapp):
    blue = QColor("#308CC6")
    all_img, one_img = (repeat_icon(m, blue).pixmap(18, 18).toImage() for m in ("all", "one"))
    assert not all_img.isNull() and all_img != one_img
    assert repeat_icon("off", OFF_COLOR).pixmap(18, 18).toImage() != all_img
    assert not shuffle_icon(blue).pixmap(18, 18).isNull()
```

`tests/test_panel_view.py`에 더한다(import: `from funplayer.ui.player_panel import ERROR_COLOR, INFO_COLOR, PlayerPanel`).

```python
def test_repeat_and_shuffle_buttons(panel):
    p, _ = panel
    assert p.repeat_button.toolTip() == "반복: 끔" and not p.repeat_button.isChecked()
    p.repeat_button.click(); assert p.repeat_button.toolTip() == "반복: 전체" and p.repeat_button.isChecked()
    p.repeat_button.click(); assert p.repeat_button.toolTip() == "반복: 한 곡" and p.repeat_button.isChecked()
    p.repeat_button.click(); assert p.repeat_button.toolTip() == "반복: 끔" and not p.repeat_button.isChecked()
    p.shuffle_button.click()
    assert p.controller.shuffle and p.shuffle_button.isChecked() and p.shuffle_button.toolTip() == "무작위: 켬"
    p.shuffle_button.click(); assert not p.shuffle_button.isChecked()

def test_buttons_follow_saved_settings(qapp):
    p = PlayerPanel(Settings({"player_repeat": "one", "player_shuffle": True}, lambda: None), player=FakePlayer())
    try:
        assert p.repeat_button.toolTip() == "반복: 한 곡" and p.shuffle_button.isChecked()
    finally:
        p.shutdown(); p.deleteLater()

def test_status_color(panel, tmp_path):
    p, _ = panel
    p.controller.on_player_error("소리 장치를 열 수 없습니다"); p.refresh()
    assert ERROR_COLOR in p.status_label.styleSheet()
    p.controller.open([str(make_songs(tmp_path, ["01 a.mp3"]))]); p.controller.remove_duplicates(); p.refresh()
    assert p.status_label.text() == "중복 곡이 없습니다" and INFO_COLOR in p.status_label.styleSheet()
```

`tests/test_panel_input.py`에서 고치거나 더한다.
- `test_shortcut_table`의 집합에 `"R", "S"`를 더한다.
- `test_shortcuts_trigger`의 parametrize에 `("R", lambda p, f: p.controller.repeat == "all")`, `("S", lambda p, f: p.controller.shuffle)`를 더한다.
- 1단계의 `test_jump_slider_handle_click_keeps_value`를 지우고 아래 테스트로 바꾼다.

```python
def test_jump_slider_handle_edge_click_keeps_value(qapp):
    s = JumpSlider(Qt.Horizontal); s.setRange(0, 180000); s.resize(200, 20); s.show()
    s.setValue(90000)
    opt = QStyleOptionSlider(); s.initStyleOption(opt)
    handle = s.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, s)
    QTest.mouseClick(s, Qt.LeftButton, Qt.NoModifier, QPoint(handle.left() + 1, handle.center().y()))
    assert s.value() == 90000
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_icons.py tests/test_panel_view.py tests/test_panel_input.py -v` / Expected: 새 테스트 FAIL(`ModuleNotFoundError: funplayer.ui.icons`, `AttributeError: repeat_button`)

- [ ] **Step 3: 손잡이 테스트가 약하지 않은지 확인**
  1. `funplayer/ui/jump_slider.py`의 `if not handle.contains(event.pos()):` 검사를 잠시 빼서 항상 점프하게 만든다.
  2. `test_jump_slider_handle_edge_click_keeps_value`가 FAIL하는지 본다.
  3. 원래대로 되돌리고 PASS를 확인한다.
  4. 결과를 보고서에 적는다. 이 단계에서 `jump_slider.py`는 바뀌지 않아야 한다.

- [ ] **Step 4: 구현** (Interfaces대로)

- [ ] **Step 5: 통과 확인** — Run: `.venv/Scripts/python.exe -m pytest -q` / Expected: 모두 PASS

- [ ] **Step 6: 커밋**

```bash
git add funplayer/ui/icons.py funplayer/ui/player_panel.py tests/test_icons.py tests/test_panel_view.py tests/test_panel_input.py
git commit -m "Add repeat/shuffle buttons, status colors and a stronger handle-click test"
```

---

### Task 8: 목록 위젯 — 여러 줄 선택, 끌어 옮기기, 줄 갱신, Del·Enter·Ctrl+A, 오른쪽 클릭

**Files:**
- Create: `funplayer/ui/playlist_view.py`
- Test: `tests/test_playlist_view.py`
- Modify: `funplayer/ui/player_panel.py`, `tests/test_panel_input.py`, `tests/test_panel_view.py`

**Interfaces:**
- Consumes: `controller.remove`·`move`·`add`·`play_index`(Task 5·6), `Playlist.layout_version`(Task 4)
- Produces (`playlist_view.py`): 아래 코드를 그대로 쓴다. Review Focus 1번의 Qt 함정을 피하는 코드다.

```python
from __future__ import annotations

from PyQt5.QtCore import QMimeData, QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QAbstractItemView, QListWidget

ROWS_MIME = "application/x-myfun-rows"


class PlaylistView(QListWidget):
    """여러 줄 선택, 끌어서 옮기기, 파일 놓기. 줄을 직접 옮기지 않고 신호만 보낸다."""

    rowsMoved = pyqtSignal(list, int)   # 옮길 줄(오름차순), 놓을 자리(옛 번호 기준 0..n)
    filesDropped = pyqtSignal(list)     # 로컬 파일 경로

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

    def mimeTypes(self) -> list[str]:
        return [ROWS_MIME, "text/uri-list"]

    def mimeData(self, items) -> QMimeData:
        rows = sorted(self.row(i) for i in items)
        md = QMimeData()
        md.setData(ROWS_MIME, ",".join(map(str, rows)).encode("ascii"))
        return md

    def startDrag(self, supported_actions) -> None:
        # Qt 기본 startDrag는 MoveAction으로 끝나면 원래 줄을 지운다. 그래서 직접 끈다.
        items = self.selectedItems()
        if not items:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(items))
        drag.exec_(Qt.MoveAction)

    def drop_row(self, pos: QPoint) -> int:
        item = self.itemAt(pos)
        if item is None:
            return self.count()
        row = self.row(item)
        return row if pos.y() < self.visualItemRect(item).center().y() else row + 1

    @staticmethod
    def _rows(md) -> list[int]:
        if not md.hasFormat(ROWS_MIME):
            return []
        text = bytes(md.data(ROWS_MIME)).decode("ascii")
        return [int(x) for x in text.split(",") if x]

    @staticmethod
    def _paths(md) -> list[str]:
        return [u.toLocalFile() for u in md.urls() if u.isLocalFile()] if md.hasUrls() else []

    def _wanted(self, md) -> bool:
        return bool(self._rows(md) or self._paths(md))

    def dragEnterEvent(self, event) -> None:
        if self._wanted(event.mimeData()):
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._wanted(event.mimeData()):
            super().dragMoveEvent(event)
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        rows, paths = self._rows(md), self._paths(md)
        before = self.drop_row(event.pos())
        # 모델이 아무것도 넣거나 옮기지 않게 IgnoreAction으로 바꾼 뒤,
        # 끌기 표시와 자동 스크롤 정리만 부모에게 맡긴다.
        event.setDropAction(Qt.IgnoreAction)
        super().dropEvent(event)
        if rows:
            self.rowsMoved.emit(rows, before)
        elif paths:
            self.filesDropped.emit(paths)
```

- Produces (`player_panel.py`):
  - `playlist_view = PlaylistView()`
    - `rowsMoved` → `_rows_moved(rows, before)`: `new = controller.move(rows, before)` → `refresh()` → `select_rows(new)`
    - `filesDropped` → `controller.add(paths)` → `refresh()`
  - 줄 갱신:
    - `_style_item(item, i, track)`: 1단계 줄 글자(`"▶"`/공백, 번호, 제목), 굵게, 회색을 매번 설정한다. 굵기를 끄는 것과 글자색을 기본으로 되돌리는 것(`setData(Qt.ForegroundRole, None)`)까지 한다.
    - `_rebuild_list()`(1단계 그대로, 줄 모양은 `_style_item`으로)
    - `_repaint_rows()`(줄마다 `_style_item`만 다시 부른다)
    - `refresh()`
      - `layout_version`이 바뀌었거나 줄 수가 다르면 다시 만든다.
      - `version`만 바뀌었으면 줄 모양만 고친다.
  - 메서드:
    - `selected_rows() -> list[int]`: 오름차순
    - `select_rows(rows: list[int]) -> None`
      1. 선택을 지운다.
      2. 첫 줄을 `setCurrentRow(row, QItemSelectionModel.NoUpdate)`로 현재 줄로 만든다.
      3. 각 줄을 `setSelected(True)`로 고른다.
    - `remove_selected()`
      1. 고른 줄이 없으면 아무것도 하지 않는다.
      2. `controller.remove(rows)` → `refresh()`
      3. 줄이 남아 있으면 `select_rows([min(rows[0], count-1)])`
    - `play_selected()`: `currentRow() >= 0`이면 `controller.play_index(row)` → `refresh()`
    - `select_all()`: `playlist_view.selectAll()`
  - `self.actions: dict[str, QAction]` 시작. 이 Task에서 만드는 키는 다음과 같다.
    - `"play_selected"`(`재생\tEnter`)
    - `"remove"`(`선택한 곡 지우기\tDel`)
    - `"select_all"`(`전체 선택\tCtrl+A`)
  - `self.context_menu`(QMenu): 위 세 항목을 Global Constraints 순서대로, 구분선을 넣어 담는다.
    - `aboutToShow` → `_update_actions()`. 계획 결정 11번대로 켠다.
    - `playlist_view.setContextMenuPolicy(Qt.CustomContextMenu)`로 두고, `customContextMenuRequested`가 오면 `context_menu.exec_(playlist_view.viewport().mapToGlobal(pos))`를 부른다.
  - `SHORTCUTS`에 더한다: `("Delete", "remove_selected")`, `("Return", "play_selected")`, `("Enter", "play_selected")`, `("Ctrl+A", "select_all")`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_playlist_view.py
import os
from PyQt5.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt5.QtGui import QDropEvent
from PyQt5.QtWidgets import QAbstractItemView
from funplayer.ui.playlist_view import ROWS_MIME, PlaylistView

def make_view():
    v = PlaylistView(); v.resize(300, 200)
    for t in ["a", "b", "c"]:
        v.addItem(t)
    v.show(); return v

def drop(v, pos, mime, action=Qt.MoveAction):
    v.dropEvent(QDropEvent(QPointF(pos), action, mime, Qt.LeftButton, Qt.NoModifier))

def test_view_setup(qapp):
    v = PlaylistView()
    assert v.selectionMode() == QAbstractItemView.ExtendedSelection
    assert v.dragDropMode() == QAbstractItemView.DragDrop and v.dragEnabled() and v.acceptDrops()

def test_mime_carries_sorted_rows(qapp):
    v = make_view(); md = v.mimeData([v.item(2), v.item(0)])
    assert md.hasFormat(ROWS_MIME) and bytes(md.data(ROWS_MIME)).decode() == "0,2"

def test_drop_row(qapp):
    v = make_view(); r1 = v.visualItemRect(v.item(1))
    assert v.drop_row(r1.topLeft() + QPoint(3, 1)) == 1
    assert v.drop_row(QPoint(3, r1.bottom())) == 2
    assert v.drop_row(QPoint(3, 190)) == 3

def test_drop_emits_rows_moved_and_leaves_items(qapp):
    v = make_view(); got = []
    v.rowsMoved.connect(lambda rows, before: got.append((rows, before)))
    drop(v, v.visualItemRect(v.item(0)).topLeft() + QPoint(3, 1), v.mimeData([v.item(2)]))
    assert got == [([2], 0)] and [v.item(i).text() for i in range(v.count())] == ["a", "b", "c"]

def test_drop_files_emits_local_paths(qapp, tmp_path):
    v = make_view(); got = []
    v.filesDropped.connect(got.append)
    md = QMimeData(); md.setUrls([QUrl.fromLocalFile(str(tmp_path / "x.mp3")), QUrl("http://e.com/a.mp3")])
    drop(v, QPoint(5, 5), md, Qt.CopyAction)
    assert [[os.path.normpath(p) for p in paths] for paths in got] == [[str(tmp_path / "x.mp3")]]
    assert v.count() == 3
```

`tests/test_panel_input.py`에 더한다(1단계 import에 `QPoint`, `QPointF`, `QMimeData`, `QUrl`, `QDropEvent`가 이미 있다).

```python
def test_selection_survives_track_change(rig):
    p, *_ = rig; v = p.playlist_view
    v.item(2).setSelected(True); p.controller.next(); p.refresh()
    assert v.item(2).isSelected() and v.item(1).text().startswith("▶") and v.item(1).font().bold()
    assert not v.item(0).font().bold() and not v.item(0).text().startswith("▶")

def test_delete_removes_selected_and_selects_same_row(rig):
    p, fake, *_ = rig; v = p.playlist_view
    v.item(0).setSelected(True); v.item(1).setSelected(True)
    p.shortcuts["Delete"].activated.emit()
    assert [t.title for t in p.controller.playlist.tracks] == ["03 c"] and fake.loaded[-1].endswith("03 c.mp3")
    assert p.selected_rows() == [0]

def test_real_keys_in_list(rig):
    p, fake, *_ = rig; v = p.playlist_view; p.activateWindow()
    assert QTest.qWaitForWindowActive(p)
    v.setFocus(); v.setCurrentRow(2)
    QTest.keyClick(v, Qt.Key_Return); assert fake.loaded[-1].endswith("03 c.mp3")
    QTest.keyClick(v, Qt.Key_Delete); assert len(p.controller.playlist) == 2

def test_enter_and_select_all(rig):
    p, fake, *_ = rig; p.playlist_view.setCurrentRow(1)
    p.shortcuts["Return"].activated.emit(); assert fake.loaded[-1].endswith("02 b.mp3")
    p.shortcuts["Ctrl+A"].activated.emit(); assert p.selected_rows() == [0, 1, 2]

def test_context_menu(rig):
    p, fake, *_ = rig
    assert [a.text() for a in p.context_menu.actions()] == [
        "재생\tEnter", "선택한 곡 지우기\tDel", "", "전체 선택\tCtrl+A"]
    p.playlist_view.clearSelection(); p.context_menu.aboutToShow.emit()
    assert not p.actions["remove"].isEnabled()
    p.playlist_view.setCurrentRow(1); p.context_menu.aboutToShow.emit()
    assert p.actions["remove"].isEnabled() and p.actions["play_selected"].isEnabled()
    p.actions["play_selected"].trigger(); assert fake.loaded[-1].endswith("02 b.mp3")

def test_drag_rows_reorders_and_keeps_selection(rig):
    p, fake, *_ = rig; v = p.playlist_view
    at = v.visualItemRect(v.item(0)).topLeft() + QPoint(5, 2)
    v.dropEvent(QDropEvent(QPointF(at), Qt.MoveAction, v.mimeData([v.item(2)]), Qt.LeftButton, Qt.NoModifier))
    assert [t.title for t in p.controller.playlist.tracks] == ["03 c", "01 a", "02 b"]
    assert p.controller.playlist.index == 1 and p.selected_rows() == [0] and len(fake.loaded) == 1

def test_file_drop_on_list_adds(rig):
    p, _, _, tmp = rig; v = p.playlist_view
    song = make_songs(tmp / "d", ["05 d.mp3"]) / "05 d.mp3"
    mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(song))])
    v.dropEvent(QDropEvent(QPointF(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert len(p.controller.playlist) == 4
```

`test_shortcut_table`의 집합에 `"Delete", "Return", "Enter", "Ctrl+A"`를 더한다.

- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_playlist_view.py tests/test_panel_input.py tests/test_panel_view.py -v` / Expected: 새 테스트 FAIL

- [ ] **Step 3: 구현** (Interfaces대로)

- [ ] **Step 4: 통과 확인** — Run: `.venv/Scripts/python.exe -m pytest -q` / Expected: 모두 PASS. 1단계의 `test_list_not_rebuilt_without_change`, `test_scroll_kept_on_rebuild`도 PASS여야 한다.

- [ ] **Step 5: 커밋**

```bash
git add funplayer/ui/playlist_view.py funplayer/ui/player_panel.py tests/test_playlist_view.py tests/test_panel_input.py tests/test_panel_view.py
git commit -m "Add multi-select playlist view with drag reorder, Del, Enter and context menu"
```

---

### Task 9: 메뉴 — 재생목록 열기·추가·저장, [목록] 메뉴, [비우기] 옮기기

**Files:**
- Modify: `funplayer/ui/player_panel.py`, `tests/test_panel_input.py`

**Interfaces:**
- Consumes: `controller.open`·`add`·`save_playlist`·`remove_duplicates`·`remove_unplayable`·`sort`·`clear`(Task 5·6), `self.actions`·`_update_actions`(Task 8)
- Produces:
  - 아래 줄: `open_button`, `add_button`, `list_button`(`목록`), stretch, `count_label`. `clear_button`은 없앤다.
  - `_make_menu(button, items: list[tuple[str, callable]]) -> QMenu`
    - [열기]: `파일…\tL`→`open_files`, `폴더…`→`open_folder`, `재생목록…\tCtrl+O`→`open_playlist`
    - [추가]: `파일…`→`add_files`, `폴더…`→`add_folder`, `재생목록…`→`add_playlist`
  - `self.list_menu`(= `list_button.menu()`)에 다음 `self.actions` 항목을 Global Constraints 순서대로 넣는다.
    - `"save"` → `save_playlist`
    - Task 8의 `"remove"`(같은 QAction)
    - `"dedupe"` → `remove_duplicates`
    - `"remove_unplayable"` → `remove_unplayable`
    - 하위 메뉴 `정렬`: `"sort_name"` → `sort_by("name")`, `"sort_path"` → `sort_by("path")`
    - `"clear"` → `clear_list`(1단계 `_clear`의 새 이름)
    - `aboutToShow`는 `_update_actions()`에 연결한다.
  - 대화상자(테스트에서 바꿔 끼운다):
    - `ask_playlist_open() -> str`: `QFileDialog.getOpenFileName(self, "재생목록 열기", "", "재생목록 (*.m3u8 *.m3u)")[0]`
    - `ask_playlist_save() -> str`: `QFileDialog.getSaveFileName(self, "재생목록 저장", "재생목록.m3u8", "재생목록 (*.m3u8)")[0]`
  - 메서드:
    - `open_playlist()`·`add_playlist()`: 경로가 있으면 `controller.open([path])`·`add([path])` → `refresh()`
    - `save_playlist()`: 곡이 없으면 아무것도 하지 않는다. 경로가 있으면 `controller.save_playlist(path)` → `refresh()`
    - `remove_duplicates()`, `remove_unplayable()`, `sort_by(by)`, `clear_list()`: 컨트롤러를 부르고 `refresh()`
  - `SHORTCUTS`에 `("Ctrl+S", "save_playlist")`, `("Ctrl+O", "open_playlist")`를 더한다.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_panel_input.py`)

1단계 테스트 두 곳을 고친다.
- `test_buttons`의 `QTest.mouseClick(p.clear_button, Qt.LeftButton)`을 `p.actions["clear"].trigger()`로 바꾼다.
- `test_menus`의 첫 assert를 `assert [a.text() for a in p.open_button.menu().actions()][:2] == ["파일…\tL", "폴더…"]`로 바꾼다.

`test_shortcut_table`의 집합은 최종적으로 다음과 같다.

```python
    assert set(p.shortcuts) == {"Space", "X", "V", "Z", "B", "Left", "Right", "Up", "Down", "M", "L",
                                "R", "S", "Ctrl+S", "Ctrl+O", "Delete", "Return", "Enter", "Ctrl+A"}
```

더하는 테스트:

```python
def test_bottom_row_and_menus(rig):
    p, *_ = rig
    assert not hasattr(p, "clear_button") and p.list_button.text() == "목록"
    assert [a.text() for a in p.open_button.menu().actions()] == ["파일…\tL", "폴더…", "재생목록…\tCtrl+O"]
    assert [a.text() for a in p.add_button.menu().actions()] == ["파일…", "폴더…", "재생목록…"]
    assert [a.text() for a in p.list_menu.actions()] == [
        "저장…\tCtrl+S", "", "선택한 곡 지우기\tDel", "중복 곡 지우기", "없는·깨진 파일 지우기", "정렬", "", "목록 비우기"]
    assert [a.text() for a in p.list_menu.actions()[5].menu().actions()] == ["이름순", "폴더·이름순"]

def test_save_and_open_playlist_with_keys(rig, monkeypatch):
    p, fake, _, tmp = rig
    monkeypatch.setattr(p, "ask_playlist_save", lambda: str(tmp / "목록"))
    p.shortcuts["Ctrl+S"].activated.emit()
    assert (tmp / "목록.m3u8").exists() and p.status_label.text() == "저장했습니다: 목록.m3u8"
    p.actions["clear"].trigger(); assert len(p.controller.playlist) == 0
    monkeypatch.setattr(p, "ask_playlist_open", lambda: str(tmp / "목록.m3u8"))
    p.shortcuts["Ctrl+O"].activated.emit()
    assert [t.title for t in p.controller.playlist.tracks] == ["01 a", "02 b", "03 c"]

def test_add_playlist_menu(rig, monkeypatch):
    p, _, _, tmp = rig
    p.controller.save_playlist(str(tmp / "l.m3u8"))
    monkeypatch.setattr(p, "ask_playlist_open", lambda: str(tmp / "l.m3u8"))
    p.add_button.menu().actions()[2].trigger(); assert len(p.controller.playlist) == 6

def test_save_skipped_when_cancelled_or_empty(rig, monkeypatch):
    p, *_ = rig; asked = []
    monkeypatch.setattr(p, "ask_playlist_save", lambda: asked.append(1) or "")
    p.save_playlist(); assert asked == [1] and p.controller.status == ""
    p.actions["clear"].trigger(); p.save_playlist(); assert asked == [1]
    p.list_menu.aboutToShow.emit(); assert not p.actions["save"].isEnabled()

def test_list_menu_edit_actions(rig):
    p, *_ = rig
    p.playlist_view.clearSelection(); p.list_menu.aboutToShow.emit()
    assert p.actions["save"].isEnabled() and not p.actions["remove"].isEnabled()
    p.actions["sort_path"].trigger(); p.actions["dedupe"].trigger()
    assert p.status_label.text() == "중복 곡이 없습니다"
    p.actions["remove_unplayable"].trigger(); assert p.status_label.text() == "지울 곡이 없습니다"
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python.exe -m pytest tests/test_panel_input.py -v` / Expected: 새 테스트와 고친 테스트 FAIL

- [ ] **Step 3: 구현** (Interfaces대로)

- [ ] **Step 4: 통과 확인** — Run: `.venv/Scripts/python.exe -m pytest -q` / Expected: 모두 PASS(MP3 인코더가 없으면 1개 SKIP)

- [ ] **Step 5: 커밋**

```bash
git add funplayer/ui/player_panel.py tests/test_panel_input.py
git commit -m "Add playlist open/add/save menus and the list menu"
```

---

### Task 10: 실제 화면 확인과 도장 (컨트롤러가 직접 한다)

**Files:**
- Create: `docs/images/stage2a_real.png`
- Modify: `docs/개발로드맵.md` §3, §9 (Step 5)

- [ ] **Step 1: 실제 화면 캡처**
  - 스크래치 패드의 `real_stage1.py`를 본떠 `real_stage2a.py`를 만든다.
  - 시안과 같은 상태로 offscreen에서 `docs/images/stage2a_real.png`로 캡처한다.
    - 반복은 전체, 무작위는 켬이다.
    - 두 줄을 골라 둔다.
    - 상태 줄에 회색 안내 하나를 띄운다.

- [ ] **Step 2: 확인 페이지 갱신**
  - 기존 artifact 페이지(같은 파일 경로)에 시안과 실제 화면을 나란히 놓는다.
  - spec §7의 사용자 체크리스트를 체크 상자로 넣는다(localStorage, try/catch).

- [ ] **Step 3: 사용자 확인 요청** — `run.bat`로 spec §7 체크리스트를 확인해 달라고 한다. **결과를 받을 때까지 다음 단계로 가지 않는다.**

- [ ] **Step 4: 실패 항목이 있으면** superpowers:systematic-debugging으로 원인을 찾는다. 고친 것은 따로 커밋하고, 다시 확인을 부탁한다.

- [ ] **Step 5: 통과하면 도장**
  - §3에서 B-7, B-8, C-5, C-6을 `☑ 날짜`로 바꾼다. J-1 줄에는 2-A분을 메모한다.
  - §9의 2-A를 완료로 바꾸고, 마지막 커밋 해시를 적는다.
  - `git add docs/개발로드맵.md docs/images/stage2a_real.png` 후 커밋한다: `Mark stage 2-A complete`
  - 이 계획의 작업 폴더(`.superpowers/sdd/…`)를 지운다.
  - superpowers:finishing-a-development-branch로 로컬 `main`에 합친다(push 없음).
