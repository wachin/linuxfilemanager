"""Context menu builders extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QHBoxLayout, QToolButton, QWidget, QWidgetAction

from lfmapp.services import is_archive
from lfmapp.ui.icons import app_icon
from lfmapp.utils.open_with import (
    get_available_applications,
    launch_application_for_path,
)


class ContextMenuMixin:
    # ─── Context Menu ──────────────────────────────────────────

    def open_context_menu(self, pos):
        index = self.workspace.indexAt(pos)
        if index.isValid():
            self.workspace.setCurrentIndex(index)
            path = Path(self.workspace.model.filePath(index))
        else:
            path = None

        menu = QMenu(self)
        self._add_compact_context_actions(menu, path)

        if path and path.is_file():
            self._build_file_context_menu(menu, path)
        elif path and path.is_dir():
            self._build_folder_context_menu(menu, path)
        else:
            self._build_empty_context_menu(menu)

        menu.exec(self.workspace.viewport().mapToGlobal(pos))

    def _add_compact_context_actions(self, menu: QMenu, path: Path | None):
        if not self.config.data.get("modern_context_menu_enabled", True):
            return
        container = QWidget(menu)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        has_selection = path is not None

        cut_button = self._context_strip_button(
            menu,
            app_icon("edit-cut"),
            self.tr("Cut"),
            self.cut_selected,
            enabled=has_selection and self._context_entry_enabled("selection", "cut"),
        )
        copy_button = self._context_strip_button(
            menu,
            app_icon("edit-copy"),
            self.tr("Copy"),
            self.copy_selected,
            enabled=has_selection and self._context_entry_enabled("selection", "copy"),
        )
        paste_button = self._context_strip_button(
            menu,
            app_icon("edit-paste"),
            self.tr("Paste"),
            self.paste_from_clipboard,
            enabled=self._clipboard_mode in {"copy", "cut"}
            and bool(self._clipboard_paths)
            and (
                (path is None and self._context_entry_enabled("background", "paste"))
                or (has_selection and self._context_entry_enabled("selection", "paste"))
            ),
        )
        rename_button = self._context_strip_button(
            menu,
            app_icon("document-save-as", "edit-rename"),
            self.tr("Rename"),
            self.rename_selected_dialog,
            enabled=has_selection and self._context_entry_enabled("selection", "rename"),
        )

        share_menu = QMenu(menu)
        if has_selection:
            share_menu.addAction(self.tr("Desktop"), self.send_selected_to_desktop)
            share_menu.addAction(self.tr("Email recipient"), self.send_selected_to_email)
            self._add_share_with_menu(share_menu, path)
        share_button = QToolButton(container)
        share_button.setToolTip(self.tr("Share"))
        share_button.setIcon(app_icon("document-share", "emblem-shared", "mail-send"))
        share_button.setAutoRaise(True)
        share_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        share_button.setMenu(share_menu)
        share_button.setEnabled(has_selection)

        delete_button = self._context_strip_button(
            menu,
            app_icon("user-trash", "edit-delete"),
            self.tr("Delete"),
            self.trash_selected if has_selection else self.delete_selected,
            enabled=has_selection,
        )

        for button in (
            cut_button,
            copy_button,
            paste_button,
            rename_button,
            share_button,
            delete_button,
        ):
            layout.addWidget(button)
        layout.addStretch(1)

        action = QWidgetAction(menu)
        action.setDefaultWidget(container)
        menu.addAction(action)
        menu.addSeparator()

    def _context_strip_button(
        self,
        menu: QMenu,
        icon,
        tooltip: str,
        slot,
        *,
        enabled: bool = True,
    ) -> QToolButton:
        button = QToolButton(menu)
        button.setIcon(icon)
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.setEnabled(enabled)
        button.clicked.connect(
            lambda checked=False, menu=menu, slot=slot: self._run_compact_context_action(
                menu,
                slot,
            )
        )
        return button

    def _run_compact_context_action(self, menu: QMenu, slot):
        menu.close()
        slot()

    def _context_entry_enabled(self, group: str, key: str) -> bool:
        entries = self.config.data.get(f"context_menu_{group}_entries", [])
        return key in entries

    def _traditional_context_entry_enabled(self, group: str, key: str) -> bool:
        if not self._context_entry_enabled(group, key):
            return False
        if not self.config.data.get("modern_context_menu_enabled", True):
            return True
        hidden_when_modern = {
            ("selection", "cut"),
            ("selection", "copy"),
            ("selection", "paste"),
            ("selection", "rename"),
            ("background", "paste"),
        }
        return (group, key) not in hidden_when_modern

    def _build_file_context_menu(self, menu: QMenu, path: Path):
        if self._context_entry_enabled("selection", "open"):
            menu.addAction(app_icon("document-open", "folder-open"), self.tr("Open"), self.open_selected)
        menu.addAction(self.tr("Open with..."), self.open_with_dialog)
        menu.addAction(self.tr("Set default application..."), self.set_default_application_dialog)
        menu.addSeparator()
        if self._context_entry_enabled("selection", "open_in_terminal"):
            menu.addAction(app_icon("utilities-terminal", "terminal"), self.tr("Open in Terminal"), lambda: self.open_terminal_in_directory(path.parent))
        menu.addSeparator()
        if self._traditional_context_entry_enabled("selection", "cut"):
            menu.addAction(app_icon("edit-cut"), self.tr("Cut"), self.cut_selected)
        if self._traditional_context_entry_enabled("selection", "copy"):
            menu.addAction(app_icon("edit-copy"), self.tr("Copy"), self.copy_selected)
        menu.addAction(self.tr("Copy path"), self.copy_path)
        if self._context_entry_enabled("selection", "copy_to") and self.config.data.get("move_copy_menu_show_bookmarks", True):
            menu.addAction(self.tr("Copy to..."), self.copy_selected_to)
        if self._context_entry_enabled("selection", "move_to") and self.config.data.get("move_copy_menu_show_bookmarks", True):
            menu.addAction(self.tr("Move to..."), self.move_selected_to)
        menu.addSeparator()

        send_to_menu = menu.addMenu(self.tr("Send to"))
        send_to_menu.addAction(self.tr("Desktop"), self.send_selected_to_desktop)
        send_to_menu.addAction(self.tr("Email recipient"), self.send_selected_to_email)
        menu.addSeparator()
        self._add_share_with_menu(menu, path)
        menu.addSeparator()
        menu.addAction(app_icon("document-print", "printer"), self.tr("Print"), self.print_selected)
        menu.addSeparator()

        # Archive extraction
        if is_archive(path):
            menu.addAction(app_icon("package-x-generic", "archive-extract"), self.tr("Extract Here"), lambda: self.extract_archive(path))
            menu.addAction(self.tr("Extract to..."), lambda: self.extract_archive_to(path))
            menu.addSeparator()

        # Compress to ZIP
        menu.addAction(app_icon("package-x-generic", "folder-compressed"), self.tr("Compress to ZIP"), lambda: self.compress_to_zip(path))
        menu.addAction(app_icon("document-properties", "security-medium"), self.tr("Advanced Security..."), self.show_advanced_security)

        if self._traditional_context_entry_enabled("selection", "rename"):
            menu.addAction(app_icon("document-save-as", "edit-rename"), self.tr("Rename"), self.rename_selected_dialog)
        if self._context_entry_enabled("selection", "move_to_trash"):
            menu.addAction(app_icon("user-trash", "trash-empty"), self.tr("Move to Trash"), self.trash_selected)
        if self.config.data.get("show_delete_bypassing_trash", True):
            menu.addAction(app_icon("edit-delete"), self.tr("Delete Permanently"), self.delete_selected)
        menu.addSeparator()

        # Tags submenu
        tags_menu = menu.addMenu(self.tr("Tags"))
        tags_menu.addAction(self.tr("Add tag..."), lambda: self.on_add_tag_to_file(path))
        file_tags = self.tag_service.get_tags_for_file(str(path))
        if file_tags:
            for tag in file_tags:
                tag_action = tags_menu.addAction(f"✓ {tag['name']}")
                tag_action.triggered.connect(
                    lambda checked, t=tag['name'], p=path: self.on_remove_tag_from_file(p, t)
                )

                # Register tag actions in the command palette so tags are discoverable
                try:
                    self._register_command_action(
                        tag_action,
                        category=tags_menu.title().replace("&", ""),
                        alias=[tag['name'], "tag"],
                        command_id=f"tag::{tag['name']}::{path}",
                    )
                except Exception:
                    # Non-critical: continue if registration fails
                    pass

        menu.addSeparator()
        if self._context_entry_enabled("selection", "properties"):
            menu.addAction(app_icon("document-properties", "settings"), self.tr("Properties"), self.show_properties)

    def _build_folder_context_menu(self, menu: QMenu, path: Path):
        if self._context_entry_enabled("selection", "open"):
            menu.addAction(app_icon("document-open", "folder-open"), self.tr("Open"), self.open_selected)
        if self._context_entry_enabled("selection", "open_in_terminal"):
            menu.addAction(app_icon("utilities-terminal", "terminal"), self.tr("Open in Terminal"), lambda: self.open_terminal_in_directory(path))
        menu.addSeparator()
        if self._traditional_context_entry_enabled("selection", "cut"):
            menu.addAction(app_icon("edit-cut"), self.tr("Cut"), self.cut_selected)
        if self._traditional_context_entry_enabled("selection", "copy"):
            menu.addAction(app_icon("edit-copy"), self.tr("Copy"), self.copy_selected)
        menu.addAction(self.tr("Copy path"), self.copy_path)
        if self._context_entry_enabled("selection", "copy_to") and self.config.data.get("move_copy_menu_show_bookmarks", True):
            menu.addAction(self.tr("Copy to..."), self.copy_selected_to)
        if self._context_entry_enabled("selection", "move_to") and self.config.data.get("move_copy_menu_show_bookmarks", True):
            menu.addAction(self.tr("Move to..."), self.move_selected_to)
        menu.addSeparator()

        send_to_menu = menu.addMenu(self.tr("Send to"))
        send_to_menu.addAction(self.tr("Desktop"), self.send_selected_to_desktop)
        send_to_menu.addAction(self.tr("Email recipient"), self.send_selected_to_email)
        menu.addSeparator()
        self._add_share_with_menu(menu, path)
        menu.addSeparator()
        menu.addAction(app_icon("document-print", "printer"), self.tr("Print"), self.print_selected)
        menu.addSeparator()

        # Compress to ZIP
        menu.addAction(app_icon("package-x-generic", "folder-compressed"), self.tr("Compress to ZIP"), lambda: self.compress_to_zip(path))
        menu.addAction(app_icon("document-properties", "security-medium"), self.tr("Advanced Security..."), self.show_advanced_security)

        if self._traditional_context_entry_enabled("selection", "rename"):
            menu.addAction(app_icon("document-save-as", "edit-rename"), self.tr("Rename"), self.rename_selected_dialog)
        if self._context_entry_enabled("selection", "move_to_trash"):
            menu.addAction(app_icon("user-trash", "trash-empty"), self.tr("Move to Trash"), self.trash_selected)
        if self.config.data.get("show_delete_bypassing_trash", True):
            menu.addAction(app_icon("edit-delete"), self.tr("Delete Permanently"), self.delete_selected)
        menu.addSeparator()

        new_menu = menu.addMenu(self.tr("New"))
        new_menu.addAction(self.tr("Folder"), self.new_folder)
        new_menu.addAction(self.tr("Empty file"), self.new_file)
        new_menu.addAction(self.tr("Multiple items..."), self.new_multiple_items)
        menu.addSeparator()

        if self._context_entry_enabled("selection", "pin"):
            menu.addAction(self.tr("Add folder to Quick Access"), self.add_bookmark)
        if self._context_entry_enabled("selection", "properties"):
            menu.addAction(app_icon("document-properties", "settings"), self.tr("Properties"), self.show_properties)

    def _build_empty_context_menu(self, menu: QMenu):
        if self._context_entry_enabled("background", "open_in_terminal"):
            menu.addAction(app_icon("utilities-terminal", "terminal"), self.tr("Open in Terminal"), self.open_current_directory_in_terminal)
        menu.addSeparator()
        if self._traditional_context_entry_enabled("background", "paste"):
            menu.addAction(app_icon("edit-paste"), self.tr("Paste"), self.paste_from_clipboard)
        menu.addSeparator()

        if self._context_entry_enabled("background", "create_new_folder"):
            new_menu = menu.addMenu(self.tr("New"))
            new_menu.addAction(self.tr("Folder"), self.new_folder)
            new_menu.addAction(self.tr("Empty file"), self.new_file)
            new_menu.addAction(self.tr("Multiple items..."), self.new_multiple_items)
            menu.addSeparator()

        view_menu = menu.addMenu(self.tr("View"))
        hidden_action = QAction(self.tr("Hidden files"), self, checkable=True)
        hidden_action.setChecked(self.config.show_hidden_files)
        hidden_action.triggered.connect(self.toggle_hidden_files)
        view_menu.addAction(hidden_action)
        extensions_action = QAction(self.tr("File extensions"), self, checkable=True)
        extensions_action.setChecked(self.workspace.model.show_extensions)
        extensions_action.triggered.connect(self.toggle_file_extensions)
        view_menu.addAction(extensions_action)
        view_menu.addAction(self.tr("Toggle preview panel"), self.toggle_preview)
        view_menu.addSeparator()
        self._add_icon_grid_menu(view_menu)
        view_menu.addSeparator()
        self._add_sort_menus(view_menu)
        self._add_group_menus(view_menu)
        menu.addSeparator()

        menu.addAction(self.tr("Refresh"), self.refresh_view)
        if self._context_entry_enabled("background", "properties"):
            menu.addAction(app_icon("document-properties", "settings"), self.tr("Properties"), self.show_folder_properties)

    def _add_share_with_menu(self, menu: QMenu, path: Path):
        """Add a dynamic Share with submenu for a file or folder."""
        apps = get_available_applications(path)
        share_menu = menu.addMenu(self.tr("Share with"))
        if not apps:
            empty_action = QAction(self.tr("No compatible applications"), self)
            empty_action.setEnabled(False)
            share_menu.addAction(empty_action)
            self._register_command_action(empty_action, category=share_menu.title().replace("&", ""))
            return

        for desktop_file, app_name in apps:
            action = QAction(app_name, self)
            action.setToolTip(desktop_file)
            action.triggered.connect(
                lambda checked=False, desktop_file=desktop_file, target=path: self.share_with_application(
                    target,
                    desktop_file,
                )
            )
            share_menu.addAction(action)
            self._register_command_action(
                action,
                category=share_menu.title().replace("&", ""),
                alias=[desktop_file, "share", "send"],
                command_id=f"share_with::{desktop_file}",
            )

    def share_with_application(self, path: Path, desktop_file: str):
        """Launch a chosen application for the supplied path."""
        if not path.exists() or not desktop_file:
            return False
        launched = launch_application_for_path(desktop_file, path)
        if launched and path.is_file():
            self.record_recent_file(path)
        return launched
