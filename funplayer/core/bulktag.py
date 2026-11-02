"""여러 곡 태그(5-D): 파일 이름·붙여 넣은 글에서 태그 값을 뽑고, 트랙 번호를 매긴다. Qt 없음."""
from __future__ import annotations

import os
import re

FIELDS = ("artist", "title", "album", "year", "genre", "track")
AUTO = "auto"

# 이름 모양에 쓰는 낱말: 한글과 영어 둘 다 받는다
TOKENS = {"가수": "artist", "제목": "title", "앨범": "album", "년도": "year", "장르": "genre", "트랙": "track",
          "artist": "artist", "title": "title", "album": "album", "year": "year", "genre": "genre",
          "track": "track"}
_TOKEN = re.compile(r"%([^%]+)%")
_LEAD_BRACKET = re.compile(r"^\s*\[([^\]]*)\]\s*")
_PAREN = re.compile(r"\s*\([^)]*\)\s*")
_LEAD_NUMBER = re.compile(r"^\s*(\d{1,3})\s*(?:[.\-_)]\s*|\s+)(?=\S)")
_SPACES = re.compile(r"\s+")


class PatternError(ValueError):
    pass


def _tidy(text: str) -> str:
    return _SPACES.sub(" ", text).strip().strip("_-").strip()


def _track(text: str) -> str:
    return str(int(text)) if text.isdigit() else text


def compile_pattern(pattern: str) -> re.Pattern:
    """'%가수% - %제목%' 같은 모양을 정규식으로. 낱말 사이 글자는 그대로, 빈칸은 있어도 없어도 된다."""
    parts: list[str] = []
    pos = 0
    used: set[str] = set()
    for m in _TOKEN.finditer(pattern):
        field = TOKENS.get(m.group(1).strip().lower()) or TOKENS.get(m.group(1).strip())
        if field is None:
            raise PatternError(f"모르는 낱말: %{m.group(1)}%")
        parts.append(_literal(pattern[pos:m.start()]))
        if field in used:
            parts.append(".+?")
        else:
            parts.append(rf"(?P<{field}>\d+)" if field == "track" else rf"(?P<{field}>.+?)")
            used.add(field)
        pos = m.end()
    parts.append(_literal(pattern[pos:]))
    if not used:
        raise PatternError("%제목% 같은 낱말이 하나는 있어야 합니다")
    return re.compile(r"^\s*" + "".join(parts) + r"\s*$")


def _literal(text: str) -> str:
    return r"\s*".join(re.escape(piece) for piece in text.split(" "))


def match_pattern(text: str, pattern: str) -> dict[str, str]:
    m = compile_pattern(pattern).match(text)
    if not m:
        return {}
    out = {k: _tidy(v) for k, v in m.groupdict().items() if v is not None}
    if "track" in out:
        out["track"] = _track(out["track"])
    return {k: v for k, v in out.items() if v}


def guess_auto(stem: str) -> dict[str, str]:
    """파일 이름(확장자 뺀 것)에서 짐작: [가수]제목, 가수 - 제목, 앞 번호는 트랙, 괄호 군말은 뺀다."""
    name = stem
    artist = ""
    m = _LEAD_BRACKET.match(name)
    if m:
        artist = m.group(1)
        name = name[m.end():]
    name = _PAREN.sub(" ", name)
    out: dict[str, str] = {}
    parts = [p for p in re.split(r"\s+-\s+", name) if p.strip()]
    if len(parts) >= 2 and not artist:
        artist, name = parts[0], parts[1]
    elif len(parts) >= 2:
        name = parts[0]   # [가수]제목 - 군말
    elif parts:
        name = parts[0]
    for which in ("title", "artist"):
        text = name if which == "title" else artist
        n = _LEAD_NUMBER.match(text)
        if n and "track" not in out:
            out["track"] = _track(n.group(1))
            text = text[n.end():]
        if which == "title":
            name = text
        else:
            artist = text
    title, artist = _tidy(name), _tidy(artist)
    if title:
        out["title"] = title
    if artist:
        out["artist"] = artist
    return out


def from_filename(path: str, pattern: str = AUTO, underscores: bool = True) -> dict[str, str]:
    stem = os.path.splitext(os.path.basename(path))[0]
    if underscores:
        stem = stem.replace("_", " ")
    return guess_auto(stem) if pattern == AUTO else match_pattern(stem, pattern)


def from_lines(text: str, pattern: str = AUTO) -> list[dict[str, str]]:
    """붙여 넣은 글을 줄마다 나눠 값을 뽑는다. 빈 줄은 건너뛴다. 맞지 않는 줄은 {}."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if pattern == AUTO:
            values: dict[str, str] = {}
            n = _LEAD_NUMBER.match(line)
            if n:
                values["track"] = _track(n.group(1))
                line = line[n.end():]
            if _tidy(line):
                values["title"] = _tidy(line)
            out.append(values)
        else:
            out.append(match_pattern(line, pattern))
    return out


def track_numbers(count: int, start: int = 1, with_total: bool = False) -> list[str]:
    last = start + count - 1
    return [f"{n}/{last}" if with_total else str(n) for n in range(start, start + count)]


def merge(base: dict[str, str], change: dict[str, str], only_empty: bool = False) -> dict[str, str]:
    out = dict(base)
    for k, v in change.items():
        if k in FIELDS and (not only_empty or not out.get(k)):
            out[k] = v
    return out
