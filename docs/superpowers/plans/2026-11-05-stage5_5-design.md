# 5.5단계 디자인 개편 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** my-fun 화면을 승인된 시안(탭 4개, 긴 막대 미니, 테두리 없는 둥근 창, 테마 12종)으로 바꾼다.

**Architecture:** 색은 Qt 없는 `core/themes.py`가 갖고, `ui/style.py`가 QSS로 바꾼다. `PlayerPanel`은 기존 위젯 이름과 슬롯을 유지하고 배치만 `QStackedWidget` 페이지로 옮긴다.

**Tech Stack:** Python 3.13/3.14, PyQt5 5.15 (QtSvg 포함), pytest

**Spec:** `docs/stage5_5_design.md`. 시안: `docs/design55/mockup.html`, 색 원본: `docs/design55/themes1.js`, `themes2.js`, 아이콘 경로: `docs/design55/icons.js`.

## Global Constraints
- 브랜치 `stage5.5-design`에서 작업한다. main에 합치거나 push하지 않는다.
- PySide6를 import하지 않는다. `core/`, `engine/`, `controller.py`, `radio.py`는 Qt를 import하지 않는다.
- 화면 문구는 한국어다. 알송의 코드·아이콘·문구를 쓰지 않는다.
- 사용자의 음악 파일에 쓰지 않는다. 자동 테스트는 실제 소리 장치를 쓰지 않는다.
- 추적하지 않는 사용자 파일(저장소 맨 위 png, jpg, m3u8, Test-mp3 등)을 커밋하지 않는다. `git add`는 파일을 지정해서 한다.
- 커밋 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.
- 테스트: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -W error::SyntaxWarning` (G:\REA-test\my-fun에서). 각 작업 끝에 전체 통과.
- 위젯 이름이 없어지거나 동작이 바뀐 경우에만 기존 테스트를 고친다. 지우기 전에 같은 동작을 새 구조에서 검증하는 테스트로 바꾼다.

## Review Focus
1. **이전 버전 설정:** 저장된 창 크기 380×480, 미니 304×100, `player_fx_visible` 등이 있어도 새 최소 크기 이상으로 열린다. (Task 5, 6 테스트)
2. **`setStyleSheet` 빈도:** 앨범 색 테마에서 200ms 새로고침마다 스타일을 다시 적용하면 멈춘다. 곡이 바뀌어 색이 달라질 때만 적용한다. (Task 7 테스트)
3. **작업 표시줄 최소화·복원:** 테두리 없는 창도 작업 표시줄 클릭과 Win+D로 최소화된다. `Qt.WindowMinimizeButtonHint`를 켠다. (Task 5 테스트, 사용자 확인)
4. **항상 위 전환:** 미니 전환으로 창 플래그가 바뀌어도 테두리 없음·투명 바탕이 유지된다. (Task 6 테스트)
5. **대화상자 오염:** 패널 QSS가 곡 정보·태그 창의 입력칸과 버튼 모양을 바꾸지 않는다. (Task 2 테스트)

---

### Task 1: 테마 데이터와 설정

**Files:**
- Create: `funplayer/core/themes.py`, `tests/test_themes.py`
- Modify: `funplayer/core/settings.py`, `tests/test_settings.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Theme`: `id, name, desc: str`; 필드는 시안 토큰과 같은 이름 `bg, bar, bar_fg, tabs, tab_fg, tab_on, tab_line, ink, mute, line, acc, acc2, acc_t, g1, g2, on_acc, track, tint, row_fg, icon, ic2, edge, ctrl_bg, fav, mini_edge, strip_bg: str`; `art: tuple[str, str, str, str]`; `spec: tuple[str, ...]`; `foot: tuple[tuple[str, str], ...]`(4쌍 또는 빈 값); `hero: dict[str, str]`, `mini: dict[str, str]`.
  - 기본값 규칙은 `build.js`와 같다: `tab_fg=mute, tab_on=acc_t, tab_line=acc, row_fg=acc_t, strip_bg=tabs, ic2=icon, acc2=acc`, `mini`가 비면 `hero`를 쓴다.
  - `THEMES: tuple[Theme, ...]` (순서: light, dark, mid, c, d, f, g, h, i, k, l, m), `THEME_IDS`, `DEFAULT_THEME = "light"`, `get_theme(id: str) -> Theme` (모르는 id면 기본).
  - `accent_from_pixels(pixels: list[tuple[int, int, int]]) -> str | None`: 채도 0.25 이상, 밝기 0.15~0.95 픽셀의 평균 색상을 hex로. 해당 픽셀이 없으면 None.
  - `album_theme(accent: str | None) -> Theme`: `None`이면 기본 보라 `#C9B6FF`.
  - `Settings.theme` (str, 잘못된 값이면 `"light"`), `TABS = ("now", "playlist", "radio", "fx")`, `DEFAULTS["player_tab"] = "now"`.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_themes.py`, `tests/test_settings.py`)

```python
def test_twelve_themes_without_j():
    assert THEME_IDS == ("light", "dark", "mid", "c", "d", "f", "g", "h", "i", "k", "l", "m")

