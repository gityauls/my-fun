"""방송 그림. 사용자가 넣은 그림이 먼저고, 없으면 기본 로고, 그것도 없으면 None(테마 기본 그림)이다."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap

log = logging.getLogger(__name__)

LOGO_DIR = Path(__file__).resolve().parent.parent / "assets" / "stations"
CARD_SIZE = 512
LOGO_FILL = .76      # 네모가 아닌 그림은 흰 카드의 이만큼만 차지한다
SQUARE_RATIO = 1.15  # 이보다 네모에 가까우면 카드 가득 채운다


def square_card(img: QImage) -> QImage:
    """어떤 그림이든 잘리지 않게 흰 정사각 카드로 만든다."""
    ratio = max(img.width(), img.height()) / max(1, min(img.width(), img.height()))
    side = CARD_SIZE if ratio <= SQUARE_RATIO else round(CARD_SIZE * LOGO_FILL)
    scaled = img.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    card = QImage(CARD_SIZE, CARD_SIZE, QImage.Format_ARGB32_Premultiplied)
    card.fill(QColor("#FFFFFF"))
    p = QPainter(card)
    p.drawImage((CARD_SIZE - scaled.width()) // 2, (CARD_SIZE - scaled.height()) // 2, scaled)
    p.end()
    return card


class StationArt:
    def __init__(self, user_dir: str | Path | None = None, logo_dir: Path = LOGO_DIR) -> None:
        self._user_dir = Path(user_dir) if user_dir else None
        self._logo_dir = logo_dir
        self._memory: dict[str, QImage] = {}   # 저장 폴더가 없을 때(테스트)
        self.version = 0   # 바뀔 때마다 오른다. 패널이 다시 그릴 때를 안다

    def _user_path(self, station_id: str) -> Path:
        # 직접 넣은 방송의 id에는 파일 이름에 못 쓰는 글자가 있을 수 있다
        return self._user_dir / (hashlib.sha1(station_id.encode("utf-8")).hexdigest() + ".png")

    def has_user(self, station_id: str) -> bool:
        if self._user_dir is None:
            return station_id in self._memory
        return self._user_path(station_id).exists()

    def has_logo(self, station_id: str) -> bool:
        return (self._logo_dir / f"{station_id}.png").exists()

    def pixmap(self, station_id: str | None) -> QPixmap | None:
        if not station_id:
            return None
        if self._user_dir is None and station_id in self._memory:
            return QPixmap.fromImage(self._memory[station_id])
        if self._user_dir is not None and self.has_user(station_id):
            pm = QPixmap(str(self._user_path(station_id)))
            if not pm.isNull():
                return pm
            log.warning("방송 그림을 읽지 못했습니다: %s", station_id)
        pm = QPixmap(str(self._logo_dir / f"{station_id}.png"))
        return None if pm.isNull() else pm

    def save(self, station_id: str, img: QImage) -> bool:
        card = square_card(img)
        self.version += 1
        if self._user_dir is None:
            self._memory[station_id] = card
            return True
        try:
            self._user_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.exception("방송 그림 폴더를 만들지 못했습니다")
            return False
        return card.save(str(self._user_path(station_id)), "PNG")

    def clear(self, station_id: str) -> None:
        self.version += 1
        self._memory.pop(station_id, None)
        if self._user_dir is not None:
            try:
                self._user_path(station_id).unlink(missing_ok=True)
            except OSError:
                log.exception("방송 그림을 지우지 못했습니다")
