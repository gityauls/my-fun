import threading, time
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from fakes import FakePlayer
from funplayer.ui.bridge import PlayerBridge

def wait_for(cond, timeout=1.0):
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        QApplication.processEvents(); time.sleep(0.005)

def test_callbacks_arrive_on_gui_thread(qapp):
    fake = FakePlayer(); bridge = PlayerBridge(fake); got = []
    bridge.ended.connect(lambda: got.append(threading.current_thread() is threading.main_thread()), Qt.QueuedConnection)
    bridge.error.connect(lambda m: got.append(m), Qt.QueuedConnection)
    t = threading.Thread(target=lambda: (fake.on_end(), fake.on_error("x"))); t.start(); t.join()
    wait_for(lambda: len(got) == 2)
    assert got == [True, "x"]
