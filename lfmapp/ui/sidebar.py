"""Sidebar for linux-file-manager.

Left panel with:
- Quick Access with pinned items
- Known XDG folders: Desktop, Documents, Downloads, Pictures, Music, Videos
- Computer: local drives
- Trash with item count
- Bookmarks
"""

from pathlib import Path

from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QRect, QSize
from PyQt6.QtGui import QIcon, QPainter, QPalette
from PyQt6.QtWidgets import (
    QFrame, QLabel, QListWidget, QListWidgetItem,
    QStyle, QStyleOptionTab, QTabBar, QTabWidget, QVBoxLayout, QWidget
)

from lfmapp.core.paths import HOME_DIR
from lfmapp.services.network_service import discover_network_locations
from lfmapp.ui.icons import app_icon


class _SidebarTabBar(QTabBar):
    """Compact icon-first tab bar with tooltips."""

    def tabSizeHint(self, index):
        return QSize(30, 30)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for index in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, index)
            rect = self.tabRect(index)
            is_active = index == self.currentIndex()

            fill = option.palette.color(QPalette.ColorRole.Base if is_active else QPalette.ColorRole.Window)
            border = option.palette.color(QPalette.ColorRole.Mid)
            text_color = option.palette.color(QPalette.ColorRole.WindowText)
            active_accent = option.palette.color(QPalette.ColorRole.Highlight)

            painter.save()
            painter.setPen(border)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect.adjusted(1, 2, -1, -1), 6, 6)

            if is_active:
                painter.fillRect(rect.adjusted(6, rect.height() - 4, -6, -1), active_accent)

            icon = self.tabIcon(index)
            icon_size = 18
            icon_y = 7 if is_active else (rect.height() - icon_size) // 2
            icon_rect = rect.adjusted(0, icon_y, 0, 0)
            icon.paint(
                painter,
                QRect(rect.center().x() - icon_size // 2, icon_rect.top(), icon_size, icon_size),
            )
            painter.restore()


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
        layout.setSpacing(6)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabBar(_SidebarTabBar(self.tab_widget))
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setMovable(False)
        self.tab_widget.tabBar().setExpanding(False)
        self.tab_widget.tabBar().setDrawBase(False)

        self.quick_list = self._create_section_list()
        self.computer_list = self._create_section_list()
        self.network_list = self._create_section_list()
        self.bookmark_list = self._create_section_list()
        self.recent_list = self._create_section_list()

        self.quick_title = self._create_section_title(self.tr("Quick Access"))
        self.computer_title = self._create_section_title(self.tr("This Computer"))
        self.network_title = self._create_section_title(self.tr("Network"))
        self.bookmark_title = self._create_section_title(self.tr("Bookmarks"))
        self.recent_title = self._create_section_title(self.tr("Recent"))

        self._add_tab(self.quick_list, self.quick_title, self.tr("Quick Access"), app_icon("user-bookmarks", "emblem-favorite", "bookmark-new"))
        self._add_tab(self.computer_list, self.computer_title, self.tr("This Computer"), app_icon("computer", "drive-harddisk", "computer-symbolic"))
        self._add_tab(self.network_list, self.network_title, self.tr("Network"), app_icon("network-workgroup", "network-server", "folder-remote"))
        self._add_tab(self.bookmark_list, self.bookmark_title, self.tr("Bookmarks"), app_icon("bookmarks", "folder-bookmarks", "bookmark-new"))
        self._add_tab(self.recent_list, self.recent_title, self.tr("Recent"), app_icon("document-open-recent", "folder-recent", "view-history"))

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tab_widget)
        self._apply_sidebar_style()
        self._on_tab_changed(self.tab_widget.currentIndex())

        self.populate()

    def _create_section_list(self) -> QListWidget:
        section_list = QListWidget()
        section_list.setAlternatingRowColors(True)
        section_list.setFrameShape(QFrame.Shape.NoFrame)
        section_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        section_list.itemDoubleClicked.connect(self._on_item_activated)
        section_list.itemActivated.connect(self._on_item_activated)
        return section_list

    def _create_section_title(self, title: str) -> QLabel:
        label = QLabel(title, self)
        label.setObjectName("sidebarSectionTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _create_tab_page(self, title_label: QLabel, section_list: QListWidget) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(title_label)
        layout.addWidget(section_list)
        return page

    def _add_tab(self, section_list: QListWidget, title_label: QLabel, title: str, icon: QIcon):
        page = self._create_tab_page(title_label, section_list)
        index = self.tab_widget.addTab(page, icon, title)
        self.tab_widget.tabBar().setTabToolTip(index, title)

    def _on_tab_changed(self, index: int):
        self.tab_widget.tabBar().update()
        self.tab_widget.tabBar().updateGeometry()

    def _apply_sidebar_style(self):
        self.tab_widget.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid palette(mid);
                border-top: none;
                background: palette(base);
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QLabel#sidebarSectionTitle {
                padding: 6px 8px 2px 8px;
                color: palette(window-text);
                font-weight: 600;
            }
            QListWidget {
                border: none;
                background: palette(base);
                padding: 4px 0;
            }
            QListWidget::item {
                padding: 4px 8px;
            }
            QListWidget::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
                border-radius: 4px;
            }
            """
        )

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
