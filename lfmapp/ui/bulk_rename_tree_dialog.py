"""Recursive/template bulk rename dialog (ROADMAP Phase 6.2 — tree mode).

A separate window from ``BulkRenameDialog``: it renames across a whole folder
tree using a token template, without touching the flat-engine code path.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from lfmapp.services.bulk_rename_tree import (
    DEFAULT_DATE_FMT,
    TreePlan,
    apply_tree_plan,
    build_tree_plan,
    render_template,
)
from lfmapp.services.operation_history import CompositeOperation, RenameOperation


class BulkRenameTreeDialog(QDialog):
    """Recursively rename/relocate a tree via a token template."""

    TOKEN_HELP = "{n} {n:03} {name} {parent} {folder} {ext} {date}"

    def __init__(self, root: Path, record_callback, on_applied_callback=None, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.record_callback = record_callback
        self.on_applied_callback = on_applied_callback
        self._plan = TreePlan()
        self._last_batch: list[RenameOperation] = []

        self.setWindowTitle(self.tr("Bulk Rename (Tree)"))
        self.resize(820, 540)
        layout = QVBoxLayout(self)

        # Folder + options row
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel(self.tr("Folder:")))
        self.root_edit = QLineEdit(str(self.root))
        self.root_edit.textChanged.connect(self.rebuild_plan)
        folder_row.addWidget(self.root_edit, 1)
        self.browse_button = QPushButton(self.tr("Browse..."))
        self.browse_button.clicked.connect(self._browse)
        folder_row.addWidget(self.browse_button)
        layout.addLayout(folder_row)

        options_row = QHBoxLayout()
        self.include_folders_checkbox = QCheckBox(self.tr("Rename folders too"))
        self.include_folders_checkbox.toggled.connect(self.rebuild_plan)
        options_row.addWidget(self.include_folders_checkbox)
        options_row.addWidget(QLabel(self.tr("Start number:")))
        self.start_number_spin = QSpinBox()
        self.start_number_spin.setRange(1, 1000000)
        self.start_number_spin.setValue(1)
        self.start_number_spin.valueChanged.connect(self.rebuild_plan)
        options_row.addWidget(self.start_number_spin)
        options_row.addWidget(QLabel(self.tr("Date:")))
        self.date_fmt_edit = QLineEdit(DEFAULT_DATE_FMT)
        self.date_fmt_edit.textChanged.connect(self.rebuild_plan)
        options_row.addWidget(self.date_fmt_edit)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        # Template row
        template_row = QHBoxLayout()
        template_row.addWidget(QLabel(self.tr("Template:")))
        self.template_edit = QLineEdit(self)
        self.template_edit.setPlaceholderText(self.tr("{n:03}_{name}  or  {parent}/{name}"))
        self.template_edit.textChanged.connect(self.rebuild_plan)
        template_row.addWidget(self.template_edit, 1)
        layout.addLayout(template_row)

        help_label = QLabel(self.tr("Tokens: ") + self.TOKEN_HELP)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: gray;")
        layout.addWidget(help_label)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([self.tr("Current (relative)"), self.tr("New (relative)")])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 360)
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

    # ─── Plan ──────────────────────────────────────────────────

    def _root(self) -> Path:
        return Path(self.root_edit.text()) if self.root_edit.text().strip() else self.root

    def rebuild_plan(self):
        root = self._root()
        template = self.template_edit.text()
        if not template or not root.is_dir():
            self.table.setRowCount(0)
            self._plan = TreePlan()
            return
        self._plan = build_tree_plan(
            root,
            template,
            include_folders=self.include_folders_checkbox.isChecked(),
            date_fmt=self.date_fmt_edit.text() or DEFAULT_DATE_FMT,
            start_number=self.start_number_spin.value(),
        )
        self._preview()

    def _preview(self):
        self.table.setRowCount(len(self._plan.items))
        for row, item in enumerate(self._plan.items):
            try:
                before = str(item.original.relative_to(self._root()))
            except ValueError:
                before = str(item.original)
            try:
                after = str(item.target.relative_to(self._root()))
            except ValueError:
                after = str(item.target)

            before_item = QTableWidgetItem(before)
            before_item.setFlags(before_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, before_item)

            after_item = QTableWidgetItem(after)
            after_item.setFlags(after_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if item.original == item.target:
                after_item.setForeground(Qt.GlobalColor.gray)
            elif item.target.exists():
                after_item.setForeground(Qt.GlobalColor.red)
                after_item.setToolTip(self.tr("Target already exists"))
            self.table.setItem(row, 1, after_item)

    # ─── Apply / undo ──────────────────────────────────────────

    def apply_batch(self):
        try:
            renamed = apply_tree_plan(self._plan)
        except ValueError as exc:
            self.apply_button.setText(self.tr("Fix conflicts first"))
            QMessageBox.warning(self, self.tr("Bulk Rename"), str(exc))
            return
        if not renamed:
            self.apply_button.setText(self.tr("Nothing to apply"))
            return
        operations = [RenameOperation(old, new) for old, new in renamed]
        if self.record_callback and operations:
            self.record_callback(
                CompositeOperation.from_operations(self.tr("Bulk rename (tree)"), operations)
            )
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

    def _browse(self):
        directory = QFileDialog.getExistingDirectory(self, self.tr("Choose folder"), str(self.root))
        if directory:
            self.root_edit.setText(directory)
            self.rebuild_plan()


__all__ = ["BulkRenameTreeDialog"]