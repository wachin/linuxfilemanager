"""View controls & trash ops extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QMessageBox

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

    def toggle_inline_expansion(self, checked: bool):
        """Toggle expandable folders in the Details view (inline tree arrows)."""
        self.workspace.setRootIsDecorated(checked)
        self.workspace.setItemsExpandable(checked)
        self.config.set_inline_tree_expansion(checked)
        state = self.tr("enabled") if checked else self.tr("disabled")
        self.statusBar().showMessage(
            self.tr("Expandable folders {state}").format(state=state), 3000
        )

    def expand_current_folder(self):
        """Expand the currently selected folder row in the details view."""
        view = self.workspace.details_view
        if not view.isExpanded(view.currentIndex()):
            view.expand(view.currentIndex())

    def collapse_current_folder(self):
        """Collapse the currently selected folder row in the details view."""
        view = self.workspace.details_view
        if view.isExpanded(view.currentIndex()):
            view.collapse(view.currentIndex())

    def expand_recursive_selected(self):
        """Expand the selected folder and all its sub-folders recursively."""
        view = self.workspace.details_view
        view.expandRecursively(view.currentIndex(), 10)

    def collapse_all_expanded(self):
        """Collapse all expanded branches in the details view."""
        view = self.workspace.details_view
        view.collapseAll()

    def show_highlighting_rules(self):
        """Open the appearance-rules editor and re-apply on accept."""
        from lfmapp.ui.highlight_rules_dialog import HighlightRulesDialog

        dlg = HighlightRulesDialog(self.config, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.reload_highlighting()

    def set_view_mode(self, mode: ViewMode):
        """Set the workspace view mode (Icon, List, or Details)."""
        self.workspace.set_view_mode(mode)
        self.app_state.set_view_mode(mode.value)
        # Persist the complete folder format for the current folder (P2);
        # the legacy view-only store stays in sync through the controller.
        self.view_controller.remember_format(
            self.workspace.current_path(),
            mode,
            self.workspace.sort_key(),
            self.workspace.group_key(),
            self.workspace.icon_grid_size().value,
            flat_mode=self.workspace.flat_view_mode_value(),
        )
        self._sync_sort_group_menu_state()
        mode_name = mode.value.capitalize()
        self.statusBar().showMessage(self.tr("View mode: {mode}").format(mode=mode_name), 3000)

    def set_flat_view_mode(self, mode):
        """Set the flat view degree and persist it in the folder format."""
        self.workspace.set_flat_view_mode(mode)
        self._remember_current_folder_format()
        self._sync_sort_group_menu_state()
        self.statusBar().showMessage(
            self.tr("Flat view: {mode}").format(mode=self.workspace.flat_view_mode_value()),
            3000,
        )

    def _remember_current_folder_format(self):
        """Snapshot the current visual presentation as this folder's format."""
        self.view_controller.remember_format(
            self.workspace.current_path(),
            self.workspace.view_mode(),
            self.workspace.sort_key(),
            self.workspace.group_key(),
            self.workspace.icon_grid_size().value,
            flat_mode=self.workspace.flat_view_mode_value(),
        )

    def _sync_sort_group_menu_state(self):
        """Refresh the sort/group/grid menu checkmarks from the workspace."""
        for sort_key, action in self._sort_column_actions.items():
            action.setChecked(sort_key == self.workspace.sort_key())
        for sort_order, action in self._sort_order_actions.items():
            action.setChecked(sort_order == self.workspace.sort_order())
        for group_key, action in self._group_actions.items():
            action.setChecked(group_key == self.workspace.group_key())
        for grid_size, action in self._icon_grid_actions.items():
            action.setChecked(grid_size == self.workspace.icon_grid_size())
        flat_actions = getattr(self, "_flat_mode_actions", None)
        if flat_actions:
            from lfmapp.services.flat_view_service import FlatViewMode

            for mode, action in flat_actions.items():
                action.setChecked(
                    FlatViewMode.from_string(
                        self.workspace.flat_view_mode_value(), FlatViewMode.MIXED
                    )
                    == mode
                )

    def set_icon_grid_size(self, size: IconGridSize):
        """Set and persist the icon grid density."""
        self.workspace.set_icon_grid_size(size)
        self.config.set_icon_grid_size(self.workspace.icon_grid_size().value)
        for grid_size, action in self._icon_grid_actions.items():
            action.setChecked(grid_size == self.workspace.icon_grid_size())
        self._remember_current_folder_format()
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
        self._remember_current_folder_format()
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
        self._remember_current_folder_format()
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

    def restore_folder_format(self, path) -> None:
        """Apply the remembered visual format for a folder (P2).

        Called on navigation: view mode, sort, group and icon grid are
        restored together; columns are handled by the workspace itself.
        Absent/ignored folders keep the current presentation (global
        defaults), and the menu checkmarks are refreshed either way.
        """
        from lfmapp.ui.workspace import ViewMode as _ViewMode

        fmt = self.view_controller.format_to_restore(path)
        if fmt is not None:
            view_mode = _ViewMode.from_string(fmt.get("view", ""), self.workspace.view_mode())
            if view_mode != self.workspace.view_mode():
                self.workspace.set_view_mode(view_mode)
                self.app_state.set_view_mode(view_mode.value)
                self.statusBar().showMessage(
                    self.tr("Restored saved view: {view}").format(view=view_mode.value),
                    3000,
                )
            # Apply group before sort: Workspace.group_by("none") re-sorts by
            # name, so sort must have the final word to keep the saved order.
            if fmt.get("group"):
                self.workspace.group_by(fmt["group"], self.workspace.sort_order())
            if fmt.get("sort"):
                self.workspace.sort_by(fmt["sort"], self.workspace.sort_order())
            if fmt.get("grid"):
                from lfmapp.ui.workspace import IconGridSize as _IconGridSize

                self.workspace.set_icon_grid_size(
                    _IconGridSize.from_string(fmt["grid"], self.workspace.icon_grid_size())
                )
            if fmt.get("flat_mode"):
                self.workspace.set_flat_view_mode(fmt["flat_mode"])
        self._sync_sort_group_menu_state()

    def refresh_view(self):
        """Refresh the current directory view."""
        current = self.workspace.current_path()
        if current:
            self.workspace.model.setRootPath("")
            self.workspace.set_root_path(current)
            self.update_statusbar()

    def select_all(self):
        """Select every visible row; keep checks in sync in checkbox mode."""
        self.workspace.selectAll()
        model = self.workspace.model
        if model.show_selection_checkboxes:
            model.set_checked_paths(self.workspace.selected_paths())

    def deselect_all(self):
        self.workspace.clearSelection()
        self.workspace.model.clear_checked_paths()

    def invert_selection(self):
        """Invert the effective selection (view selection ∪ checkboxes).

        Fixes audit T16: the previous version always used the details-view
        root and ignored `_checked_paths`, so checked items kept counting
        after an invert.  Now it operates on the active view and, in checkbox
        mode, rewrites the checks as the source of truth.
        """
        model = self.workspace.model
        view = self.workspace._get_current_view()
        root = view.rootIndex()
        currently = {str(self.workspace.model.filePath(i))
                     for i in self.workspace.selectedIndexes() if i.column() == 0}
        currently |= {str(p) for p in model.checked_paths()}

        sm = view.selectionModel()
        self.workspace.clearSelection()
        inverse_paths: list = []
        for row in range(model.rowCount(root)):
            index = model.index(row, 0, root)
            if not index.isValid():
                continue
            path = Path(model.filePath(index))
            if str(path) in currently:
                continue
            sm.select(index, sm.SelectionFlag.Select | sm.SelectionFlag.Rows)
            inverse_paths.append(path)

        if model.show_selection_checkboxes:
            model.set_checked_paths(inverse_paths)
            self.workspace.clearSelection()

    def toggle_checked_for_current(self):
        """Space: flip the checkbox of the currently selected item(s)."""
        model = self.workspace.model
        if not model.show_selection_checkboxes:
            return False
        selected = self.workspace.selected_paths()
        if not selected:
            return False
        current_checks = {str(p) for p in model.checked_paths()}
        for path in selected:
            if str(path) in current_checks:
                current_checks.discard(str(path))
            else:
                current_checks.add(str(path))
        model.set_checked_paths([Path(p) for p in current_checks])
        return True

    def select_by_dialog(self):
        """Open the "Select By…" dialog and apply the resulting subset."""
        from lfmapp.controllers import SelectionController, SelectionCriteria
        from lfmapp.ui.select_by_dialog import SelectByDialog

        view = self.workspace._get_current_view()
        model = self.workspace.model
        root = view.rootIndex()
        all_paths = []
        for row in range(model.rowCount(root)):
            index = model.index(row, 0, root)
            if index.isValid():
                all_paths.append(Path(model.filePath(index)))

        dlg = SelectByDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        criteria: SelectionCriteria = dlg.criteria()
        if not criteria.is_active():
            self.show_info_banner(self.tr("No criteria set — nothing selected."))
            return
        matches = SelectionController.select_by(all_paths, criteria)
        if model.show_selection_checkboxes:
            model.set_checked_paths(matches)
        else:
            self.workspace.clearSelection()
            sm = view.selectionModel()
            for path in matches:
                for row in range(model.rowCount(root)):
                    index = model.index(row, 0, root)
                    if index.isValid() and Path(model.filePath(index)) == path:
                        sm.select(index, sm.SelectionFlag.Select | sm.SelectionFlag.Rows)
                        break
        self.statusBar().showMessage(
            self.tr("Selected {n} item(s) by criteria").format(n=len(matches)), 3000
        )
        self.update_statusbar()

    # ─── Batch action bar (Phase 6.1) ──────────────────────────

    def build_selection_bar(self, central_layout):
        """Create the batch action bar (hidden until a selection exists)."""
        from lfmapp.ui.selection_bar import SelectionBar

        self.selection_bar = SelectionBar(self)
        central_layout.insertWidget(2, self.selection_bar)
        self.selection_bar.copy_requested.connect(self.copy_selected)
        self.selection_bar.cut_requested.connect(self.cut_selected)
        self.selection_bar.trash_requested.connect(self.trash_selected)
        self.selection_bar.delete_requested.connect(self.delete_selected)
        self.selection_bar.rename_requested.connect(self.rename_selected_dialog)
        self.selection_bar.invert_requested.connect(self.invert_selection)
        self.selection_bar.select_by_requested.connect(self.select_by_dialog)
        self.selection_bar.clear_requested.connect(self.deselect_all)

    def update_selection_bar(self):
        """Refresh the batch bar's summary and visibility from the selection."""
        bar = getattr(self, "selection_bar", None)
        if bar is None:
            return
        from lfmapp.controllers import SelectionController

        summary = SelectionController.summarize(self.workspace.selected_paths())
        size_text = ""
        if summary.file_count:
            size_text = self._human_size(summary.total_file_size())
        bar.update_for(summary.file_count, summary.folder_count, size_text)

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
