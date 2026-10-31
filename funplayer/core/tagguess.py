from __future__ import annotations

import os
import re

_LEAD_BRACKET = re.compile(r"^\s*\[([^\]]*)\]")
_LEAD_PAREN = re.compile(r"^\s*\([^)]*\)")
_TRAIL_PAREN = re.compile(r"\s*\([^)]*\)\s*$")


def _clean(text: str) -> str:
    return text.strip().strip("_").strip()


_LEAD_NUMBER = re.compile(r"^\s*\d{1,3}\s*[.\-_)]\s*")
_AUDIO_EXT = re.compile(r"\.(mp3|wma|ogg|flac|m4a|wav)\s*$", re.I)


def clean_search_title(title: str) -> str:
    """찾기 칸에 넣을 제목: 태그에 묻어 온 '02. ' 같은 앞 번호와 '.mp3' 같은 확장자를 뗀다."""
    title = _AUDIO_EXT.sub("", title or "")
    return _clean(_LEAD_NUMBER.sub("", title)) or _clean(title)


def guess_from_filename(path: str) -> tuple[str, str]:
    """파일 이름에서 (가수, 제목)을 짐작한다."""
    name = os.path.splitext(os.path.basename(path or ""))[0]
    candidate = ""
    m = _LEAD_BRACKET.match(name)
    if m:
        candidate = m.group(1)
        name = name[m.end():]
    name = _LEAD_PAREN.sub("", name)
    parts = [p for p in name.split(" - ")]
    if len(parts) >= 2:
        artist = _clean(parts[0])
        title = _clean(_TRAIL_PAREN.sub("", parts[1]))
        if artist and title:
            return artist, title
    return _clean(candidate), _clean(name)
