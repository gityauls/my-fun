# Stage 5-C: Genie/Melon Browser Search, Picture Paste, Safe File Rename — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The track info dialog opens Genie/Melon searches in the browser, takes covers by Ctrl+V or browser drag, and can rename the file to `가수 - 제목.ext` on save (opt-in, never overwriting, undoable).

**Architecture:**
- **Qt-free pieces:**
  - `core/renamer.py`: name rules, conflict check, rename, undo log.
  - `websearch.py`: search URLs, single image download.
  - `Playlist.rename_path`.
  - `Settings.rename_on_save`.
- **Controller:** gains `save_and_rename` / `undo_rename`. These reuse the 5-A unload → write → reload path and update the playlist and `last_track`.
- **Dialog:** gets the new rows and signals.
- **Panel:** wires the dialog, settings, context menu and log path.

**Tech Stack:** Python 3.13/3.14, PyQt5 5.15.11, mutagen 1.47.0, pytest. No new dependencies.

**Spec:** `docs/stage5c_design.md` (mockup `docs/images/stage5c_mockup.png`, approved 2026-10-31). Base: branch `stage5c` off `stage5a` `96ab88f`.

## Global Constraints

- **Dependencies:** none new. Never import PySide6. `from __future__ import annotations` in every module.
- **Qt-free modules:** `core/renamer.py` and `websearch.py`. Add `websearch.py` to the Qt-free list in `tests/test_layering.py`.
- **Tests:**
  - No network, no real browser, no real audio device.
  - Fake `fetch`, fake `open_url`, fake player as in the existing tests.
  - The user's `Test-mp3` files are never touched. Tests use `tmp_path` copies (`tone_mp3` fixture).
  - Run with `-W error::SyntaxWarning`. Use raw strings for regexes and Windows paths.
- **Copy:**
  - All user-visible text exactly as spec §2–§5 (table in §5, error texts §4.3/§4.4).
  - New color `RENAME_OK_COLOR = "#1E7B34"` in `funplayer/ui/colors.py`. Errors use the existing `ERROR_COLOR`, notes `NOTE_COLOR`, gray `INFO_COLOR`.
- **Network:**
  - Image download User-Agent is `musicbrainz.USER_AGENT` exactly.
  - Timeout 10 s, cap 10 MB, `http`/`https` only.
  - The app never requests genie.co.kr or melon.com itself.
- **Rename safety:**
  - Use `os.rename` only (never `os.replace`).
  - Check for a conflict before writing anything.
  - Rename only within the same folder, keeping the original extension text.
  - Never write to the user's `.m3u` files.

## Review Focus

1. **Renaming the playing/paused file.** It comes back on the new path at the same position and state. On a rename failure it comes back on the old path. (Task 3 `test_rename_playing_reloads_new_path`, `test_rename_failure_reloads_old_path`.)
2. **Conflicts.** An existing different file at the target means nothing is written: the tags stay byte-identical. A case-only rename is allowed. (Task 1 `test_case_only_not_conflict`, Task 3 `test_conflict_writes_nothing`.)
3. **Duplicate rows and session state.** Duplicate playlist rows of the same file (different case) all follow the rename, and `last_track` follows. (Task 1 `test_rename_path_all_rows_casefold`, Task 3 `test_rename_updates_last_track`.)
4. **Ctrl+V inside a text field.** With text on the clipboard it still pastes text. With an image it sets the cover and the field text is unchanged. (Task 4 `test_ctrl_v_text_in_field_pastes_text`, `test_ctrl_v_image_in_field_sets_cover`.)
5. **Pending rename vs discard prompt.** A pending rename alone enables `[저장]` but does not trigger the discard prompt. (Task 4 `test_pending_rename_not_dirty`.)

---

### Task 1: Name rules, rename, undo log, playlist and setting

**Files:**
- Create `funplayer/core/renamer.py`.
- Modify `funplayer/core/playlist.py` and `funplayer/core/settings.py`.
- Tests: `tests/test_renamer.py`, plus additions to `tests/test_playlist.py` and `tests/test_settings.py`.

