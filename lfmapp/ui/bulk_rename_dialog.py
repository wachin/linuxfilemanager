"""Bulk rename dialog (ROADMAP Phase 6.2).

Non-destructive 'before/after' preview that updates live, per-item checkboxes,
hide-unchanged option, manual name editing, and apply/undo of the last batch.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from lfmapp.services.bulk_rename import (
    RenamePlan,
    Transform,
    TransformType,
    apply_plan,
    build_plan,
)
from lfmapp.services.operation_history import CompositeOperation, RenameOperation


class BulkRenameDialog(QDialog):
    """Collects transformations and previews/applies a batch rename."""

    CASE_MODES = [
        ("No change", "", ""),
        ("UPPERCASE", "upper", ""),
        ("lowercase", "lower", ""),
        ("Title Case", "title", ""),
        ("UPPER extension", "upper", "extension"),
        ("lower extension", "lower", "extension"),
    ]

    def __init__(self, paths: list[Path], record_callback, on_applied_callback=None, parent=None):
        super().__init__(parent)
        self.paths = [p for p in paths if p.exists()]
        self.record_callback = record_callback  # called with a CompositeOperation
        self.on_applied_callback = on_applied_callback
        self._plan = RenamePlan()
        self._last_batch: list[RenameOperation] = []

        self.setWindowTitle(self.tr("Bulk Rename"))
        self.resize(720, 520)
        layout = QVBoxLayout(self)

        layout.addLayout(self._build_transform_controls())
        layout.addLayout(self._build_more_controls())

        self.hide_unchanged_checkbox = QCheckBox(self.tr("Hide files that do not change"))
        self.hide_unchanged_checkbox.setChecked(False)
        self.hide_unchanged_checkbox.toggled.connect(self._refresh_preview)
        layout.addWidget(self.hide_unchanged_checkbox)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [self.tr("Include"), self.tr("Before"), self.tr("After")]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 64)
        self.table.setColumnWidth(1, 300)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Close
        )
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setText(self.tr("Rename"))
        self.apply_button.clicked.connect(self.apply_batch)
        self.undo_button = buttons.addButton(self.tr("Undo last batch"), QDialogButtonBox.ButtonRole.ActionRole)
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.undo_last_batch)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.rebuild_plan()

    # ─── Transform controls ────────────────────────────────────

    def _build_transform_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()

        row.addWidget(QLabel(self.tr("Find:")))
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(self.tr("text or regex"))
        self.search_edit.textChanged.connect(self.rebuild_plan)
        row.addWidget(self.search_edit, 2)

        row.addWidget(QLabel(self.tr("Replace:")))
        self.replace_edit = QLineEdit(self)
        self.replace_edit.textChanged.connect(self.rebuild_plan)
        row.addWidget(self.replace_edit, 2)

        self.regex_checkbox = QCheckBox(self.tr("Regex"))
        self.regex_checkbox.toggled.connect(self.rebuild_plan)
        row.addWidget(self.regex_checkbox)

        self.case_checkbox = QCheckBox(self.tr("Case sensitive"))
        self.case_checkbox.toggled.connect(self.rebuild_plan)
        row.addWidget(self.case_checkbox)
        return row

    def _build_more_controls(self) -> QHBoxLayout:
        # Kept simple: search/replace + numbering + case are the core modes.
        row = QHBoxLayout()
        row.addWidget(QLabel(self.tr("Prefix:")))
        self.prefix_edit = QLineEdit(self)
        self.prefix_edit.textChanged.connect(self.rebuild_plan)
        row.addWidget(self.prefix_edit)

        row.addWidget(QLabel(self.tr("Suffix:")))
        self.suffix_edit = QLineEdit(self)
        self.suffix_edit.textChanged.connect(self.rebuild_plan)
        row.addWidget(self.suffix_edit)

        row.addWidget(QLabel(self.tr("Numbering start:")))
        self.number_start_spin = QSpinBox(self)
        self.number_start_spin.setRange(0, 100000)
        self.number_start_spin.valueChanged.connect(self.rebuild_plan)
        row.addWidget(self.number_start_spin)

        row.addWidget(QLabel(self.tr("Digits:")))
        self.number_digits_spin = QSpinBox(self)
        self.number_digits_spin.setRange(0, 12)
        self.number_digits_spin.setValue(2)
        self.number_digits_spin.valueChanged.connect(self.rebuild_plan)
        row.addWidget(self.number_digits_spin)

        row.addWidget(QLabel(self.tr("Case:")))
        self.case_combo = QComboBox(self)
        for label, mode, scope in self.CASE_MODES:
            self.case_combo.addItem(self.tr(label), (mode, scope))
        self.case_combo.currentIndexChanged.connect(self.rebuild_plan)
        row.addWidget(self.case_combo)
        return row

    # ─── Plan building ─────────────────────────────────────────

    def _collect_transforms(self) -> list[Transform]:
        transforms: list[Transform] = []
        search = self.search_edit.text() if hasattr(self, "search_edit") else ""
        replace = self.replace_edit.text() if hasattr(self, "replace_edit") else ""
        if search:
            if getattr(self, "regex_checkbox").isChecked():
                transforms.append(
                    Transform(
                        TransformType.REGEX,
                        search=search,
                        replace=replace,
                        case_sensitive=getattr(self, "case_checkbox").isChecked(),
                    )
                )
            else:
                transforms.append(
                    Transform(
                        TransformType.SEARCH_REPLACE,
                        search=search,
                        replace=replace,
                        case_sensitive=getattr(self, "case_checkbox").isChecked(),
                    )
                )
        if hasattr(self, "prefix_edit") and self.prefix_edit.text():
            transforms.append(Transform(TransformType.PREFIX, value=self.prefix_edit.text()))
        if hasattr(self, "suffix_edit") and self.suffix_edit.text():
            transforms.append(Transform(TransformType.SUFFIX, value=self.suffix_edit.text()))
        if hasattr(self, "number_start_spin") and self.number_start_spin.value() > 0:
            transforms.append(
                Transform(
                    TransformType.NUMBERING,
                    start=self.number_start_spin.value(),
                    digits=self.number_digits_spin.value(),
                )
            )
        if hasattr(self, "case_combo") and self.case_combo.currentData():
            mode, scope = self.case_combo.currentData()
            if mode:
                transforms.append(Transform(TransformType.CASE, value=mode, search=scope))
        return transforms

    def rebuild_plan(self):
        transforms = self._collect_transforms()
        self._plan = build_plan(self.paths, transforms)
        self._refresh_preview()

    # ─── Preview table ─────────────────────────────────────────

    def _refresh_preview(self):
        hide = self.hide_unchanged_checkbox.isChecked()
        self._table_import_mapping: dict[int, PlannedRenameIndex] = {}
        self._table_import_mapping.clear()

        rows: list[tuple[int, object]] = []
        for i, item in enumerate(self._plan.items):
            if hide and not item.changed:
                continue
            rows.append((i, item))

        self.table.setRowCount(len(rows))
        for row, (index, item) in enumerate(rows):
            self._table_import_mapping[row] = index

            checkbox = QCheckBox()
            checkbox.setChecked(item.enabled)
            checkbox.toggled.connect(
                lambda checked, idx=index: self._on_item_toggled(idx, checked)
            )
            self.table.setCellWidget(row, 0, checkbox)

            before_item = QTableWidgetItem(item.original_name)
            before_item.setFlags(before_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, before_item)

            after_item = QTableWidgetItem(item.new_name)
            after_item.setFlags(after_item.flags() | Qt.ItemFlag.ItemIsEditable)
            if item.conflict:
                after_item.setForeground(Qt.GlobalColor.red)
                after_item.setToolTip(self.tr("Conflict: {kind}").format(kind=item.conflict))
            self.table.setItem(row, 2, after_item)

        self.table.itemChanged.connect(self._on_after_edited)

    def _on_item_toggled(self, index: int, checked: bool):
        if 0 <= index < len(self._plan.items):
            self._plan.items[index].enabled = checked

    def _on_after_edited(self, item: QTableWidgetItem):
        if item.column() != 2:
            return
        row = item.row()
        index = self._table_import_mapping.get(row)
        if index is None:
            return
        new_name = item.text()
        planned = self._plan.items[index]
        planned.new_name = new_name
        planned.new_path = planned.original_path.with_name(new_name)
        planned.changed = new_name != planned.original_name
        # Re-validate this row only (quick heuristic).
        if not new_name or new_name in {".", ".."} or "/" in new_name:
            planned.conflict = "invalid"
            item.setForeground(Qt.GlobalColor.red)
        else:
            planned.conflict = None
            item.setForeground(Qt.GlobalColor.black)

    # ─── Apply / undo ──────────────────────────────────────────

    def apply_batch(self):
        plan = self._plan
        try:
            renamed = apply_plan(plan)
        except ValueError as exc:
            self.apply_button.setText(self.tr("Fix conflicts first"))
            return
        if not renamed:
            self.apply_button.setText(self.tr("Nothing to apply"))
            return

        operations = [RenameOperation(old, new) for old, new in renamed]
        if self.record_callback and operations:
            self.record_callback(CompositeOperation.from_operations(self.tr("Bulk rename"), operations))
        self._last_batch = operations
        self.undo_button.setEnabled(True)
        self.apply_button.setText(self.tr("Applied"))
        if self.on_applied_callback:
            self.on_applied_callback()
        self.rebuild_plan()

    def undo_last_batch(self):
        for operation in reversed(self._last_batch):
            operation.undo()
        self._last_batch = []
        self.undo_button.setEnabled(False)
        self.apply_button.setText(self.tr("Rename"))
        if self.on_applied_callback:
            self.on_applied_callback()


__all__ = ["BulkRenameDialog"]