def test_unknown_theme_falls_back():
    assert get_theme("j").id == "light"

@pytest.mark.parametrize("t", THEMES, ids=lambda t: t.id)
def test_text_contrast(t):
    for fg, bg in ((t.ink, t.bg), (t.mute, t.bg), (t.tab_fg, t.tabs), (t.row_fg, t.tint)):
        if solid(fg) and solid(bg):
            assert contrast(fg, bg) >= 4.4

@pytest.mark.parametrize("hue", range(0, 360, 30))
def test_album_theme_readable_for_any_hue(hue):
    t = album_theme(hsl_hex(hue, .7, .5))
    assert contrast(t.ink, t.bg) >= 7 and contrast(t.acc, t.bg) >= 4.5

def test_accent_ignores_gray_and_empty():
    assert accent_from_pixels([(128, 128, 128)] * 50) is None
    assert accent_from_pixels([]) is None

def test_settings_theme_default_and_invalid(settings_factory):
    assert settings_factory({}).theme == "light"
    assert settings_factory({"player_theme": "j"}).theme == "light"

def test_old_tab_values_still_valid(settings_factory):
    assert settings_factory({"player_tab": "radio"}).tab == "radio"
```

`solid`, `contrast`, `hsl_hex`는 테스트 파일 안의 작은 도우미로 둔다. 네추럴 미드 상단바 대비는 시안대로 4.43이므로 이 검사에 넣지 않는다.

- [ ] **Step 2: 테스트 실패 확인**
- [ ] **Step 3: 구현.** 색값은 `docs/design55/themes1.js`, `themes2.js`에서 그대로 옮기고 J는 뺀다. 그라데이션은 CSS 문자열 그대로 둔다 (`style.py`가 변환). `c`는 `album_theme(None)`에 id·name·desc를 붙인 것이다. `album_theme`의 색은 HSL로 `bg=(h,.30,.13), bar/tabs=(h,.33,.10), tint=(h,.30,.26), acc=g1=(h,.80,.82), g2=(h,.65,.70)`, 글자는 `ink=#F1F3F5, mute=#B4BCC6`, 흰 투명 값은 themes2.js의 `cover()`와 같다.
- [ ] **Step 4: 테스트 통과 확인**
- [ ] **Step 5: 커밋** `feat(5.5): theme data and settings`

---

### Task 2: 글꼴, 아이콘, 기본 그림, QSS

**Files:**
- Create: `funplayer/ui/fonts.py`, `funplayer/ui/glyphs.py`, `funplayer/ui/style.py`, `funplayer/assets/fonts/NotoSansKR-Regular.otf`, `NotoSansKR-Bold.otf`, `OFL.txt`, `funplayer/assets/LICENSES.md`, `tests/test_style.py`, `tests/test_glyphs.py`
- Modify: `funplayer/ui/cover.py`, `funplayer/__main__.py`, `tests/test_cover.py`

