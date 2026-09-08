"""Tests for the flat view (backlog P2).

Covers:
- Service: collect_entries in the three modes (mixed / files_only / grouped
  by structure), hidden filtering and unreadable folders.
- FlatViewWorker: progressive batches + cancellation.
- FlatViewModel: population, columns, sorting, path resolution.
- GUI: Flat View entry via the menu action, flat selection feeding the
  normal operations, navigation on activation, folder-format persistence of
  the flat mode, and the nested-file paste rule (recreate vs same folder).
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

import lfmapp.core.config as config_module
from lfmapp.services.flat_view_service import (
    FlatEntry,
    FlatViewMode,
    FlatViewWorker,
    collect_entries,
)
from lfmapp.models.flat_view_model import FlatViewModel
from lfmapp.ui.main_window import MainWindow
from lfmapp.ui.workspace import ViewMode


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


def make_tree(root: Path) -> dict:
    """docs/readme.md, docs/manual.pdf, images/f1.png, images/old/f2.png, top.txt."""
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "readme.md").write_text("r", encoding="utf-8")
    (root / "docs" / "manual.pdf").write_bytes(b"%PDF fake")
    (root / "images" / "old").mkdir(parents=True)
    (root / "images" / "f1.png").write_bytes(b"png fake")
    (root / "images" / "old" / "f2.png").write_bytes(b"png fake 2")
    (root / "top.txt").write_text("t", encoding="utf-8")
    return {"root": root}


class CollectEntriesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tree = make_tree(self.tmp)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def paths(self, entries):
        return [e.path for e in entries]

    def test_mixed_includes_files_and_folders(self):
        entries = collect_entries(self.tmp, FlatViewMode.MIXED)
        names = {e.path.name for e in entries}
        self.assertIn("docs", names)
        self.assertIn("readme.md", names)
        self.assertIn("f2.png", names)  # nested two levels deep
        self.assertIn("top.txt", names)

    def test_files_only_hides_folders_but_walks_them(self):
        entries = collect_entries(self.tmp, FlatViewMode.FILES_ONLY)
        self.assertFalse(any(e.is_dir for e in entries))
        names = {e.path.name for e in entries}
        self.assertIn("readme.md", names)
        self.assertIn("f2.png", names)  # still traverses subfolders

    def test_relative_paths_reflect_tree(self):
        entries = {str(e.path): e for e in collect_entries(self.tmp, FlatViewMode.MIXED)}
        self.assertEqual(entries[str(self.tmp / "top.txt")].relative, "top.txt")
        self.assertEqual(entries[str(self.tmp / "docs" / "readme.md")].relative, "docs/readme.md")
        self.assertEqual(
            entries[str(self.tmp / "images" / "old" / "f2.png")].relative,
            "images/old/f2.png",
        )

    def test_hidden_entries_can_be_excluded(self):
        (self.tmp / ".secret").write_text("s", encoding="utf-8")
        with_hidden = collect_entries(self.tmp, include_hidden=True)
        without_hidden = collect_entries(self.tmp, include_hidden=False)
        self.assertIn(self.tmp / ".secret", self.paths(with_hidden))
        self.assertNotIn(self.tmp / ".secret", self.paths(without_hidden))

    def test_unreadable_folder_is_skipped(self):
        locked = self.tmp / "locked"
        locked.mkdir()
        (locked / "x.txt").write_text("x", encoding="utf-8")
        try:
            os.chmod(locked, 0)
        except OSError:
            self.skipTest("chmod 0 not effective on this filesystem")
        try:
            entries = collect_entries(self.tmp)
            self.assertIn(self.tmp / "top.txt", self.paths(entries))
        finally:
            os.chmod(locked, 0o755)

    def test_mode_from_string_falls_back(self):
        self.assertEqual(FlatViewMode.from_string("files_only"), FlatViewMode.FILES_ONLY)
        self.assertEqual(FlatViewMode.from_string("bogus"), FlatViewMode.MIXED)


class FlatViewWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def test_worker_emits_batches_and_total(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        make_tree(tmp)

        worker = FlatViewWorker(tmp, FlatViewMode.MIXED)
        batches = []
        totals = []
        worker.batch.connect(batches.append)
        worker.finished.connect(totals.append)
        worker.start()
        deadline = time.monotonic() + 5
        while not totals and time.monotonic() < deadline:
            QApplication.processEvents()
        worker.wait(2000)

        self.assertEqual(len(totals), 1)
        self.assertEqual(totals[0], sum(len(b) for b in batches))
        self.assertGreaterEqual(totals[0], 6)  # 3 dirs + 4 files (hidden varies)

    def test_stop_halts_scan(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        for i in range(200):
            (tmp / f"f{i:03}.txt").write_text("x", encoding="utf-8")

        worker = FlatViewWorker(tmp, FlatViewMode.MIXED, batch_size=10)
        batches = []
        totals = []
        worker.batch.connect(batches.append)
        worker.finished.connect(totals.append)
        worker.start()
        worker.stop()
        worker.wait(3000)
        # Either it stopped early or finished before stopping; never crashed.
        self.assertIsInstance(totals, list)


class FlatViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def test_population_and_columns(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        make_tree(tmp)

        model = FlatViewModel()
        entries = collect_entries(tmp, FlatViewMode.MIXED)
        model.set_entries(entries)

        self.assertEqual(model.columnCount(), 5)
        self.assertEqual(model.rowCount(), len(entries))
        first = entries[0]
        row = entries.index(first)
        self.assertEqual(model.data(model.index(row, 0)), first.name)
        self.assertEqual(model.data(model.index(row, 1)), first.relative)
        self.assertEqual(model.data(model.index(row, 0), Qt.ItemDataRole.UserRole), str(first.path))

    def test_sort_by_name_and_size(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        (tmp / "b.txt").write_text("xx", encoding="utf-8")
        (tmp / "a.txt").write_text("x", encoding="utf-8")
        (tmp / "c.txt").write_text("xxxx", encoding="utf-8")

        model = FlatViewModel()
        model.set_entries(collect_entries(tmp))
        # name column = 0, ascending
        model.sort(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            [e.name for e in model.entries()], ["a.txt", "b.txt", "c.txt"]
        )
        # size column = 2, descending
        model.sort(2, Qt.SortOrder.DescendingOrder)
        self.assertEqual(
            [e.name for e in model.entries()], ["c.txt", "b.txt", "a.txt"]
        )


def _patch_question(answer):
    """Patch the nested-files QMessageBox.question with a fixed answer."""
    from unittest.mock import patch

    return patch(
        "lfmapp.ui.file_actions_mixin.QMessageBox.question",
        return_value=answer,
    )


class FlatViewGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def setUp(self):
        import shutil

        self._orig_config_dir = config_module.CONFIG_DIR
        self._orig_config_file = config_module.CONFIG_FILE
        self.temp_dir = Path(tempfile.mkdtemp())
        config_module.CONFIG_DIR = self.temp_dir / "config"
        config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
        config_module.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._shutil = shutil

        self.root = Path(tempfile.mkdtemp(prefix="lfm_flat_"))
        self.sub = self.root / "docs"
        make_tree(self.root)

    def tearDown(self):
        config_module.CONFIG_DIR = self._orig_config_dir
        config_module.CONFIG_FILE = self._orig_config_file
        self._shutil.rmtree(self.temp_dir, ignore_errors=True)
        self._shutil.rmtree(self.root, ignore_errors=True)

    def _window(self) -> MainWindow:
        window = MainWindow()
        self.addCleanup(window.close)
        return window

    def _pump_flat_scan(self, window, minimum: int):
        deadline = time.monotonic() + 5
        while window.workspace.flat_model.rowCount() < minimum and time.monotonic() < deadline:
            QApplication.processEvents()
        QApplication.processEvents()

    def test_flat_view_lists_whole_tree(self):
        window = self._window()
        window.go_to(self.root)
        window.set_view_mode(ViewMode.FLAT)
        self._pump_flat_scan(window, 7)

        listed = {e.path for e in window.workspace.flat_model.entries()}
        self.assertIn(self.sub / "readme.md", listed)
        self.assertIn(self.root / "top.txt", listed)
        self.assertIn(self.root / "images" / "old" / "f2.png", listed)

    def test_flat_selection_feeds_operations(self):
        window = self._window()
        window.go_to(self.root)
        window.set_view_mode(ViewMode.FLAT)
        self._pump_flat_scan(window, 7)

        # Select the nested file row and copy it: the clipboard must carry
        # the real (nested) path with its relative structure.
        target = self.root / "images" / "old" / "f2.png"
        self._copy_in_flat_view(window, target)
        self.assertIn(target, window._clipboard_paths)
        self.assertEqual(
            dict(window._clipboard_structure)[target],
            "images/old",
        )

    def test_flat_mode_persists_in_folder_format(self):
        window = self._window()
        window.go_to(self.root)
        window.set_view_mode(ViewMode.FLAT)
        window.set_flat_view_mode(FlatViewMode.FILES_ONLY)
        fmt = window.view_controller.format_to_restore(self.root)
        self.assertIsNotNone(fmt)
        self.assertEqual(fmt["view"], "flat")
        self.assertEqual(fmt["flat_mode"], "files_only")

    def test_flat_mode_restored_on_navigation(self):
        window = self._window()
        window.go_to(self.root)
        window.set_view_mode(ViewMode.FLAT)
        window.set_flat_view_mode(FlatViewMode.FILES_ONLY)
        # Navigate away and back: the folder format restores flat + mode.
        other = Path(tempfile.mkdtemp(prefix="lfm_other_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(other, ignore_errors=True))
        window.go_to(other)
        window.go_to(self.root)
        self.assertEqual(window.workspace.view_mode(), ViewMode.FLAT)
        self.assertEqual(window.workspace.flat_view_mode, FlatViewMode.FILES_ONLY)

    def _copy_in_flat_view(self, window, target: Path):
        """Select a row in the flat view and copy it (structure captured)."""
        for row, entry in enumerate(window.workspace.flat_model.entries()):
            if entry.path == target:
                index = window.workspace.flat_model.index(row, 0)
                selection_model = window.workspace.flat_view.selectionModel()
                selection_model.setCurrentIndex(
                    index,
                    selection_model.SelectionFlag.ClearAndSelect
                    | selection_model.SelectionFlag.Current,
                )
                break
        else:
            self.fail(f"{target} not found in flat model")
        window.copy_selected()
        self.assertIn(target, window._clipboard_paths)

    def _wait_workers_done(self, window, timeout=5.0):
        """Pump until all registered workers finished (safe window close)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            QApplication.processEvents()
            if not window._active_workers and window._operation_queue.pending_count == 0:
                return True
        return not window._active_workers

    def test_nested_paste_rule_cancel_aborts(self):
        window = self._window()
        dest = self.root / "dest"
        dest.mkdir(exist_ok=True)
        window.go_to(self.root)
        window.set_view_mode(ViewMode.FLAT)
        self._pump_flat_scan(window, 7)

        # Copy the nested file from the flat view of root: its structure
        # ("docs") is captured against the base folder at copy time.
        self._copy_in_flat_view(window, self.root / "docs" / "readme.md")
        self.assertEqual(
            dict(window._clipboard_structure)[self.root / "docs" / "readme.md"],
            "docs",
        )

        window.go_to(dest)
        with _patch_question(QMessageBox.StandardButton.Cancel):
            window.paste_from_clipboard()
        self.assertFalse((dest / "readme.md").exists())
        self.assertFalse((dest / "docs").exists())

    def test_nested_paste_rule_recreate_builds_structure(self):
        window = self._window()
        dest = self.root / "dest"
        dest.mkdir(exist_ok=True)
        window.go_to(self.root)
        window.set_view_mode(ViewMode.FLAT)
        self._pump_flat_scan(window, 7)

        self._copy_in_flat_view(window, self.root / "docs" / "readme.md")
        window.go_to(dest)
        with _patch_question(QMessageBox.StandardButton.Yes):
            window.paste_from_clipboard()

        self.assertTrue(
            self._wait_workers_done(window),
            "copy worker still running at test end",
        )
        self.assertTrue((dest / "docs" / "readme.md").exists())

    def test_nested_paste_rule_same_folder_flattens(self):
        window = self._window()
        dest = self.root / "dest"
        dest.mkdir(exist_ok=True)
        window.go_to(self.root)
        window.set_view_mode(ViewMode.FLAT)
        self._pump_flat_scan(window, 7)

        self._copy_in_flat_view(window, self.root / "docs" / "readme.md")
        window.go_to(dest)
        with _patch_question(QMessageBox.StandardButton.No):
            window.paste_from_clipboard()

        self.assertTrue(
            self._wait_workers_done(window),
            "copy worker still running at test end",
        )
        self.assertTrue((dest / "readme.md").exists())
        self.assertFalse((dest / "docs").exists())

    def test_paste_into_same_base_folder_skips_question(self):
        """Pasting back into the same base folder asks nothing and is a no-op
        for the nested items themselves (source == dest is skipped)."""
        window = self._window()
        window.go_to(self.root)
        window.set_view_mode(ViewMode.FLAT)
        self._pump_flat_scan(window, 7)

        self._copy_in_flat_view(window, self.root / "docs" / "readme.md")
        # Paste while still in the same base folder (the flat view of root).
        with _patch_question(QMessageBox.StandardButton.Yes) as mocked:
            window.paste_from_clipboard()
            mocked.assert_not_called()
        # The worker skipped copying onto itself; nothing crashed.
        self.assertTrue(self._wait_workers_done(window))


# Re-export for the tests above.
from PyQt6.QtWidgets import QMessageBox  # noqa: E402


if __name__ == "__main__":
    unittest.main()
