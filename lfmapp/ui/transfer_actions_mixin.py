"""Transfer actions (trash/delete/copy/move/send) extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QMessageBox

from lfmapp.services import (
    CompositeOperation,
    CopyOperation,
    CopyWorker,
    DeleteWorker,
    FileOperations,
    MoveOperation,
    MoveWorker,
    TrashOperation,
    TrashWorker,
)
from lfmapp.utils.open_with import send_email_with_attachments


class TransferActionsMixin:
    def trash_selected(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        self.statusBar().showMessage(
            self.tr("Moving {count} item(s) to trash...").format(count=len(paths)),
            0,
        )
        worker = TrashWorker(paths)
        self._trash_worker_operations[worker] = []
        worker.item_trashed.connect(
            lambda original, trashed, trashinfo, w=worker: self.on_item_trashed(
                w,
                original,
                trashed,
                trashinfo,
            )
        )
        self._register_worker(
            worker,
            self.tr("Sending items to Trash..."),
            finished_callback=lambda s, m, w=worker: self._on_trash_finished(w, s, m),
        )

    def on_item_trashed(self, worker, original_path: str, trashed_path: str, trashinfo_path: str):
        operation = TrashOperation(
            Path(original_path),
            Path(trashed_path),
            Path(trashinfo_path),
        )
        self._trash_worker_operations.setdefault(worker, []).append(operation)

    def _on_trash_finished(self, worker, success, message):
        operations = self._trash_worker_operations.pop(worker, [])
        if len(operations) == 1:
            self.record_operation(operations[0])
        elif len(operations) > 1:
            self.record_operation(
                CompositeOperation.from_operations(
                    self.tr("Move {count} item(s) to Trash").format(count=len(operations)),
                    operations,
                )
            )
        if success:
            self.statusBar().showMessage(message, 5000)
        else:
            QMessageBox.critical(
                self,
                self.tr("Trash Error"),
                self.tr("Could not move to trash:\n{message}").format(message=message),
            )
        self.refresh_view()
        self.update_trash_count()

    def on_files_dropped(self, paths: list, action: str):
        """Handle files/folders dropped onto the workspace.

        `paths` is a list of Path objects; `action` is 'copy' or 'move'.
        """
        destination = self.workspace.current_path()
        if not destination:
            return
        sources = [src for src in paths if src.exists()]
        if not sources:
            return
        action_label = self.tr("Copy") if action == "copy" else self.tr("Move")
        batch_id = self.create_operation_batch(
            self.tr("{action} {count} dropped item(s)").format(action=action_label, count=len(sources)),
            len(sources),
        )
        for src in sources:
            try:
                activity = self.tr("Copying") if action == "copy" else self.tr("Moving")
                if action == "copy":
                    worker = CopyWorker(src, destination)
                    copied_path = destination / src.name
                    callback = lambda s, m, w=worker, source=src, copied=copied_path, batch=batch_id: self._on_drop_worker_finished(
                        w,
                        s,
                        m,
                        copied_source=source,
                        copied_path=copied,
                        batch_id=batch,
                    )
                else:
                    worker = MoveWorker(src, destination)
                    moved_path = destination / src.name
                    callback = lambda s, m, w=worker, source=src, moved=moved_path, batch=batch_id: self._on_drop_worker_finished(
                        w,
                        s,
                        m,
                        source,
                        moved,
                        batch_id=batch,
                    )
                # Register worker and forward finished to drop handler
                self._register_worker(
                    worker,
                    self.tr("{activity} {name}...").format(activity=activity, name=src.name),
                    finished_callback=callback,
                )
                self._drop_workers.append(worker)
                self.statusBar().showMessage(
                    self.tr("{activity} {name}...").format(activity=activity, name=src.name),
                    0,
                )
            except Exception as exc:
                self.finish_operation_batch_item(batch_id)
                QMessageBox.critical(
                    self,
                    self.tr("Drop Error"),
                    self.tr("Could not perform {action} on {path}:\n{error}").format(
                        action=action,
                        path=src,
                        error=exc,
                    ),
                )

    def _on_drop_worker_finished(
        self,
        worker,
        success,
        message,
        source=None,
        moved_path=None,
        copied_source=None,
        copied_path=None,
        batch_id=None,
    ):
        try:
            if worker in self._drop_workers:
                self._drop_workers.remove(worker)
            if success:
                if source is not None and moved_path is not None:
                    self.record_batched_operation(batch_id, MoveOperation(source, moved_path))
                if copied_source is not None and copied_path is not None:
                    operation = self.create_copy_operation(copied_source, copied_path)
                    if operation is not None:
                        self.record_batched_operation(batch_id, operation)
                self.statusBar().showMessage(message, 5000)
            else:
                QMessageBox.critical(self, self.tr("Operation Error"), message)
            self.refresh_view()
        finally:
            self.finish_operation_batch_item(batch_id)

    def delete_selected(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        answer = QMessageBox.question(
            self,
            self.tr("Delete Permanently"),
            self.tr(
                "Are you sure you want to permanently delete {count} item(s)?\n"
                "This action cannot be undone."
            ).format(count=len(paths)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.statusBar().showMessage(self.tr("Deleting {count} item(s)...").format(count=len(paths)), 0)
        worker = DeleteWorker(paths)
        self._register_worker(
            worker,
            self.tr("Deleting selected item(s)..."),
            finished_callback=self._on_delete_finished,
        )

    def _on_delete_finished(self, success, message):
        if success:
            self.statusBar().showMessage(message, 5000)
        else:
            QMessageBox.critical(
                self,
                self.tr("Delete Error"),
                self.tr("Could not delete:\n{message}").format(message=message),
            )
        self.refresh_view()

    def copy_selected_to(self):
        paths = [path for path in self.workspace.selected_paths() if path.exists()]
        if not paths:
            return
        destination = FileOperations.choose_folder(self, self.tr("Copy to"), str(paths[0].parent))
        if not destination:
            return
        batch_id = self.create_operation_batch(self.tr("Copy {count} item(s)").format(count=len(paths)), len(paths))
        for path in paths:
            try:
                worker = CopyWorker(path, destination)
                copied_path = destination / path.name
                self._register_worker(
                    worker,
                    self.tr("Copying {name}...").format(name=path.name),
                    finished_callback=lambda s, m, source=path, copied=copied_path, batch=batch_id: self._on_copy_finished(
                        source,
                        copied,
                        s,
                        m,
                        self.tr("Copy Error"),
                        batch,
                    ),
                )
            except Exception as exc:
                self.finish_operation_batch_item(batch_id)
                QMessageBox.critical(
                    self,
                    self.tr("Error"),
                    self.tr("Could not copy:\n{error}").format(error=exc),
                )
        self.statusBar().showMessage(self.tr("Copying {count} item(s)...").format(count=len(paths)), 0)

    def move_selected_to(self):
        paths = [path for path in self.workspace.selected_paths() if path.exists()]
        if not paths:
            return
        destination = FileOperations.choose_folder(self, self.tr("Move to"), str(paths[0].parent))
        if not destination:
            return
        batch_id = self.create_operation_batch(self.tr("Move {count} item(s)").format(count=len(paths)), len(paths))
        for path in paths:
            try:
                worker = MoveWorker(path, destination)
                moved_path = destination / path.name
                self._register_worker(
                    worker,
                    self.tr("Moving {name}...").format(name=path.name),
                    finished_callback=lambda s, m, source=path, moved=moved_path, batch=batch_id: self._on_move_finished(
                        source,
                        moved,
                        s,
                        m,
                        self.tr("Move Error"),
                        batch,
                    ),
                )
            except Exception as exc:
                self.finish_operation_batch_item(batch_id)
                QMessageBox.critical(
                    self,
                    self.tr("Error"),
                    self.tr("Could not move:\n{error}").format(error=exc),
                )
        self.statusBar().showMessage(self.tr("Moving {count} item(s)...").format(count=len(paths)), 0)

    def _on_move_finished(
        self,
        source: Path,
        moved_path: Path,
        success,
        message,
        error_title: str,
        batch_id=None,
    ):
        try:
            if success:
                self.record_batched_operation(batch_id, MoveOperation(source, moved_path))
                self.statusBar().showMessage(message, 5000)
            else:
                QMessageBox.critical(
                    self,
                    error_title,
                    self.tr("Operation failed:\n{message}").format(message=message),
                )
            self.refresh_view()
        finally:
            self.finish_operation_batch_item(batch_id)

    def _on_copy_finished(
        self,
        source: Path,
        copied_path: Path,
        success,
        message,
        error_title: str,
        batch_id=None,
    ):
        try:
            if success:
                operation = self.create_copy_operation(source, copied_path)
                if operation is not None:
                    self.record_batched_operation(batch_id, operation)
                self.statusBar().showMessage(message, 5000)
            else:
                QMessageBox.critical(
                    self,
                    error_title,
                    self.tr("Operation failed:\n{message}").format(message=message),
                )
            self.refresh_view()
        finally:
            self.finish_operation_batch_item(batch_id)

    def create_copy_operation(self, source: Path, copied_path: Path):
        if not copied_path.exists() or not source.exists():
            return None
        try:
            return CopyOperation.from_completed_copy(source, copied_path)
        except Exception:
            return None

    def record_copy_operation(self, source: Path, copied_path: Path):
        operation = self.create_copy_operation(source, copied_path)
        if operation is not None:
            self.record_operation(operation)

    def send_selected_to_desktop(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        try:
            destination = FileOperations.ensure_desktop_directory()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Could not prepare Desktop folder:\n{error}").format(error=exc),
            )
            return

        paths = [path for path in paths if path.exists()]
        if not paths:
            return
        batch_id = self.create_operation_batch(
            self.tr("Send {count} item(s) to Desktop").format(count=len(paths)),
            len(paths),
        )

        for path in paths:
            if not path.exists():
                continue
            worker = CopyWorker(path, destination)
            copied_path = destination / path.name
            self._register_worker(
                worker,
                self.tr("Sending {name} to Desktop...").format(name=path.name),
                finished_callback=lambda s, m, source=path, copied=copied_path, batch=batch_id: self._on_send_to_desktop_finished(
                    source,
                    copied,
                    s,
                    m,
                    batch,
                ),
            )
        self.statusBar().showMessage(
            self.tr("Sending {count} item(s) to Desktop...").format(count=len(paths)),
            0,
        )

    def _on_send_to_desktop_finished(self, source: Path, copied_path: Path, success, message, batch_id=None):
        try:
            if success:
                operation = self.create_copy_operation(source, copied_path)
                if operation is not None:
                    self.record_batched_operation(batch_id, operation)
                self.statusBar().showMessage(message, 5000)
            else:
                QMessageBox.critical(
                    self,
                    self.tr("Send to Desktop Error"),
                    self.tr("Could not send to Desktop:\n{message}").format(message=message),
                )
        finally:
            self.finish_operation_batch_item(batch_id)

    def send_selected_to_email(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        if any(path.is_dir() for path in paths):
            QMessageBox.warning(
                self,
                self.tr("Send to Email"),
                self.tr("Only files can be attached to an email. Compress folders to ZIP first."),
            )
            return

        if send_email_with_attachments(paths):
            self.statusBar().showMessage(
                self.tr("Opening email composer for {count} file(s)...").format(count=len(paths)),
                5000,
            )
        else:
            QMessageBox.critical(
                self,
                self.tr("Send to Email Error"),
                self.tr("Could not open the default email composer. Make sure xdg-email and a mail client are configured."),
            )
