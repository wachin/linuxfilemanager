""""Select By…" dialog (Phase 6.1 / backlog P2 advanced selection).

A small form that builds a `SelectionCriteria` (name glob, extension list,
type group, size window).  The actual matching lives in the pure
`SelectionController.select_by`; this dialog is only the input surface.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from lfmapp.controllers import SelectionCriteria


# Combo label → file_type value (mirrors SearchFilters groups).
_TYPES = [
    ("Any", "any"),
    ("Files", "file"),
    ("Folders", "folder"),
    ("Images", "image"),
    ("Documents", "document"),
    ("Audio", "audio"),
    ("Video", "video"),
    ("Archives", "archive"),
]


class SelectByDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Select By…"))
        self.setMinimumWidth(380)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self._glob_edit = QLineEdit()
        self._glob_edit.setPlaceholderText("*.jpg, report_??.pdf")
        self._case_cb = QCheckBox(self.tr("Match case"))
        glob_row = QHBoxLayout()
        glob_row.addWidget(self._glob_edit, 1)
        glob_row.addWidget(self._case_cb)
        form.addRow(self.tr("Name pattern"), glob_row)

        self._ext_edit = QLineEdit()
        self._ext_edit.setPlaceholderText("jpg, png, txt")
        form.addRow(self.tr("Extensions"), self._ext_edit)

        self._type_combo = QComboBox()
        for label, _ in _TYPES:
            self._type_combo.addItem(self.tr(label))
        form.addRow(self.tr("Type"), self._type_combo)

        self._use_size_cb = QCheckBox(self.tr("Limit by size"))
        self._use_size_cb.stateChanged.connect(self._on_size_toggled)
        form.addRow(self._use_size_cb)

        size_row = QHBoxLayout()
        self._min_size = QSpinBox()
        self._min_size.setRange(0, 1_000_000_000)
        self._min_size.setSuffix(" KB")
        self._min_size.setEnabled(False)
        self._max_size = QSpinBox()
        self._max_size.setRange(0, 1_000_000_000)
        self._max_size.setSuffix(" KB")
        self._max_size.setEnabled(False)
        size_row.addWidget(QLabel(self.tr("from")))
        size_row.addWidget(self._min_size)
        size_row.addWidget(QLabel(self.tr("to")))
        size_row.addWidget(self._max_size)
        size_row.addStretch()
        form.addRow(size_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_size_toggled(self, state: int):
        on = state == Qt.CheckState.Checked.value
        self._min_size.setEnabled(on)
        self._max_size.setEnabled(on)

    def _parse_extensions(self) -> tuple[str, ...]:
        raw = self._ext_edit.text().strip()
        if not raw:
            return ()
        out = []
        for part in raw.replace(" ", ",").split(","):
            part = part.strip().lstrip(".").lower()
            if part:
                out.append("." + part)
        return tuple(out)

    def criteria(self) -> SelectionCriteria:
        type_value = _TYPES[self._type_combo.currentIndex()][1]
        min_size = self._min_size.value() * 1024 if self._min_size.isEnabled() else None
        max_size = self._max_size.value() * 1024 if self._max_size.isEnabled() else None
        return SelectionCriteria(
            name_glob=self._glob_edit.text().strip(),
            extensions=self._parse_extensions(),
            file_type=type_value,
            min_size=min_size or None,
            max_size=max_size or None,
            case_sensitive=self._case_cb.isChecked(),
        )
