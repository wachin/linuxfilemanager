"""Tests for the selection controller (Fase 1.1)."""

import tempfile
import unittest
from pathlib import Path

from lfmapp.controllers import SelectionController, SelectionSummary


class SelectionControllerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.folder = self.root / "docs"
        self.folder.mkdir()
        self.small = self.root / "a.txt"
        self.small.write_text("12345", encoding="utf-8")  # 5 bytes
        self.big = self.root / "b.bin"
        self.big.write_bytes(b"\x00" * 1000)  # 1000 bytes
        self.missing = self.root / "gone.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def test_summarize_splits_files_and_folders(self):
        summary = SelectionController.summarize([self.small, self.folder, self.big])
        self.assertIsInstance(summary, SelectionSummary)
        self.assertEqual(summary.count, 3)
        self.assertEqual(summary.file_count, 2)
        self.assertEqual(summary.folder_count, 1)
        self.assertTrue(summary.has_files())
        self.assertTrue(summary.has_folders())

    def test_missing_paths_are_skipped(self):
        summary = SelectionController.summarize([self.missing, self.small])
        self.assertEqual(summary.count, 1)
        self.assertEqual(summary.files, [self.small])

    def test_total_file_size_sums_files_only(self):
        summary = SelectionController.summarize([self.small, self.big, self.folder])
        self.assertEqual(summary.total_file_size(), 1005)

    def test_total_file_size_with_folders_flag(self):
        summary = SelectionController.summarize([self.small])
        # include_folders has no effect when no folders are selected.
        self.assertEqual(summary.total_file_size(include_folders=True), 5)

    def test_vanished_file_does_not_break_total(self):
        path = self.root / "transient.bin"
        path.write_bytes(b"x")
        summary = SelectionController.summarize([path, self.small])
        path.unlink()
        # is_file()/stat inside total_file_size guard with OSError.
        self.assertGreaterEqual(summary.total_file_size(), 5)

    def test_empty_selection_flags(self):
        summary = SelectionController.summarize([self.missing])
        self.assertTrue(summary.is_empty())
        self.assertFalse(summary.has_files())
        self.assertFalse(summary.has_folders())
        self.assertEqual(summary.count, 0)

    def test_convenience_total_file_size(self):
        total = SelectionController.total_file_size_of([self.small, self.folder])
        self.assertEqual(total, 5)


if __name__ == "__main__":
    unittest.main()
