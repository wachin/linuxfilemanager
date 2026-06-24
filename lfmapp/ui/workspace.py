"""Workspace for linux-file-manager.

Main file view area using QTreeView with QFileSystemModel.
Supports:
- List/detail view
- Icon view
- Path navigation
- Open folders and files
- Keyboard navigation
- Right-click context menu
- Multiple selection
"""

from pathlib import Path
from enum import Enum

from PyQt6.QtCore import QDir, Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QTreeView,
    QHeaderView,
    QListView,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QWidget,
    QVBoxLayout,
    QStackedWidget,
)

from lfmapp.models import FileSystemModel


class ViewMode(Enum):
    """View mode enumeration."""
    ICON = "icon"
    LIST = "list"
    DETAILS = "details"
    COMPACT = "compact"

    @classmethod
    def from_string(cls, value: str, default: "ViewMode" = None) -> "ViewMode":
        """Convert a string to a ViewMode, falling back to default."""
        if default is None:
            default = cls.DETAILS
        try:
            return cls(str(value).lower())
        except ValueError:
            return default


class IconGridSize(Enum):
    """Icon grid density presets."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

    @classmethod
    def from_string(cls, value: str, default: "IconGridSize" = None) -> "IconGridSize":
        """Convert a string to an IconGridSize, falling back to default."""
        if default is None:
            default = cls.MEDIUM
        try:
            return cls(str(value).lower())
        except ValueError:
            return default


class Workspace(QWidget):
    MIN_NAME_COLUMN_WIDTH = 180
    SIZE_COLUMN_WIDTH = 90
    TYPE_COLUMN_WIDTH = 120
    DATE_COLUMN_WIDTH = 160

    doubleClicked = pyqtSignal(object)
    customContextMenuRequested = pyqtSignal(object)
    filesDropped = pyqtSignal(list, str)  # paths, action: 'copy'|'move'
    selectionChanged = pyqtSignal(object, object)

    def __init__(self, parent=None, initial_path: Path | str | None = None, config=None):
        super().__init__(parent)
        self.config = config
        self._view_mode = ViewMode.DETAILS
        self._current_path = Path(initial_path).expanduser() if initial_path else Path.home()
        self._sort_key = "name"
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._group_key = "none"
        self._icon_grid_size = IconGridSize.MEDIUM

        # Create stacked widget for different views
        self.stacked_widget = QStackedWidget(self)

        # Create details view (QTreeView)
        self.details_view = QTreeView(self)
        self.details_view.setAlternatingRowColors(True)
        self.details_view.setUniformRowHeights(True)
        self.details_view.setSortingEnabled(True)
        self.details_view.setRootIsDecorated(False)
        self.details_view.setItemsExpandable(False)
        self.details_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.details_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.details_view.setEditTriggers(QTreeView.EditTrigger.EditKeyPressed)
        self.details_view.setDragEnabled(True)
        self.details_view.setAcceptDrops(True)
        self.details_view.setDropIndicatorShown(True)
        self.details_view.setDragDropMode(QTreeView.DragDropMode.DragDrop)

        # Create list view (QListView)
        self.list_view = QListView(self)
        self.list_view.setAlternatingRowColors(True)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setMovement(QListView.Movement.Static)
        self.list_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_view.setViewMode(QListView.ViewMode.ListMode)
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.list_view.setEditTriggers(QListView.EditTrigger.EditKeyPressed)
        self.list_view.setDragEnabled(True)
        self.list_view.setAcceptDrops(True)
        self.list_view.setDropIndicatorShown(True)
        self.list_view.setDragDropMode(QListView.DragDropMode.DragDrop)

        # Create icon view (QListView with IconMode)
        self.icon_view = QListView(self)
        self.icon_view.setAlternatingRowColors(True)
        self.icon_view.setUniformItemSizes(True)
        self.icon_view.setMovement(QListView.Movement.Static)
        self.icon_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.icon_view.setViewMode(QListView.ViewMode.IconMode)
        self._apply_icon_grid_size()
        self.icon_view.setWordWrap(True)
        self.icon_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.icon_view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.icon_view.setEditTriggers(QListView.EditTrigger.EditKeyPressed)
        self.icon_view.setDragEnabled(True)
        self.icon_view.setAcceptDrops(True)
        self.icon_view.setDropIndicatorShown(True)
        self.icon_view.setDragDropMode(QListView.DragDropMode.DragDrop)

        # Add views to stacked widget
        self.stacked_widget.addWidget(self.details_view)
        self.stacked_widget.addWidget(self.list_view)
        self.stacked_widget.addWidget(self.icon_view)

        # Create and set up the custom model
        self.model = FileSystemModel(self, root_path=self._current_path, config=config)

        # Set model for all views
        self.details_view.setModel(self.model)
        self.list_view.setModel(self.model)
        self.icon_view.setModel(self.model)

        # Configure details view columns
        self.details_view.setColumnWidth(0, 420)
        self.details_view.setColumnWidth(1, self.SIZE_COLUMN_WIDTH)
        self.details_view.setColumnWidth(2, self.TYPE_COLUMN_WIDTH)
        self.details_view.setColumnWidth(3, self.DATE_COLUMN_WIDTH)
        self.details_view.header().setStretchLastSection(False)
        self.details_view.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.details_view.header().setMinimumSectionSize(24)
        self.details_view.header().setSectionsMovable(True)
        self.details_view.header().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.details_view.header().customContextMenuRequested.connect(
            self._show_list_columns_dialog
        )
        self.sort_by(self._sort_key, self._sort_order)

        # Set initial path
        self.set_root_path(self._current_path)

        # Connect signals from all views
        self.details_view.doubleClicked.connect(self._forward_double_clicked)
        self.list_view.doubleClicked.connect(self._forward_double_clicked)
        self.icon_view.doubleClicked.connect(self._forward_double_clicked)

        self.details_view.selectionModel().selectionChanged.connect(self._forward_selection_changed)
        self.list_view.selectionModel().selectionChanged.connect(self._forward_selection_changed)
        self.icon_view.selectionModel().selectionChanged.connect(self._forward_selection_changed)

        self.details_view.customContextMenuRequested.connect(self._forward_context_menu_requested)
        self.list_view.customContextMenuRequested.connect(self._forward_context_menu_requested)
        self.icon_view.customContextMenuRequested.connect(self._forward_context_menu_requested)

        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stacked_widget)

        # Show details view by default
        self.set_view_mode(ViewMode.DETAILS)

        # Install event filter on views to handle drag & drop semantics
        for v in (self.details_view, self.list_view, self.icon_view):
            v.setAcceptDrops(True)
            v.installEventFilter(self)
        self.apply_preferences()

    def _ensure_name_column_width(self):
        """Keep the name column readable in Details view."""
        width = self.details_view.columnWidth(0)
        if width < self.MIN_NAME_COLUMN_WIDTH:
            self.details_view.setColumnWidth(0, self.MIN_NAME_COLUMN_WIDTH)

    def apply_preferences(self):
        if self.config is None:
            return
        self.model.apply_display_preferences()
        self.set_icon_grid_size(self.config.icon_grid_size)
        default_view = ViewMode.from_string(
            self.config.data.get("default_view_mode", "details"),
            ViewMode.DETAILS,
        )
        self.set_view_mode(default_view)
        order = (
            Qt.SortOrder.DescendingOrder
            if self.config.data.get("default_sort_descending", False)
            else Qt.SortOrder.AscendingOrder
        )
        self.sort_by(
            str(self.config.data.get("default_sort_key", "name")),
            order,
        )
        self.apply_list_columns_preferences()

    def apply_list_columns_preferences(self):
        if self.config is None:
            return
        visible = set(self.config.data.get("list_columns_visible", ["name", "size", "type", "modified"]))
        order = list(self.config.data.get("list_columns_order", ["name", "size", "type", "modified"]))
        column_map = {
            key: index for index, key in enumerate(self.model.COLUMN_KEYS)
        }
        visible.add("name")
        for key, column in column_map.items():
            self.details_view.setColumnHidden(column, key not in visible)
        header = self.details_view.header()
        visual_order = [column_map[key] for key in order if key in column_map]
        for visual_index, column in enumerate(visual_order):
            current = header.visualIndex(column)
            if current != visual_index:
                header.moveSection(current, visual_index)
        for key, width in (
            ("name", 420),
            ("size", self.SIZE_COLUMN_WIDTH),
            ("type", self.TYPE_COLUMN_WIDTH),
            ("modified", self.DATE_COLUMN_WIDTH),
        ):
            column = column_map[key]
            if self.details_view.columnWidth(column) <= self.details_view.header().minimumSectionSize():
                self.details_view.setColumnWidth(column, width)
        self._ensure_name_column_width()

    def _show_list_columns_dialog(self, _pos):
        if self.config is None:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("List Columns"))
        dialog.resize(320, 420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                self.tr("Choose the columns to show in the Details view."),
                dialog,
            )
        )

        list_widget = QListWidget(dialog)
        visible = set(
            self.config.data.get(
                "list_columns_visible",
                ["name", "size", "type", "modified"],
            )
        )
        order = list(
            self.config.data.get(
                "list_columns_order",
                ["name", "size", "type", "modified"],
            )
        )
        ordered_keys = [key for key in order if key in self.model.COLUMN_KEYS]
        ordered_keys.extend(
            key for key in self.model.COLUMN_KEYS if key not in ordered_keys
        )
        for key in ordered_keys:
            item = QListWidgetItem(self.model.COLUMN_LABELS[key], list_widget)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            checked = key == "name" or key in visible
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            list_widget.addItem(item)
        layout.addWidget(list_widget, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = []
        for index in range(list_widget.count()):
            item = list_widget.item(index)
            key = str(item.data(Qt.ItemDataRole.UserRole))
            if key == "name" or item.checkState() == Qt.CheckState.Checked:
                selected.append(key)
        self.config.data["list_columns_visible"] = selected
        self.config.data["list_columns_order"] = ordered_keys
        self.config.save()
        self.apply_list_columns_preferences()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._ensure_name_column_width()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent

        # Only handle drag enter and drop events from our views
        if event.type() == QEvent.Type.DragEnter:
            mime = event.mimeData()
            if mime.hasUrls():
                event.acceptProposedAction()
                return True
            return False

        if event.type() == QEvent.Type.Drop:
            mime = event.mimeData()
            if not mime.hasUrls():
                return False

            # Collect local file paths
            paths = []
            for url in mime.urls():
                if url.isLocalFile():
                    paths.append(Path(url.toLocalFile()))

            if not paths:
                return True

            # Decide action: Ctrl -> copy, Shift -> move, otherwise infer
            mods = event.keyboardModifiers()
            action = self.drop_action_for_paths(paths, self.current_path(), mods)

            # Emit to MainWindow to perform the operation
            self.filesDropped.emit(paths, action)
            event.acceptProposedAction()
            return True

        return super().eventFilter(obj, event)

    @staticmethod
    def drop_action_for_paths(paths: list[Path], destination: Path, modifiers: Qt.KeyboardModifier) -> str:
        """Return copy/move action for a drop based on modifiers and devices."""
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            return "copy"
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            return "move"
        try:
            src_dev = paths[0].stat().st_dev
            dest_dev = Path(destination).stat().st_dev
            return "move" if src_dev == dest_dev else "copy"
        except Exception:
            return "copy"

    def _forward_double_clicked(self, index):
        """Forward double-clicked signal from any view."""
        self.doubleClicked.emit(index)

    def _forward_selection_changed(self, selected, deselected):
        """Forward selection changed signal from any view."""
        self.selectionChanged.emit(selected, deselected)

    def _forward_context_menu_requested(self, pos):
        """Forward context menu request from any view."""
        self.customContextMenuRequested.emit(pos)

    def _get_current_view(self):
        """Get the currently visible view widget."""
        if self._view_mode == ViewMode.DETAILS:
            return self.details_view
        elif self._view_mode == ViewMode.LIST:
            return self.list_view
        else:
            return self.icon_view

    def set_view_mode(self, mode: ViewMode):
        """Set the current view mode."""
        self._view_mode = mode
        if mode == ViewMode.DETAILS:
            self.stacked_widget.setCurrentWidget(self.details_view)
            self._ensure_name_column_width()
        elif mode == ViewMode.LIST:
            self.stacked_widget.setCurrentWidget(self.list_view)
        elif mode == ViewMode.ICON:
            # Standard icon view with the configured grid density.
            self.icon_view.setViewMode(QListView.ViewMode.IconMode)
            self._apply_icon_grid_size()
            self.stacked_widget.setCurrentWidget(self.icon_view)
        else:
            # Compact icon view (smaller icons, denser grid)
            self.icon_view.setViewMode(QListView.ViewMode.IconMode)
            self.icon_view.setIconSize(QSize(32, 32))
            self.icon_view.setGridSize(QSize(64, 64))
            self.stacked_widget.setCurrentWidget(self.icon_view)

    def view_mode(self) -> ViewMode:
        """Get the current view mode."""
        return self._view_mode

    def set_icon_grid_size(self, size: IconGridSize | str):
        """Set the icon view grid density."""
        if not isinstance(size, IconGridSize):
            size = IconGridSize.from_string(str(size), self._icon_grid_size)
        self._icon_grid_size = size
        if self._view_mode == ViewMode.ICON:
            self._apply_icon_grid_size()

    def icon_grid_size(self) -> IconGridSize:
        """Return the active icon grid density."""
        return self._icon_grid_size

    def _apply_icon_grid_size(self):
        """Apply the configured icon grid dimensions to the icon view."""
        sizes = {
            IconGridSize.SMALL: (QSize(48, 48), QSize(82, 82), 6),
            IconGridSize.MEDIUM: (QSize(64, 64), QSize(96, 96), 8),
            IconGridSize.LARGE: (QSize(96, 96), QSize(132, 132), 10),
        }
        icon_size, grid_size, spacing = sizes[self._icon_grid_size]
        self.icon_view.setIconSize(icon_size)
        self.icon_view.setGridSize(grid_size)
        self.icon_view.setSpacing(spacing)

    def set_root_path(self, path: Path):
        """Set the root path for all views."""
        self._current_path = path
        index = self.model.index(str(path))
        self.details_view.setRootIndex(index)
        self.list_view.setRootIndex(index)
        self.icon_view.setRootIndex(index)
        self._ensure_name_column_width()

    def current_path(self) -> Path:
        """Get the current root path."""
        return self._current_path

    def selected_path(self) -> Path | None:
        """Return the path of the currently selected item."""
        view = self._get_current_view()
        index = view.currentIndex()
        if index.isValid():
            return Path(self.model.filePath(index))
        return None

    def selected_paths(self) -> list[Path]:
        """Return list of all selected file/folder paths."""
        view = self._get_current_view()
        paths = []
        for index in view.selectedIndexes():
            # Only count column 0 to avoid duplicates in details view
            if self._view_mode == ViewMode.DETAILS and index.column() != 0:
                continue
            path = Path(self.model.filePath(index))
            if path not in paths:
                paths.append(path)
        for path in self.model.checked_paths():
            if path not in paths:
                paths.append(path)
        return paths

    def selectionModel(self):
        """Return the selection model of the current view."""
        return self._get_current_view().selectionModel()

    def currentIndex(self):
        """Return the current index of the current view."""
        return self._get_current_view().currentIndex()

    def setAlternatingRowColors(self, enable: bool):
        """Set alternating row colors for all views."""
        self.details_view.setAlternatingRowColors(enable)
        self.list_view.setAlternatingRowColors(enable)
        self.icon_view.setAlternatingRowColors(enable)

    def setSortingEnabled(self, enable: bool):
        """Set sorting enabled for all views."""
        self.details_view.setSortingEnabled(enable)
        # List and icon views use the same sorting as the model

    def sort_by(self, key: str, order: Qt.SortOrder | None = None):
        """Sort all workspace views by a known file model column."""
        columns = {
            "name": 0,
            "size": 1,
            "type": 2,
            "modified": 3,
        }
        if key not in columns:
            key = "name"
        if order is None:
            order = self._sort_order

        self._sort_key = key
        self._sort_order = order
        column = columns[key]
        self.model.sort(column, order)
        self.details_view.sortByColumn(column, order)
        self.details_view.header().setSortIndicator(column, order)

    def group_by(self, key: str, order: Qt.SortOrder | None = None):
        """Group the workspace by a known file-model column."""
        groups = {
            "none": "name",
            "name": "name",
            "type": "type",
            "size": "size",
            "modified": "modified",
        }
        if key not in groups:
            key = "none"
        self._group_key = key
        self.sort_by(groups[key], order)

    def group_key(self) -> str:
        """Return the active group key."""
        return self._group_key

    def sort_key(self) -> str:
        """Return the active sort key."""
        return self._sort_key

    def sort_order(self) -> Qt.SortOrder:
        """Return the active sort order."""
        return self._sort_order

    def setRootIsDecorated(self, decorated: bool):
        """Set root decoration for details view."""
        self.details_view.setRootIsDecorated(decorated)

    def setItemsExpandable(self, expandable: bool):
        """Set items expandable for details view."""
        self.details_view.setItemsExpandable(expandable)

    def setContextMenuPolicy(self, policy: Qt.ContextMenuPolicy):
        """Set context menu policy for all views."""
        self.details_view.setContextMenuPolicy(policy)
        self.list_view.setContextMenuPolicy(policy)
        self.icon_view.setContextMenuPolicy(policy)

    def setSelectionMode(self, mode: QTreeView.SelectionMode):
        """Set selection mode for all views."""
        self.details_view.setSelectionMode(mode)
        self.list_view.setSelectionMode(mode)
        self.icon_view.setSelectionMode(mode)

    def setEditTriggers(self, triggers: QTreeView.EditTrigger):
        """Set edit triggers for all views."""
        self.details_view.setEditTriggers(triggers)
        self.list_view.setEditTriggers(triggers)
        self.icon_view.setEditTriggers(triggers)

    def selectAll(self):
        """Select all items in the current view."""
        self._get_current_view().selectAll()

    def clearSelection(self):
        """Clear selection in the current view."""
        self._get_current_view().clearSelection()

    def selectedIndexes(self):
        """Return selected indexes from the current view."""
        return self._get_current_view().selectedIndexes()

    def edit(self, index) -> None:
        """Start inline editing in the currently visible view."""
        self._get_current_view().edit(index)

    def setRootIndex(self, index):
        """Set root index for all views."""
        self.details_view.setRootIndex(index)
        self.list_view.setRootIndex(index)
        self.icon_view.setRootIndex(index)

    def indexAt(self, pos):
        """Get index at position in the current view."""
        return self._get_current_view().indexAt(pos)

    def viewport(self):
        """Get viewport of the current view."""
        return self._get_current_view().viewport()

    def setDragEnabled(self, enable: bool):
        """Set drag enabled for all views."""
        self.details_view.setDragEnabled(enable)
        self.list_view.setDragEnabled(enable)
        self.icon_view.setDragEnabled(enable)

    def setAcceptDrops(self, accept: bool):
        """Set accept drops for all views."""
        self.details_view.setAcceptDrops(accept)
        self.list_view.setAcceptDrops(accept)
        self.icon_view.setAcceptDrops(accept)

    def setDropIndicatorShown(self, show: bool):
        """Set drop indicator shown for all views."""
        self.details_view.setDropIndicatorShown(show)
        self.list_view.setDropIndicatorShown(show)
        self.icon_view.setDropIndicatorShown(show)

    def setDragDropMode(self, mode: QTreeView.DragDropMode):
        """Set drag drop mode for all views."""
        self.details_view.setDragDropMode(mode)
        self.list_view.setDragDropMode(mode)
        self.icon_view.setDragDropMode(mode)

    def set_root_path(self, path: Path):
        self._current_path = path
        self.setRootIndex(self.model.index(str(path)))

    def current_path(self) -> Path:
        return self._current_path

    def selected_path(self) -> Path | None:
        index = self.currentIndex()
        if index.isValid():
            return Path(self.model.filePath(index))
        return None

    def selected_paths(self) -> list[Path]:
        """Return list of all selected file/folder paths."""
        paths = []
        for index in self.selectedIndexes():
            # Only count column 0 to avoid duplicates
            if index.column() == 0:
                path = Path(self.model.filePath(index))
                if path not in paths:
                    paths.append(path)
        for path in self.model.checked_paths():
            if path not in paths:
                paths.append(path)
        return paths
