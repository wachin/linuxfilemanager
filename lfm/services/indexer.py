"""Background indexer and folder watcher for linux-file-manager.

Provides `IndexerThread` for long-running indexing jobs and `IndexerService`
that manages background indexing and optional folder watching.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtCore import QFileSystemWatcher

from .indexing import IndexService


class IndexerThread(QThread):
    progress = pyqtSignal(int)  # percent (approx)
    indexed = pyqtSignal(str)  # path
    finished = pyqtSignal(int)  # count

    def __init__(self, indexer: IndexService, root: Path, recursive: bool = True, limit: int = 50000):
        super().__init__()
        self.indexer = indexer
        self.root = Path(root)
        self.recursive = recursive
        self.limit = limit
        self._running = True

    def run(self):
        # Simple implementation: iterate files and call backend.index_file
        count = 0
        try:
            files = list(self.root.rglob("*")) if self.recursive else list(self.root.iterdir())
            total = len([p for p in files if p.is_file()])
            processed = 0
            for p in files:
                if not self._running:
                    break
                try:
                    if p.is_file():
                        self.indexer.index_file(p)
                        self.indexed.emit(str(p))
                        processed += 1
                        count += 1
                        if total > 0:
                            percent = int(processed / total * 100)
                            self.progress.emit(percent)
                        if count >= self.limit:
                            break
                except Exception:
                    continue
        finally:
            self.finished.emit(count)

    def stop(self):
        self._running = False


class IndexerService(QObject):
    """Manage indexing tasks and folder watching."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.index_service = IndexService.default()
        self._current_thread: Optional[IndexerThread] = None
        self._watcher = QFileSystemWatcher(self)

    def index_path(self, path: Path) -> QThread:
        """Index a single path (file or folder) in a short-lived thread.

        Returns the started QThread so callers can connect signals.
        """
        class _SingleIndexThread(QThread):
            finished = pyqtSignal(str)
            error = pyqtSignal(str)

            def __init__(self, indexer: IndexService, p: Path):
                super().__init__()
                self.indexer = indexer
                self.p = Path(p)

            def run(self):
                try:
                    if self.p.is_file():
                        self.indexer.index_file(self.p)
                    else:
                        self.indexer.index_folder(self.p, recursive=False)
                    self.finished.emit(str(self.p))
                except Exception as exc:
                    self.error.emit(str(exc))

        thread = _SingleIndexThread(self.index_service, Path(path))
        thread.start()
        return thread

    def start_index(self, root: Path, recursive: bool = True, limit: int = 50000) -> IndexerThread:
        if self._current_thread is not None and self._current_thread.isRunning():
            # stop existing job
            self._current_thread.stop()
            self._current_thread.wait()
        thread = IndexerThread(self.index_service, root, recursive=recursive, limit=limit)
        self._current_thread = thread
        thread.start()
        return thread

    def stop_current(self):
        if self._current_thread is not None and self._current_thread.isRunning():
            self._current_thread.stop()

    def watch_folder(self, folder: Path):
        # Add folder to QFileSystemWatcher so changes can be observed
        folder = str(Path(folder).resolve())
        if folder not in self._watcher.directories():
            try:
                self._watcher.addPath(folder)
            except Exception:
                pass

    def remove_watch(self, folder: Path):
        folder = str(Path(folder).resolve())
        if folder in self._watcher.directories():
            try:
                self._watcher.removePath(folder)
            except Exception:
                pass

    def connect_changed(self, slot):
        self._watcher.directoryChanged.connect(slot)
        self._watcher.fileChanged.connect(slot)
