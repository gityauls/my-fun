from __future__ import annotations

import os
from dataclasses import dataclass

# 트랙 정보 (Qt/PyAV 의존 없음)
@dataclass
class TrackInfo:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    genre: str = ""
    track: str = ""
    codec: str = ""
    duration: float = 0.0
    bitrate: int = 0
    sample_rate: int = 0
    channels: int = 0
    size: int = 0
    picture: bytes | None = None


# 옛 한국어 MP3 태그(CP949) 복구. 서양 이름은 그대로 둔다.
def fix_text(s: str) -> str:
    if any(0xDC80 <= ord(c) <= 0xDCFF for c in s):        # 1. 깨진 바이트가 섞였다
        return s.encode("utf-8", "surrogateescape").decode("cp949", "replace")
    if any(ord(c) >= 0x80 for c in s) and all(ord(c) <= 0xFF for c in s):   # 2. Latin-1로 읽혔다
        try:
            fixed = s.encode("latin-1").decode("cp949")
        except UnicodeDecodeError:
            return s
        if any(_ksx1001_hangul(c) for c in fixed):
            return fixed
    return s


# KS X 1001(완성형) 한글인가: 두 바이트가 모두 0xA1 이상. "Ärzte"의 "Är" 같은 확장 UHC 짝은 아니다
def _ksx1001_hangul(c: str) -> bool:
    return "가" <= c <= "힣" and all(b >= 0xA1 for b in c.encode("cp949"))


_COVER_STEMS = ("cover", "folder", "front", "album")
_PIC_EXTS = (".jpg", ".jpeg", ".png")


# 앨범 그림 파일 고르기
def pick_cover(names: list[str], album: str) -> str | None:
    pics = [n for n in names if os.path.splitext(n)[1].lower() in _PIC_EXTS]
    stems = {n: os.path.splitext(n)[0].lower() for n in pics}
    cands = list(_COVER_STEMS) + ([album.lower()] if album else [])
    for c in cands:
        for n in pics:
            if stems[n] == c:
                return n
    return pics[0] if len(pics) == 1 else None


_CODEC_NAMES = {"mp3": "MP3", "mp3float": "MP3", "aac": "AAC", "flac": "FLAC", "vorbis": "Vorbis",
                "opus": "Opus", "wmav1": "WMA", "wmav2": "WMA", "alac": "ALAC"}


# 코덱 이름을 보기 좋은 이름으로
def codec_label(name: str) -> str:
    if name in _CODEC_NAMES:
        return _CODEC_NAMES[name]
    if name.startswith("pcm_"):
        return "PCM"
    return name.upper()


# 기술 정보 한 줄 (예: "MP3 · 192 kbps · 44.1 kHz · 스테레오")
def format_line(info: TrackInfo) -> str:
    parts = [codec_label(info.codec)]
    if info.bitrate:
        parts.append(f"{round(info.bitrate / 1000)} kbps")
    if info.sample_rate:
        parts.append(f"{info.sample_rate / 1000:g} kHz")
    if info.channels:
        parts.append({1: "모노", 2: "스테레오"}.get(info.channels, f"{info.channels}채널"))
    return " · ".join(p for p in parts if p)


# 파일 크기 표시 (예: "5.2 MB", "2 KB")
def format_size(n: int) -> str:
    if n <= 0:
        return ""
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{max(1, round(n / 1024))} KB"


# 아티스트 · 앨범 부제목
def subtitle(info: TrackInfo | None) -> str:
    if info is None:
        return ""
    return " · ".join(p for p in (info.artist, info.album) if p)
