# Stage 4 Sound Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A collapsible "음향 효과" strip between the transport row and the tabs: 10-band EQ with presets, a speaker/earphone space effect, and a limiter, applied right before output to files and radio alike.

**Architecture:** `core/effects.py` holds an immutable `FxSettings` value plus presets and dict (de)serialization. `engine/fx.py` turns it into an FFmpeg filter chain (`build_chain`) and runs it per output block (`FxProcessor`, PyAV filter graph, crossfaded swaps). `AudioPlayer` runs the processor in its output callback after the buffer lock is released; the controller owns the value and saving; `ui/fx_strip.py` is the widget; the panel wires menu, shortcut, mini mode and persistence.

**Tech Stack:** Python 3.13/3.14, PyQt5 5.15.11, PyAV 19.0.2 (`av.filter.Graph`), numpy, pytest. No new dependencies.

**Spec:** `docs/stage4_design.md` (approved 2026-10-27, ea5e056). Mockup `docs/images/stage4_mockup.png`.

## Global Constraints

- No new dependencies (no scipy). Never import PySide6. Python 3.13 compatible; `from __future__ import annotations` in new modules.
- `core/`, `engine/`, `controller.py`, `radio.py` stay Qt-free (tests/test_layering.py).
- Tests never use the network or a real audio device. Engine tests may use real PyAV filters.
- Exact UI strings:
  - Strip title `음향 효과`; checkbox `켜기`; label `프리셋`; label `듣는 곳`; radio buttons `끄기` `스피커` `이어폰`; button `초기화`.
  - Horizontal slider labels: speaker `넓이`; earphone `입체감`, `베이스`.
  - Band labels `31 62 125 250 500 1k 2k 4k 8k 16k`; scale labels `+12` `0` `-12`.
  - Custom preset name `사용자 설정`. Preset names, in order: `기본` `발라드` `팝` `록` `재즈` `클래식` `댄스` `보컬` `베이스 강하게` `고음 강하게`.
  - Collapsed summary: `꺼짐` when off; else `켜짐 · {프리셋}` plus ` · 스피커` / ` · 이어폰` when that mode is on.
  - Fold button tooltips `접기` (expanded) / `펼치기` (collapsed).
  - Band tooltip `1 kHz: +3 dB` style (`31 Hz: 0 dB`, `16 kHz: -2 dB`; positive values carry `+`). Horizontal tooltip `넓이 40%` style.
  - View menu item `음향 효과 칸 보이기\tCtrl+E` (checkable).
- Preset values (dB, 31 Hz first) exactly as spec §3 table.
- Band centers Hz: `31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000`; band range ±12, step 1.
- Defaults: enabled False, preset `기본`, bands all 0, mode `off`, width 40, depth 40, bass 30, custom all 0.
- Filter chain (spec §5): `volume=volume=-{x}dB` (x = max positive band / 2, omitted when 0) → `equalizer=f={Hz}:t=o:w=1:g={dB}` per non-zero band → speaker `extrastereo=m={1 + w/100}` (w>0) or earphone `crossfeed=strength={0.6*d/100}` (d>0) then `bass=g={9*b/100}:f=100` (b>0) → `alimiter=limit=0.98:level=disabled` always last. Disabled → empty chain.
- Settings keys: `player_fx` (dict, default `{}`), `player_fx_visible` (bool, default False), `player_fx_open` (bool, default True).
- Rebuild throttle while dragging: at most once per 50 ms. Save only on slider release (or on discrete changes: preset, mode, checkbox, reset).

## Review Focus

1. Rapid slider drags (hundreds of `update` calls before one output block) → only the newest chain is swapped in, no exception, no growing memory. (Task 2 test `test_many_updates_one_swap`.)
2. Output callback block sizes vary (1, 7, 2048, 4096 frames) → processor returns exactly that many frames every time. (Task 2 `test_varying_block_sizes`.)
3. Loud input with every band +12 → output never exceeds 1.0 in magnitude. (Task 2 `test_all_bands_max_never_clips`.)
4. Corrupt or hand-edited settings (`bands` with strings, wrong length, out-of-range numbers, unknown mode/preset) → clamped or default values, never a crash. (Task 1 `test_from_dict_garbage`.)
5. Turning effects off mid-play and on again, and switching file↔radio with effects on → sound continues, no exception, off gives the raw signal back after the crossfade block. (Task 2 `test_off_returns_raw_after_crossfade`, Task 3 `test_player_effects_toggle`.)

