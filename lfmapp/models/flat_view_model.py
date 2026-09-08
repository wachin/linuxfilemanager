"""Flat view model (backlog P2).

A read-only table model presenting flattened tree entries (see
``lfmapp.services.flat_view_service``) with the columns the roadmap asks
for: Name, Relative location, Size, Type and Date modified. It reuses the
human-readable formatters of ``FileSystemModel`` so the flat view shows the
same size/type/date text as the normal views.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QGuiApplication

from lfmapp.models.file_system_model import FileSystemModel
from lfmapp.services.flat_view_service import FlatEntry


class FlatViewModel(QAbstractTableModel):
    COLUMN_KEYS = ["name", "location", "size", "type", "modified"]
    COLUMN_LABELS = {
        "name": "Name",
        "location": "Location",
        "size": "Size",
        "type": "Type",
        "modified": "Date Modified",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[FlatEntry] = []
        self._date_format = "yyyy-MM-dd HH:mm"

    # ── Population ─────────────────────────────────────────────

    def set_entries(self, entries: list[FlatEntry]):
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def append_entries(self, entries: list[FlatEntry]):
        if not entries:
            return
        row = len(self._entries)
        self.beginInsertRows(QModelIndex(), row, row + len(entries) - 1)
        self._entries.extend(entries)
        self.endInsertRows()

    def entry_at(self, row: int) -> FlatEntry | None:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def entries(self) -> list[FlatEntry]:
        return list(self._entries)

    def path_at(self, row: int) -> Path | None:
        entry = self.entry_at(row)
        return entry.path if entry else None

    def set_date_format(self, fmt: str):
        self._date_format = fmt or "yyyy-MM-dd HH:mm"

    # ── QAbstractTableModel ────────────────────────────────────

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMN_KEYS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self.COLUMN_KEYS)
        ):
            return QGuiApplication.translate("FlatViewModel", self.COLUMN_LABELS[self.COLUMN_KEYS[section]])
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entry_at(index.row())
        if entry is None:
            return None
        key = self.COLUMN_KEYS[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            if key == "name":
                return entry.name
            if key == "location":
                return entry.relative
            if key == "size":
                if entry.is_dir:
                    return ""
                try:
                    return FileSystemModel._human_readable_size_with_base(
                        entry.path.stat().st_size, 1000
                    )
                except OSError:
                    return ""
            if key == "type":
                if entry.is_dir:
                    return QGuiApplication.translate("FlatViewModel", "Folder")
                suffix = entry.path.suffix.lower().lstrip(".")
                if not suffix:
                    return QGuiApplication.translate("FlatViewModel", "File")
                return f"{suffix.upper()} file"
            if key == "modified":
                try:
                    from datetime import datetime as _dt

                    return _dt.fromtimestamp(
                        entry.path.stat().st_mtime
                    ).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    return ""
        elif role == Qt.ItemDataRole.UserRole:
            # The absolute path, for surfaces that resolve real locations.
            return str(entry.path)
        elif role == Qt.ItemDataRole.ToolTipRole:
            return str(entry.path)
        return None

    def sort(self, column: int, order=Qt.SortOrder.AscendingOrder):
        if not (0 <= column < len(self.COLUMN_KEYS)):
            return
        key = self.COLUMN_KEYS[column]

        def sort_value(entry: FlatEntry):
            if key == "name":
                return (entry.is_dir, entry.name.casefold())
            if key == "location":
                return entry.relative.casefold()
            if key == "size":
                try:
                    return entry.path.stat().st_size
                except OSError:
                    return 0
            if key == "type":
                suffix = entry.path.suffix.lower()
                return (0, "") if entry.is_dir else (1, suffix)
            if key == "modified":
                try:
                    return entry.path.stat().st_mtime
                except OSError:
                    return 0.0
            return 0

        self.layoutAboutToBeChanged.emit()
        self._entries.sort(
            key=sort_value,
            reverse=(order == Qt.SortOrder.DescendingOrder),
        )
        self.layoutChanged.emit()
