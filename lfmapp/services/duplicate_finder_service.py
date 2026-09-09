"""Duplicate file finder service.

Pure functions for scanning, grouping and hashing are separated from the
QThread-based worker so that the logic can be tested without Qt.

Two-pass approach (same as fdupes / rmlint):
1. Collect files and group by **size** — cheap pre-filter.
2. Within each size-collision group, compute a content hash (xxhash xxh64)
   and group by hash — the actual duplicate sets.

The worker emits results progressively so the UI can show groups as soon as
they are discovered, without waiting for the full scan to finish.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import xxhash
from PyQt6.QtCore import QThread, pyqtSignal

_HASH_CHUNK = 65536  # 64 KiB


# ---------------------------------------------------------------------------
# Pure data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileEntry:
    """A single file discovered during the scan."""

    path: Path
    size: int
    modified: float  # os.stat().st_mtime


@dataclass(frozen=True)
class DuplicateGroup:
    """A set of files with identical content."""

    hash_value: str
    size: int
    files: tuple[FileEntry, ...]

    @property
    def wasted(self) -> int:
        """Space wasted by keeping only one copy."""
        if len(self.files) < 2:
            return 0
        return self.size * (len(self.files) - 1)


# ---------------------------------------------------------------------------
# Pure helpers (testable without Qt)
# ---------------------------------------------------------------------------

def hash_file(path: Path) -> str:
    """Compute xxh64 content hash of *path* (incremental, 64 KiB chunks)."""
    h = xxhash.xxh64()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(_HASH_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
    except (OSError, PermissionError):
        return ""
    return h.hexdigest()


def collect_files(
    roots: list[Path],
    *,
    recursive: bool = True,
    min_size: int = 0,
    ignore_hidden: bool = False,
) -> list[FileEntry]:
    """Walk *roots* and return all matching file entries.

    Parameters
    ----------
    roots:
        Directories to scan.  Each root is walked independently; paths are
        kept absolute.
    recursive:
        When *True* (default), descend into subdirectories.
    min_size:
        Ignore files smaller than this many bytes.
    ignore_hidden:
        Skip files whose name starts with ``.``.
    """
    entries: list[FileEntry] = []
    for root in roots:
        if not root.is_dir():
            continue
        if recursive:
            for dirpath, dirnames, filenames in os.walk(root):
                # Prune hidden directories in-place so os.walk skips them.
                dirnames[:] = [
                    d for d in dirnames
                    if not (ignore_hidden and d.startswith("."))
                ]
                for name in filenames:
                    if ignore_hidden and name.startswith("."):
                        continue
                    fp = Path(dirpath) / name
                    try:
                        st = os.lstat(fp)
                    except (OSError, PermissionError):
                        continue
                    if not stat_is_regular(st):
                        continue
                    if st.st_size < min_size:
                        continue
                    entries.append(FileEntry(
                        path=fp,
                        size=st.st_size,
                        modified=st.st_mtime,
                    ))
        else:
            try:
                for item in root.iterdir():
                    if ignore_hidden and item.name.startswith("."):
                        continue
                    try:
                        st = os.lstat(item)
                    except (OSError, PermissionError):
                        continue
                    if not stat_is_regular(st):
                        continue
                    if st.st_size < min_size:
                        continue
                    entries.append(FileEntry(
                        path=item,
                        size=st.st_size,
                        modified=st.st_mtime,
                    ))
            except (OSError, PermissionError):
                pass
    return entries


def stat_is_regular(st: os.stat_result) -> bool:
    """Return *True* if *st* describes a regular file (not a symlink, pipe…)."""
    import stat as _stat
    return _stat.S_ISREG(st.st_mode)


def group_by_size(entries: list[FileEntry]) -> dict[int, list[FileEntry]]:
    """Bucket files by size. Only sizes with 2+ files are kept."""
    buckets: dict[int, list[FileEntry]] = {}
    for entry in entries:
        buckets.setdefault(entry.size, []).append(entry)
    return {size: files for size, files in buckets.items() if len(files) >= 2}


def group_duplicates(
    entries: list[FileEntry],
) -> list[DuplicateGroup]:
    """Two-pass duplicate detection: group by size, then hash within groups.

    Returns a list of `DuplicateGroup` sorted by wasted space descending.
    """
    size_groups = group_by_size(entries)
    result: list[DuplicateGroup] = []
    for _size, candidates in size_groups.items():
        hash_buckets: dict[str, list[FileEntry]] = {}
        for entry in candidates:
            digest = hash_file(entry.path)
            if not digest:
                continue
            hash_buckets.setdefault(digest, []).append(entry)
        for digest, files in hash_buckets.items():
            if len(files) < 2:
                continue
            result.append(DuplicateGroup(
                hash_value=digest,
                size=files[0].size,
                files=tuple(files),
            ))
    result.sort(key=lambda g: g.wasted, reverse=True)
    return result


# ---------------------------------------------------------------------------
# QThread worker (follows the project's standard worker pattern)
# ---------------------------------------------------------------------------

class DuplicateFinderWorker(QThread):
    """Scan directories and emit duplicate groups progressively.

    Signals
    -------
    progress(scanned: int)
        Emitted periodically with the number of files scanned so far.
    group_found(group)
        Emitted each time a `DuplicateGroup` is identified.
    finished(total_groups: int, total_wasted: int)
        Emitted once when the scan completes (or is cancelled).
    """

    progress = pyqtSignal(int)
    group_found = pyqtSignal(object)  # DuplicateGroup
    finished = pyqtSignal(int, int)   # total_groups, total_wasted

    def __init__(
        self,
        roots: list[Path],
        *,
        recursive: bool = True,
        min_size: int = 0,
        ignore_hidden: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._roots = list(roots)
        self._recursive = recursive
        self._min_size = min_size
        self._ignore_hidden = ignore_hidden
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        entries = collect_files(
            self._roots,
            recursive=self._recursive,
            min_size=self._min_size,
            ignore_hidden=self._ignore_hidden,
        )
        if not self._running:
            self.finished.emit(0, 0)
            return

        # Phase 1: group by size and report progress as files scanned.
        size_groups = group_by_size(entries)
        self.progress.emit(len(entries))

        if not self._running:
            self.finished.emit(0, 0)
            return

        # Phase 2: hash within size-collision groups.
        total_groups = 0
        total_wasted = 0
        for _size, candidates in size_groups.items():
            if not self._running:
                break
            hash_buckets: dict[str, list[FileEntry]] = {}
            for entry in candidates:
                if not self._running:
                    break
                digest = hash_file(entry.path)
                if digest:
                    hash_buckets.setdefault(digest, []).append(entry)
            for digest, files in hash_buckets.items():
                if len(files) < 2:
                    continue
                group = DuplicateGroup(
                    hash_value=digest,
                    size=files[0].size,
                    files=tuple(files),
                )
                total_groups += 1
                total_wasted += group.wasted
                self.group_found.emit(group)

        self.finished.emit(total_groups, total_wasted)