---

### Task 1: FxSettings, presets, settings keys

**Files:**
- Create: `funplayer/core/effects.py`
- Modify: `funplayer/core/settings.py` (DEFAULTS + three properties)
- Test: `tests/test_effects.py`, `tests/test_settings.py`

**Interfaces:**
- Produces:
  - `BANDS_HZ: tuple[int, ...]`, `BAND_LABELS: tuple[str, ...]` (`"31"…"16k"`), `PRESETS: dict[str, tuple[int, ...]]` (insertion order = Global order), `CUSTOM = "사용자 설정"`, `MODES = ("off", "speaker", "earphone")`.
  - `@dataclass(frozen=True) class FxSettings` with fields `enabled: bool, preset: str, bands: tuple[int, ...], mode: str, width: int, depth: int, bass: int, custom: tuple[int, ...]` and defaults from Global Constraints.
  - Methods (all return a new `FxSettings`): `with_enabled(on: bool)`, `with_preset(name: str)` (known preset → its values; `CUSTOM` → `custom`; unknown → unchanged), `with_band(i: int, db: int)` (clamped; preset becomes `CUSTOM`, `custom` becomes the new bands), `with_mode(mode: str)`, `with_level(name: str, value: int)` (`name` in `"width" | "depth" | "bass"`, clamped 0..100), `reset()` (spec §3: preset 기본, bands 0, mode off, levels default; keeps `enabled` and `custom`).
  - `summary(self) -> str` (Global copy), `to_dict(self) -> dict`, `@classmethod from_dict(cls, d: object) -> FxSettings`.
  - `Settings.fx: dict` (getter returns a dict, non-dict → `{}`; setter saves), `Settings.fx_visible: bool`, `Settings.fx_open: bool` (non-bool → default).

- [ ] **Step 1: Write failing tests** in `tests/test_effects.py`:

```python
def test_defaults_and_presets():
    fx = FxSettings()
    assert (fx.enabled, fx.preset, fx.bands, fx.mode, fx.width, fx.depth, fx.bass) == (False, "기본", (0,) * 10, "off", 40, 40, 30)
    assert list(PRESETS) == ["기본", "발라드", "팝", "록", "재즈", "클래식", "댄스", "보컬", "베이스 강하게", "고음 강하게"]
    assert PRESETS["발라드"] == (3, 2, 1, 0, -1, 0, 1, 2, 3, 2) and PRESETS["고음 강하게"] == (0, 0, 0, 0, 0, 1, 3, 5, 6, 7)
    assert FxSettings().with_preset("록").bands == PRESETS["록"]

def test_band_move_becomes_custom_and_is_remembered():
    fx = FxSettings().with_preset("팝").with_band(0, 20)
    assert fx.preset == CUSTOM and fx.bands[0] == 12 and fx.custom == fx.bands
    back = fx.with_preset("기본").with_preset(CUSTOM)
    assert back.bands == fx.bands

def test_reset_keeps_enabled_and_custom():
    fx = FxSettings().with_enabled(True).with_band(3, 5).with_mode("earphone").with_level("bass", 90).reset()
    assert fx.enabled and fx.preset == "기본" and fx.bands == (0,) * 10 and fx.mode == "off" and fx.bass == 30
    assert fx.custom[3] == 5

def test_summary():
    assert FxSettings().summary() == "꺼짐"
    on = FxSettings().with_enabled(True).with_preset("발라드")
    assert on.summary() == "켜짐 · 발라드"
    assert on.with_mode("earphone").summary() == "켜짐 · 발라드 · 이어폰"
    assert on.with_mode("speaker").summary() == "켜짐 · 발라드 · 스피커"

def test_dict_round_trip():
    fx = FxSettings().with_enabled(True).with_preset("재즈").with_mode("speaker").with_level("width", 77)
    assert FxSettings.from_dict(fx.to_dict()) == fx

def test_from_dict_garbage():
    assert FxSettings.from_dict("x") == FxSettings()
    fx = FxSettings.from_dict({"enabled": "yes", "preset": "없음", "bands": [1, "a", 99, -99], "mode": "tv",
                               "width": 500, "depth": -3, "bass": "z", "custom": None})
    assert fx.enabled is False and fx.preset == "기본" and fx.bands == (0,) * 10 and fx.mode == "off"
    assert (fx.width, fx.depth, fx.bass) == (100, 0, 30) and fx.custom == (0,) * 10
    ok = FxSettings.from_dict({"bands": [1, 2, 3, 4, 5, 6, 7, 8, 99, -99], "preset": CUSTOM})
    assert ok.bands == (1, 2, 3, 4, 5, 6, 7, 8, 12, -12) and ok.preset == CUSTOM
```

