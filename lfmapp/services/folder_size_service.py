"""Folder (directory) size computation in the background (Phase 9.2).

A `QFileSystemModel` reports a directory's *inode* size in its Size column,
which is meaningless to users ("4 KB" for a folder that holds 2 GB). Thunar and
Dolphin instead show a recursively summed size, computed off the UI thread, with
an "approximate" marker for very large trees and a cache invalidated by the
directory's own mtime.

This module keeps the logic **pure and Qt-free** (`compute_folder_size`,
`FolderSizeCache`) so it is testable headless, and provides a standard
`FolderSizeWorker` (QThread) that the workspace drives for the folders currently
listed. Symlinks are never followed (no cycles, no double counting); unreadable
entries are skipped rather than aborting the whole walk.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


def compute_folder_size(path: Path, *, limit: int | None = None) -> tuple[int, bool]:
    """Return ``(total_bytes, approximate)`` for the subtree under *path*.

    - Only regular files are summed; symlinks are skipped (not followed).
    - Inaccessible directories/files are ignored, not fatal.
    - If ``limit`` is given and the running total exceeds it, the walk stops and
      ``approximate`` is True (the cap guards pathological trees so the UI thread
      or a worker is never blocked unbounded).
    """
    path = Path(path)
    if not path.is_dir():
        return (0, False)
    total = 0
    approximate = False
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        for name in filenames:
            fp = os.path.join(dirpath, name)
            try:
                st = os.lstat(fp)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            total += st.st_size
            if limit is not None and total > limit:
                return (total, True)
        # Stop early on the limit even between directories.
        if limit is not None and total > limit:
            return (total, True)
    return (total, approximate)


class FolderSizeCache:
    """Memoizes folder sizes and invalidates them when the folder's own
    ``st_mtime_ns`` changes (a rename/add/remove inside bumps the dir mtime)."""

    def __init__(self):
        # path_str -> (size_bytes, approximate, mtime_ns)
        self._entries: dict[str, tuple[int, bool, int]] = {}

    def get(self, path: Path) -> tuple[int, bool] | None:
        """Return ``(size, approximate)`` if a still-fresh value is cached, else None."""
        key = str(path)
        entry = self._entries.get(key)
        if entry is None:
            return None
        size, approximate, mtime_ns = entry
        try:
            current = os.stat(path).st_mtime_ns
        except OSError:
            self._entries.pop(key, None)
            return None
        if current != mtime_ns:
            # Folder changed since we measured it: treat as stale.
            self._entries.pop(key, None)
            return None
        return (size, approximate)

    def put(self, path: Path, size: int, approximate: bool) -> None:
        try:
            mtime_ns = os.stat(path).st_mtime_ns
        except OSError:
            return
        self._entries[str(path)] = (size, bool(approximate), mtime_ns)

    def invalidate(self, path: Path | None = None) -> None:
        if path is None:
            self._entries.clear()
        else:
            self._entries.pop(str(path), None)

    def __len__(self) -> int:
        return len(self._entries)


class FolderSizeWorker(QThread):
    """Compute the size of a batch of folders off the UI thread.

    Emits ``size_ready`` (path, size_bytes, approximate) as each folder
    finishes so the view can update incrementally. ``stop()`` requests a
    cooperative cancellation between folders.
    """

    size_ready = pyqtSignal(object, object, bool)  # Path, int, bool

    def __init__(self, paths: list[Path], *, limit: int | None = None, parent=None):
        super().__init__(parent)
        self._paths = list(paths)
        self._limit = limit
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        for path in self._paths:
            if not self._running:
                return
            try:
                if not path.is_dir():
                    continue
                size, approximate = compute_folder_size(path, limit=self._limit)
            except OSError:
                continue
            if not self._running:
                return
            self.size_ready.emit(path, size, approximate)