**Interfaces (produces):**
- **Constants:** `MAX_NAME = 150`, `MAX_PATH = 259`, `MAX_LOG = 200`.
- `clean_part(s: str) -> str`: applies the spec §4.2 cleanup to one part (invalid/control chars → `_`, whitespace runs → one space, strip, trailing `.`/spaces removed).
- `build_name(artist: str, title: str, ext: str, dir_len: int = 0) -> str`:
  - Returns `"{a} - {t}{ext}"`, or `""` if either cleaned part is empty.
  - Adds the reserved-name `_` suffix.
  - Truncates the title so that `len(name) <= MAX_NAME` and `dir_len + 1 + len(name) <= MAX_PATH`, then strips trailing `.`/spaces again. Returns `""` if the title becomes empty.
- `target_path(path: str, artist: str, title: str) -> str | None`:
  - Same directory and original extension.
  - Returns `None` if no name can be built. Returns `path` itself, unchanged, when the built name equals the current basename exactly.
- `same_file(a: str, b: str) -> bool`: compares `os.path.normcase(os.path.abspath(...))`.
- `conflict(old: str, new: str) -> bool`: `os.path.exists(new) and not same_file(old, new)`.
- **Errors:** `class RenameError(Exception)` and `class RenameConflict(RenameError)`.
- `rename_file(old: str, new: str) -> None`: raises `RenameConflict` if `conflict(old, new)`, then calls `os.rename(old, new)`. An `OSError` becomes `RenameError` (chained).
- `class RenameLog(path: str | None, clock=time.time)`:
  - Methods: `add(old, new)`, `last() -> tuple[str, str] | None`, `pop() -> None` (removes the last entry).
  - File format: UTF-8 lines `ISO-seconds\told\tnew`, keeping only the last `MAX_LOG`. Malformed lines are ignored.
  - Writes go through a temp file + `os.replace`.
  - `path=None` keeps the log in memory only. A missing file means an empty log.
- `Playlist.rename_path(old: str, new: str) -> int`: every track whose path normcase-equals `old` gets `path = new`. Returns the count and bumps `version` (not `layout_version`) when the count is > 0.
- `Settings.rename_on_save: bool`: key `player_rename_on_save`, default `False`. Non-bool values read as `False`.

