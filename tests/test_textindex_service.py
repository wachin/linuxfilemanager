import shutil
import tempfile
import unittest
from pathlib import Path

from lfmapp.services.textindex_service import TextIndexService


class TextIndexServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "index" / "text_index.db"
        self.folder = self.temp_dir / "folder"
        self.folder.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_index_folder_creates_database_lazily_at_given_path(self):
        service = TextIndexService(self.db_path)
        try:
            self.assertTrue(self.db_path.exists())
        finally:
            service.close()

    def test_index_folder_and_search_by_name(self):
        (self.folder / "Report.txt").write_text("content", encoding="utf-8")
        (self.folder / "notes.md").write_text("content", encoding="utf-8")

        service = TextIndexService(self.db_path)
        try:
            count = service.index_folder(self.folder, recursive=True)
            results = service.search("report", self.folder)
        finally:
            service.close()

        self.assertEqual(count, 2)
        self.assertEqual(results, [str(self.folder / "Report.txt")])

    def test_index_folder_respects_recursive_flag(self):
        nested = self.folder / "nested"
        nested.mkdir()
        (nested / "deep.txt").write_text("content", encoding="utf-8")
        (self.folder / "top.txt").write_text("content", encoding="utf-8")

        service = TextIndexService(self.db_path)
        try:
            count = service.index_folder(self.folder, recursive=False)
            results = service.search("txt", self.folder)
        finally:
            service.close()

        self.assertEqual(count, 1)
        self.assertEqual(results, [str(self.folder / "top.txt")])

    def test_clear_index_for_folder(self):
        other_folder = self.temp_dir / "other"
        other_folder.mkdir()
        (self.folder / "one.txt").write_text("content", encoding="utf-8")
        (other_folder / "two.txt").write_text("content", encoding="utf-8")

        service = TextIndexService(self.db_path)
        try:
            service.index_folder(self.folder)
            service.index_folder(other_folder)
            deleted = service.clear_index(self.folder)
            folder_results = service.search("txt", self.folder)
            all_results = service.search("txt")
        finally:
            service.close()

        self.assertEqual(deleted, 1)
        self.assertEqual(folder_results, [])
        self.assertEqual(all_results, [str(other_folder / "two.txt")])


if __name__ == "__main__":
    unittest.main()
