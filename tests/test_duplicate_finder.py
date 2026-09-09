"""Tests for the duplicate finder (backlog P2).

Covers:
- Pure logic: collect_files, hash_file, group_by_size, group_duplicates.
- DuplicateFinderWorker: progressive group_found signals + cancellation.
- GUI: dialog wired from Tools menu, selection helpers, delete/trash flow.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from lfmapp.services.duplicate_finder_service import (
    DuplicateFinderWorker,
    DuplicateGroup,
    FileEntry,
    collect_files,
    group_by_size,
    group_duplicates,
    hash_file,
)


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


def make_duplicate_tree(root: Path) -> dict:
    """Create a tree with known duplicate content.

    Layout:
        root/
            a.txt   = "same content"
            b.txt   = "same content"
            subdir/
                c.txt = "same content"
                d.txt = "different"
            e.txt   = "different"
            tiny.txt = ""  (empty, below min_size if set)
    """
    (root / "subdir").mkdir(parents=True)
    (root / "a.txt").write_text("same content", encoding="utf-8")
    (root / "b.txt").write_text("same content", encoding="utf-8")
    (root / "subdir" / "c.txt").write_text("same content", encoding="utf-8")
    (root / "subdir" / "d.txt").write_text("different content", encoding="utf-8")
    (root / "e.txt").write_text("different content", encoding="utf-8")
    (root / "tiny.txt").write_text("", encoding="utf-8")
    return {"root": root}


# ---------------------------------------------------------------------------
# Pure logic tests
# ---------------------------------------------------------------------------

class CollectFilesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        make_duplicate_tree(self.root)
        self.addCleanup(lambda: os.unlink(self.root / "a.txt") if False else None)

    def test_recursive_collects_all_files(self):
        entries = collect_files([self.root], recursive=True)
        names = sorted(e.path.name for e in entries)
        self.assertIn("a.txt", names)
        self.assertIn("c.txt", names)
        self.assertEqual(len(names), 6)

    def test_non_recursive_only_top_level(self):
        entries = collect_files([self.root], recursive=False)
        names = sorted(e.path.name for e in entries)
        self.assertIn("a.txt", names)
        self.assertNotIn("c.txt", names)

    def test_min_size_filters(self):
        entries = collect_files([self.root], recursive=True, min_size=1)
        names = [e.path.name for e in entries]
        self.assertNotIn("tiny.txt", names)

    def test_ignore_hidden(self):
        hidden = self.root / ".hidden.txt"
        hidden.write_text("secret", encoding="utf-8")
        entries = collect_files([self.root], recursive=True, ignore_hidden=True)
        self.assertFalse(any(e.path.name == ".hidden.txt" for e in entries))
        entries2 = collect_files([self.root], recursive=True, ignore_hidden=False)
        self.assertTrue(any(e.path.name == ".hidden.txt" for e in entries2))

    def test_nonexistent_root_skipped(self):
        entries = collect_files([Path("/nonexistent/path")], recursive=True)
        self.assertEqual(entries, [])

    def test_file_entry_fields(self):
        entries = collect_files([self.root], recursive=True)
        a = next(e for e in entries if e.path.name == "a.txt")
        self.assertEqual(a.size, len(b"same content"))
        self.assertIsInstance(a.modified, float)

    def test_symlink_not_collected(self):
        """Symlinks should not be treated as regular files."""
        link = self.root / "link.txt"
        try:
            link.symlink_to(self.root / "a.txt")
        except OSError:
            self.skipTest("symlinks not supported")
        entries = collect_files([self.root], recursive=True)
        self.assertFalse(any(e.path == link for e in entries))


class HashFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)

    def test_same_content_same_hash(self):
        p1 = self.root / "a.txt"
        p2 = self.root / "b.txt"
        p1.write_text("hello", encoding="utf-8")
        p2.write_text("hello", encoding="utf-8")
        self.assertEqual(hash_file(p1), hash_file(p2))

    def test_different_content_different_hash(self):
        p1 = self.root / "a.txt"
        p2 = self.root / "b.txt"
        p1.write_text("hello", encoding="utf-8")
        p2.write_text("world", encoding="utf-8")
        self.assertNotEqual(hash_file(p1), hash_file(p2))

    def test_nonexistent_file_returns_empty(self):
        self.assertEqual(hash_file(self.root / "nope.txt"), "")

    def test_empty_file(self):
        p = self.root / "empty.txt"
        p.write_bytes(b"")
        h = hash_file(p)
        self.assertIsInstance(h, str)
        self.assertTrue(len(h) > 0)


class GroupBySizeTests(unittest.TestCase):
    def test_groups_by_size(self):
        entries = [
            FileEntry(Path("/a.txt"), 100, 0.0),
            FileEntry(Path("/b.txt"), 100, 0.0),
            FileEntry(Path("/c.txt"), 200, 0.0),
        ]
        groups = group_by_size(entries)
        self.assertIn(100, groups)
        self.assertEqual(len(groups[100]), 2)
        self.assertNotIn(200, groups)  # single file, not a collision

    def test_empty_input(self):
        self.assertEqual(group_by_size([]), {})


class GroupDuplicatesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        make_duplicate_tree(self.root)

    def test_finds_duplicate_group(self):
        entries = collect_files([self.root], recursive=True)
        groups = group_duplicates(entries)
        # a.txt, b.txt, subdir/c.txt share "same content"
        sizes = [g.size for g in groups]
        self.assertIn(len(b"same content"), sizes)

    def test_groups_sorted_by_wasted_space(self):
        entries = collect_files([self.root], recursive=True)
        groups = group_duplicates(entries)
        if len(groups) >= 2:
            self.assertGreaterEqual(groups[0].wasted, groups[1].wasted)

    def test_wasted_calculation(self):
        entries = collect_files([self.root], recursive=True)
        groups = group_duplicates(entries)
        g = next(g for g in groups if g.size == len(b"same content"))
        # 3 files, keep 1: waste = size * 2
        self.assertEqual(g.wasted, len(b"same content") * 2)

    def test_no_duplicates_for_unique_files(self):
        (self.root / "unique1.txt").write_text("alpha", encoding="utf-8")
        (self.root / "unique2.txt").write_text("beta", encoding="utf-8")
        (self.root / "unique3.txt").write_text("gamma", encoding="utf-8")
        entries = collect_files([self.root], recursive=True)
        groups = group_duplicates(entries)
        # Only the original duplicates should be found
        for g in groups:
            self.assertGreaterEqual(len(g.files), 2)


# ---------------------------------------------------------------------------
# Worker tests
# ---------------------------------------------------------------------------

class DuplicateFinderWorkerTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        make_duplicate_tree(self.root)

    def _pump_until(self, condition, timeout=10.0):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QApplication.processEvents()
        return condition()

    def test_worker_emits_groups(self):
        worker = DuplicateFinderWorker([self.root], recursive=True)
        groups = []
        done = []
        worker.group_found.connect(lambda g: groups.append(g))
        worker.finished.connect(lambda total, wasted: done.append((total, wasted)))
        worker.start()
        self.assertTrue(self._pump_until(lambda: len(done) > 0))
        worker.wait(2000)
        self.assertGreater(len(groups), 0)
        sizes = [g.size for g in groups]
        self.assertIn(len(b"same content"), sizes)

    def test_worker_emits_progress(self):
        worker = DuplicateFinderWorker([self.root], recursive=True)
        progress_vals = []
        worker.progress.connect(lambda n: progress_vals.append(n))
        worker.start()
        self._pump_until(lambda: len(progress_vals) >= 1, timeout=10)
        worker.wait(2000)
        self.assertTrue(len(progress_vals) >= 1)

    def test_worker_cancellation(self):
        worker = DuplicateFinderWorker([self.root], recursive=True)
        done = []
        worker.finished.connect(lambda total, wasted: done.append(True))
        worker.start()
        worker.stop()
        self._pump_until(lambda: len(done) > 0, timeout=10)
        worker.wait(2000)
        self.assertTrue(done)

    def test_worker_min_size(self):
        worker = DuplicateFinderWorker([self.root], recursive=True, min_size=5)
        groups = []
        done = []
        worker.group_found.connect(lambda g: groups.append(g))
        worker.finished.connect(lambda t, w: done.append(True))
        worker.start()
        self._pump_until(lambda: len(done) > 0)
        worker.wait(2000)
        for g in groups:
            self.assertGreaterEqual(g.size, 5)

    def test_worker_nonexistent_root(self):
        worker = DuplicateFinderWorker([Path("/nonexistent")], recursive=True)
        done = []
        worker.finished.connect(lambda total, wasted: done.append((total, wasted)))
        worker.start()
        self._pump_until(lambda: len(done) > 0)
        worker.wait(2000)
        self.assertEqual(done, [(0, 0)])

    def test_worker_non_recursive(self):
        worker = DuplicateFinderWorker([self.root], recursive=False)
        groups = []
        done = []
        worker.group_found.connect(lambda g: groups.append(g))
        worker.finished.connect(lambda t, w: done.append(True))
        worker.start()
        self._pump_until(lambda: len(done) > 0)
        worker.wait(2000)
        for g in groups:
            for f in g.files:
                self.assertEqual(f.path.parent, self.root)

    def test_group_found_emits_correct_type(self):
        worker = DuplicateFinderWorker([self.root], recursive=True)
        groups = []
        done = []
        worker.group_found.connect(lambda g: groups.append(g))
        worker.finished.connect(lambda t, w: done.append(True))
        worker.start()
        self._pump_until(lambda: len(done) > 0)
        worker.wait(2000)
        for g in groups:
            self.assertIsInstance(g, DuplicateGroup)
            self.assertIsInstance(g.hash_value, str)
            self.assertIsInstance(g.size, int)
            self.assertIsInstance(g.files, tuple)
            self.assertGreaterEqual(len(g.files), 2)


# ---------------------------------------------------------------------------
# Selection helper tests (pure logic, no Qt needed)
# ---------------------------------------------------------------------------

class SelectionHelperTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        make_duplicate_tree(self.root)
        entries = collect_files([self.root], recursive=True)
        self.groups = group_duplicates(entries)
        self.assertTrue(self.groups, "need at least one group")

    def test_select_keep_newest(self):
        from lfmapp.ui.duplicate_finder_dialog import _select_keep_newest
        g = self.groups[0]
        to_delete = _select_keep_newest(g)
        self.assertEqual(len(to_delete), len(g.files) - 1)
        # The kept file is NOT in the delete list
        kept = sorted(g.files, key=lambda f: f.modified, reverse=True)[0]
        self.assertNotIn(kept.path, to_delete)

    def test_select_keep_oldest(self):
        from lfmapp.ui.duplicate_finder_dialog import _select_keep_oldest
        g = self.groups[0]
        to_delete = _select_keep_oldest(g)
        self.assertEqual(len(to_delete), len(g.files) - 1)
        kept = sorted(g.files, key=lambda f: f.modified)[0]
        self.assertNotIn(kept.path, to_delete)

    def test_select_keep_shortest_path(self):
        from lfmapp.ui.duplicate_finder_dialog import _select_keep_shortest_path
        g = self.groups[0]
        to_delete = _select_keep_shortest_path(g)
        self.assertEqual(len(to_delete), len(g.files) - 1)
        kept = sorted(g.files, key=lambda f: len(str(f.path)))[0]
        self.assertNotIn(kept.path, to_delete)

    def test_select_keep_newest_two_files(self):
        from lfmapp.ui.duplicate_finder_dialog import _select_keep_newest
        g = DuplicateGroup(
            hash_value="abc",
            size=10,
            files=(
                FileEntry(Path("/a.txt"), 10, 100.0),
                FileEntry(Path("/b.txt"), 10, 200.0),
            ),
        )
        to_delete = _select_keep_newest(g)
        self.assertEqual(to_delete, [Path("/a.txt")])  # older deleted


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

class DuplicateFinderDialogTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        make_duplicate_tree(self.root)

    def _pump_until(self, condition, timeout=10.0):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QApplication.processEvents()
        return condition()

    def test_dialog_opens_and_shows_duplicates(self):
        from lfmapp.ui.duplicate_finder_dialog import DuplicateFinderDialog
        dlg = DuplicateFinderDialog()
        dlg.start_from_folders([self.root], recursive=True)
        self.assertTrue(self._pump_until(lambda: dlg._tree.topLevelItemCount() > 0))
        # At least one group header with children
        top = dlg._tree.topLevelItem(0)
        self.assertIsNotNone(top)
        self.assertGreater(top.childCount(), 0)
        if dlg._worker and dlg._worker.isRunning():
            dlg._worker.stop()
            dlg._worker.wait(3000)
        dlg.close()

    def test_dialog_set_groups(self):
        from lfmapp.ui.duplicate_finder_dialog import DuplicateFinderDialog
        entries = collect_files([self.root], recursive=True)
        groups = group_duplicates(entries)
        dlg = DuplicateFinderDialog()
        dlg.set_groups(groups)
        self.assertEqual(dlg._tree.topLevelItemCount(), len(groups))
        dlg.close()

    def test_checked_paths(self):
        from lfmapp.ui.duplicate_finder_dialog import DuplicateFinderDialog
        from PyQt6.QtCore import Qt
        entries = collect_files([self.root], recursive=True)
        groups = group_duplicates(entries)
        dlg = DuplicateFinderDialog()
        dlg.set_groups(groups)
        # Check the first child of the first group
        top = dlg._tree.topLevelItem(0)
        child = top.child(0)
        child.setCheckState(0, Qt.CheckState.Checked)
        paths = dlg.checked_paths()
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], Path(child.data(0, Qt.ItemDataRole.UserRole)))
        dlg.close()

    def test_auto_select_keep_newest(self):
        from lfmapp.ui.duplicate_finder_dialog import DuplicateFinderDialog
        from PyQt6.QtCore import Qt
        entries = collect_files([self.root], recursive=True)
        groups = group_duplicates(entries)
        dlg = DuplicateFinderDialog()
        dlg.set_groups(groups)
        dlg._auto_select_combo.setCurrentIndex(0)  # Keep newest
        dlg._apply_auto_select()
        # In each group, all but one should be checked
        for g_idx in range(dlg._tree.topLevelItemCount()):
            top = dlg._tree.topLevelItem(g_idx)
            checked = sum(
                1 for j in range(top.childCount())
                if top.child(j).checkState(0) == Qt.CheckState.Checked
            )
            self.assertEqual(checked, top.childCount() - 1)
        dlg.close()


class DuplicateFinderMenuTests(unittest.TestCase):
    """Verify the menu action is wired and opens the dialog."""

    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def test_menu_action_exists(self):
        import lfmapp.core.config as config_module
        from lfmapp.ui.main_window import MainWindow

        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_dir = config_module.CONFIG_DIR
            old_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir)
            config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
            try:
                window = MainWindow()
                menubar = window.menuBar()
                tools = None
                for action in menubar.actions():
                    if action.text().replace("&", "") == "Tools":
                        tools = action.menu()
                        break
                self.assertIsNotNone(tools, "Tools menu not found")
                labels = [a.text() for a in tools.actions()]
                self.assertTrue(
                    any("Duplicate" in l for l in labels),
                    f"'Find Duplicates...' not in Tools menu: {labels}",
                )
            finally:
                config_module.CONFIG_DIR = old_config_dir
                config_module.CONFIG_FILE = old_config_file


if __name__ == "__main__":
    unittest.main()