**Interfaces:**
- Consumes: `Theme`
- Produces:
  - `fonts.load_fonts() -> str`: 글꼴을 등록하고 패밀리 이름을 돌려준다. 파일이 없거나 실패하면 로그를 남기고 `"Malgun Gothic"`.
  - `glyphs.glyph(name: str, color: str, size: int = 20) -> QIcon`, `glyphs.glyph_pixmap(...) -> QPixmap`. 이름은 `icons.js`의 키. 모르는 이름은 `KeyError`.
  - `cover.rounded_art(src: QPixmap | None, size: int, radius: int, theme: Theme) -> QPixmap`: `src`를 가득 채워 자르고 둥글게. `None`이면 `theme_art`.
  - `cover.theme_art(theme: Theme, size: int) -> QPixmap`: `art` 4색 언덕 그림 (`themes2.js`의 `artSvg`와 같은 모양).
  - `cover.radio_art_for(theme: Theme, size: int, radius: int) -> QPixmap`: g1→g2 그라데이션 + `radio` 글리프(on_acc 색).
  - `style.qcolor_gradient(css: str) -> str`: CSS 색 또는 `linear-gradient(...)`, `rgba(...)`를 QSS 값으로.
  - `style.stylesheet(theme: Theme, family: str) -> str`: objectName 선택자만 쓴 패널 QSS. 뒤 작업에서 쓰는 이름: `root, titleBar, tabs, pageNow, pagePlaylist, pageRadio, pageFx, footBar, nowStrip, miniBar, pill, foot0..foot3`.

- [ ] **Step 1: 글꼴 받기.** noto-cjk 저장소의 `Sans/SubsetOTF/KR/NotoSansKR-Regular.otf`, `-Bold.otf`, `LICENSE`를 `funplayer/assets/fonts/`에 저장한다 (`LICENSE`는 `OFL.txt`로). 파일이 OTF가 맞는지 첫 4바이트(`OTTO`)로 확인한다. 받지 못하면 멈추고 보고한다. `LICENSES.md`에 Noto Sans KR(OFL)과 Lucide(ISC) 출처를 적는다.
- [ ] **Step 2: 실패하는 테스트 작성**

```python
def test_gradient_to_qss():
    v = qcolor_gradient("linear-gradient(90deg,#2B3D63,#8A5A7C 55%,#C46A5A)")
    assert v.startswith("qlineargradient(") and "stop:0.55 #8A5A7C" in v

@pytest.mark.parametrize("t", THEMES, ids=lambda t: t.id)
def test_stylesheet_builds_for_all_themes(qapp, t):
    QWidget().setStyleSheet(stylesheet(t, "Noto Sans KR"))
    assert "linear-gradient" not in stylesheet(t, "x")

def test_stylesheet_uses_object_selectors_only():
    # QSS가 대화상자에 번지면 안 된다 (Review Focus 5): 맨몸 위젯 선택자 금지
    for line in stylesheet(get_theme("dark"), "x").splitlines():
        assert not re.match(r"^\s*(QPushButton|QLineEdit|QLabel|QComboBox|QDialog|QWidget)\s*[{,]", line)

def test_all_glyphs_render(qapp):
    for name in GLYPHS:
        assert not glyph_pixmap(name, "#112233", 24).toImage().isNull()

def test_rounded_art_fills_square_and_clips_corner(qapp):
    src = QPixmap(100, 40); src.fill(Qt.red)
    img = rounded_art(src, 64, 12, get_theme("light")).toImage()
    assert img.pixelColor(32, 2).red() > 200       # 위아래 빈틈 없음
    assert img.pixelColor(0, 0).alpha() == 0       # 모서리 투명

def test_load_fonts_falls_back(monkeypatch, qapp):
    monkeypatch.setattr(fonts, "FONT_DIR", Path("없는곳"))
    assert fonts.load_fonts() == "Malgun Gothic"
```

- [ ] **Step 3: 테스트 실패 확인**
- [ ] **Step 4: 구현.** `glyph`는 `QSvgRenderer`로 `icons.js` 경로를 그린다 (`currentColor`를 색으로 치환, viewBox 24, 선 굵기 1.9, 둥근 끝). `stylesheet`는 `docs/design55/mockup.html`의 `<style>` 수치(탭 글자 12px, 탭 선택 3px 밑줄, 버튼 모서리 8px, 슬라이더 홈 5px·손잡이 13px)를 따른다. `__main__.main`에서 `load_fonts()` 결과를 `app.setFont(QFont(family, 9))`로 넣고 `PlayerPanel`에 `font_family=family`로 넘긴다.
- [ ] **Step 5: 테스트 통과 확인**
- [ ] **Step 6: 커밋** `feat(5.5): fonts, glyphs, themed art and stylesheet` (assets 파일 포함)

