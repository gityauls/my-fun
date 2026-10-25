from __future__ import annotations

import os
import re
from pathlib import PurePath
from typing import Iterable

SUPPORTED_EXTS = frozenset({".mp3", ".wav", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".wma"})

_DIGITS = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple:
    parts = _DIGITS.split(name.lower())
    return tuple(int(p) if i % 2 else p for i, p in enumerate(parts))


def is_supported(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTS


def path_sort_key(path: str) -> tuple:
    parent, name = os.path.split(path)
    return (tuple(natural_key(part) for part in PurePath(parent).parts), natural_key(name))


def name_sort_key(path: str) -> tuple:
    return (natural_key(os.path.basename(path)), path_sort_key(path))


def expand_paths(paths: Iterable[str]) -> list[str]:
    found: list[str] = []
    for raw in paths:
        path = os.path.abspath(raw)
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                found.extend(os.path.join(root, f) for f in files if is_supported(f))
        elif os.path.isfile(path) and is_supported(path):
            found.append(path)
    return sorted(found, key=path_sort_key)
