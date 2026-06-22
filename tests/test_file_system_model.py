import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFileIconProvider

from lfmapp.models.file_system_model import FileSystemModel


class FileSystemModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_selection_checkboxes_track_checked_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("sample", encoding="utf-8")

            model = FileSystemModel()
            model.show_selection_checkboxes = True
            model.setRootPath(tmpdir)
            index = model.index(str(path))

            self.assertEqual(
                model.data(index, Qt.ItemDataRole.CheckStateRole),
                Qt.CheckState.Unchecked,
            )

            self.assertTrue(
                model.setData(
                    index,
                    Qt.CheckState.Checked,
                    Qt.ItemDataRole.CheckStateRole,
                )
            )
            self.assertEqual(model.checked_paths(), [path])
            self.assertEqual(
                model.data(index, Qt.ItemDataRole.CheckStateRole),
                Qt.CheckState.Checked,
            )

            model.clear_checked_paths()
            self.assertEqual(model.checked_paths(), [])

    def test_icon_provider_skips_custom_directory_icons(self):
        model = FileSystemModel()

        self.assertTrue(
            model.iconProvider().options()
            & QFileIconProvider.Option.DontUseCustomDirectoryIcons
        )


if __name__ == "__main__":
    unittest.main()
