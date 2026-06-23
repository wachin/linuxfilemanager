import importlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import lfmapp.core.paths as paths_module
import lfmapp.core.config as config_module
import lfmapp.core.app_data as app_data_module
import lfmapp.services.bookmark_service as bookmark_service_module
import lfmapp.services.tag_service as tag_service_module


class AppDataBootstrapTests(unittest.TestCase):
    def setUp(self):
        self._orig_paths = {
            "CONFIG_DIR": paths_module.CONFIG_DIR,
            "CONFIG_FILE": paths_module.CONFIG_FILE,
            "USER_EXTENSIONS_DIR": paths_module.USER_EXTENSIONS_DIR,
            "VAULT_DIR": paths_module.VAULT_DIR,
        }
        self.temp_dir = Path(tempfile.mkdtemp())

        paths_module.CONFIG_DIR = self.temp_dir
        paths_module.CONFIG_FILE = self.temp_dir / "config.json"
        paths_module.USER_EXTENSIONS_DIR = self.temp_dir / "extensions"
        paths_module.VAULT_DIR = self.temp_dir / "vault"

        importlib.reload(config_module)
        importlib.reload(bookmark_service_module)
        importlib.reload(tag_service_module)
        importlib.reload(app_data_module)

    def tearDown(self):
        for name, value in self._orig_paths.items():
            setattr(paths_module, name, value)
        importlib.reload(config_module)
        importlib.reload(bookmark_service_module)
        importlib.reload(tag_service_module)
        importlib.reload(app_data_module)
        shutil.rmtree(self.temp_dir)

    def test_ensure_app_data_creates_core_files_and_directories(self):
        config = app_data_module.ensure_app_data()

        self.assertIsInstance(config, config_module.Config)
        self.assertTrue(paths_module.CONFIG_FILE.exists())
        self.assertTrue(bookmark_service_module.BOOKMARKS_FILE.exists())
        self.assertTrue(tag_service_module.TAGS_DB_FILE.exists())
        self.assertTrue(paths_module.USER_EXTENSIONS_DIR.is_dir())
        self.assertTrue(paths_module.VAULT_DIR.is_dir())
        self.assertEqual(
            json.loads(bookmark_service_module.BOOKMARKS_FILE.read_text(encoding="utf-8")),
            [],
        )

        conn = sqlite3.connect(str(tag_service_module.TAGS_DB_FILE))
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        finally:
            conn.close()

        self.assertIn("tags", tables)
        self.assertIn("file_tags", tables)

    def test_ensure_app_data_preserves_existing_bookmarks(self):
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        bookmark_service_module.BOOKMARKS_FILE.write_text(
            json.dumps([{"label": "Docs", "path": "/tmp/docs", "pinned": False}]),
            encoding="utf-8",
        )

        app_data_module.ensure_app_data()

        self.assertEqual(
            json.loads(bookmark_service_module.BOOKMARKS_FILE.read_text(encoding="utf-8")),
            [{"label": "Docs", "path": "/tmp/docs", "pinned": False}],
        )


if __name__ == "__main__":
    unittest.main()
