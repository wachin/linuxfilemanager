"""Custom file system model for linux-file-manager.

Extends QFileSystemModel with additional functionality:
- Human-readable file sizes
- File type descriptions
- Tag display support
"""

from pathlib import Path

from PyQt6.QtCore import QDir, QFileInfo, Qt
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QFileIconProvider


class FileSystemModel(QFileSystemModel):
    """Extended file system model with improved display."""

    def __init__(self, parent=None, root_path: Path | str | None = None):
        super().__init__(parent)
        self.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.Hidden)
        self.setIconProvider(self._optimized_icon_provider())
        self.setRootPath(str(root_path or Path.home()))
        self._show_extensions = True
        self._show_selection_checkboxes = False
        self._checked_paths: set[str] = set()

    @staticmethod
    def _optimized_icon_provider() -> QFileIconProvider:
        """Return an icon provider that avoids expensive per-directory icon lookups."""
        provider = QFileIconProvider()
        provider.setOptions(QFileIconProvider.Option.DontUseCustomDirectoryIcons)
        return provider

    @property
    def show_extensions(self) -> bool:
        return self._show_extensions

    @show_extensions.setter
    def show_extensions(self, value: bool):
        self._show_extensions = value

    @property
    def show_selection_checkboxes(self) -> bool:
        return self._show_selection_checkboxes

    @show_selection_checkboxes.setter
    def show_selection_checkboxes(self, value: bool):
        self._show_selection_checkboxes = bool(value)

    def checked_paths(self) -> list[Path]:
        """Return paths checked through optional selection checkboxes."""
        return [Path(path) for path in sorted(self._checked_paths)]

    def clear_checked_paths(self):
        """Clear all checkbox selections."""
        self._checked_paths.clear()
        self.layoutChanged.emit()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Override data to provide human-readable sizes and type info."""
        if not index.isValid():
            return super().data(index, role)

        if (
            role == Qt.ItemDataRole.CheckStateRole
            and self._show_selection_checkboxes
            and index.column() == 0
        ):
            path = self.filePath(index)
            if path in self._checked_paths:
                return Qt.CheckState.Checked
            return Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.DisplayRole:
            column = index.column()

            # Column 0: Name - optionally hide extensions
            if column == 0 and not self._show_extensions:
                file_info = self.fileInfo(index)
                if file_info.isFile():
                    name = file_info.fileName()
                    dot_pos = name.rfind(".")
                    if dot_pos > 0:
                        return name[:dot_pos]

            # Column 1: Size - show human-readable format
            if column == 1:
                file_info = self.fileInfo(index)
                if file_info.isDir():
                    return ""
                size = file_info.size()
                return self._human_readable_size(size)

            # Column 2: Type - show file type description
            if column == 2:
                file_info = self.fileInfo(index)
                return self._file_type_description(file_info)

            # Column 3: Date - show formatted date
            if column == 3:
                file_info = self.fileInfo(index)
                return file_info.lastModified().toString("yyyy-MM-dd HH:mm")

        elif role == Qt.ItemDataRole.ToolTipRole:
            file_info = self.fileInfo(index)
            if file_info.isFile():
                size = self._human_readable_size(file_info.size())
                return f"{file_info.fileName()}\n{size}\n{file_info.absoluteFilePath()}"

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            column = index.column()
            if column == 1:  # Size column right-aligned
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        return super().data(index, role)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if (
            role == Qt.ItemDataRole.CheckStateRole
            and self._show_selection_checkboxes
            and index.isValid()
            and index.column() == 0
        ):
            path = self.filePath(index)
            if value == Qt.CheckState.Checked or value == Qt.CheckState.Checked.value:
                self._checked_paths.add(path)
            else:
                self._checked_paths.discard(path)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return super().setData(index, value, role)

    def flags(self, index):
        flags = super().flags(index)
        if self._show_selection_checkboxes and index.isValid() and index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    @staticmethod
    def _human_readable_size(size: int) -> str:
        """Convert bytes to human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                if unit == "B":
                    return f"{size} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    @staticmethod
    def _file_type_description(file_info: QFileInfo) -> str:
        """Return a human-readable file type description."""
        if file_info.isDir():
            return "Folder"

        suffix = file_info.suffix().lower()
        type_map = {
            # Documents
            "txt": "Text file",
            "md": "Markdown document",
            "pdf": "PDF document",
            "doc": "Word document",
            "docx": "Word document",
            "odt": "OpenDocument text",
            "rtf": "Rich text file",
            # Spreadsheets
            "xls": "Excel spreadsheet",
            "xlsx": "Excel spreadsheet",
            "ods": "OpenDocument spreadsheet",
            "csv": "CSV file",
            # Presentations
            "ppt": "PowerPoint presentation",
            "pptx": "PowerPoint presentation",
            "odp": "OpenDocument presentation",
            # Images
            "png": "PNG image",
            "jpg": "JPEG image",
            "jpeg": "JPEG image",
            "gif": "GIF image",
            "bmp": "Bitmap image",
            "svg": "SVG image",
            "webp": "WebP image",
            "ico": "Icon file",
            # Audio
            "mp3": "MP3 audio",
            "wav": "WAV audio",
            "ogg": "OGG audio",
            "flac": "FLAC audio",
            "aac": "AAC audio",
            # Video
            "mp4": "MP4 video",
            "avi": "AVI video",
            "mkv": "Matroska video",
            "mov": "QuickTime video",
            "webm": "WebM video",
            # Archives
            "zip": "ZIP archive",
            "tar": "TAR archive",
            "gz": "GZip archive",
            "bz2": "BZip2 archive",
            "xz": "XZ archive",
            "7z": "7-Zip archive",
            "rar": "RAR archive",
            "deb": "Debian package",
            # Code
            "py": "Python script",
            "sh": "Shell script",
            "js": "JavaScript file",
            "html": "HTML file",
            "css": "CSS stylesheet",
            "json": "JSON file",
            "xml": "XML file",
            "yaml": "YAML file",
            "yml": "YAML file",
            "toml": "TOML file",
            "ini": "INI configuration",
            "cfg": "Configuration file",
            # Executables
            "exe": "Windows executable",
            "appimage": "AppImage",
            "desktop": "Desktop entry",
        }

        return type_map.get(suffix, f"{suffix.upper()} file" if suffix else "File")