- [ ] **Step 1: Write failing tests.**
  - `test_clean_part_invalid_chars`: `clean_part('AC/DC: "Live"?') == "AC_DC_ _Live__"`.
  - `test_clean_part_control_and_spaces`: `clean_part(" a\t\x01  b. ") == "a__ b"`. Tab and `\x01` are control chars → `_` each; space runs collapse to one; trailing `.` stripped.
  - `test_build_name_basic`: `build_name("서지원", "I Miss You", ".mp3") == "서지원 - I Miss You.mp3"`.
  - `test_build_name_empty_part`: `build_name("", "x", ".mp3") == ""` and `build_name("a", "  ", ".mp3") == ""`.
  - `test_is_reserved`: helper `is_reserved(stem)`: `"nul"`, `"COM3"`, `"lpt9"` → True; `"COM10"`, `"a - b"` → False. `build_name` appends `_` to the stem when `is_reserved(stem)` (a guard; the `a - t` pattern rarely hits it).
  - `test_build_name_truncates`: a 300-char title → `len(name) == 150`, ending `.mp3`. With `dir_len=200` → `200 + 1 + len(name) <= 259`.
  - `test_target_path_same_name_returns_path`.
  - `test_target_path_keeps_ext_case`: `X.MP3` → `... .MP3`.
  - `test_case_only_not_conflict`: in `tmp_path`, `a.mp3` → `A.mp3` gives `conflict() is False`, and `rename_file` works (the listing shows `A.mp3`).
  - `test_conflict_existing_other_file`: `rename_file` raises `RenameConflict`, and both files are unchanged.
  - `test_rename_oserror_wrapped`: monkeypatch `os.rename` to raise `PermissionError` → `RenameError`.
  - `test_log_roundtrip_and_cap`: add 205 entries → 200 lines; `last()` is the newest; `pop()` removes it.
  - `test_log_ignores_bad_lines`, `test_log_memory_only`.
  - `test_rename_path_all_rows_casefold` (playlist): two rows `C:\a\x.mp3` and `c:\A\X.mp3` both change; count 2; `version` +1; `layout_version` unchanged.
  - `test_rename_on_save_default_and_bad_value` (settings).
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -W error::SyntaxWarning tests/test_renamer.py tests/test_playlist.py tests/test_settings.py`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Run the same command.** Expected: PASS. Then run the full suite.
- [ ] **Step 5: Commit** `feat(5-C): file-name rules, rename, undo log`.

### Task 2: Browser search URLs and image download

**Files:**
- Create `funplayer/websearch.py`.
- Modify `tests/test_layering.py`, adding `websearch.py` to the Qt-free list.
- Tests: `tests/test_websearch.py`.

**Interfaces (produces):**
- **Constants:**
  - `GENIE_URL = "https://www.genie.co.kr/search/searchMain?query={q}"`
  - `MELON_URL = "https://www.melon.com/search/total/index.htm?q={q}"`
  - `SITES = {"genie": GENIE_URL, "melon": MELON_URL}`
  - `MAX_IMAGE = 10 * 1024 * 1024`
- `search_terms(artist: str, title: str, path: str) -> str`:
  - Returns `f"{artist.strip()} {title.strip()}".strip()`.
  - If both are empty, uses `tagguess.guess_from_filename(path)`, with the title passed through `clean_search_title`, joined the same way.
  - May return `""`.
- `search_url(site: str, terms: str) -> str`: `urllib.parse.quote(terms, safe="")` substituted into the site template.
- `class ImageFetchError(Exception)`.
- `fetch_image(url: str, fetch=None) -> bytes`:
  - Only the `http`/`https` schemes; anything else raises `ImageFetchError`.
  - Default fetch: `urllib.request` with User-Agent `musicbrainz.USER_AGENT`, timeout 10 s, reading at most `MAX_IMAGE + 1` bytes.
  - More than `MAX_IMAGE` bytes raises `ImageFetchError`.
  - Any `OSError`, `ValueError`, `http.client.HTTPException` or `urllib.error.URLError` becomes `ImageFetchError` (chained).
  - The injected fetch has the signature `fetch(url, headers, limit) -> bytes`.

- [ ] **Step 1: Write failing tests.**
  - `test_search_url_korean`: `search_url("genie", "서지원 I Miss You") == "https://www.genie.co.kr/search/searchMain?query=%EC%84%9C%EC%A7%80%EC%9B%90%20I%20Miss%20You"`.
  - `test_search_url_melon`.
  - `test_search_terms_fields`.
  - `test_search_terms_from_filename`: `("", "", r"C:\m\02. I Miss You.mp3")` → `"I Miss You"`.
  - `test_search_terms_empty`.
  - `test_fetch_image_headers`: the fake fetch receives the exact UA and `limit == MAX_IMAGE + 1`.
  - `test_fetch_image_too_big`.
  - `test_fetch_image_bad_scheme`: `file:///c:/x.jpg` → error.
  - `test_fetch_image_oserror_wrapped`.
- [ ] **Step 2: Run** `pytest tests/test_websearch.py tests/test_layering.py`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS, then the full suite.
- [ ] **Step 5: Commit** `feat(5-C): browser search URLs and image download`.

### Task 3: Controller rename on save, undo

**Files:**
- Modify `funplayer/controller.py`.
- Tests: `tests/test_controller.py` (new section; reuse its fake player and the `tone_mp3` copies).

