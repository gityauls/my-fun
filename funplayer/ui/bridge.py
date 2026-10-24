from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal


class PlayerBridge(QObject):
    """엔진 스레드의 콜백을 Qt 신호로 바꾼다."""

    ended = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, player, parent=None) -> None:
        super().__init__(parent)
        player.on_end = self.ended.emit
        player.on_error = self.error.emit
