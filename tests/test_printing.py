import tempfile
import unittest
from pathlib import Path

from lfm.ui.main_window import MainWindow


class PrintingTests(unittest.TestCase):
    def test_printable_text_for_text_file_uses_file_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notes.txt"
            path.write_text("hello print", encoding="utf-8")

            printable = MainWindow.printable_text_for_path(path)

        self.assertEqual(printable, "hello print")

    def test_printable_text_for_folder_uses_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            printable = MainWindow.printable_text_for_path(path)

        self.assertIn("Type: Folder", printable)
        self.assertIn("Permissions:", printable)


if __name__ == "__main__":
    unittest.main()