**Interfaces:**
- Consumes Task 1: `renamer.*` and `Playlist.rename_path`.
- **Produces:**
  - Constructor kwargs `rename_log: RenameLog | None = None` (default: `RenameLog(None)`) and `rename_file=None` (default `renamer.rename_file`).
  - `@dataclass class SaveOutcome: info: TrackInfo; renamed_from: str | None = None; warning: str = ""`.
  - Messages as module constants, exactly the spec §4.3/§4.4 texts:
    - `RENAME_EXISTS = "같은 이름의 파일이 이미 있습니다 ({name}). 아무것도 저장하지 않았습니다."`
    - `RENAME_PARTIAL = "태그는 저장했지만 파일 이름은 바꾸지 못했습니다 (다른 프로그램이 쓰는 중이거나 권한이 없습니다)."`
    - `RENAME_FAILED = "파일 이름을 바꾸지 못했습니다 (다른 프로그램이 쓰는 중이거나 권한이 없습니다)."`
    - `UNDO_DONE = "파일 이름을 되돌렸습니다"`
    - `UNDO_MISSING = "되돌릴 파일이 없습니다 ({name})"`
    - `UNDO_EXISTS = "원래 이름의 파일이 이미 있습니다 ({name})"`
    - `UNDO_FAILED = "파일 이름을 되돌리지 못했습니다 (다른 프로그램이 쓰는 중이거나 권한이 없습니다)."`
  - `save_and_rename(path, fields, picture, new_path) -> SaveOutcome`:
    1. If `conflict(path, new_path)`, raise `RenameError(RENAME_EXISTS.format(name=basename(new_path)))` before anything else.
    2. Unload if loaded (same rules as `_edit_tags`).
    3. Write tags only if `fields` or `picture is not KEEP`. On `TagWriteError`, reload the old path and re-raise.
    4. Rename. On `RenameError`:
       - If the tags were written, return `SaveOutcome(info_of_old_path, None, RENAME_PARTIAL)`.
       - Otherwise raise `RenameError(RENAME_FAILED)`.
       - Either way reload the old path.
    5. On success:
       - Reload the new path, then call `_rename_everywhere(path, new_path)`: `playlist.rename_path` plus `settings.last_track` when normcase-equal.
       - Call `rename_log.add(path, new_path)`.
       - Return `SaveOutcome(info_of_new_path, path)`.
    - Afterwards, same as `_edit_tags`: info cache cleared, `_synced_key = None`, `sync_effects()`.
    - Refactor `_edit_tags` so the unload/reload logic is shared rather than duplicated. The reload path must be the final path.
  - `last_rename() -> tuple[str, str] | None`: delegates to the log.
  - `undo_rename() -> tuple[str | None, str]`: returns `(old_path, UNDO_DONE)` on success, otherwise `(None, error_text)`. It also sets the status line (`_set_status(UNDO_DONE, False)` or `_error(text)`).
    - Empty log → `(None, "")`, with the status unchanged.
    - New path missing → `log.pop()`, `UNDO_MISSING`.
    - `RenameConflict` → `UNDO_EXISTS` with the old basename; the entry is kept.
    - Other `RenameError` → `UNDO_FAILED`; the entry is kept.
    - Success → unload/reload like a rename, `_rename_everywhere(new, old)`, `log.pop()`.

- [ ] **Step 1: Write failing tests** (copies in `tmp_path`, fake player):
  - `test_rename_playing_reloads_new_path`: playing at 12.0 → after save, the player loaded `new_path`, sought to 12.0 and is PLAYING. The playlist row, `title` and `last_track` are all the new path. The log `last()` is `(old, new)`.
  - `test_rename_paused_stays_paused`.
  - `test_rename_only_skips_tag_write`: a spy `write_tags` is not called when `fields == {}` and the picture is `KEEP`.
  - `test_conflict_writes_nothing`: another file exists at the target → `RenameError` with the exact text. The spy `write_tags` was not called and the file bytes are unchanged.
  - `test_rename_failure_reloads_old_path`: `rename_file` raises `RenameError` after a tag write → outcome warning `RENAME_PARTIAL`, `renamed_from is None`, the player reloads the old path, and the log stays empty.
  - `test_rename_only_failure_raises`.
  - `test_tag_failure_no_rename`.
  - `test_rename_updates_last_track`: also covers duplicate rows.
  - `test_undo_roundtrip`, `test_undo_missing_pops`, `test_undo_conflict_keeps_entry`, `test_undo_empty_log`.
