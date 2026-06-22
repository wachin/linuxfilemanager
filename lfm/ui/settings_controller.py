from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QDir
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QDialog, QInputDialog

from lfm.ui.preferences_dialog import PreferencesDialog

if TYPE_CHECKING:
    from lfm.ui.main_window import MainWindow


class SettingsController:
    def __init__(self, window: "MainWindow"):
        self.window = window

    @property
    def config(self):
        return self.window.config

    def apply_window_size_from_config(self):
        if not self.config.window_remember_size:
            self.window.resize(980, 620)
            return
        width = self.config.window_width
        height = self.config.window_height
        if width < 640 or height < 420:
            self.window.resize(980, 620)
            return
        self.window.resize(width, height)

    def save_window_size_to_config(self):
        if not self.config.window_remember_size:
            return
        if self.window.isMaximized() or self.window.isFullScreen():
            return
        size = self.window.size()
        self.config.set_window_size(size.width(), size.height())

    def apply_ui_font_from_config(self):
        app = QApplication.instance()
        if app is None:
            return
        font = app.font()
        if self.config.ui_font_family.strip():
            font.setFamily(self.config.ui_font_family.strip())
        font.setPointSize(self.config.ui_font_size)
        font.setWeight(self.config.ui_font_weight)
        font.setItalic(self.config.ui_font_italic)
        app.setFont(QFont(font))

    def increase_font_size(self):
        self.config.set_ui_font_size(self.config.ui_font_size + 1)
        self.apply_ui_font_from_config()

    def decrease_font_size(self):
        self.config.set_ui_font_size(self.config.ui_font_size - 1)
        self.apply_ui_font_from_config()

    def reset_font_size(self):
        self.config.set_ui_font_size(10)
        self.apply_ui_font_from_config()

    def set_font_size_dialog(self):
        value, ok = QInputDialog.getInt(
            self.window,
            self.window.tr("Font Size"),
            self.window.tr("Font size (points):"),
            self.config.ui_font_size,
            6,
            48,
            1,
        )
        if not ok:
            return
        self.config.set_ui_font_size(value)
        self.apply_ui_font_from_config()

    def choose_font_dialog(self):
        self.show_preferences_dialog()

    def show_preferences_dialog(self):
        dialog = PreferencesDialog(self.config, self.window.terminal_service, self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.apply_preferences(dialog.preferences())
        self.window.statusBar().showMessage(self.window.tr("Preferences updated"), 3000)

    def apply_preferences(self, preferences: dict):
        self.set_sidebar_visible(preferences["sidebar_visible"])
        self.set_preview_visible(preferences["preview_visible"])
        self.set_hidden_files_visible(preferences["show_hidden_files"])
        self.set_file_extensions_visible(preferences["show_file_extensions"])
        self.set_selection_checkboxes_visible(preferences["selection_checkboxes"])
        self.set_remember_folder_view(preferences["remember_folder_view"])
        self.set_window_preferences(
            preferences["window_remember_size"],
            preferences["window_width"],
            preferences["window_height"],
        )
        self.set_startup_location_preferences(
            preferences["startup_location_mode"],
            preferences["startup_location_custom_path"],
        )
        self.set_font_preferences(
            preferences["ui_font_family"],
            preferences["ui_font_size"],
            preferences["ui_font_weight"],
            preferences["ui_font_italic"],
        )
        self.set_preferred_terminal(preferences["preferred_terminal"])

    def set_sidebar_visible(self, visible: bool):
        self.window.sidebar.setVisible(visible)
        self.config.set_sidebar_visible(visible)
        if hasattr(self.window, "sidebar_action"):
            self.window.sidebar_action.setChecked(visible)

    def set_preview_visible(self, visible: bool):
        self.window.preview.setVisible(visible)
        self.config.set_preview_visible(visible)
        if hasattr(self.window, "preview_action"):
            self.window.preview_action.setChecked(visible)

    def apply_hidden_files_visibility(self, show_hidden: bool):
        filter_value = self.window.workspace.model.filter()
        if show_hidden:
            filter_value |= QDir.Filter.Hidden
        else:
            filter_value &= ~QDir.Filter.Hidden
        self.window.workspace.model.setFilter(filter_value)

    def set_hidden_files_visible(self, show_hidden: bool):
        self.apply_hidden_files_visibility(show_hidden)
        self.config.set_show_hidden_files(show_hidden)
        if hasattr(self.window, "hidden_files_action"):
            self.window.hidden_files_action.setChecked(show_hidden)

    def set_file_extensions_visible(self, show_extensions: bool):
        model = self.window.workspace.model
        model.show_extensions = bool(show_extensions)
        self.config.set_show_file_extensions(model.show_extensions)
        if hasattr(self.window, "file_extensions_action"):
            self.window.file_extensions_action.setChecked(model.show_extensions)
        model.layoutChanged.emit()

    def set_selection_checkboxes_visible(self, show_checkboxes: bool):
        model = self.window.workspace.model
        model.show_selection_checkboxes = bool(show_checkboxes)
        if not show_checkboxes:
            model.clear_checked_paths()
        else:
            model.layoutChanged.emit()
        self.config.set_selection_checkboxes(show_checkboxes)
        if hasattr(self.window, "selection_checkboxes_action"):
            self.window.selection_checkboxes_action.setChecked(show_checkboxes)

    def set_remember_folder_view(self, enabled: bool):
        self.config.set_remember_folder_view(enabled)
        if hasattr(self.window, "remember_view_action"):
            self.window.remember_view_action.setChecked(enabled)
        self.window.update_view_persistence_indicator()

    def set_window_preferences(self, remember_size: bool, width: int, height: int):
        self.config.set_window_remember_size(remember_size)
        self.config.set_window_size(width, height)
        self.window.resize(width, height)

    def set_startup_location_preferences(self, mode: str, custom_path: str):
        self.config.set_startup_location_mode(mode)
        self.config.set_startup_location_custom_path(custom_path)

    def set_font_preferences(
        self,
        family: str,
        size: int,
        weight: int,
        italic: bool,
    ):
        self.config.set_ui_font_family(family)
        self.config.set_ui_font_size(size)
        self.config.set_ui_font_weight(weight)
        self.config.set_ui_font_italic(italic)
        self.apply_ui_font_from_config()

    def set_preferred_terminal(self, terminal: str):
        self.config.set_preferred_terminal(terminal)
        self.window.terminal_service.refresh_terminals()
