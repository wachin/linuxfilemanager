import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPalette
from PyQt6.QtWidgets import QApplication, QWidget

from lfmapp.ui import icons as icons_module


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


class UiIconsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def test_preferred_tabler_variant_uses_light_palette(self):
        widget = QWidget()
        palette = widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("white"))
        widget.setPalette(palette)

        self.assertEqual(icons_module.preferred_tabler_variant(widget), "outline")

    def test_preferred_tabler_variant_uses_dark_palette(self):
        widget = QWidget()
        palette = widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("black"))
        widget.setPalette(palette)

        self.assertEqual(icons_module.preferred_tabler_variant(widget), "filled")

    def test_tabler_icon_path_prefers_requested_variant_and_falls_back(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "outline").mkdir()
            (root / "filled").mkdir()
            outline = root / "outline" / "folder.svg"
            filled = root / "filled" / "folder.svg"
            outline.write_text("<svg outline/>", encoding="utf-8")
            filled.write_text("<svg filled/>", encoding="utf-8")

            with patch.object(icons_module, "TABLER_ICONS_DIR", root):
                self.assertEqual(
                    icons_module.tabler_icon_path("folder", variant="filled"),
                    filled,
                )
                self.assertEqual(
                    icons_module.tabler_icon_path("folder", variant="outline"),
                    outline,
                )

    def test_app_icon_uses_shipped_tabler_asset_before_theme_fallback(self):
        icon = icons_module.app_icon("folder")

        self.assertFalse(icon.isNull())

    def test_app_icon_falls_back_to_theme_when_no_shipped_icon_exists(self):
        with patch.object(icons_module.QIcon, "fromTheme", return_value=QIcon()) as from_theme:
            icon = icons_module.app_icon(None, "document-open")

        self.assertTrue(icon.isNull())
        from_theme.assert_called_once_with("document-open")


if __name__ == "__main__":
    unittest.main()
