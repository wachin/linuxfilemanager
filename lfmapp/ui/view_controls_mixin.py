"""View controls & trash ops extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from lfmapp.services import empty_trash
from lfmapp.ui.workspace import IconGridSize, ViewMode


class ViewControlsMixin:
    # ─── View Controls ─────────────────────────────────────────

    def toggle_preview(self):
        visible = not self.preview.isVisible()
        self.settings_controller.set_preview_visible(visible)

    def toggle_sidebar(self):
        visible = not self.sidebar.isVisible()
        self.settings_controller.set_sidebar_visible(visible)
        self.statusBar().showMessage(
            self.tr("Sidebar shown") if visible else self.tr("Sidebar hidden"),
            3000,
        )

    def toggle_hidden_files(self, checked=None):
        show_hidden = (not self.config.show_hidden_files) if checked is None else bool(checked)
        self.settings_controller.set_hidden_files_visible(show_hidden)
        state = self.tr("shown") if show_hidden else self.tr("hidden")
        self.statusBar().showMessage(self.tr("Hidden files {state}").format(state=state), 3000)

    def apply_hidden_files_visibility(self, show_hidden: bool):
        self.settings_controller.apply_hidden_files_visibility(show_hidden)

    def toggle_file_extensions(self, checked=None):
        """Toggle showing file extensions in the name column."""
        model = self.workspace.model
        show_extensions = (not model.show_extensions) if checked is None else bool(checked)
        self.settings_controller.set_file_extensions_visible(show_extensions)
        state = self.tr("shown") if model.show_extensions else self.tr("hidden")
        self.statusBar().showMessage(self.tr("File extensions {state}").format(state=state), 3000)

    def toggle_selection_checkboxes(self, checked: bool):
        """Toggle optional checkboxes used for item selection."""
        model = self.workspace.model
        self.settings_controller.set_selection_checkboxes_visible(checked)
        state = self.tr("shown") if checked else self.tr("hidden")
        self.statusBar().showMessage(self.tr("Selection checkboxes {state}").format(state=state), 3000)

    def set_view_mode(self, mode: ViewMode):
        """Set the workspace view mode (Icon, List, or Details)."""
        self.workspace.set_view_mode(mode)
        self.app_state.set_view_mode(mode.value)
        # Persist view type for current folder (policy lives in the controller).
        self.view_controller.remember(self.workspace.current_path(), mode)
        mode_name = mode.value.capitalize()
        self.statusBar().showMessage(self.tr("View mode: {mode}").format(mode=mode_name), 3000)

    def set_icon_grid_size(self, size: IconGridSize):
        """Set and persist the icon grid density."""
        self.workspace.set_icon_grid_size(size)
        self.config.set_icon_grid_size(self.workspace.icon_grid_size().value)
        for grid_size, action in self._icon_grid_actions.items():
            action.setChecked(grid_size == self.workspace.icon_grid_size())
        label = self.workspace.icon_grid_size().value.capitalize()
        self.statusBar().showMessage(self.tr("Icon grid size: {label}").format(label=label), 3000)

    def set_sort(self, key: str | None = None, order: Qt.SortOrder | None = None):
        """Apply sorting to the workspace and update menu checkmarks."""
        if key is None:
            key = self.workspace.sort_key()
        if order is None:
            order = self.workspace.sort_order()
        self.workspace.sort_by(key, order)
        for sort_key, action in self._sort_column_actions.items():
            action.setChecked(sort_key == self.workspace.sort_key())
        for sort_order, action in self._sort_order_actions.items():
            action.setChecked(sort_order == self.workspace.sort_order())
        order_name = self.tr("ascending") if order == Qt.SortOrder.AscendingOrder else self.tr("descending")
        self.statusBar().showMessage(
            self.tr("Sorted by {key} ({order})").format(key=key, order=order_name),
            3000,
        )

    def set_group(self, key: str | None = None, order: Qt.SortOrder | None = None):
        """Apply grouping to the workspace and update menu checkmarks."""
        if key is None:
            key = self.workspace.group_key()
        if order is None:
            order = self.workspace.sort_order()
        self.workspace.group_by(key, order)
        for group_key, action in self._group_actions.items():
            action.setChecked(group_key == self.workspace.group_key())
        if self.workspace.group_key() == "none":
            self.statusBar().showMessage(self.tr("Grouping disabled"), 3000)
        else:
            self.statusBar().showMessage(
                self.tr("Grouped by {key}").format(key=self.workspace.group_key()),
                3000,
            )

    def toggle_folder_view_persistence(self, checked: bool):
        self.view_controller.set_enabled(bool(checked))
        self.update_view_persistence_indicator()
        state = self.tr("enabled") if checked else self.tr("disabled")
        self.statusBar().showMessage(
            self.tr("Folder view persistence {state}").format(state=state),
            3000,
        )

    def update_view_persistence_indicator(self):
        if self.view_controller.enabled:
            self.status_view_persistence.setText(self.tr("Persist: On"))
            self.status_view_persistence.setStyleSheet(
                "background: #3a9d23; color: white; border-radius: 6px; padding: 2px 8px;"
            )
        else:
            self.status_view_persistence.setText(self.tr("Persist: Off"))
            self.status_view_persistence.setStyleSheet(
                "background: #d85a5a; color: white; border-radius: 6px; padding: 2px 8px;"
            )
        self.status_view_persistence.setToolTip(self.tr("Remember folder view settings across navigation"))

    def clear_current_folder_view(self):
        self.view_controller.clear(self.workspace.current_path())
        self.statusBar().showMessage(self.tr("Cleared saved view for current folder"), 3000)

    def clear_all_folder_views(self):
        self.view_controller.clear_all()
        self.statusBar().showMessage(self.tr("Cleared all saved folder views"), 3000)

    def refresh_view(self):
        """Refresh the current directory view."""
        current = self.workspace.current_path()
        if current:
            self.workspace.model.setRootPath("")
            self.workspace.set_root_path(current)
            self.update_statusbar()

    def select_all(self):
        self.workspace.selectAll()

    def deselect_all(self):
        self.workspace.clearSelection()
        self.workspace.model.clear_checked_paths()

    def invert_selection(self):
        """Invert the current selection: selected items become unselected and vice versa."""
        model = self.workspace.model
        root = self.workspace.details_view.rootIndex()
        selected_indexes = set(self.workspace.selectedIndexes())
        # Only consider column 0 indexes for selection
        column0_selected = {idx for idx in selected_indexes if idx.column() == 0}

        # Get all visible items
        all_items = []
        for row in range(model.rowCount(root)):
            index = model.index(row, 0, root)
            if index.isValid():
                all_items.append(index)

        # Build new selection: invert column 0 items
        self.workspace.clearSelection()
        for index in all_items:
            if index not in column0_selected:
                self.workspace.selectionModel().select(
                    index,
                    self.workspace.selectionModel().SelectionFlag.Select
                )

    # ─── Trash Operations ──────────────────────────────────────

    def on_empty_trash(self):
        answer = QMessageBox.question(
            self,
            self.tr("Empty Trash"),
            self.tr("Are you sure you want to permanently delete all items in the Trash?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            empty_trash()
            self.statusBar().showMessage(self.tr("Trash emptied"), 5000)
            self.update_trash_count()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Could not empty trash:\n{error}").format(error=exc),
            )
