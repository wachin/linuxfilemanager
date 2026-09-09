"""Two-phase folder synchronization dialog.

Phase 1 (compare): The user picks source/destination folders, chooses the
mode (unidirectional/bidirectional), update criterion, and whether to delete
orphans.  Clicking "Compare" runs the comparison and shows the results.

Phase 2 (review): The table lists every file with its planned action
(Copy →, Delete ✗, Nothing —).  The user can change the action per item,
hide unaffected items, and filter by action.

Phase 3 (apply): Clicking "Apply" executes the confirmed actions through
the normal copy/move/delete workers.
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
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from lfmapp.services.sync_service import (
    SyncAction,
    SyncActionType,
    SyncCompareWorker,
    SyncMode,
    SyncPlan,
    UpdateCriterion,
    apply_plan,
    compare_folders,
)


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            if unit == "B":
                return f"{size} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


_ACTION_LABELS = {
    SyncActionType.COPY: "Copy →",
    SyncActionType.DELETE: "Delete ✗",
    SyncActionType.NOTHING: "—",
    SyncActionType.CONFLICT: "Conflict ?",
}


class SyncDialog(QDialog):
    """Two-phase folder synchronization dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Folder Synchronization"))
        self.setMinimumSize(780, 520)
        self.resize(900, 600)
        self._plan: SyncPlan | None = None
        self._worker: SyncCompareWorker | None = None
        self._build_ui()

    # -- UI ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- Source / Destination -------------------------------------------
        paths_group = QGroupBox(self.tr("Locations"))
        paths_layout = QVBoxLayout(paths_group)

        row_src = QHBoxLayout()
        row_src.addWidget(QLabel(self.tr("Source")))
        self._src_edit = QLineEdit()
        self._src_edit.setPlaceholderText(self.tr("Folder to sync from"))
        row_src.addWidget(self._src_edit, 1)
        self._src_browse = QPushButton(self.tr("Browse…"))
        row_src.addWidget(self._src_browse)
        paths_layout.addLayout(row_src)

        row_dst = QHBoxLayout()
        row_dst.addWidget(QLabel(self.tr("Destination")))
        self._dst_edit = QLineEdit()
        self._dst_edit.setPlaceholderText(self.tr("Folder to sync to"))
        row_dst.addWidget(self._dst_edit, 1)
        self._dst_browse = QPushButton(self.tr("Browse…"))
        row_dst.addWidget(self._dst_browse)
        paths_layout.addLayout(row_dst)

        root.addWidget(paths_group)

        # --- Options --------------------------------------------------------
        opts_group = QGroupBox(self.tr("Options"))
        opts_layout = QHBoxLayout(opts_group)

        opts_layout.addWidget(QLabel(self.tr("Mode")))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([
            self.tr("Source → Destination"),
            self.tr("Newest wins (bidirectional)"),
        ])
        opts_layout.addWidget(self._mode_combo)

        opts_layout.addWidget(QLabel(self.tr("Criterion")))
        self._criterion_combo = QComboBox()
        self._criterion_combo.addItems([
            self.tr("Name only"),
            self.tr("Name + Size"),
            self.tr("Name + MTime"),
            self.tr("Name + Size + MTime"),
        ])
        self._criterion_combo.setCurrentIndex(3)
        opts_layout.addWidget(self._criterion_combo)

        self._delete_orphans_cb = QCheckBox(self.tr("Delete orphans"))
        opts_layout.addWidget(self._delete_orphans_cb)

        self._compare_btn = QPushButton(self.tr("Compare"))
        self._compare_btn.clicked.connect(self._on_compare)
        opts_layout.addWidget(self._compare_btn)

        root.addWidget(opts_group)

        # --- Results table --------------------------------------------------
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            self.tr("Action"), self.tr("File"), self.tr("Source size"),
            self.tr("Dest size"), self.tr("Reason"),
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setAlternatingRowColors(True)
        root.addWidget(self._table, 1)

        # --- Filter row -----------------------------------------------------
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(self.tr("Show")))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            self.tr("All"),
            self.tr("Copy only"),
            self.tr("Delete only"),
            self.tr("Changes only"),
        ])
        self._filter_combo.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_combo)
        self._hide_unchanged_cb = QCheckBox(self.tr("Hide unchanged"))
        self._hide_unchanged_cb.stateChanged.connect(self._apply_filter)
        filter_row.addWidget(self._hide_unchanged_cb)
        filter_row.addStretch()
        root.addLayout(filter_row)

        # --- Buttons --------------------------------------------------------
        btn_box = QDialogButtonBox()
        self._apply_btn = btn_box.addButton(
            self.tr("Apply"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_box.addButton(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self._on_close)
        root.addWidget(btn_box)

        # --- Summary --------------------------------------------------------
        self._summary = QLabel("")
        root.addWidget(self._summary)

    # -- Compare phase -------------------------------------------------------

    def _on_compare(self) -> None:
        src = Path(self._src_edit.text().strip())
        dst = Path(self._dst_edit.text().strip())
        if not src.is_dir():
            QMessageBox.warning(self, self.tr("Error"), self.tr("Source folder does not exist."))
            return
        if not dst.is_dir():
            QMessageBox.warning(self, self.tr("Error"), self.tr("Destination folder does not exist."))
            return

        mode_idx = self._mode_combo.currentIndex()
        mode = SyncMode.BIDIRECTIONAL if mode_idx == 1 else SyncMode.UNIDIRECTIONAL

        criterion_idx = self._criterion_combo.currentIndex()
        criterion = [
            UpdateCriterion.NAME,
            UpdateCriterion.SIZE,
            UpdateCriterion.MTIME,
            UpdateCriterion.MTIME_SIZE,
        ][criterion_idx]

        delete_orphans = self._delete_orphans_cb.isChecked()

        self._compare_btn.setEnabled(False)
        self._summary.setText(self.tr("Comparing…"))

        self._worker = SyncCompareWorker(
            src, dst,
            mode=mode,
            criterion=criterion,
            delete_orphans=delete_orphans,
            parent=self,
        )
        self._worker.plan_ready.connect(self._on_plan_ready)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    def _on_plan_ready(self, plan: SyncPlan) -> None:
        self._plan = plan
        self._populate_table(plan)
        self._update_summary()
        self._compare_btn.setEnabled(True)
        self._apply_btn.setEnabled(len(plan.actions) > 0)

    def _on_worker_done(self) -> None:
        self._worker = None
        self._compare_btn.setEnabled(True)

    # -- Table population ----------------------------------------------------

    def _populate_table(self, plan: SyncPlan) -> None:
        self._table.setRowCount(len(plan.actions))
        for row, action in enumerate(plan.actions):
            # Action column (editable combo)
            action_label = _ACTION_LABELS.get(action.action, "?")
            action_item = QTableWidgetItem(action_label)
            action_item.setFlags(action_item.flags() | Qt.ItemFlag.ItemIsEditable)
            action_item.setData(Qt.ItemDataRole.UserRole, action)
            if action.action == SyncActionType.COPY:
                action_item.setForeground(Qt.GlobalColor.darkGreen)
            elif action.action == SyncActionType.DELETE:
                action_item.setForeground(Qt.GlobalColor.red)
            self._table.setItem(row, 0, action_item)

            # File path
            rel = ""
            try:
                rel = str(action.source.relative_to(plan.source))
            except ValueError:
                rel = str(action.source)
            self._table.setItem(row, 1, QTableWidgetItem(rel))

            # Sizes
            self._table.setItem(row, 2, QTableWidgetItem(_human_size(action.source_size)))
            self._table.setItem(row, 3, QTableWidgetItem(_human_size(action.dest_size)))

            # Reason
            self._table.setItem(row, 4, QTableWidgetItem(action.reason))

    def _update_summary(self) -> None:
        if not self._plan:
            self._summary.setText("")
            return
        copies = len(self._plan.to_copy)
        deletes = len(self._plan.to_delete)
        total = _human_size(self._plan.total_size)
        self._summary.setText(
            self.tr("{total} to copy, {deletes} to delete ({size})").format(
                total=copies, deletes=deletes, size=total,
            )
        )

    # -- Filter --------------------------------------------------------------

    def _apply_filter(self) -> None:
        filter_idx = self._filter_combo.currentIndex()
        hide_unchanged = self._hide_unchanged_cb.isChecked()

        for row in range(self._table.rowCount()):
            action_item = self._table.item(row, 0)
            if not action_item:
                continue
            action: SyncAction = action_item.data(Qt.ItemDataRole.UserRole)
            if not action:
                continue

            show = True
            if filter_idx == 1:  # Copy only
                show = action.action == SyncActionType.COPY
            elif filter_idx == 2:  # Delete only
                show = action.action == SyncActionType.DELETE
            elif filter_idx == 3:  # Changes only
                show = action.action in (SyncActionType.COPY, SyncActionType.DELETE)

            if hide_unchanged and action.action == SyncActionType.NOTHING:
                show = False

            self._table.setRowHidden(row, not show)

    # -- Apply phase ---------------------------------------------------------

    def _on_apply(self) -> None:
        if not self._plan:
            return
        # Collect user-modified actions from the table.
        confirmed = []
        for row in range(self._table.rowCount()):
            action_item = self._table.item(row, 0)
            if not action_item:
                continue
            action: SyncAction = action_item.data(Qt.ItemDataRole.UserRole)
            if action and action.action != SyncActionType.NOTHING:
                confirmed.append(action)

        if not confirmed:
            return

        copies = sum(1 for a in confirmed if a.action == SyncActionType.COPY)
        deletes = sum(1 for a in confirmed if a.action == SyncActionType.DELETE)
        answer = QMessageBox.question(
            self,
            self.tr("Confirm synchronization"),
            self.tr(
                "Apply {copies} copy(ies) and {deletes} deletion(s)?"
            ).format(copies=copies, deletes=deletes),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        # Execute through the parent's operations.
        plan = SyncPlan(
            actions=confirmed,
            source=self._plan.source,
            destination=self._plan.destination,
            mode=self._plan.mode,
            criterion=self._plan.criterion,
        )
        results = apply_plan(plan)
        if self.parent() and hasattr(self.parent(), "apply_sync_results"):
            self.parent().apply_sync_results(results)
        self.accept()

    def _on_close(self) -> None:
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
