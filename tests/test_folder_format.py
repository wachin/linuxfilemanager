"""Tests for per-folder visual persistence (folder format) — backlog P2.

Covers:
- Config store: save/load/clear folder formats (versioned dict).
- ViewController: snapshot + restore, parent inheritance, ignore flag,
  sanitization of corrupt/foreign entries, legacy view-store sync.
- Workspace: column restore on navigation + no re-save during restore.
- GUI (MainWindow): changing sort/group/grid persists and is restored on
  navigation back to the folder; ignored folders keep global defaults.
"""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

import lfmapp.core.config as config_module
from lfmapp.controllers.view_controller import ViewController, FORMAT_VERSION
from lfmapp.ui.workspace import IconGridSize, ViewMode
from lfmapp.ui.main_window import MainWindow


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


class FakeConfig:
    """In-memory config exposing the folder-view/format API used here."""

    def __init__(self):
        self._remember = True
        self._views = {}
        self._formats = {}
        self.data = {"ignore_per_folder_view_preferences": False}

    def remember_folder_view(self) -> bool:
        return self._remember

    def set_remember_folder_view(self, value: bool):
        self._remember = bool(value)

    def get_folder_view(self, path: str) -> str | None:
        return self._views.get(path)

    def set_folder_view(self, path: str | None, view: str):
        if path:
            self._views[path] = view

    def clear_folder_view(self, path: str | None):
        self._views.pop(path, None)

    def clear_all_folder_views(self):
        self._views.clear()

    # folder-format API (mirrors lfmapp.core.config.Config)
    folder_format_inherit_from_parent = True

    def get_folder_format(self, path: str) -> dict | None:
        return self._formats.get(path)

    def set_folder_format(self, path: str | None, fmt: dict | None):
        if path is None:
            return
        if fmt is None:
            self._formats.pop(path, None)
        else:
            self._formats[path] = dict(fmt)

    def clear_folder_format(self, path: str | None):
        if path:
            self._formats.pop(path, None)

    def clear_all_folder_formats(self):
        self._formats.clear()


class FolderFormatConfigTests(unittest.TestCase):
    def setUp(self):
        self._orig_config_dir = config_module.CONFIG_DIR
        self._orig_config_file = config_module.CONFIG_FILE
        self.temp_dir = Path(tempfile.mkdtemp())
        config_module.CONFIG_DIR = self.temp_dir
        config_module.CONFIG_FILE = self.temp_dir / "config.json"

    def tearDown(self):
        config_module.CONFIG_DIR = self._orig_config_dir
        config_module.CONFIG_FILE = self._orig_config_file
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_folder_format_roundtrip(self):
        cfg = config_module.Config()
        fmt = {"version": FORMAT_VERSION, "view": "icon", "sort": "size"}
        cfg.set_folder_format("/tmp/x", fmt)
        loaded = cfg.get_folder_format("/tmp/x")
        self.assertEqual(loaded["view"], "icon")
        self.assertEqual(loaded["sort"], "size")

    def test_folder_format_clear_and_clear_all(self):
        cfg = config_module.Config()
        cfg.set_folder_format("/tmp/x", {"version": FORMAT_VERSION, "view": "list"})
        cfg.set_folder_format("/tmp/y", {"version": FORMAT_VERSION, "view": "icon"})
        cfg.clear_folder_format("/tmp/x")
        self.assertIsNone(cfg.get_folder_format("/tmp/x"))
        cfg.clear_all_folder_formats()
        self.assertIsNone(cfg.get_folder_format("/tmp/y"))

    def test_folder_format_rejects_wrong_version(self):
        cfg = config_module.Config()
        cfg.set_folder_format("/tmp/x", {"version": 99, "view": "icon"})
        self.assertIsNone(cfg.get_folder_format("/tmp/x"))

    def test_folder_format_inherit_flag_persists(self):
        cfg = config_module.Config()
        self.assertTrue(cfg.folder_format_inherit_from_parent)
        cfg.set_folder_format_inherit_from_parent(False)
        cfg2 = config_module.Config()
        self.assertFalse(cfg2.folder_format_inherit_from_parent)


