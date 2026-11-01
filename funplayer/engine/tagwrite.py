from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable

from mutagen.id3 import APIC, ID3, delete, ID3NoHeaderError, TALB, TCON, TDRC, TIT2, TPE1, TRCK, TYER

from funplayer.engine.tags import read_info

logger = logging.getLogger(__name__)

FIELDS = ("title", "artist", "album", "year", "genre", "track")
MAX_PICTURE = 10 * 1024 * 1024

_FRAMES = {"title": ("TIT2", TIT2), "artist": ("TPE1", TPE1), "album": ("TALB", TALB),
           "year": ("TYER", TYER), "genre": ("TCON", TCON), "track": ("TRCK", TRCK)}

MSG_NOT_MP3 = "MP3만 고칠 수 있습니다"
MSG_DENIED = "파일에 쓸 수 없습니다 (읽기 전용이거나 다른 프로그램이 쓰는 중)"
MSG_VERIFY = "저장한 파일을 다시 읽지 못해 원래대로 두었습니다"
MSG_OTHER = "저장하지 못했습니다"


class _Sentinel:
    def __init__(self, name: str) -> None:
        self._name = name

    def __repr__(self) -> str:
        return self._name


KEEP = _Sentinel("KEEP")
REMOVE = _Sentinel("REMOVE")


class TagWriteError(Exception):
    """메시지 = 사용자에게 보일 한국어 이유."""


def picture_mime(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return None


def _default_verify(title: str | None) -> Callable[[str], bool]:
    def check(path: str) -> bool:
        info = read_info(path)
        if not info.duration > 0:
            return False
        return title is None or info.title == title
    return check


def _safe_write(path: str, edit: Callable[[str], None], verify: Callable[[str], bool]) -> None:
    if not path.lower().endswith(".mp3"):
        raise TagWriteError(MSG_NOT_MP3)
    folder, name = os.path.split(path)
    tmp = os.path.join(folder, f".{name}.myfun-tmp")
    try:
        try:
            shutil.copyfile(path, tmp)
            edit(tmp)
            if not verify(tmp):
                raise TagWriteError(MSG_VERIFY)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    logger.warning("임시 파일을 지우지 못함: %s", tmp)
    except TagWriteError:
        raise
    except PermissionError as exc:
        raise TagWriteError(MSG_DENIED) from exc
    except Exception as exc:
        logger.warning("태그 쓰기 실패: %s", exc)
        raise TagWriteError(MSG_OTHER) from exc


def _drop_front_covers(tags: ID3) -> None:
    """앞표지(type 3, 그리고 흔히 표지로 쓰는 type 0)만 지운다. 뒷표지·가수 사진 등은 둔다."""
    for key in [k for k, f in tags.items() if k.startswith("APIC") and f.type in (0, 3)]:
        del tags[key]


def write_tags(path: str, fields: dict[str, str], picture: bytes | object = KEEP,
               verify: Callable[[str], bool] | None = None) -> None:
    """fields에 없는 키는 그대로, 빈 글자는 그 프레임 삭제. picture = 바이트 / REMOVE / KEEP."""
    if isinstance(picture, (bytes, bytearray)):
        if picture_mime(bytes(picture)) is None or len(picture) > MAX_PICTURE:
            raise TagWriteError("그림은 10MB 이하의 jpg·png만 쓸 수 있습니다")
    title = fields.get("title")
    check = verify or _default_verify(title if title else None)

    def edit(tmp: str) -> None:
        try:
            tags = ID3(tmp)
            v24 = tags.version >= (2, 4, 0)
        except ID3NoHeaderError:
            tags, v24 = ID3(), False
        # 이미 v2.4인 파일은 v2.4로 둔다 (TSOP·TMOO 등이 안 사라지게)
        if not v24:
            tags.update_to_v23()
        for key, (fid, cls) in _FRAMES.items():
            if key not in fields:
                continue
            if key == "year":
                for old in ("TYER", "TDRC", "TDAT", "TIME"):   # 옛 날짜 조각이 새 년도와 섞이지 않게
                    tags.delall(old)
                fid, cls = ("TDRC", TDRC) if v24 else ("TYER", TYER)
            else:
                tags.delall(fid)
            value = fields[key]
            if value:
                tags.add(cls(encoding=1, text=[value]))
        if picture is REMOVE:
            _drop_front_covers(tags)
        elif isinstance(picture, (bytes, bytearray)):
            data = bytes(picture)
            _drop_front_covers(tags)
            desc = ""
            while f"APIC:{desc}" in tags:   # 남은 그림과 이름이 겹치면 덮어쓰니 피한다
                desc += " "
            tags.add(APIC(encoding=1, mime=picture_mime(data), type=3, desc=desc, data=data))
        tags.save(tmp, v1=0, v2_version=4 if v24 else 3)

    _safe_write(path, edit, check)


def clear_tags(path: str, verify: Callable[[str], bool] | None = None) -> None:
    """ID3 v1·v2를 모두 지운다."""
    def edit(tmp: str) -> None:
        delete(tmp, delete_v1=True, delete_v2=True)

    _safe_write(path, edit, verify or _default_verify(None))