Rule for `from_dict`: `bands`/`custom` must be a list of exactly 10 numbers (non-bool) to be used (each clamped to ±12, rounded); otherwise all zeros. `enabled` must be a bool. Levels: non-bool number → clamped 0..100, else default. `preset` must be a known name or `CUSTOM`, else `기본`.

Settings tests (append to `tests/test_settings.py`): defaults `s.fx == {}`, `s.fx_visible is False`, `s.fx_open is True`; non-dict `player_fx` → `{}`; setters store under the three keys and call save once each.

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_effects.py tests/test_settings.py` — expect failures (module missing).
- [ ] **Step 3: Implement** `funplayer/core/effects.py` and the settings properties (follow the existing `Settings` property style).
- [ ] **Step 4: Run** the same command — PASS; then the full suite.
- [ ] **Step 5: Commit** `git add funplayer/core/effects.py funplayer/core/settings.py tests/test_effects.py tests/test_settings.py` — "Add effect settings, presets and settings keys".

### Task 2: Filter chain and FxProcessor

**Files:**
- Create: `funplayer/engine/fx.py`
- Test: `tests/test_fx.py`

**Interfaces:**
- Consumes: `FxSettings`, `BANDS_HZ` (Task 1); `SAMPLE_RATE` from `funplayer.engine.decoder`.
- Produces:
  - `build_chain(fx: FxSettings) -> list[tuple[str, str]]` (Global chain rules; numbers formatted with `:g`, e.g. `g=3`, `m=1.4`, `strength=0.24`, `g=2.7`).
  - `class FxProcessor` with `__init__(self, rate: int = SAMPLE_RATE, build_graph=None)`; `update(self, fx: FxSettings) -> None` (builds the new graph on the caller's thread; an empty chain means bypass; only the newest pending graph is kept); `process(self, block: np.ndarray) -> np.ndarray` (shape `(n, 2)` float32 in, same shape out); `active: bool` (a graph is installed or a swap is pending).
  - `build_graph` is injectable for tests: `Callable[[list[tuple[str, str]]], object]`; default builds an `av.filter.Graph` (`abuffer` flt/stereo/rate → filters → `abuffersink`).

Algorithm (not determined by the tests alone):
- `process`: if a pending swap exists, take it (under a small lock), run the block through the old path (old graph, or raw if none) and the new path (new graph, or raw if bypass), and mix with a linear ramp old→new across the block; drop the old graph. Otherwise run through the current graph (or return the block unchanged when none).
- Running a graph: push one `AudioFrame` (packed `flt`, stereo, `pts` counting frames), pull all available frames into a per-graph FIFO, return exactly `n` frames from the FIFO, padding missing frames with zeros at the front (limiter look-ahead).
- If building a graph raises, log a warning and treat it as bypass. If running a graph raises, log once, drop it, return the raw block.

- [ ] **Step 1: Failing tests** in `tests/test_fx.py` (real PyAV, sine helpers `tone(hz, n, amp)` returning `(n, 2)` float32):

```python
def test_chain_off_is_empty():
    assert build_chain(FxSettings()) == []

def test_chain_eq_preamp_and_limiter_last():
    fx = FxSettings().with_enabled(True).with_preset("발라드")
    chain = build_chain(fx)
    assert chain[0] == ("volume", "volume=-1.5dB")
    eq = [a for n, a in chain if n == "equalizer"]
    assert "f=31:t=o:w=1:g=3" in eq and not any("f=250:" in a for a in eq)   # 0 dB 밴드는 없다
    assert chain[-1] == ("alimiter", "limit=0.98:level=disabled")

