# Stage 4-B: Genre Auto Preset, Spectrum, Clickable Collapsed Line — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 8 more presets plus "자동 (장르 따라)" driven by the track's genre tag (or overseas station genre), a bar spectrum of the sound as heard (expanded strip and collapsed line), and click-to-change 켜짐/꺼짐 and preset on the collapsed line.

**Architecture:** Pure logic in `core/` (`genre.py` mapping, `effects.py` auto/applied/next_choice, `spectrum.py` FFT bars + decay). The player taps a copy of each output block (`latest_block`). The controller picks the genre preset for the current source and always sends the *applied* settings to the player. The UI adds `SpectrumView` and extends `FxStrip`; the panel drives a 40 ms spectrum timer only while the strip is visible.

**Tech Stack:** Python 3.13/3.14, PyQt5 5.15.11, numpy, PyAV 19.0.2 (unchanged chain), pytest. No new dependencies.

**Spec:** `docs/stage4b_design.md` (approved 2026-10-30). Mockup `docs/images/stage4b_mockup.png`. Base: stage 4 on main `722fd72`.

## Global Constraints

- No new dependencies. Never import PySide6. Python 3.13 compatible; `from __future__ import annotations` in new modules. `core/`, `engine/`, `controller.py`, `radio.py` Qt-free (tests/test_layering.py). Tests use no network and no real audio device.
- Exact strings: auto item `자동 (장르 따라)`; auto display `자동: {프리셋}`; collapsed parts `켜짐` / `꺼짐`, joined by ` · `, mode part `스피커` / `이어폰` (omitted when mode off); tooltips `눌러서 끄기`, `눌러서 켜기`, `눌러서 다음 프리셋`.
- New presets, appended after the existing 10 in this order, values exactly as spec §2: 알앤비, 힙합, 일렉트로닉, 어쿠스틱, 블루스, 트로트, 라운지, 라이브.
- Genre table, order and words exactly as spec §3 (first match wins; lower-cased substring match); ID3v1 numbers exactly as spec §3.
- Spectrum: 40 Hz–16 kHz log-spaced bars; level = dB re full scale clipped to -60..0 mapped to 0..1; expanded 24 bars, height 38 px, full strip width; collapsed 12 bars, 72×16 px; colors bars `#4A86D8`, peaks `#9DB9E6` (put both in `funplayer/ui/colors.py`); update every 40 ms only while the strip is visible and not mini.
- Settings: effects dict gains `"auto": bool` (default False; non-bool → False).

## Review Focus

1. Auto on, then the user drags a band → auto off, `사용자 설정` holds the dragged curve built from the *displayed* (genre) curve, and the next track does not change it. (Task 1 `test_band_while_auto_turns_auto_off`, Task 4 `test_slider_while_auto_becomes_custom`.)
2. Genre strings in the wild: mixed case, Korean, slashes (`알앤비/어반`), numeric ID3v1 (`(17)`), `Classic Rock` vs `Classical`, empty/whitespace. (Task 1 `test_genre_table_cases`.)
3. Spectrum while paused/stopped or with no output yet → bars fall to zero, no exception, no work when the strip is hidden. (Task 5 `test_spectrum_timer_only_when_visible`, Task 2 `test_silence_is_zero`.)
4. Track changes very fast (holding [다음]) → the player gets one applied-settings update per distinct track, never stale. (Task 3 `test_sync_only_on_key_change`.)
5. Collapsed preset click cycles past `사용자 설정` when it was never set, and wraps to auto. (Task 1 `test_next_choice_order`.)

---

### Task 1: Presets, auto, genre mapping

**Files:** Create `funplayer/core/genre.py`; modify `funplayer/core/effects.py`; tests `tests/test_genre.py`, `tests/test_effects.py`.

**Interfaces (produces):**
- `genre.preset_for_genre(text: str) -> str | None`.
- `effects.AUTO = "자동 (장르 따라)"`; `PRESETS` now 18 entries.
- `FxSettings.auto: bool = False`; `with_auto(on: bool) -> FxSettings`; `with_preset(AUTO)` == `with_auto(True)` (preset/bands unchanged = 설정값); `with_preset(other)` also sets `auto=False`.
- `applied(genre_preset: str | None) -> FxSettings`: auto and genre_preset in PRESETS → copy with `bands=PRESETS[genre_preset]` (preset, auto, custom unchanged); else self.
- `applied_name(genre_preset: str | None) -> str`: auto and match → genre_preset; else `self.preset`.
- `with_band` sets `auto=False` (call it on the applied copy so the displayed curve is the base). `reset()` sets `auto=False`.
- `summary(genre_preset: str | None = None) -> str`: `"{켜짐|꺼짐} · {name}"` + `" · 스피커"`/`" · 이어폰"`; name is `자동: {applied_name}` when auto.
- `next_choice() -> FxSettings`: order `[AUTO, *PRESETS, CUSTOM]`, skipping CUSTOM when `custom` is all zero; current is AUTO when auto else `preset`; returns `with_preset(next)`.
- `to_dict`/`from_dict` carry `auto`.

