from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Callable

from funplayer.core.themes import THEME_IDS

logger = logging.getLogger(__name__)

REPEAT_MODES = ("off", "all", "one")

DEFAULTS = {"player_volume": 70, "player_muted": False, "player_seek_step": 5,
            "player_repeat": "off", "player_shuffle": False,
            "player_last_track": "", "player_last_position": 0.0, "player_mini": False,
            "player_mini_on_top": True, "player_media_keys": True,
            "player_geometry": None, "player_mini_geometry": None,
            "player_last_source": "file", "player_last_station": "", "player_tab": "now",
            "player_theme": "light",
            "player_radio_open": ["favorites", "kr:big3", "user"],
            "player_fx": {}, "player_fx_visible": False, "player_fx_open": True,
            "player_rename_on_save": False, "player_favorites": []}

LAST_SOURCES = ("file", "radio")
TABS = ("now", "playlist", "radio", "fx")


def _read_int(store: dict, key: str, lo: int, hi: int) -> int:
    value = store.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return DEFAULTS[key]
    try:
        return max(lo, min(hi, int(value)))
    except (ValueError, OverflowError):
        return DEFAULTS[key]


def _read_geometry(value) -> list[int] | None:
    # [x, y, w, h] of ints with a positive size; anything else is treated as unset
    if not isinstance(value, list) or len(value) != 4:
        return None
    if any(isinstance(v, bool) or not isinstance(v, int) for v in value):
        return None
    return list(value) if value[2] > 0 and value[3] > 0 else None


class Settings:
    """Typed view over a host-owned dict; reads the store on every access."""

    def __init__(self, store: dict, save: Callable[[], None]) -> None:
        self._store = store
        self._save = save
        self.favorites_version = 0   # 즐겨찾기가 바뀔 때마다 는다 (화면이 매번 목록을 다시 보지 않게)

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

    @property
    def last_track(self) -> str:
        value = self._store.get("player_last_track")
        return value if isinstance(value, str) else DEFAULTS["player_last_track"]

    @last_track.setter
    def last_track(self, value: str) -> None:
        self._set("player_last_track", str(value))

    @property
    def last_position(self) -> float:
        value = self._store.get("player_last_position")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return DEFAULTS["player_last_position"]
        try:
            position = float(value)
        except OverflowError:
            return DEFAULTS["player_last_position"]
        return position if math.isfinite(position) and position >= 0 else DEFAULTS["player_last_position"]

    @last_position.setter
    def last_position(self, value: float) -> None:
        self._set("player_last_position", float(value))

    @property
    def mini(self) -> bool:
        value = self._store.get("player_mini")
        return value if isinstance(value, bool) else DEFAULTS["player_mini"]

    @mini.setter
    def mini(self, value: bool) -> None:
        self._set("player_mini", bool(value))

    @property
    def mini_on_top(self) -> bool:
        value = self._store.get("player_mini_on_top")
        return value if isinstance(value, bool) else DEFAULTS["player_mini_on_top"]

    @mini_on_top.setter
    def mini_on_top(self, value: bool) -> None:
        self._set("player_mini_on_top", bool(value))

    @property
    def media_keys(self) -> bool:
        value = self._store.get("player_media_keys")
        return value if isinstance(value, bool) else DEFAULTS["player_media_keys"]

    @media_keys.setter
    def media_keys(self, value: bool) -> None:
        self._set("player_media_keys", bool(value))

    @property
    def geometry(self) -> list[int] | None:
        return _read_geometry(self._store.get("player_geometry"))

    @geometry.setter
    def geometry(self, value) -> None:
        self._set("player_geometry", None if value is None else [int(v) for v in value])

    @property
    def mini_geometry(self) -> list[int] | None:
        return _read_geometry(self._store.get("player_mini_geometry"))

    @mini_geometry.setter
    def mini_geometry(self, value) -> None:
        self._set("player_mini_geometry", None if value is None else [int(v) for v in value])

    @property
    def last_source(self) -> str:
        value = self._store.get("player_last_source")
        return value if value in LAST_SOURCES else DEFAULTS["player_last_source"]

    @last_source.setter
    def last_source(self, value: str) -> None:
        self._set("player_last_source", value if value in LAST_SOURCES else DEFAULTS["player_last_source"])

    @property
    def last_station(self) -> str:
        value = self._store.get("player_last_station")
        return value if isinstance(value, str) else DEFAULTS["player_last_station"]

    @last_station.setter
    def last_station(self, value: str) -> None:
        self._set("player_last_station", str(value))

    @property
    def tab(self) -> str:
        value = self._store.get("player_tab")
        return value if value in TABS else DEFAULTS["player_tab"]

    @tab.setter
    def tab(self, value: str) -> None:
        self._set("player_tab", value if value in TABS else DEFAULTS["player_tab"])

    @property
    def theme(self) -> str:
        value = self._store.get("player_theme")
        return value if isinstance(value, str) and value in THEME_IDS else DEFAULTS["player_theme"]

    @theme.setter
    def theme(self, value: str) -> None:
        self._set("player_theme", value if isinstance(value, str) and value in THEME_IDS
                  else DEFAULTS["player_theme"])

    @property
    def radio_open(self) -> list[str]:
        value = self._store.get("player_radio_open")
        if not isinstance(value, list):
            return list(DEFAULTS["player_radio_open"])
        out: list[str] = []
        for v in value:
            if v == "domestic":
                v = "kr:big3"   # 옛 "국내 방송" 묶음은 첫 국내 묶음으로 옮긴다
            if isinstance(v, str) and v not in out:
                out.append(v)
        return out

    @radio_open.setter
    def radio_open(self, value: list[str]) -> None:
        if isinstance(value, str):
            value = [value]   # 글자 하나하나로 쪼개지 않게
        self._set("player_radio_open", [v for v in value if isinstance(v, str)])

    @property
    def fx(self) -> dict:
        value = self._store.get("player_fx")
        return value if isinstance(value, dict) else {}

    @fx.setter
    def fx(self, value: dict) -> None:
        self._set("player_fx", dict(value))

    @property
    def fx_visible(self) -> bool:
        value = self._store.get("player_fx_visible")
        return value if isinstance(value, bool) else DEFAULTS["player_fx_visible"]

    @fx_visible.setter
    def fx_visible(self, value: bool) -> None:
        self._set("player_fx_visible", bool(value))

    @property
    def fx_open(self) -> bool:
        value = self._store.get("player_fx_open")
        return value if isinstance(value, bool) else DEFAULTS["player_fx_open"]

    @fx_open.setter
    def fx_open(self, value: bool) -> None:
        self._set("player_fx_open", bool(value))

    @property
    def rename_on_save(self) -> bool:
        value = self._store.get("player_rename_on_save")
        return value if isinstance(value, bool) else DEFAULTS["player_rename_on_save"]

    @rename_on_save.setter
    def rename_on_save(self, value: bool) -> None:
        self._set("player_rename_on_save", bool(value))

    @property
    def favorites(self) -> list[str]:
        """즐겨찾기한 파일 경로, 즐겨찾기한 순서대로."""
        value = self._store.get("player_favorites")
        if not isinstance(value, list):
            return []
        return [v for v in value if isinstance(v, str) and v]

    @favorites.setter
    def favorites(self, value: list[str]) -> None:
        self._set("player_favorites", [v for v in value if isinstance(v, str) and v])
        self.favorites_version += 1


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
