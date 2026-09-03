"""Tabs, navigation, sidebar & workspace events extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QInputDialog, QMessageBox, QTabBar

from lfmapp.controllers import NavigationController
from lfmapp.services import RenameOperation, trash_count
from lfmapp.ui.workspace import ViewMode


class TabsNavigationMixin:
    # ─── Keyboard Shortcuts ────────────────────────────────────

    def setup_shortcuts(self):
        """Set up additional keyboard shortcuts."""
        # Delete to trash
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self.trash_selected)
        # Shift+Delete permanent delete
        QShortcut(QKeySequence("Shift+Delete"), self, self.delete_selected)
        # F2 rename
        QShortcut(QKeySequence(Qt.Key.Key_F2), self, self.rename_selected)
        # Ctrl+L focus path bar
        QShortcut(QKeySequence("Ctrl+L"), self, self.focus_path_bar)
        # Ctrl+E focus search
        QShortcut(QKeySequence("Ctrl+E"), self, self.focus_search)
        # Ctrl+Shift+I invert selection
        QShortcut(QKeySequence("Ctrl+Shift+I"), self, self.invert_selection)
        # Ctrl+Shift+P open command palette
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self.show_command_palette)

    # ─── Tabs ─────────────────────────────────────────────────

    def new_tab(self, path: Path | None = None):
        """Open a new navigation tab at path or the current folder."""
        target = path or self.workspace.current_path() or Path.home()
        target = target.expanduser()
        if not target.exists() or not target.is_dir():
            target = Path.home()

        self._sync_active_tab_state()
        self._tabs.append({
            "path": target,
            "history": [target],
            "history_index": 0,
        })
        index = self.tabbar.addTab(self._tab_title(target))
        self.tabbar.setCurrentIndex(index)
        if self._active_tab_index != index:
            self.on_tab_changed(index)

    def close_current_tab(self):
        self.close_tab(self.tabbar.currentIndex())

    def close_tab(self, index: int):
        """Close a tab. Closing the final tab closes the window."""
        if index < 0 or index >= len(self._tabs):
            return
        if len(self._tabs) == 1:
            self.close()
            return

        self._sync_active_tab_state()
        self.tabbar.blockSignals(True)
        self.tabbar.removeTab(index)
        self.tabbar.blockSignals(False)
        del self._tabs[index]

        next_index = min(index, len(self._tabs) - 1)
        self._active_tab_index = -1
        self.tabbar.setCurrentIndex(next_index)
        self.on_tab_changed(next_index)

    def next_tab(self):
        if len(self._tabs) < 2:
            return
        self.tabbar.setCurrentIndex((self.tabbar.currentIndex() + 1) % len(self._tabs))

    def previous_tab(self):
        if len(self._tabs) < 2:
            return
        self.tabbar.setCurrentIndex((self.tabbar.currentIndex() - 1) % len(self._tabs))

    def on_tab_changed(self, index: int):
        if index < 0 or index >= len(self._tabs):
            return
        if self._active_tab_index == index:
            return

        self._sync_active_tab_state()
        self._active_tab_index = index
        state = self._tabs[index]
        self.navigation = NavigationController.from_state(state)
        self.go_to(state["path"], record_history=False)
        self.update_navigation_actions()

    def _sync_active_tab_state(self):
        if self._active_tab_index < 0 or self._active_tab_index >= len(self._tabs):
            return
        current = self.workspace.current_path()
        self._tabs[self._active_tab_index]["path"] = current
        self._tabs[self._active_tab_index]["history"] = list(self.navigation.history)
        self._tabs[self._active_tab_index]["history_index"] = self.navigation.index
        self._update_tab_title(self._active_tab_index, current)

    def _update_tab_title(self, index: int, path: Path):
        if 0 <= index < self.tabbar.count():
            self.tabbar.setTabText(index, self._tab_title(path))
            self.tabbar.setTabToolTip(index, str(path))

    def _tab_title(self, path: Path) -> str:
        if self.config.data.get("title_show_full_path", False):
            return str(path)
        return path.name or str(path)

    # ─── Navigation ────────────────────────────────────────────

    def update_navigation_actions(self):
        self.back_action.setEnabled(self.navigation.can_go_back)
        self.forward_action.setEnabled(self.navigation.can_go_forward)

    def add_history(self, path: Path):
        self.navigation.navigate_to(path)
        self.update_navigation_actions()
        self._sync_active_tab_state()

    def go_to(self, path: Path, record_history=True):
        path = path.expanduser()
        if not path.exists() or not path.is_dir():
            QMessageBox.warning(
                self,
                self.tr("Invalid path"),
                self.tr("Does not exist or is not a folder:\n{path}").format(path=path),
            )
            return
        self.workspace.set_root_path(path)
        self.app_state.set_path(path)
        # Apply any persisted view preference (policy lives in the controller).
        view_name = self.view_controller.view_to_restore(
            path, fallback=self.workspace.view_mode().value
        )
        if view_name:
            view_mode = ViewMode.from_string(view_name, self.workspace.view_mode())
            if view_mode != self.workspace.view_mode():
                self.workspace.set_view_mode(view_mode)
                self.app_state.set_view_mode(view_mode.value)
                self.statusBar().showMessage(
                    self.tr("Restored saved view: {view}").format(view=view_mode.value),
                    3000,
                )
        self.path_edit.setText(str(path))
        self.statusBar().showMessage(str(path), 5000)
        if record_history:
            self.add_history(path)
        self.config.set_last_visited(path)
        self.config.add_recent_location(path)
        self.config.add_folder_visit(path)
        self.sidebar.set_recent_locations(self.config.recent_locations)
        self.sidebar.set_frequent_folders(self.config.frequent_folders())
        self.update_quick_access_action()
        self.update_statusbar()
        self.update_trash_count()
        self.apply_title_preferences()
        self._sync_active_tab_state()

    def apply_workspace_preferences(self):
        self.workspace.apply_preferences()
        self.preview.apply_preferences(self.config)

    def apply_toolbar_preferences(self):
        visible = set(self.config.data.get("toolbar_visible_buttons", []))
        if hasattr(self, "toolbar_buttons"):
            for key, action in self.toolbar_buttons.items():
                action.setVisible(key in visible)

    def apply_title_preferences(self):
        current = self.workspace.current_path()
        title = str(current) if self.config.data.get("title_show_full_path", False) else (current.name or str(current))
        self.setWindowTitle(f"linux-file-manager - {title}")
        for index, state in enumerate(self._tabs):
            self._update_tab_title(index, state["path"])

    def go_up(self):
        current = self.workspace.current_path()
        if current and current.parent != current:
            self.go_to(current.parent)

    def go_home(self):
        self.go_to(Path.home())

    def go_back(self):
        target = self.navigation.back()
        if target is not None:
            self.go_to(target, record_history=False)
            self.update_navigation_actions()

    def go_forward(self):
        target = self.navigation.forward()
        if target is not None:
            self.go_to(target, record_history=False)
            self.update_navigation_actions()

    def on_go_to_path(self):
        self.go_to(Path(self.path_edit.text()).expanduser())

    def focus_path_bar(self):
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    # ─── Sidebar ───────────────────────────────────────────────

    def on_sidebar_item_activated(self, item):
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        try:
            target = Path(path)
        except Exception:
            return
        if not target.exists() or not target.is_dir():
            QMessageBox.warning(
                self,
                self.tr("Invalid location"),
                self.tr("This location is not available:\n{path}").format(path=path),
            )
            return
        self.go_to(target)

    def update_trash_count(self):
        """Update trash count in sidebar."""
        try:
            count = trash_count()
            self.sidebar.update_trash_count(count)
        except Exception:
            pass

    # ─── Workspace Events ──────────────────────────────────────

    def on_workspace_double_clicked(self, index):
        path = Path(self.workspace.model.filePath(index))
        if path.is_dir():
            self.go_to(path)
        else:
            self.open_file(path)

    def on_selection_changed(self, *_):
        path = self.workspace.selected_path()
        if path and path.exists():
            self.preview.show_path(path)
        else:
            self.preview.clear()
        self.app_state.set_selection_paths(self.workspace.selected_paths())
        self.update_quick_access_action()
        self.update_contextual_toolbar()
        self.update_statusbar()
        self.refresh_registry_enablement()

    def on_model_data_changed(self, *_):
        self.update_statusbar()

    def on_file_renamed(self, directory, old_name, new_name):
        """Record inline renames performed through QFileSystemModel."""
        if self._history_replaying:
            return
        old_path = Path(directory) / old_name
        new_path = Path(directory) / new_name
        self.record_operation(RenameOperation(old_path, new_path))
