from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

REPEAT_MODES = ("off", "all", "one")

DEFAULTS = {"player_volume": 70, "player_muted": False, "player_seek_step": 5,
            "player_repeat": "off", "player_shuffle": False}


def _read_int(store: dict, key: str, lo: int, hi: int) -> int:
    value = store.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return DEFAULTS[key]
    try:
        return max(lo, min(hi, int(value)))
    except (ValueError, OverflowError):
        return DEFAULTS[key]


class Settings:
    """Typed view over a host-owned dict; reads the store on every access."""

    def __init__(self, store: dict, save: Callable[[], None]) -> None:
        self._store = store
        self._save = save

    def _set(self, key: str, value) -> None:
        self._store[key] = value
        self._save()

    @property
    def volume(self) -> int:
        return _read_int(self._store, "player_volume", 0, 100)

    @volume.setter
    def volume(self, value: int) -> None:
        self._set("player_volume", max(0, min(100, int(value))))

    @property
    def muted(self) -> bool:
        value = self._store.get("player_muted")
        return value if isinstance(value, bool) else DEFAULTS["player_muted"]

    @muted.setter
    def muted(self, value: bool) -> None:
        self._set("player_muted", bool(value))

    @property
    def seek_step(self) -> int:
        return _read_int(self._store, "player_seek_step", 1, 100)

    @seek_step.setter
    def seek_step(self, value: int) -> None:
        self._set("player_seek_step", max(1, min(100, int(value))))

    @property
    def repeat(self) -> str:
        value = self._store.get("player_repeat")
        return value if value in REPEAT_MODES else DEFAULTS["player_repeat"]

    @repeat.setter
    def repeat(self, value: str) -> None:
        self._set("player_repeat", value if value in REPEAT_MODES else DEFAULTS["player_repeat"])

    @property
    def shuffle(self) -> bool:
        value = self._store.get("player_shuffle")
        return value if isinstance(value, bool) else DEFAULTS["player_shuffle"]

    @shuffle.setter
    def shuffle(self, value: bool) -> None:
        self._set("player_shuffle", bool(value))


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.data: dict = self._load()

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError as e:
            logger.warning("settings save failed: %s", e)
