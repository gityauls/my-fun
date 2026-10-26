from __future__ import annotations

import threading
from typing import Any, Callable

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal


class _Signals(QObject):
    finished = pyqtSignal(object, object)  # (result, error)


def _close(result: Any) -> None:
    close = getattr(result, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001
            pass


class QtRunner(QObject):
    """작업 스레드 실행과 단발 타이머. 결과는 UI 스레드에서 done(result, error)로 전달한다.

    작업마다 데몬 스레드를 쓴다: 네트워크에 막힌 작업이 앱 종료를 붙잡거나
    스레드 풀을 굶기지 않게 하기 위해서다.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._closed = False
        self._jobs: set[tuple[threading.Thread, _Signals]] = set()
        self._timers: set[QTimer] = set()

    def run_async(self, work: Callable[[], Any], done: Callable[[Any, Any], None]) -> None:
        if self._closed:
            return
        signals = _Signals()

        def run() -> None:
            result, error = None, None
            try:
                result = work()
            except Exception as e:  # noqa: BLE001 - 예외는 UI로 넘긴다
                error = e
            try:
                signals.finished.emit(result, error)
            except RuntimeError:
                _close(result)

        thread = threading.Thread(target=run, name="radio-worker", daemon=True)
        entry = (thread, signals)

        def deliver(result: Any, error: Any) -> None:
            self._jobs.discard(entry)
            if self._closed:
                # 이벤트 루프가 아직 돌 때만 닫힌다(종료 중이면 도착하지 않는다)
                _close(result)
                return
            done(result, error)

        signals.finished.connect(deliver, Qt.QueuedConnection)
        self._jobs.add(entry)
        thread.start()

    def call_later(self, seconds: float, fn: Callable[[], None]) -> Callable[[], None]:
        if self._closed:
            return lambda: None
        timer = QTimer(self)
        timer.setSingleShot(True)

        def fire() -> None:
            self._timers.discard(timer)
            timer.deleteLater()
            if not self._closed:
                fn()

        def cancel() -> None:
            if timer in self._timers:
                self._timers.discard(timer)
                timer.stop()
                timer.deleteLater()

        timer.timeout.connect(fire)
        self._timers.add(timer)
        timer.start(max(0, int(seconds * 1000)))
        return cancel

    def shutdown(self) -> None:
        # 진행 중인 작업은 참조를 유지해 늦은 결과를 받아 버린다(deliver가 닫기까지 한다).
        self._closed = True
        for timer in list(self._timers):
            timer.stop()
            timer.deleteLater()
        self._timers.clear()
