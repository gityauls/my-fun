# Stage 5-A: Track Info Editing and MusicBrainz Lookup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The track info dialog edits title/artist/album/year/genre/track and the cover of MP3 files, fills missing values from MusicBrainz on demand, and can clear all tags — saving safely even while the file is playing.

**Architecture:** Qt-free pieces first: `core/tagguess.py` (file-name guess), `engine/tagwrite.py` (mutagen, copy→write→verify→replace), `musicbrainz.py` (urllib with injectable fetch, 1 s spacing). The controller wraps writes with unload/reload of the playing file. `ui/info_dialog.py` becomes an editor that asks the panel to save and runs network calls through the panel's `QtRunner.run_async`.

**Tech Stack:** Python 3.13/3.14, PyQt5 5.15.11, PyAV 19.0.2 (reading), mutagen 1.47.0 (writing, newly approved), pytest.

**Spec:** `docs/stage5a_design.md` (mockup approved 2026-10-31). Mockup `docs/images/stage5a_mockup.png`. Base: main `bbad79e` + spec commit.

## Global Constraints

- Only new dependency: `mutagen==1.47.0` (add to requirements.txt). Never import PySide6. `from __future__ import annotations` in every module (tests/test_layering.py). `core/`, `engine/`, `controller.py`, `radio.py`, `musicbrainz.py` are Qt-free — add `musicbrainz.py` to the Qt-free list in tests/test_layering.py.
- Tests never touch the network or a real audio device. MusicBrainz tests use a fake fetch and a fake clock.
- MusicBrainz User-Agent exactly `my-fun/0.5 ( personal music player )`; never send the user's email or other personal data. ≥1.0 s between MusicBrainz API calls, timeout 10 s.
- Exact copy (spec §2–§5): menu `곡 정보 고치기…`; window title `곡 정보`; buttons `그림 넣기…`, `빼기`, `태그 모두 지우기…`, `폴더 열기`, `저장`, `닫기`, `찾기`, `고른 곡으로 채우기`, `지우기`, `그만두기`; checkbox `빈 칸만 채우기` (default on); section `인터넷에서 찾기` + gray `(MusicBrainz)`; notes `MP3만 고칠 수 있습니다`, `파일이 없습니다`, `노란 칸 = 바뀐 값 (아직 저장 안 됨)`, `저장했습니다`, `저장 안 한 내용이 있습니다. 버릴까요?`, `태그와 그림을 모두 지웁니다. 소리는 그대로입니다.`; status texts and error texts exactly as spec §3, §4, §5.1.
- Colors: changed field `#FFF6D6`, changed cover border 2 px `#E8B400`, note `#8A6D00` — put them in `funplayer/ui/colors.py`.
- Genre list exactly spec §3. Picture: jpg/png magic bytes only, ≤10 MB.
- Writes: ID3v2.3, UTF-16 text (encoding=1), ID3v1 removed, APIC type 3; unknown frames preserved; temp file `.{name}.myfun-tmp` in the same folder; original untouched on any failure; temp file never left behind.

## Review Focus

1. Saving the file that is playing (and paused, and cued/stopped) — position and play state come back; a failed write still reloads the original. (Task 3 `test_save_playing_reloads_at_position`, `test_failed_save_still_reloads`.)
2. Read-only / locked files and verify failures leave the original byte-identical and no temp file behind. (Task 1 `test_readonly_untouched`, `test_verify_failure_untouched`.)
3. Korean text round-trip: written tags read back through PyAV `read_info` unchanged (no CP949 mangling via fix_text), ID3v1 gone. (Task 1 `test_korean_roundtrip`.)
4. A late MusicBrainz reply after the dialog moved to another track is ignored; network errors show the red text and don't crash. (Task 5 `test_late_reply_ignored`, `test_search_error_text`.)
5. Unsaved edits are not lost silently: closing or opening another track asks first. (Task 4 `test_close_dirty_asks`.)

---

### Task 1: File-name guess and tag writer

**Files:** create `funplayer/core/tagguess.py`, `funplayer/engine/tagwrite.py`; modify `requirements.txt`; tests `tests/test_tagguess.py`, `tests/test_tagwrite.py` (use `tone_mp3` copied into tmp_path and `tests/tagfiles.py` helpers).

