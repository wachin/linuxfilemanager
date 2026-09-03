"""Selection state controller.

Owns derived selection facts that MainWindow currently recomputes inline
(status bar summary, contextual toolbar decisions).  Keeping them here makes
the rules testable without a QMainWindow and gives every surface one answer
for "how many files / how many folders / total size is selected".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SelectionSummary:
    """Aggregated facts about a set of selected paths."""

    files: list[Path] = field(default_factory=list)
    folders: list[Path] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.files) + len(self.folders)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def folder_count(self) -> int:
        return len(self.folders)

    def total_file_size(self, *, include_folders: bool = False) -> int:
        """Sum of file sizes.

        Folder sizes are only included when include_folders is True, and then
        only as their immediate stat size (dirs usually report a small block
        size); recursive folder sizing belongs to the folder-sizes feature.
        OSError during stat is ignored so a vanished file does not blow up.
        """
        total = 0
        for path in self.files:
            try:
                if path.is_file():
                    total += path.stat().st_size
            except OSError:
                pass
        if include_folders:
            for path in self.folders:
                try:
                    total += path.stat().st_size
                except OSError:
                    pass
        return total

    def is_empty(self) -> bool:
        return self.count == 0

    def has_files(self) -> bool:
        return bool(self.files)

    def has_folders(self) -> bool:
        return bool(self.folders)


class SelectionController:
    """Pure helpers to derive selection facts from a path list."""

    @staticmethod
    def summarize(paths: list[Path]) -> SelectionSummary:
        """Split a list of paths into files and folders.

        Non-existent entries are skipped silently (selection can lag the file
        system right after a rename or delete).
        """
        files: list[Path] = []
        folders: list[Path] = []
        for raw in paths:
            path = Path(raw)
            if not path.exists():
                continue
            if path.is_dir():
                folders.append(path)
            else:
                files.append(path)
        return SelectionSummary(files=files, folders=folders)

    @staticmethod
    def total_file_size_of(paths: list[Path]) -> int:
        """Convenience one-liner used before the summary exists."""
        return SelectionController.summarize(paths).total_file_size()
