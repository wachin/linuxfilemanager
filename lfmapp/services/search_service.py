import os
from dataclasses import dataclass
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


class SearchThread(QThread):
    found = pyqtSignal(Path)
    finished = pyqtSignal(int)

    def __init__(self, root: Path, query: str, recursive: bool = False, filters: SearchFilters | None = None):
        super().__init__()
        self.root = root
        self.query = query.lower()
        self.recursive = recursive
        self.filters = filters or SearchFilters()
        self._running = True

    def run(self):
        count = 0
        if self.recursive:
            for current_root, dirs, files in os.walk(self.root):
                if not self._running:
                    break
                for name in dirs + files:
                    path = Path(current_root) / name
                    if self._matches(path):
                        self.found.emit(path)
                        count += 1
        else:
            try:
                for entry in Path(self.root).iterdir():
                    if not self._running:
                        break
                    if self._matches(entry):
                        self.found.emit(entry)
                        count += 1
            except PermissionError:
                pass
        self.finished.emit(count)

    def _matches(self, path: Path) -> bool:
        return self.query in path.name.lower() and self.filters.matches(path)

    def stop(self):
        self._running = False
