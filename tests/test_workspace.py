import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QApplication

from lfmapp.ui.workspace import IconGridSize
from lfmapp.ui.workspace import ViewMode
from lfmapp.ui.workspace import Workspace


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def test_view_mode_from_string_valid(self):
        self.assertEqual(ViewMode.from_string("icon"), ViewMode.ICON)
        self.assertEqual(ViewMode.from_string("list"), ViewMode.LIST)
        self.assertEqual(ViewMode.from_string("details"), ViewMode.DETAILS)
        self.assertEqual(ViewMode.from_string("compact"), ViewMode.COMPACT)

    def test_view_mode_from_string_invalid(self):
        self.assertEqual(ViewMode.from_string("unknown"), ViewMode.DETAILS)
        self.assertEqual(ViewMode.from_string("", default=ViewMode.LIST), ViewMode.LIST)

    def test_icon_grid_size_from_string(self):
        self.assertEqual(IconGridSize.from_string("small"), IconGridSize.SMALL)
        self.assertEqual(IconGridSize.from_string("large"), IconGridSize.LARGE)
        self.assertEqual(IconGridSize.from_string("unknown"), IconGridSize.MEDIUM)

    def test_icon_grid_size_updates_icon_view_dimensions(self):
        workspace = Workspace()

        workspace.set_view_mode(ViewMode.ICON)
        workspace.set_icon_grid_size(IconGridSize.LARGE)

        self.assertEqual(workspace.icon_grid_size(), IconGridSize.LARGE)
        self.assertEqual(workspace.icon_view.iconSize(), QSize(96, 96))
        self.assertEqual(workspace.icon_view.gridSize(), QSize(132, 132))

    def test_initial_path_sets_workspace_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(initial_path=tmpdir)

            self.assertEqual(workspace.current_path(), Path(tmpdir))

    def test_sort_by_tracks_key_and_order(self):
        workspace = Workspace()

        workspace.sort_by("size", Qt.SortOrder.DescendingOrder)

        self.assertEqual(workspace.sort_key(), "size")
        self.assertEqual(workspace.sort_order(), Qt.SortOrder.DescendingOrder)

        workspace.sort_by("unknown")

        self.assertEqual(workspace.sort_key(), "name")
        self.assertEqual(workspace.sort_order(), Qt.SortOrder.DescendingOrder)

    def test_group_by_tracks_key(self):
        workspace = Workspace()

        workspace.group_by("type")

        self.assertEqual(workspace.group_key(), "type")

        workspace.group_by("unknown")

        self.assertEqual(workspace.group_key(), "none")

    def test_drop_action_control_modifier_copies(self):
        self.assertEqual(
            Workspace.drop_action_for_paths(
                [Path("/does/not/matter")],
                Path("/also/irrelevant"),
                Qt.KeyboardModifier.ControlModifier,
            ),
            "copy",
        )

    def test_drop_action_shift_modifier_moves(self):
        self.assertEqual(
            Workspace.drop_action_for_paths(
                [Path("/does/not/matter")],
                Path("/also/irrelevant"),
                Qt.KeyboardModifier.ShiftModifier,
            ),
            "move",
        )

    def test_drop_action_infers_move_on_same_device(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source.txt"
            source.write_text("data", encoding="utf-8")
            destination = root / "dest"
            destination.mkdir()

            self.assertEqual(
                Workspace.drop_action_for_paths(
                    [source],
                    destination,
                    Qt.KeyboardModifier.NoModifier,
                ),
                "move",
            )

    def test_drop_action_falls_back_to_copy_when_device_check_fails(self):
        self.assertEqual(
            Workspace.drop_action_for_paths(
                [Path("/missing/source")],
                Path("/missing/destination"),
                Qt.KeyboardModifier.NoModifier,
            ),
            "copy",
        )

    def test_workspace_handles_directory_with_10000_files(self):
        file_count = 10000
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for number in range(file_count):
                (root / f"file-{number:05d}.txt").touch()

            workspace = Workspace(initial_path=root)
            root_index = workspace.details_view.rootIndex()
            deadline = time.monotonic() + 10

            while workspace.model.rowCount(root_index) < file_count and time.monotonic() < deadline:
                QApplication.processEvents()

            self.assertEqual(workspace.model.rowCount(root_index), file_count)
            self.assertEqual(workspace.list_view.rootIndex(), root_index)
            self.assertEqual(workspace.icon_view.rootIndex(), root_index)

    def test_details_name_column_keeps_minimum_width(self):
        workspace = Workspace()

        workspace.details_view.setColumnWidth(0, 40)
        workspace._ensure_name_column_width()

        self.assertGreaterEqual(
            workspace.details_view.columnWidth(0),
            workspace.MIN_NAME_COLUMN_WIDTH,
        )


if __name__ == "__main__":
    unittest.main()