---

### Task 3: 탭 4개와 페이지 구조

**Files:**
- Create: `funplayer/ui/icon_tabs.py`, `funplayer/ui/now_strip.py`, `tests/test_icon_tabs.py`, `tests/test_now_strip.py`
- Modify: `funplayer/ui/player_panel.py`, `funplayer/ui/playlist_view.py`, `funplayer/ui/station_view.py`, `tests/test_panel_*.py`

**Interfaces:**
- Consumes: Task 1, 2 전부
- Produces:
  - `IconTabs(QWidget)`: `addTab(icon_name, title)`, `currentIndex()`, `setCurrentIndex(i)`, `count()`, 신호 `currentChanged(int)`, `set_theme(theme)`. QToolButton + `ToolButtonTextUnderIcon`, 배타 선택.
  - `NowStrip(QWidget)`: 신호 `prevClicked, toggleClicked, nextClicked, openClicked`; `set_track(pixmap, title, subtitle, playing, ratio: float)`, `set_theme(theme)`.
  - `PlayerPanel`: 상수 `TABS = ("now", "playlist", "radio", "fx")`, `TAB_TITLES = ("지금 재생", "재생목록", "라디오", "음향 효과")`, 위젯 `self.pages: QStackedWidget`, `self.now_strip`, `self.heart_button`, 메서드 `toggle_current_favorite()`, `apply_theme(theme: Theme)`. 생성자에 `font_family: str = "Malgun Gothic"`.
  - `ART_NORMAL = 216`, `ART_MINI = 80`.
  - `source_menu: QMenu` (항목 "정지", "라디오로"/"MP3로"). `play_button`, `title_label`의 오른쪽 클릭에서 연다.
  - `PlaylistView.set_theme(theme)`와 줄 그리기 delegate. 줄 데이터 역할 `ROLE_NUMBER, ROLE_CURRENT, ROLE_FAVORITE`. `item.text()`는 지금과 같게 둔다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_four_tabs_and_default_now(panel):
    assert panel.tab == "now" and panel.tab_bar.count() == 4
    assert panel.pages.currentWidget().objectName() == "pageNow"

@pytest.mark.parametrize("name,page", [("playlist", "pagePlaylist"), ("radio", "pageRadio"), ("fx", "pageFx")])
def test_set_tab_shows_page_and_strip(panel, name, page):
    panel.set_tab(name)
    assert panel.pages.currentWidget().objectName() == page
    assert not panel.now_strip.isHidden()

def test_now_tab_hides_strip(panel):
    panel.set_tab("playlist"); panel.set_tab("now")
    assert panel.now_strip.isHidden()

def test_stop_lives_in_source_menu(panel):
    texts = [a.text() for a in panel.source_menu.actions()]
    assert "정지" in texts and not hasattr(panel, "stop_button")

def test_stop_shortcut_still_works(panel): ...      # V 키가 panel.stop을 부른다

def test_heart_toggles_current_track(panel_with_tracks):
    panel = panel_with_tracks
    panel.heart_button.click()
    assert panel.heart_button.isChecked()
    assert panel.controller.playlist.current.path in {t.path for t in favorites(panel)}

def test_heart_on_radio_toggles_station(panel_on_radio):
    panel_on_radio.heart_button.click()
    assert panel_on_radio.stations.is_favorite(panel_on_radio.radio.station.id)

def test_ctrl_e_toggles_fx_tab(panel):
    panel.toggle_fx_visible(); assert panel.tab == "fx"
    panel.toggle_fx_visible(); assert panel.tab == "now"

def test_spectrum_runs_only_on_fx_tab(panel_playing):
    panel_playing.set_tab("now"); assert not panel_playing._spectrum_wanted()
    panel_playing.set_tab("fx");  assert panel_playing._spectrum_wanted()

