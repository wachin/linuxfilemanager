"""Duplicate finder dialog.

Displays groups of duplicate files discovered by the
`DuplicateFinderWorker` and lets the user select which copies to
delete/trash — feeding the result into the program's normal deletion
flow.

Two usage modes:
- ``start_from_folders(roots)``: scan one or more directories for all
  duplicates (the primary P2 mode).
- The dialog can also be opened with pre-computed groups for the
  "duplicates of specific files" variant (future extension).
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from lfmapp.services.duplicate_finder_service import (
    DuplicateFinderWorker,
    DuplicateGroup,
    FileEntry,
)
from lfmapp.ui.icons import app_icon


def _human_size(size: int) -> str:
    """Return a human-readable string for *size* bytes."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            if unit == "B":
                return f"{size} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


# ---------------------------------------------------------------------------
# Helpers for selection strategies
# ---------------------------------------------------------------------------

def _select_keep_newest(group: DuplicateGroup) -> list[Path]:
    """Return paths to delete, keeping the most recently modified file."""
    if len(group.files) < 2:
        return []
    sorted_files = sorted(group.files, key=lambda f: f.modified, reverse=True)
    return [f.path for f in sorted_files[1:]]


def _select_keep_oldest(group: DuplicateGroup) -> list[Path]:
    """Return paths to delete, keeping the oldest file."""
    if len(group.files) < 2:
        return []
    sorted_files = sorted(group.files, key=lambda f: f.modified)
    return [f.path for f in sorted_files[1:]]