def test_chain_modes():
    on = FxSettings().with_enabled(True)
    assert ("extrastereo", "m=1.4") in build_chain(on.with_mode("speaker"))
    ear = build_chain(on.with_mode("earphone"))
    assert ("crossfeed", "strength=0.24") in ear and ("bass", "g=2.7:f=100") in ear
    assert not any(n == "crossfeed" for n, _ in build_chain(on.with_mode("earphone").with_level("depth", 0)))
    assert build_chain(on) == [("alimiter", "limit=0.98:level=disabled")]

def test_bypass_returns_input():
    p = FxProcessor(); b = tone(440, 2048, 0.3)
    assert np.array_equal(p.process(b), b) and not p.active

def test_varying_block_sizes():
    p = FxProcessor(); p.update(FxSettings().with_enabled(True).with_preset("록").with_mode("earphone"))
    for n in (1, 7, 2048, 4096, 300):
        out = p.process(tone(1000, n, 0.3)); assert out.shape == (n, 2) and out.dtype == np.float32 and np.isfinite(out).all()

def test_all_bands_max_never_clips():
    p = FxProcessor(); fx = FxSettings().with_enabled(True)
    for i in range(10): fx = fx.with_band(i, 12)
    p.update(fx.with_mode("earphone").with_level("bass", 100))
    peak = max(np.abs(p.process(tone(60, 2048, 0.95))).max() for _ in range(20))
    assert peak <= 1.0

def test_bass_preset_boosts_low_not_high():
    def gain(hz):
        p = FxProcessor(); p.update(FxSettings().with_enabled(True).with_preset("베이스 강하게"))
        outs = [p.process(tone(hz, 2048, 0.1)) for _ in range(10)]
        return np.abs(outs[-1]).max() / 0.1
    assert gain(62) > 1.8 * gain(8000)   # 미리 낮춤(-3.5 dB) 때문에 절대값이 아니라 비율로 본다

def test_swap_has_no_jump():
    p = FxProcessor(); p.update(FxSettings().with_enabled(True))
    prev = p.process(tone(200, 2048, 0.3))
    p.update(FxSettings().with_enabled(True).with_preset("베이스 강하게"))
    cur = p.process(tone(200, 2048, 0.3))
    assert abs(float(cur[0, 0]) - float(prev[-1, 0])) < 0.1

def test_off_returns_raw_after_crossfade():
    p = FxProcessor(); p.update(FxSettings().with_enabled(True).with_preset("록"))
    p.process(tone(500, 2048, 0.3)); p.update(FxSettings())
    p.process(tone(500, 2048, 0.3))            # 섞는 블록
    b = tone(500, 2048, 0.3); assert np.array_equal(p.process(b), b) and not p.active

def test_many_updates_one_swap():
    built = []
    def fake_build(chain): built.append(chain); return IdentityGraph()   # tests/fakes or local: process returns input
    p = FxProcessor(build_graph=fake_build)
    for i in range(300): p.update(FxSettings().with_enabled(True).with_band(0, i % 12))
    p.process(tone(100, 64, 0.1)); assert p._pending is None

def test_build_failure_is_bypass():
    def boom(chain): raise ValueError("no filter")
    p = FxProcessor(build_graph=boom); p.update(FxSettings().with_enabled(True))
    b = tone(300, 512, 0.2); assert np.array_equal(p.process(b), b)
```

Define what `IdentityGraph` is in the test file: an object exposing the same method the processor calls on a graph. Choose that method name in Step 3 (e.g. `run(block) -> np.ndarray`) and wrap the PyAV graph in a small private class with the same method, so tests can fake it.

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_fx.py` — FAIL.
- [ ] **Step 3: Implement** `funplayer/engine/fx.py`.
- [ ] **Step 4: Run** — PASS; full suite.
- [ ] **Step 5: Commit** `git add funplayer/engine/fx.py tests/test_fx.py` — "Add the effect chain and per-block processor".

### Task 3: Player and controller wiring

