from __future__ import annotations

import threading

from PyQt5.QtTest import QTest

from funplayer.ui.worker import QtRunner


def _wait_for(cond, ms):
    # PyQt5 QTest에는 qWaitFor가 없다
    waited = 0
    while not cond() and waited < ms:
        QTest.qWait(10); waited += 10
    return cond()


def test_run_async_delivers_on_ui_thread(qapp):
    r = QtRunner(); got = []; main = threading.get_ident()
    r.run_async(lambda: threading.get_ident(), lambda res, err: got.append((res != main, err, threading.get_ident() == main)))
    _wait_for(lambda: got, 2000)
    assert got == [(True, None, True)]


def test_run_async_passes_exception(qapp):
    r = QtRunner(); got = []
    def boom(): raise ValueError("x")
    r.run_async(boom, lambda res, err: got.append((res, type(err))))
    _wait_for(lambda: got, 2000); assert got == [(None, ValueError)]


def test_call_later_and_cancel(qapp):
    r = QtRunner(); hits = []
    r.call_later(0.01, lambda: hits.append(1)); cancel = r.call_later(0.01, lambda: hits.append(2)); cancel()
    QTest.qWait(80); assert hits == [1]


def test_shutdown_drops_late_results(qapp):
    r = QtRunner(); got = []; gate = threading.Event()
    r.run_async(lambda: gate.wait(1) or 1, lambda res, err: got.append(res)); r.call_later(0.01, lambda: got.append("t"))
    r.shutdown(); gate.set(); QTest.qWait(150); assert got == []


def test_shutdown_closes_late_closable_result(qapp):
    class Res:
        closed = False
        def close(self): self.closed = True
    r = QtRunner(); got = []; gate = threading.Event(); res = Res()
    r.run_async(lambda: gate.wait(1) and res, lambda x, e: got.append(x))
    r.shutdown(); gate.set()
    _wait_for(lambda: res.closed, 2000)
    assert res.closed and got == []
