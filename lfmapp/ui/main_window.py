"""Main window for linux-file-manager.

Implements the full main window with:
- Navigation toolbar (Back, Forward, Up, Home)
- Editable path bar
- Search bar
- Sidebar with Quick Access, Computer, Bookmarks
- Workspace with file listing
- Preview panel (toggleable)
- Status bar with item count, selection size, disk space
- Full keyboard shortcuts
- Context menus with archive extraction and tagging
"""

import os
import mimetypes
import shutil
from pathlib import Path
import subprocess

from PyQt6.QtCore import QDir, Qt
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabBar,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QMenu,
    QInputDialog,
    QFileDialog,
    QDialog,
    QScrollArea,
    QProgressBar,
    QFrame,
    QSizePolicy,
    QWidgetAction,
    QToolButton,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

from lfmapp.core.config import Config
from lfmapp.core.xdg import get_xdg_user_dirs
from lfmapp.services import (
    FileOperations,
    BookmarkService,
    SearchFilters,
    SearchThread,
    is_archive,
    ExtractThread,
    CompressThread,
    send_to_trash,
    trash_count,
    empty_trash,
    list_trash,
    restore_from_trash,
    CopyWorker,
    MoveWorker,
    DeleteWorker,
    TrashWorker,
    BackgroundOperationQueue,
    OperationHistory,
    RenameOperation,
    CreateOperation,
    MoveOperation,
    CopyOperation,
    TrashOperation,
    CompositeOperation,
    TerminalService,
)
from lfmapp.services.textindex_service import TextIndexService
from lfmapp.ui.about_dialog import AboutDialog
from lfmapp.ui.create_multiple_dialog import CreateMultipleDialog
from lfmapp.ui.icons import app_icon, application_icon
from lfmapp.ui.property_dialog import AdvancedSecurityDialog, PropertyDialog
from lfmapp.ui.preview_panel import PreviewPanel
from lfmapp.ui.settings_controller import SettingsController
from lfmapp.services.preview_worker import PreviewWorker
from lfmapp.ui.search_filter_dialog import SearchFilterDialog
from lfmapp.ui.sidebar import Sidebar
from lfmapp.ui.tag_management_dialog import TagManagementDialog
from lfmapp.ui.tag_search_dialog import TagSearchDialog
from lfmapp.ui.workspace import IconGridSize, Workspace, ViewMode
from lfmapp.utils.open_with import (
    get_available_applications,
    launch_application_for_path,
    open_with_default,
    send_email_with_attachments,
    set_default_application_for_file,
)


