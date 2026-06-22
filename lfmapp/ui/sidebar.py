"""Sidebar for linux-file-manager.

Left panel with:
- Quick Access with pinned items
- Known XDG folders: Desktop, Documents, Downloads, Pictures, Music, Videos
- Computer: local drives
- Trash with item count
- Bookmarks
"""

from pathlib import Path

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QStyle, QVBoxLayout, QWidget
)

from lfmapp.core.paths import HOME_DIR
from lfmapp.services.network_service import discover_network_locations


class _SectionHeader(QLabel):
    """A styled section header label."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            "color: #888; font-size: 11px; font-weight: bold; "
            "padding: 8px 4px 2px 4px; border: none;"
        )


class Sidebar(QWidget):
    """Sidebar with quick access, known folders, computer, trash, and bookmarks."""

    itemActivated = pyqtSignal(QListWidgetItem)

    def __init__(self, bookmarks=None, parent=None, lazy_network=True):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        self._bookmarks = list(bookmarks or [])
        self._frequent_folders = []
        self._lazy_network = lazy_network

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Quick Access section
        layout.addWidget(_SectionHeader(self.tr("Quick Access")))
        self.quick_list = QListWidget()
        self.quick_list.setAlternatingRowColors(True)
        self.quick_list.setFrameShape(QFrame.Shape.NoFrame)
        self.quick_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.quick_list.itemDoubleClicked.connect(self._on_item_activated)
        self.quick_list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.quick_list)

        # Computer section
        layout.addWidget(_SectionHeader(self.tr("This Computer")))
        self.computer_list = QListWidget()
        self.computer_list.setAlternatingRowColors(True)
        self.computer_list.setFrameShape(QFrame.Shape.NoFrame)
        self.computer_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.computer_list.itemDoubleClicked.connect(self._on_item_activated)
        self.computer_list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.computer_list)

        # Network section
        layout.addWidget(_SectionHeader(self.tr("Network")))
        self.network_list = QListWidget()
        self.network_list.setAlternatingRowColors(True)
        self.network_list.setFrameShape(QFrame.Shape.NoFrame)
        self.network_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.network_list.itemDoubleClicked.connect(self._on_item_activated)
        self.network_list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.network_list)

        # Bookmarks section
        layout.addWidget(_SectionHeader(self.tr("Bookmarks")))
        self.bookmark_list = QListWidget()
        self.bookmark_list.setAlternatingRowColors(True)
        self.bookmark_list.setFrameShape(QFrame.Shape.NoFrame)
        self.bookmark_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.bookmark_list.itemDoubleClicked.connect(self._on_item_activated)
        self.bookmark_list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.bookmark_list)

        # Recent section
        layout.addWidget(_SectionHeader(self.tr("Recent")))
        self.recent_list = QListWidget()
        self.recent_list.setAlternatingRowColors(True)
        self.recent_list.setFrameShape(QFrame.Shape.NoFrame)
        self.recent_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_list.itemDoubleClicked.connect(self._on_item_activated)
        self.recent_list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.recent_list)

        self.populate()

    def _on_item_activated(self, item):
        if item is not None:
            self.itemActivated.emit(item)

    def populate(self):
        """Populate all sidebar sections."""
        self._populate_quick_access()
        self._populate_recent_locations()
        self._populate_computer()
        if self._lazy_network:
            self._populate_network_placeholder()
            QTimer.singleShot(0, self.refresh_network_locations)
        else:
            self._populate_network_locations()
        self._populate_bookmarks()

    def _populate_quick_access(self):
        """Populate Quick Access with home and known XDG folders."""
        self.quick_list.clear()
        style = self.quick_list.style()

        items = [
            (self.tr("Home"), str(HOME_DIR), QStyle.StandardPixmap.SP_DirHomeIcon),
        ]

        # XDG user directories
        xdg_dirs = [
            (self.tr("Desktop"), "Desktop", QStyle.StandardPixmap.SP_DirIcon),
            (self.tr("Documents"), "Documents", QStyle.StandardPixmap.SP_DirIcon),
            (self.tr("Downloads"), "Downloads", QStyle.StandardPixmap.SP_DirIcon),
            (self.tr("Music"), "Music", QStyle.StandardPixmap.SP_DirIcon),
            (self.tr("Pictures"), "Pictures", QStyle.StandardPixmap.SP_DirIcon),
            (self.tr("Videos"), "Videos", QStyle.StandardPixmap.SP_DirIcon),
        ]

        for label, dirname, icon in xdg_dirs:
            path = HOME_DIR / dirname
            if path.exists() and path.is_dir():
                items.append((label, str(path), icon))

        seen_paths = set()
        for label, path, icon in items:
            item = QListWidgetItem(style.standardIcon(icon), label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.quick_list.addItem(item)
            seen_paths.add(path)

        pinned_items = []
        for bookmark in self._bookmarks:
            if not self._bookmark_is_pinned(bookmark):
                continue
            path = self._bookmark_path(bookmark)
            if not path or path in seen_paths:
                continue
            folder = Path(path)
            if not folder.exists() or not folder.is_dir():
                continue
            pinned_items.append((self._bookmark_label(bookmark), path))
            seen_paths.add(path)

        if pinned_items:
            header = QListWidgetItem(self.tr("Pinned"))
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.quick_list.addItem(header)
            for label, path in pinned_items:
                item = QListWidgetItem(
                    style.standardIcon(QStyle.StandardPixmap.SP_DirIcon),
                    label,
                )
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setToolTip(path)
                self.quick_list.addItem(item)

        frequent_items = []
        for path in self._frequent_folders:
            folder = Path(path)
            if str(folder) in seen_paths or not folder.exists() or not folder.is_dir():
                continue
            frequent_items.append(folder)
            seen_paths.add(str(folder))

        if frequent_items:
            header = QListWidgetItem(self.tr("Frequent"))
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.quick_list.addItem(header)
            for folder in frequent_items:
                item = QListWidgetItem(
                    style.standardIcon(QStyle.StandardPixmap.SP_DirIcon),
                    folder.name or str(folder),
                )
                item.setData(Qt.ItemDataRole.UserRole, str(folder))
                item.setToolTip(str(folder))
                self.quick_list.addItem(item)

    def _populate_computer(self):
        """Populate Computer section with root filesystem and trash."""
        self.computer_list.clear()
        style = self.computer_list.style()

        # Root filesystem
        root_item = QListWidgetItem(
            style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon),
            self.tr("File System")
        )
        root_item.setData(Qt.ItemDataRole.UserRole, "/")
        root_item.setToolTip("/")
        self.computer_list.addItem(root_item)

        # Detect mounted drives under /media and /mnt
        for mount_base in [Path("/media"), Path("/mnt")]:
            if mount_base.exists():
                try:
                    for user_dir in mount_base.iterdir():
                        if user_dir.is_dir():
                            for drive in user_dir.iterdir():
                                if drive.is_dir() and drive.name not in (".", ".."):
                                    drive_item = QListWidgetItem(
                                        style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon),
                                        drive.name
                                    )
                                    drive_item.setData(Qt.ItemDataRole.UserRole, str(drive))
                                    drive_item.setToolTip(str(drive))
                                    self.computer_list.addItem(drive_item)
                except PermissionError:
                    pass

        # Trash
        trash_item = QListWidgetItem(
            style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon),
            self.tr("Trash")
        )
        trash_path = str(HOME_DIR / ".local" / "share" / "Trash" / "files")
        trash_item.setData(Qt.ItemDataRole.UserRole, trash_path)
        trash_item.setToolTip(self.tr("Trash"))
        self.computer_list.addItem(trash_item)

    def _populate_network_locations(self):
        """Populate network section with mounted GVFS shares."""
        self.network_list.clear()
        style = self.network_list.style()
        network_icon = getattr(QStyle.StandardPixmap, "SP_DriveNetIcon", QStyle.StandardPixmap.SP_DriveHDIcon)
        mounts = discover_network_locations()

        if not mounts:
            empty = QListWidgetItem(
                style.standardIcon(QStyle.StandardPixmap.SP_DirIcon),
                self.tr("No network shares mounted"),
            )
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.network_list.addItem(empty)
            return

        for path in mounts:
            label = Path(path).name or str(path)
            item = QListWidgetItem(style.standardIcon(network_icon), label)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.network_list.addItem(item)

    def _populate_network_placeholder(self):
        """Show a temporary network row until deferred discovery runs."""
        self.network_list.clear()
        item = QListWidgetItem(
            self.network_list.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon),
            self.tr("Loading network locations..."),
        )
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.network_list.addItem(item)

    def refresh_network_locations(self):
        """Refresh network locations after the sidebar is visible."""
        self._populate_network_locations()

    def _populate_bookmarks(self):
        """Populate bookmarks section."""
        self.bookmark_list.clear()
        style = self.bookmark_list.style()

        for bookmark in self._bookmarks:
            path = self._bookmark_path(bookmark)
            if not path:
                continue
            name = self._bookmark_label(bookmark)
            item = QListWidgetItem(
                style.standardIcon(QStyle.StandardPixmap.SP_DirIcon),
                name
            )
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.bookmark_list.addItem(item)

    def _populate_recent_locations(self):
        """Populate recent locations section."""
        self.recent_list.clear()
        style = self.recent_list.style()
        for path in getattr(self, "_recent_locations", []):
            item = QListWidgetItem(style.standardIcon(QStyle.StandardPixmap.SP_DirIcon), Path(path).name or path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.recent_list.addItem(item)

    def set_bookmarks(self, bookmarks):
        """Update bookmarks list."""
        self._bookmarks = list(bookmarks or [])
        self._populate_quick_access()
        self._populate_bookmarks()

    @staticmethod
    def _bookmark_path(bookmark):
        if isinstance(bookmark, dict):
            return bookmark.get("path")
        return str(bookmark) if bookmark else None

    @staticmethod
    def _bookmark_label(bookmark):
        if isinstance(bookmark, dict):
            path = bookmark.get("path", "")
            return bookmark.get("label") or Path(path).name or path
        path = str(bookmark)
        return Path(path).name or path

    @staticmethod
    def _bookmark_is_pinned(bookmark):
        return isinstance(bookmark, dict) and bool(bookmark.get("pinned", False))

    def set_recent_locations(self, recent_locations):
        """Update recent locations section."""
        self._recent_locations = list(recent_locations or [])
        self._populate_recent_locations()

    def set_frequent_folders(self, frequent_folders):
        """Update frequent folders shown in Quick Access."""
        self._frequent_folders = list(frequent_folders or [])
        self._populate_quick_access()

    def update_trash_count(self, count: int):
        """Update trash display with item count."""
        trash_path = str(HOME_DIR / ".local" / "share" / "Trash" / "files")
        for i in range(self.computer_list.count()):
            item = self.computer_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == trash_path:
                item.setText(
                    self.tr("Trash ({count})").format(count=count)
                    if count > 0
                    else self.tr("Trash")
                )
                break
