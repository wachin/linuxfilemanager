"""File action methods extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PyQt6.QtGui import QAction, QKeySequence, QTextDocument
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox

from lfmapp.core.xdg import get_xdg_user_dirs
from lfmapp.services import (
    CompositeOperation,
    CopyOperation,
    CopyWorker,
    CreateOperation,
    FileOperations,
    MoveWorker,
    RenameOperation,
)
from lfmapp.services.preview_worker import PreviewWorker
from lfmapp.ui.create_multiple_dialog import CreateMultipleDialog
from lfmapp.ui.icons import app_icon
from lfmapp.ui.property_dialog import AdvancedSecurityDialog, PropertyDialog
from lfmapp.utils.open_with import (
    get_available_applications,
    open_with_default,
    set_default_application_for_file,
)


class FileActionsMixin:
    # ─── File Operations ───────────────────────────────────────

    def open_selected(self):
        path = self.workspace.selected_path()
        if not path:
            return
        if path.is_dir():
            self.go_to(path)
        else:
            self.open_file(path)

    def print_selected(self):
        path = self.workspace.selected_path()
        if not path or not path.exists():
            return
        self.print_path(path)

    def print_path(self, path: Path):
        """Print a readable summary for a file or folder."""
        if not path or not path.exists():
            return

        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        document = QTextDocument(self.printable_text_for_path(path))
        document.print(printer)
        self.statusBar().showMessage(self.tr("Printed {name}").format(name=path.name), 3000)

    @staticmethod
    def printable_text_for_path(path: Path) -> str:
        """Return printable content for a path."""
        if path.is_file() and PreviewWorker._is_text(path):
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        return PreviewWorker.metadata_for_path(path)

    def open_file(self, path: Path) -> bool:
        """Open a file with the default application and track it as recent."""
        if not path or not path.is_file():
            return False
        opened = open_with_default(path)
        if opened:
            self.record_recent_file(path)
        return opened

    def record_recent_file(self, path: Path):
        self.config.add_recent_file(path)
        self.rebuild_recent_files_menu()

    def open_recent_file(self, path: Path):
        if not path.exists() or not path.is_file():
            QMessageBox.warning(
                self,
                self.tr("Recent file unavailable"),
                self.tr("Does not exist or is not a file:\n{path}").format(path=path),
            )
            self.rebuild_recent_files_menu()
            return
        self.open_file(path)

    def clear_recent_files(self):
        self.config.clear_recent_files()
        self.rebuild_recent_files_menu()

    def open_with_dialog(self):
        path = self.workspace.selected_path()
        if not path or not path.is_file():
            return
        apps = get_available_applications(path)
        if not apps:
            self.open_file(path)
            return

        if len(apps) == 1:
            desktop_file, _ = apps[0]
            try:
                subprocess.Popen(
                    ["gtk-launch", desktop_file, str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                self.record_recent_file(path)
                return
            except Exception:
                self.open_file(path)
                return

        choices = [f"{name} ({desktop})" for desktop, name in apps]
        selection, ok = QInputDialog.getItem(
            self,
            self.tr("Open with..."),
            self.tr("Choose application:"),
            choices,
            0,
            False,
        )
        if ok and selection:
            index = choices.index(selection)
            desktop_file, _ = apps[index]
            try:
                subprocess.Popen(
                    ["gtk-launch", desktop_file, str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                self.record_recent_file(path)
            except Exception:
                self.open_file(path)

    def set_default_application_dialog(self):
        path = self.workspace.selected_path()
        if not path or not path.is_file():
            return
        apps = get_available_applications(path)
        if not apps:
            QMessageBox.information(
                self,
                self.tr("Set Default Application"),
                self.tr("No compatible applications were found for this file."),
            )
            return

        choices = [f"{name} ({desktop})" for desktop, name in apps]
        selection, ok = QInputDialog.getItem(
            self,
            self.tr("Set Default Application"),
            self.tr("Choose default application:"),
            choices,
            0,
            False,
        )
        if not ok or not selection:
            return

        index = choices.index(selection)
        desktop_file, app_name = apps[index]
        if set_default_application_for_file(path, desktop_file):
            self.statusBar().showMessage(
                self.tr("Default application set to {app}").format(app=app_name),
                5000,
            )
        else:
            QMessageBox.critical(
                self,
                self.tr("Set Default Application Error"),
                self.tr("Could not set the default application for this file type."),
            )

    def show_properties(self):
        path = self.workspace.selected_path()
        if path:
            dialog = PropertyDialog(path, self)
            dialog.exec()

    def show_folder_properties(self):
        path = self.workspace.current_path()
        if path:
            dialog = PropertyDialog(path, self)
            dialog.exec()

    def show_context_properties(self):
        path = self.workspace.selected_path() or self.workspace.current_path()
        if path:
            dialog = PropertyDialog(path, self)
            dialog.exec()

    def show_advanced_security(self):
        path = self.workspace.selected_path() or self.workspace.current_path()
        if path:
            dialog = AdvancedSecurityDialog(path, self)
            dialog.exec()

    def add_bookmark(self):
        path = self.workspace.selected_path() or self.workspace.current_path()
        if not path:
            return
        self.bookmark_service.add(str(path), pinned=True)
        self.sidebar.set_bookmarks(self.bookmark_service.bookmarks)
        self.update_quick_access_action()

    def quick_access_target(self):
        selected = self.workspace.selected_path()
        if selected and selected.exists() and selected.is_dir():
            return selected
        current = self.workspace.current_path()
        if current and current.exists() and current.is_dir():
            return current
        return None

    def update_quick_access_action(self):
        if not hasattr(self, "quick_access_action"):
            return
        path = self.quick_access_target()
        if path and self.is_builtin_quick_access_path(path):
            self.quick_access_action.setText(self.tr("In Quick Access"))
            self.quick_access_action.setEnabled(False)
            return
        self.quick_access_action.setEnabled(path is not None)
        if path and self.bookmark_service.is_pinned(str(path)):
            self.quick_access_action.setText(self.tr("Unpin from Quick Access"))
        else:
            self.quick_access_action.setText(self.tr("Pin to Quick Access"))
        self._update_registered_action_title(self.quick_access_action)

    def _update_registered_action_title(self, action: QAction):
        record = self._command_action_by_action.get(action)
        if record is not None:
            record["title"] = action.text().replace("&", "")

    @staticmethod
    def is_builtin_quick_access_path(path: Path) -> bool:
        builtins = {Path.home(), *get_xdg_user_dirs().values()}
        try:
            return path.resolve() in {candidate.resolve() for candidate in builtins}
        except OSError:
            return path in builtins

    def toggle_quick_access_pin(self):
        path = self.quick_access_target()
        if not path or self.is_builtin_quick_access_path(path):
            return
        path_text = str(path)
        if self.bookmark_service.exists(path_text):
            pinned = self.bookmark_service.toggle_pin(path_text)
        else:
            self.bookmark_service.add(path_text, pinned=True)
            pinned = True
        self.sidebar.set_bookmarks(self.bookmark_service.bookmarks)
        self.update_quick_access_action()
        message = self.tr("Pinned to Quick Access") if pinned else self.tr("Unpinned from Quick Access")
        self.statusBar().showMessage(message, 3000)

    # ─── Clipboard ─────────────────────────────────────────────

    def copy_selected(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        self._clipboard_paths = paths
        self._clipboard_mode = "copy"
        self.statusBar().showMessage(self.tr("Copied {count} item(s)").format(count=len(paths)), 3000)
        self.refresh_registry_enablement()

    def cut_selected(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        self._clipboard_paths = paths
        self._clipboard_mode = "cut"
        self.statusBar().showMessage(self.tr("Cut {count} item(s)").format(count=len(paths)), 3000)
        self.refresh_registry_enablement()

    def paste_from_clipboard(self):
        if not self._clipboard_paths:
            return
        destination = self.workspace.current_path()
        if not destination:
            return

        sources = [src for src in self._clipboard_paths if src.exists()]
        if not sources:
            return
        action_label = self.tr("Copy") if self._clipboard_mode == "copy" else self.tr("Move")
        batch_id = self.create_operation_batch(
            self.tr("{action} {count} item(s)").format(action=action_label, count=len(sources)),
            len(sources),
        )

        # Process each clipboard item with worker threads
        for src in sources:
            if self._clipboard_mode == "copy":
                self.statusBar().showMessage(self.tr("Copying {name}...").format(name=src.name), 0)
                worker = CopyWorker(src, destination)
                copied_path = destination / src.name
                self._register_worker(
                    worker,
                    self.tr("Copying {name}...").format(name=src.name),
                    finished_callback=lambda s, m, source=src, copied=copied_path, batch=batch_id: self._on_copy_finished(
                        source,
                        copied,
                        s,
                        m,
                        self.tr("Paste Error"),
                        batch,
                    ),
                )
            elif self._clipboard_mode == "cut":
                self.statusBar().showMessage(self.tr("Moving {name}...").format(name=src.name), 0)
                worker = MoveWorker(src, destination)
                moved_path = destination / src.name
                self._register_worker(
                    worker,
                    self.tr("Moving {name}...").format(name=src.name),
                    finished_callback=lambda s, m, source=src, moved=moved_path, batch=batch_id: self._on_move_finished(
                        source,
                        moved,
                        s,
                        m,
                        self.tr("Paste Error"),
                        batch,
                    ),
                )
            else:
                self.finish_operation_batch_item(batch_id)

        # If cut mode, clear clipboard after paste
        if self._clipboard_mode == "cut":
            self._clipboard_paths = []
            self._clipboard_mode = None

    def _on_paste_finished(self, success, message):
        if success:
            self.statusBar().showMessage(message, 5000)
        else:
            QMessageBox.critical(
                self,
                self.tr("Paste Error"),
                self.tr("Operation failed:\n{message}").format(message=message),
            )
        self.refresh_view()
        # _register_worker/unregister handles active worker bookkeeping

    def copy_path(self):
        path = self.workspace.selected_path()
        if path:
            QApplication.clipboard().setText(str(path))
            self.statusBar().showMessage(self.tr("Path copied: {path}").format(path=path), 3000)

    # ─── File Creation ─────────────────────────────────────────

    def new_folder(self):
        current = self.workspace.current_path()
        if not current:
            return
        name, ok = QInputDialog.getText(self, self.tr("New Folder"), self.tr("Folder name:"))
        if not ok or not name.strip():
            return
        try:
            FileOperations.create_folder(current, name)
            self.record_operation(CreateOperation(current / name.strip(), "folder"))
            self.refresh_view()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Could not create folder:\n{error}").format(error=exc),
            )

    def new_file(self):
        current = self.workspace.current_path()
        if not current:
            return
        name, ok = QInputDialog.getText(self, self.tr("New File"), self.tr("File name:"))
        if not ok or not name.strip():
            return
        try:
            FileOperations.create_file(current, name)
            self.record_operation(CreateOperation(current / name.strip(), "file"))
            self.refresh_view()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Could not create file:\n{error}").format(error=exc),
            )

    def new_multiple_items(self):
        current = self.workspace.current_path()
        if not current:
            return
        dialog = CreateMultipleDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            created = FileOperations.create_multiple(
                current,
                dialog.names(),
                dialog.item_type(),
            )
            if not created:
                return
            operations = [CreateOperation(path, dialog.item_type()) for path in created]
            self.record_operation(
                CompositeOperation.from_operations(
                    self.tr("Create {count} item(s)").format(count=len(created)),
                    operations,
                )
            )
            self.refresh_view()
            self.statusBar().showMessage(self.tr("Created {count} item(s)").format(count=len(created)), 5000)
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Could not create items:\n{error}").format(error=exc),
            )

    # ─── File Modification ─────────────────────────────────────

    def rename_selected(self):
        """Rename selected item. Uses inline editing in the tree view."""
        index = self.workspace.currentIndex()
        if not index.isValid():
            return
        # Trigger inline editing in the name column (column 0)
        name_index = self.workspace.model.index(index.row(), 0, index.parent())
        self.workspace.edit(name_index)

    def rename_selected_dialog(self):
        """Rename selected item using a dialog (for context menu use)."""
        path = self.workspace.selected_path()
        if not path:
            return
        new_name, ok = QInputDialog.getText(self, self.tr("Rename"), self.tr("New name:"), text=path.name)
        if not ok or not new_name.strip():
            return
        try:
            old_path = path
            new_path = path.with_name(new_name.strip())
            FileOperations.rename(path, new_name)
            self.record_operation(RenameOperation(old_path, new_path))
            self.refresh_view()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Could not rename:\n{error}").format(error=exc),
            )