def test_strip_shows_current_track_and_buttons_work(panel_with_tracks): ...
def test_ctrl_tab_cycles_four_tabs(panel): ...
def test_ctrl_d_on_now_tab_toggles_current(panel_with_tracks): ...
```

fixture 이름은 `tests/conftest.py`와 `test_panel_*.py`에 이미 있는 것을 쓰고, 없으면 같은 방식으로 만든다.

- [ ] **Step 2: 테스트 실패 확인**
- [ ] **Step 3: 구현.** `_build`를 페이지별 메서드로 나눈다: `_build_now_page`, `_build_list_page`, `_build_radio_page`, `_build_fx_page`. 치수는 시안을 따른다 (상단바 자리 44, 탭 64, 재생 버튼 60, 띠 58 + 진행선 3). 재생목록 페이지 아래에 열기·추가·목록·보기와 곡 수, 라디오 페이지 아래에 주소 넣기·보기와 방송 수를 둔다. [보기] 단추는 하나만 있어야 하므로 탭이 바뀔 때 해당 줄로 옮긴다. `status_label`은 지금 재생 페이지 소리 막대 아래, 재생 띠 위에 공용으로 둔다. `fx_visible` 메뉴 항목과 `fx_strip` 접기는 없앤다. `refresh`에서 하트 상태와 `now_strip.set_track`을 갱신한다. 재생 띠 그림은 곡이 바뀔 때만 다시 만든다. 곡 정보는 그림 클릭으로 연다. 라디오에서는 재생 막대 자리에 LIVE 줄을 둔다 (시안의 '라디오를 듣는 중').
- [ ] **Step 4: 테스트 통과 확인, 기존 패널 테스트를 새 구조에 맞게 수정**
- [ ] **Step 5: 커밋** `feat(5.5): four tab pages, now strip and heart`

---

### Task 4: 음향 효과 탭 모양과 스펙트럼 색

**Files:**
- Modify: `funplayer/ui/fx_strip.py`, `funplayer/ui/spectrum_view.py`, `tests/test_fx_strip.py`, `tests/test_spectrum_view.py`

**Interfaces:**
- Consumes: `Theme`
- Produces: `FxStrip.set_theme(theme)`, `SpectrumView.set_colors(colors: tuple[str, ...], peak: str)`. `spec`가 비면 g1을 쓴다. 막대 수는 24로 고정한다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_fx_order_matches_mockup(qapp):      # 위에서 아래로: 제목·켜기, 스펙트럼, 프리셋·초기화, 밴드 10개, 듣는 곳, 세기
    s = FxStrip(); s.resize(344, 420); s.show()
    ys = [s.enabled_box, s.spectrum, s.preset_combo, s.band_sliders[0]]
    assert sorted(w.mapTo(s, QPoint()).y() for w in ys) == [w.mapTo(s, QPoint()).y() for w in ys]

def test_spectrum_colors_split_evenly(qapp):
    v = SpectrumView(); v.set_colors(("#111111", "#222222", "#333333"), "#444444")
    assert [v.bar_color(i, 24) for i in (0, 8, 16)] == ["#111111", "#222222", "#333333"]

def test_all_fx_values_still_change_on_controls(qapp): ...   # 프리셋, 밴드, 듣는 곳, 세기, 초기화 신호 유지
```

- [ ] **Step 2: 테스트 실패 확인**
- [ ] **Step 3: 구현.** 접기·펼치기 단추와 `set_open` 호출 경로를 지우고 배치를 시안 순서로 옮긴다. 글자색 하드코딩(`SMALL_STYLE`, `_link_label`)을 테마 값으로 바꾼다. 듣는 곳은 라디오 단추를 유지하되 QSS로 세 칸 묶음 모양을 만든다. 효과 값·신호·저장은 바꾸지 않는다.
- [ ] **Step 4: 테스트 통과 확인**
- [ ] **Step 5: 커밋** `feat(5.5): effects tab layout and themed spectrum`

---

### Task 5: 상단바와 테두리 없는 창

