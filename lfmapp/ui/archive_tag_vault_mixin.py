"""Archives, tags, vault, about & key events extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QDialog, QInputDialog, QLineEdit, QMessageBox

from lfmapp.services import (
    CompressThread,
    ExtractThread,
    FileOperations,
    is_archive,
)
from lfmapp.ui.about_dialog import AboutDialog
from lfmapp.ui.icons import app_icon
from lfmapp.ui.tag_management_dialog import TagManagementDialog
from lfmapp.ui.tag_search_dialog import TagSearchDialog
from lfmapp.utils.open_with import send_email_with_attachments


class ArchiveTagVaultMixin:
    # ─── Archive Extraction ────────────────────────────────────

    def extract_archive(self, path: Path):
        """Extract archive in its current directory."""
        self._extract_thread = ExtractThread(path, path.parent)
        self._register_worker(
            self._extract_thread,
            self.tr("Extracting {name}...").format(name=path.name),
            finished_callback=self._on_extract_finished,
        )

    def extract_archive_to(self, path: Path):
        """Extract archive to a chosen directory."""
        destination = FileOperations.choose_folder(self, self.tr("Extract to"), str(path.parent))
        if not destination:
            return
        self._extract_thread = ExtractThread(path, destination)
        self._register_worker(
            self._extract_thread,
            self.tr("Extracting {name}...").format(name=path.name),
            finished_callback=self._on_extract_finished,
        )

    def _on_extract_finished(self, success, message):
        if success:
            self.statusBar().showMessage(message, 5000)
            self.refresh_view()
        else:
            QMessageBox.critical(
                self,
                self.tr("Extraction Error"),
                self.tr("Extraction failed:\n{message}").format(message=message),
            )

    # ─── Archive Compression ───────────────────────────────────

    def compress_to_zip(self, path: Path):
        """Compress a file or directory to a ZIP archive."""
        if not path or not path.exists():
            return
        self._compress_paths_to_zip([path], path.parent, f"{path.name}.zip", path.name)

    def compress_selection_to_zip(self):
        """Compress selected files/folders to a single ZIP archive."""
        paths = [path for path in self.workspace.selected_paths() if path.exists()]
        if not paths:
            QMessageBox.information(
                self,
                self.tr("Compress to ZIP"),
                self.tr("Select one or more items to compress."),
            )
            return
        current = self.workspace.current_path() or paths[0].parent
        if len(paths) == 1:
            default_name = f"{paths[0].name}.zip"
            label = paths[0].name
        else:
            default_name = f"{current.name or 'archive'}.zip"
            label = self.tr("{count} item(s)").format(count=len(paths))
        self._compress_paths_to_zip(paths, current, default_name, label)

    def _compress_paths_to_zip(self, paths: list[Path], destination_dir: Path, default_name: str, label: str):
        # Ask user for confirmation/destination
        dest, ok = QInputDialog.getText(
            self,
            self.tr("Compress to ZIP"),
            self.tr("Archive filename:"),
            text=default_name,
        )
        if not ok or not dest.strip():
            return

        destination = destination_dir / dest.strip()
        self.statusBar().showMessage(self.tr("Compressing {label}...").format(label=label), 0)
        self._compress_thread = CompressThread(paths, destination)
        self._register_worker(
            self._compress_thread,
            self.tr("Compressing {label}...").format(label=label),
            finished_callback=self._on_compress_finished,
        )

    def _on_compress_finished(self, success, message):
        if success:
            self.statusBar().showMessage(message, 5000)
            self.refresh_view()
        else:
            QMessageBox.critical(
                self,
                self.tr("Compression Error"),
                self.tr("Could not create archive:\n{message}").format(message=message),
            )

    # ─── Tag Operations ────────────────────────────────────────

    def on_add_tag(self):
        path = self.workspace.selected_path()
        if path:
            self.on_add_tag_to_file(path)

    def on_manage_tags(self):
        dialog = TagManagementDialog(self.tag_service, self)
        dialog.exec()

    def on_search_by_tag(self):
        tags = self.tag_service.list_tags()
        if not tags:
            QMessageBox.information(
                self,
                self.tr("Search by Tag"),
                self.tr("No tags have been created yet."),
            )
            return

        dialog = TagSearchDialog(tags, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_tags = dialog.selected_tags()
        if not selected_tags:
            return

        results = self.tag_service.search_by_tags(selected_tags, match_all=dialog.match_all())
        if results:
            self.preview.show_search_results([Path(p) for p in results])
            mode = self.tr("all") if dialog.match_all() else self.tr("any")
            self.statusBar().showMessage(
                self.tr("Found {count} files matching {mode} of selected tags").format(
                    count=len(results),
                    mode=mode,
                ),
                5000,
            )
        else:
            self.preview.show_search_results([])
            self.statusBar().showMessage(
                self.tr("No files found matching selected tags"),
                5000,
            )

    def on_add_tag_to_file(self, path: Path):
        name, ok = QInputDialog.getText(self, self.tr("Add Tag"), self.tr("Tag name:"))
        if not ok or not name.strip():
            return
        self.tag_service.add_tag_to_file(str(path), name.strip())
        self.statusBar().showMessage(
            self.tr("Tag '{tag}' added to {name}").format(tag=name.strip(), name=path.name),
            3000,
        )

    def on_remove_tag_from_file(self, path: Path, tag_name: str):
        self.tag_service.remove_tag_from_file(str(path), tag_name)
        self.statusBar().showMessage(
            self.tr("Tag '{tag}' removed from {name}").format(tag=tag_name, name=path.name),
            3000,
        )

    # ─── Vault ─────────────────────────────────────────────────

    def on_open_vault(self):
        if not self.vault_service.is_initialized():
            self.vault_service.initialize()
        if self.vault_service.is_locked() and self.vault_service.encryption_enabled():
            password, ok = QInputDialog.getText(
                self,
                self.tr("Unlock Vault"),
                self.tr("Password:"),
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return
            if not self.vault_service.unlock(password):
                QMessageBox.warning(
                    self,
                    self.tr("Vault"),
                    self.tr("The vault password is incorrect."),
                )
                return
        elif self.vault_service.is_locked():
            self.vault_service.unlock()
        vault_path = self.vault_service.vault_path
        self.go_to(vault_path)

    def on_enable_vault_encryption(self):
        if not self.vault_service.is_initialized():
            self.vault_service.initialize()
        if self.vault_service.encryption_enabled():
            QMessageBox.information(
                self,
                self.tr("Vault"),
                self.tr("Vault encryption is already enabled."),
            )
            return
        password, ok = QInputDialog.getText(
            self,
            self.tr("Enable Vault Encryption"),
            self.tr("Password:"),
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        confirm, ok = QInputDialog.getText(
            self,
            self.tr("Enable Vault Encryption"),
            self.tr("Confirm password:"),
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        if not password or password != confirm:
            QMessageBox.warning(
                self,
                self.tr("Vault"),
                self.tr("Vault passwords do not match."),
            )
            return
        if self.vault_service.enable_encryption(password):
            QMessageBox.information(
                self,
                self.tr("Vault"),
                self.tr("Vault encryption is enabled. Lock the vault to encrypt its contents."),
            )
        else:
            QMessageBox.warning(
                self,
                self.tr("Vault"),
                self.tr("Vault encryption could not be enabled."),
            )

    def on_lock_vault(self):
        if not self.vault_service.is_initialized():
            return
        if self.vault_service.encryption_enabled():
            password, ok = QInputDialog.getText(
                self,
                self.tr("Lock Vault"),
                self.tr("Password:"),
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return
            if not self.vault_service.lock(password):
                QMessageBox.warning(
                    self,
                    self.tr("Vault"),
                    self.tr("The vault could not be locked."),
                )
                return
        else:
            self.vault_service.lock()
        self.statusBar().showMessage(self.tr("Vault locked"), 3000)

    # ─── About ─────────────────────────────────────────────────

    def on_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    # ─── Key Events ────────────────────────────────────────────

    def keyPressEvent(self, event):
        """Handle key events at the window level."""
        key = event.key()
        modifiers = event.modifiers()

        # Enter key on selected item = open
        if key == Qt.Key.Key_Return and not modifiers:
            self.open_selected()
            return

        # Backspace = go up
        if key == Qt.Key.Key_Backspace and not modifiers:
            self.go_up()
            return

        super().keyPressEvent(event)

    def open_terminal_in_directory(self, path: Path):
        """Open a terminal emulator at the specified path.
        
        Args:
            path: Directory path where terminal should open
        """
        if not path or not path.exists():
            return
        
        if not path.is_dir():
            path = path.parent
        
        self.terminal_service.open_terminal(path)

    def open_current_directory_in_terminal(self):
        """Open a terminal emulator in the current directory being viewed."""
        current_path = Path(self.workspace.model.rootPath())
        if current_path.exists():
            self.terminal_service.open_terminal(current_path)
