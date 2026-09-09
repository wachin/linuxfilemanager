"""Conflict model and resolution logic for copy/move (ROADMAP Phase 3.1).

UI-independent: the workers ask a resolver callable whenever a destination
already exists. The resolver may come from the GUI (a dialog) or from tests,
and returns a :class:`ConflictAnswer` with the chosen resolution and, for
rename-like resolutions, the new name.

Decisions with "apply to all" are remembered per conflict kind
(``file`` / ``folder``) and only for the current operation -- nothing is
persisted to disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Resolution(Enum):
    REPLACE = "replace"      # overwrite the existing item (files)
    SKIP = "skip"            # leave the existing item untouched
    KEEP_BOTH = "keep_both"  # copy/move under a generated free name
    RENAME = "rename"        # copy/move under a user-provided name
    MERGE = "merge"          # folder + folder: descend and resolve per item
    CANCEL = "cancel"        # abort the rest of the operation
    KEEP_NEWER = "keep_newer"          # replace only if the source is newer
    SKIP_IDENTICAL = "skip_identical"  # skip files that are identical (size+mtime)
    RENAME_OLD = "rename_old"          # rename the existing item, then write the source


def files_identical(source: Path, existing: Path) -> bool:
    """True if two *files* have the same size and same modification time.

    Deliberately cheap (no content read), matching the "Skip Identical"
    semantics of the reference managers. Non-files → False.
    """
    try:
        if not source.is_file() or not existing.is_file():
            return False
        s, e = source.stat(), existing.stat()
    except OSError:
        return False
    return s.st_size == e.st_size and int(s.st_mtime) == int(e.st_mtime)


def source_is_newer(source: Path, existing: Path) -> bool:
    """True if ``source``'s modification time is strictly newer than ``existing``."""
    try:
        return source.stat().st_mtime > existing.stat().st_mtime
    except OSError:
        return False


@dataclass
class Conflict:
    """A collision between an incoming item and an existing destination."""

    source: Path
    existing: Path

    @property
    def kind(self) -> str:
        return "folder" if self.source.is_dir() else "file"

    @property
    def source_info(self) -> dict:
        return _path_info(self.source)

    @property
    def existing_info(self) -> dict:
        return _path_info(self.existing)


def _path_info(path: Path) -> dict:
    """Snapshot of name/size/date for the side-by-side comparison."""
    info = {"name": path.name, "location": str(path.parent), "size": None, "modified": None}
    try:
        stat = path.stat()
    except OSError:
        return info
    if path.is_file():
        info["size"] = stat.st_size
    info["modified"] = stat.st_mtime
    return info


@dataclass
class ConflictAnswer:
    resolution: Resolution
    new_name: str | None = None


def suggest_free_name(source: Path, parent: Path) -> str:
    """Return a non-conflicting name in ``parent`` based on ``source``.

    ``report.pdf`` → ``report (copy).pdf``, then ``report (copy 2).pdf``…
    """
    stem = source.stem
    suffix = source.suffix
    candidate = f"{stem} (copy){suffix}"
    counter = 2
    while True:
        if not (parent / candidate).exists():
            return candidate
        candidate = f"{stem} (copy {counter}){suffix}"
        counter += 1


def _validate_new_name(name: str) -> bool:
    """Reject empty names, path separators and traversal attempts."""
    if not name or name.strip() != name or name in {".", ".."}:
        return False
    separators = {os.sep}
    if os.altsep:
        separators.add(os.altsep)
    return not any(sep in name for sep in separators)


class ConflictResolver:
    """Remembers "apply to all" decisions for the current operation."""

    def __init__(self):
        self._memory: dict[str, ConflictAnswer] = {}

    def remembered(self, conflict: Conflict) -> ConflictAnswer | None:
        return self._memory.get(conflict.kind)

    def remember(self, conflict: Conflict, answer: ConflictAnswer):
        # CANCEL is never remembered as an automatic decision.
        if answer.resolution is Resolution.CANCEL:
            return
        self._memory[conflict.kind] = answer

    def clear(self):
        self._memory.clear()


__all__ = [
    "Resolution",
    "Conflict",
    "ConflictAnswer",
    "ConflictResolver",
    "files_identical",
    "source_is_newer",
    "suggest_free_name",
    "_validate_new_name",
]