**Files:**
- Modify: `funplayer/engine/player.py` (`__init__`, new `set_effects`, `_callback`)
- Modify: `funplayer/controller.py` (effects property + setter, apply on start)
- Modify: `tests/fakes.py` (`FakePlayer.set_effects` records `self.effects`)
- Test: `tests/test_player.py`, `tests/test_controller.py`

**Interfaces:**
- Consumes: `FxSettings` (Task 1), `FxProcessor` (Task 2).
- Produces:
  - `AudioPlayer.__init__(..., fx_processor: FxProcessor | None = None)` (default `FxProcessor()`); `AudioPlayer.set_effects(fx: FxSettings) -> None`.
  - `_callback`: unchanged buffer/gain code under `_buf_lock`; after the lock, `if self._fx.active: outdata[:] = self._fx.process(outdata)`.
  - `PlayerController.effects -> FxSettings` (from `settings.fx` via `from_dict`), `PlayerController.set_effects(fx: FxSettings, save: bool = True) -> None` (always `player.set_effects(fx)`; writes `settings.fx = fx.to_dict()` only when `save`). The controller calls `player.set_effects(self.effects)` once in `__init__`.

- [ ] **Step 1: Failing tests:**
  - `test_player_effects_toggle` (test_player.py, FakeSink with `threaded=False`, tone wav fixture already used there): pull one callback block with effects off → equals the gain-scaled buffer; `set_effects(enabled 록)`, pull blocks → differs from raw; `set_effects(FxSettings())`, pull two blocks → second equals raw again.
  - `test_controller_applies_saved_effects_on_start`: store `{"player_fx": FxSettings().with_enabled(True).with_preset("팝").to_dict()}` → `FakePlayer.effects.preset == "팝"` right after constructing the controller.
  - `test_set_effects_save_flag`: `set_effects(fx, save=False)` → player updated, `store` has no `player_fx` change and save not called; `save=True` → stored.
- [ ] **Step 2: Run** the two test files — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — PASS; full suite (layering test must stay green).
- [ ] **Step 5: Commit** — "Run effects in the output callback; controller owns effect settings".

### Task 4: FxStrip widget

**Files:**
- Create: `funplayer/ui/fx_strip.py`
- Test: `tests/test_fx_strip.py`

**Interfaces:**
- Consumes: `FxSettings`, `PRESETS`, `CUSTOM`, `BAND_LABELS`, `BANDS_HZ` (Task 1); `INFO_COLOR` from `funplayer.ui.colors`.
- Produces: `class FxStrip(QWidget)`:
  - Signals: `changed = pyqtSignal(object, bool)` → `(FxSettings, final)`; `final` is False while a slider is being dragged and True on release and for every discrete change (checkbox, preset, mode radio, reset). `open_changed = pyqtSignal(bool)`.
  - `set_value(fx: FxSettings) -> None` (updates widgets without emitting), `value -> FxSettings`, `set_open(on: bool)`, `is_open -> bool`.
  - Public children for tests: `fold_button` (QToolButton), `enabled_box` (QCheckBox `켜기`), `preset_combo` (QComboBox: the 10 presets then `사용자 설정`), `band_sliders` (list of 10 vertical QSlider, range -12..12), `mode_buttons` (dict `"off"|"speaker"|"earphone"` → QRadioButton), `reset_button`, `level_sliders` (dict `"width"|"depth"|"bass"` → horizontal QSlider 0..100), `summary_label`.
  - Layout per mockup and spec §2; level row shows only the sliders of the current mode (none for off). Expanded: header shows `켜기` and preset; collapsed: header shows `summary_label` only, body hidden.
  - Tooltips per Global copy, updated on value change.
  - Drag throttle: while a slider is dragged, emit `changed(value, False)` at most every 50 ms (QTimer single-shot coalescing); on `sliderReleased` emit `changed(value, True)`. Keyboard/wheel changes (no drag) emit `(value, True)` directly.