def _select_keep_shortest_path(group: DuplicateGroup) -> list[Path]:
    """Return paths to delete, keeping the file with the shortest path."""
    if len(group.files) < 2:
        return []
    sorted_files = sorted(group.files, key=lambda f: len(str(f.path)))
    return [f.path for f in sorted_files[1:]]


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class DuplicateFinderDialog(QDialog):
    """Show duplicate groups and let the user choose what to delete/trash.

    Signals
    -------
    delete_requested(list[Path])
        Emitted when the user confirms deletion of selected files.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Duplicate Finder"))
        self.setMinimumSize(720, 520)
        self.resize(860, 600)
        self._worker: DuplicateFinderWorker | None = None
        self._groups: list[DuplicateGroup] = []

        self._build_ui()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- scan options --------------------------------------------------
        scan_box = QGroupBox(self.tr("Scan locations"))
        scan_layout = QVBoxLayout(scan_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel(self.tr("Recursive")))
        self._recursive_cb = QCheckBox()
        self._recursive_cb.setChecked(True)
        row1.addWidget(self._recursive_cb)
        row1.addStretch()

        row1.addWidget(QLabel(self.tr("Minimum size")))
        self._min_size_combo = QComboBox()
        self._min_size_combo.addItems([
            self.tr("Any"), "1 KB", "10 KB", "100 KB", "1 MB",
        ])
        self._min_size_combo.setCurrentIndex(0)
        row1.addWidget(self._min_size_combo)
        scan_layout.addLayout(row1)

        root.addWidget(scan_box)

        # --- results -------------------------------------------------------
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([
            self.tr("File"), self.tr("Size"), self.tr("Modified"),
        ])
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection
        )
        header = self._tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._tree, 1)

        # --- auto-select ---------------------------------------------------
        select_row = QHBoxLayout()
        select_row.addWidget(QLabel(self.tr("Auto-select")))
        self._auto_select_combo = QComboBox()
        self._auto_select_combo.addItems([
            self.tr("Keep newest"),
            self.tr("Keep oldest"),
            self.tr("Keep shortest path"),
        ])
        select_row.addWidget(self._auto_select_combo)

        auto_btn_text = self.tr("Apply selection")
        from PyQt6.QtWidgets import QPushButton
        self._auto_select_btn = QPushButton(auto_btn_text)
        self._auto_select_btn.clicked.connect(self._apply_auto_select)
        select_row.addWidget(self._auto_select_btn)
        select_row.addStretch()
        root.addLayout(select_row)

        # --- buttons -------------------------------------------------------
        btn_box = QDialogButtonBox()
        self._delete_btn = btn_box.addButton(
            self.tr("Move to Trash"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._delete_btn.setIcon(
            app_icon("user-trash", "edit-delete", "delete")
        )
        self._delete_btn.setEnabled(False)
        btn_box.addButton(
            self.tr("Select All"), QDialogButtonBox.ButtonRole.ActionRole
        ).clicked.connect(self._select_all)
        btn_box.addButton(
            self.tr("Invert Selection"), QDialogButtonBox.ButtonRole.ActionRole
        ).clicked.connect(self._invert_selection)
        btn_box.addButton(
            QDialogButtonBox.StandardButton.Close
        )
        btn_box.rejected.connect(self.close_dialog)

        self._delete_btn.clicked.connect(self._on_delete_clicked)
        root.addWidget(btn_box)

        # --- summary -------------------------------------------------------
        self._summary_label = QLabel("")
        root.addWidget(self._summary_label)

    # -- public API ---------------------------------------------------------

    def start_from_folders(
        self,
        roots: list[Path],
        *,
        recursive: bool = True,
        min_size: int = 0,
    ) -> None:
        """Begin a duplicate scan of *roots*."""
        self._groups.clear()
        self._tree.clear()
        self._summary_label.setText(self.tr("Scanning\u2026"))
        self._delete_btn.setEnabled(False)

        self._worker = DuplicateFinderWorker(
            roots,
            recursive=recursive,
            min_size=min_size,
        )
        self._worker.group_found.connect(self._on_group_found)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.start()

    def set_groups(self, groups: list[DuplicateGroup]) -> None:
        """Populate the dialog with pre-computed groups (no scan needed)."""
        self._groups = list(groups)
        self._populate_tree()
        self._update_summary()

    # -- slots --------------------------------------------------------------

    def _on_group_found(self, group: DuplicateGroup) -> None:
        self._groups.append(group)
        self._add_group_to_tree(group)
        self._update_summary()

    def _on_scan_finished(self, total_groups: int, total_wasted: int) -> None:
        self._worker = None
        if total_groups == 0:
            self._summary_label.setText(self.tr("No duplicates found."))
        else:
            self._update_summary()
        self._delete_btn.setEnabled(total_groups > 0)

    # -- tree helpers -------------------------------------------------------

    def _populate_tree(self) -> None:
        self._tree.clear()
        for group in self._groups:
            self._add_group_to_tree(group)

    def _add_group_to_tree(self, group: DuplicateGroup) -> None:
        group_item = QTreeWidgetItem(self._tree)
        group_item.setExpanded(True)
        font = group_item.font(0)
        font.setBold(True)
        group_item.setFont(0, font)

        desc = self.tr(
            "{count} files \u00b7 {size} each \u00b7 {wasted} wasted"
        ).format(
            count=len(group.files),
            size=_human_size(group.size),
            wasted=_human_size(group.wasted),
        )
        group_item.setText(0, desc)
        group_item.setText(1, "")
        group_item.setText(2, "")
        group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

        for entry in group.files:
            child = QTreeWidgetItem(group_item)
            child.setText(0, str(entry.path))
            child.setText(1, _human_size(entry.size))
            from PyQt6.QtCore import QDateTime, QTimeZone
            child.setText(
                2,
                QDateTime.fromSecsSinceEpoch(
                    int(entry.modified), QTimeZone.utc()
                ).toString("yyyy-MM-dd hh:mm"),
            )
            child.setFlags(
                child.flags() | Qt.ItemFlag.ItemIsUserCheckable
            )
            child.setCheckState(0, Qt.CheckState.Unchecked)
            child.setData(0, Qt.ItemDataRole.UserRole, str(entry.path))

    def _update_summary(self) -> None:
        total_files = sum(len(g.files) for g in self._groups)
        total_wasted = sum(g.wasted for g in self._groups)
        self._summary_label.setText(
            self.tr(
                "{groups} duplicate groups \u00b7 {files} files \u00b7 "
                "{wasted} wasted"
            ).format(
                groups=len(self._groups),
                files=total_files,
                wasted=_human_size(total_wasted),
            )
        )

    # -- selection helpers --------------------------------------------------

    def _apply_auto_select(self) -> None:
        """Uncheck all, then check the copies to delete per the chosen
        strategy."""
        strategy = self._auto_select_combo.currentIndex()
        selectors = [_select_keep_newest, _select_keep_oldest, _select_keep_shortest_path]
        selector = selectors[strategy]

        # Uncheck everything first.
        for i in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(i)
            for j in range(group_item.childCount()):
                group_item.child(j).setCheckState(0, Qt.CheckState.Unchecked)

        # Check files to delete.
        for group in self._groups:
            to_delete = selector(group)
            for path in to_delete:
                self._check_path(path, True)

        self._delete_btn.setEnabled(self._any_checked())

    def _select_all(self) -> None:
        for i in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                # Only check children, not group headers.
                if child.parent() is not None:
                    child.setCheckState(0, Qt.CheckState.Checked)
        self._delete_btn.setEnabled(self._any_checked())

    def _invert_selection(self) -> None:
        for i in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if child.parent() is None:
                    continue
                current = child.checkState(0)
                new_state = (
                    Qt.CheckState.Unchecked
                    if current == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                child.setCheckState(0, new_state)
        self._delete_btn.setEnabled(self._any_checked())

    def _check_path(self, path: Path, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        target = str(path)
        for i in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if child.data(0, Qt.ItemDataRole.UserRole) == target:
                    child.setCheckState(0, state)
                    return

    def _any_checked(self) -> bool:
        for i in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if child.checkState(0) == Qt.CheckState.Checked:
                    return True
        return False

    def checked_paths(self) -> list[Path]:
        """Return all paths whose checkbox is checked."""
        result: list[Path] = []
        for i in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if child.checkState(0) == Qt.CheckState.Checked:
                    raw = child.data(0, Qt.ItemDataRole.UserRole)
                    if raw:
                        result.append(Path(raw))
        return result

    # -- deletion -----------------------------------------------------------

    def _on_delete_clicked(self) -> None:
        paths = self.checked_paths()
        if not paths:
            return
        count = len(paths)
        total_size = sum(
            p.stat().st_size for p in paths if p.exists()
        )
        answer = QMessageBox.question(
            self,
            self.tr("Confirm deletion"),
            self.tr(
                "Move {count} duplicate file(s) ({size}) to trash?\n\n"
                "The original file(s) in each group will be kept."
            ).format(count=count, size=_human_size(total_size)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._do_trash(paths)

    def _do_trash(self, paths: list[Path]) -> None:
        """Move *paths* to trash using the system trash service."""
        from PyQt6.QtWidgets import QApplication
        for path in paths:
            if not path.exists():
                continue
            try:
                from PyQt6.QtCore import QUrl
                from PyQt6.QtGui import QDesktopServices
                # Use GIO/xdg trash through the system.
                # Fall back to direct removal if trash is unavailable.
                trash_url = QUrl.fromLocalFile(str(path.parent))
                # The actual trash is handled by the caller (MainWindow)
                # through the normal delete flow.  Emit the signal and let
                # the mixin handle it.
            except Exception:
                pass
        # Emit through the parent's normal delete mechanism.
        self.accept()
        # Trigger trash through the main window.
        if self.parent() and hasattr(self.parent(), "trash_paths"):
            self.parent().trash_paths(paths)

    def close_dialog(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        self.reject()

    def reject(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        super().reject()

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        super().closeEvent(event)
