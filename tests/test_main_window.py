import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QLabel

import lfmapp.core.config as config_module
from lfmapp.ui.about_dialog import AboutDialog
from lfmapp.ui.main_window import MainWindow
from lfmapp.services.operation_history import RenameOperation


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


class MainWindowMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    @patch("lfmapp.ui.main_window.get_available_applications", return_value=[("testapp.desktop", "Test App")])
    def test_share_menu_contains_share_actions(self, _mock_apps):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir)
            config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
            try:
                window = MainWindow()
                window.rebuild_share_menu()

                actions = [action.text() for action in window.share_menu.actions() if action.text()]

                self.assertIn("Send to Desktop", actions)
                self.assertIn("Send by Email", actions)
                self.assertIn("Print", actions)
                self.assertIn("Compress to ZIP", actions)
                self.assertIn("Advanced Security...", actions)
                self.assertIn("Share with", actions)
            finally:
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_toolbar_contains_properties_and_quick_access_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir)
            config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
            try:
                window = MainWindow()
                actions = [action.text() for action in window.findChildren(QAction) if action.text()]

                self.assertIn("Properties", actions)
                self.assertTrue(
                    "Pin to Quick Access" in actions
                    or "Unpin from Quick Access" in actions
                    or "In Quick Access" in actions
                )
            finally:
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_tag_and_vault_services_are_lazy(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir)
            config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
            try:
                window = MainWindow()

                self.assertIsNone(window._tag_service)
                self.assertIsNone(window._vault_service)

                self.assertIs(window.tag_service, window.tag_service)
                self.assertIsNotNone(window._tag_service)
                self.assertIs(window.vault_service, window.vault_service)
                self.assertIsNotNone(window._vault_service)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_view_menu_contains_icon_grid_size_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir)
            config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
            try:
                window = MainWindow()
                actions = [action.text() for action in window.findChildren(QAction) if action.text()]

                self.assertIn("Icon grid size", actions)
                self.assertIn("Small", actions)
                self.assertIn("Medium", actions)
                self.assertIn("Large", actions)
            finally:
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_file_menu_contains_tab_actions(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir)
            config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
            try:
                window = MainWindow()
                actions = [action.text() for action in window.findChildren(QAction) if action.text()]

                self.assertIn("New Tab", actions)
                self.assertIn("Close Tab", actions)
                self.assertIn("Next Tab", actions)
                self.assertIn("Previous Tab", actions)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_undo_redo_action_text_uses_main_window_translation_boundary(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                operation = RenameOperation(Path(tmpdir) / "old.txt", Path(tmpdir) / "new.txt")

                window.record_operation(operation)

                self.assertEqual(window.undo_action.text(), "Undo Rename old.txt to new.txt")
                self.assertFalse(window.redo_action.isEnabled())
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_contextual_toolbar_classifies_selected_path_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            folder = root / "folder"
            folder.mkdir()
            archive = root / "archive.zip"
            archive.write_bytes(b"PK\x05\x06" + b"\0" * 18)
            image = root / "photo.png"
            image.write_bytes(b"")
            document = root / "notes.txt"
            document.write_text("hello", encoding="utf-8")
            unknown = root / "data.bin"
            unknown.write_bytes(b"\0")

            self.assertEqual(MainWindow.contextual_type_for_path(folder), "folder")
            self.assertEqual(MainWindow.contextual_type_for_path(archive), "archive")
            self.assertEqual(MainWindow.contextual_type_for_path(image), "image")
            self.assertEqual(MainWindow.contextual_type_for_path(document), "document")
            self.assertEqual(MainWindow.contextual_type_for_path(unknown), "file")

    def test_contextual_toolbar_updates_visible_actions_for_archive(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                archive = Path(tmpdir) / "archive.zip"
                archive.write_bytes(b"PK\x05\x06" + b"\0" * 18)
                window = MainWindow()

                with patch.object(window.workspace, "selected_path", return_value=archive):
                    window.update_contextual_toolbar()

                visible = {
                    key
                    for key, action in window.context_actions.items()
                    if action.isVisible()
                }
                self.assertEqual(window.context_title_label.text(), "Archive Tools")
                self.assertIn("extract_here", visible)
                self.assertIn("extract_to", visible)
                self.assertNotIn("print", visible)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_tabs_keep_independent_navigation_history(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                root = Path(tmpdir)
                first = root / "first"
                second = root / "second"
                first.mkdir()
                second.mkdir()

                window = MainWindow()
                window.go_to(first)
                first_tab = window.tabbar.currentIndex()

                window.new_tab(second)
                second_tab = window.tabbar.currentIndex()

                self.assertEqual(window.tabbar.count(), 2)
                self.assertEqual(window.workspace.current_path(), second)
                self.assertEqual(window.history, [second])

                window.tabbar.setCurrentIndex(first_tab)

                self.assertEqual(window.workspace.current_path(), first)
                self.assertEqual(window.history[-1], first)

                window.tabbar.setCurrentIndex(second_tab)

                self.assertEqual(window.workspace.current_path(), second)
                self.assertEqual(window.history, [second])
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_tools_menu_contains_preferences_action(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                actions = [action.text() for action in window.findChildren(QAction) if action.text()]
                self.assertIn("Preferences...", actions)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_apply_preferences_updates_runtime_state_and_config(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                window.apply_preferences(
                    {
                        "sidebar_visible": False,
                        "preview_visible": False,
                        "show_hidden_files": False,
                        "show_file_extensions": False,
                        "selection_checkboxes": True,
                        "remember_folder_view": False,
                        "window_remember_size": True,
                        "window_width": 840,
                        "window_height": 560,
                        "startup_location_mode": "custom",
                        "startup_location_custom_path": tmpdir,
                        "ui_font_family": "DejaVu Sans",
                        "ui_font_size": 13,
                        "ui_font_weight": 700,
                        "ui_font_italic": True,
                        "preferred_terminal": "",
                    }
                )

                self.assertFalse(window.sidebar.isVisible())
                self.assertFalse(window.preview.isVisible())
                self.assertFalse(window.config.show_hidden_files)
                self.assertFalse(window.workspace.model.show_extensions)
                self.assertTrue(window.workspace.model.show_selection_checkboxes)
                self.assertFalse(window.config.remember_folder_view)
                self.assertEqual(window.config.window_width, 840)
                self.assertEqual(window.config.window_height, 560)
                self.assertEqual(window.config.startup_location_mode, "custom")
                self.assertEqual(window.config.startup_location_custom_path, tmpdir)
                self.assertEqual(window.config.ui_font_family, "DejaVu Sans")
                self.assertEqual(window.config.ui_font_size, 13)
                self.assertEqual(window.config.ui_font_weight, 700)
                self.assertTrue(window.config.ui_font_italic)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_about_dialog_contains_contact_and_license_information(self):
        dialog = AboutDialog()
        labels = dialog.findChildren(QLabel)
        text = "\n".join(label.text() for label in labels if label.text())

        self.assertIn("linuxfrontier@proton.me", text)
        self.assertIn("mailto:linuxfrontier@proton.me", text)
        self.assertIn("https://github.com/wachin/linuxfilemanager", text)
        self.assertIn("GPL3", text)
        self.assertIn("Washington Indacochea Delgado", text)

    def test_startup_path_uses_custom_folder_when_configured(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                startup_folder = Path(tmpdir) / "startup"
                startup_folder.mkdir()

                cfg = config_module.Config()
                cfg.set_startup_location_mode("custom")
                cfg.set_startup_location_custom_path(str(startup_folder))

                window = MainWindow()

                self.assertEqual(window.workspace.current_path(), startup_folder)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_startup_path_falls_back_to_home_when_custom_folder_is_missing(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                cfg = config_module.Config()
                cfg.set_startup_location_mode("custom")
                cfg.set_startup_location_custom_path(str(Path(tmpdir) / "missing"))

                window = MainWindow()

                self.assertEqual(window.workspace.current_path(), Path.home())
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file


if __name__ == "__main__":
    unittest.main()
