from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtGui import QFontDatabase

logger = logging.getLogger("funplayer")

FONT_DIR: Path = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FALLBACK_FAMILY = "Malgun Gothic"
_FILES = ("NotoSansKR-Regular.otf", "NotoSansKR-Bold.otf")


def load_fonts() -> str:
    """번들 글꼴(Noto Sans KR)을 등록하고 패밀리 이름을 돌려준다. 실패하면 맑은 고딕."""
    family = ""
    for name in _FILES:
        path = FONT_DIR / name
        if not path.is_file():
            logger.warning("font file missing: %s", path)
            continue
        fid = QFontDatabase.addApplicationFont(str(path))
        if fid < 0:
            logger.warning("font load failed: %s", path)
            continue
        families = QFontDatabase.applicationFontFamilies(fid)
        if families and not family:
            family = families[0]
    return family or FALLBACK_FAMILY
