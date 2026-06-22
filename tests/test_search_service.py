import os
import tempfile
import unittest
from pathlib import Path

from lfm.services.search_service import SearchFilters


class SearchFiltersTests(unittest.TestCase):
    def test_file_type_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image = root / "photo.jpg"
            document = root / "notes.txt"
            folder = root / "folder"
            image.write_text("image", encoding="utf-8")
            document.write_text("document", encoding="utf-8")
            folder.mkdir()

            self.assertTrue(SearchFilters(file_type="image").matches(image))
            self.assertFalse(SearchFilters(file_type="image").matches(document))
            self.assertTrue(SearchFilters(file_type="document").matches(document))
            self.assertTrue(SearchFilters(file_type="folder").matches(folder))
            self.assertFalse(SearchFilters(file_type="file").matches(folder))

    def test_size_filters_apply_to_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.bin"
            path.write_bytes(b"x" * 2048)

            self.assertTrue(SearchFilters(min_size=1024, max_size=4096).matches(path))
            self.assertFalse(SearchFilters(min_size=4096).matches(path))
            self.assertFalse(SearchFilters(max_size=1024).matches(path))

    def test_modified_date_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("sample", encoding="utf-8")
            modified = 1_700_000_000
            os.utime(path, (modified, modified))

            self.assertTrue(SearchFilters(modified_after=modified - 1).matches(path))
            self.assertTrue(SearchFilters(modified_before=modified + 1).matches(path))
            self.assertFalse(SearchFilters(modified_after=modified + 1).matches(path))
            self.assertFalse(SearchFilters(modified_before=modified - 1).matches(path))

    def test_is_active(self):
        self.assertFalse(SearchFilters().is_active())
        self.assertTrue(SearchFilters(file_type="archive").is_active())
        self.assertTrue(SearchFilters(min_size=1).is_active())


if __name__ == "__main__":
    unittest.main()