- [ ] **Step 1: Failing tests.**
  - `test_new_presets`: `list(PRESETS)[10:] == ["알앤비","힙합","일렉트로닉","어쿠스틱","블루스","트로트","라운지","라이브"]`; values per spec (check 알앤비, 라이브).
  - `test_genre_table_cases`: `Ballad`→발라드, `ROCK`→록, `Classic Rock`→록, `Classical`→클래식, `Rhythm and Blues`→알앤비, `Blues`→블루스, `알앤비/어반`→알앤비, `R&B`→알앤비, `Hip-Hop`→힙합, `K-Pop`→팝, `Lo-fi`→라운지, `재즈`→재즈, `(17)`→록, `17`→록, `32`→클래식, `레게`→None, `""`/`"  "`→None.
  - `test_auto_applied`: auto + `록` → applied bands == PRESETS["록"], applied_name `록`; auto + None → own bands, name = preset; not auto → self.
  - `test_band_while_auto_turns_auto_off`: `fx = FxSettings().with_preset("발라드").with_auto(True)`; `fx.applied("록").with_band(0, 9)` → auto False, preset CUSTOM, bands == PRESETS["록"] with [0]=9, custom == bands.
  - `test_summary_forms`: off → `꺼짐 · 기본`; on+speaker → `켜짐 · 기본 · 스피커`; auto+록+earphone → `켜짐 · 자동: 록 · 이어폰`; auto no genre with preset 발라드 → `켜짐 · 자동: 발라드`.
  - `test_next_choice_order`: from auto → 기본 (auto False); from 라이브 with zero custom → AUTO; with non-zero custom → CUSTOM then AUTO.
  - `test_reset_turns_auto_off`, dict round trip with auto, `from_dict({"auto": "yes"})` → False.
  - Update the old summary test in tests/test_effects.py to the new forms (spec §5 changed it).
- [ ] **Step 2:** run `tests/test_genre.py tests/test_effects.py` → FAIL. **Step 3:** implement. **Step 4:** PASS + full suite (fix any other test that asserted the old `꺼짐`-only summary, e.g. in tests/test_fx_strip.py / tests/test_panel_fx.py, to the new copy). **Step 5:** commit "Add genre auto preset and eight presets".

### Task 2: Spectrum analysis and output tap

**Files:** Create `funplayer/core/spectrum.py`; modify `funplayer/engine/player.py`; tests `tests/test_spectrum.py`, `tests/test_player.py`.

**Interfaces (produces):**
- `band_levels(block: np.ndarray, rate: int, bars: int) -> np.ndarray` (float32, len `bars`, 0..1). Mono = mean of channels; use the last up to 2048 frames (zero-pad shorter); Hann window; `np.fft.rfft`; bar edges log-spaced 40–16000 Hz; bar value = max magnitude in the bar, normalised so a full-scale sine reads 0 dB; map -60..0 dB → 0..1.
- `class Decay(bars: int, fall_per_sec: float = 1.5, peak_fall_per_sec: float = 0.5)`: `update(levels: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]` — shown level = max(new, previous − fall·dt); peak = max(shown, previous peak − peak_fall·dt).
- `AudioPlayer.latest_block() -> np.ndarray | None`: copy of the last block written to the device (after gain and effects), or None before any output. The callback copies into a preallocated buffer (grow only when a larger block arrives) under a tiny dedicated lock; never allocates per block in steady state.

- [ ] **Step 1: Failing tests:** `test_sine_peaks_in_its_bar` (1 kHz full-scale sine, 24 bars → argmax is the bar containing 1 kHz and its value > 0.9); `test_silence_is_zero`; `test_short_and_long_blocks` (n=100 and n=4096 → len bars, finite); `test_decay_falls_slowly` (1 → 0 input, dt 0.04 → 0.94); `test_latest_block_after_output` (FakeSink pull → equals that outdata; before → None; varying sizes).
- [ ] **Steps 2–5:** fail → implement → pass + full suite → commit "Add spectrum bars and an output tap".

### Task 3: Controller picks the genre preset

**Files:** modify `funplayer/controller.py`, `tests/fakes.py`; tests `tests/test_controller.py`.

**Interfaces (produces):**
- `PlayerController.genre_preset -> str | None`: file source → `preset_for_genre(info.genre)` (None when no info); radio → current station group `genre:X` → `preset_for_genre(X)`; other stations → None.
- `PlayerController.applied_preset -> str` = `effects.applied_name(genre_preset)`.
- `set_effects(fx, save=True)` sends `fx.applied(self.genre_preset)` to the player.
- `sync_effects() -> bool`: key = `("file", track path)` / `("radio", station id)` / None; when the key differs from the last synced key, send `effects.applied(genre_preset)` to the player, remember the key, return True; else False. Called at the end of `_play_index` and `play_station`, and by the panel's refresh.

