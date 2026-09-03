"""History actions (undo/redo & operation recording) extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox

from lfmapp.services import CompositeOperation


class HistoryActionsMixin:
    # ─── Undo / Redo ───────────────────────────────────────────

    def record_operation(self, operation):
        self.operation_history.push(operation)
        self.update_undo_redo_actions()

    def create_operation_batch(self, label: str, total: int):
        if total <= 1:
            return None
        batch_id = object()
        self._operation_batches[batch_id] = {
            "label": label,
            "remaining": total,
            "operations": [],
        }
        return batch_id

    def record_batched_operation(self, batch_id, operation):
        if batch_id is None:
            self.record_operation(operation)
            return
        batch = self._operation_batches.get(batch_id)
        if batch is not None:
            batch["operations"].append(operation)

    def finish_operation_batch_item(self, batch_id):
        if batch_id is None:
            return
        batch = self._operation_batches.get(batch_id)
        if batch is None:
            return
        batch["remaining"] -= 1
        if batch["remaining"] > 0:
            return
        self._operation_batches.pop(batch_id, None)
        operations = batch["operations"]
        if len(operations) == 1:
            self.record_operation(operations[0])
        elif len(operations) > 1:
            self.record_operation(
                CompositeOperation.from_operations(batch["label"], operations)
            )

    def update_undo_redo_actions(self):
        if not hasattr(self, "undo_action") or not hasattr(self, "redo_action"):
            return
        undo_label = self.operation_history.next_undo_operation_label()
        redo_label = self.operation_history.next_redo_operation_label()
        self.undo_action.setText(
            self.tr("Undo {operation}").format(
                operation=self._translated_operation_label(undo_label),
            )
            if undo_label
            else self.tr("Undo")
        )
        self.undo_action.setEnabled(self.operation_history.can_undo())
        self.redo_action.setText(
            self.tr("Redo {operation}").format(
                operation=self._translated_operation_label(redo_label),
            )
            if redo_label
            else self.tr("Redo")
        )
        self.redo_action.setEnabled(self.operation_history.can_redo())

    def _translated_operation_label(self, label: str | None) -> str:
        """Translate operation-history labels at the Qt UI boundary."""
        if not label:
            return ""
        if label.startswith("Rename ") and " to " in label:
            original, renamed = label[len("Rename "):].rsplit(" to ", 1)
            return self.tr("Rename {original} to {renamed}").format(
                original=original,
                renamed=renamed,
            )
        if label.startswith("Create folder "):
            return self.tr("Create folder {name}").format(name=label[len("Create folder "):])
        if label.startswith("Create file "):
            return self.tr("Create file {name}").format(name=label[len("Create file "):])
        if label.startswith("Move ") and label.endswith(" to Trash"):
            name = label[len("Move "):-len(" to Trash")]
            return self.tr("Move {name} to Trash").format(name=name)
        if label.startswith("Move "):
            return self.tr("Move {name}").format(name=label[len("Move "):])
        if label.startswith("Copy "):
            return self.tr("Copy {name}").format(name=label[len("Copy "):])
        return label

    def undo_last_operation(self):
        if not self.operation_history.can_undo():
            return
        try:
            self._history_replaying = True
            operation = self.operation_history.undo()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Undo Error"),
                self.tr("Could not undo operation:\n{error}").format(error=exc),
            )
        else:
            self.statusBar().showMessage(self.tr("Undone: {label}").format(label=operation.label), 5000)
            self.refresh_view()
        finally:
            self._history_replaying = False
            self.update_undo_redo_actions()

    def redo_last_operation(self):
        if not self.operation_history.can_redo():
            return
        try:
            self._history_replaying = True
            operation = self.operation_history.redo()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Redo Error"),
                self.tr("Could not redo operation:\n{error}").format(error=exc),
            )
        else:
            self.statusBar().showMessage(self.tr("Redone: {label}").format(label=operation.label), 5000)
            self.refresh_view()
        finally:
            self._history_replaying = False
            self.update_undo_redo_actions()
