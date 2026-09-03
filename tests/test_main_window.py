import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QLabel

import lfmapp.core.config as config_module
from lfmapp.controllers import SearchOutcome
from lfmapp.ui.about_dialog import AboutDialog
from lfmapp.ui.command_palette_dialog import CommandPaletteDialog
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

    @patch("lfmapp.ui.context_menu_mixin.get_available_applications", return_value=[("testapp.desktop", "Test App")])
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

                with patch("lfmapp.services.tag_service.TAGS_DB_FILE", Path(tmpdir) / "tags.db"):
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

    def test_command_palette_registers_menu_actions(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                registered_titles = {info["title"] for info in window._command_actions}
                self.assertIn("Command Palette...", registered_titles)
                self.assertIn("Preferences...", registered_titles)
                self.assertIn("Back", registered_titles)
                self.assertIn("Toggle Preview Panel", registered_titles)
                self.assertIn("Small", registered_titles)
                self.assertIn("Medium", registered_titles)
                self.assertIn("Large", registered_titles)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_recent_files_menu_registers_recent_file_actions(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                first = Path(tmpdir) / "first.txt"
                second = Path(tmpdir) / "second.txt"
                first.write_text("one", encoding="utf-8")
                second.write_text("two", encoding="utf-8")

                window = MainWindow()
                window.config.add_recent_file(str(first))
                window.config.add_recent_file(str(second))
                window.rebuild_recent_files_menu()

                commands = window._palette_commands()
                titles = {command["title"] for command in commands}
                self.assertIn("Clear Recent Files", titles)
                self.assertIn(first.name, titles)
                self.assertIn(second.name, titles)

                recent_command = next(
                    command for command in commands if command["title"] == first.name
                )
                self.assertIn(str(first), recent_command.get("alias", []))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_share_with_menu_registers_actions_in_palette(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                fake_app = ("/usr/share/applications/fake.desktop", "Fake App")

                with patch("lfmapp.ui.context_menu_mixin.get_available_applications", return_value=[fake_app]):
                    window._add_share_with_menu(window.share_menu, Path(tmpdir) / "file.txt")

                commands = window._palette_commands()
                titles = {command["title"] for command in commands}
                self.assertIn("Fake App", titles)
                self.assertIn("Share with", {command["category"] for command in commands})
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_tags_in_context_menu_register_in_palette(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                tagged = Path(tmpdir) / "file.txt"
                tagged.write_text("hello", encoding="utf-8")

                fake_tags = [{"name": "project"}, {"name": "todo"}]
                from unittest.mock import MagicMock
                mock_tags = MagicMock()
                mock_tags.get_tags_for_file.return_value = fake_tags
                window._tag_service = mock_tags
                # Build a QMenu and invoke the file context menu builder to register tag actions
                from PyQt6.QtWidgets import QMenu
                menu = QMenu(window)
                window._build_file_context_menu(menu, tagged)
                commands = window._palette_commands()
                titles = {command["title"] for command in commands}

                # Actions are titled with a checkmark prefix in the menu
                self.assertIn("✓ project", titles)
                self.assertIn("✓ todo", titles)
                aliases = {command["title"]: command.get("alias", []) for command in commands}
                self.assertIn("project", aliases.get("✓ project", []))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_share_with_context_menu_registers_apps_in_palette(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                target = Path(tmpdir) / "file.txt"
                target.write_text("hello", encoding="utf-8")

                fake_app = ("/usr/share/applications/fake.desktop", "Fake Share App")
                from unittest.mock import patch
                with patch("lfmapp.ui.context_menu_mixin.get_available_applications", return_value=[fake_app]):
                    # build the file context menu which will call _add_share_with_menu
                    from PyQt6.QtWidgets import QMenu
                    menu = QMenu(window)
                    window._build_file_context_menu(menu, target)

                commands = window._palette_commands()
                titles = {command["title"] for command in commands}
                self.assertIn("Fake Share App", titles)
                aliases = {command["title"]: command.get("alias", []) for command in commands}
                self.assertIn("share", aliases.get("Fake Share App", []))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_contextual_palette_commands_include_selection_actions(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                selected = Path(tmpdir) / "file.txt"
                selected.write_text("hello", encoding="utf-8")

                with patch.object(window.workspace, "selected_path", return_value=selected):
                    commands = window._palette_commands()
                    titles = {command["title"] for command in commands}

                self.assertIn("Open", titles)
                self.assertIn("Open with...", titles)
                self.assertIn("Copy path", titles)
                self.assertIn("Rename", titles)
                self.assertIn("Properties", titles)
                self.assertIn("Set default application...", titles)
                self.assertIn("Copy to...", titles)
                self.assertIn("Move to...", titles)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_contextual_palette_commands_include_paste_when_clipboard_has_items(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                window._clipboard_mode = "copy"
                window._clipboard_paths = [Path(tmpdir) / "file.txt"]
                commands = window._palette_commands()
                titles = {command["title"] for command in commands}

                self.assertIn("Paste", titles)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_palette_includes_navigation_shortcuts(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                commands = window._palette_commands()
                titles = {command["title"] for command in commands}

                self.assertIn("Go to Path...", titles)
                self.assertIn("Open Recent File...", titles)
                self.assertIn("Open in Terminal", titles)
                self.assertIn("Refresh", titles)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_quick_access_commands_include_home_destination(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                commands = window._palette_commands()
                quick_access_commands = [
                    command for command in commands if command["category"] == "Quick Access"
                ]
                titles = {command["title"] for command in quick_access_commands}

                self.assertIn("Open Home", titles)
                home_command = next(
                    command for command in quick_access_commands if command["title"] == "Open Home"
                )
                self.assertIn("home", home_command.get("alias", []))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_quick_access_commands_include_pinned_bookmarks(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                bookmark_path = Path(tmpdir) / "pinned"
                bookmark_path.mkdir()
                window.bookmark_service.add(str(bookmark_path), label="Pinned Folder", pinned=True)

                commands = window._palette_commands()
                titles = {command["title"] for command in commands}
                self.assertIn("Open Pinned Folder", titles)

                command = next(
                    command for command in commands if command["title"] == "Open Pinned Folder"
                )
                self.assertEqual(command["category"], "Quick Access")
                self.assertIn(str(bookmark_path), command.get("alias", []))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_recent_locations_register_as_quick_access_palette_commands(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                recent_dir = Path(tmpdir) / "recent-folder"
                recent_dir.mkdir()
                window.config.add_recent_location(str(recent_dir))

                commands = window._palette_commands()
                quick_access_commands = [
                    command for command in commands if command["category"] == "Quick Access"
                ]
                self.assertIn("Open recent-folder", {command["title"] for command in quick_access_commands})

                command = next(
                    command for command in quick_access_commands if command["title"] == "Open recent-folder"
                )
                self.assertEqual(command["category"], "Quick Access")
                self.assertIn(str(recent_dir), command.get("alias", []))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_dynamic_action_title_updates_in_palette(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                window.update_quick_access_action()
                title = window.quick_access_action.text()
                command = next(
                    command for command in window._palette_commands() if command["title"] == title
                )
                self.assertEqual(command["title"], title)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_quick_access_action_title_is_kept_in_sync_in_palette(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                window.quick_access_action.setText(window.tr("In Quick Access"))
                window.update_quick_access_action()
                self.assertTrue(any(
                    command["title"] == "In Quick Access" for command in window._palette_commands()
                ))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_dynamic_action_title_aliases_update_in_palette(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                window.update_quick_access_action()
                title = window.quick_access_action.text()
                command = next(
                    command for command in window._palette_commands() if command["title"] == title
                )
                self.assertIn("quick access", command.get("alias", []))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_command_palette_search_matches_aliases(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                commands = window._palette_commands()
                aliases = {command["title"]: command.get("alias", []) for command in commands}
                self.assertIn("refresh", aliases["Refresh"])
                self.assertIn("terminal", aliases["Open in Terminal"])
                self.assertIn("cd", aliases["Go to Path..."])

                fake_file = Path(tmpdir) / "file.txt"
                fake_file.write_text("hello", encoding="utf-8")
                with patch("lfmapp.ui.context_menu_mixin.get_available_applications", return_value=[("/usr/share/applications/fake.desktop", "Fake App")]):
                    window._add_share_with_menu(window.share_menu, fake_file)

                commands = window._palette_commands()
                aliases = {command["title"]: command.get("alias", []) for command in commands}
                self.assertIn("share", aliases.get("Fake App", []))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_unique_palette_commands_keep_different_command_ids(self):
        commands = [
            {
                "title": "Open Sample",
                "callback": lambda: None,
                "shortcut": "",
                "category": "Recent Files",
                "enabled": True,
                "alias": ["sample"],
                "command_id": "recent_file::1",
            },
            {
                "title": "Open Sample",
                "callback": lambda: None,
                "shortcut": "",
                "category": "Recent Files",
                "enabled": True,
                "alias": ["sample"],
                "command_id": "recent_file::2",
            },
        ]
        dialog = CommandPaletteDialog(commands)
        self.assertEqual(dialog.command_list.count(), 2)

    def test_command_palette_prioritizes_enabled_commands(self):
        commands = [
            {
                "title": "Open",
                "callback": lambda: None,
                "shortcut": "",
                "category": "Selection",
                "enabled": False,
                "alias": ["open"],
            },
            {
                "title": "Open File",
                "callback": lambda: None,
                "shortcut": "",
                "category": "Selection",
                "enabled": True,
                "alias": ["open"],
            },
        ]
        dialog = CommandPaletteDialog(commands)
        dialog._filter_commands("open")
        titles = [dialog.command_list.item(i).data(Qt.ItemDataRole.UserRole)["title"] for i in range(dialog.command_list.count())]
        self.assertEqual("Open File", titles[0])

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

    def test_open_terminal_in_directory_uses_parent_for_files(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                root = Path(tmpdir)
                file_path = root / "note.txt"
                file_path.write_text("hello", encoding="utf-8")
                window = MainWindow()

                with patch.object(window.terminal_service, "open_terminal") as open_terminal:
                    window.open_terminal_in_directory(file_path)

                open_terminal.assert_called_once_with(root)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

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

    def test_core_action_registry_exposes_stable_ids_with_callbacks(self):
        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                window = MainWindow()
                registry = window.action_registry
                # Core vocabulary present with stable ids.
                for action_id in (
                    "nav.back",
                    "nav.forward",
                    "nav.up",
                    "nav.home",
                    "clip.copy",
                    "clip.cut",
                    "clip.paste",
                    "file.rename",
                    "file.delete",
                    "file.trash",
                    "hist.undo",
                    "hist.redo",
                ):
                    self.assertIn(action_id, registry)
                    spec = registry.get(action_id)
                    self.assertIsNotNone(spec.callback, action_id)
                    self.assertTrue(spec.title)
                # Enablement predicates evaluate against a context.
                self.assertTrue(registry.enabled("clip.copy", {"selection_count": 1}))
                self.assertFalse(registry.enabled("clip.copy", {"selection_count": 0}))
                self.assertTrue(registry.enabled("clip.paste", {"clipboard_mode": "copy"}))
                self.assertFalse(registry.enabled("clip.paste", {"clipboard_mode": None}))
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_search_controller_handles_threaded_search(self):
        import time

        from PyQt6.QtWidgets import QApplication

        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                root = Path(tmpdir) / "data"
                root.mkdir()
                for i in range(10):
                    (root / f"informe-{i}.txt").write_text("x", encoding="utf-8")
                for i in range(5):
                    (root / f"foto-{i}.jpg").write_bytes(b"jpeg")

                window = MainWindow()
                window.go_to(root)
                controller = window._search_controller
                self.assertIsNotNone(controller)

                finished = {"ok": False}
                controller.start(
                    "informe",
                    root=root,
                    outcome=SearchOutcome(
                        on_finished=lambda count: finished.update(ok=True, count=count)
                    ),
                )
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and not finished["ok"]:
                    QApplication.processEvents()
                    time.sleep(0.02)
                self.assertTrue(finished["ok"])
                self.assertEqual(finished.get("count"), 10)
                self.assertEqual(len(controller.results), 10)
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file

    def test_registry_enablement_controls_edit_actions(self):
        import time

        from PyQt6.QtWidgets import QApplication

        window = None
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir) / "config"
            config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
            try:
                file_ = Path(tmpdir) / "target.txt"
                file_.write_text("x", encoding="utf-8")

                window = MainWindow()
                # Sin selección ni clipboard: Copy/Cut/Paste deshabilitados.
                window.refresh_registry_enablement()
                self.assertFalse(window.copy_action.isEnabled())
                self.assertFalse(window.cut_action.isEnabled())
                self.assertFalse(window.paste_action.isEnabled())

                # Con selección: Copy/Cut habilitados.
                window.go_to(Path(tmpdir))
                index = window.workspace.model.index(str(file_))
                window.workspace.setCurrentIndex(index)
                QApplication.processEvents()
                self.assertTrue(window.copy_action.isEnabled())
                self.assertTrue(window.cut_action.isEnabled())

                # Tras copiar, Paste se habilita (clipboard interno lleno).
                window.copy_selected()
                self.assertTrue(window.paste_action.isEnabled())
            finally:
                if window is not None:
                    window.close()
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file


if __name__ == "__main__":
    unittest.main()
