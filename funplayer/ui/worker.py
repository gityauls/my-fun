from __future__ import annotations

from typing import Any, Callable

from PyQt5.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal


class _Signals(QObject):
    finished = pyqtSignal(object, object)  # (result, error)


class _Job(QRunnable):
    def __init__(self, work: Callable[[], Any], signals: _Signals) -> None:
        super().__init__()
        self.setAutoDelete(False)  # 파이썬 쪽이 수명을 쥔다
        self._work = work
        self._signals = signals

    def run(self) -> None:
        result, error = None, None
        try:
            result = self._work()
        except BaseException as e:  # noqa: BLE001 - 어떤 예외든 UI로 넘긴다
            error = e
        try:
            self._signals.finished.emit(result, error)
        except RuntimeError:
            # 신호 객체가 이미 사라졌다: 열린 결과가 있으면 닫는다
            _close(result)


def _close(result: Any) -> None:
    close = getattr(result, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001
            pass


class QtRunner(QObject):
    """작업 스레드 실행과 단발 타이머. 결과는 UI 스레드에서 done(result, error)로 전달한다."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._closed = False
        self._jobs: set[tuple[_Job, _Signals]] = set()
        self._timers: set[QTimer] = set()

    def run_async(self, work: Callable[[], Any], done: Callable[[Any, Any], None]) -> None:
        if self._closed:
            return
        signals = _Signals()
        job = _Job(work, signals)
        entry = (job, signals)

        def deliver(result: Any, error: Any) -> None:
            self._jobs.discard(entry)
            if self._closed:
                _close(result)
                return
            done(result, error)

        signals.finished.connect(deliver, Qt.QueuedConnection)
        self._jobs.add(entry)
        QThreadPool.globalInstance().start(job)

    def call_later(self, seconds: float, fn: Callable[[], None]) -> Callable[[], None]:
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

        if self._closed:
            return lambda: None
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
