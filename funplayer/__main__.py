from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

from funplayer.core.settings import JsonStore, Settings
from funplayer.ui import media_keys as media_keys_mod
from funplayer.ui.fonts import load_fonts
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
    family = load_fonts()
    app.setFont(QFont(family, 9))
    store = JsonStore(app_dir() / "settings.json")
    settings = Settings(store.data, store.save)
    panel = PlayerPanel(
        settings, session_path=str(app_dir() / "last.m3u8"),
        stations_path=str(app_dir() / "stations.json"),
        rename_log_path=str(app_dir() / "rename_log.txt"),
        media_keys=media_keys_mod.MediaKeys(api=media_keys_mod.default_api()),
        font_family=family)
    panel.setWindowTitle("my-fun")
    panel.use_window_chrome()
    keeper = WindowKeeper(panel, settings)
    keeper.start()
    # Windows 로그오프·종료 때는 exec_() 뒤가 돌지 않을 수 있어 끝나기 직전에도 저장한다 (두 번 해도 된다)
    app.aboutToQuit.connect(keeper.save)
    app.aboutToQuit.connect(panel.controller.save_session)
    panel.show()
    code = app.exec_()
    app.aboutToQuit.disconnect(keeper.save)
    app.aboutToQuit.disconnect(panel.controller.save_session)
    keeper.save()
    panel.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
