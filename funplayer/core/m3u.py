from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request

from funplayer.core.tracks import is_supported

PLAYLIST_EXTS = frozenset({".m3u", ".m3u8"})

_URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+://")


def is_playlist(path: str) -> bool:
    """True if the extension is .m3u or .m3u8 (case-insensitive)."""
    return os.path.splitext(path)[1].lower() in PLAYLIST_EXTS


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp949", errors="replace")


def read_playlist(path: str) -> list[str]:
    """Return supported track paths in file order; raises OSError if unreadable."""
    with open(path, "rb") as f:
        text = _decode(f.read())
    base = os.path.dirname(os.path.abspath(path))
    tracks: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if _URL_RE.match(line):
            if not line.lower().startswith("file:"):
                continue
            line = urllib.request.url2pathname(urllib.parse.urlparse(line).path)
        full = os.path.abspath(os.path.join(base, line))
        if is_supported(full):
            tracks.append(full)
    return tracks


def _entry(track: str, base: str) -> str:
    try:
        nbase, ntrack = os.path.normcase(base), os.path.normcase(track)
        if os.path.commonpath([nbase, ntrack]) == nbase:
            return os.path.relpath(track, base)
    except ValueError:
        pass
    return track


def write_playlist(path: str, tracks: list[str]) -> None:
    """Write an m3u8 file atomically; raises OSError (or ValueError for an unencodable path) on failure."""
    base = os.path.dirname(os.path.abspath(path))
    entries = [_entry(t, base) for t in tracks]
    data = ("\r\n".join(["#EXTM3U", *entries]) + "\r\n").encode("utf-8")
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
