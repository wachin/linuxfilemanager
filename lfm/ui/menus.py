"""Context menus for linux-file-manager.

Provides the main context menu and specialized menus
for common file management workflows.
"""

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu


class ContextMenu(QMenu):
    """Main context menu for files and folders."""

    openRequested = pyqtSignal(object)
    openWithRequested = pyqtSignal(object)
    cutRequested = pyqtSignal(object)
    copyRequested = pyqtSignal(object)
    copyPathRequested = pyqtSignal(object)
    pasteRequested = pyqtSignal(object)
    renameRequested = pyqtSignal(object)
    deleteRequested = pyqtSignal(object)
    trashRequested = pyqtSignal(object)
    propertiesRequested = pyqtSignal(object)
    newFolderRequested = pyqtSignal(object)
    newFileRequested = pyqtSignal(object)
    sendToDesktopRequested = pyqtSignal(object)
    compressRequested = pyqtSignal(object)
    viewModeRequested = pyqtSignal(str)
    toggleHiddenRequested = pyqtSignal()
    toggleExtensionsRequested = pyqtSignal()
    sortRequested = pyqtSignal(str)
    openTerminalRequested = pyqtSignal(object)

    def __init__(self, path: Path = None, parent=None):
        super().__init__(parent)
        self.path = path
        self._build()

    def _build(self):
        """Build the context menu."""
        if self.path and self.path.is_dir():
            self._build_folder_menu()
        elif self.path and self.path.is_file():
            self._build_file_menu()
        else:
            self._build_empty_area_menu()

    def _build_file_menu(self):
        """Build context menu for a file."""
        # Open section
        self.addAction(QIcon.fromTheme("document-open"), self.tr("Open"), self._on_open)
        self.addAction(self.tr("Open with..."), self._on_open_with)

        self.addSeparator()

        # Clipboard section
        self.addAction(QIcon.fromTheme("edit-cut"), self.tr("Cut"), self._on_cut)
        self.addAction(QIcon.fromTheme("edit-copy"), self.tr("Copy"), self._on_copy)
        self.addAction(self.tr("Copy path"), self._on_copy_path)

        self.addSeparator()

        # File operations section
        self.addAction(QIcon.fromTheme("document-save-as"), self.tr("Rename"), self._on_rename)
        self.addAction(QIcon.fromTheme("edit-delete"), self.tr("Delete"), self._on_delete)
        self.addAction(QIcon.fromTheme("user-trash"), self.tr("Move to Trash"), self._on_trash)

        self.addSeparator()

        # Send to section
        send_to_menu = QMenu(self.tr("Send to"), self)
        send_to_menu.addAction(self.tr("Desktop"), self._on_send_to_desktop)
        send_to_menu.addAction(self.tr("Compress to ZIP"), self._on_compress)
        self.addMenu(send_to_menu)

        self.addSeparator()

        # Properties
        self.addAction(QIcon.fromTheme("document-properties"), self.tr("Properties"), self._on_properties)

    def _build_folder_menu(self):
        """Build context menu for a folder."""
        self.addAction(QIcon.fromTheme("document-open"), self.tr("Open"), self._on_open)
        self.addAction(QIcon.fromTheme("utilities-terminal"), self.tr("Open in Terminal"), self._on_open_terminal)

        self.addSeparator()

        # Clipboard section
        self.addAction(QIcon.fromTheme("edit-cut"), self.tr("Cut"), self._on_cut)
        self.addAction(QIcon.fromTheme("edit-copy"), self.tr("Copy"), self._on_copy)
        self.addAction(self.tr("Copy path"), self._on_copy_path)

        self.addSeparator()

        # Folder operations
        self.addAction(QIcon.fromTheme("document-save-as"), self.tr("Rename"), self._on_rename)
        self.addAction(QIcon.fromTheme("edit-delete"), self.tr("Delete"), self._on_delete)
        self.addAction(QIcon.fromTheme("user-trash"), self.tr("Move to Trash"), self._on_trash)

        self.addSeparator()

        # New section
        new_menu = QMenu(self.tr("New"), self)
        new_menu.addAction(self.tr("Folder"), self._on_new_folder)
        new_menu.addAction(self.tr("Empty file"), self._on_new_file)
        self.addMenu(new_menu)

        self.addSeparator()

        # Properties
        self.addAction(QIcon.fromTheme("document-properties"), self.tr("Properties"), self._on_properties)

    def _build_empty_area_menu(self):
        """Build context menu for empty workspace area."""
        self.addAction(QIcon.fromTheme("utilities-terminal"), self.tr("Open in Terminal"), self._on_open_terminal)

        self.addSeparator()

        # View section
        view_menu = QMenu(self.tr("View"), self)
        view_menu.addAction(self.tr("Icons"), self._on_view_icons)
        view_menu.addAction(self.tr("List"), self._on_view_list)
        view_menu.addAction(self.tr("Details"), self._on_view_details)
        view_menu.addSeparator()
        view_menu.addAction(self.tr("Show hidden files"), self._on_toggle_hidden)
        view_menu.addAction(self.tr("Show file extensions"), self._on_toggle_extensions)
        self.addMenu(view_menu)

        self.addSeparator()

        # Sort section
        sort_menu = QMenu(self.tr("Sort by"), self)
        sort_menu.addAction(self.tr("Name"), self._on_sort_name)
        sort_menu.addAction(self.tr("Size"), self._on_sort_size)
        sort_menu.addAction(self.tr("Type"), self._on_sort_type)
        sort_menu.addAction(self.tr("Date modified"), self._on_sort_date)
        self.addMenu(sort_menu)

        self.addSeparator()

        # New section
        new_menu = QMenu(self.tr("New"), self)
        new_menu.addAction(self.tr("Folder"), self._on_new_folder)
        new_menu.addAction(self.tr("Empty file"), self._on_new_file)
        self.addMenu(new_menu)

        self.addSeparator()

        self.addAction(self.tr("Paste"), self._on_paste)
        self.addAction(QIcon.fromTheme("document-properties"), self.tr("Properties"), self._on_properties)

    def _on_open(self):
        self.openRequested.emit(self.path)

    def _on_open_with(self):
        self.openWithRequested.emit(self.path)

    def _on_cut(self):
        self.cutRequested.emit(self.path)

    def _on_copy(self):
        self.copyRequested.emit(self.path)

    def _on_copy_path(self):
        self.copyPathRequested.emit(self.path)

    def _on_paste(self):
        self.pasteRequested.emit(self.path)

    def _on_rename(self):
        self.renameRequested.emit(self.path)

    def _on_delete(self):
        self.deleteRequested.emit(self.path)

    def _on_trash(self):
        self.trashRequested.emit(self.path)

    def _on_properties(self):
        self.propertiesRequested.emit(self.path)

    def _on_new_folder(self):
        self.newFolderRequested.emit(self.path)

    def _on_new_file(self):
        self.newFileRequested.emit(self.path)

    def _on_send_to_desktop(self):
        self.sendToDesktopRequested.emit(self.path)

    def _on_compress(self):
        self.compressRequested.emit(self.path)

    def _on_view_icons(self):
        self.viewModeRequested.emit("icon")

    def _on_view_list(self):
        self.viewModeRequested.emit("list")

    def _on_view_details(self):
        self.viewModeRequested.emit("details")

    def _on_toggle_hidden(self):
        self.toggleHiddenRequested.emit()

    def _on_toggle_extensions(self):
        self.toggleExtensionsRequested.emit()

    def _on_sort_name(self):
        self.sortRequested.emit("name")

    def _on_sort_size(self):
        self.sortRequested.emit("size")

    def _on_sort_type(self):
        self.sortRequested.emit("type")

    def _on_sort_date(self):
        self.sortRequested.emit("modified")

    def _on_open_terminal(self):
        self.openTerminalRequested.emit(self.path)


