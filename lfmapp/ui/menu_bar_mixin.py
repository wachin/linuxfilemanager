"""Menu bar construction extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence

from lfmapp.ui.workspace import IconGridSize, ViewMode


class MenuBarMixin:
    # ─── Menu Bar ──────────────────────────────────────────────

    def _add_action(self, menu, text, slot, shortcut=None):
        """Helper to add an action with optional shortcut to a menu."""
        action = QAction(self.tr(text), self)
        action.triggered.connect(slot)
        shortcut_text = ""
        if shortcut:
            action.setShortcut(shortcut)
            shortcut_text = self._format_shortcut(shortcut)
        menu.addAction(action)
        self._register_command_action(action, category=menu.title().replace("&", ""), shortcut=shortcut_text)
        return action

    def _add_sort_menus(self, menu, persistent: bool = False):
        """Add sorting controls to a menu."""
        sort_menu = menu.addMenu(self.tr("Sort by"))
        column_group = QActionGroup(self)
        column_group.setExclusive(True)
        self._action_groups.append(column_group)
        column_actions = {}
        for key, label in (
            ("name", self.tr("Name")),
            ("size", self.tr("Size")),
            ("type", self.tr("Type")),
            ("modified", self.tr("Date modified")),
        ):
            action = QAction(label, self, checkable=True)
            action.setChecked(self.workspace.sort_key() == key)
            action.triggered.connect(lambda checked=False, key=key: self.set_sort(key=key))
            column_group.addAction(action)
            sort_menu.addAction(action)
            column_actions[key] = action
            self._register_command_action(action, category=sort_menu.title().replace("&", ""))

        order_menu = menu.addMenu(self.tr("Sort order"))
        order_group = QActionGroup(self)
        order_group.setExclusive(True)
        self._action_groups.append(order_group)
        order_actions = {}
        for order, label in (
            (Qt.SortOrder.AscendingOrder, self.tr("Ascending")),
            (Qt.SortOrder.DescendingOrder, self.tr("Descending")),
        ):
            action = QAction(label, self, checkable=True)
            action.setChecked(self.workspace.sort_order() == order)
            action.triggered.connect(lambda checked=False, order=order: self.set_sort(order=order))
            order_group.addAction(action)
            order_menu.addAction(action)
            order_actions[order] = action
            self._register_command_action(action, category=order_menu.title().replace("&", ""))

        if persistent:
            self._sort_column_actions = column_actions
            self._sort_order_actions = order_actions

    # ─── Status Bar ────────────────────────────────────────────
    def _add_group_menus(self, menu, persistent: bool = False):
        """Add grouping controls to a menu."""
        group_menu = menu.addMenu(self.tr("Group by"))
        group_group = QActionGroup(self)
        group_group.setExclusive(True)
        self._action_groups.append(group_group)
        group_actions = {}
        for key, label in (
            ("none", self.tr("None")),
            ("type", self.tr("Type")),
            ("size", self.tr("Size")),
            ("modified", self.tr("Date modified")),
            ("name", self.tr("Name")),
        ):
            action = QAction(label, self, checkable=True)
            action.setChecked(self.workspace.group_key() == key)
            action.triggered.connect(lambda checked=False, key=key: self.set_group(key=key))
            group_group.addAction(action)
            group_menu.addAction(action)
            group_actions[key] = action
            self._register_command_action(action, category=group_menu.title().replace("&", ""))

        if persistent:
            self._group_actions = group_actions

    def _add_icon_grid_menu(self, menu, persistent: bool = False):
        """Add icon grid density controls to a menu."""
        grid_menu = menu.addMenu(self.tr("Icon grid size"))
        grid_group = QActionGroup(self)
        grid_group.setExclusive(True)
        self._action_groups.append(grid_group)
        grid_actions = {}
        for size, label in (
            (IconGridSize.SMALL, self.tr("Small")),
            (IconGridSize.MEDIUM, self.tr("Medium")),
            (IconGridSize.LARGE, self.tr("Large")),
        ):
            action = QAction(label, self, checkable=True)
            action.setChecked(self.workspace.icon_grid_size() == size)
            action.triggered.connect(lambda checked=False, size=size: self.set_icon_grid_size(size))
            grid_group.addAction(action)
            grid_menu.addAction(action)
            grid_actions[size] = action
            self._register_command_action(action, category=grid_menu.title().replace("&", ""))

        if persistent:
            self._icon_grid_actions = grid_actions

    def rebuild_recent_files_menu(self):
        """Refresh the File > Recent Files menu."""
        if self.recent_files_menu is None:
            return
        self.recent_files_menu.clear()
        recent_files = [Path(path) for path in self.config.recent_files]
        existing_files = [path for path in recent_files if path.exists() and path.is_file()]
        recent_category = self.recent_files_menu.title().replace("&", "")

        if not existing_files:
            empty_action = QAction(self.tr("No recent files"), self)
            empty_action.setEnabled(False)
            self.recent_files_menu.addAction(empty_action)
            self._register_command_action(empty_action, category=recent_category, command_id="recent_file::empty")
        else:
            for path in existing_files:
                action = QAction(path.name, self)
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked=False, path=path: self.open_recent_file(path))
                self.recent_files_menu.addAction(action)
                self._register_command_action(
                    action,
                    category=recent_category,
                    alias=[str(path)],
                    command_id=f"recent_file::{path}",
                )
            self.recent_files_menu.addSeparator()

        clear_action = QAction(self.tr("Clear Recent Files"), self)
        clear_action.setEnabled(bool(self.config.recent_files))
        clear_action.triggered.connect(self.clear_recent_files)
        self.recent_files_menu.addAction(clear_action)
        self._register_command_action(clear_action, category=recent_category)

    def rebuild_share_menu(self):
        """Refresh the Share menu from the current selection."""
        if not hasattr(self, "share_menu") or self.share_menu is None:
            return
        self.share_menu.clear()

        self._add_action(self.share_menu, "Send to Desktop", self.send_selected_to_desktop)
        self._add_action(self.share_menu, "Send by Email", self.send_selected_to_email)
        self.share_menu.addSeparator()
        target = self.workspace.selected_path() or self.workspace.current_path()
        self._add_share_with_menu(self.share_menu, target)
        self.share_menu.addSeparator()
        self._add_action(self.share_menu, "Print", self.print_selected)
        self._add_action(self.share_menu, "Compress to ZIP", self.compress_selection_to_zip)
        self.share_menu.addSeparator()
        self._add_action(self.share_menu, "Advanced Security...", self.show_advanced_security)

    def build_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu(self.tr("&File"))
        self._add_action(file_menu, "New Folder", self.new_folder, "Ctrl+Shift+N")
        self._add_action(file_menu, "New File", self.new_file, "Ctrl+N")
        self._add_action(file_menu, "New Multiple Items...", self.new_multiple_items)
        file_menu.addSeparator()
        self._add_action(file_menu, "Print", self.print_selected)
        file_menu.addSeparator()
        self._add_action(file_menu, "Compress Selection to ZIP", self.compress_selection_to_zip)
        file_menu.addSeparator()
        self.recent_files_menu = file_menu.addMenu(self.tr("Recent Files"))
        self.rebuild_recent_files_menu()
        file_menu.addSeparator()
        self._add_action(file_menu, "New Tab", self.new_tab, "Ctrl+T")
        self._add_action(file_menu, "Close Tab", self.close_current_tab, "Ctrl+W")
        self._add_action(file_menu, "Next Tab", self.next_tab, "Ctrl+Tab")
        self._add_action(file_menu, "Previous Tab", self.previous_tab, "Ctrl+Shift+Tab")
        file_menu.addSeparator()
        self._add_action(file_menu, "Close Window", self.close, "Ctrl+Shift+W")

        # Edit menu
        edit_menu = menubar.addMenu(self.tr("&Edit"))
        self.copy_action = self._add_action(edit_menu, "Copy", self.copy_selected, QKeySequence.StandardKey.Copy)
        self.cut_action = self._add_action(edit_menu, "Cut", self.cut_selected, QKeySequence.StandardKey.Cut)
        self.paste_action = self._add_action(edit_menu, "Paste", self.paste_from_clipboard, QKeySequence.StandardKey.Paste)
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Copy Path", self.copy_path, "Ctrl+Shift+C")
        edit_menu.addSeparator()
        self.undo_action = self._add_action(edit_menu, "Undo", self.undo_last_operation, "Ctrl+Z")
        self.redo_action = self._add_action(edit_menu, "Redo", self.redo_last_operation, "Ctrl+Y")
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Select All", self.select_all, QKeySequence.StandardKey.SelectAll)
        self._add_action(edit_menu, "Deselect All", self.deselect_all, "Ctrl+Shift+A")
        self._add_action(edit_menu, "Invert Selection", self.invert_selection, "Ctrl+Shift+I")
        self.update_undo_redo_actions()

        # View menu
        view_menu = menubar.addMenu(self.tr("&View"))
        self._add_action(view_menu, "Refresh", self.refresh_view, "F5")
        font_menu = view_menu.addMenu(self.tr("Font Size"))
        self._add_action(font_menu, "Choose Font...", self.choose_font_dialog)
        font_menu.addSeparator()
        self._add_action(font_menu, "Increase", self.increase_font_size, "Ctrl++")
        self._add_action(font_menu, "Decrease", self.decrease_font_size, "Ctrl+-")
        self._add_action(font_menu, "Reset", self.reset_font_size, "Ctrl+0")
        self._add_action(font_menu, "Set...", self.set_font_size_dialog)
        view_menu.addSeparator()
        self.hidden_files_action = QAction(self.tr("Hidden Files"), self, checkable=True)
        self.hidden_files_action.setShortcut("Ctrl+H")
        self.hidden_files_action.setChecked(self.config.show_hidden_files)
        self.hidden_files_action.triggered.connect(self.toggle_hidden_files)
        view_menu.addAction(self.hidden_files_action)
        self._register_command_action(self.hidden_files_action, category=self.tr("View"), shortcut="Ctrl+H")
        self.file_extensions_action = QAction(self.tr("File Extensions"), self, checkable=True)
        self.file_extensions_action.setChecked(self.config.show_file_extensions)
        self.file_extensions_action.triggered.connect(self.toggle_file_extensions)
        view_menu.addAction(self.file_extensions_action)
        self._register_command_action(self.file_extensions_action, category=self.tr("View"))
        self.selection_checkboxes_action = QAction(self.tr("Selection Checkboxes"), self, checkable=True)
        self.selection_checkboxes_action.setChecked(self.config.selection_checkboxes)
        self.selection_checkboxes_action.triggered.connect(self.toggle_selection_checkboxes)
        view_menu.addAction(self.selection_checkboxes_action)
        self._register_command_action(self.selection_checkboxes_action, category=self.tr("View"))
        self._add_action(view_menu, "Toggle Preview Panel", self.toggle_preview)
        self._add_action(view_menu, "Toggle Sidebar", self.toggle_sidebar)
        view_menu.addSeparator()
        self._add_action(view_menu, "Icons View", lambda: self.set_view_mode(ViewMode.ICON), "Ctrl+1")
        self._add_action(view_menu, "List View", lambda: self.set_view_mode(ViewMode.LIST), "Ctrl+2")
        self._add_action(view_menu, "Details View", lambda: self.set_view_mode(ViewMode.DETAILS), "Ctrl+3")
        self._add_action(view_menu, "Compact View", lambda: self.set_view_mode(ViewMode.COMPACT), "Ctrl+4")
        view_menu.addSeparator()
        self._add_icon_grid_menu(view_menu, persistent=True)
        view_menu.addSeparator()
        self._add_sort_menus(view_menu, persistent=True)
        self._add_group_menus(view_menu, persistent=True)
        view_menu.addSeparator()
        self.remember_view_action = QAction(self.tr("Remember folder view"), self, checkable=True)
        self.remember_view_action.setChecked(self.config.remember_folder_view)
        self.remember_view_action.triggered.connect(self.toggle_folder_view_persistence)
        view_menu.addAction(self.remember_view_action)
        self._register_command_action(self.remember_view_action, category=self.tr("View"))
        self._clear_folder_view_action = QAction(self.tr("Clear saved view for current folder"), self)
        self._clear_folder_view_action.triggered.connect(self.clear_current_folder_view)
        view_menu.addAction(self._clear_folder_view_action)
        self._register_command_action(self._clear_folder_view_action, category=self.tr("View"))
        self._clear_all_folder_views_action = QAction(self.tr("Clear all saved folder views"), self)
        self._clear_all_folder_views_action.triggered.connect(self.clear_all_folder_views)
        view_menu.addAction(self._clear_all_folder_views_action)
        self._register_command_action(self._clear_all_folder_views_action, category=self.tr("View"))

        # Share menu
        self.share_menu = menubar.addMenu(self.tr("&Share"))
        self.share_menu.aboutToShow.connect(self.rebuild_share_menu)
        self.rebuild_share_menu()

        # Go menu
        go_menu = menubar.addMenu(self.tr("&Go"))
        self._add_action(go_menu, "Back", self.go_back, "Alt+Left")
        self._add_action(go_menu, "Forward", self.go_forward, "Alt+Right")
        self._add_action(go_menu, "Up", self.go_up, "Alt+Up")
        self._add_action(go_menu, "Home", self.go_home, "Alt+Home")

        # Tools menu
        tools_menu = menubar.addMenu(self.tr("&Tools"))
        self._add_action(tools_menu, "Preferences...", self.show_preferences_dialog, "Ctrl+,")
        self._add_action(tools_menu, "Command Palette...", self.show_command_palette, "Ctrl+Shift+P")
        tools_menu.addSeparator()
        self._add_action(tools_menu, "Empty Trash", self.on_empty_trash)
        self._add_action(tools_menu, "Open Vault", self.on_open_vault)
        self._add_action(tools_menu, "Enable Vault Encryption...", self.on_enable_vault_encryption)
        self._add_action(tools_menu, "Lock Vault", self.on_lock_vault)
        self._add_action(tools_menu, "Add Current Folder to Bookmarks", self.add_bookmark)
        tools_menu.addSeparator()
        self._add_action(tools_menu, "Add Tag to File", self.on_add_tag)
        self._add_action(tools_menu, "Manage Tags...", self.on_manage_tags)
        self._add_action(tools_menu, "Search by Tag...", self.on_search_by_tag)
        tools_menu.addSeparator()
        self._add_action(tools_menu, "Index Current Folder", self.on_index_current_folder)
        self._add_action(tools_menu, "Toggle Text Index Search", self.on_toggle_text_index)

        # Help menu
        help_menu = menubar.addMenu(self.tr("&Help"))
        self._add_action(help_menu, "About", self.on_about)
