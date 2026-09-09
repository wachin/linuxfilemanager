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


class TabsNavigationMixin:
    # ─── Keyboard Shortcuts ────────────────────────────────────

    def setup_shortcuts(self):
        """Set up additional keyboard shortcuts.

        Window-level bindings live here only when there is no equivalent menu
        action (which would otherwise create a duplicate shortcut). `Ctrl+Shift+P`
        (palette) and `Ctrl+Shift+I` (invert selection) are provided by menu
        actions, so they are intentionally omitted here.
        """
        shortcuts = [
            ("Delete", Qt.Key.Key_Delete, self.trash_selected, "trash_selected"),
            ("Shift+Delete", "Shift+Delete", self.delete_selected, "delete_permanently"),
            ("F2", Qt.Key.Key_F2, self.rename_selected, "rename"),
            ("Ctrl+L", "Ctrl+L", self.focus_path_bar, "focus_path"),
            ("Ctrl+E", "Ctrl+E", self.focus_search, "focus_search"),
            ("Alt+Down", "Alt+Down", self._expand_or_navigate_down, "expand_down"),
        ]
        for _label, seq, slot, command_id in shortcuts:
            sc = QShortcut(QKeySequence(seq), self, slot)
            if hasattr(self, "shortcut_map"):
                # Record window-level bindings in the single-source shortcut map.
                self.shortcut_map.register(
                    command_id,
                    _label,
                    shortcut=QKeySequence(seq).toString(QKeySequence.SequenceFormat.NativeText),
                    category=self.tr("Keyboard"),
                    callback=slot,
                )

    # ─── Inline expansion helpers (Alt+Down/Up) ────────────────

    def _expand_or_navigate_down(self) -> None:
        """Alt+Down: expand the current folder if possible; else move selection down."""
        if not self.config.inline_tree_expansion:
            self._move_selection_down()
            return
        view = self.workspace.details_view
        idx = view.currentIndex()
        if idx.isValid() and view.canExpand(idx):
            view.expand(idx)
        else:
            self._move_selection_down()

    def _collapse_or_navigate_up(self) -> None:
        """Alt+Up: collapse the current folder if expanded; else move selection up."""
        if not self.config.inline_tree_expansion:
            self._move_selection_up()
            return
        view = self.workspace.details_view
        idx = view.currentIndex()
        if idx.isValid() and view.isExpanded(idx):
            view.collapse(idx)
        else:
            self._move_selection_up()

    def _expand_recursive(self) -> None:
        """Ctrl+Alt+Down: expand the selected folder and all descendants."""
        view = self.workspace.details_view
        idx = view.currentIndex()
        if idx.isValid():
            view.expandRecursively(idx, 10)

    def _collapse_all(self) -> None:
        """Ctrl+Alt+Left: collapse all expanded branches."""
        self.workspace.details_view.collapseAll()

    def _move_selection_down(self) -> None:
        """Move selection to the next row in the current view."""
        view = self.workspace._get_current_view()
        idx = view.currentIndex()
        if not idx.isValid():
            return
        model = view.model()
        next_row = idx.row() + 1
        if next_row < model.rowCount(idx.parent()):
            view.setCurrentIndex(model.index(next_row, idx.column(), idx.parent()))

    def _move_selection_up(self) -> None:
        """Move selection to the previous row in the current view."""
        view = self.workspace._get_current_view()
        idx = view.currentIndex()
        if not idx.isValid():
            return
        model = view.model()
        prev_row = idx.row() - 1
        if prev_row >= 0:
            view.setCurrentIndex(model.index(prev_row, idx.column(), idx.parent()))

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
            self.show_warning_banner(
                self.tr("Path does not exist or is not a folder: {path}").format(path=path)
            )
            return
        self.workspace.set_root_path(path)
        self.app_state.set_path(path)
        # Restore the remembered visual presentation for this folder (P2):
        # view mode + sort + group + grid as one folder format; the columns
        # are restored by the workspace on set_root_path.
        self.restore_folder_format(path)
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
            self.show_warning_banner(
                self.tr("This location is not available: {path}").format(path=path)
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

    def on_flat_entry_activated(self, path):
        """Open a flat-view row: folders navigate, files open (P2)."""
        path = Path(path)
        if path.is_dir():
            self.go_to(path)
        else:
            self.open_file(path)

    def on_flat_scan_finished(self, count: int):
        """Report the end of a flat scan without interrupting navigation."""
        if self.workspace.view_mode().value == "flat":
            self.statusBar().showMessage(
                self.tr("Flat view: {count} item(s) from the whole tree").format(count=count),
                4000,
            )

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
