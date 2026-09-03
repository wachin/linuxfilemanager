"""Tests for the observable app state model (Fase 1.3)."""

import tempfile
import unittest
from pathlib import Path

from lfmapp.controllers import AppState, classify_location


class AppStateTests(unittest.TestCase):
    def test_path_setter_normalizes_and_notifies(self):
        state = AppState()
        seen = []
        state.subscribe("path", lambda key: seen.append(key))
        state.set_path("~/sub dir")
        self.assertEqual(state.path, Path("~/sub dir").expanduser())
        self.assertEqual(seen, ["path"])

    def test_setting_same_path_does_not_notify(self):
        state = AppState()
        state.set_path(Path.home())
        seen = []
        state.subscribe("path", lambda key: seen.append(key))
        state.set_path(Path.home())
        self.assertEqual(seen, [])

    def test_selection_summary_derived_on_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "docs"
            folder.mkdir()
            f1 = root / "a.txt"
            f1.write_text("hello", encoding="utf-8")
            state = AppState()
            state.set_selection_paths([f1, folder, root / "missing.bin"])
            self.assertEqual(state.selection_count, 2)
            self.assertEqual(state.selection.file_count, 1)
            self.assertEqual(state.selection.folder_count, 1)
            self.assertEqual(state.selection.total_file_size(), 5)

    def test_view_mode_roundtrip(self):
        state = AppState()
        seen = []
        state.subscribe("view_mode", lambda key: seen.append(key))
        state.set_view_mode("icons")
        self.assertEqual(state.view_mode, "icons")
        self.assertEqual(seen, ["view_mode"])
        state.set_view_mode("icons")  # no change -> no notify
        self.assertEqual(len(seen), 1)

    def test_search_state(self):
        state = AppState()
        search_seen = []
        result_seen = []
        state.subscribe("searching", lambda key: search_seen.append(key))
        state.subscribe("search_results", lambda key: result_seen.append(key))
        state.set_searching(True, result_count=12)
        self.assertTrue(state.searching)
        self.assertEqual(state.search_result_count, 12)
        self.assertIn("searching", search_seen)
        self.assertIn("search_results", result_seen)

    def test_operations_counter(self):
        state = AppState()
        seen = []
        state.subscribe("operations", lambda key: seen.append(key))
        state.operation_started()
        state.operation_started()
        self.assertEqual(state.busy_operations, 2)
        state.operation_finished()
        self.assertEqual(state.busy_operations, 1)
        # Never below zero.
        state.operation_finished()
        state.operation_finished()
        self.assertEqual(state.busy_operations, 0)

    def test_unsubscribe_stops_notifications(self):
        state = AppState()
        seen = []
        listener = lambda key: seen.append(key)
        state.subscribe("path", listener)
        state.unsubscribe("path", listener)
        state.set_path(Path.home() / "x")
        self.assertEqual(seen, [])


class ClassifyLocationTests(unittest.TestCase):
    def test_home_and_xdg_dirs(self):
        home = Path.home()
        self.assertEqual(classify_location(home, home).scheme, "home")
        # A path inside home is filesystem-typed but still a real folder.
        inside = home / "Documents"
        self.assertEqual(classify_location(inside, home).scheme, "filesystem")
        self.assertIsNone(classify_location(None, home).path)
        self.assertEqual(classify_location(None, home).scheme, "this-computer")


if __name__ == "__main__":
    unittest.main()
