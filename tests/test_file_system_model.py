import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QImage
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

    def test_icon_provider_falls_back_when_theme_has_no_icons(self):
        """On bare themes (e.g. hicolor) the base provider returns null
        icons; the fallback must still return meaningful file-type icons."""
        import lfmapp.ui.icons as icons_module
        from unittest.mock import patch

        from lfmapp.models.file_system_model import FallbackIconProvider

        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "doc.txt").write_text("x")
            (root / "song.mp3").write_bytes(b"\0")
            (root / "subdir").mkdir()
            svg_path = root / "generic.svg"
            svg_path.write_text(svg)

            old_paths = dict(icons_module._ICON_PATH_CACHE)
            old_icons = dict(icons_module._ICON_CACHE)
            try:
                icons_module._ICON_PATH_CACHE.clear()
                icons_module._ICON_CACHE.clear()
                for name in (
                    "folder",
                    "text-x-generic",
                    "audio-x-generic",
                    "application-octet-stream",
                ):
                    icons_module._ICON_PATH_CACHE[name] = svg_path
                provider = FallbackIconProvider()
                with patch.object(
                    QFileIconProvider, "icon", return_value=QIcon()
                ), patch("lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon()):
                    for name in ("doc.txt", "song.mp3", "subdir"):
                        with self.subTest(name=name):
                            from PyQt6.QtCore import QFileInfo

                            icon = provider.icon(QFileInfo(str(root / name)))
                            self.assertFalse(icon.isNull())
            finally:
                icons_module._ICON_PATH_CACHE.clear()
                icons_module._ICON_PATH_CACHE.update(old_paths)
                icons_module._ICON_CACHE.clear()
                icons_module._ICON_CACHE.update(old_icons)

    def test_only_name_column_exposes_decoration_icon(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("sample", encoding="utf-8")

            model = FileSystemModel(root_path=tmpdir)
            name_index = model.index(str(path))
            size_index = name_index.siblingAtColumn(1)
            type_index = name_index.siblingAtColumn(2)

            self.assertIsNotNone(model.data(name_index, Qt.ItemDataRole.DecorationRole))
            self.assertIsNone(model.data(size_index, Qt.ItemDataRole.DecorationRole))
            self.assertIsNone(model.data(type_index, Qt.ItemDataRole.DecorationRole))

    def test_image_files_return_thumbnail_icon_for_name_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.png"
            self._write_png(path)

            model = FileSystemModel(root_path=tmpdir)
            index = model.index(str(path))

            icon = model.data(index, Qt.ItemDataRole.DecorationRole)

            self.assertIsInstance(icon, QIcon)
            self.assertFalse(icon.isNull())

    def test_workspace_thumbnails_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.png"
            self._write_png(path)

            class ConfigStub:
                data = {"preview_show_thumbnails": "never"}

            model = FileSystemModel(root_path=tmpdir, config=ConfigStub())
            index = model.index(str(path))

            icon = model.data(index, Qt.ItemDataRole.DecorationRole)

            self.assertIsNotNone(icon)
            self.assertFalse(icon.isNull())

    @staticmethod
    def _write_png(path: Path):
        image = QImage(16, 12, QImage.Format.Format_ARGB32)
        image.fill(0xFF3399CC)
        if not image.save(str(path), "PNG"):
            raise AssertionError(f"Could not create image fixture at {path}")


if __name__ == "__main__":
    unittest.main()
