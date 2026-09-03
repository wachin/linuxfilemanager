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

from pathlib import Path

from PyQt6.QtWidgets import QLineEdit, QMainWindow, QTabBar, QTreeView

from lfmapp.core.config import Config
from lfmapp.actions import ActionRegistry
from lfmapp.actions.catalog import build_core_registry, with_callbacks
from lfmapp.controllers import AppState, NavigationController, SearchController, ViewController
from lfmapp.services import (
    BookmarkService,
    SearchFilters,
    BackgroundOperationQueue,
    OperationHistory,
    TerminalService,
)
from lfmapp.services.textindex_service import TextIndexService
from lfmapp.ui.icons import application_icon
from lfmapp.ui.preview_panel import PreviewPanel
from lfmapp.ui.context_menu_mixin import ContextMenuMixin
from lfmapp.ui.transfer_actions_mixin import TransferActionsMixin
from lfmapp.ui.history_actions_mixin import HistoryActionsMixin
from lfmapp.ui.search_actions_mixin import SearchActionsMixin
from lfmapp.ui.menu_bar_mixin import MenuBarMixin
from lfmapp.ui.toolbar_mixin import ToolbarMixin
from lfmapp.ui.operation_center_mixin import OperationCenterMixin
from lfmapp.ui.file_actions_mixin import FileActionsMixin
from lfmapp.ui.palette_actions import PaletteActionsMixin
from lfmapp.ui.settings_controller import SettingsController
from lfmapp.ui.sidebar import Sidebar
from lfmapp.ui.workspace import Workspace, ViewMode
from lfmapp.ui.central_status_mixin import CentralWidgetStatusBarMixin
from lfmapp.ui.tabs_navigation_mixin import TabsNavigationMixin
from lfmapp.ui.view_controls_mixin import ViewControlsMixin
from lfmapp.ui.archive_tag_vault_mixin import ArchiveTagVaultMixin


