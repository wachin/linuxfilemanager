"""Custom file system model for linux-file-manager.

Extends QFileSystemModel with additional functionality:
- Human-readable file sizes
- File type descriptions
- Extended Details-view columns
"""

import mimetypes
import os
import stat
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QDir, QFileInfo, Qt
from PyQt6.QtGui import QFileSystemModel, QIcon, QImageReader, QPixmap
from PyQt6.QtWidgets import QFileIconProvider

try:
    import grp
except ImportError:  # pragma: no cover - not expected on Linux
    grp = None

try:
    import pwd
except ImportError:  # pragma: no cover - not expected on Linux
    pwd = None


class FileSystemModel(QFileSystemModel):
    """Extended file system model with improved display."""

    COLUMN_KEYS = [
        "name",
        "size",
        "type",
        "modified",
        "created_time",
        "accessed_time",
        "created_date",
        "detailed_type",
        "group",
        "location",
        "mime_type",
        "octal_permissions",
        "owner",
        "permissions",
        "selinux_context",
        "modified_time",
    ]
    COLUMN_LABELS = {
        "name": "Name",
        "size": "Size",
        "type": "Type",
        "modified": "Date Modified",
        "created_time": "Created - Time",
        "accessed_time": "Date Accessed",
        "created_date": "Date Created",
        "detailed_type": "Detailed Type",
        "group": "Group",
        "location": "Location",
        "mime_type": "MIME Type",
        "octal_permissions": "Octal Permissions",
        "owner": "Owner",
        "permissions": "Permissions",
        "selinux_context": "SELinux Context",
        "modified_time": "Modified - Time",
    }

    def __init__(self, parent=None, root_path: Path | str | None = None, config=None):
        super().__init__(parent)
        self.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.Hidden)
        self.setIconProvider(self._optimized_icon_provider())
        self.setRootPath(str(root_path or Path.home()))
        self.config = config
        self._show_extensions = True
        self._show_selection_checkboxes = False
        self._checked_paths: set[str] = set()
        self._size_prefix_style = "decimal"
        self._date_format = "yyyy-MM-dd HH:mm"
        self._tooltips_enabled = False
        self._tooltip_fields: list[str] = []
        self._workspace_thumbnails_enabled = True
        self._thumbnail_cache: dict[tuple[str, int, int], QIcon] = {}
        self.apply_display_preferences()

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

    def apply_display_preferences(self):
        if self.config is None:
            return
        self._size_prefix_style = str(
            self.config.data.get("file_size_prefix_style", "decimal")
        )
        self._date_format = str(
            self.config.data.get("date_display_format", "yyyy-MM-dd HH:mm")
        ) or "yyyy-MM-dd HH:mm"
        self._tooltips_enabled = bool(
            self.config.data.get("preview_tooltips_icon_compact", False)
            or self.config.data.get("preview_tooltips_list", False)
        )
        self._workspace_thumbnails_enabled = (
            str(self.config.data.get("preview_show_thumbnails", "local_only")) != "never"
        )
        self._tooltip_fields = [
            str(value)
            for value in self.config.data.get("preview_tooltip_fields", [])
            if value
        ]
        self._thumbnail_cache.clear()
        self.layoutChanged.emit()

    def columnCount(self, parent=None):
        return len(self.COLUMN_KEYS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.COLUMN_KEYS):
                return self.COLUMN_LABELS[self.COLUMN_KEYS[section]]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Override data to provide human-readable sizes and type info."""
        if not index.isValid():
            return super().data(index, role)

        source_index = index.siblingAtColumn(0)
        file_info = self.fileInfo(source_index)

        if (
            role == Qt.ItemDataRole.CheckStateRole
            and self._show_selection_checkboxes
            and index.column() == 0
        ):
            path = self.filePath(index)
            if path in self._checked_paths:
                return Qt.CheckState.Checked
            return Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.DecorationRole:
            if index.column() != 0:
                return None
            thumbnail = self._thumbnail_icon(file_info)
            if thumbnail is not None:
                return thumbnail

        if role == Qt.ItemDataRole.DisplayRole:
            column = index.column()
            if column >= len(self.COLUMN_KEYS):
                return None
            key = self.COLUMN_KEYS[column]

            # Column 0: Name - optionally hide extensions
            if key == "name" and not self._show_extensions:
                if file_info.isFile():
                    name = file_info.fileName()
                    dot_pos = name.rfind(".")
                    if dot_pos > 0:
                        return name[:dot_pos]
                return super().data(source_index, role)

            if key == "name":
                return super().data(source_index, role)

            if key == "size":
                if file_info.isDir():
                    return ""
                size = file_info.size()
                return self._human_readable_size(size)

            if key == "type":
                return self._file_type_description(file_info)

            if key == "modified":
                return file_info.lastModified().toString(self._date_format)

            return self._extended_column_value(file_info, key)

        elif role == Qt.ItemDataRole.ToolTipRole:
            if not self._tooltips_enabled:
                return None
            lines = [file_info.fileName()]
            if file_info.isFile():
                lines.append(self._human_readable_size(file_info.size()))
            if "detailed_type" in self._tooltip_fields:
                lines.append(self._file_type_description(file_info))
            if "modified_date" in self._tooltip_fields:
                lines.append(file_info.lastModified().toString(self._date_format))
            if "accessed_date" in self._tooltip_fields:
                lines.append(file_info.lastRead().toString(self._date_format))
            if "created_date" in self._tooltip_fields:
                created = getattr(file_info, "birthTime", lambda: file_info.lastModified())()
                lines.append(created.toString(self._date_format))
            if "location" in self._tooltip_fields or not self._tooltip_fields:
                lines.append(file_info.absoluteFilePath())
            return "\n".join(line for line in lines if line)

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            column = index.column()
            if 0 <= column < len(self.COLUMN_KEYS) and self.COLUMN_KEYS[column] in {
                "size",
                "octal_permissions",
            }:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        return super().data(source_index, role)

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

    def _human_readable_size(self, size: int) -> str:
        base = 1000 if self._size_prefix_style == "decimal" else 1024
        return self._human_readable_size_with_base(size, base)

    def _thumbnail_icon(self, file_info: QFileInfo) -> QIcon | None:
        """Return a cached thumbnail icon for image files in the main workspace."""
        if not self._workspace_thumbnails_enabled or not file_info.isFile():
            return None

        suffix = file_info.suffix().lower()
        if suffix not in {"png", "jpg", "jpeg", "gif", "bmp", "svg", "webp"}:
            return None

        path = file_info.absoluteFilePath()
        stat_result = os.stat(path)
        cache_key = (path, stat_result.st_mtime_ns, stat_result.st_size)
        cached = self._thumbnail_cache.get(cache_key)
        if cached is not None:
            return cached

        reader = QImageReader(path)
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            return None

        icon = QIcon()
        for size in (22, 32, 48, 64, 96):
            pixmap = QPixmap.fromImage(
                image.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            if not pixmap.isNull():
                icon.addPixmap(pixmap)

        if icon.isNull():
            return None

        self._thumbnail_cache[cache_key] = icon
        if len(self._thumbnail_cache) > 512:
            # Keep the cache bounded so long sessions do not retain every thumbnail forever.
            self._thumbnail_cache.pop(next(iter(self._thumbnail_cache)))
        return icon

    @staticmethod
    def _human_readable_size_with_base(size: int, base: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < base:
                if unit == "B":
                    return f"{size} {unit}"
                return f"{size:.1f} {unit}"
            size /= base
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

    def _extended_column_value(self, file_info: QFileInfo, key: str) -> str:
        path = Path(file_info.absoluteFilePath())
        stat_result = self._safe_stat(path)

        if key == "created_time":
            return self._format_datetime(self._created_timestamp(file_info, stat_result))
        if key == "accessed_time":
            return self._format_datetime(stat_result.st_atime if stat_result else None)
        if key == "created_date":
            return self._format_date(self._created_timestamp(file_info, stat_result))
        if key == "detailed_type":
            return self._detailed_type_description(file_info)
        if key == "group":
            return self._group_name(stat_result)
        if key == "location":
            return str(path.parent)
        if key == "mime_type":
            return mimetypes.guess_type(str(path))[0] or ""
        if key == "octal_permissions":
            return self._octal_permissions(stat_result)
        if key == "owner":
            return self._owner_name(stat_result)
        if key == "permissions":
            return self._symbolic_permissions(stat_result)
        if key == "selinux_context":
            return self._selinux_context(path)
        if key == "modified_time":
            return self._format_time_only(stat_result.st_mtime if stat_result else None)
        return ""

    @staticmethod
    def _safe_stat(path: Path):
        try:
            return path.stat()
        except OSError:
            return None

    def _created_timestamp(self, file_info: QFileInfo, stat_result) -> float | None:
        birth_time = file_info.birthTime()
        if birth_time.isValid():
            return birth_time.toSecsSinceEpoch()
        if stat_result is not None:
            return stat_result.st_ctime
        return None

    def _format_datetime(self, timestamp: float | None) -> str:
        if timestamp is None:
            return ""
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _format_date(timestamp: float | None) -> str:
        if timestamp is None:
            return ""

        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

    @staticmethod
    def _format_time_only(timestamp: float | None) -> str:
        if timestamp is None:
            return ""

        return datetime.fromtimestamp(timestamp).strftime("%H:%M")

    @staticmethod
    def _detailed_type_description(file_info: QFileInfo) -> str:
        path = Path(file_info.absoluteFilePath())
        mime_type = mimetypes.guess_type(str(path))[0]
        if mime_type:
            return mime_type
        return FileSystemModel._file_type_description(file_info)

    @staticmethod
    def _group_name(stat_result) -> str:
        if stat_result is None or grp is None:
            return ""
        try:
            return grp.getgrgid(stat_result.st_gid).gr_name
        except KeyError:
            return str(stat_result.st_gid)

    @staticmethod
    def _owner_name(stat_result) -> str:
        if stat_result is None or pwd is None:
            return ""
        try:
            return pwd.getpwuid(stat_result.st_uid).pw_name
        except KeyError:
            return str(stat_result.st_uid)

    @staticmethod
    def _octal_permissions(stat_result) -> str:
        if stat_result is None:
            return ""
        return oct(stat.S_IMODE(stat_result.st_mode))[2:]

    @staticmethod
    def _symbolic_permissions(stat_result) -> str:
        if stat_result is None:
            return ""
        return stat.filemode(stat_result.st_mode)

    @staticmethod
    def _selinux_context(path: Path) -> str:
        try:
            return os.getxattr(path, "security.selinux").decode("utf-8", errors="replace")
        except OSError:
            return ""
