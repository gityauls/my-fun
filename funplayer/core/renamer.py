from __future__ import annotations

import os
import re
import time
from datetime import datetime

MAX_NAME = 150   # 확장자 포함 이름 길이
MAX_PATH = 259   # 전체 경로 길이
MAX_LOG = 200    # 기록에 남기는 줄 수

_BAD = re.compile(r'[\/:*?"<>|\x00-\x1f]')
_SPACES = re.compile(r" {2,}")
_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", re.IGNORECASE)


def clean_part(s: str) -> str:
    s = _BAD.sub("_", s)
    s = _SPACES.sub(" ", s).strip()
    return s.rstrip(". ")


def is_reserved(stem: str) -> bool:
    return bool(_RESERVED.match(stem))


def build_name(artist: str, title: str, ext: str, dir_len: int = 0) -> str:
    a, t = clean_part(artist), clean_part(title)
    if not a or not t:
        return ""
    limit = min(MAX_NAME, MAX_PATH - dir_len - 1)
    keep = limit - len(ext) - len(a) - 3   # 제목에 남길 수 있는 글자 수
    for _ in range(2):
        t = t[:max(keep, 0)].rstrip(". ")
        if not t:
            return ""
        stem = f"{a} - {t}"
        if not is_reserved(stem):
            break
        stem += "_"                         # 예약 이름이면 뒤에 _ (한 글자 더 줄여 다시 맞춘다)
        keep -= 1
    return stem + ext


def target_path(path: str, artist: str, title: str) -> str | None:
    folder, base = os.path.split(path)
    ext = os.path.splitext(base)[1]
    name = build_name(artist, title, ext, len(folder))
    if not name:
        return None
    if name == base:
        return path
    return os.path.join(folder, name)


def same_file(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def conflict(old: str, new: str) -> bool:
    return os.path.exists(new) and not same_file(old, new)


class RenameError(Exception):
    pass


class RenameConflict(RenameError):
    pass


def rename_file(old: str, new: str) -> None:
    if conflict(old, new):
        raise RenameConflict(new)
    try:
        os.rename(old, new)   # 덮어쓰지 않는 os.rename만 쓴다
    except OSError as e:
        raise RenameError(str(e)) from e


class RenameLog:
    """바꾼 이름 기록: 한 줄에 `시각\t옛 경로\t새 경로`, 최근 MAX_LOG줄만 남긴다."""

    def __init__(self, path: str | None, clock=time.time) -> None:
        self._path = path
        self._clock = clock
        self._rows: list[tuple[str, str, str]] = self._load()

    def _load(self) -> list[tuple[str, str, str]]:
        if self._path is None:
            return []
        try:
            with open(self._path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, ValueError):
            return []
        rows = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) == 3 and parts[1] and parts[2]:
                rows.append((parts[0], parts[1], parts[2]))
        return rows[-MAX_LOG:]

    def _save(self) -> None:
        if self._path is None:
            return
        tmp = self._path + ".tmp"
        try:
            folder = os.path.dirname(self._path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write("".join("\t".join(r) + "\n" for r in self._rows))
            os.replace(tmp, self._path)
        except OSError:
            pass   # 기록을 못 써도 이름 바꾸기 자체는 막지 않는다

    def add(self, old: str, new: str) -> None:
        stamp = datetime.fromtimestamp(self._clock()).isoformat(timespec="seconds")
        self._rows.append((stamp, old, new))
        del self._rows[:-MAX_LOG]
        self._save()

    def last(self) -> tuple[str, str] | None:
        return (self._rows[-1][1], self._rows[-1][2]) if self._rows else None

    def pop(self) -> None:
        if self._rows:
            self._rows.pop()
            self._save()