class MainWindow(PaletteActionsMixin, ContextMenuMixin, FileActionsMixin, TransferActionsMixin, OperationCenterMixin, HistoryActionsMixin, SearchActionsMixin, MenuBarMixin, ToolbarMixin, CentralWidgetStatusBarMixin, TabsNavigationMixin, ViewControlsMixin, ArchiveTagVaultMixin, QMainWindow):
    def __init__(self, config: Config | None = None):
        super().__init__()
        self.setWindowTitle("linux-file-manager")
        self.config = config or Config()
        self.setWindowIcon(application_icon(self.config))
        self.terminal_service = TerminalService(self.config)
        self.settings_controller = SettingsController(self)
        self._apply_window_size_from_config()
        self.bookmark_service = BookmarkService(
            bookmarks_file=self.config.file_path.parent / "bookmarks.json"
        )
        self._tag_service = None
        self._vault_service = None
        self._tag_db_file = self.config.file_path.parent / "tags.db"
        self.navigation = NavigationController()
        self.view_controller = ViewController(self.config)
        self.app_state = AppState()
        self._tabs = []
        self._active_tab_index = -1
        self._clipboard_paths: list[Path] = []
        self._clipboard_mode = None  # "copy" or "cut"
        self._current_search_results = []
        self._active_search_filters = SearchFilters()
        self._search_controller = None  # built lazily in _build_search_controller
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
        self._command_actions = []
        self._command_action_by_action = {}
        self._command_action_keys = set()
        # Fase 1.2: central action registry with stable ids.
        self.action_registry = ActionRegistry()
        self._registry_action_actions: dict[str, object] = {}
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
        self._init_core_action_registry()
        self.refresh_registry_enablement()
        self._search_controller = self._build_search_controller()

    def _build_search_controller(self) -> SearchController:
        """Create the search lifecycle controller wired to real services."""
        return SearchController(
            text_index_enabled_provider=lambda: bool(self.config.text_index_enabled),
            index_search=lambda query, root: [
                Path(p) for p in self.text_index_service.search(query, root)
            ],
        )

    def _init_core_action_registry(self):
        """Populate the central ActionRegistry with the core vocabulary.

        Fase 1.2: menus, toolbars and the palette already register the same
        commands through _register_command_action(); this registry adds the
        stable-id view of the core commands (callbacks bound to the window)
        that surfaces can query for consistent enablement later.
        """
        self.action_registry = with_callbacks(
            build_core_registry(),
            {
                "nav.back": self.go_back,
                "nav.forward": self.go_forward,
                "nav.up": self.go_up,
                "nav.home": self.go_home,
                "nav.refresh": self.refresh_view,
                "clip.copy": self.copy_selected,
                "clip.cut": self.cut_selected,
                "clip.paste": self.paste_from_clipboard,
                "clip.copy_path": self.copy_path,
                "sel.all": self.select_all,
                "sel.none": self.deselect_all,
                "sel.invert": self.invert_selection,
                "file.new_folder": self.new_folder,
                "file.new_file": self.new_file,
                "file.rename": self.rename_selected,
                "file.trash": self.trash_selected,
                "file.delete": self.delete_selected,
                "hist.undo": self.undo_last_operation,
                "hist.redo": self.redo_last_operation,
                "win.preferences": self.show_preferences_dialog,
                "win.palette": self.show_command_palette,
                "win.new_tab": self.new_tab,
                "win.close_tab": self.close_current_tab,
                "win.close_window": self.close,
                "win.toggle_preview": self.toggle_preview,
                "win.toggle_sidebar": self.toggle_sidebar,
                "view.mode.icons": lambda: self.set_view_mode(ViewMode.ICON),
                "view.mode.list": lambda: self.set_view_mode(ViewMode.LIST),
                "view.mode.details": lambda: self.set_view_mode(ViewMode.DETAILS),
                "view.mode.compact": lambda: self.set_view_mode(ViewMode.COMPACT),
                "view.hidden": lambda checked=None: self.toggle_hidden_files(checked),
                "view.extensions": lambda checked=None: self.toggle_file_extensions(checked),
                "view.checkboxes": lambda checked=None: self.toggle_selection_checkboxes(checked),
                "view.remember": lambda checked=None: self.toggle_folder_view_persistence(checked),
            },
        )
        self._registry_action_actions = {
            "clip.copy": getattr(self, "copy_action", None),
            "clip.cut": getattr(self, "cut_action", None),
            "clip.paste": getattr(self, "paste_action", None),
            "clip.copy_path": None,
            "hist.undo": getattr(self, "undo_action", None),
            "hist.redo": getattr(self, "redo_action", None),
            "nav.back": getattr(self, "back_action", None),
            "nav.forward": getattr(self, "forward_action", None),
            "view.hidden": getattr(self, "hidden_files_action", None),
            "view.extensions": getattr(self, "file_extensions_action", None),
            "view.checkboxes": getattr(self, "selection_checkboxes_action", None),
            "view.remember": getattr(self, "remember_view_action", None),
        }

    def refresh_registry_enablement(self) -> None:
        """Apply the central ActionRegistry enablement to real QActions.

        Builds a context from live state (selection, clipboard, undo/redo) and
        lets the declarative predicates in the catalog decide enabled state.
        Surfaces whose enablement is intentionally managed elsewhere (e.g. the
        contextual toolbar) keep their own logic; this method covers the
        always-visible actions (Edit > Copy/Cut/Paste, Undo/Redo).
        """
        from lfmapp.actions.qt import apply_enablement

        selected = self.workspace.selected_paths() if hasattr(self, "workspace") else []
        context = {
            "selection_count": len(selected),
            "clipboard_mode": getattr(self, "_clipboard_mode", None),
            "can_undo": self.operation_history.can_undo() if hasattr(self, "operation_history") else False,
            "can_redo": self.operation_history.can_redo() if hasattr(self, "operation_history") else False,
        }
        actions = {
            action_id: action
            for action_id, action in self._registry_action_actions.items()
            if action is not None
        }
        apply_enablement(self.action_registry, actions, context)

    @property
    def text_index_service(self):
        if self._text_index_service is None:
            self._text_index_service = TextIndexService()
        return self._text_index_service

    @property
    def history(self) -> list[Path]:
        """Back/forward history of the active tab (delegates to controller)."""
        return list(self.navigation.history)

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

