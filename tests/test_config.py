import importlib
import shutil
import tempfile
import unittest
from pathlib import Path

import lfm.core.paths as paths_module
import lfm.core.config as config_module


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._orig_config_dir = paths_module.CONFIG_DIR
        self._orig_config_file = paths_module.CONFIG_FILE

        self.temp_dir = Path(tempfile.mkdtemp())
        paths_module.CONFIG_DIR = self.temp_dir
        paths_module.CONFIG_FILE = self.temp_dir / "config.json"

        importlib.reload(config_module)

    def tearDown(self):
        paths_module.CONFIG_DIR = self._orig_config_dir
        paths_module.CONFIG_FILE = self._orig_config_file
        importlib.reload(config_module)
        shutil.rmtree(self.temp_dir)

    def test_set_and_get_folder_view(self):
        cfg = config_module.Config()
        self.assertTrue(cfg.remember_folder_view)
        self.assertIsNone(cfg.get_folder_view("/tmp/example"))

        cfg.set_folder_view("/tmp/example", "list")
        self.assertEqual(cfg.get_folder_view("/tmp/example"), "list")

    def test_remember_folder_view_toggle_persists(self):
        cfg = config_module.Config()
        cfg.set_remember_folder_view(False)

        cfg2 = config_module.Config()
        self.assertFalse(cfg2.remember_folder_view)

        cfg2.set_folder_view("/tmp/another", "details")
        self.assertEqual(cfg2.get_folder_view("/tmp/another"), "details")

    def test_clear_folder_view(self):
        cfg = config_module.Config()
        cfg.set_folder_view("/tmp/example", "list")
        self.assertEqual(cfg.get_folder_view("/tmp/example"), "list")
        cfg.clear_folder_view("/tmp/example")
        self.assertIsNone(cfg.get_folder_view("/tmp/example"))

    def test_clear_all_folder_views(self):
        cfg = config_module.Config()
        cfg.set_folder_view("/tmp/one", "icon")
        cfg.set_folder_view("/tmp/two", "compact")
        cfg.clear_all_folder_views()
        self.assertIsNone(cfg.get_folder_view("/tmp/one"))
        self.assertIsNone(cfg.get_folder_view("/tmp/two"))

    def test_sidebar_and_preview_visibility_persist(self):
        cfg = config_module.Config()
        cfg.set_sidebar_visible(False)
        cfg.set_preview_visible(False)

        cfg2 = config_module.Config()
        self.assertFalse(cfg2.sidebar_visible)
        self.assertFalse(cfg2.preview_visible)

    def test_sidebar_and_preview_visibility_defaults(self):
        cfg = config_module.Config()
        self.assertTrue(cfg.sidebar_visible)
        self.assertTrue(cfg.preview_visible)

    def test_selection_checkboxes_persist(self):
        cfg = config_module.Config()
        self.assertFalse(cfg.selection_checkboxes)
        cfg.set_selection_checkboxes(True)

        cfg2 = config_module.Config()
        self.assertTrue(cfg2.selection_checkboxes)

    def test_view_visibility_options_persist(self):
        cfg = config_module.Config()
        self.assertTrue(cfg.show_hidden_files)
        self.assertTrue(cfg.show_file_extensions)
        cfg.set_show_hidden_files(False)
        cfg.set_show_file_extensions(False)

        cfg2 = config_module.Config()
        self.assertFalse(cfg2.show_hidden_files)
        self.assertFalse(cfg2.show_file_extensions)

    def test_icon_grid_size_persists(self):
        cfg = config_module.Config()
        self.assertEqual(cfg.icon_grid_size, "medium")
        cfg.set_icon_grid_size("large")

        cfg2 = config_module.Config()
        self.assertEqual(cfg2.icon_grid_size, "large")

    def test_extension_settings_default_to_disabled_and_persist(self):
        cfg = config_module.Config()
        self.assertFalse(cfg.extensions_enabled)
        self.assertEqual(cfg.enabled_extensions, [])

        cfg.set_extensions_enabled(True)
        cfg.set_extension_enabled("example.extension", True)

        cfg2 = config_module.Config()
        self.assertTrue(cfg2.extensions_enabled)
        self.assertEqual(cfg2.enabled_extensions, ["example.extension"])

        cfg2.set_extension_enabled("example.extension", False)
        cfg3 = config_module.Config()
        self.assertEqual(cfg3.enabled_extensions, [])

    def test_text_index_disabled_by_default(self):
        cfg = config_module.Config()

        self.assertFalse(cfg.text_index_enabled)

    def test_recent_files_persist_and_dedupe(self):
        cfg = config_module.Config()
        cfg.add_recent_file("/tmp/one.txt")
        cfg.add_recent_file("/tmp/two.txt")
        cfg.add_recent_file("/tmp/one.txt")

        cfg2 = config_module.Config()
        self.assertEqual(cfg2.recent_files[:2], ["/tmp/one.txt", "/tmp/two.txt"])

    def test_recent_files_limit_and_clear(self):
        cfg = config_module.Config()
        for index in range(12):
            cfg.add_recent_file(f"/tmp/{index}.txt", max_items=10)

        self.assertEqual(len(cfg.recent_files), 10)
        self.assertEqual(cfg.recent_files[0], "/tmp/11.txt")
        self.assertEqual(cfg.recent_files[-1], "/tmp/2.txt")

        cfg.clear_recent_files()
        self.assertEqual(cfg.recent_files, [])

    def test_frequent_folders_rank_by_visit_count(self):
        cfg = config_module.Config()
        cfg.add_folder_visit("/tmp/b")
        cfg.add_folder_visit("/tmp/a")
        cfg.add_folder_visit("/tmp/b")

        cfg2 = config_module.Config()
        self.assertEqual(cfg2.frequent_folders(), ["/tmp/b", "/tmp/a"])

        cfg2.clear_frequent_folders()
        self.assertEqual(cfg2.frequent_folders(), [])

    def test_terminal_and_font_preferences_persist(self):
        cfg = config_module.Config()
        cfg.set_preferred_terminal("konsole")
        cfg.set_ui_font_family("DejaVu Sans")
        cfg.set_ui_font_size(12)
        cfg.set_ui_font_weight(700)
        cfg.set_ui_font_italic(True)

        cfg2 = config_module.Config()
        self.assertEqual(cfg2.preferred_terminal, "konsole")
        self.assertEqual(cfg2.ui_font_family, "DejaVu Sans")
        self.assertEqual(cfg2.ui_font_size, 12)
        self.assertEqual(cfg2.ui_font_weight, 700)
        self.assertTrue(cfg2.ui_font_italic)


if __name__ == "__main__":
    unittest.main()
