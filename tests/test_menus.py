import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from lfmapp.ui.menus import ContextMenu, ToolbarMenu


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


class MenuSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def test_context_menu_file_actions_emit_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "note.txt"
            path.write_text("hello", encoding="utf-8")
            menu = ContextMenu(path)
            seen = []

            menu.openRequested.connect(lambda emitted: seen.append(("open", emitted)))
            menu.copyRequested.connect(lambda emitted: seen.append(("copy", emitted)))
            menu.propertiesRequested.connect(lambda emitted: seen.append(("properties", emitted)))

            menu._on_open()
            menu._on_copy()
            menu._on_properties()

            self.assertEqual(
                seen,
                [
                    ("open", path),
                    ("copy", path),
                    ("properties", path),
                ],
            )

    def test_context_menu_empty_area_emits_view_and_sort_requests(self):
        menu = ContextMenu()
        view_modes = []
        sort_keys = []
        toggles = []

        menu.viewModeRequested.connect(view_modes.append)
        menu.sortRequested.connect(sort_keys.append)
        menu.toggleHiddenRequested.connect(lambda: toggles.append("hidden"))
        menu.toggleExtensionsRequested.connect(lambda: toggles.append("extensions"))

        menu._on_view_icons()
        menu._on_view_details()
        menu._on_sort_size()
        menu._on_sort_date()
        menu._on_toggle_hidden()
        menu._on_toggle_extensions()

        self.assertEqual(view_modes, ["icon", "details"])
        self.assertEqual(sort_keys, ["size", "modified"])
        self.assertEqual(toggles, ["hidden", "extensions"])

    def test_toolbar_menu_emits_navigation_and_view_requests(self):
        menu = ToolbarMenu()
        events = []
        view_modes = []

        menu.newTabRequested.connect(lambda: events.append("new-tab"))
        menu.closeTabRequested.connect(lambda: events.append("close-tab"))
        menu.backRequested.connect(lambda: events.append("back"))
        menu.homeRequested.connect(lambda: events.append("home"))
        menu.viewModeRequested.connect(view_modes.append)

        menu._on_new_tab()
        menu._on_close_tab()
        menu._on_back()
        menu._on_home()
        menu._on_view_list()

        self.assertEqual(events, ["new-tab", "close-tab", "back", "home"])
        self.assertEqual(view_modes, ["list"])


if __name__ == "__main__":
    unittest.main()
