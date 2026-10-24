from __future__ import annotations

import math


def format_time(sec: float) -> str:
    if sec is None or math.isnan(sec) or math.isinf(sec) or sec < 0:
        return "0:00"
    total = int(sec)
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f"{h}:{m:02}:{s:02}"
    return f"{m}:{s:02}"
