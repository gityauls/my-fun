"""Colour themes (stage 5.5). Pure data and colour maths; no Qt here.

Values come from docs/design55/themes1.js and themes2.js (theme J is dropped, there is no
window shadow). Gradients stay CSS strings; the style layer converts them.
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass, field, replace

DEFAULT_THEME = "light"
DEFAULT_ALBUM_ACCENT = "#C9B6FF"


@dataclass(frozen=True)
class Theme:
    id: str
    name: str
    desc: str
    bg: str
    bar: str
    bar_fg: str
    tabs: str
    tab_fg: str
    tab_on: str
    tab_line: str
    ink: str
    mute: str
    line: str
    acc: str
    acc2: str
    acc_t: str
    g1: str
    g2: str
    on_acc: str
    track: str
    tint: str
    row_fg: str
    icon: str
    ic2: str
    edge: str
    ctrl_bg: str
    fav: str
    mini_edge: str
    strip_bg: str
    art: tuple[str, str, str, str] = ("", "", "", "")
    spec: tuple[str, ...] = ()
    foot: tuple[tuple[str, str], ...] = ()
    hero: dict[str, str] = field(default_factory=dict)
    mini: dict[str, str] = field(default_factory=dict)


_CAMEL = {"barFg": "bar_fg", "accT": "acc_t", "onAcc": "on_acc", "tabFg": "tab_fg",
          "tabOn": "tab_on", "tabLine": "tab_line", "rowFg": "row_fg", "ctrlBg": "ctrl_bg",
          "miniEdge": "mini_edge", "stripBg": "strip_bg"}


def _snake(d: dict[str, str]) -> dict[str, str]:
    return {_CAMEL.get(k, k): v for k, v in d.items()}


def _make(id: str, name: str, desc: str, v: dict[str, str], art=("", "", "", ""),
          hero=None, mini=None, foot=(), spec=()) -> Theme:
    s = _snake(v)
    s.setdefault("tab_fg", s["mute"])
    s.setdefault("tab_on", s["acc_t"])
    s.setdefault("tab_line", s["acc"])
    s.setdefault("row_fg", s["acc_t"])
    s.setdefault("strip_bg", s["tabs"])
    s.setdefault("ic2", s["icon"])
    s.setdefault("acc2", s["acc"])
    s.pop("shadow", None)
    return Theme(id=id, name=name, desc=desc, art=tuple(art), spec=tuple(spec),
                 foot=tuple(tuple(p) for p in foot), hero=_snake(hero or {}),
                 mini=_snake(mini or {}), **s)


# ---- album colour -----------------------------------------------------------------------

def _hsl_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l, s)
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def _hue(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)[0] * 360


def accent_from_pixels(pixels: list[tuple[int, int, int]]) -> str | None:
    """Average colour of the saturated, mid-bright pixels as hex; None when there are none."""
    total = [0, 0, 0]
    count = 0
    for r, g, b in pixels:
        _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s >= 0.25 and 0.15 <= v <= 0.95:
            total[0] += r
            total[1] += g
            total[2] += b
            count += 1
    if not count:
        return None
    return "#%02X%02X%02X" % tuple(round(c / count) for c in total)


def album_theme(accent: str | None) -> Theme:
    h = _hue(accent or DEFAULT_ALBUM_ACCENT)
    acc = _hsl_hex(h, .80, .82)
    v = {"bg": _hsl_hex(h, .30, .13), "bar": _hsl_hex(h, .33, .10), "barFg": "#F1F3F5",
         "tabs": _hsl_hex(h, .33, .10), "ink": "#F1F3F5", "mute": "#B4BCC6",
         "line": "rgba(255,255,255,.12)", "acc": acc, "accT": acc, "g1": acc,
         "g2": _hsl_hex(h, .65, .70), "onAcc": "#14171C", "track": "rgba(255,255,255,.22)",
         "tint": _hsl_hex(h, .30, .26), "icon": "#E4E8EE", "edge": "rgba(255,255,255,.1)",
         "ctrlBg": "rgba(255,255,255,.1)", "fav": acc, "miniEdge": "rgba(255,255,255,.2)",
         "tabFg": "#B4BCC6"}
    return _make("album", "앨범 색", "곡의 그림에서 색을 뽑아 곡마다 색이 바뀝니다", v,
                 art=("#C9B8F0", "#FBD9E6", "#A98FE0", "#6C3DCB"))


def _album_c() -> Theme:
    t = album_theme(None)
    return replace(t, id="c", name="C 앨범 색")


# ---- themes -----------------------------------------------------------------------------

_LIGHT_ART = ("#C9B8F0", "#FBD9E6", "#A98FE0", "#6C3DCB")
_DARK_ART = ("#2A2A5E", "#E9E4FF", "#3A2F78", "#14152E")
_MID_ART = ("#9CC3DF", "#FBE3C9", "#4F7E9B", "#2B5468")


def _art(sky: str, sun: str, hill1: str, hill2: str) -> tuple[str, str, str, str]:
    return (sky, sun, hill1, hill2)


THEMES: tuple[Theme, ...] = (
    _make("light", "라이트 모던", "밝고 깔끔한 기본 테마 · 보라 포인트", art=_LIGHT_ART, v={
        "bg": "#F8F6FD", "bar": "#FFFFFF", "barFg": "#2A2740", "tabs": "#FBFAFE",
        "ink": "#1B1830", "mute": "#6E6A86", "line": "#E9E5F3", "acc": "#7A4FD6",
        "accT": "#6B3FCB", "g1": "#8E63E6", "g2": "#6C3DCB", "onAcc": "#FFFFFF",
        "track": "#D9D5EA", "tint": "#EFE9FB", "icon": "#2E2B47", "edge": "#E4DFF2",
        "ctrlBg": "#EFECF7", "fav": "#7A4FD6", "miniEdge": "#C7B2F0"}),
    _make("dark", "다크 시티", "눈이 편한 어두운 테마 · 연보라 포인트", art=_DARK_ART, v={
        "bg": "#1C1D2F", "bar": "#191A2A", "barFg": "#ECEAF7", "tabs": "#222338",
        "ink": "#F2F0FB", "mute": "#A3A1BC", "line": "#32334B", "acc": "#B58BF5",
        "accT": "#C4A2F8", "g1": "#BE93F7", "g2": "#8450DB", "onAcc": "#1B1430",
        "track": "#47485F", "tint": "#2E2C4A", "icon": "#D9D7EA", "edge": "#2C2D44",
        "ctrlBg": "#2A2B42", "fav": "#C4A2F8", "miniEdge": "#55577C"}),
    _make("mid", "네추럴 미드", "차분한 푸른 회색 테마 · 청록 포인트", art=_MID_ART, v={
        "bg": "#E8EEF2", "bar": "#657A90", "barFg": "#FFFFFF", "tabs": "#EDF2F5",
        "ink": "#15222F", "mute": "#55677A", "line": "#D1DBE2", "acc": "#1E9C99",
        "accT": "#0D7371", "g1": "#2CA9A5", "g2": "#14827F", "onAcc": "#FFFFFF",
        "track": "#BCCBD5", "tint": "#D6E9E9", "icon": "#223244", "edge": "#D5DFE6",
        "ctrlBg": "#DCE5EA", "fav": "#0D7371", "miniEdge": "#9FB3C4"}),
    _album_c(),
    _make("d", "D 흑연", "짙은 회색 바탕 · 코랄 포인트",
          art=_art("#3A3432", "#F08A72", "#5A5350", "#2A2726"), v={
        "bg": "#1C1A19", "bar": "#151312", "barFg": "#F2EFEC", "tabs": "#242120",
        "ink": "#F2EFEC", "mute": "#ADA6A0", "line": "#35312F", "acc": "#F08A72",
        "accT": "#F4A08B", "g1": "#F59A82", "g2": "#E0705A", "onAcc": "#2A120C",
        "track": "#4A4542", "tint": "#332B28", "icon": "#DDD8D3", "edge": "#2C2826",
        "ctrlBg": "#2E2A28", "fav": "#F4A08B", "miniEdge": "#4A4542"}),
    _make("f", "F 서리", "푸른 회색 상단에 뽀얀 바탕",
          art=_art("#C6CDD8", "#ECEDED", "#8D94A2", "#474C58"), v={
        "bg": "#ECEDED", "bar": "#666D7D", "barFg": "#FFFFFF", "tabs": "#E4E5E4",
        "ink": "#23262E", "mute": "#474C58", "line": "#D3D6DA", "acc": "#4B5160",
        "accT": "#3B404D", "g1": "#666D7D", "g2": "#474C58", "onAcc": "#FFFFFF",
        "track": "#BCC2CC", "tint": "#D8DCE3", "icon": "#2E323C", "edge": "#D3D6DA",
        "ctrlBg": "#DCDEE1", "fav": "#3B404D", "miniEdge": "#9AA2B1"}),
    _make("g", "G 세이지", "차분한 녹회색",
          art=_art("#C9D2C3", "#EEF1EA", "#7F8D7C", "#4E5A4C"), v={
        "bg": "#EEF1EA", "bar": "#6A7867", "barFg": "#FFFFFF", "tabs": "#E6EBE1",
        "ink": "#232B22", "mute": "#4E5A4C", "line": "#D5DCCF", "acc": "#5C6A59",
        "accT": "#47544A", "g1": "#7F8D7C", "g2": "#4E5A4C", "onAcc": "#FFFFFF",
        "track": "#C9D2C3", "tint": "#DCE3D6", "icon": "#2E382D", "edge": "#D5DCCF",
        "ctrlBg": "#E0E6DA", "fav": "#47544A", "miniEdge": "#A9B5A5"}),
    _make("h", "H 남보라", "연보라 바탕에 남색 재생 영역",
          art=_art("#B4B8D2", "#F2F3FA", "#54587A", "#23264A"), v={
        "bg": "#E7E9F6", "bar": "#23264A", "barFg": "#F2F3FA", "tabs": "#D9DCEA",
        "tabFg": "#3A3E63", "ink": "#23264A", "mute": "#54587A", "line": "#C9CCE2",
        "acc": "#3A3E63", "accT": "#2C2F4D", "g1": "#3A3E63", "g2": "#23264A",
        "onAcc": "#F2F3FA", "track": "#C5C9E2", "tint": "#D2D5EA", "icon": "#2C2F4D",
        "edge": "#D9DCEA", "ctrlBg": "#D9DCEA", "fav": "#3A3E63", "miniEdge": "#8D92BB"},
          hero={"bg": "#2C2F4D", "ink": "#F2F3FA", "mute": "#C5C9E2", "icon": "#F2F3FA",
                "ic2": "#C9CCE2", "track": "#54587A", "acc": "#C9CCE2", "acc2": "#C9CCE2",
                "accT": "#C9CCE2", "g1": "#F2F3FA", "g2": "#C9CCE2", "onAcc": "#23264A",
                "line": "#54587A"}),
    _make("i", "I 숲과 테라코타", "아이보리 · 숲색 · 민트 · 테라코타 · 남색",
          art=_art("#E9D9BD", "#C8643C", "#3F7A63", "#1E3A52"), v={
        "bg": "#F4EEE3", "bar": "#1F4D3A", "barFg": "#FBF7EF", "tabs": "#DCEBDD",
        "tabFg": "#2E5A48", "tabOn": "#A8481F", "tabLine": "#C8643C", "ink": "#22302A",
        "mute": "#5C665F", "line": "#DCD3C3", "acc": "#C8643C", "accT": "#A8481F",
        "g1": "#D97A50", "g2": "#C05A32", "onAcc": "#FFFFFF", "track": "#DCD3C3",
        "tint": "#1F4D3A", "rowFg": "#FBF7EF", "icon": "#22302A", "ic2": "#1E3A52",
        "acc2": "#1F4D3A", "edge": "#DCD3C3", "ctrlBg": "#E8DFCF", "fav": "#1E4F78",
        "miniEdge": "#3F7A63", "stripBg": "#FBF7EF"},
          foot=[("#1F4D3A", "#FFFFFF"), ("#B7D9C1", "#1F3D30"), ("#E8B98E", "#4A2A14"),
                ("#1E3A52", "#FFFFFF")],
          spec=("#C8643C", "#3F7A63", "#1E3A52"),
          hero={"bg": "#1F4D3A", "ink": "#FBF7EF", "mute": "#B7D9C1", "icon": "#FBF7EF",
                "ic2": "#B7D9C1", "track": "#3C6F5B", "acc": "#E8926B", "acc2": "#B7D9C1",
                "accT": "#E8926B", "line": "#3C6F5B", "g1": "#E8926B", "g2": "#C8643C"}),
    _make("k", "K 흙과 올리브", "모래색 · 올리브 · 갈색 · 황토색",
          art=_art("#D9B98A", "#F0DCB0", "#8A5A3C", "#5E6B43"), v={
        "bg": "#F6EFE2", "bar": "#5E6B43", "barFg": "#F6EFE2", "tabs": "#E6DAC6",
        "tabFg": "#3A2F25", "tabOn": "#6B3F22", "tabLine": "#8A5A3C", "ink": "#3A2F25",
        "mute": "#695B4C", "line": "#D6C9B3", "acc": "#5E6B43", "accT": "#5E6B43",
        "g1": "#9A6A4A", "g2": "#8A5A3C", "onAcc": "#FFFFFF", "track": "#D6C9B3",
        "tint": "#5E6B43", "rowFg": "#F6EFE2", "icon": "#3A2F25", "ic2": "#8A5A3C",
        "acc2": "#8A5A3C", "edge": "#D6C9B3", "ctrlBg": "#E6DAC6", "fav": "#8A5A3C",
        "miniEdge": "#C9A67A"},
          foot=[("#5E6B43", "#FFFFFF"), ("#8A5A3C", "#FFFFFF"), ("#C9A67A", "#3A2613"),
                ("#E6DAC6", "#3A2F25")],
          spec=("#5E6B43", "#8A5A3C", "#C98F3F")),
    _make("l", "L 노을", "노을 그라데이션 · 남색 · 금색",
          art=_art("#F6C88E", "#FFF1D6", "#C0647A", "#2B3D63"), v={
        "bg": "#FBF8F4", "bar": "linear-gradient(90deg,#2B3D63,#8A5A7C 55%,#C46A5A)",
        "barFg": "#FFFFFF", "tabs": "#F3DCC5", "tabFg": "#3F2412", "tabOn": "#1E2F4D",
        "tabLine": "#1E2F4D", "ink": "#22304A", "mute": "#566377", "line": "#E3DDD5",
        "acc": "#C98638", "accT": "#8F5716", "g1": "#F0B080", "g2": "#E9906A",
        "onAcc": "#3F2412", "track": "#E3DDD5", "tint": "#F6C8A2", "rowFg": "#3F2412",
        "icon": "#22304A", "ic2": "#1F5EA8", "acc2": "#C98638", "edge": "#E3DDD5",
        "ctrlBg": "#EFE6DC", "fav": "#B23320", "miniEdge": "#C98638"},
          foot=[("#1E2F4D", "#FFFFFF"), ("#E9A06C", "#3F2412"), ("#F3D9A4", "#4A3410"),
                ("#9FC0D8", "#14304A")],
          spec=("#2B3D63", "#8A5A7C", "#E9906A", "#E2A95C"),
          hero={"bg": "linear-gradient(170deg,#2B3D63 0%,#6F4F7E 48%,#B05F62 82%,#C46A5A 100%)",
                "ink": "#FFFFFF", "mute": "#FFE9D4", "icon": "#FFFFFF", "ic2": "#FFE08F",
                "track": "rgba(255,255,255,.35)", "acc": "#FFE08F", "acc2": "#FFE08F",
                "accT": "#FFE08F", "line": "rgba(255,255,255,.3)"},
          mini={"bg": "linear-gradient(100deg,#2B3D63 0%,#6F4F7E 45%,#B05F62 80%,#C46A5A 100%)",
                "ink": "#FFFFFF", "mute": "#FFE9D4", "icon": "#FFFFFF", "ic2": "#FFE08F",
                "track": "rgba(255,255,255,.35)", "acc": "#FFE08F", "acc2": "#FFE08F",
                "accT": "#FFE08F", "line": "rgba(255,255,255,.3)"}),
    _make("m", "M 청록과 구리", "청록 회색 · 크림 · 구리색 · 복숭아",
          art=_art("#A9C4BD", "#F2D9BC", "#D18F54", "#3E6B68"), v={
        "bg": "#F5F0E6", "bar": "#3E6B68", "barFg": "#FFFFFF", "tabs": "#A9C4BD",
        "tabFg": "#27393A", "tabOn": "#1F4744", "tabLine": "#1F4744", "ink": "#27393A",
        "mute": "#546A69", "line": "#D9D3C5", "acc": "#C07A3E", "accT": "#8F5219",
        "g1": "#D18F54", "g2": "#B97638", "onAcc": "#2E1A08", "track": "#D9D3C5",
        "tint": "#F2D9BC", "rowFg": "#4A2C10", "icon": "#27393A", "ic2": "#3E6B68",
        "acc2": "#3E6B68", "edge": "#D9D3C5", "ctrlBg": "#E7E0D2", "fav": "#8F5219",
        "miniEdge": "#3E6B68", "stripBg": "#EFE7D8"},
          foot=[("#3E6B68", "#FFFFFF"), ("#D18F54", "#2E1A08"), ("#F2D9BC", "#4A2C10"),
                ("#A9C4BD", "#27393A")],
          spec=("#3E6B68", "#D18F54", "#7FA89F"),
          mini={"bg": "#A9C4BD", "mute": "#2F4443", "line": "#7FA19A", "track": "#7FA19A",
                "acc": "#27393A", "acc2": "#27393A", "accT": "#27393A", "ic2": "#27393A"}),
)

THEME_IDS: tuple[str, ...] = tuple(t.id for t in THEMES)
_BY_ID = {t.id: t for t in THEMES}


def get_theme(id: str) -> Theme:
    return _BY_ID.get(id, _BY_ID[DEFAULT_THEME])
