"""Selection state controller.

Owns derived selection facts that MainWindow currently recomputes inline
(status bar summary, contextual toolbar decisions).  Keeping them here makes
the rules testable without a QMainWindow and gives every surface one answer
for "how many files / how many folders / total size is selected".

It also provides the pure **select-by-criteria** helper behind the "Select
By…" action (Phase 6.1): a name glob, an extension set, a type group, a size
window and a modification-date window, reusing the same matching language as
search (`services.search_service.SearchFilters`) so the UI stays consistent.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from lfmapp.services.search_service import SearchFilters


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


@dataclass(frozen=True)
class SelectionCriteria:
    """Criteria for a "select by" operation. Blank/None means "don't filter"."""

    name_glob: str = ""               # fnmatch against the file name
    extensions: tuple[str, ...] = ()  # lowercase suffixes, e.g. (".jpg", ".png")
    file_type: str = "any"            # any/file/folder/image/document/audio/video/archive
    min_size: int | None = None
    max_size: int | None = None
    modified_after: float | None = None   # epoch seconds
    modified_before: float | None = None
    case_sensitive: bool = False

    def is_active(self) -> bool:
        return bool(
            self.name_glob
            or self.extensions
            or self.file_type != "any"
            or self.min_size is not None
            or self.max_size is not None
            or self.modified_after is not None
            or self.modified_before is not None
        )

    def matches(self, path: Path) -> bool:
        if self.name_glob:
            name, pattern = path.name, self.name_glob
            ok = (
                fnmatch.fnmatchcase(name, pattern)
                if self.case_sensitive
                else fnmatch.fnmatch(name.lower(), pattern.lower())
            )
            if not ok:
                return False
        if self.extensions:
            if path.suffix.lower() not in {e.lower() for e in self.extensions}:
                return False
        if (
            self.file_type != "any"
            or self.min_size is not None
            or self.max_size is not None
            or self.modified_after is not None
            or self.modified_before is not None
        ):
            filters = SearchFilters(
                file_type=self.file_type,
                min_size=self.min_size,
                max_size=self.max_size,
                modified_after=self.modified_after,
                modified_before=self.modified_before,
            )
            if not filters.matches(path):
                return False
        return True


class SelectionController:
    """Pure helpers to derive selection facts and build selections."""

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

    @staticmethod
    def select_by(paths: list[Path], criteria: SelectionCriteria) -> list[Path]:
        """Return the subset of *paths* satisfying *criteria*.

        An inactive (empty) criteria returns nothing on purpose — the caller
        decides what "select by nothing" means (usually select-all), rather
        than silently grabbing everything.
        """
        if not criteria.is_active():
            return []
        return [Path(p) for p in paths if criteria.matches(Path(p))]
