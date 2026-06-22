import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from lfm.ui.sidebar import Sidebar


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


class SidebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def test_frequent_folders_are_added_to_quick_access(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            frequent = Path(tmpdir) / "frequent"
            frequent.mkdir()
            sidebar = Sidebar([])

            sidebar.set_frequent_folders([frequent])

            paths = [
                sidebar.quick_list.item(index).data(Qt.ItemDataRole.UserRole)
                for index in range(sidebar.quick_list.count())
            ]
            self.assertIn(str(frequent), paths)

    def test_pinned_bookmarks_are_added_to_quick_access(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pinned = Path(tmpdir) / "pinned"
            unpinned = Path(tmpdir) / "unpinned"
            pinned.mkdir()
            unpinned.mkdir()

            sidebar = Sidebar([
                {"label": "Pinned Folder", "path": str(pinned), "pinned": True},
                {"label": "Unpinned Folder", "path": str(unpinned), "pinned": False},
            ])

            quick_paths = [
                sidebar.quick_list.item(index).data(Qt.ItemDataRole.UserRole)
                for index in range(sidebar.quick_list.count())
            ]
            bookmark_paths = [
                sidebar.bookmark_list.item(index).data(Qt.ItemDataRole.UserRole)
                for index in range(sidebar.bookmark_list.count())
            ]

            self.assertIn(str(pinned), quick_paths)
            self.assertNotIn(str(unpinned), quick_paths)
            self.assertIn(str(pinned), bookmark_paths)
            self.assertIn(str(unpinned), bookmark_paths)

    def test_network_discovery_is_deferred_by_default(self):
        with patch("lfm.ui.sidebar.discover_network_locations") as discover:
            sidebar = Sidebar([])

            discover.assert_not_called()
            self.assertEqual(sidebar.network_list.item(0).text(), "Loading network locations...")

    def test_network_discovery_can_run_synchronously_for_tests(self):
        with patch("lfm.ui.sidebar.discover_network_locations", return_value=[Path("/mnt/share")]) as discover:
            sidebar = Sidebar([], lazy_network=False)

            discover.assert_called_once()
            self.assertEqual(sidebar.network_list.item(0).data(Qt.ItemDataRole.UserRole), "/mnt/share")


if __name__ == "__main__":
    unittest.main()
