"""Two-phase folder synchronization service.

Phase 1 — **compare**: Walk two directories, compute which files would be
copied, moved, or deleted according to the chosen rules.  Returns a list of
`SyncAction` items.

Phase 2 — **apply**: Execute the confirmed actions through the normal
copy/move/delete workers (or the operation queue).

The comparison is deliberately implemented in pure Python (no rsync
dependency) so that the logic is testable without external tools.  The
`rsync` backend is a future refinement behind the same interface.

Two comparison modes are supported:

- **Unidirectional** (source → destination): files newer in *source* are
  copied forward; files only in *destination* are optionally deleted.
- **Bidirectional** (newest wins): each file is copied toward the side
  holding the newest version.

Update criteria (from coarsest to finest):

- ``name`` — files with the same name are treated as the same file.
- ``size`` — same name *and* same size = up to date.
- ``mtime`` — same name *and* same modification time = up to date.
- ``mtime_size`` — same name *and* same mtime *and* same size = up to date.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator

from PyQt6.QtCore import QThread, pyqtSignal


# ---------------------------------------------------------------------------
# Enums and data classes
# ---------------------------------------------------------------------------

class SyncMode(Enum):
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"


class UpdateCriterion(Enum):
    NAME = "name"
    SIZE = "size"
    MTIME = "mtime"
    MTIME_SIZE = "mtime_size"


class SyncActionType(Enum):
    COPY = "copy"
    MOVE = "move"
    DELETE = "delete"
    CONFLICT = "conflict"
    NOTHING = "nothing"


@dataclass
class SyncAction:
    """A single planned action in the synchronization plan."""

    action: SyncActionType
    source: Path
    destination: Path
    source_mtime: float = 0.0
    dest_mtime: float = 0.0
    source_size: int = 0
    dest_size: int = 0
    reason: str = ""

    @property
    def size(self) -> int:
        return self.source_size if self.action == SyncActionType.COPY else 0


@dataclass
class SyncPlan:
    """The result of a comparison: a list of planned actions."""

    actions: list[SyncAction] = field(default_factory=list)
    source: Path = field(default_factory=lambda: Path("/"))
    destination: Path = field(default_factory=lambda: Path("/"))
    mode: SyncMode = SyncMode.UNIDIRECTIONAL
    criterion: UpdateCriterion = UpdateCriterion.MTIME_SIZE

    @property
    def to_copy(self) -> list[SyncAction]:
        return [a for a in self.actions if a.action == SyncActionType.COPY]

    @property
    def to_delete(self) -> list[SyncAction]:
        return [a for a in self.actions if a.action == SyncActionType.DELETE]

    @property
    def conflicts(self) -> list[SyncAction]:
        return [a for a in self.actions if a.action == SyncActionType.CONFLICT]

    @property
    def total_size(self) -> int:
        return sum(a.size for a in self.actions)


# ---------------------------------------------------------------------------
# Pure comparison helpers
# ---------------------------------------------------------------------------

def _walk_files(root: Path) -> dict[str, os.stat_result]:
    """Return ``{relative_path: stat_result}`` for all files under *root*."""
    result: dict[str, os.stat_result] = {}
    if not root.is_dir():
        return result
    for dirpath, _dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        for name in filenames:
            full = Path(dirpath) / name
            rel = name if rel_dir == "." else os.path.join(rel_dir, name)
            try:
                st = os.lstat(full)
                import stat as _stat
                if not _stat.S_ISREG(st.st_mode):
                    continue
                result[rel] = st
            except (OSError, PermissionError):
                continue
    return result


def _is_up_to_date(
    src_stat: os.stat_result,
    dst_stat: os.stat_result | None,
    criterion: UpdateCriterion,
    time_tolerance: float = 3600.0,
) -> bool:
    """Return *True* if *dst_stat* is current relative to *src_stat*.

    *time_tolerance* (seconds): differences smaller than this are ignored
    (handles seasonal clock changes and filesystem time-resolution
    differences).
    """
    if dst_stat is None:
        return False
    if criterion == UpdateCriterion.NAME:
        return True
    if criterion == UpdateCriterion.SIZE:
        return src_stat.st_size == dst_stat.st_size
    if criterion == UpdateCriterion.MTIME:
        return abs(src_stat.st_mtime - dst_stat.st_mtime) < time_tolerance
    # mtime_size
    return (
        abs(src_stat.st_mtime - dst_stat.st_mtime) < time_tolerance
        and src_stat.st_size == dst_stat.st_size
    )


def compare_folders(
    source: Path,
    destination: Path,
    *,
    mode: SyncMode = SyncMode.UNIDIRECTIONAL,
    criterion: UpdateCriterion = UpdateCriterion.MTIME_SIZE,
    delete_orphans: bool = False,
    time_tolerance: float = 3600.0,
) -> SyncPlan:
    """Compare *source* and *destination* and return a `SyncPlan`.

    Parameters
    ----------
    source, destination:
        The two folders to compare.
    mode:
        ``UNIDIRECTIONAL``: source is authoritative, destination is updated.
        ``BIDIRECTIONAL``: newest version wins.
    criterion:
        What to compare (see `UpdateCriterion`).
    delete_orphans:
        If *True*, files only in *destination* are marked for deletion in
        unidirectional mode.
    time_tolerance:
        Seconds of tolerance when comparing mtimes (default 1 hour).
    """
    src_files = _walk_files(source)
    dst_files = _walk_files(destination)
    all_names = sorted(set(src_files) | set(dst_files))

    actions: list[SyncAction] = []

    for rel in all_names:
        src_stat = src_files.get(rel)
        dst_stat = dst_files.get(rel)
        src_path = source / rel
        dst_path = destination / rel

        if src_stat and dst_stat:
            # File exists on both sides.
            if _is_up_to_date(src_stat, dst_stat, criterion, time_tolerance):
                actions.append(SyncAction(
                    action=SyncActionType.NOTHING,
                    source=src_path,
                    destination=dst_path,
                    source_mtime=src_stat.st_mtime,
                    dest_mtime=dst_stat.st_mtime,
                    source_size=src_stat.st_size,
                    dest_size=dst_stat.st_size,
                    reason="Up to date",
                ))
            elif mode == SyncMode.BIDIRECTIONAL:
                if src_stat.st_mtime > dst_stat.st_mtime:
                    actions.append(SyncAction(
                        action=SyncActionType.COPY,
                        source=src_path,
                        destination=dst_path,
                        source_mtime=src_stat.st_mtime,
                        dest_mtime=dst_stat.st_mtime,
                        source_size=src_stat.st_size,
                        dest_size=dst_stat.st_size,
                        reason="Source is newer",
                    ))
                elif dst_stat.st_mtime > src_stat.st_mtime:
                    actions.append(SyncAction(
                        action=SyncActionType.COPY,
                        source=dst_path,
                        destination=src_path,
                        source_mtime=dst_stat.st_mtime,
                        dest_mtime=src_stat.st_mtime,
                        source_size=dst_stat.st_size,
                        dest_size=src_stat.st_size,
                        reason="Destination is newer",
                    ))
                else:
                    actions.append(SyncAction(
                        action=SyncActionType.NOTHING,
                        source=src_path,
                        destination=dst_path,
                        reason="Same mtime, different content (conflict)",
                    ))
            else:
                # Unidirectional: source is authoritative.
                actions.append(SyncAction(
                    action=SyncActionType.COPY,
                    source=src_path,
                    destination=dst_path,
                    source_mtime=src_stat.st_mtime,
                    dest_mtime=dst_stat.st_mtime,
                    source_size=src_stat.st_size,
                    dest_size=dst_stat.st_size,
                    reason="Source differs",
                ))

        elif src_stat and not dst_stat:
            # Only in source → copy to destination.
            actions.append(SyncAction(
                action=SyncActionType.COPY,
                source=src_path,
                destination=dst_path,
                source_mtime=src_stat.st_mtime,
                source_size=src_stat.st_size,
                reason="New in source",
            ))

        elif dst_stat and not src_stat:
            # Only in destination.
            if mode == SyncMode.BIDIRECTIONAL:
                actions.append(SyncAction(
                    action=SyncActionType.COPY,
                    source=dst_path,
                    destination=src_path,
                    source_mtime=dst_stat.st_mtime,
                    source_size=dst_stat.st_size,
                    reason="New in destination",
                ))
            elif delete_orphans:
                actions.append(SyncAction(
                    action=SyncActionType.DELETE,
                    source=dst_path,
                    destination=dst_path,
                    source_mtime=dst_stat.st_mtime,
                    source_size=dst_stat.st_size,
                    reason="Orphan in destination",
                ))
            else:
                actions.append(SyncAction(
                    action=SyncActionType.NOTHING,
                    source=src_path,
                    destination=dst_path,
                    reason="Only in destination (kept)",
                ))

    return SyncPlan(
        actions=actions,
        source=source,
        destination=destination,
        mode=mode,
        criterion=criterion,
    )


# ---------------------------------------------------------------------------
# QThread worker for the comparison phase (large folders)
# ---------------------------------------------------------------------------

class SyncCompareWorker(QThread):
    """Run `compare_folders` in a background thread.

    Signals
    -------
    progress(path: str)
        Emitted for each file being compared.
    plan_ready(plan)
        Emitted once with the complete `SyncPlan`.
    """

    progress = pyqtSignal(str)
    plan_ready = pyqtSignal(object)  # SyncPlan

    def __init__(
        self,
        source: Path,
        destination: Path,
        *,
        mode: SyncMode = SyncMode.UNIDIRECTIONAL,
        criterion: UpdateCriterion = UpdateCriterion.MTIME_SIZE,
        delete_orphans: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._source = source
        self._destination = destination
        self._mode = mode
        self._criterion = criterion
        self._delete_orphans = delete_orphans
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        plan = compare_folders(
            self._source,
            self._destination,
            mode=self._mode,
            criterion=self._criterion,
            delete_orphans=self._delete_orphans,
        )
        if self._running:
            self.plan_ready.emit(plan)


# ---------------------------------------------------------------------------
# Apply phase helpers
# ---------------------------------------------------------------------------

def apply_plan(
    plan: SyncPlan,
    actions: list[SyncAction] | None = None,
) -> list[tuple[Path, Path, SyncActionType]]:
    """Execute the confirmed actions.

    Returns a list of ``(source, destination, action_type)`` tuples describing
    what was done.  The caller is responsible for actually calling the
    copy/move/delete workers — this function simply filters and orders the
    actions.

    Deletions are applied **after** copies to avoid data loss.
    """
    to_apply = actions or plan.actions
    # Sort: copies first, then deletes.
    copies = [a for a in to_apply if a.action in (SyncActionType.COPY, SyncActionType.MOVE)]
    deletes = [a for a in to_apply if a.action == SyncActionType.DELETE]
    results: list[tuple[Path, Path, SyncActionType]] = []
    for a in copies:
        results.append((a.source, a.destination, a.action))
    for a in deletes:
        results.append((a.source, a.destination, a.action))
    return results
