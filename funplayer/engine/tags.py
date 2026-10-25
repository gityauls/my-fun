from __future__ import annotations

import logging
import os

import av

from funplayer.core.taginfo import TrackInfo, fix_text
from funplayer.engine.decoder import _duration

logger = logging.getLogger(__name__)

_KEYS = ("title", "artist", "album", "date", "genre", "track")


def read_info(path: str) -> TrackInfo:
    """곡 정보를 읽는다. 예외를 밖으로 내지 않고, 실패하면 경로와 크기만 채워 돌려준다."""
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    info = TrackInfo(path, size=size)
    container = None
    try:
        container = av.open(path)
        stream = next(iter(container.streams.audio), None)
        if stream is None:
            return info
        # FLAC·Ogg·Opus·APEv2는 키가 TITLE·Year처럼 대문자로 온다: 소문자로 맞추고, 같은 키는 컨테이너 것을 쓴다
        tags: dict[str, object] = {}
        for meta in (container.metadata, stream.metadata):
            for key, value in meta.items():
                tags.setdefault(key.lower(), value)
        if not tags.get("date"):
            tags["date"] = tags.get("year", "")
        text = {k: fix_text(str(tags.get(k, ""))) for k in _KEYS}
        date = text["date"]
        info.title, info.artist, info.album = text["title"], text["artist"], text["album"]
        info.genre, info.track = text["genre"], text["track"]
        info.year = date[:4] if date[:4].isdigit() else date
        ctx = stream.codec_context
        info.codec, info.sample_rate, info.channels = ctx.name, ctx.sample_rate, ctx.channels
        # 컨테이너 비트레이트는 파일 크기로 셈해 큰 표지 그림까지 들어가므로 스트림 값을 먼저 본다
        info.bitrate = stream.bit_rate or ctx.bit_rate or container.bit_rate or 0
        info.duration = _duration(container, stream)
        art = next((s for s in container.streams.video
                    if s.disposition & av.stream.Disposition.attached_pic), None)
        if art is not None:
            packet = next(container.demux(art), None)
            info.picture = bytes(packet) if packet is not None else None
    except Exception:
        logger.debug("read_info failed: %s", path, exc_info=True)
    finally:
        if container is not None:
            container.close()
    return info
