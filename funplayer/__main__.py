from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from funplayer.core.settings import JsonStore, Settings
from funplayer.ui.player_panel import PlayerPanel
from funplayer.ui.window_keeper import WindowKeeper

logger = logging.getLogger("funplayer")


def app_dir() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "my-fun"


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "funplayer.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    stream_handler = logging.StreamHandler()
    for h in (file_handler, stream_handler):
        h.setFormatter(fmt)
        logger.addHandler(h)


def _log_excepthook(exc_type, exc_value, exc_tb) -> None:
    logger.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


def main(argv: list[str] | None = None) -> int:
    setup_logging(app_dir() / "logs")
    sys.excepthook = _log_excepthook
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setStyle("Fusion")
    store = JsonStore(app_dir() / "settings.json")
    settings = Settings(store.data, store.save)
    panel = PlayerPanel(settings, session_path=str(app_dir() / "last.m3u8"))
    panel.setWindowTitle("my-fun")
    keeper = WindowKeeper(panel, settings)
    keeper.start()
    panel.show()
    code = app.exec_()
    keeper.save()
    panel.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