- [ ] **Step 2: Run** `pytest tests/test_controller.py`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS, then the full suite (the existing 5-A save tests must still pass).
- [ ] **Step 5: Commit** `feat(5-C): rename on save and undo in controller`.

### Task 4: Dialog — browser search row, paste/drop, rename row, undo link

**Files:**
- Modify `funplayer/ui/info_dialog.py` and `funplayer/ui/colors.py`.
- Tests: `tests/test_info_dialog.py`.

**Interfaces:**
- **Consumes:** Task 1 `renamer.target_path`, `renamer.conflict`; Task 2 `websearch.search_terms`, `search_url`, `fetch_image`, `ImageFetchError`.
- **Produces (public names used by Task 5 and the tests):**
  - **Widgets:**
    - Row widgets `genie_button` / `melon_button`, both inside a `web_row` QWidget.
    - `paste_hint` QLabel.
    - `rename_box` QCheckBox and `rename_preview` QLabel, inside a `rename_row` QWidget.
    - `undo_link` QLabel (rich text `<a href="#">되돌리기</a>`, `linkActivated`), shown next to `message_label`. Put both in one row widget, `message_row`.
  - **Signals:**
    - `rename_toggled = pyqtSignal(bool)`: user clicks only.
    - `undo_rename_requested = pyqtSignal(str, str)`: `(old, new)`.
  - `set_services(run_async, client_factory, open_url=None, fetch_image=None)`: `open_url(QUrl)` defaults to `QDesktopServices.openUrl`; `fetch_image` defaults to `websearch.fetch_image`.
  - `set_rename_checked(on: bool)`: no signal.
  - `rename_target() -> str | None`: the new path when a rename is pending, else `None`.
  - `has_pending_rename() -> bool`: box checked, editable, `target_path(...)` not `None` and `!= self._path`, and no conflict.
  - `saved(info, cover, renamed_from: str | None = None, warning: str = "")`:
    - `renamed_from` → green text (`RENAME_OK_COLOR`): `저장했습니다 · 파일 이름을 바꿨습니다`, or `파일 이름을 바꿨습니다` when no tag field or picture changed in that save. The undo link is shown and `(renamed_from, info.path)` is remembered.
    - `warning` → red warning, no undo link.
    - Otherwise: 5-A `저장했습니다` (gray).
  - `renamed_back(info, cover)`: repopulates and shows green `파일 이름을 되돌렸습니다`. The undo link is hidden.
  - `clear_undo()`: hides the undo link and forgets the pair.