- [ ] **Step 1: Failing tests** (`qapp` fixture from conftest):
  - `test_preset_moves_sliders_and_emits_final`: pick `발라드` in combo → slider values equal preset, one `changed` with `final=True`, `value.preset == "발라드"`.
  - `test_slider_makes_custom`: `band_sliders[0].setValue(5)` (not dragging) → combo text `사용자 설정`, last emit final True, `value.bands[0] == 5`.
  - `test_drag_throttled_and_final_on_release`: `setSliderDown(True)`, set values 1..10 rapidly, process events < 50 ms → at most 1 non-final emit; `setSliderDown(False)` / emit `sliderReleased` → last emit final True with value 10.
  - `test_mode_rows`: off → no level slider visible; speaker → only `width` visible; earphone → `depth` and `bass` visible.
  - `test_fold_and_summary`: `fold_button.click()` → `is_open False`, body hidden, `summary_label` visible with `fx.summary()`, tooltip `펼치기`; `open_changed(False)` emitted.
  - `test_set_value_does_not_emit` and `test_reset_button` (reset keeps enabled, emits final).
  - `test_tooltips`: band 5 at +3 → `1 kHz: +3 dB`; band 0 at 0 → `31 Hz: 0 dB`; width 40 → `넓이 40%`.
- [ ] **Step 2–4:** run `tests/test_fx_strip.py` (FAIL → implement → PASS), full suite.
- [ ] **Step 5: Commit** — "Add the sound effects strip widget".

### Task 5: Panel integration

**Files:**
- Modify: `funplayer/ui/player_panel.py` (create strip + its separator line between `self.separator` and `self.tab_bar`; view menu item; `SHORTCUTS` gets `("Ctrl+E", "toggle_fx_visible")`; `_apply_visibility`/`set_mini`; wiring)
- Modify: `CLAUDE.md` (file table/list: `core/effects.py`, `engine/fx.py`, `ui/fx_strip.py`) and `docs/개발로드맵.md` §5 structure lines for the same files
- Test: `tests/test_panel_fx.py`; update `tests/test_panel_input.py` shortcut table test

**Interfaces:**
- Consumes: `FxStrip` (Task 4), `PlayerController.effects/set_effects` (Task 3), `Settings.fx_visible/fx_open` (Task 1).
- Produces: `PlayerPanel.fx_strip`, `PlayerPanel.toggle_fx_visible() -> None`, action key `"fx_visible"` in `self.actions` (checkable, text from Global copy).
- Rules:
  - Strip and its line visible iff `settings.fx_visible and not is_mini`.
  - Startup: `fx_strip.set_value(controller.effects)`, `set_open(settings.fx_open)`.
  - `fx_strip.changed(fx, final)` → `controller.set_effects(fx, save=final)`.
  - `fx_strip.open_changed(on)` → `settings.fx_open = on`.

- [ ] **Step 1: Failing tests** (`make_panel` helper as in test_panel_radio.py):
  - `test_fx_hidden_by_default_and_menu_toggles`: strip hidden; trigger `actions["fx_visible"]` → visible, checked, `settings.fx_visible` True; `shortcuts["Ctrl+E"].activated.emit()` → hidden again.
  - `test_fx_strip_sits_between_controls_and_tabs`: layout index of strip is greater than the separator's and less than `tab_bar`'s.
  - `test_fx_hidden_in_mini_and_back`: visible → `set_mini(True)` hidden → `set_mini(False)` visible.
  - `test_fx_changes_reach_player_and_save_on_final`: drag-like `changed(fx, False)` → FakePlayer.effects updated, store unchanged; `changed(fx, True)` → store `player_fx` equals `fx.to_dict()`.
  - `test_fx_state_survives_restart`: store with `player_fx` (발라드, enabled), `player_fx_visible True`, `player_fx_open False` → new panel shows strip collapsed with summary `켜짐 · 발라드`, FakePlayer.effects.preset `발라드`.
  - Shortcut table test lists `Ctrl+E`.
- [ ] **Step 2–4:** run, implement, full suite twice.
- [ ] **Step 5: Commit** — "Add the sound effects strip to the panel".

### Task 6: Real check (controller, not an implementer)

- Offscreen real panel + real device: play a test song and a radio station with effects off/on, 발라드/록/베이스 강하게, speaker and earphone, all bands +12 at full volume; log callback peak (must stay ≤ 1.0) and per-block processing time.
- Capture `docs/images/stage4_real.png` (strip expanded, collapsed, mini).
- Update the artifact page into the stage 4 check page with spec §7 checklist. Stop at the user checklist gate.