**Files:**
- Create: `funplayer/ui/title_bar.py`, `tests/test_title_bar.py`
- Modify: `funplayer/ui/player_panel.py`, `funplayer/ui/window_keeper.py`, `funplayer/__main__.py`, `tests/test_window_keeper.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `glyph`, `Theme`
- Produces:
  - `TitleBar(QWidget)`: 신호 `miniClicked, minimizeClicked, maximizeClicked, closeClicked`; `set_theme(theme)`, `set_maximized(on)`. 왼쪽 버튼 끌기는 `windowHandle().startSystemMove()`, 더블클릭은 `maximizeClicked`, 오른쪽 클릭은 `menu_requested` 신호.
  - `EdgeGrips(QObject)`: `EdgeGrips(window, thickness=6)`. 8방향 투명 위젯을 올려 `startSystemResize(edges)`를 부른다. `set_enabled_edges(horizontal_only: bool)`.
  - `PlayerPanel.use_window_chrome()`: `Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint`, `WA_TranslucentBackground`, 그립 생성. `self.chrome: bool`.
  - `window_keeper.DEFAULT_SIZE = (380, 620)`, `MIN_SIZE = (340, 560)`.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_old_saved_size_is_raised_to_minimum(qapp, panel, settings):
    settings.geometry = [10, 10, 380, 480]
    WindowKeeper(panel, settings).start()
    assert panel.height() >= 560 and panel.width() >= 340

def test_chrome_keeps_flags_minimizable(panel):
    panel.use_window_chrome()
    assert panel.windowFlags() & Qt.FramelessWindowHint
    assert panel.windowFlags() & Qt.WindowMinimizeButtonHint
    assert panel.testAttribute(Qt.WA_TranslucentBackground)

def test_panel_without_chrome_stays_plain(panel):      # 6단계 캘린더용
    assert not panel.windowFlags() & Qt.FramelessWindowHint

def test_titlebar_buttons_emit(qapp): ...
def test_maximize_toggle_and_square_corners(panel): ...  # 최대화 때 모서리 반지름 0, 복원 때 20
def test_main_uses_chrome(monkeypatch, ...): ...
```

- [ ] **Step 2: 테스트 실패 확인**
- [ ] **Step 3: 구현.** 전체 내용을 `objectName="root"` 위젯 안에 넣어 둥근 배경을 준다. 상단바와 맨 아래 줄은 위쪽·아래쪽 모서리만 둥글게 한다. 최대화 때는 `setGeometry(screen.availableGeometry())`가 아니라 `showMaximized`를 쓰되 작업 표시줄을 덮으면 `setMaximumSize(availableGeometry.size())`로 막는다. `WindowKeeper._store`의 `normalGeometry` 경로를 유지한다.
- [ ] **Step 4: 테스트 통과 확인**
- [ ] **Step 5: 커밋** `feat(5.5): frameless rounded window with title bar`

---

### Task 6: 긴 막대 미니 모드

**Files:**
- Modify: `funplayer/ui/player_panel.py`, `funplayer/ui/window_keeper.py`, `tests/test_panel_view.py`, `tests/test_panel_input.py`, `tests/test_panel_radio.py`, `tests/test_window_keeper.py`

**Interfaces:**
- Consumes: `IconTabs`, `TitleBar`, `EdgeGrips`
- Produces: `MINI_SIZE = (680, 104)`, 위젯 `self.mini_bar`, `self.list_button_mini`, `self.mini_controls`(최소화, 보통 보기, 닫기). `set_mini(on)`는 공용 위젯(`art_label, title_label, artist_label, heart_button, elapsed_label, seek_slider, total_label, shuffle_button, prev_button, play_button, next_button, repeat_button, mute_button, volume_slider, live_label, listened_label`)을 `now` 또는 `mini` 배치로 옮기는 `_place_shared(mini: bool)`를 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_mini_size_and_shared_widgets(panel):
    panel.set_mini(True)
    assert panel.art_label.width() == 80 and panel.play_button.window() is panel
    assert panel.seek_slider.parent() is panel.mini_bar or panel.mini_bar.isAncestorOf(panel.seek_slider)
    panel.set_mini(False)
    assert panel.pages.widget(0).isAncestorOf(panel.seek_slider)

def test_mini_list_button_opens_playlist(panel):
    panel.set_mini(True); panel.list_button_mini.click()
    assert not panel.is_mini and panel.tab == "playlist"

def test_old_mini_geometry_raised(panel, settings):
    settings.mini_geometry = [5, 5, 304, 100]
    keeper = WindowKeeper(panel, settings); keeper.start(); panel.set_mini(True)
    assert (panel.width(), panel.height()) == (680, 104)

