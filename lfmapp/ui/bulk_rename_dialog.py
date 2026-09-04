"""Bulk rename dialog (ROADMAP Phase 6.2).

Non-destructive 'before/after' preview that updates live, per-item checkboxes,
hide-unchanged option, manual name editing, and apply/undo of the last batch.
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QClipboard
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from lfmapp.services.bulk_rename import (
    BulkRenamePreset,
    RenamePlan,
    Transform,
    TransformType,
    apply_names_list,
    apply_plan,
    build_plan,
    split_name,
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

    METADATA_FIELDS = [
        ("<none>", ""),
        ("Modification date", TransformType.DATE),
        ("Image date (EXIF)", TransformType.EXIF),
        ("Audio — Title", TransformType.AUDIO),
        ("Audio — Artist", TransformType.AUDIO),
        ("Audio — Album", TransformType.AUDIO),
    ]
    AUDIO_FIELD = {
        1: "title",
        2: "artist",
        3: "album",
    }

    def __init__(self, paths: list[Path], record_callback, on_applied_callback=None, parent=None):
        super().__init__(parent)
        self.paths = [p for p in paths if p.exists()]
        self.record_callback = record_callback  # called with a CompositeOperation
        self.on_applied_callback = on_applied_callback
        self._plan = RenamePlan()
        self._last_batch: list[RenameOperation] = []
        self._presets: dict[str, list[Transform]] = {}
        self._transform_order: list[int] | None = None

        self.setWindowTitle(self.tr("Bulk Rename"))
        self.resize(760, 560)
        layout = QVBoxLayout(self)

        layout.addLayout(self._build_transform_controls())
        layout.addLayout(self._build_more_controls())
        layout.addLayout(self._build_metadata_controls())
        layout.addLayout(self._build_order_controls())
        layout.addLayout(self._build_preset_controls())

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
        self.copy_names_button = buttons.addButton(self.tr("Copy names"), QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_names_button.clicked.connect(self._copy_names)
        self.paste_names_button = buttons.addButton(self.tr("Paste names"), QDialogButtonBox.ButtonRole.ActionRole)
        self.paste_names_button.clicked.connect(self._paste_names)
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

    def _build_metadata_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(self.tr("Metadata:")))
        self.metadata_combo = QComboBox(self)
        for label, value in self.METADATA_FIELDS:
            self.metadata_combo.addItem(self.tr(label), value)
        self.metadata_combo.currentIndexChanged.connect(self.rebuild_plan)
        row.addWidget(self.metadata_combo)

        row.addWidget(QLabel(self.tr("Format:")))
        self.metadata_format_edit = QLineEdit(self)
        self.metadata_format_edit.setPlaceholderText(self.tr("e.g. %Y-%m-%d"))
        self.metadata_format_edit.setText("%Y-%m-%d")
        self.metadata_format_edit.textChanged.connect(self.rebuild_plan)
        row.addWidget(self.metadata_format_edit)

        self.grouped_checkbox = QCheckBox(self.tr("Renumber paired files together"))
        self.grouped_checkbox.setToolTip(self.tr("photo.jpg + photo.raw share one number"))
        self.grouped_checkbox.toggled.connect(self.rebuild_plan)
        row.addWidget(self.grouped_checkbox)

        self.sanitize_checkbox = QCheckBox(self.tr("Sanitize invalid characters"))
        self.sanitize_checkbox.setToolTip(self.tr("Replace \\/:*?\"<>| and reserved names"))
        self.sanitize_checkbox.toggled.connect(self.rebuild_plan)
        row.addWidget(self.sanitize_checkbox)
        return row

    def _build_order_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        list_box = QVBoxLayout()
        list_box.addWidget(QLabel(self.tr("Active steps (applied top to bottom):")))
        self.order_list = QListWidget(self)
        self.order_list.setMaximumHeight(88)
        list_box.addWidget(self.order_list)

        nav = QVBoxLayout()
        self.up_button = QPushButton(self.tr("Up"), self)
        self.up_button.clicked.connect(self._move_transform_up)
        self.down_button = QPushButton(self.tr("Down"), self)
        self.down_button.clicked.connect(self._move_transform_down)
        self.remove_button = QPushButton(self.tr("Remove"), self)
        self.remove_button.clicked.connect(self._remove_transform)
        nav.addWidget(self.up_button)
        nav.addWidget(self.down_button)
        nav.addWidget(self.remove_button)
        nav.addStretch(1)

        row.addLayout(list_box, 1)
        row.addLayout(nav)
        return row

    def _humanize_transform(self, transform: Transform) -> str:
        t = transform.type
        if t == TransformType.SEARCH_REPLACE:
            return f"Replace “{transform.search}” → “{transform.replace}”"
        if t == TransformType.REGEX:
            return f"Regex “{transform.search}” → “{transform.replace}”"
        if t == TransformType.PREFIX:
            return f"Prefix “{transform.value}”"
        if t == TransformType.SUFFIX:
            return f"Suffix “{transform.value}”"
        if t == TransformType.NUMBERING:
            grouped = " (paired)" if transform.grouped else ""
            return f"Numbering from {transform.start}, {transform.digits} digits{grouped}"
        if t == TransformType.CASE:
            return f"Case {transform.value or 'none'}"
        if t == TransformType.DATE:
            return f"Date ({transform.format or 'default'})"
        if t == TransformType.EXIF:
            return f"EXIF date ({transform.format or 'default'})"
        if t == TransformType.AUDIO:
            return f"Audio {transform.field}"
        if t == TransformType.SANITIZE:
            return "Sanitize characters"
        return transform.type

    def _sync_order_list(self):
        transforms = self._collect_transforms(record_order=False)
        if self._transform_order is None:
            self._transform_order = list(range(len(transforms)))
        else:
            # Keep only valid indices for the current transform count.
            self._transform_order = [i for i in self._transform_order if i < len(transforms)]
            # Append any new steps at the end.
            existing = set(self._transform_order)
            for i in range(len(transforms)):
                if i not in existing:
                    self._transform_order.append(i)
        self.order_list.clear()
        for i in self._transform_order:
            self.order_list.addItem(self._humanize_transform(transforms[i]))

    def _move_transform_up(self):
        row = self.order_list.currentRow()
        if row <= 0 or self._transform_order is None:
            return
        self._transform_order[row], self._transform_order[row - 1] = (
            self._transform_order[row - 1],
            self._transform_order[row],
        )
        self._sync_order_list()
        self._rebuild_plan_from_order()

    def _move_transform_down(self):
        row = self.order_list.currentRow()
        if row < 0 or self._transform_order is None or row >= len(self._transform_order) - 1:
            return
        self._transform_order[row], self._transform_order[row + 1] = (
            self._transform_order[row + 1],
            self._transform_order[row],
        )
        self._sync_order_list()
        self._rebuild_plan_from_order()

    def _remove_transform(self):
        row = self.order_list.currentRow()
        if row < 0 or self._transform_order is None:
            return
        self._transform_order.pop(row)
        self._sync_order_list()
        self._rebuild_plan_from_order()

    def _rebuild_plan_from_order(self):
        self._plan = build_plan(self.paths, self._collect_transforms(record_order=True))
        self._refresh_preview()

    def _build_preset_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(self.tr("Preset:")))
        self.preset_combo = QComboBox(self)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        row.addWidget(self.preset_combo, 1)
        self.save_preset_button = QPushButton(self.tr("Save"), self)
        self.save_preset_button.clicked.connect(self._save_preset)
        row.addWidget(self.save_preset_button)
        self.delete_preset_button = QPushButton(self.tr("Delete"), self)
        self.delete_preset_button.clicked.connect(self._delete_preset)
        row.addWidget(self.delete_preset_button)
        self.export_preset_button = QPushButton(self.tr("Export"), self)
        self.export_preset_button.clicked.connect(self._export_presets)
        row.addWidget(self.export_preset_button)
        self.import_preset_button = QPushButton(self.tr("Import"), self)
        self.import_preset_button.clicked.connect(self._import_presets)
        row.addWidget(self.import_preset_button)
        return row

    # ─── Presets ───────────────────────────────────────────────

    def load_presets(self, presets: list[BulkRenamePreset]):
        self._presets = {p.name: p.transforms for p in presets}
        self._rebuild_preset_combo()

    def export_presets(self) -> list[BulkRenamePreset]:
        return [BulkRenamePreset(name, transforms) for name, transforms in self._presets.items()]

    def _rebuild_preset_combo(self):
        current = self.preset_combo.currentText()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem(self.tr("— none —"))
        for name in sorted(self._presets):
            self.preset_combo.addItem(name)
        if current:
            index = self.preset_combo.findText(current)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)

    def _on_preset_selected(self):
        name = self.preset_combo.currentText()
        transforms = self._presets.get(name)
        if transforms is None:
            return
        self._apply_transforms_to_controls(transforms)
        self.rebuild_plan()

    def _apply_transforms_to_controls(self, transforms: list[Transform]):
        # Reflect a preset into the controls (best-effort, one transform each).
        self.search_edit.clear()
        self.replace_edit.clear()
        self.prefix_edit.clear()
        self.suffix_edit.clear()
        self.regex_checkbox.setChecked(False)
        self.case_combo.setCurrentIndex(0)
        self.metadata_combo.setCurrentIndex(0)
        self.grouped_checkbox.setChecked(False)
        self.number_start_spin.setValue(0)
        if hasattr(self, "sanitize_checkbox"):
            self.sanitize_checkbox.setChecked(False)
        for transform in transforms:
            if transform.type == TransformType.PREFIX:
                self.prefix_edit.setText(transform.value)
            elif transform.type == TransformType.SUFFIX:
                self.suffix_edit.setText(transform.value)
            elif transform.type == TransformType.SEARCH_REPLACE:
                self.search_edit.setText(transform.search)
                self.replace_edit.setText(transform.replace)
                self.case_checkbox.setChecked(transform.case_sensitive)
            elif transform.type == TransformType.REGEX:
                self.search_edit.setText(transform.search)
                self.replace_edit.setText(transform.replace)
                self.regex_checkbox.setChecked(True)
                self.case_checkbox.setChecked(transform.case_sensitive)
            elif transform.type == TransformType.NUMBERING:
                self.number_start_spin.setValue(transform.start)
                self.number_digits_spin.setValue(transform.digits)
                self.grouped_checkbox.setChecked(transform.grouped)
            elif transform.type == TransformType.CASE:
                for i, (_label, mode, scope) in enumerate(self.CASE_MODES):
                    if mode == transform.value and scope == transform.search:
                        self.case_combo.setCurrentIndex(i)
                        break
            elif transform.type in (TransformType.DATE, TransformType.EXIF):
                idx = self.metadata_combo.findData(transform.type)
                if idx >= 0:
                    self.metadata_combo.setCurrentIndex(idx)
                self.metadata_format_edit.setText(transform.format or "%Y-%m-%d")
            elif transform.type == TransformType.AUDIO:
                idx = 1 + list(self.AUDIO_FIELD.values()).index(transform.field)
                self.metadata_combo.setCurrentIndex(
                    self.metadata_combo.findText(self.metadata_combo.itemText(idx))
                )
            elif transform.type == TransformType.SANITIZE:
                if hasattr(self, "sanitize_checkbox"):
                    self.sanitize_checkbox.setChecked(True)

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, self.tr("Save preset"), self.tr("Preset name:"))
        if not ok or not name.strip():
            return
        self._presets[name.strip()] = self._collect_transforms()
        self._rebuild_preset_combo()
        self.preset_combo.setCurrentText(name.strip())

    def _delete_preset(self):
        name = self.preset_combo.currentText()
        if name in self._presets:
            del self._presets[name]
            self._rebuild_preset_combo()

    def _export_presets(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export presets"), "bulk-rename-presets.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(
                    {"presets": [BulkRenamePreset(n, t).to_dict() for n, t in self._presets.items()]},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.critical(self, self.tr("Export"), str(exc))

    def _import_presets(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Import presets"), "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, self.tr("Import"), str(exc))
            return
        for entry in data.get("presets", []):
            preset = BulkRenamePreset.from_dict(entry)
            if preset.name:
                self._presets[preset.name] = preset.transforms
        self._rebuild_preset_combo()

    def remember_transforms(self, transforms: list[Transform]):
        """Recall the transforms from the previous batch (a '<last>' preset)."""
        self._apply_transforms_to_controls(transforms)
        self.rebuild_plan()

    def last_batch_transforms(self) -> list[Transform]:
        return self._collect_transforms()

    # ─── Plan building ─────────────────────────────────────────

    def _collect_transforms(self, record_order: bool = True) -> list[Transform]:
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
                    grouped=getattr(self, "grouped_checkbox").isChecked() if hasattr(self, "grouped_checkbox") else False,
                )
            )
        # Metadata transforms (date / EXIF / audio).
        if hasattr(self, "metadata_combo") and self.metadata_combo.currentData():
            mtype = self.metadata_combo.currentData()
            fmt = getattr(self, "metadata_format_edit").text() if hasattr(self, "metadata_format_edit") else ""
            if mtype == TransformType.DATE:
                transforms.append(Transform(TransformType.DATE, format=fmt))
            elif mtype == TransformType.EXIF:
                transforms.append(Transform(TransformType.EXIF, format=fmt))
            elif mtype == TransformType.AUDIO:
                index = self.metadata_combo.currentIndex()
                field = self.AUDIO_FIELD.get(index, "title")
                transforms.append(Transform(TransformType.AUDIO, value="_", field=field))
        if hasattr(self, "case_combo") and self.case_combo.currentData():
            mode, scope = self.case_combo.currentData()
            if mode:
                transforms.append(Transform(TransformType.CASE, value=mode, search=scope))
        # Sanitization goes last so it cleans whatever the other transforms produced.
        if hasattr(self, "sanitize_checkbox") and self.sanitize_checkbox.isChecked():
            transforms.append(Transform(TransformType.SANITIZE))

        # Respect an explicit user order when present and still consistent.
        order = getattr(self, "_transform_order", None)
        if record_order and order is not None and len(order) == len(transforms):
            ordered = [transforms[i] for i in order]
            return ordered
        return transforms

    def rebuild_plan(self):
        transforms = self._collect_transforms(record_order=False)
        # Reset the explicit order whenever the underlying steps change.
        if self._transform_order is not None and len(self._transform_order) != len(transforms):
            self._transform_order = None
        self._plan = build_plan(self.paths, self._collect_transforms(record_order=True))
        if hasattr(self, "order_list"):
            self._sync_order_list()
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

    def _copy_names(self):
        names = [item.new_name for item in self._plan.items]
        QApplication.clipboard().setText("\n".join(names))

    def _paste_names(self):
        text = QApplication.clipboard().text()
        if not text:
            return
        lines = [line for line in text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if idx >= len(self._plan.items):
                break
            self._plan.items[idx].new_name = line.strip()
            self._plan.items[idx].new_path = self._plan.items[idx].original_path.with_name(line.strip())
            self._plan.items[idx].changed = line.strip() != self._plan.items[idx].original_name
        self._refresh_preview()

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