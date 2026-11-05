import logging, sys
from logging.handlers import RotatingFileHandler
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
import funplayer.__main__ as entry

def _cleanup():
    lg = logging.getLogger("funplayer")
    for h in list(lg.handlers):
        h.close(); lg.removeHandler(h)

def test_app_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert entry.app_dir() == tmp_path / "my-fun"

def test_setup_logging(tmp_path):
    try:
        entry.setup_logging(tmp_path / "logs"); entry.setup_logging(tmp_path / "logs")
        files = [h for h in logging.getLogger("funplayer").handlers if isinstance(h, RotatingFileHandler)]
        assert len(files) == 1 and files[0].maxBytes == 1_000_000 and files[0].backupCount == 2
        assert files[0].baseFilename.endswith("funplayer.log")
    finally:
        _cleanup()

def test_main_smoke(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    import funplayer.ui.media_keys as mk
    monkeypatch.setattr(mk, "default_api", lambda: None)
    seen = {}

    class Panel(entry.PlayerPanel):
        def __init__(self, *a, **kw):
            seen.update(kw)
            super().__init__(*a, **kw)
    monkeypatch.setattr(entry, "PlayerPanel", Panel)
    QTimer.singleShot(0, QApplication.instance().quit)
    try:
        assert entry.main([]) == 0
        # stations.json이 없어도 켜지고 꺼진다. 바꾼 게 없으면 파일을 만들지 않는다
        assert seen["font_family"] == "Noto Sans KR"
        assert seen["stations_path"] == str(tmp_path / "my-fun" / "stations.json")
        assert not (tmp_path / "my-fun" / "stations.json").exists()
        assert (tmp_path / "my-fun" / "logs" / "funplayer.log").exists()
        import json
        data = json.loads((tmp_path / "my-fun" / "settings.json").read_text(encoding="utf-8"))
        assert data["player_geometry"][2:] == [380, 480]
    finally:
        _cleanup()
