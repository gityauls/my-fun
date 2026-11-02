"""여러 곡 태그(5-D) 이름 정리: 파일 이름에서 가수·제목을 찾아 '가수 - 제목'으로 통일한다. Qt 없음.

가수 표기 규칙(사용자 지정 2026-11-02): 같은 가수면 '한글(영어)' > '한글' > '영어' 순으로 좋은 표기로 맞추고,
한 칸에 같은 가수가 겹치면('이승철,이승철') 하나로 합친다."""
from __future__ import annotations

import re

FIELDS = ("artist", "title", "album", "year", "genre", "track")

SURE, BY_TAG, BY_KNOWN, UNSURE, NO_ARTIST, MISMATCH = "sure", "tag", "known", "unsure", "no_artist", "mismatch"
NOTES = {SURE: "", BY_TAG: "기존 태그의 가수와 같음 → 앞뒤 바꿈", BY_KNOWN: "다른 곡에서 가수로 쓰임 → 앞뒤 바꿈",
         UNSURE: "제목-가수로 봤습니다 · 확인", NO_ARTIST: "가수를 모름 · 직접 입력",
         MISMATCH: "태그의 가수는 '{tag}' · 확인"}
MERGED_NOTE = "가수 이름 겹침 → 하나로"
UNIFIED_NOTE = "같은 가수 → {name}로 통일"

_LEAD_BRACKET = re.compile(r"^\s*\[([^\]]*)\]\s*")
_LEAD_PAREN = re.compile(r"^\s*\([^)]*\)\s*")
_PAREN = re.compile(r"\s*\([^)]*\)\s*")
_TRAIL_PAREN = re.compile(r"^(.*?\S)\s*\(([^()]*)\)\s*$")
_SPACES = re.compile(r"\s+")
_SPACED_HYPHEN = re.compile(r"\s+-\s+")
_BARE_HYPHEN = re.compile(r"(?<=\S)-(?=\S)")
_LEAD_NUMBER = re.compile(r"^\s*\d{1,3}\s*[.\-_)]\s*(?=\S)|^\s*\d{1,3}\s+(?=\S)")
_ARTIST_SEP = re.compile(r"\s*[,;/&·]\s*")
_HANGUL = re.compile(r"[가-힣ㄱ-ㅎ]")


def _tidy(text: str) -> str:
    return _SPACES.sub(" ", text).strip().strip("_-").strip()


def _is_korean(text: str) -> bool:
    return bool(_HANGUL.search(text))


def split_alias(name: str) -> tuple[str, str]:
    """'이승철(Lee Seung Chul)' → ('이승철', 'Lee Seung Chul'). 괄호 안팎이 같은 글자(한글/영어)면 별칭이 아니다."""
    m = _TRAIL_PAREN.match(name or "")
    if m:
        main, alias = _tidy(m.group(1)), _tidy(m.group(2))
        if main and alias and _is_korean(main) != _is_korean(alias):
            return (main, alias) if _is_korean(main) else (alias, main)
    return _tidy(name or ""), ""


def canon(name: str) -> str:
    """'Lee(이승철)'도 '이승철(Lee)'로. 별칭이 없으면 그대로."""
    ko, en = split_alias(name)
    return f"{ko}({en})" if en else ko


def _norm(text: str) -> str:
    return text.casefold().replace(" ", "")


def _keys(name: str) -> set[str]:
    ko, en = split_alias(name)
    return {_norm(x) for x in (ko, en) if x}


def _rank(name: str) -> int:
    """좋은 표기 순: 한글(영어)=2, 한글=1, 영어=0."""
    ko, en = split_alias(name)
    return 2 if en else 1 if _is_korean(ko) else 0


def _same(a: str, b: str) -> bool:
    return bool(a and b) and bool(_keys(a) & _keys(b))


def clean_title(raw: str) -> str:
    text = _PAREN.sub(" ", raw.replace("_", " "))
    return _tidy(_LEAD_NUMBER.sub("", text))


def clean_artist(raw: str) -> str:
    """가수 조각: 앞 번호·밑줄·군말 괄호는 빼되, 끝의 다른 글자 괄호(한글(영어))는 별칭이라 남긴다."""
    text = _LEAD_NUMBER.sub("", _LEAD_PAREN.sub("", raw.replace("_", " ")))
    ko, en = split_alias(text)
    if en:
        return f"{clean_title(ko)}({_tidy(en)})"
    return clean_title(text)


def merge_artist(text: str) -> str:
    """한 칸에 같은 가수가 겹치면 하나로('이승철,이승철' → '이승철'), 좋은 표기를 남긴다. 다른 가수들은 그대로."""
    names = [n.strip() for n in _ARTIST_SEP.split(text or "") if n.strip()]
    kept: list[str] = []
    for n in names:
        for i, k in enumerate(kept):
            if _same(n, k):
                if _rank(n) > _rank(k):
                    kept[i] = n
                break
        else:
            kept.append(n)
    if len(kept) == len(names):
        return text
    return ", ".join(canon(n) for n in kept)