def test_chrome_survives_on_top_toggle(panel, settings):
    panel.use_window_chrome(); WindowKeeper(panel, settings).start(); panel.set_mini(True)
    assert panel.windowFlags() & Qt.FramelessWindowHint
    assert panel.testAttribute(Qt.WA_TranslucentBackground)

def test_radio_mini_shows_live(panel_on_radio): ...       # seek 대신 LIVE·들은 시간
def test_mini_drag_area_starts_move(panel): ...
```

- [ ] **Step 2: 테스트 실패 확인**
- [ ] **Step 3: 구현.** 배치 폭은 시안을 따른다 (그림 80, 곡 정보 206, 조작부, 소리 92, 목록 26, 사이 12). 높이 104, 폭은 680 고정 최소에서 가로로만 늘린다. 재생 버튼은 미니에서 46px. 빈 곳을 끌면 창이 움직인다. `HIDDEN_IN_MINI`는 페이지·탭·띠 단위로 줄인다.
- [ ] **Step 4: 테스트 통과 확인**
- [ ] **Step 5: 커밋** `feat(5.5): long bar mini mode`

---

### Task 7: 설정 창과 테마 적용

**Files:**
- Create: `funplayer/ui/settings_dialog.py`, `tests/test_settings_dialog.py`, `tests/test_panel_theme.py`
- Modify: `funplayer/ui/player_panel.py`

**Interfaces:**
- Consumes: `THEMES`, `album_theme`, `accent_from_pixels`, `apply_theme`, 각 부품의 `set_theme`
- Produces: `SettingsDialog(current_id, parent)`: 신호 `themePicked(str)`, 테마마다 색 점 5개와 이름이 있는 목록. 고르면 바로 미리 보이고, [취소]하면 처음 테마로 돌아간다. `PlayerPanel.show_settings()`, 메뉴 "설정…"(view_menu 맨 위). `PlayerPanel._album_accent: str | None`.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_default_theme_is_light(panel):
    assert panel.theme.id == "light"

def test_settings_lists_twelve(qapp):
    assert SettingsDialog("light").theme_list.count() == 12

def test_pick_previews_and_cancel_restores(panel, settings):
    d = panel.show_settings(modal=False); d.themePicked.emit("dark")
    assert panel.theme.id == "dark"
    d.reject()
    assert panel.theme.id == "light" and settings.theme == "light"

def test_accept_saves(panel, settings): ...

def test_album_theme_applies_only_when_accent_changes(panel_with_tracks, monkeypatch):
    calls = []
    monkeypatch.setattr(panel, "setStyleSheet", lambda s: calls.append(s))
    panel.set_theme_id("c"); calls.clear()
    for _ in range(5): panel.refresh()
    assert calls == []          # Review Focus 2

def test_album_theme_radio_uses_default_accent(panel_on_radio): ...
def test_all_themes_apply_without_error(panel): ...      # 12종 전부, 미니·보통
def test_theme_change_updates_art_without_cover(panel): ... # 그림 없는 곡의 그림이 새 테마 색
```

- [ ] **Step 2: 테스트 실패 확인**
- [ ] **Step 3: 구현.** `apply_theme`는 `self.setStyleSheet`, 부품 `set_theme`, 아이콘·그림 다시 만들기를 한 곳에서 한다. 앨범 색은 곡이 바뀔 때 표지를 32×32로 줄여 `accent_from_pixels`로 계산한다. 값이 같으면 아무것도 하지 않는다.
- [ ] **Step 4: 테스트 통과 확인**
- [ ] **Step 5: 커밋** `feat(5.5): settings dialog and live theme switching`

---

### Task 8: 문서 정리

**Files:**
- Modify: `CLAUDE.md`, `docs/개발로드맵.md`

- [ ] **Step 1:** `CLAUDE.md` 파일 목록에 새 파일 설명을 추가하고, 로드맵에 5.5단계 결과를 적는다. "사용자 확인 대기"로 표시한다.
- [ ] **Step 2: 전체 테스트 실행.** 전부 통과해야 한다.
- [ ] **Step 3: 커밋** `docs(5.5): record design stage`