class FolderFormatControllerTests(unittest.TestCase):
    def setUp(self):
        self.config = FakeConfig()
        self.controller = ViewController(self.config)

    def test_remember_and_restore_format(self):
        path = Path("/tmp/example")
        self.controller.remember_format(path, ViewMode.ICON, "size", "type", "large")
        fmt = self.controller.format_to_restore(path)
        self.assertEqual(fmt["view"], "icon")
        self.assertEqual(fmt["sort"], "size")
        self.assertEqual(fmt["group"], "type")
        self.assertEqual(fmt["grid"], "large")
        # Legacy view store stays in sync.
        self.assertEqual(self.config.get_folder_view(str(path)), "icon")

    def test_disabled_remember_stores_nothing(self):
        self.controller.set_enabled(False)
        path = Path("/tmp/example")
        self.controller.remember_format(path, ViewMode.ICON, "size", "none", "large")
        self.assertIsNone(self.controller.format_to_restore(path))
        self.assertEqual(self.config._formats, {})

    def test_ignore_per_folder_preferences_disables_everything(self):
        self.config.data["ignore_per_folder_view_preferences"] = True
        path = Path("/tmp/example")
        self.controller.remember_format(path, ViewMode.ICON, "size", "none", "large")
        self.assertIsNone(self.controller.format_to_restore(path))

    def test_inherits_closest_ancestor_format(self):
        parent = Path("/tmp/project")
        child = Path("/tmp/project/sub/leaf")
        self.controller.remember_format(parent, ViewMode.ICON, "size", "none", "large")
        fmt = self.controller.format_to_restore(child)
        self.assertIsNotNone(fmt)
        self.assertEqual(fmt["view"], "icon")

    def test_inheritance_can_be_turned_off(self):
        self.config.folder_format_inherit_from_parent = False
        parent = Path("/tmp/project")
        child = Path("/tmp/project/sub/leaf")
        self.controller.remember_format(parent, ViewMode.ICON, "size", "none", "large")
        self.assertIsNone(self.controller.format_to_restore(child))

    def test_sanitize_drops_unknown_keys_and_corrupt_entries(self):
        self.assertIsNone(ViewController.sanitize_format(None))
        self.assertIsNone(ViewController.sanitize_format({"version": 7}))
        self.assertIsNone(ViewController.sanitize_format("nonsense"))
        clean = ViewController.sanitize_format(
            {"version": FORMAT_VERSION, "view": "bogus", "sort": "size", "extra": 1}
        )
        self.assertEqual(clean, {"version": FORMAT_VERSION, "sort": "size"})

    def test_clear_removes_both_stores(self):
        path = Path("/tmp/example")
        self.controller.remember_format(path, ViewMode.ICON, "size", "none", "large")
        self.controller.clear(path)
        self.assertIsNone(self.controller.format_to_restore(path))
        self.assertEqual(self.config._views, {})

    def test_clear_all_removes_both_stores(self):
        self.controller.remember_format(Path("/tmp/a"), ViewMode.ICON, "size", "none", "small")
        self.controller.remember_format(Path("/tmp/b"), ViewMode.LIST, "name", "type", "medium")
        self.controller.clear_all()
        self.assertEqual(self.config._formats, {})
        self.assertEqual(self.config._views, {})


class FolderFormatGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def setUp(self):
        import shutil

        self._orig_config_dir = config_module.CONFIG_DIR
        self._orig_config_file = config_module.CONFIG_FILE
        self.temp_dir = Path(tempfile.mkdtemp())
        config_module.CONFIG_DIR = self.temp_dir / "config"
        config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
        config_module.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._shutil = shutil

        self.root = Path(tempfile.mkdtemp(prefix="lfm_tree_"))
        self.a = self.root / "alpha"
        self.b = self.root / "beta"
        self.a.mkdir()
        self.b.mkdir()
        (self.a / "one.txt").write_text("x", encoding="utf-8")
        (self.b / "two.txt").write_text("y", encoding="utf-8")

    def tearDown(self):
        config_module.CONFIG_DIR = self._orig_config_dir
        config_module.CONFIG_FILE = self._orig_config_file
        self._shutil.rmtree(self.temp_dir, ignore_errors=True)
        self._shutil.rmtree(self.root, ignore_errors=True)

    def _window(self) -> MainWindow:
        window = MainWindow()
        self.addCleanup(window.close)
        return window

    def test_sort_group_grid_persist_and_restore_on_navigation(self):
        window = self._window()
        window.go_to(self.a)
        window.set_icon_grid_size(IconGridSize.LARGE)
        window.set_sort("size", Qt.SortOrder.DescendingOrder)
        # Snapshot what alpha remembers.
        fmt = window.view_controller.format_to_restore(self.a)
        self.assertEqual(fmt["sort"], "size")
        self.assertEqual(fmt["grid"], "large")

        # In beta (no saved format) the user changes the presentation.
        window.go_to(self.b)
        window.set_sort("name", Qt.SortOrder.AscendingOrder)
        window.set_icon_grid_size(IconGridSize.SMALL)
        self.assertEqual(window.workspace.sort_key(), "name")
        self.assertEqual(window.workspace.icon_grid_size(), IconGridSize.SMALL)

        # Back in alpha the remembered format is restored.
        window.go_to(self.a)
        self.assertEqual(window.workspace.sort_key(), "size")
        self.assertEqual(window.workspace.icon_grid_size(), IconGridSize.LARGE)

    def test_menu_checkmarks_follow_restore(self):
        window = self._window()
        window.go_to(self.a)
        window.set_sort("size", Qt.SortOrder.DescendingOrder)
        window.go_to(self.b)
        # beta has no saved format: the restored presentation is whatever alpha
        # left active (it is the live workspace), and the menus agree with it.
        for key, action in window._sort_column_actions.items():
            self.assertEqual(action.isChecked(), key == window.workspace.sort_key())

    def test_clear_all_resets_everything(self):
        window = self._window()
        window.go_to(self.a)
        window.set_sort("size", Qt.SortOrder.DescendingOrder)
        window.clear_all_folder_views()
        self.assertEqual(config_module.Config().data["folder_formats"], {})
        self.assertEqual(config_module.Config().data["folder_views"], {})

    def test_clear_current_folder_only(self):
        window = self._window()
        window.go_to(self.a)
        window.set_sort("size", Qt.SortOrder.DescendingOrder)
        window.go_to(self.b)
        window.set_sort("type", Qt.SortOrder.AscendingOrder)
        window.clear_current_folder_view()
        cfg = config_module.Config()
        self.assertIsNone(cfg.get_folder_format(str(self.b)))
        fmt = cfg.get_folder_format(str(self.a))
        self.assertIsNotNone(fmt)
        self.assertEqual(fmt["sort"], "size")

    def test_ignore_per_folder_preferences_keeps_live_state(self):
        window = self._window()
        window.config.data["ignore_per_folder_view_preferences"] = True
        window.go_to(self.a)
        window.set_sort("size", Qt.SortOrder.DescendingOrder)
        window.go_to(self.b)
        window.set_sort("name", Qt.SortOrder.AscendingOrder)
        # No format was stored for alpha (ignored), so beta keeps live state.
        self.assertEqual(config_module.Config().data["folder_formats"], {})
        self.assertEqual(window.workspace.sort_key(), "name")

    def test_columns_restore_on_navigation(self):
        window = self._window()
        window.go_to(self.a)
        owner_column = window.workspace.model.COLUMN_KEYS.index("owner")
        folder_map = dict(window.config.data.get("list_columns_by_folder", {}))
        folder_map[str(self.a)] = {
            "visible": ["name", "size", "type", "modified", "owner"],
            "order": ["name", "owner", "size", "type", "modified"],
            "widths": {},
        }
        window.config.data["list_columns_by_folder"] = folder_map
        window.config.save()

        window.go_to(self.b)
        self.assertTrue(window.workspace.details_view.isColumnHidden(owner_column))
        window.go_to(self.a)
        self.assertFalse(window.workspace.details_view.isColumnHidden(owner_column))


if __name__ == "__main__":
    unittest.main()