- [ ] **Step 1: Failing tests** (FakePlayer.effects records what was sent; `read_info` is injectable in the controller — use it to give tracks genres): `test_auto_uses_track_genre` (track genre `Rock`, auto with preset 발라드 → player bands == PRESETS["록"]); `test_auto_without_genre_uses_setting` (→ 발라드 bands); `test_next_track_switches_preset` (two tracks Rock/Ballad → after next, bands of 발라드); `test_radio_overseas_genre_and_domestic` (station `net-somafm-groove-salad` group `genre:앰비언트` → 라운지; `kbs-25` → setting); `test_sync_only_on_key_change` (calling sync twice on the same track → second returns False, player not called again); `test_not_auto_ignores_genre`.
- [ ] **Steps 2–5:** fail → implement → pass + full suite → commit "Controller applies the genre preset per track and station".

### Task 4: SpectrumView and FxStrip changes

**Files:** create `funplayer/ui/spectrum_view.py`; modify `funplayer/ui/fx_strip.py`, `funplayer/ui/colors.py`; tests `tests/test_fx_strip.py`, `tests/test_spectrum_view.py`.

**Interfaces (produces):**
- `SpectrumView(bars: int, parent=None)`: `set_levels(levels, peaks)` stores and `update()`s; paints bars `SPECTRUM_COLOR` and 1.5 px peaks `SPECTRUM_PEAK_COLOR`; gaps 2 px when bars > 14 else 1 px.
- `FxStrip`: combo item 0 = `AUTO` (display text `자동: {name}` while auto); `set_genre_preset(name: str | None)` updates sliders/combo/summary without emitting; band slider changes build from `value.applied(genre).with_band(...)`; `big_spectrum` (SpectrumView 24, height 38) inserted between the header row and the band grid inside the body; collapsed header shows `power_link`, `preset_link` (clickable rich-text labels, pointing-hand cursor, tooltips per Global), `mode_label` (gray, not clickable), `small_spectrum` (SpectrumView 12, 72×16) at the right; `power_link` click → `with_enabled(not enabled)`; `preset_link` click → `next_choice()`; both emit `changed(fx, True)`. Remove the old single `summary_label` text use (keep the name only if tests need it; prefer the new parts).
- Width rule from stage 4 still holds: the strip's minimum width must not exceed the panel's (test exists in tests/test_panel_fx.py — keep it green).

- [ ] **Step 1: Failing tests:** `test_combo_has_auto_first_and_shows_applied` (set_value auto + set_genre_preset("록") → combo text `자동: 록`, sliders == 록); `test_slider_while_auto_becomes_custom`; `test_collapsed_power_click_toggles`; `test_collapsed_preset_click_cycles` (기본 → 발라드 …; emits final True); `test_mode_label_not_clickable` (no linkActivated / mouse press does nothing); `test_spectrum_views_placed` (big inside body above the grid, visible only when open; small in header, visible only when collapsed); `test_spectrum_view_paints` (grab without error, set_levels stores).
- [ ] **Steps 2–5:** fail → implement → pass + full suite → commit "Strip: auto preset, clickable collapsed line, spectrum views".

### Task 5: Panel wiring

**Files:** modify `funplayer/ui/player_panel.py`; tests `tests/test_panel_fx.py`; docs `CLAUDE.md` (file list), `docs/개발로드맵.md` (§3 add rows for 4-B features as `E-1+`… or a short line under stage 4; §5 structure lines for genre.py, spectrum.py, spectrum_view.py).

**Interfaces/rules:**
- `refresh()` calls `controller.sync_effects()`; whenever it returns True (or on startup), `fx_strip.set_genre_preset(controller.genre_preset)`.
- `_spectrum_timer` (QTimer 40 ms) runs only while the strip is visible and not mini; each tick: block = `player.latest_block()` if the current source is playing (file PLAYING or radio LIVE) else silence; `band_levels` for 24 and 12 bars; one `Decay` each with the real dt; push to `big_spectrum`/`small_spectrum`. FakePlayer gets `latest_block()` returning a settable value (default None → treated as silence).
- [ ] **Step 1: Failing tests:** `test_spectrum_timer_only_when_visible` (hidden → inactive; Ctrl+E → active; mini → inactive); `test_track_change_updates_strip_genre` (auto, two tracks with genres → after next + refresh, combo text changes); `test_spectrum_falls_when_paused` (block then None → levels decrease over ticks).
- [ ] **Steps 2–5:** fail → implement → pass; full suite twice → commit "Panel: drive spectrum and genre preset".

### Task 6: Real check (controller)

- Real panel offscreen + real device: auto on, play Test-mp3 songs with genres Rock/Ballad/R&B and one without; log applied preset per track; overseas station (jazz) and KBS; spectrum timer cost per tick; capture `docs/images/stage4b_real.png` (expanded with spectrum, collapsed with small spectrum). Update the artifact page into the 4-B check page with spec §8. Stop at the user checklist gate.
