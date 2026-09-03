"""Undo/redo operation history for reversible file actions."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lfmapp.services.trash_service import TRASH_FILES_DIR, TRASH_INFO_DIR, send_to_trash


class ReversibleOperation(Protocol):
    """Protocol for file operations that can be undone and redone."""

    label: str

    def undo(self) -> None:
        """Undo the operation."""

    def redo(self) -> None:
        """Redo the operation."""


@dataclass(frozen=True)
class RenameOperation:
    """A reversible file or folder rename."""

    original_path: Path
    renamed_path: Path

    @property
    def label(self) -> str:
        return f"Rename {self.original_path.name} to {self.renamed_path.name}"

    def undo(self) -> None:
        if not self.renamed_path.exists():
            raise FileNotFoundError(f"Cannot undo rename; missing: {self.renamed_path}")
        if self.original_path.exists():
            raise FileExistsError(f"Cannot undo rename; target exists: {self.original_path}")
        self.renamed_path.rename(self.original_path)

    def redo(self) -> None:
        if not self.original_path.exists():
            raise FileNotFoundError(f"Cannot redo rename; missing: {self.original_path}")
        if self.renamed_path.exists():
            raise FileExistsError(f"Cannot redo rename; target exists: {self.renamed_path}")
        self.original_path.rename(self.renamed_path)


@dataclass(frozen=True)
class CreateOperation:
    """A reversible creation of an empty file or empty folder."""

    path: Path
    item_type: str

    def __post_init__(self):
        if self.item_type not in {"file", "folder"}:
            raise ValueError("item_type must be 'file' or 'folder'")

    @property
    def label(self) -> str:
        item_name = "folder" if self.item_type == "folder" else "file"
        return f"Create {item_name} {self.path.name}"

    def undo(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"Cannot undo creation; missing: {self.path}")
        if self.item_type == "folder":
            if not self.path.is_dir():
                raise NotADirectoryError(f"Cannot undo folder creation; not a folder: {self.path}")
            try:
                self.path.rmdir()
            except OSError as exc:
                raise OSError(f"Cannot undo folder creation; folder is not empty: {self.path}") from exc
            return

        if not self.path.is_file():
            raise IsADirectoryError(f"Cannot undo file creation; not a file: {self.path}")
        if self.path.stat().st_size != 0:
            raise OSError(f"Cannot undo file creation; file is not empty: {self.path}")
        self.path.unlink()

    def redo(self) -> None:
        if self.path.exists():
            raise FileExistsError(f"Cannot redo creation; target exists: {self.path}")
        if self.item_type == "folder":
            self.path.mkdir()
        else:
            self.path.touch()


@dataclass(frozen=True)
class MoveOperation:
    """A reversible file or folder move."""

    original_path: Path
    moved_path: Path

    @property
    def label(self) -> str:
        return f"Move {self.original_path.name}"

    def undo(self) -> None:
        if not self.moved_path.exists():
            raise FileNotFoundError(f"Cannot undo move; missing: {self.moved_path}")
        if self.original_path.exists():
            raise FileExistsError(f"Cannot undo move; target exists: {self.original_path}")
        if not self.original_path.parent.exists():
            raise FileNotFoundError(f"Cannot undo move; parent missing: {self.original_path.parent}")
        shutil.move(str(self.moved_path), str(self.original_path))

    def redo(self) -> None:
        if not self.original_path.exists():
            raise FileNotFoundError(f"Cannot redo move; missing: {self.original_path}")
        if self.moved_path.exists():
            raise FileExistsError(f"Cannot redo move; target exists: {self.moved_path}")
        if not self.moved_path.parent.exists():
            raise FileNotFoundError(f"Cannot redo move; parent missing: {self.moved_path.parent}")
        shutil.move(str(self.original_path), str(self.moved_path))


@dataclass
class CopyOperation:
    """A reversible copy of a file or folder."""

    source_path: Path
    copied_path: Path
    expected_size: int
    expected_mtime_ns: int
    is_directory: bool = False
    expected_entries: tuple[tuple[str, str, int, int], ...] = ()

    @classmethod
    def from_completed_copy(cls, source_path: Path, copied_path: Path) -> "CopyOperation":
        if copied_path.is_dir():
            stat = copied_path.stat()
            return cls(
                source_path,
                copied_path,
                0,
                stat.st_mtime_ns,
                True,
                cls._directory_manifest(copied_path),
            )
        if not copied_path.is_file():
            raise FileNotFoundError(f"Copied path is not a file or folder: {copied_path}")
        stat = copied_path.stat()
        return cls(source_path, copied_path, stat.st_size, stat.st_mtime_ns)

    @staticmethod
    def _directory_manifest(path: Path) -> tuple[tuple[str, str, int, int], ...]:
        entries = []
        for item in sorted(path.rglob("*")):
            relative = item.relative_to(path).as_posix()
            if item.is_dir():
                entries.append((relative, "dir", 0, item.stat().st_mtime_ns))
            elif item.is_file():
                stat = item.stat()
                entries.append((relative, "file", stat.st_size, stat.st_mtime_ns))
            else:
                entries.append((relative, "other", 0, item.stat().st_mtime_ns))
        return tuple(entries)

    @property
    def label(self) -> str:
        return f"Copy {self.copied_path.name}"

    def undo(self) -> None:
        if not self.copied_path.exists():
            raise FileNotFoundError(f"Cannot undo copy; missing: {self.copied_path}")
        if self.is_directory:
            if not self.copied_path.is_dir():
                raise NotADirectoryError(f"Cannot undo copy; not a folder: {self.copied_path}")
            if self._directory_manifest(self.copied_path) != self.expected_entries:
                raise OSError(f"Cannot undo copy; copied folder changed: {self.copied_path}")
            shutil.rmtree(str(self.copied_path))
            return
        if not self.copied_path.is_file():
            raise IsADirectoryError(f"Cannot undo copy; not a file: {self.copied_path}")
        stat = self.copied_path.stat()
        if stat.st_size != self.expected_size or stat.st_mtime_ns != self.expected_mtime_ns:
            raise OSError(f"Cannot undo copy; copied file changed: {self.copied_path}")
        self.copied_path.unlink()

    def redo(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(f"Cannot redo copy; missing: {self.source_path}")
        if self.copied_path.exists():
            raise FileExistsError(f"Cannot redo copy; target exists: {self.copied_path}")
        if not self.copied_path.parent.exists():
            raise FileNotFoundError(f"Cannot redo copy; parent missing: {self.copied_path.parent}")
        if self.is_directory:
            if not self.source_path.is_dir():
                raise NotADirectoryError(f"Cannot redo copy; source is not a folder: {self.source_path}")
            shutil.copytree(str(self.source_path), str(self.copied_path))
            stat = self.copied_path.stat()
            self.expected_size = 0
            self.expected_mtime_ns = stat.st_mtime_ns
            self.expected_entries = self._directory_manifest(self.copied_path)
        else:
            if not self.source_path.is_file():
                raise FileNotFoundError(f"Cannot redo copy; source is not a file: {self.source_path}")
            shutil.copy2(str(self.source_path), str(self.copied_path))
            stat = self.copied_path.stat()
            self.expected_size = stat.st_size
            self.expected_mtime_ns = stat.st_mtime_ns


@dataclass
class TrashOperation:
    """A reversible move to the FreeDesktop trash."""

    original_path: Path
    trashed_path: Path
    trashinfo_path: Path

    @property
    def label(self) -> str:
        return f"Move {self.original_path.name} to Trash"

    def undo(self) -> None:
        if not self.trashed_path.exists():
            raise FileNotFoundError(f"Cannot undo trash; missing: {self.trashed_path}")
        if self.original_path.exists():
            raise FileExistsError(f"Cannot undo trash; target exists: {self.original_path}")
        if not self.original_path.parent.exists():
            raise FileNotFoundError(f"Cannot undo trash; parent missing: {self.original_path.parent}")
        shutil.move(str(self.trashed_path), str(self.original_path))
        if self.trashinfo_path.exists():
            self.trashinfo_path.unlink()

    def redo(self) -> None:
        if not self.original_path.exists():
            raise FileNotFoundError(f"Cannot redo trash; missing: {self.original_path}")
        trash_name = send_to_trash(self.original_path)
        self.trashed_path = TRASH_FILES_DIR / trash_name
        self.trashinfo_path = TRASH_INFO_DIR / f"{trash_name}.trashinfo"


@dataclass(frozen=True)
class CompositeOperation:
    """A reversible group of operations treated as one undo/redo entry."""

    label_text: str
    operations: tuple[ReversibleOperation, ...]

    def __post_init__(self):
        if not self.operations:
            raise ValueError("CompositeOperation requires at least one operation")

    @classmethod
    def from_operations(
        cls,
        label: str,
        operations: list[ReversibleOperation],
    ) -> "CompositeOperation":
        return cls(label, tuple(operations))

    @property
    def label(self) -> str:
        return self.label_text

    def undo(self) -> None:
        for operation in reversed(self.operations):
            operation.undo()

    def redo(self) -> None:
        for operation in self.operations:
            operation.redo()


class OperationHistory:
    """In-memory undo/redo stack for reversible operations."""

    def __init__(self):
        self._undo_stack: list[ReversibleOperation] = []
        self._redo_stack: list[ReversibleOperation] = []

    def push(self, operation: ReversibleOperation) -> None:
        """Record a completed operation and clear redo history."""
        if self._undo_stack and self._undo_stack[-1] == operation:
            return
        self._undo_stack.append(operation)
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo_label(self) -> str:
        if not self._undo_stack:
            return "Undo"
        return f"Undo {self._undo_stack[-1].label}"

    def redo_label(self) -> str:
        if not self._redo_stack:
            return "Redo"
        return f"Redo {self._redo_stack[-1].label}"

    def next_undo_operation_label(self) -> str | None:
        """Return the next undo operation label without UI action text."""
        if not self._undo_stack:
            return None
        return self._undo_stack[-1].label

    def next_redo_operation_label(self) -> str | None:
        """Return the next redo operation label without UI action text."""
        if not self._redo_stack:
            return None
        return self._redo_stack[-1].label

    def undo(self) -> ReversibleOperation:
        if not self._undo_stack:
            raise IndexError("No operation to undo")
        operation = self._undo_stack.pop()
        operation.undo()
        self._redo_stack.append(operation)
        return operation

    def redo(self) -> ReversibleOperation:
        if not self._redo_stack:
            raise IndexError("No operation to redo")
        operation = self._redo_stack.pop()
        operation.redo()
        self._undo_stack.append(operation)
        return operation
