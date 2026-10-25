from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys

from PyQt5.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, pyqtSignal

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
HOTKEY_ID_BASE = 0xA000
KEYS = {0xB3: "play_pause", 0xB0: "next", 0xB1: "prev", 0xB2: "stop"}
MEDIA_KEYS_BUSY_MSG = "멀티미디어 키를 다른 프로그램이 쓰고 있습니다"


class Win32HotkeyApi:
    """RegisterHotKey를 창 핸들 없이(스레드에) 건다."""

    def register(self, hotkey_id: int, vk: int) -> bool:
        return bool(ctypes.windll.user32.RegisterHotKey(None, hotkey_id, MOD_NOREPEAT, vk))

    def unregister(self, hotkey_id: int) -> None:
        ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)


def default_api() -> Win32HotkeyApi | None:
    return Win32HotkeyApi() if sys.platform == "win32" else None


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, owner: MediaKeys) -> None:
        super().__init__()
        self._owner = owner

    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and self._owner.handle_hotkey(int(msg.wParam)):
                return True, 0
        return False, 0


class MediaKeys(QObject):
    play_pause_pressed = pyqtSignal()
    next_pressed = pyqtSignal()
    prev_pressed = pyqtSignal()
    stop_pressed = pyqtSignal()

    def __init__(self, parent=None, api=None) -> None:
        super().__init__(parent)
        self._api = api
        self._ids: dict[int, str] = {}
        self._on = False
        self._filter: _HotkeyFilter | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._ids) if self._api is not None else self._on

    @property
    def complete(self) -> bool:
        """네 키가 모두 걸려 있는가."""
        return len(self._ids) == len(KEYS) if self._api is not None else self._on

    def enable(self) -> bool:
        if self._api is None:
            self._on = True
            return True
        for vk, name in KEYS.items():
            hid = HOTKEY_ID_BASE + vk
            if hid not in self._ids and self._api.register(hid, vk):
                self._ids[hid] = name
        if self._filter is None:
            app = QCoreApplication.instance()
            if app is not None:
                self._filter = _HotkeyFilter(self)
                app.installNativeEventFilter(self._filter)
        return len(self._ids) == len(KEYS)

    def disable(self) -> None:
        self._on = False
        if self._api is not None:
            for hid in list(self._ids):
                self._api.unregister(hid)
        self._ids.clear()
        if self._filter is not None:
            app = QCoreApplication.instance()
            if app is not None:
                app.removeNativeEventFilter(self._filter)
            self._filter = None

    def handle_hotkey(self, hotkey_id: int) -> bool:
        name = self._ids.get(hotkey_id)
        if name is None:
            return False
        getattr(self, f"{name}_pressed").emit()
        return True
