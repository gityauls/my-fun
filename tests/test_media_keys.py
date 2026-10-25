import ctypes, sys
import pytest
from PyQt5.QtWidgets import QApplication
from fakes import FakeApi
from funplayer.ui.media_keys import HOTKEY_ID_BASE, WM_HOTKEY, MediaKeys

def test_enable_registers_four_keys_once(qapp):
    api = FakeApi(); k = MediaKeys(api=api)
    assert k.enable() and k.enabled
    assert api.registered == {HOTKEY_ID_BASE + vk: vk for vk in (0xB3, 0xB0, 0xB1, 0xB2)}
    k.enable(); assert len(api.calls) == 4
    k.disable()

def test_busy_key_returns_false_and_keeps_others(qapp):
    api = FakeApi(busy={0xB3}); k = MediaKeys(api=api)
    assert k.enable() is False and set(api.registered.values()) == {0xB0, 0xB1, 0xB2}
    k.disable(); assert api.registered == {}

def test_disable_unregisters_and_is_idempotent(qapp):
    api = FakeApi(); k = MediaKeys(api=api); k.enable(); k.disable(); k.disable()
    assert api.registered == {} and not k.enabled

def test_handle_hotkey_emits(qapp):
    k = MediaKeys(api=FakeApi()); k.enable(); hits = []
    for name in ("play_pause", "next", "prev", "stop"):
        getattr(k, f"{name}_pressed").connect(lambda n=name: hits.append(n))
    for vk in (0xB3, 0xB0, 0xB1, 0xB2):
        assert k.handle_hotkey(HOTKEY_ID_BASE + vk)
    assert hits == ["play_pause", "next", "prev", "stop"] and not k.handle_hotkey(1)
    k.disable(); assert not k.handle_hotkey(HOTKEY_ID_BASE + 0xB3)

def test_no_api_is_noop(qapp):
    k = MediaKeys()
    assert k.enable() is True and not k.handle_hotkey(HOTKEY_ID_BASE + 0xB3)
    k.disable()

@pytest.mark.skipif(sys.platform != "win32", reason="Windows 메시지")
def test_native_filter_routes_thread_hotkey(qapp):
    k = MediaKeys(api=FakeApi()); k.enable(); hits = []
    k.play_pause_pressed.connect(lambda: hits.append(1))
    tid = ctypes.windll.kernel32.GetCurrentThreadId()
    ctypes.windll.user32.PostThreadMessageW(tid, WM_HOTKEY, HOTKEY_ID_BASE + 0xB3, 0)
    QApplication.processEvents()
    assert hits == [1]
    k.disable()
    ctypes.windll.user32.PostThreadMessageW(tid, WM_HOTKEY, HOTKEY_ID_BASE + 0xB3, 0)
    QApplication.processEvents()
    assert hits == [1]
