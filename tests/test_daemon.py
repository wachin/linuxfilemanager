import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from lfm.daemon import FileManagerDaemon, main
from lfm.services.textindex_service import TextIndexService


class DummyConfig:
    def __init__(self, bookmarks, text_index_enabled):
        self._bookmarks = bookmarks
        self._text_index_enabled = text_index_enabled

    @property
    def bookmarks(self):
        return self._bookmarks

    @property
    def text_index_enabled(self):
        return self._text_index_enabled


class FileManagerDaemonTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.folder = self.temp_dir / "folder"
        self.folder.mkdir()
        self.db_path = self.temp_dir / "text_index.db"

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_run_once_does_nothing_when_text_index_is_disabled(self):
        config = DummyConfig([str(self.folder)], text_index_enabled=False)
        daemon = FileManagerDaemon(config=config)

        result = daemon.run_once()

        self.assertFalse(result.text_index_enabled)
        self.assertEqual(result.indexed_folders, 0)
        self.assertEqual(result.indexed_files, 0)

    def test_run_once_indexes_configured_folders_when_enabled(self):
        (self.folder / "Report.txt").write_text("content", encoding="utf-8")
        missing = self.temp_dir / "missing"
        config = DummyConfig(
            [str(self.folder), str(self.folder), str(missing)],
            text_index_enabled=True,
        )
        service = TextIndexService(self.db_path)
        daemon = FileManagerDaemon(config=config, text_index_service=service)
        try:
            result = daemon.run_once(recursive=True)
            matches = service.search("report", self.folder)
        finally:
            daemon.close()
            service.close()

        self.assertTrue(result.text_index_enabled)
        self.assertEqual(result.indexed_folders, 1)
        self.assertEqual(result.indexed_files, 1)
        self.assertEqual(result.skipped_folders, 1)
        self.assertEqual(matches, [str(self.folder / "Report.txt")])

    def test_main_once_accepts_explicit_path(self):
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(
                ["--once", "--path", str(self.folder), "--no-recursive", "--limit", "10"]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("text_index_enabled=false", output.getvalue())


if __name__ == "__main__":
    unittest.main()
