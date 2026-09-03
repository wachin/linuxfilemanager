"""File operation worker threads for linux-file-manager.

Provides CopyWorker, MoveWorker, DeleteWorker, and TrashWorker with
progress and file-level events. MoveWorker uses a copy+delete strategy
so operations can be cancelled cooperatively.
"""

import shutil
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


class CopyWorker(QThread):
    """Copy files/directories in a background thread."""

    progress = pyqtSignal(int)       # percentage (0-100)
    finished = pyqtSignal(bool, str) # success, message
    file_copied = pyqtSignal(str)    # path of copied file

    def __init__(self, source: Path, destination: Path, parent=None):
        super().__init__(parent)
        self.source = source
        self.destination = destination
        self._running = True

    def run(self):
        try:
            dest = self.destination / self.source.name
            if self.source.is_dir():
                self._copy_tree(self.source, dest)
            else:
                shutil.copy2(str(self.source), str(dest))
                self.file_copied.emit(str(self.source))
                self.progress.emit(100)
            self.finished.emit(True, f"Copied to {dest}")
        except Exception as exc:
            self.finished.emit(False, str(exc))

    def _copy_tree(self, src: Path, dst: Path):
        dst.mkdir(parents=True, exist_ok=True)
        items = list(src.iterdir())
        total = len(items)
        for i, item in enumerate(items):
            if not self._running:
                break
            dest_item = dst / item.name
            if item.is_dir():
                self._copy_tree(item, dest_item)
            else:
                shutil.copy2(str(item), str(dest_item))
                self.file_copied.emit(str(item))
            if total > 0:
                self.progress.emit(int((i + 1) / total * 100))

    def stop(self):
        self._running = False


class MoveWorker(QThread):
    """Move files/directories in a background thread using copy+delete.

    This approach allows cooperative cancellation while copying large files.
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    file_copied = pyqtSignal(str)

    def __init__(self, source: Path, destination: Path, parent=None):
        super().__init__(parent)
        self.source = source
        self.destination = destination
        self._running = True

    def run(self):
        try:
            dest = self.destination / self.source.name
            if self.source.is_dir():
                self._copy_tree(self.source, dest)
                if self._running:
                    shutil.rmtree(str(self.source))
            else:
                self._copy_file(self.source, dest)
                if self._running:
                    self.source.unlink()

            if self._running:
                self.progress.emit(100)
                self.finished.emit(True, f"Moved to {dest}")
            else:
                self.finished.emit(False, "Operation canceled")
        except Exception as exc:
            self.finished.emit(False, str(exc))

    def _copy_file(self, src: Path, dst: Path, bufsize: int = 1024 * 1024):
        dst.parent.mkdir(parents=True, exist_ok=True)
        total = src.stat().st_size if src.exists() else 0
        copied = 0
        if not self._running:
            return
        with src.open("rb") as fsrc, dst.open("wb") as fdst:
            while True:
                if not self._running:
                    break
                buf = fsrc.read(bufsize)
                if not buf:
                    break
                fdst.write(buf)
                copied += len(buf)
                # emit file event and progress
                self.file_copied.emit(str(src))
                if total > 0:
                    self.progress.emit(int(copied / total * 100))
        if not self._running and dst.exists():
            try:
                dst.unlink()
            except Exception:
                pass

    def _copy_tree(self, src: Path, dst: Path):
        dst.mkdir(parents=True, exist_ok=True)
        items = list(src.iterdir())
        total = len(items)
        for i, item in enumerate(items):
            if not self._running:
                break
            dest_item = dst / item.name
            if item.is_dir():
                self._copy_tree(item, dest_item)
            else:
                self._copy_file(item, dest_item)
            if total > 0:
                self.progress.emit(int((i + 1) / total * 100))

    def stop(self):
        self._running = False


class DeleteWorker(QThread):
    """Delete files/directories in a background thread."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    file_deleted = pyqtSignal(str)

    def __init__(self, paths: list[Path], parent=None):
        super().__init__(parent)
        self.paths = paths
        self._running = True

    def run(self):
        total = len(self.paths)
        deleted = 0
        errors = []
        for path in self.paths:
            if not self._running:
                break
            try:
                if path.is_dir():
                    shutil.rmtree(str(path))
                else:
                    path.unlink()
                self.file_deleted.emit(str(path))
                deleted += 1
            except Exception as exc:
                errors.append(f"{path}: {exc}")
            if total > 0:
                self.progress.emit(int(deleted / total * 100))

        if errors:
            self.finished.emit(False, "\n".join(errors))
        else:
            self.finished.emit(True, f"Deleted {deleted} item(s)")

    def stop(self):
        self._running = False


class TrashWorker(QThread):
    """Send files to trash in a background thread."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    item_trashed = pyqtSignal(str, str, str)

    def __init__(self, paths: list[Path], parent=None):
        super().__init__(parent)
        self.paths = paths
        self._running = True

    def run(self):
        from lfmapp.services.trash_service import TRASH_FILES_DIR, TRASH_INFO_DIR, send_to_trash
        total = len(self.paths)
        errors = []
        for i, path in enumerate(self.paths):
            if not self._running:
                break
            try:
                original = path.resolve()
                trash_name = send_to_trash(path)
                self.item_trashed.emit(
                    str(original),
                    str(TRASH_FILES_DIR / trash_name),
                    str(TRASH_INFO_DIR / f"{trash_name}.trashinfo"),
                )
            except Exception as exc:
                errors.append(f"{path}: {exc}")
            if total > 0:
                self.progress.emit(int((i + 1) / total * 100))

        if errors:
            self.finished.emit(False, "\n".join(errors))
        else:
            self.finished.emit(True, f"Moved {total} item(s) to trash")

    def stop(self):
        self._running = False
