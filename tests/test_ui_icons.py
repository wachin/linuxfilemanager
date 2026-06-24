import unittest
from unittest.mock import patch

from PyQt6.QtGui import QIcon

from lfmapp.ui.icons import app_icon, application_icon


class UiIconsTests(unittest.TestCase):
    def test_app_icon_uses_first_available_theme_icon(self):
        with patch("lfmapp.ui.icons.QIcon.fromTheme") as from_theme:
            from_theme.side_effect = [QIcon(), QIcon("second")]

            icon = app_icon("missing", "document-open")

        self.assertFalse(icon.isNull())
        self.assertEqual(from_theme.call_args_list[0].args, ("missing",))
        self.assertEqual(from_theme.call_args_list[1].args, ("document-open",))

    def test_app_icon_returns_empty_icon_when_none_are_available(self):
        with patch("lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon()) as from_theme:
            icon = app_icon("missing-one", "missing-two")

        self.assertTrue(icon.isNull())
        self.assertEqual(from_theme.call_count, 2)

    def test_application_icon_falls_back_to_svg_asset(self):
        with patch("lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon()):
            icon = application_icon()

        self.assertFalse(icon.isNull())


if __name__ == "__main__":
    unittest.main()
