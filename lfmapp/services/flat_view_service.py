"""Flat view service (backlog P2 — "Flat View: one folder and its whole tree").

Walks a folder tree and flattens the hierarchy into a single list, in three
modes:

- ``mixed``: files and folders from the whole tree, interleaved;
- ``files_only``: only files (folders are hidden but still traversed);
- ``grouped``: like mixed, but each subfolder appears as a collapsible block
  (the model exposes a ``group`` column for this; entries keep the tree
  relation through the relative path).

The scanning logic is pure (``collect_entries``) so it can be unit-tested
without Qt; ``FlatViewWorker`` is the background thread that emits entries in
progressive batches, reusing the same pattern as ``SearchThread``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


class FlatViewMode(str, Enum):
    """The three degrees of flatness."""
    MIXED = "mixed"
    FILES_ONLY = "files_only"
    GROUPED = "grouped"

    @classmethod
    def from_string(cls, value: str, default: "FlatViewMode | None" = None) -> "FlatViewMode":
        if default is None:
            default = cls.MIXED
        try:
            return cls(str(value).lower())
        except ValueError:
            return default


@dataclass(frozen=True)
class FlatEntry:
    """One flattened item: the absolute path plus where it lives in the tree."""
    path: Path
    relative: str  # path relative to the scan root, "" for direct children

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_dir(self) -> bool:
        try:
            return self.path.is_dir()
        except OSError:
            return False


def collect_entries(
    root: Path,
    mode: FlatViewMode | str = FlatViewMode.MIXED,
    include_hidden: bool = True,
) -> list[FlatEntry]:
    """Synchronously flatten a folder tree (pure, testable).

    Never raises for unreadable subfolders: they are simply skipped. The
    root itself is not included; its direct children have ``relative == ""``.
    """
    mode = FlatViewMode.from_string(mode) if not isinstance(mode, FlatViewMode) else mode
    root = Path(root)
    entries: list[FlatEntry] = []

    def walk(current: Path, rel_prefix: str):
        try:
            children = sorted(
                current.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.casefold()),
            )
        except (PermissionError, FileNotFoundError, OSError):
            return
        for child in children:
            if not include_hidden and child.name.startswith("."):
                continue
            rel = f"{rel_prefix}/{child.name}" if rel_prefix else child.name
            try:
                is_dir = child.is_dir()
            except OSError:
                continue
            if mode != FlatViewMode.FILES_ONLY or not is_dir:
                entries.append(FlatEntry(path=child, relative=rel))
            if is_dir:
                walk(child, rel)

    walk(root, "")
    return entries


class FlatViewWorker(QThread):
    """Background tree walk emitting flat entries in progressive batches."""

    batch = pyqtSignal(list)   # list[FlatEntry]
    finished = pyqtSignal(int)  # total count

    def __init__(self, root: Path, mode: FlatViewMode | str = FlatViewMode.MIXED,
                 include_hidden: bool = True, batch_size: int = 100, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.mode = mode
        self.include_hidden = include_hidden
        self.batch_size = max(1, batch_size)
        self._running = True

    def run(self):
        count = 0
        pending: list[FlatEntry] = []
        mode = self.mode if isinstance(self.mode, FlatViewMode) else FlatViewMode.from_string(self.mode)

        for current_root, dirs, files in os.walk(self.root):
            if not self._running:
                break
            current = Path(current_root)
            rel_root = current.relative_to(self.root)
            rel_prefix = "" if rel_root == Path(".") else str(rel_root)
            try:
                children = sorted(
                    current.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.casefold()),
                )
            except (PermissionError, FileNotFoundError, OSError):
                continue
            for child in children:
                if not self._running:
                    break
                if not self.include_hidden and child.name.startswith("."):
                    continue
                rel = f"{rel_prefix}/{child.name}" if rel_prefix else child.name
                try:
                    is_dir = child.is_dir()
                except OSError:
                    continue
                if mode == FlatViewMode.FILES_ONLY and is_dir:
                    continue
                pending.append(FlatEntry(path=child, relative=rel))
                count += 1
                if len(pending) >= self.batch_size:
                    self.batch.emit(pending)
                    pending = []
        if pending:
            self.batch.emit(pending)
        self.finished.emit(count)

    def stop(self):
        self._running = False
