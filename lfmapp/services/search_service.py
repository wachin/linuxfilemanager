import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from PyQt6.QtCore import QThread, pyqtSignal


@dataclass(frozen=True)
class SearchFilters:
    """Optional filters for file searches."""

    file_type: str = "any"
    min_size: int | None = None
    max_size: int | None = None
    modified_after: float | None = None
    modified_before: float | None = None

    IMAGE_EXTENSIONS: ClassVar[set[str]] = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico"}
    DOCUMENT_EXTENSIONS: ClassVar[set[str]] = {
        ".txt", ".md", ".pdf", ".doc", ".docx", ".odt", ".rtf", ".csv", ".xls", ".xlsx", ".ods"
    }
    AUDIO_EXTENSIONS: ClassVar[set[str]] = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"}
    VIDEO_EXTENSIONS: ClassVar[set[str]] = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".mpeg", ".mpg"}
    ARCHIVE_EXTENSIONS: ClassVar[set[str]] = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".deb"}

    def is_active(self) -> bool:
        return (
            self.file_type != "any"
            or self.min_size is not None
            or self.max_size is not None
            or self.modified_after is not None
            or self.modified_before is not None
        )

    def to_dict(self) -> dict:
        return {
            "file_type": self.file_type,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "modified_after": self.modified_after,
            "modified_before": self.modified_before,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "SearchFilters":
        if not data:
            return cls()
        return cls(
            file_type=data.get("file_type", "any"),
            min_size=data.get("min_size"),
            max_size=data.get("max_size"),
            modified_after=data.get("modified_after"),
            modified_before=data.get("modified_before"),
        )

    def matches(self, path: Path) -> bool:
        try:
            st = path.stat()
        except OSError:
            return False

        if not self._matches_type(path):
            return False

        if path.is_file():
            size = st.st_size
            if self.min_size is not None and size < self.min_size:
                return False
            if self.max_size is not None and size > self.max_size:
                return False
        elif self.min_size is not None or self.max_size is not None:
            return False

        if self.modified_after is not None and st.st_mtime < self.modified_after:
            return False
        if self.modified_before is not None and st.st_mtime > self.modified_before:
            return False

        return True

    def _matches_type(self, path: Path) -> bool:
        file_type = self.file_type
        if file_type == "any":
            return True
        if file_type == "file":
            return path.is_file()
        if file_type == "folder":
            return path.is_dir()

        if not path.is_file():
            return False
        suffix = path.suffix.lower()
        extension_map = {
            "image": self.IMAGE_EXTENSIONS,
            "document": self.DOCUMENT_EXTENSIONS,
            "audio": self.AUDIO_EXTENSIONS,
            "video": self.VIDEO_EXTENSIONS,
            "archive": self.ARCHIVE_EXTENSIONS,
        }
        return suffix in extension_map.get(file_type, set())


@dataclass(frozen=True)
class SearchQuery:
    """Serializable search request (ROADMAP Phase 5.1).

    Separates the query text from its mode (name vs content) and scope
    (current folder vs recursive), plus the optional filters. Serialisable so
    it can be stored, re-executed and passed to a service.
    """

    query: str = ""
    mode: str = "name"          # "name" | "content"
    recursive: bool = False
    filters: SearchFilters = field(default_factory=SearchFilters)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "mode": self.mode,
            "recursive": self.recursive,
            "filters": self.filters.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "SearchQuery":
        if not data:
            return cls()
        return cls(
            query=str(data.get("query", "")),
            mode=data.get("mode", "name"),
            recursive=bool(data.get("recursive", False)),
            filters=SearchFilters.from_dict(data.get("filters")),
        )


class SearchThread(QThread):
    found = pyqtSignal(Path)
    batch = pyqtSignal(list)      # progressive results in small batches
    finished = pyqtSignal(int)

    NAME_MODE = "name"
    CONTENT_MODE = "content"

    def __init__(
        self,
        root: Path,
        query: str,
        recursive: bool = False,
        filters: SearchFilters | None = None,
        mode: str = "name",
        batch_size: int = 50,
    ):
        super().__init__()
        self.root = root
        self.query = query.lower()
        self.recursive = recursive
        self.filters = filters or SearchFilters()
        self.mode = mode
        self.batch_size = max(1, batch_size)
        self._running = True

    def run(self):
        count = 0
        pending: list[Path] = []

        def emit(path: Path):
            nonlocal count, pending
            count += 1
            pending.append(path)
            if len(pending) >= self.batch_size:
                self.batch.emit(list(pending))
                pending = []

        if self.recursive:
            for current_root, dirs, files in os.walk(self.root):
                if not self._running:
                    break
                for name in dirs + files:
                    if not self._running:
                        break
                    path = Path(current_root) / name
                    if self._matches(path):
                        self.found.emit(path)
                        emit(path)
        else:
            try:
                for entry in Path(self.root).iterdir():
                    if not self._running:
                        break
                    if self._matches(entry):
                        self.found.emit(entry)
                        emit(entry)
            except PermissionError:
                pass
        if pending:
            self.batch.emit(pending)
        self.finished.emit(count)

    def _matches(self, path: Path) -> bool:
        if not self.filters.matches(path):
            return False
        if self.mode == self.CONTENT_MODE:
            if not path.is_file():
                return False
            return self.query in self._file_text(path)
        return self.query in path.name.lower()

    def _file_text(self, path: Path) -> str:
        """Read a small text preview of a file for content search.

        Uses a size cap and encoding fallback so a binary/huge file never
        blocks the search.
        """
        try:
            size = path.stat().st_size
        except OSError:
            return ""
        if size == 0 or size > 2 * 1024 * 1024:
            return ""
        try:
            data = path.read_bytes()
        except OSError:
            return ""
        for encoding in ("utf-8", "latin-1"):
            try:
                return data.decode(encoding).lower()
            except UnicodeDecodeError:
                continue
        return ""

    def stop(self):
        self._running = False
