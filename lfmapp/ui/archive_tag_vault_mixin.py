"""Archives, tags, vault, about & key events extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QDialog, QInputDialog, QLineEdit, QMenu, QMessageBox

from lfmapp.services import FileOperations, is_archive
from lfmapp.ui.about_dialog import AboutDialog
from lfmapp.ui.icons import app_icon
from lfmapp.ui.tag_management_dialog import TagManagementDialog
from lfmapp.ui.tag_search_dialog import TagSearchDialog
from lfmapp.utils.open_with import send_email_with_attachments


class ArchiveTagVaultMixin:
    # ─── Archive tool delegation (ROADMAP 10.1) ────────────────
    #
    # Compression and extraction are delegated to the external archiver
    # selected in Preferences (`archive_tool`: "ark" | "peazip"). The
    # internal extractor stays available only as code, never on a menu.

    def _archive_tool_available(self) -> bool:
        """Check the active tool; warn with an install hint when missing."""
        service = self.archive_service
        if service.is_available():
            return True
        QMessageBox.information(
            self,
            self.tr("Archive tool not available"),
            self.tr(
                "The selected archive tool ({tool}) is not installed.\n"
                "Install it with:\n{hint}\n\n"
                "You can choose another tool in Tools > Preferences..."
            ).format(tool=service.tool_id, hint=service.install_hint),
        )
        return False

    def extract_archive(self, path: Path):
        """Extract archive in its current directory via the active tool."""
        if self._archive_tool_available():
            if self.archive_service.extract_here(path):
                self.statusBar().showMessage(
                    self.tr("Extracting {name}...").format(name=path.name), 3000
                )

    def extract_archive_into_new_folder(self, path: Path):
        """Extract archive into a new folder named after the archive."""
        if self._archive_tool_available():
            self.archive_service.extract_into_new_folder(path)

    def extract_archive_to(self, path: Path):
        """Extract archive to a chosen directory via the active tool."""
        if not self._archive_tool_available():
            return
        destination = None
        if self.archive_service.backend.needs_destination_arg():
            destination = FileOperations.choose_folder(
                self, self.tr("Extract to"), str(path.parent)
            )
            if not destination:
                return
        self.archive_service.extract_to(path, destination)

    def open_archive_with_tool(self, path: Path):
        """Open the archive in the active external tool."""
        if self._archive_tool_available():
            self.archive_service.open_archive(path)

    def test_archive_integrity(self, path: Path):
        """Ask the active tool to verify the archive (when supported)."""
        if not self._archive_tool_available():
            return
        if not self.archive_service.test_archive(path):
            QMessageBox.information(
                self,
                self.tr("Archive integrity"),
                self.tr("The selected archive tool does not support integrity tests."),
            )

    def add_to_archive(self, paths: list[Path]):
        """Interactive 'add to archive…' handled by the active tool."""
        paths = [Path(p) for p in paths if Path(p).exists()]
        if not paths:
            QMessageBox.information(
                self,
                self.tr("Add to archive"),
                self.tr("Select one or more items to compress."),
            )
            return
        if self._archive_tool_available():
            self.archive_service.create_archive(paths)

    def compress_to_zip(self, path: Path):
        """Quick-add a file or folder into a new ZIP via the active tool."""
        if not path or not path.exists():
            return
        if self._archive_tool_available():
            self.archive_service.quick_add([path], fmt="zip")

    def compress_selection_to_zip(self):
        """Quick-add the current selection into a new ZIP via the active tool."""
        paths = [path for path in self.workspace.selected_paths() if path.exists()]
        if not paths:
            QMessageBox.information(
                self,
                self.tr("Compress to ZIP"),
                self.tr("Select one or more items to compress."),
            )
            return
        if self._archive_tool_available():
            self.archive_service.quick_add(paths, fmt="zip")

    def add_selection_to_archive(self):
        """Interactive 'Add to archive…' for the current selection."""
        paths = [path for path in self.workspace.selected_paths() if path.exists()]
        self.add_to_archive(paths)

    # ─── Archive submenu for context menus ─────────────────────

    def _archive_tool_menu(self, parent, paths: list[Path]) -> QMenu:
        """Build the submenu of the active archive tool for ``paths``."""
        service = self.archive_service
        backend = service.backend
        title = backend.label or self.tr("Archives")
        menu = QMenu(title, parent)
        menu.setIcon(app_icon("package-x-generic", "ark", "peazip"))

        archives = [p for p in paths if p.is_file() and is_archive(p)]
        if not service.is_available():
            notice = menu.addAction(
                self.tr("{tool} is not installed ({hint})").format(
                    tool=backend.label, hint=service.install_hint
                )
            )
            notice.setEnabled(False)
            return menu

        if len(archives) == 1:
            archive = archives[0]
            menu.addAction(
                app_icon("package-x-generic", "archive-extract"),
                self.tr("Extract Here"),
                lambda: self.extract_archive(archive),
            )
            menu.addAction(
                self.tr("Extract Into New Folder"),
                lambda: self.extract_archive_into_new_folder(archive),
            )
            menu.addAction(
                self.tr("Extract to..."),
                lambda: self.extract_archive_to(archive),
            )
            menu.addAction(
                self.tr("Open with {tool}").format(tool=backend.label),
                lambda: self.open_archive_with_tool(archive),
            )
            test_command = backend.test_command(archive)
            if test_command is not None:
                menu.addAction(
                    self.tr("Check Integrity"),
                    lambda: self.test_archive_integrity(archive),
                )
            menu.addSeparator()

        menu.addAction(
            self.tr("Add to Archive..."),
            lambda: self.add_to_archive(paths),
        )
        menu.addAction(
            self.tr("Add to ZIP"),
            lambda: (
                self.archive_service.quick_add(paths, fmt="zip")
                if self._archive_tool_available()
                else None
            ),
        )
        return menu

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

    # ─── Duplicate Finder (ROADMAP P2) ──────────────────────────

    def show_duplicate_finder(self) -> None:
        """Open the duplicate finder dialog for the current folder."""
        from lfmapp.ui.duplicate_finder_dialog import DuplicateFinderDialog

        current = Path(self.workspace.model.rootPath())
        if not current.exists():
            return
        dlg = DuplicateFinderDialog(parent=self)
        dlg.start_from_folders([current], recursive=True)
        dlg.exec()