class MainWindow(QMainWindow):
    def __init__(self, config: Config | None = None):
        super().__init__()
        self.setWindowTitle("linux-file-manager")
        self.setWindowIcon(application_icon())
        self.config = config or Config()
        self.terminal_service = TerminalService(self.config)
        self.settings_controller = SettingsController(self)
        self._apply_window_size_from_config()
        self.bookmark_service = BookmarkService(
            bookmarks_file=self.config.file_path.parent / "bookmarks.json"
        )
        self._tag_service = None
        self._vault_service = None
        self._tag_db_file = self.config.file_path.parent / "tags.db"
        self.history: list[Path] = []
        self.history_index = -1
        self._tabs = []
        self._active_tab_index = -1
        self._clipboard_paths: list[Path] = []
        self._clipboard_mode = None  # "copy" or "cut"
        self._current_search = None
        self._current_search_results = []
        self._active_search_filters = SearchFilters()
        self._extract_thread = None
        self._text_index_service = None
        self._indexer_service = None
        self.operation_history = OperationHistory()
        self._operation_queue = BackgroundOperationQueue(max_concurrent=1, parent=self)
        self._operation_queue.operation_started.connect(self._on_queued_worker_started)
        self._history_replaying = False

        startup_path = self._startup_path()

        # --- UI Components ---
        self.sidebar = Sidebar(self.bookmark_service.bookmarks)
        self.sidebar.set_recent_locations(self.config.recent_locations)
        self.sidebar.set_frequent_folders(self.config.frequent_folders())
        self.sidebar.itemActivated.connect(self.on_sidebar_item_activated)

        self.workspace = Workspace(initial_path=startup_path, config=self.config)
        self.workspace.set_icon_grid_size(self.config.icon_grid_size)
        self.workspace.model.show_selection_checkboxes = self.config.selection_checkboxes
        self.workspace.model.show_extensions = self.config.show_file_extensions
        self.apply_hidden_files_visibility(self.config.show_hidden_files)
        self.workspace.model.dataChanged.connect(self.on_model_data_changed)
        self.workspace.model.fileRenamed.connect(self.on_file_renamed)
        self.workspace.doubleClicked.connect(self.on_workspace_double_clicked)
        self.workspace.selectionChanged.connect(self.on_selection_changed)
        self.workspace.customContextMenuRequested.connect(self.open_context_menu)
        self.workspace.filesDropped.connect(self.on_files_dropped)
        self._drop_workers = []
        self._trash_worker_operations = {}
        self._operation_batches = {}
        self._sort_column_actions = {}
        self._sort_order_actions = {}
        self._group_actions = {}
        self._icon_grid_actions = {}
        self._action_groups = []
        self.recent_files_menu = None
        self._progress_dialog = None
        # Track active background workers for aggregated progress
        self._active_workers = []
        self._worker_progress = {}
        # Batch counters for aggregated completed/total display
        self._batch_total = 0
        self._batch_done = 0
        self._current_file = None
        # Map worker -> UI row widgets
        self._progress_rows = {}
        self._worker_labels = {}
        self.workspace.setDragEnabled(True)
        self.workspace.setAcceptDrops(True)
        self.workspace.setDropIndicatorShown(True)
        self.workspace.setDragDropMode(QTreeView.DragDropMode.DragDrop)

        self.preview = PreviewPanel()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(self.tr("Search current folder..."))
        self.search_edit.returnPressed.connect(self.on_search_requested)

        self.path_edit = QLineEdit()
        self.path_edit.returnPressed.connect(self.on_go_to_path)

        self.tabbar = QTabBar()
        self.tabbar.setDocumentMode(True)
        self.tabbar.setMovable(False)
        self.tabbar.setTabsClosable(True)
        self.tabbar.currentChanged.connect(self.on_tab_changed)
        self.tabbar.tabCloseRequested.connect(self.close_tab)

        self.build_toolbar()
        self.build_menu_bar()
        self.build_central_widget()
        self.sidebar.setVisible(self.config.sidebar_visible)
        self.preview.setVisible(self.config.preview_visible)
        self.build_statusbar()
        self.update_view_persistence_indicator()
        self.setup_shortcuts()
        self._progress_dialog = None
        self.apply_toolbar_preferences()
        self.apply_workspace_preferences()
        self.apply_title_preferences()

        self.new_tab(startup_path)

    @property
    def text_index_service(self):
        if self._text_index_service is None:
            self._text_index_service = TextIndexService()
        return self._text_index_service

    @property
    def indexer_service(self):
        if self._indexer_service is None:
            from lfmapp.services import IndexerService

            self._indexer_service = IndexerService(self)
            self._indexer_service.connect_changed(self._on_indexer_changed)
        return self._indexer_service

    def _on_indexer_changed(self, path):
        try:
            p = Path(path)
            # For single-file changes prefer incremental indexing
            if p.exists() and p.is_file():
                thread = self.indexer_service.index_path(p)
                thread.finished.connect(lambda pstr: self.statusBar().showMessage(self.tr("Indexed: {p}").format(p=pstr), 3000))
                # ignore thread.error for now
            else:
                # Directory changed: do a shallow re-index
                thread = self.indexer_service.start_index(p, recursive=False)
                thread.progress.connect(lambda v: self.statusBar().showMessage(self.tr("Indexing... {p}%").format(p=v), 2000))
                thread.finished.connect(lambda count: self.statusBar().showMessage(self.tr("Indexed {count} items").format(count=count), 4000))
        except Exception:
            pass

    @property
    def tag_service(self):
        if self._tag_service is None:
            from lfmapp.services.tag_service import TagService

            self._tag_service = TagService(db_file=self._tag_db_file)
        return self._tag_service

    @property
    def vault_service(self):
        if self._vault_service is None:
            from lfmapp.services.vault_service import VaultService

            self._vault_service = VaultService()
        return self._vault_service

    def closeEvent(self, event):
        self._save_window_size_to_config()
        if self._tag_service is not None:
            self._tag_service.close()
        if self._text_index_service is not None:
            self._text_index_service.close()
        super().closeEvent(event)

    def _apply_window_size_from_config(self):
        self.settings_controller.apply_window_size_from_config()

    def _save_window_size_to_config(self):
        self.settings_controller.save_window_size_to_config()

    def _apply_ui_font_from_config(self):
        self.settings_controller.apply_ui_font_from_config()

    def increase_font_size(self):
        self.settings_controller.increase_font_size()

    def decrease_font_size(self):
        self.settings_controller.decrease_font_size()

    def reset_font_size(self):
        self.settings_controller.reset_font_size()

    def set_font_size_dialog(self):
        self.settings_controller.set_font_size_dialog()

    def choose_font_dialog(self):
        self.settings_controller.choose_font_dialog()

    def show_preferences_dialog(self):
        self.settings_controller.show_preferences_dialog()

    def apply_preferences(self, preferences: dict):
        self.settings_controller.apply_preferences(preferences)

    def _startup_path(self) -> Path:
        """Return the first folder to show without forcing a second model load."""
        mode = self.config.startup_location_mode
        if mode == "home":
            return Path.home()
        if mode == "custom":
            custom_path = self.config.startup_location_custom_path
            if custom_path:
                custom_location = Path(custom_path).expanduser()
                if custom_location.exists() and custom_location.is_dir():
                    return custom_location
        last_path = self.config.last_visited
        if last_path:
            last_location = Path(last_path).expanduser()
            if last_location.exists() and last_location.is_dir():
                return last_location
        return Path.home()

    # ─── Toolbar ───────────────────────────────────────────────

    def build_toolbar(self):
        toolbar = QToolBar(self.tr("Navigation"))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.back_action = QAction(app_icon("go-previous", "arrow-left"), self.tr("Back"), self)
        self.back_action.triggered.connect(self.go_back)
        self.back_action.setEnabled(False)
        toolbar.addAction(self.back_action)

        self.forward_action = QAction(app_icon("go-next", "arrow-right"), self.tr("Forward"), self)
        self.forward_action.triggered.connect(self.go_forward)
        self.forward_action.setEnabled(False)
        toolbar.addAction(self.forward_action)

        self.up_action = QAction(app_icon("go-up", "arrow-up"), self.tr("Up"), self)
        self.up_action.triggered.connect(self.go_up)
        toolbar.addAction(self.up_action)

        self.home_action = QAction(app_icon("go-home", "user-home"), self.tr("Home"), self)
        self.home_action.triggered.connect(self.go_home)
        toolbar.addAction(self.home_action)

        toolbar.addSeparator()

        self.properties_action = QAction(app_icon("document-properties", "settings"), self.tr("Properties"), self)
        self.properties_action.triggered.connect(self.show_context_properties)
        toolbar.addAction(self.properties_action)

        self.quick_access_action = QAction(app_icon("emblem-favorite", "bookmark-new"), self.tr("Pin to Quick Access"), self)
        self.quick_access_action.triggered.connect(self.toggle_quick_access_pin)
        toolbar.addAction(self.quick_access_action)

        toolbar.addSeparator()

        # View toggle actions
        self.preview_action = QAction(app_icon("dialog-information", "view-preview"), self.tr("Preview"), self)
        self.preview_action.setCheckable(True)
        self.preview_action.setChecked(self.config.preview_visible)
        self.preview_action.triggered.connect(self.toggle_preview)
        toolbar.addAction(self.preview_action)

        self.sidebar_action = QAction(app_icon("view-sidebar"), self.tr("Sidebar"), self)
        self.sidebar_action.setCheckable(True)
        self.sidebar_action.setChecked(self.config.sidebar_visible)
        self.sidebar_action.triggered.connect(self.toggle_sidebar)
        toolbar.addAction(self.sidebar_action)

        self.build_context_toolbar()
        self.toolbar_buttons = {
            "back": self.back_action,
            "forward": self.forward_action,
            "up": self.up_action,
            "home": self.home_action,
        }

    def build_context_toolbar(self):
        """Build a contextual toolbar that changes with the selected item type."""
        self.context_toolbar = QToolBar(self.tr("Context"))
        self.context_toolbar.setMovable(False)
        self.addToolBar(self.context_toolbar)

        self.context_title_label = QLabel("")
        self.context_toolbar.addWidget(self.context_title_label)
        self.context_toolbar.addSeparator()

        self.context_actions = {
            "open": QAction(app_icon("document-open", "folder-open"), self.tr("Open"), self),
            "open_with": QAction(self.tr("Open with..."), self),
            "set_default": QAction(self.tr("Set default application..."), self),
            "print": QAction(app_icon("document-print", "printer"), self.tr("Print"), self),
            "preview": QAction(app_icon("dialog-information", "view-preview"), self.tr("Preview"), self),
            "extract_here": QAction(app_icon("package-x-generic", "archive-extract"), self.tr("Extract Here"), self),
            "extract_to": QAction(self.tr("Extract to..."), self),
            "compress": QAction(app_icon("package-x-generic", "folder-compressed"), self.tr("Compress to ZIP"), self),
            "advanced_security": QAction(
                app_icon("document-properties", "security-medium"),
                self.tr("Advanced Security..."),
                self,
            ),
            "pin": QAction(app_icon("emblem-favorite", "bookmark-new"), self.tr("Pin to Quick Access"), self),
            "properties": QAction(app_icon("document-properties", "settings"), self.tr("Properties"), self),
        }
        self.context_actions["open"].triggered.connect(self.open_selected)
        self.context_actions["open_with"].triggered.connect(self.open_with_dialog)
        self.context_actions["set_default"].triggered.connect(self.set_default_application_dialog)
        self.context_actions["print"].triggered.connect(self.print_selected)
        self.context_actions["preview"].triggered.connect(self.preview_selected)
        self.context_actions["extract_here"].triggered.connect(self.extract_selected_archive)
        self.context_actions["extract_to"].triggered.connect(self.extract_selected_archive_to)
        self.context_actions["compress"].triggered.connect(self.compress_selection_to_zip)
        self.context_actions["advanced_security"].triggered.connect(self.show_advanced_security)
        self.context_actions["pin"].triggered.connect(self.toggle_quick_access_pin)
        self.context_actions["properties"].triggered.connect(self.show_context_properties)

        for action in self.context_actions.values():
            self.context_toolbar.addAction(action)

        self.update_contextual_toolbar()

    @staticmethod
    def contextual_type_for_path(path: Path | None) -> str | None:
        """Return the contextual toolbar type for a selected path."""
        if path is None:
            return None
        path = Path(path)
        if path.is_dir():
            return "folder"
        if not path.is_file():
            return None
        if is_archive(path):
            return "archive"

        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            family = mime_type.split("/", 1)[0]
            if family in {"image", "audio", "video"}:
                return family
            if mime_type in {
                "application/pdf",
                "application/rtf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.oasis.opendocument.text",
                "text/plain",
            } or family == "text":
                return "document"
        return "file"

    def update_contextual_toolbar(self):
        """Show contextual actions relevant to the current selection."""
        if not hasattr(self, "context_actions"):
            return

        path = self.workspace.selected_path()
        context_type = self.contextual_type_for_path(path)
        visible_actions = {
            "folder": {"open", "pin", "compress", "advanced_security", "properties"},
            "archive": {"open", "open_with", "extract_here", "extract_to", "compress", "properties"},
            "image": {"open", "open_with", "preview", "compress", "properties"},
            "audio": {"open", "open_with", "preview", "compress", "properties"},
            "video": {"open", "open_with", "preview", "compress", "properties"},
            "document": {"open", "open_with", "set_default", "preview", "print", "compress", "properties"},
            "file": {"open", "open_with", "set_default", "compress", "properties"},
        }.get(context_type, set())

        titles = {
            "folder": self.tr("Folder Tools"),
            "archive": self.tr("Archive Tools"),
            "image": self.tr("Image Tools"),
            "audio": self.tr("Audio Tools"),
            "video": self.tr("Video Tools"),
            "document": self.tr("Document Tools"),
            "file": self.tr("File Tools"),
        }
        self.context_title_label.setText(titles.get(context_type, ""))
        self.context_toolbar.setVisible(bool(visible_actions))
        for key, action in self.context_actions.items():
            action.setVisible(key in visible_actions)

    def preview_selected(self):
        path = self.workspace.selected_path()
        if path and path.exists():
            self.preview.show_path(path)
            if not self.preview.isVisible():
                self.toggle_preview()

    def extract_selected_archive(self):
        path = self.workspace.selected_path()
        if path and path.is_file() and is_archive(path):
            self.extract_archive(path)

    def extract_selected_archive_to(self):
        path = self.workspace.selected_path()
        if path and path.is_file() and is_archive(path):
            self.extract_archive_to(path)

    # ─── Menu Bar ──────────────────────────────────────────────

    def _add_action(self, menu, text, slot, shortcut=None):
        """Helper to add an action with optional shortcut to a menu."""
        action = QAction(self.tr(text), self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(shortcut)
        menu.addAction(action)
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

        if persistent:
            self._sort_column_actions = column_actions
            self._sort_order_actions = order_actions

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

        if persistent:
            self._icon_grid_actions = grid_actions

    def rebuild_recent_files_menu(self):
        """Refresh the File > Recent Files menu."""
        if self.recent_files_menu is None:
            return
        self.recent_files_menu.clear()
        recent_files = [Path(path) for path in self.config.recent_files]
        existing_files = [path for path in recent_files if path.exists() and path.is_file()]

        if not existing_files:
            empty_action = QAction(self.tr("No recent files"), self)
            empty_action.setEnabled(False)
            self.recent_files_menu.addAction(empty_action)
        else:
            for path in existing_files:
                action = QAction(path.name, self)
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked=False, path=path: self.open_recent_file(path))
                self.recent_files_menu.addAction(action)
            self.recent_files_menu.addSeparator()

        clear_action = QAction(self.tr("Clear Recent Files"), self)
        clear_action.setEnabled(bool(self.config.recent_files))
        clear_action.triggered.connect(self.clear_recent_files)
        self.recent_files_menu.addAction(clear_action)

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
        self._add_action(edit_menu, "Copy", self.copy_selected, QKeySequence.StandardKey.Copy)
        self._add_action(edit_menu, "Cut", self.cut_selected, QKeySequence.StandardKey.Cut)
        self._add_action(edit_menu, "Paste", self.paste_from_clipboard, QKeySequence.StandardKey.Paste)
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
        self.file_extensions_action = QAction(self.tr("File Extensions"), self, checkable=True)
        self.file_extensions_action.setChecked(self.config.show_file_extensions)
        self.file_extensions_action.triggered.connect(self.toggle_file_extensions)
        view_menu.addAction(self.file_extensions_action)
        self.selection_checkboxes_action = QAction(self.tr("Selection Checkboxes"), self, checkable=True)
        self.selection_checkboxes_action.setChecked(self.config.selection_checkboxes)
        self.selection_checkboxes_action.triggered.connect(self.toggle_selection_checkboxes)
        view_menu.addAction(self.selection_checkboxes_action)
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
        self._clear_folder_view_action = QAction(self.tr("Clear saved view for current folder"), self)
        self._clear_folder_view_action.triggered.connect(self.clear_current_folder_view)
        view_menu.addAction(self._clear_folder_view_action)
        self._clear_all_folder_views_action = QAction(self.tr("Clear all saved folder views"), self)
        self._clear_all_folder_views_action.triggered.connect(self.clear_all_folder_views)
        view_menu.addAction(self._clear_all_folder_views_action)

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

    # ─── Central Widget ────────────────────────────────────────

    def build_central_widget(self):
        self.path_widget = QWidget()
        self.path_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        path_layout = QHBoxLayout(self.path_widget)
        path_layout.setContentsMargins(4, 4, 4, 4)
        path_layout.setSpacing(6)
        path_layout.addWidget(QLabel(self.tr("Path:")))
        path_layout.addWidget(self.path_edit, 2)
        go_button = QPushButton(self.tr("Go"))
        go_button.clicked.connect(self.on_go_to_path)
        path_layout.addWidget(go_button)
        path_layout.addWidget(self.search_edit, 1)
        search_button = QPushButton(self.tr("Search"))
        search_button.clicked.connect(self.on_search_requested)
        path_layout.addWidget(search_button)
        filters_button = QPushButton(self.tr("Filters..."))
        filters_button.clicked.connect(self.on_search_filters_requested)
        path_layout.addWidget(filters_button)
        self.path_widget.setMaximumHeight(self.path_widget.sizeHint().height())

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.workspace)
        self.splitter.addWidget(self.preview)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, True)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([180, 760, 220])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(2, 2, 2, 2)
        central_layout.setSpacing(4)
        central_layout.addWidget(self.path_widget, 0)
        central_layout.addWidget(self.tabbar)
        central_layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)

    # ─── Status Bar ────────────────────────────────────────────

    def build_statusbar(self):
        self.setStatusBar(QStatusBar(self))

        self.status_items = QLabel()
        self.status_selection = QLabel()
        self.status_space = QLabel()
        self.status_view_persistence = QLabel()
        self.status_view_persistence.setContentsMargins(6, 2, 6, 2)
        self.status_view_persistence.setStyleSheet(
            "border-radius: 6px; padding: 2px 8px;"
        )

        statusbar = self.statusBar()
        statusbar.addPermanentWidget(self.status_items, 1)
        statusbar.addPermanentWidget(self.status_selection, 1)
        statusbar.addPermanentWidget(self.status_space, 1)
        statusbar.addPermanentWidget(self.status_view_persistence)

    def update_statusbar(self):
        """Update status bar with current folder info."""
        current = self.workspace.current_path()
        if not current:
            return

        # Item count
        try:
            count = sum(1 for _ in current.iterdir())
            self.status_items.setText(self.tr("  {count} items").format(count=count))
        except PermissionError:
            self.status_items.setText(self.tr("  (access denied)"))

        # Selection info
        selected = self.workspace.selected_paths()
        if len(selected) > 0:
            total_size = 0
            for p in selected:
                try:
                    if p.is_file():
                        total_size += p.stat().st_size
                except OSError:
                    pass
            size_str = self._human_size(total_size) if total_size else ""
            self.status_selection.setText(
                self.tr("  {count} selected  {size}").format(count=len(selected), size=size_str)
            )
        else:
            self.status_selection.setText("")

        # Disk space
        try:
            usage = shutil.disk_usage(str(current))
            free_str = self._human_size(usage.free)
            total_str = self._human_size(usage.total)
            self.status_space.setText(
                self.tr("  {free} free of {total}  ").format(free=free_str, total=total_str)
            )
        except OSError:
            self.status_space.setText("")

    @staticmethod
    def _human_size(size: int) -> str:
        """Convert bytes to human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                if unit == "B":
                    return f"{size} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

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
        self.history = state["history"]
        self.history_index = state["history_index"]
        self.go_to(state["path"], record_history=False)
        self.update_navigation_actions()

    def _sync_active_tab_state(self):
        if self._active_tab_index < 0 or self._active_tab_index >= len(self._tabs):
            return
        current = self.workspace.current_path()
        self._tabs[self._active_tab_index]["path"] = current
        self._tabs[self._active_tab_index]["history"] = self.history
        self._tabs[self._active_tab_index]["history_index"] = self.history_index
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
        self.back_action.setEnabled(self.history_index > 0)
        self.forward_action.setEnabled(self.history_index < len(self.history) - 1)

    def add_history(self, path: Path):
        if self.history_index >= 0 and self.history_index < len(self.history) - 1:
            self.history = self.history[: self.history_index + 1]
        if not self.history or self.history[self.history_index] != path:
            self.history.append(path)
            self.history_index = len(self.history) - 1
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
        # Apply any persisted view preference for this folder.
        if self.config.remember_folder_view:
            try:
                view_name = self.config.get_folder_view(path)
                if view_name:
                    view_mode = ViewMode.from_string(view_name, self.workspace.view_mode())
                    self.workspace.set_view_mode(view_mode)
                    self.statusBar().showMessage(
                        self.tr("Restored saved view: {view}").format(view=view_mode.value),
                        3000,
                    )
            except Exception:
                pass
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
        if self.history_index > 0:
            self.history_index -= 1
            self.go_to(self.history[self.history_index], record_history=False)
            self.update_navigation_actions()

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.go_to(self.history[self.history_index], record_history=False)
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
        self.update_quick_access_action()
        self.update_contextual_toolbar()
        self.update_statusbar()

    def on_model_data_changed(self, *_):
        self.update_statusbar()

    def on_file_renamed(self, directory, old_name, new_name):
        """Record inline renames performed through QFileSystemModel."""
        if self._history_replaying:
            return
        old_path = Path(directory) / old_name
        new_path = Path(directory) / new_name
        self.record_operation(RenameOperation(old_path, new_path))

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
            enabled=(path is None and self._context_entry_enabled("background", "paste"))
            or (has_selection and self._context_entry_enabled("selection", "paste")),
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

    def _build_file_context_menu(self, menu: QMenu, path: Path):
        if self._context_entry_enabled("selection", "open"):
            menu.addAction(app_icon("document-open", "folder-open"), self.tr("Open"), self.open_selected)
        menu.addAction(self.tr("Open with..."), self.open_with_dialog)
        menu.addAction(self.tr("Set default application..."), self.set_default_application_dialog)
        menu.addSeparator()
        if self._context_entry_enabled("selection", "open_in_terminal"):
            menu.addAction(app_icon("utilities-terminal", "terminal"), self.tr("Open in Terminal"), lambda: self.open_terminal_in_directory(path.parent))
        menu.addSeparator()
        if self._context_entry_enabled("selection", "cut"):
            menu.addAction(app_icon("edit-cut"), self.tr("Cut"), self.cut_selected)
        if self._context_entry_enabled("selection", "copy"):
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

        if self._context_entry_enabled("selection", "rename"):
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

        menu.addSeparator()
        if self._context_entry_enabled("selection", "properties"):
            menu.addAction(app_icon("document-properties", "settings"), self.tr("Properties"), self.show_properties)

    def _build_folder_context_menu(self, menu: QMenu, path: Path):
        if self._context_entry_enabled("selection", "open"):
            menu.addAction(app_icon("document-open", "folder-open"), self.tr("Open"), self.open_selected)
        if self._context_entry_enabled("selection", "open_in_terminal"):
            menu.addAction(app_icon("utilities-terminal", "terminal"), self.tr("Open in Terminal"), lambda: self.open_terminal_in_directory(path))
        menu.addSeparator()
        if self._context_entry_enabled("selection", "cut"):
            menu.addAction(app_icon("edit-cut"), self.tr("Cut"), self.cut_selected)
        if self._context_entry_enabled("selection", "copy"):
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

        if self._context_entry_enabled("selection", "rename"):
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
        if self._context_entry_enabled("background", "paste"):
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

    def share_with_application(self, path: Path, desktop_file: str):
        """Launch a chosen application for the supplied path."""
        if not path.exists() or not desktop_file:
            return False
        launched = launch_application_for_path(desktop_file, path)
        if launched and path.is_file():
            self.record_recent_file(path)
        return launched

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

    def cut_selected(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        self._clipboard_paths = paths
        self._clipboard_mode = "cut"
        self.statusBar().showMessage(self.tr("Cut {count} item(s)").format(count=len(paths)), 3000)

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

    # ─── Undo / Redo ───────────────────────────────────────────

    def record_operation(self, operation):
        self.operation_history.push(operation)
        self.update_undo_redo_actions()

    def create_operation_batch(self, label: str, total: int):
        if total <= 1:
            return None
        batch_id = object()
        self._operation_batches[batch_id] = {
            "label": label,
            "remaining": total,
            "operations": [],
        }
        return batch_id

    def record_batched_operation(self, batch_id, operation):
        if batch_id is None:
            self.record_operation(operation)
            return
        batch = self._operation_batches.get(batch_id)
        if batch is not None:
            batch["operations"].append(operation)

    def finish_operation_batch_item(self, batch_id):
        if batch_id is None:
            return
        batch = self._operation_batches.get(batch_id)
        if batch is None:
            return
        batch["remaining"] -= 1
        if batch["remaining"] > 0:
            return
        self._operation_batches.pop(batch_id, None)
        operations = batch["operations"]
        if len(operations) == 1:
            self.record_operation(operations[0])
        elif len(operations) > 1:
            self.record_operation(
                CompositeOperation.from_operations(batch["label"], operations)
            )

    def update_undo_redo_actions(self):
        if not hasattr(self, "undo_action") or not hasattr(self, "redo_action"):
            return
        undo_label = self.operation_history.next_undo_operation_label()
        redo_label = self.operation_history.next_redo_operation_label()
        self.undo_action.setText(
            self.tr("Undo {operation}").format(
                operation=self._translated_operation_label(undo_label),
            )
            if undo_label
            else self.tr("Undo")
        )
        self.undo_action.setEnabled(self.operation_history.can_undo())
        self.redo_action.setText(
            self.tr("Redo {operation}").format(
                operation=self._translated_operation_label(redo_label),
            )
            if redo_label
            else self.tr("Redo")
        )
        self.redo_action.setEnabled(self.operation_history.can_redo())

    def _translated_operation_label(self, label: str | None) -> str:
        """Translate operation-history labels at the Qt UI boundary."""
        if not label:
            return ""
        if label.startswith("Rename ") and " to " in label:
            original, renamed = label[len("Rename "):].rsplit(" to ", 1)
            return self.tr("Rename {original} to {renamed}").format(
                original=original,
                renamed=renamed,
            )
        if label.startswith("Create folder "):
            return self.tr("Create folder {name}").format(name=label[len("Create folder "):])
        if label.startswith("Create file "):
            return self.tr("Create file {name}").format(name=label[len("Create file "):])
        if label.startswith("Move ") and label.endswith(" to Trash"):
            name = label[len("Move "):-len(" to Trash")]
            return self.tr("Move {name} to Trash").format(name=name)
        if label.startswith("Move "):
            return self.tr("Move {name}").format(name=label[len("Move "):])
        if label.startswith("Copy "):
            return self.tr("Copy {name}").format(name=label[len("Copy "):])
        return label

    def undo_last_operation(self):
        if not self.operation_history.can_undo():
            return
        try:
            self._history_replaying = True
            operation = self.operation_history.undo()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Undo Error"),
                self.tr("Could not undo operation:\n{error}").format(error=exc),
            )
        else:
            self.statusBar().showMessage(self.tr("Undone: {label}").format(label=operation.label), 5000)
            self.refresh_view()
        finally:
            self._history_replaying = False
            self.update_undo_redo_actions()

    def redo_last_operation(self):
        if not self.operation_history.can_redo():
            return
        try:
            self._history_replaying = True
            operation = self.operation_history.redo()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Redo Error"),
                self.tr("Could not redo operation:\n{error}").format(error=exc),
            )
        else:
            self.statusBar().showMessage(self.tr("Redone: {label}").format(label=operation.label), 5000)
            self.refresh_view()
        finally:
            self._history_replaying = False
            self.update_undo_redo_actions()

    def trash_selected(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        self.statusBar().showMessage(
            self.tr("Moving {count} item(s) to trash...").format(count=len(paths)),
            0,
        )
        worker = TrashWorker(paths)
        self._trash_worker_operations[worker] = []
        worker.item_trashed.connect(
            lambda original, trashed, trashinfo, w=worker: self.on_item_trashed(
                w,
                original,
                trashed,
                trashinfo,
            )
        )
        self._register_worker(
            worker,
            self.tr("Sending items to Trash..."),
            finished_callback=lambda s, m, w=worker: self._on_trash_finished(w, s, m),
        )

    def on_item_trashed(self, worker, original_path: str, trashed_path: str, trashinfo_path: str):
        operation = TrashOperation(
            Path(original_path),
            Path(trashed_path),
            Path(trashinfo_path),
        )
        self._trash_worker_operations.setdefault(worker, []).append(operation)

    def _on_trash_finished(self, worker, success, message):
        operations = self._trash_worker_operations.pop(worker, [])
        if len(operations) == 1:
            self.record_operation(operations[0])
        elif len(operations) > 1:
            self.record_operation(
                CompositeOperation.from_operations(
                    self.tr("Move {count} item(s) to Trash").format(count=len(operations)),
                    operations,
                )
            )
        if success:
            self.statusBar().showMessage(message, 5000)
        else:
            QMessageBox.critical(
                self,
                self.tr("Trash Error"),
                self.tr("Could not move to trash:\n{message}").format(message=message),
            )
        self.refresh_view()
        self.update_trash_count()

    def on_files_dropped(self, paths: list, action: str):
        """Handle files/folders dropped onto the workspace.

        `paths` is a list of Path objects; `action` is 'copy' or 'move'.
        """
        destination = self.workspace.current_path()
        if not destination:
            return
        sources = [src for src in paths if src.exists()]
        if not sources:
            return
        action_label = self.tr("Copy") if action == "copy" else self.tr("Move")
        batch_id = self.create_operation_batch(
            self.tr("{action} {count} dropped item(s)").format(action=action_label, count=len(sources)),
            len(sources),
        )
        for src in sources:
            try:
                activity = self.tr("Copying") if action == "copy" else self.tr("Moving")
                if action == "copy":
                    worker = CopyWorker(src, destination)
                    copied_path = destination / src.name
                    callback = lambda s, m, w=worker, source=src, copied=copied_path, batch=batch_id: self._on_drop_worker_finished(
                        w,
                        s,
                        m,
                        copied_source=source,
                        copied_path=copied,
                        batch_id=batch,
                    )
                else:
                    worker = MoveWorker(src, destination)
                    moved_path = destination / src.name
                    callback = lambda s, m, w=worker, source=src, moved=moved_path, batch=batch_id: self._on_drop_worker_finished(
                        w,
                        s,
                        m,
                        source,
                        moved,
                        batch_id=batch,
                    )
                # Register worker and forward finished to drop handler
                self._register_worker(
                    worker,
                    self.tr("{activity} {name}...").format(activity=activity, name=src.name),
                    finished_callback=callback,
                )
                self._drop_workers.append(worker)
                self.statusBar().showMessage(
                    self.tr("{activity} {name}...").format(activity=activity, name=src.name),
                    0,
                )
            except Exception as exc:
                self.finish_operation_batch_item(batch_id)
                QMessageBox.critical(
                    self,
                    self.tr("Drop Error"),
                    self.tr("Could not perform {action} on {path}:\n{error}").format(
                        action=action,
                        path=src,
                        error=exc,
                    ),
                )

    def _on_drop_worker_finished(
        self,
        worker,
        success,
        message,
        source=None,
        moved_path=None,
        copied_source=None,
        copied_path=None,
        batch_id=None,
    ):
        try:
            if worker in self._drop_workers:
                self._drop_workers.remove(worker)
            if success:
                if source is not None and moved_path is not None:
                    self.record_batched_operation(batch_id, MoveOperation(source, moved_path))
                if copied_source is not None and copied_path is not None:
                    operation = self.create_copy_operation(copied_source, copied_path)
                    if operation is not None:
                        self.record_batched_operation(batch_id, operation)
                self.statusBar().showMessage(message, 5000)
            else:
                QMessageBox.critical(self, self.tr("Operation Error"), message)
            self.refresh_view()
        finally:
            self.finish_operation_batch_item(batch_id)

    def _show_progress(self, title: str, label: str):
        # Create a custom dialog with per-worker rows
        if self._progress_dialog is None:
            dlg = QDialog(self)
            dlg.setWindowTitle(title)
            dlg.setModal(True)
            vlayout = QVBoxLayout(dlg)
            self._progress_main_label = QLabel(label)
            vlayout.addWidget(self._progress_main_label)

            scroll = QScrollArea(dlg)
            scroll.setWidgetResizable(True)
            container = QWidget()
            self._progress_container_layout = QVBoxLayout(container)
            self._progress_container_layout.setSpacing(6)
            self._progress_container_layout.setContentsMargins(0, 0, 0, 0)
            scroll.setWidget(container)
            vlayout.addWidget(scroll)

            # Cancel button
            btn = QPushButton(self.tr("Cancel"))
            btn.clicked.connect(self._on_progress_canceled)
            vlayout.addWidget(btn)

            self._progress_dialog = dlg
            dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            dlg.setStyleSheet(
                "QDialog { background: #f9f9f9; }"
                "QLabel { font-weight: bold; padding: 4px; }"
                "QProgressBar { min-height: 18px; }"
                "QPushButton { min-width: 80px; padding: 4px; }"
            )
            dlg.resize(520, 320)
        # Update label and show
        try:
            self._progress_main_label.setText(label)
        except Exception:
            pass
        self._progress_dialog.show()

    def _register_worker(self, worker, label: str, finished_callback=None):
        """Register a worker for aggregated progress and queue it.

        finished_callback will be invoked after internal cleanup with signature (success, message).
        """
        self._worker_labels[worker] = label
        self._worker_progress[worker] = 0
        self._batch_total += 1

        if hasattr(worker, "progress"):
            worker.progress.connect(lambda v, w=worker: self._on_worker_progress(w, v))

        if hasattr(worker, "file_copied"):
            try:
                worker.file_copied.connect(lambda p, w=worker: self._on_worker_file_event(w, p))
            except Exception:
                pass
        if hasattr(worker, "file_deleted"):
            try:
                worker.file_deleted.connect(lambda p, w=worker: self._on_worker_file_event(w, p))
            except Exception:
                pass

        def _on_finished(success, message, w=worker):
            self._on_worker_finished(w, success, message)
            if finished_callback:
                try:
                    finished_callback(success, message)
                except Exception:
                    pass

        worker.finished.connect(_on_finished)

        self._show_progress(self.tr("Operation"), label)
        try:
            self._add_progress_row(worker, label)
        except Exception:
            pass
        self._update_progress_label(label)
        self.statusBar().showMessage(self.tr("Queued: {label}").format(label=label), 3000)
        self._operation_queue.enqueue(worker)

    def _on_queued_worker_started(self, worker):
        if worker not in self._active_workers:
            self._active_workers.append(worker)
        label = self._worker_labels.get(worker, self.tr("Operation"))
        self.statusBar().showMessage(label, 0)
        row = self._progress_rows.get(worker)
        if row:
            row[0].setText(self.tr("Running: {label}").format(label=label))
        self._update_progress_label(label)

    def _on_worker_progress(self, worker, value: int):
        # Update per-worker value and aggregate (average)
        self._worker_progress[worker] = int(value)
        if self._progress_dialog is None:
            return
        if not self._worker_progress:
            return
        total = sum(self._worker_progress.values())
        avg = int(total / len(self._worker_progress))
        # Update aggregated UI (show percent)
        self._update_progress_label(None, percent=avg)
        # Update per-worker bar if present
        try:
            row = self._progress_rows.get(worker)
            if row:
                _, bar = row
                bar.setValue(int(value))
        except Exception:
            pass

    def _on_worker_finished(self, worker, success, message):
        # Remove worker from tracking
        if worker in self._active_workers:
            try:
                self._active_workers.remove(worker)
            except ValueError:
                pass
        if worker in self._worker_progress:
            try:
                del self._worker_progress[worker]
            except KeyError:
                pass
        # Mark one completed for batch and update label
        self._batch_done += 1
        self._update_progress_label()
        # Remove per-worker UI row
        try:
            self._remove_progress_row(worker)
        except Exception:
            pass
        self._worker_labels.pop(worker, None)
        # If no more active workers, close progress and reset counters
        if not self._active_workers and self._operation_queue.pending_count == 0:
            self._close_progress()

    def _add_progress_row(self, worker, label: str):
        """Add a labelled progress bar row for a worker."""
        if not hasattr(self, "_progress_container_layout"):
            return
        frame = QFrame()
        layout = QHBoxLayout(frame)
        lbl = QLabel(label)
        bar = QProgressBar()
        if hasattr(worker, "progress"):
            bar.setRange(0, 100)
            bar.setValue(0)
        else:
            bar.setRange(0, 0)
        layout.addWidget(lbl)
        layout.addWidget(bar)
        self._progress_container_layout.addWidget(frame)
        self._progress_rows[worker] = (lbl, bar)

    def _remove_progress_row(self, worker):
        try:
            row = self._progress_rows.pop(worker)
            lbl, bar = row
            widget = lbl.parent()
            if widget is not None:
                widget.setParent(None)
        except Exception:
            pass

    def _on_progress_canceled(self):
        self._operation_queue.stop_active()
        for worker in self._operation_queue.cancel_pending():
            self._worker_progress.pop(worker, None)
            self._worker_labels.pop(worker, None)
            self._batch_done += 1
            try:
                self._remove_progress_row(worker)
            except Exception:
                pass
        self._update_progress_label(self.tr("Canceling operations..."))

    def _update_progress_label(self, base_label: str | None = None, percent: int | None = None):
        """Update the progress dialog label to include completed/total batch counts."""
        if self._progress_dialog is None:
            return
        label = base_label or (getattr(self, "_progress_main_label", None).text() if getattr(self, "_progress_main_label", None) is not None else "")
        # Normalize label (strip existing suffix like "(x/y)")
        if "(" in label:
            label = label.split("(", 1)[0].strip()
        if self._batch_total > 0:
            label = f"{label} ({self._batch_done}/{self._batch_total})"
        # Append percent and current file if present
        if percent is not None:
            label = f"{label} {percent}%"
        if self._current_file:
            try:
                short = Path(self._current_file).name
                label = f"{label}: {short}"
            except Exception:
                pass
        try:
            self._progress_main_label.setText(label)
        except Exception:
            pass

    def _on_worker_file_event(self, worker, path: str):
        try:
            self._current_file = path
            self._update_progress_label()
        except Exception:
            pass

    def _close_progress(self):
        if self._progress_dialog is not None:
            try:
                self._progress_dialog.reset()
            except Exception:
                pass
            self._progress_dialog = None
        # Reset batch counters
        self._batch_total = 0
        self._batch_done = 0
        self._worker_progress.clear()

    def delete_selected(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        answer = QMessageBox.question(
            self,
            self.tr("Delete Permanently"),
            self.tr(
                "Are you sure you want to permanently delete {count} item(s)?\n"
                "This action cannot be undone."
            ).format(count=len(paths)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.statusBar().showMessage(self.tr("Deleting {count} item(s)...").format(count=len(paths)), 0)
        worker = DeleteWorker(paths)
        self._register_worker(
            worker,
            self.tr("Deleting selected item(s)..."),
            finished_callback=self._on_delete_finished,
        )

    def _on_delete_finished(self, success, message):
        if success:
            self.statusBar().showMessage(message, 5000)
        else:
            QMessageBox.critical(
                self,
                self.tr("Delete Error"),
                self.tr("Could not delete:\n{message}").format(message=message),
            )
        self.refresh_view()

    def copy_selected_to(self):
        paths = [path for path in self.workspace.selected_paths() if path.exists()]
        if not paths:
            return
        destination = FileOperations.choose_folder(self, self.tr("Copy to"), str(paths[0].parent))
        if not destination:
            return
        batch_id = self.create_operation_batch(self.tr("Copy {count} item(s)").format(count=len(paths)), len(paths))
        for path in paths:
            try:
                worker = CopyWorker(path, destination)
                copied_path = destination / path.name
                self._register_worker(
                    worker,
                    self.tr("Copying {name}...").format(name=path.name),
                    finished_callback=lambda s, m, source=path, copied=copied_path, batch=batch_id: self._on_copy_finished(
                        source,
                        copied,
                        s,
                        m,
                        self.tr("Copy Error"),
                        batch,
                    ),
                )
            except Exception as exc:
                self.finish_operation_batch_item(batch_id)
                QMessageBox.critical(
                    self,
                    self.tr("Error"),
                    self.tr("Could not copy:\n{error}").format(error=exc),
                )
        self.statusBar().showMessage(self.tr("Copying {count} item(s)...").format(count=len(paths)), 0)

    def move_selected_to(self):
        paths = [path for path in self.workspace.selected_paths() if path.exists()]
        if not paths:
            return
        destination = FileOperations.choose_folder(self, self.tr("Move to"), str(paths[0].parent))
        if not destination:
            return
        batch_id = self.create_operation_batch(self.tr("Move {count} item(s)").format(count=len(paths)), len(paths))
        for path in paths:
            try:
                worker = MoveWorker(path, destination)
                moved_path = destination / path.name
                self._register_worker(
                    worker,
                    self.tr("Moving {name}...").format(name=path.name),
                    finished_callback=lambda s, m, source=path, moved=moved_path, batch=batch_id: self._on_move_finished(
                        source,
                        moved,
                        s,
                        m,
                        self.tr("Move Error"),
                        batch,
                    ),
                )
            except Exception as exc:
                self.finish_operation_batch_item(batch_id)
                QMessageBox.critical(
                    self,
                    self.tr("Error"),
                    self.tr("Could not move:\n{error}").format(error=exc),
                )
        self.statusBar().showMessage(self.tr("Moving {count} item(s)...").format(count=len(paths)), 0)

    def _on_move_finished(
        self,
        source: Path,
        moved_path: Path,
        success,
        message,
        error_title: str,
        batch_id=None,
    ):
        try:
            if success:
                self.record_batched_operation(batch_id, MoveOperation(source, moved_path))
                self.statusBar().showMessage(message, 5000)
            else:
                QMessageBox.critical(
                    self,
                    error_title,
                    self.tr("Operation failed:\n{message}").format(message=message),
                )
            self.refresh_view()
        finally:
            self.finish_operation_batch_item(batch_id)

    def _on_copy_finished(
        self,
        source: Path,
        copied_path: Path,
        success,
        message,
        error_title: str,
        batch_id=None,
    ):
        try:
            if success:
                operation = self.create_copy_operation(source, copied_path)
                if operation is not None:
                    self.record_batched_operation(batch_id, operation)
                self.statusBar().showMessage(message, 5000)
            else:
                QMessageBox.critical(
                    self,
                    error_title,
                    self.tr("Operation failed:\n{message}").format(message=message),
                )
            self.refresh_view()
        finally:
            self.finish_operation_batch_item(batch_id)

    def create_copy_operation(self, source: Path, copied_path: Path):
        if not copied_path.exists() or not source.exists():
            return None
        try:
            return CopyOperation.from_completed_copy(source, copied_path)
        except Exception:
            return None

    def record_copy_operation(self, source: Path, copied_path: Path):
        operation = self.create_copy_operation(source, copied_path)
        if operation is not None:
            self.record_operation(operation)

    def send_selected_to_desktop(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        try:
            destination = FileOperations.ensure_desktop_directory()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Could not prepare Desktop folder:\n{error}").format(error=exc),
            )
            return

        paths = [path for path in paths if path.exists()]
        if not paths:
            return
        batch_id = self.create_operation_batch(
            self.tr("Send {count} item(s) to Desktop").format(count=len(paths)),
            len(paths),
        )

        for path in paths:
            if not path.exists():
                continue
            worker = CopyWorker(path, destination)
            copied_path = destination / path.name
            self._register_worker(
                worker,
                self.tr("Sending {name} to Desktop...").format(name=path.name),
                finished_callback=lambda s, m, source=path, copied=copied_path, batch=batch_id: self._on_send_to_desktop_finished(
                    source,
                    copied,
                    s,
                    m,
                    batch,
                ),
            )
        self.statusBar().showMessage(
            self.tr("Sending {count} item(s) to Desktop...").format(count=len(paths)),
            0,
        )

    def _on_send_to_desktop_finished(self, source: Path, copied_path: Path, success, message, batch_id=None):
        try:
            if success:
                operation = self.create_copy_operation(source, copied_path)
                if operation is not None:
                    self.record_batched_operation(batch_id, operation)
                self.statusBar().showMessage(message, 5000)
            else:
                QMessageBox.critical(
                    self,
                    self.tr("Send to Desktop Error"),
                    self.tr("Could not send to Desktop:\n{message}").format(message=message),
                )
        finally:
            self.finish_operation_batch_item(batch_id)

    def send_selected_to_email(self):
        paths = self.workspace.selected_paths()
        if not paths:
            return
        if any(path.is_dir() for path in paths):
            QMessageBox.warning(
                self,
                self.tr("Send to Email"),
                self.tr("Only files can be attached to an email. Compress folders to ZIP first."),
            )
            return

        if send_email_with_attachments(paths):
            self.statusBar().showMessage(
                self.tr("Opening email composer for {count} file(s)...").format(count=len(paths)),
                5000,
            )
        else:
            QMessageBox.critical(
                self,
                self.tr("Send to Email Error"),
                self.tr("Could not open the default email composer. Make sure xdg-email and a mail client are configured."),
            )

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

    # ─── Search ────────────────────────────────────────────────

    def on_search_requested(self):
        query = self.search_edit.text().strip()
        self._start_search(query, SearchFilters())

    def on_search_filters_requested(self):
        dialog = SearchFilterDialog(self.search_edit.text().strip(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        query = dialog.query()
        filters = dialog.filters()
        self.search_edit.setText(query)
        self._start_search(query, filters)

    def _start_search(self, query: str, filters: SearchFilters):
        if not query and not filters.is_active():
            return
        if self._current_search is not None and self._current_search.isRunning():
            self._current_search.stop()
            self._current_search.wait()
        current_dir = self.workspace.current_path()
        if not current_dir:
            return
        self._current_search_results = []
        self._active_search_filters = filters
        if self.config.text_index_enabled and not filters.is_active():
            results = self.text_index_service.search(query, current_dir)
            self.preview.show_search_results([Path(p) for p in results] if results else [])
            self.statusBar().showMessage(
                self.tr("Indexed search complete: {count} results").format(count=len(results)),
                5000,
            )
            return
        self.preview.show_search_results([])
        self._current_search = SearchThread(current_dir, query, recursive=False, filters=filters)
        self._current_search.found.connect(self.on_search_result)
        self._current_search.finished.connect(self.on_search_finished)
        self._current_search.start()

    def on_search_result(self, path):
        self._current_search_results.append(path)
        self.preview.add_search_result(path)

    def on_search_finished(self, count):
        if self._active_search_filters.is_active():
            message = self.tr("Search complete with filters: {count} results").format(count=count)
        else:
            message = self.tr("Search complete: {count} results").format(count=count)
        self.statusBar().showMessage(message, 5000)

    def on_index_current_folder(self):
        current_dir = self.workspace.current_path()
        if not current_dir or not current_dir.exists():
            return
        reply = QMessageBox.question(
            self,
            self.tr("Index Folder"),
            self.tr(
                "Index all files in {path}? This will enable text index search for this folder."
            ).format(path=current_dir),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.statusBar().showMessage(self.tr("Indexing folder..."), 0)
            thread = self.indexer_service.start_index(current_dir, recursive=True)

            # Show a small progress dialog with cancel
            dlg = QDialog(self)
            dlg.setWindowTitle(self.tr("Indexing folder"))
            vlayout = QVBoxLayout(dlg)
            label = QLabel(self.tr("Indexing {path}...").format(path=current_dir))
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            cancel_btn = QPushButton(self.tr("Cancel"))
            vlayout.addWidget(label)
            vlayout.addWidget(progress_bar)
            vlayout.addWidget(cancel_btn)
            dlg.setModal(False)
            dlg.setMinimumWidth(360)

            def on_progress(v):
                try:
                    progress_bar.setValue(int(v))
                except Exception:
                    pass

            def on_finished(count):
                self.config.set_text_index_enabled(True)
                progress_bar.setValue(100)
                self.statusBar().showMessage(
                    self.tr("Indexed {count} files in {path}").format(count=count, path=current_dir),
                    5000,
                )
                dlg.accept()
                QMessageBox.information(
                    self,
                    self.tr("Index Complete"),
                    self.tr("Indexed {count} files in {path}.\nText index search is now enabled.").format(
                        count=count,
                        path=current_dir,
                    ),
                )

            def on_cancel():
                cancel_btn.setEnabled(False)
                try:
                    thread.stop()
                except Exception:
                    pass

            thread.progress.connect(on_progress)
            thread.finished.connect(on_finished)
            cancel_btn.clicked.connect(on_cancel)
            dlg.show()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Index Error"),
                self.tr("Could not index folder:\n{error}").format(error=exc),
            )

    def on_toggle_text_index(self):
        next_state = not self.config.text_index_enabled
        self.config.set_text_index_enabled(next_state)
        state_text = self.tr("enabled") if next_state else self.tr("disabled")
        self.statusBar().showMessage(
            self.tr("Text index search {state}").format(state=state_text),
            5000,
        )

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
        # Persist view type for current folder so it restores on next visit.
        if self.config.remember_folder_view:
            try:
                current = self.workspace.current_path()
                if current:
                    self.config.set_folder_view(current, mode.value)
            except Exception:
                pass
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
        self.config.set_remember_folder_view(checked)
        self.update_view_persistence_indicator()
        state = self.tr("enabled") if checked else self.tr("disabled")
        self.statusBar().showMessage(
            self.tr("Folder view persistence {state}").format(state=state),
            3000,
        )

    def update_view_persistence_indicator(self):
        if self.config.remember_folder_view:
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
        current = self.workspace.current_path()
        if current:
            self.config.clear_folder_view(current)
            self.statusBar().showMessage(self.tr("Cleared saved view for current folder"), 3000)

    def clear_all_folder_views(self):
        self.config.clear_all_folder_views()
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
