from __future__ import annotations

import math
from dataclasses import dataclass, replace

BANDS_HZ = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
BAND_LABELS = ("31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k")
BAND_MAX = 12
CUSTOM = "사용자 설정"
MODES = ("off", "speaker", "earphone")
MODE_NAMES = {"speaker": "스피커", "earphone": "이어폰"}
LEVELS = ("width", "depth", "bass")

# 31 Hz부터 dB. 순서가 프리셋 목록 순서다
PRESETS: dict[str, tuple[int, ...]] = {
    "기본": (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    "발라드": (3, 2, 1, 0, -1, 0, 1, 2, 3, 2),
    "팝": (-1, 1, 3, 4, 3, 0, -1, -1, 1, 2),
    "록": (5, 4, 2, -1, -2, -1, 2, 4, 5, 5),
    "재즈": (3, 2, 1, 2, -1, -1, 0, 1, 2, 3),
    "클래식": (4, 3, 2, 1, -1, -1, 0, 2, 3, 4),
    "댄스": (6, 5, 2, 0, 0, -1, -2, -1, 3, 4),
    "보컬": (-2, -1, 0, 2, 4, 4, 3, 1, 0, -1),
    "베이스 강하게": (7, 6, 5, 3, 1, 0, 0, 0, 0, 0),
    "고음 강하게": (0, 0, 0, 0, 0, 1, 3, 5, 6, 7),
}

_ZEROS = (0,) * len(BANDS_HZ)
_DEFAULT_LEVELS = {"width": 40, "depth": 40, "bass": 30}


def _clamp(value: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(round(value))))


def _is_number(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _read_bands(value) -> tuple[int, ...]:
    # 숫자 10개짜리 목록만 쓰고, 아니면 전부 0
    if not isinstance(value, (list, tuple)) or len(value) != len(BANDS_HZ):
        return _ZEROS
    if not all(_is_number(v) and math.isfinite(v) for v in value):
        return _ZEROS
    return tuple(_clamp(v, -BAND_MAX, BAND_MAX) for v in value)


def _read_level(d: dict, key: str) -> int:
    value = d.get(key)
    if not _is_number(value) or math.isnan(value):
        return _DEFAULT_LEVELS[key]
    if math.isinf(value):
        return 100 if value > 0 else 0
    return _clamp(value, 0, 100)


@dataclass(frozen=True)
class FxSettings:
    enabled: bool = False
    preset: str = "기본"
    bands: tuple[int, ...] = _ZEROS
    mode: str = "off"
    width: int = 40
    depth: int = 40
    bass: int = 30
    custom: tuple[int, ...] = _ZEROS

    def with_enabled(self, on: bool) -> FxSettings:
        return replace(self, enabled=bool(on))

    def with_preset(self, name: str) -> FxSettings:
        if name == CUSTOM:
            return replace(self, preset=CUSTOM, bands=self.custom)
        if name in PRESETS:
            return replace(self, preset=name, bands=PRESETS[name])
        return self

    def with_band(self, i: int, db: int) -> FxSettings:
        if not 0 <= i < len(self.bands):
            return self
        bands = list(self.bands)
        bands[i] = _clamp(db, -BAND_MAX, BAND_MAX)
        bands = tuple(bands)
        return replace(self, preset=CUSTOM, bands=bands, custom=bands)

    def with_mode(self, mode: str) -> FxSettings:
        return replace(self, mode=mode if mode in MODES else "off")

    def with_level(self, name: str, value: int) -> FxSettings:
        if name not in LEVELS:
            return self
        return replace(self, **{name: _clamp(value, 0, 100)})

    def reset(self) -> FxSettings:
        return replace(self, preset="기본", bands=_ZEROS, mode="off", **_DEFAULT_LEVELS)

    def summary(self) -> str:
        if not self.enabled:
            return "꺼짐"
        text = f"켜짐 · {self.preset}"
        if self.mode in MODE_NAMES:
            text += f" · {MODE_NAMES[self.mode]}"
        return text

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "preset": self.preset, "bands": list(self.bands),
                "mode": self.mode, "width": self.width, "depth": self.depth, "bass": self.bass,
                "custom": list(self.custom)}

    @classmethod
    def from_dict(cls, d: object) -> FxSettings:
        if not isinstance(d, dict):
            return cls()
        enabled = d.get("enabled")
        preset = d.get("preset")
        mode = d.get("mode")
        return cls(enabled=enabled if isinstance(enabled, bool) else False,
                   preset=preset if preset in PRESETS or preset == CUSTOM else "기본",
                   bands=_read_bands(d.get("bands")),
                   mode=mode if mode in MODES else "off",
                   width=_read_level(d, "width"), depth=_read_level(d, "depth"),
                   bass=_read_level(d, "bass"), custom=_read_bands(d.get("custom")))
