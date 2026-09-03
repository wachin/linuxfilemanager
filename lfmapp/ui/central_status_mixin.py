"""Central widget & status bar construction extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from lfmapp.controllers import SelectionController
from lfmapp.ui.icons import app_icon


class CentralWidgetStatusBarMixin:
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
        except (PermissionError, FileNotFoundError, OSError):
            # The current folder may have been removed or renamed while it was
            # displayed (e.g. during an operation on the parent); never crash
            # the status refresh because of a vanished path.
            self.status_items.setText(self.tr("  (unavailable)"))

        # Selection info (derived by the selection controller, Fase 1.1)
        selected = self.workspace.selected_paths()
        if selected:
            summary = SelectionController.summarize(selected)
            total_size = summary.total_file_size()
            size_str = self._human_size(total_size) if total_size else ""
            self.status_selection.setText(
                self.tr("  {count} selected  {size}").format(count=summary.count, size=size_str)
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