class ToolbarMenu(QMenu):
    """Toolbar menu for the main window."""

    newTabRequested = pyqtSignal()
    newWindowRequested = pyqtSignal()
    closeTabRequested = pyqtSignal()
    copyRequested = pyqtSignal()
    cutRequested = pyqtSignal()
    pasteRequested = pyqtSignal()
    selectAllRequested = pyqtSignal()
    deselectAllRequested = pyqtSignal()
    viewModeRequested = pyqtSignal(str)
    toggleHiddenRequested = pyqtSignal()
    togglePreviewRequested = pyqtSignal()
    toggleSidebarRequested = pyqtSignal()
    backRequested = pyqtSignal()
    forwardRequested = pyqtSignal()
    upRequested = pyqtSignal()
    homeRequested = pyqtSignal()
    aboutRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        """Build the toolbar menu."""
        # File section
        file_menu = QMenu(self.tr("File"), self)
        file_menu.addAction(self.tr("New tab"), self._on_new_tab)
        file_menu.addAction(self.tr("New window"), self._on_new_window)
        file_menu.addSeparator()
        file_menu.addAction(self.tr("Close tab"), self._on_close_tab)
        self.addMenu(file_menu)

        # Edit section
        edit_menu = QMenu(self.tr("Edit"), self)
        edit_menu.addAction(self.tr("Copy"), self._on_copy)
        edit_menu.addAction(self.tr("Cut"), self._on_cut)
        edit_menu.addAction(self.tr("Paste"), self._on_paste)
        edit_menu.addSeparator()
        edit_menu.addAction(self.tr("Select all"), self._on_select_all)
        edit_menu.addAction(self.tr("Deselect all"), self._on_deselect_all)
        self.addMenu(edit_menu)

        # View section
        view_menu = QMenu(self.tr("View"), self)
        view_menu.addAction(self.tr("Icons"), self._on_view_icons)
        view_menu.addAction(self.tr("List"), self._on_view_list)
        view_menu.addAction(self.tr("Details"), self._on_view_details)
        view_menu.addSeparator()
        view_menu.addAction(self.tr("Show hidden files"), self._on_toggle_hidden)
        view_menu.addAction(self.tr("Show preview panel"), self._on_toggle_preview)
        view_menu.addAction(self.tr("Show sidebar"), self._on_toggle_sidebar)
        self.addMenu(view_menu)

        # Go section
        go_menu = QMenu(self.tr("Go"), self)
        go_menu.addAction(self.tr("Back"), self._on_back)
        go_menu.addAction(self.tr("Forward"), self._on_forward)
        go_menu.addAction(self.tr("Up"), self._on_up)
        go_menu.addAction(self.tr("Home"), self._on_home)
        self.addMenu(go_menu)

        # Help section
        help_menu = QMenu(self.tr("Help"), self)
        help_menu.addAction(self.tr("About"), self._on_about)
        self.addMenu(help_menu)

    def _on_new_tab(self):
        self.newTabRequested.emit()

    def _on_new_window(self):
        self.newWindowRequested.emit()

    def _on_close_tab(self):
        self.closeTabRequested.emit()

    def _on_copy(self):
        self.copyRequested.emit()

    def _on_cut(self):
        self.cutRequested.emit()

    def _on_paste(self):
        self.pasteRequested.emit()

    def _on_select_all(self):
        self.selectAllRequested.emit()

    def _on_deselect_all(self):
        self.deselectAllRequested.emit()

    def _on_view_icons(self):
        self.viewModeRequested.emit("icon")

    def _on_view_list(self):
        self.viewModeRequested.emit("list")

    def _on_view_details(self):
        self.viewModeRequested.emit("details")

    def _on_toggle_hidden(self):
        self.toggleHiddenRequested.emit()

    def _on_toggle_preview(self):
        self.togglePreviewRequested.emit()

    def _on_toggle_sidebar(self):
        self.toggleSidebarRequested.emit()

    def _on_back(self):
        self.backRequested.emit()

    def _on_forward(self):
        self.forwardRequested.emit()

    def _on_up(self):
        self.upRequested.emit()

    def _on_home(self):
        self.homeRequested.emit()

    def _on_about(self):
        self.aboutRequested.emit()
