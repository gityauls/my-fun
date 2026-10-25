"""테스트용 태그 파일 만들기: 손으로 쓴 ID3v2.3(글자 인코딩 0)·ID3v1 태그를 MP3 앞뒤에 붙인다."""
import random
import struct
import zlib
from pathlib import Path


def _png(side: int, pixels: bytes) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


def png_1x1() -> bytes:
    return _png(1, b"\x00\xff\x00\x00")


def noise_png(side: int) -> bytes:
    """잘 압축되지 않는 side×side RGB PNG (큰 표지 그림 대신)."""
    rng = random.Random(0)
    return _png(side, b"".join(b"\x00" + rng.randbytes(3 * side) for _ in range(side)))


def _frame(fid: str, data: bytes) -> bytes:
    return fid.encode() + struct.pack(">I", len(data)) + b"\x00\x00" + data


def _syncsafe(n: int) -> bytes:
    return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])


def _strip_v2(data: bytes) -> bytes:
    if data[:3] == b"ID3":
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        return data[10 + size:]
    return data


def write_tagged(dest, source_mp3, v2=None, picture=None, v1=None) -> Path:
    """v2: {"TIT2": 바이트, ...} (글자 인코딩 0 바이트 그대로), picture: PNG 바이트,
    v1: (제목, 가수, 앨범) 바이트 — 각각 30바이트로 자른다."""
    audio = _strip_v2(Path(source_mp3).read_bytes())
    head = b""
    if v2 or picture:
        body = b"".join(_frame(k, b"\x00" + v) for k, v in (v2 or {}).items())
        if picture:
            body += _frame("APIC", b"\x00image/png\x00\x03\x00" + picture)
        head = b"ID3\x03\x00\x00" + _syncsafe(len(body)) + body
    tail = b""
    if v1:
        pad = lambda b: b[:30].ljust(30, b"\x00")
        tail = b"TAG" + pad(v1[0]) + pad(v1[1]) + pad(v1[2]) + b"2000" + b"\x00" * 30 + b"\xff"
    Path(dest).write_bytes(head + audio + tail)
    return Path(dest)