class Tidy:
    def __init__(self, artist: str, title: str, how: str) -> None:
        self.artist, self.title, self.how = artist, title, how
        self.merged = False
        self.unified = ""   # 다른 표기에서 바꿔 맞췄으면 그 표기
        self.tag = ""       # MISMATCH일 때 기존 태그의 가수

    @property
    def note(self) -> str:
        notes = [NOTES[self.how].format(tag=self.tag), MERGED_NOTE if self.merged else "",
                 UNIFIED_NOTE.format(name=self.unified) if self.unified else ""]
        return " · ".join(n for n in notes if n)

    @property
    def unsure(self) -> bool:
        return self.how in (UNSURE, NO_ARTIST, MISMATCH)

    def __repr__(self) -> str:
        return f"Tidy({self.artist!r}, {self.title!r}, {self.how!r})"


def _split(stem: str) -> tuple[str, str, str]:
    """(왼쪽, 오른쪽, 모양): 다듬기 전 조각. 모양: bracket=[가수]제목, spaced=가수 - 제목, bare=제목-가수, single."""
    m = _LEAD_BRACKET.match(stem)
    if m and _tidy(m.group(1)) and clean_title(stem[m.end():]):
        return m.group(1), _SPACED_HYPHEN.split(stem[m.end():])[0], "bracket"
    body = _LEAD_PAREN.sub("", stem)
    parts = [p for p in _SPACED_HYPHEN.split(body) if clean_title(p)]
    if len(parts) >= 2:
        return parts[0], parts[1], "spaced"
    bare = _BARE_HYPHEN.split(body)
    if len(bare) == 2 and all(len(clean_title(p)) >= 2 for p in bare):
        return bare[0], bare[1], "bare"
    return "", body, "single"


def tidy_names(stems: list[str], tag_artists: list[str], tag_titles: list[str] | None = None) -> list[Tidy]:
    """파일 이름(확장자 뺀 것)들에서 가수·제목을 찾는다. 사용자 규칙: '가수 - 제목', '[가수] 제목', '제목-가수'.
    어느 쪽이 가수인지는 기존 가수 태그 → 다른 곡에서 가수로 쓰인 이름 순으로 확인하고, 모르면 unsure.
    기존 태그가 빈칸·대소문자·괄호만 다르면 태그 쪽 표기를 쓰고, 가수가 아예 다르면 확인을 받는다."""
    tags = [merge_artist(a) for a in tag_artists]
    out = _decide(stems, tags)
    for t, tag, tag_title in zip(out, tags, tag_titles or [""] * len(out)):
        if tag and t.artist and _same(tag, t.artist) and not _ARTIST_SEP.search(tag):
            t.artist = canon(tag) if _rank(tag) >= _rank(t.artist) else t.artist
        elif tag and t.artist and t.how in (SURE, UNSURE):
            t.how, t.tag = MISMATCH, tag
        if tag_title and t.title and _norm(clean_title(tag_title)) == _norm(t.title):
            t.title = _tidy(tag_title)
    for t, raw_tag, tag in zip(out, tag_artists, tags):
        merged = merge_artist(t.artist)
        if merged != t.artist or (tag != raw_tag and _same(merged, tag)):
            t.artist, t.merged = merged, True
    _unify(out, tags)
    return out


def _decide(stems: list[str], tags: list[str]) -> list[Tidy]:
    splits = [_split(s) for s in stems]
    sure_left = [clean_artist(left) if kind in ("bracket", "spaced") else "" for left, _, kind in splits]
    out = []
    for i, ((left, right, kind), tag) in enumerate(zip(splits, tags)):
        if kind == "single":
            out.append(Tidy(tag, clean_title(right), SURE if tag else NO_ARTIST))
            continue
        # 이 곡 자신의 조각은 빼고, 다른 곡의 가수 태그와 '가수 - 제목'·'[가수]'의 가수만 아는 가수로 친다
        known = [a for j, a in enumerate(tags) if a and j != i]
        known += [a for j, a in enumerate(sure_left) if a and j != i]
        a_raw, t_raw = (right, left) if kind == "bare" else (left, right)
        artist, title = clean_artist(a_raw), clean_title(t_raw)
        swapped = Tidy(clean_artist(t_raw), clean_title(a_raw), SURE)
        if _same(tag, artist) or kind == "bracket" and not _same(tag, swapped.artist):
            out.append(Tidy(artist, title, SURE))
        elif _same(tag, swapped.artist):
            swapped.how = BY_TAG
            out.append(swapped)
        elif any(_same(k, swapped.artist) for k in known) and not any(_same(k, artist) for k in known):
            swapped.how = BY_KNOWN
            out.append(swapped)
        elif kind == "bare" and not any(_same(k, artist) for k in known):
            out.append(Tidy(artist, title, UNSURE))
        else:
            out.append(Tidy(artist, title, SURE))
    return out


def _unify(out: list[Tidy], tags: list[str]) -> None:
    """같은 가수의 여러 표기를 가장 좋은 표기로 맞춘다 (여러 가수가 든 칸은 건드리지 않는다)."""
    best: dict[str, str] = {}
    for name in [t.artist for t in out] + list(tags):
        if not name or _ARTIST_SEP.search(name):
            continue
        name = canon(name)
        for k in _keys(name):
            if k not in best or _rank(name) > _rank(best[k]):
                best[k] = name
    for t in out:
        if not t.artist or _ARTIST_SEP.search(t.artist):
            continue
        choices = [best[k] for k in _keys(t.artist) if k in best]
        top = max(choices, key=_rank, default=t.artist)
        if top != t.artist and _rank(top) >= _rank(t.artist):
            t.artist = t.unified = top
