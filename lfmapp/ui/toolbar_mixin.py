"""Toolbar construction extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QLabel, QMessageBox, QToolBar, QWidget

from lfmapp.services import is_archive
from lfmapp.ui.icons import app_icon
from lfmapp.utils.open_with import get_available_applications


class ToolbarMixin:
    # ─── Toolbar ───────────────────────────────────────────────

    def build_toolbar(self):
        toolbar = QToolBar(self.tr("Navigation"))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.back_action = QAction(app_icon("go-previous", "arrow-left"), self.tr("Back"), self)
        self.back_action.triggered.connect(self.go_back)
        self.back_action.setEnabled(False)
        toolbar.addAction(self.back_action)
        self._register_command_action(self.back_action, category=self.tr("Toolbar"))

        self.forward_action = QAction(app_icon("go-next", "arrow-right"), self.tr("Forward"), self)
        self.forward_action.triggered.connect(self.go_forward)
        self.forward_action.setEnabled(False)
        toolbar.addAction(self.forward_action)
        self._register_command_action(self.forward_action, category=self.tr("Toolbar"))

        self.up_action = QAction(app_icon("go-up", "arrow-up"), self.tr("Up"), self)
        self.up_action.triggered.connect(self.go_up)
        toolbar.addAction(self.up_action)
        self._register_command_action(self.up_action, category=self.tr("Toolbar"))

        self.home_action = QAction(app_icon("go-home", "user-home"), self.tr("Home"), self)
        self.home_action.triggered.connect(self.go_home)
        toolbar.addAction(self.home_action)
        self._register_command_action(self.home_action, category=self.tr("Toolbar"))

        toolbar.addSeparator()

        self.properties_action = QAction(app_icon("document-properties", "settings"), self.tr("Properties"), self)
        self.properties_action.triggered.connect(self.show_context_properties)
        toolbar.addAction(self.properties_action)
        self._register_command_action(self.properties_action, category=self.tr("Toolbar"))

        self.quick_access_action = QAction(app_icon("emblem-favorite", "bookmark-new"), self.tr("Pin to Quick Access"), self)
        self.quick_access_action.triggered.connect(self.toggle_quick_access_pin)
        toolbar.addAction(self.quick_access_action)
        self._register_command_action(self.quick_access_action, category=self.tr("Toolbar"))

        toolbar.addSeparator()

        # View toggle actions
        self.preview_action = QAction(app_icon("dialog-information", "view-preview"), self.tr("Preview"), self)
        self.preview_action.setCheckable(True)
        self.preview_action.setChecked(self.config.preview_visible)
        self.preview_action.triggered.connect(self.toggle_preview)
        toolbar.addAction(self.preview_action)
        self._register_command_action(self.preview_action, category=self.tr("Toolbar"))

        self.sidebar_action = QAction(app_icon("view-sidebar"), self.tr("Sidebar"), self)
        self.sidebar_action.setCheckable(True)
        self.sidebar_action.setChecked(self.config.sidebar_visible)
        self.sidebar_action.triggered.connect(self.toggle_sidebar)
        toolbar.addAction(self.sidebar_action)
        self._register_command_action(self.sidebar_action, category=self.tr("Toolbar"))

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
            self._register_command_action(action, category=self.tr("Context Toolbar"))

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