- **Behavior:**
  - **Rows.** The web row sits above the path row and the rename row below it, per the mockup. Both are visible only when editable. `paste_hint` sits under the picture buttons (editable only).
  - **Web buttons.**
    - The terms come from `search_terms(current artist, current title, self._path)`.
    - Both buttons are disabled when the terms are `""` and update as fields change.
    - A click calls `open_url(QUrl(search_url(site, terms)))`.
  - **Preview.**
    - Updated on every field edit and box toggle.
    - Texts and colors exactly as spec §4.1, using the current (stripped) artist/title values.
    - Hidden when the box is unchecked.
  - **Save button.** Enabled when `is_dirty() or has_pending_rename()`.
  - **`_save`.** Proceeds when either is true. Validation runs only for changed fields, as before.
    - It records whether tags changed in that save, for the `saved()` text.
    - It emits `save_requested(self._path, fields, picture)`. The panel reads `rename_target()`.
  - **`is_dirty()` is unchanged.** It still ignores the rename, so no discard prompt is shown for a rename alone.
  - **Ctrl+V.**
    - Install an event filter on the dialog and every edit (and the combo's lineEdit).
    - On a `KeyPress` matching `QKeySequence.Paste` while editable, check the clipboard in this order:
      1. `mimeData().hasImage()` → encode the `QImage` to JPEG quality 90 bytes → `set_picture_bytes`.
      2. Otherwise exactly one local jpg/png URL → `_load_picture_file`.
    - In either case consume the event. Otherwise let it through, so the text paste happens.
  - **Drop.** Accept, in priority order:
    1. Image data (`hasImage`) → JPEG 90.
    2. Exactly one local jpg/png file (existing behavior).
    3. Exactly one `http(s)` URL → `run_async(lambda: fetch_image(url), done)`. Show gray `그림 받는 중…` in `message_label`. A late reply is dropped with the existing token mechanism (path + counter). On `ImageFetchError` show red `그림을 받지 못했습니다`. Bytes go to `set_picture_bytes`, which reports non-jpg/png with the 5-A text.
  - **Leaving a rename.** Re-showing another track hides the undo link (`_populate` calls `clear_undo`).

- [ ] **Step 1: Write failing tests** (offscreen `qapp`, fake run_async, fake `open_url` recorder, `tmp_path` MP3 copies):
  - **Search row:**
    - `test_web_buttons_open_urls`: artist `서지원`, title `I Miss You` → genie click records the exact URL from Task 2's test; melon likewise.
    - `test_web_buttons_disabled_without_terms`.
    - `test_web_rows_hidden_readonly`.
  - **Preview and checkbox:**
    - `test_rename_preview_texts`: arrow+name (brown), same name (gray `(지금 이름과 같음)`), missing artist (gray sentence), conflict (red `같은 이름의 파일이 이미 있습니다`).
    - `test_rename_toggled_signal_only_on_click`: `set_rename_checked(True)` emits nothing; a click emits `True`.
  - **Pending rename and save:**
    - `test_pending_rename_not_dirty`: box on and name differs, no field edits → `save_button` enabled, `is_dirty()` False, `has_pending_rename()` True, and `rename_target()` is the target path.
    - `test_save_emits_for_rename_only`.
    - `test_saved_with_rename_shows_link`: clicking the link emits `undo_rename_requested(old, new)`.
    - `test_saved_warning_red_no_link`.
    - `test_renamed_back_text`.
  - **Ctrl+V:**
    - `test_ctrl_v_image_in_field_sets_cover`: clipboard `setImage(QImage 20x20)`, focus in the title edit, send Ctrl+V → `_picture` is bytes starting `FF D8` and the title text is unchanged.
    - `test_ctrl_v_text_in_field_pastes_text`: clipboard text `abc` → the title edit gets `abc` inserted and the picture is still `KEEP`.
  - **Drop:**
    - `test_drop_image_data`.
    - `test_drop_http_url_fetches`: fake fetch returns PNG bytes → picture set. A fetch error shows the red text.
    - `test_drop_url_late_reply_ignored`: another track is shown before `done` runs → no change.
- [ ] **Step 2: Run** `pytest tests/test_info_dialog.py`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS, then the full suite.
- [ ] **Step 5: Commit** `feat(5-C): info dialog browser search, paste, rename row`.

### Task 5: Panel wiring, context menu undo, app paths, docs

**Files:**
- Modify `funplayer/ui/player_panel.py`, `funplayer/__main__.py`, `CLAUDE.md` (file table: `core/renamer.py`, `websearch.py`) and `docs/개발로드맵.md`.
  - The roadmap gets new rows in the stage-5 table: `H-7 | 파일 이름을 가수 - 제목으로 바꾸기 (되돌리기) | 5-C | 중 | ☐` and `H-8 | 지니·멜론 브라우저 찾기·그림 붙여 넣기 | 5-C | 하 | ☐`. Do not stamp them yet.
- Tests: `tests/test_panel_tags.py`, `tests/test_panel_input.py`.

**Interfaces:**
- **Consumes:** Task 3 controller API, Task 4 dialog API, `Settings.rename_on_save`.
- **Produces:**
  - `PlayerPanel(..., rename_log_path: str | None = None)` → controller `rename_log=RenameLog(rename_log_path)`.
  - `__main__` passes `str(app_dir() / "rename_log.txt")`.
  - Context action key `"undo_rename"`, placed right after `"info_row"`.
- **Behavior:**
  - **Dialog creation:** `set_services(self.runner.run_async, musicbrainz.default_client)` (other defaults are real), `set_rename_checked(settings.rename_on_save)`, and `rename_toggled` → `settings.rename_on_save = on`.
  - **`_save_tags(path, fields, picture)`:**
    - `target = dialog.rename_target()`.
    - With a target: `outcome = controller.save_and_rename(path, fields, picture, target)`, then `dialog.saved(outcome.info, load_cover(outcome.info), outcome.renamed_from, outcome.warning)`.
    - `RenameError` or `TagWriteError` → `dialog.failed(str(e))`.
    - Without a target: the existing path.
    - Always: wait cursor, `_cover_key = object()`, `refresh()`.
  - **Undo (from the dialog link or the menu):**
    - `old, text = controller.undo_rename()`.
    - The menu path first takes `controller.last_rename()`. The dialog path checks that `last_rename() == (old, new)` it was given. If not, call `dialog.clear_undo()` and do nothing.
    - On success, if the dialog is visible and showing the renamed file, call `dialog.renamed_back(controller info for old, cover)`.
    - On failure, if the dialog is visible, call `dialog.failed(text)`.
    - A menu undo always calls `dialog.clear_undo()` when a dialog exists. `refresh()`.
  - **Menu text:** set in `_update_actions` as `이름 되돌리기: {new} → {old}`.
    - Each name is the basename, elided to 40 chars as `name[:39] + "…"` when longer.
    - Visible only when `last_rename()` is not `None`.

- [ ] **Step 1: Write failing tests** (existing panel fixtures, fake player, `tmp_path` copies, `rename_log_path` in `tmp_path`):
  - **Rename on save:**
    - `test_save_with_rename_updates_row_text`: box on, artist/title set, save → `playlist_view.item(i).text()` ends with `가수 - 제목`. The file exists under the new name and the log file has one line.
    - `test_rename_setting_persisted`: clicking the box flips `settings.rename_on_save`; a new dialog starts checked.
    - `test_conflict_shows_red_and_writes_nothing`.
  - **Menu undo:**
    - `test_menu_undo_visible_and_text`: after a rename the menu action is visible with the exact text. After undo the file is back, the row text is old, the action is hidden and the status line shows `파일 이름을 되돌렸습니다`.
    - `test_menu_undo_hidden_without_log`.
  - **Dialog undo:**
    - `test_dialog_undo_link_restores`.
    - `test_dialog_undo_stale_pair_ignored`.
- [ ] **Step 2: Run** `pytest tests/test_panel_tags.py tests/test_panel_input.py`. Expected: FAIL.
- [ ] **Step 3: Implement**, including `__main__` and the docs.
- [ ] **Step 4: Run** the full suite with `-W error::SyntaxWarning`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(5-C): panel wiring, rename undo menu, docs`.

### Task 6: Real check (controller does this, not a subagent)

- [ ] Run the real app offscreen against `Test-mp3` **copies** in the scratchpad:
  - Rename while playing and while paused (position kept), undo, conflict, Ctrl+V of a clipboard image.
- [ ] Check that both search URLs return HTTP 200 with a normal browser-like GET. One request each, purely to verify the URL shape. No scraping.
- [ ] Capture the dialog and list as `docs/images/stage5c_real.png`.
- [ ] Publish the check page. **Stop at the user checklist gate.**
