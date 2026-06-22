"""Background operation queue for file operation workers."""

from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal


class BackgroundOperationQueue(QObject):
    """Run queued workers with a fixed concurrency limit."""

    operation_queued = pyqtSignal(object)
    operation_started = pyqtSignal(object)
    operation_finished = pyqtSignal(object)

    def __init__(self, max_concurrent: int = 1, parent=None):
        super().__init__(parent)
        self.max_concurrent = max(1, int(max_concurrent))
        self._pending = deque()
        self._active = []

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def total_count(self) -> int:
        return self.pending_count + self.active_count

    def enqueue(self, worker) -> None:
        self._pending.append(worker)
        self.operation_queued.emit(worker)
        self._start_next()

    def cancel_pending(self) -> list:
        canceled = list(self._pending)
        self._pending.clear()
        return canceled

    def stop_active(self) -> None:
        for worker in list(self._active):
            if hasattr(worker, "stop"):
                worker.stop()

    def _start_next(self) -> None:
        while self._pending and len(self._active) < self.max_concurrent:
            worker = self._pending.popleft()
            self._active.append(worker)
            worker.finished.connect(lambda *args, w=worker: self._on_worker_finished(w))
            self.operation_started.emit(worker)
            try:
                worker.start()
            except Exception:
                self._on_worker_finished(worker)

    def _on_worker_finished(self, worker) -> None:
        if worker in self._active:
            self._active.remove(worker)
        self.operation_finished.emit(worker)
        self._start_next()
