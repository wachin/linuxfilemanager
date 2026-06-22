from datetime import datetime, time

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
)

from lfmapp.services.search_service import SearchFilters


class SearchFilterDialog(QDialog):
    """Dialog for composing a filtered folder search."""

    TYPE_OPTIONS = [
        ("any", "Any"),
        ("file", "Files"),
        ("folder", "Folders"),
        ("image", "Images"),
        ("document", "Documents"),
        ("audio", "Audio"),
        ("video", "Video"),
        ("archive", "Archives"),
    ]

    def __init__(self, query: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Search Filters"))
        self.resize(360, 260)

        layout = QFormLayout(self)

        self.query_edit = QLineEdit(query)
        layout.addRow(self.tr("Name contains:"), self.query_edit)

        self.type_combo = QComboBox()
        type_labels = {
            "any": self.tr("Any"),
            "file": self.tr("Files"),
            "folder": self.tr("Folders"),
            "image": self.tr("Images"),
            "document": self.tr("Documents"),
            "audio": self.tr("Audio"),
            "video": self.tr("Video"),
            "archive": self.tr("Archives"),
        }
        for value, _label in self.TYPE_OPTIONS:
            self.type_combo.addItem(type_labels[value], value)
        layout.addRow(self.tr("Type:"), self.type_combo)

        self.min_size = self._size_spinbox()
        self.max_size = self._size_spinbox()
        layout.addRow(self.tr("Minimum size (KB):"), self.min_size)
        layout.addRow(self.tr("Maximum size (KB):"), self.max_size)

        self.after_enabled = QCheckBox()
        self.after_date = self._date_edit()
        layout.addRow(self.tr("Modified after:"), self.after_enabled)
        layout.addRow("", self.after_date)

        self.before_enabled = QCheckBox()
        self.before_date = self._date_edit()
        layout.addRow(self.tr("Modified before:"), self.before_enabled)
        layout.addRow("", self.before_date)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def query(self) -> str:
        return self.query_edit.text().strip()

    def filters(self) -> SearchFilters:
        return SearchFilters(
            file_type=self.type_combo.currentData(),
            min_size=self._kilobytes_to_bytes(self.min_size.value()),
            max_size=self._kilobytes_to_bytes(self.max_size.value()),
            modified_after=self._start_of_day_timestamp(self.after_date.date()) if self.after_enabled.isChecked() else None,
            modified_before=self._end_of_day_timestamp(self.before_date.date()) if self.before_enabled.isChecked() else None,
        )

    def _size_spinbox(self) -> QSpinBox:
        spinbox = QSpinBox()
        spinbox.setRange(0, 2_147_483_647)
        spinbox.setSpecialValueText(self.tr("Any"))
        return spinbox

    @staticmethod
    def _date_edit() -> QDateEdit:
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate())
        return date_edit

    @staticmethod
    def _kilobytes_to_bytes(value: int) -> int | None:
        return value * 1024 if value > 0 else None

    @staticmethod
    def _start_of_day_timestamp(date: QDate) -> float:
        return datetime.combine(date.toPyDate(), time.min).timestamp()

    @staticmethod
    def _end_of_day_timestamp(date: QDate) -> float:
        return datetime.combine(date.toPyDate(), time.max).timestamp()