**Interfaces (produces):**
- `guess_from_filename(path: str) -> tuple[str, str]` (artist, title) per spec §4.1.
- `KEEP`, `REMOVE` sentinels; `class TagWriteError(Exception)` (message = Korean reason per spec §5.1).
- `FIELDS = ("title", "artist", "album", "year", "genre", "track")`.
- `picture_mime(data: bytes) -> str | None` ("image/jpeg" / "image/png" / None).
- `write_tags(path: str, fields: dict[str, str], picture: bytes | object = KEEP, verify=None) -> None` — missing keys in `fields` = leave as is; `""` = delete frame. Frames: TIT2, TPE1, TALB, TYER (v2.3 year), TCON, TRCK.
- `clear_tags(path: str, verify=None) -> None`.
- `verify` (tests inject): `Callable[[str], bool]`; default reads with `funplayer.engine.tags.read_info` and checks `duration > 0` (and title equals when written).

- [ ] **Step 1: Failing tests:** tagguess cases `[서지원] I Miss You.mp3`→(서지원, I Miss You); `(홍대클럽)Benny Benassi - I Love My Sex(노래진짜좋음) - 클럽음악.mp3`→(Benny Benassi, I Love My Sex); `가수 - 제목.mp3`; `그냥제목.mp3`→("", 그냥제목); `""`→("",""). tagwrite: `test_korean_roundtrip` (title `그대향기`, artist `유영진` → read_info same; mutagen shows no ID3v1); `test_empty_deletes`; `test_picture_add_keep_remove`; `test_unknown_frame_kept` (USLT survives); `test_not_mp3` (wav → TagWriteError `MP3만 고칠 수 있습니다`); `test_readonly_untouched` (chmod read-only → error text per spec, bytes identical, no `.myfun-tmp` file); `test_verify_failure_untouched` (verify=lambda p: False); `test_clear_tags`; `test_picture_mime`.
- [ ] **Steps 2–5:** fail → implement → pass + full suite → commit "Add tag writer and file-name guess" (include requirements.txt).

### Task 2: MusicBrainz client

**Files:** create `funplayer/musicbrainz.py`; modify `tests/test_layering.py` (Qt-free list); tests `tests/test_musicbrainz.py`.

**Interfaces (produces):**
- `@dataclass(frozen=True) Candidate: title, artist, album, year, track, genre, release_id: str` and `label() -> str` = `제목 · 가수 · 앨범 · 년도` skipping empty parts.
- `class MusicBrainzError(Exception)` with Korean message: network → `인터넷에 연결하지 못했습니다`; HTTP 503 → `MusicBrainz가 바쁩니다. 잠시 뒤 다시 눌러 보세요`.
- `class Client(fetch=None, clock=time.monotonic, sleep=time.sleep)`: `search(title: str, artist: str, limit: int = 10) -> list[Candidate]`; `cover(release_id: str) -> bytes | None` (404 → None). `fetch(url, headers) -> bytes` raises `urllib.error.HTTPError`/`URLError`/`TimeoutError` like urllib; default uses `urllib.request` with timeout 10 and the UA header. Spacing ≥1.0 s between `search` calls (sleep the difference); module-level `default_client()` returns one shared instance.
- Query exactly spec §4.2; escape `\` and `"` with a backslash; URL-encode with `urllib.parse.quote`.

- [ ] **Step 1: Failing tests:** `test_query_and_headers` (records url+UA; with and without artist; escaping); `test_parse_candidates` (fixture JSON with 2 recordings × releases → year from date, track number from media track, genre = max-count tag, ≤ limit); `test_spacing` (fake clock/sleep: second call sleeps 1.0 − elapsed); `test_errors` (URLError → network text; HTTPError 503 → busy text); `test_cover_404_none`, `test_cover_bytes`; `test_label_skips_empty`.
- [ ] **Steps 2–5:** fail → implement → pass + full suite → commit "Add MusicBrainz client".

### Task 3: Controller save/clear

**Files:** modify `funplayer/controller.py`, `tests/fakes.py` (FakePlayer records `load`/`unload`/`seek`/`play` calls if not already); tests `tests/test_controller.py`.

**Interfaces (produces):**
- `PlayerController.save_tags(path: str, fields: dict[str, str], picture=KEEP) -> TrackInfo` and `clear_tags(path: str) -> TrackInfo` per spec §5.2. Writer functions injectable via constructor kwargs `write_tags=None, clear_tags=None` (default from engine.tagwrite) so tests use fakes.
- After either: info cache cleared, `_synced_key = None`, `sync_effects()` called; returns `self._read_info(path)`.

- [ ] **Step 1: Failing tests:** `test_save_playing_reloads_at_position` (playing at 42.0 → calls unload, write, load(path), seek(42.0), play in order); `test_save_paused_stays_paused`; `test_save_other_file_no_reload`; `test_failed_save_still_reloads` (writer raises TagWriteError → reload happens, error propagates); `test_save_resyncs_genre` (auto on, genre Rock→Ballad via injected read_info → player gets 발라드 bands); `test_clear_tags_reloads`.
- [ ] **Steps 2–5:** fail → implement → pass + full suite → commit "Controller saves tags around the playing file".

