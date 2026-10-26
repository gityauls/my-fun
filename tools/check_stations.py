"""Manual check of every built-in station (uses the internet; not part of the test suite).

Usage: python tools/check_stations.py OUT.txt
Opens each built-in station, decodes about 3 seconds, and writes one
"id<TAB>OK" or "id<TAB>FAIL reason" line per station to OUT.txt (UTF-8).
Needs funplayer.engine.resolve and funplayer.engine.decoder.open_stream (Tasks 3-4).
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from funplayer.core.stations import BUILTIN_STATIONS  # noqa: E402
from funplayer.engine.decoder import open_stream  # noqa: E402
from funplayer.engine.resolve import resolve  # noqa: E402

LISTEN_SECONDS = 3.0


def check(station) -> str:
    try:
        decoder = open_stream(resolve(station))
    except Exception as e:  # noqa: BLE001 - report any failure as text
        return f"FAIL {type(e).__name__}: {e}"
    try:
        blocks = 0
        end = time.monotonic() + LISTEN_SECONDS
        while time.monotonic() < end:
            if decoder.read() is None:
                break
            blocks += 1
        return "OK" if blocks else "FAIL no audio"
    except Exception as e:  # noqa: BLE001
        return f"FAIL {type(e).__name__}: {e}"
    finally:
        decoder.close()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: check_stations.py OUT.txt")
        return 2
    with open(argv[1], "w", encoding="utf-8") as out:
        for st in BUILTIN_STATIONS:
            line = f"{st.id}\t{st.name}\t{check(st)}"
            print(line)
            out.write(line + "\n")
            out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