### Task 4: Editable info dialog (fields, picture, clear, dirty)

**Files:** modify `funplayer/ui/info_dialog.py`, `funplayer/ui/colors.py`; tests `tests/test_info_dialog.py`.

**Interfaces (produces):**
- `TrackInfoDialog(parent=None)`; `show_info(info, cover, editable: bool, note: str = "")` (non-editable = today's read-only look + gray note); public parts `edits: dict[str, QLineEdit | QComboBox]` keyed by `title/artist/album/year/genre/track`, `pick_button`, `remove_pic_button`, `clear_button`, `save_button`, `close_button`, `folder_button`, `message_label`, `confirm_bar` (with `confirm_button`, `cancel_button`).
- Signals: `save_requested(str, dict, object)` (path, changed fields only, picture KEEP/REMOVE/bytes) and `clear_requested(str)`. The panel answers with `saved(info, cover)` (dialog method: reload values, gray `저장했습니다`) or `failed(message)` (red text, values kept).
- `is_dirty() -> bool`; `confirm_discard() -> bool` (QMessageBox.question; tests monkeypatch). `closeEvent` and `show_info` (when switching to another path) call it when dirty.
- Picture: `set_picture_bytes(data: bytes) -> bool` (validates mime/size, shows red text on failure); file dialog via `QFileDialog.getOpenFileName` (monkeypatched in tests); drag-and-drop of one local jpg/png file.

- [ ] **Step 1: Failing tests:** `test_changed_field_yellow_and_save_enabled`; `test_revert_disables_save`; `test_save_emits_changed_only` (strips spaces); `test_picture_bytes_checked` (gif bytes → red `jpg·png 그림만 넣을 수 있습니다`; >10 MB → red size text); `test_remove_picture_marks_remove`; `test_close_dirty_asks` (no → stays open; yes → closes); `test_clear_confirm_bar` (button shows bar; 지우기 emits clear_requested; 그만두기 hides); `test_readonly_modes` (radio/non-mp3/missing: edits read-only, buttons hidden, note text); `test_saved_resets_dirty`.
- [ ] **Steps 2–5:** fail → implement → pass + full suite → commit "Info dialog edits tags and cover".

### Task 5: Search section and panel wiring

**Files:** modify `funplayer/ui/info_dialog.py`, `funplayer/ui/player_panel.py`; tests `tests/test_info_dialog.py`, `tests/test_panel_view.py` (or a new `tests/test_panel_tags.py`); docs `CLAUDE.md` (file list), `docs/개발로드맵.md` §5 structure lines (no stamping).

**Interfaces/rules:**
- Dialog gets `set_services(run_async, client_factory)`; search section per spec §4 (collapsed by default; prefill from tags else `guess_from_filename`; Enter in a field = 찾기; results QListWidget; fill rules with `빈 칸만 채우기`; cover fetched only when the track has no picture or the box is off; status/error texts; request token so late replies for another path/request are dropped).
- Panel: context-menu text `곡 정보 고치기…`; `_show_info` passes `editable` (file source, existing `.mp3` path) and note; connects `save_requested`/`clear_requested` → `controller.save_tags/clear_tags` → `dialog.saved(info, load_cover(info))` or `dialog.failed(str(e))`, then `refresh()` (cover key reset so the big cover updates).
- [ ] **Step 1: Failing tests:** dialog — `test_prefill_from_tags_then_filename`; `test_search_lists_and_fills_empty_only` (fake run_async runs inline; fake client); `test_fill_overwrites_when_box_off`; `test_cover_fetched_only_when_missing`; `test_late_reply_ignored`; `test_search_error_text`. panel — `test_menu_text`; `test_save_updates_subtitle_and_cover` (FakePlayer + injected writer/read_info); `test_radio_info_readonly`.
- [ ] **Steps 2–5:** fail → implement → pass; full suite twice → commit "Panel: edit track info and search MusicBrainz".

### Task 6: Real check (controller)

- Real panel offscreen + real device on copies of Test-mp3 songs in scratchpad (never the user's originals): write Korean tags + cover while playing (position kept), read back with PyAV and mutagen, clear tags, one live MusicBrainz search for a known song (user-triggered equivalent; one request) and cover fetch. Capture `docs/images/stage5a_real.png`. Update the artifact page to the 5-A check page with spec §8. Stop at the user checklist gate.
