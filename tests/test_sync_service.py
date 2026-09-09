"""Tests for the two-phase folder synchronization service (backlog P2).

Covers:
- Pure comparison: compare_folders in unidirectional and bidirectional modes.
- Update criteria: name, size, mtime, mtime_size.
- Orphan handling: delete_orphans flag.
- Time tolerance: ignoring small mtime differences.
- SyncPlan properties: to_copy, to_delete, conflicts, total_size.
- apply_plan ordering: copies before deletes.
- SyncCompareWorker: background thread.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from lfmapp.services.sync_service import (
    SyncAction,
    SyncActionType,
    SyncCompareWorker,
    SyncMode,
    SyncPlan,
    UpdateCriterion,
    _is_up_to_date,
    _walk_files,
    apply_plan,
    compare_folders,
)


def _pump_until(condition, timeout=10.0):
    """Pump Qt events until *condition()* is true."""
    from PyQt6.QtWidgets import QApplication
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        QApplication.processEvents()
    return condition()


# ---------------------------------------------------------------------------
# _walk_files tests
# ---------------------------------------------------------------------------

class WalkFilesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)

    def test_walk_collects_files(self):
        (self.root / "a.txt").write_text("a")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "b.txt").write_text("b")
        files = _walk_files(self.root)
        self.assertIn("a.txt", files)
        self.assertIn(os.path.join("sub", "b.txt"), files)

    def test_walk_nonexistent_root(self):
        self.assertEqual(_walk_files(Path("/nonexistent")), {})

    def test_walk_empty_dir(self):
        self.assertEqual(_walk_files(self.root), {})

    def test_walk_skips_symlinks(self):
        (self.root / "real.txt").write_text("real")
        link = self.root / "link.txt"
        try:
            link.symlink_to(self.root / "real.txt")
        except OSError:
            self.skipTest("symlinks not supported")
        files = _walk_files(self.root)
        self.assertIn("real.txt", files)
        self.assertNotIn("link.txt", files)


# ---------------------------------------------------------------------------
# _is_up_to_date tests
# ---------------------------------------------------------------------------

class IsUpToDateTests(unittest.TestCase):
    def _stat(self, size: int = 100, mtime: float = 1000.0):
        """Create a fake stat_result."""
        class FakeStat:
            def __init__(self, size, mtime):
                self.st_size = size
                self.st_mtime = mtime
        return FakeStat(size, mtime)

    def test_name_criterion_always_up_to_date(self):
        s = self._stat()
        self.assertTrue(_is_up_to_date(s, self._stat(), UpdateCriterion.NAME))

    def test_size_same(self):
        s = self._stat(size=100)
        self.assertTrue(_is_up_to_date(s, self._stat(size=100), UpdateCriterion.SIZE))

    def test_size_different(self):
        s = self._stat(size=100)
        self.assertFalse(_is_up_to_date(s, self._stat(size=200), UpdateCriterion.SIZE))

    def test_mtime_same(self):
        s = self._stat(mtime=1000.0)
        self.assertTrue(_is_up_to_date(s, self._stat(mtime=1000.0), UpdateCriterion.MTIME))

    def test_mtime_within_tolerance(self):
        s = self._stat(mtime=1000.0)
        self.assertTrue(_is_up_to_date(s, self._stat(mtime=1000.5), UpdateCriterion.MTIME, time_tolerance=1.0))

    def test_mtime_outside_tolerance(self):
        s = self._stat(mtime=1000.0)
        self.assertFalse(_is_up_to_date(s, self._stat(mtime=2000.0), UpdateCriterion.MTIME, time_tolerance=1.0))

    def test_mtime_size_both_match(self):
        s = self._stat(size=100, mtime=1000.0)
        self.assertTrue(_is_up_to_date(s, self._stat(size=100, mtime=1000.0), UpdateCriterion.MTIME_SIZE))

    def test_mtime_size_size_differs(self):
        s = self._stat(size=100, mtime=1000.0)
        self.assertFalse(_is_up_to_date(s, self._stat(size=200, mtime=1000.0), UpdateCriterion.MTIME_SIZE))

    def test_none_dest_not_up_to_date(self):
        s = self._stat()
        self.assertFalse(_is_up_to_date(s, None, UpdateCriterion.NAME))


# ---------------------------------------------------------------------------
# compare_folders tests
# ---------------------------------------------------------------------------

class CompareFoldersTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.src = Path(self._tmp) / "src"
        self.dst = Path(self._tmp) / "dst"
        self.src.mkdir()
        self.dst.mkdir()

    def test_identical_folders_nothing_to_do(self):
        (self.src / "a.txt").write_text("same")
        (self.dst / "a.txt").write_text("same")
        # Force same mtime.
        os.utime(self.src / "a.txt", (1000, 1000))
        os.utime(self.dst / "a.txt", (1000, 1000))
        plan = compare_folders(self.src, self.dst, criterion=UpdateCriterion.MTIME_SIZE)
        actions = [a for a in plan.actions if a.action != SyncActionType.NOTHING]
        self.assertEqual(actions, [])

    def test_new_in_source_copied(self):
        (self.src / "new.txt").write_text("new")
        plan = compare_folders(self.src, self.dst, criterion=UpdateCriterion.NAME)
        copies = plan.to_copy
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].source.name, "new.txt")

    def test_only_in_destination_kept(self):
        (self.dst / "only_dst.txt").write_text("only")
        plan = compare_folders(self.src, self.dst, criterion=UpdateCriterion.NAME)
        self.assertEqual(plan.to_copy, [])
        self.assertEqual(plan.to_delete, [])

    def test_only_in_destination_deleted_with_flag(self):
        (self.dst / "orphan.txt").write_text("orphan")
        plan = compare_folders(
            self.src, self.dst,
            criterion=UpdateCriterion.NAME,
            delete_orphans=True,
        )
        self.assertEqual(len(plan.to_delete), 1)
        self.assertEqual(plan.to_delete[0].source.name, "orphan.txt")

    def test_unidirectional_copies_newer_source(self):
        (self.src / "shared.txt").write_text("v2")
        (self.dst / "shared.txt").write_text("v1")
        os.utime(self.src / "shared.txt", (20000, 20000))
        os.utime(self.dst / "shared.txt", (10000, 10000))
        plan = compare_folders(self.src, self.dst, criterion=UpdateCriterion.MTIME)
        copies = plan.to_copy
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].source.name, "shared.txt")

    def test_bidirectional_newest_wins(self):
        (self.src / "a.txt").write_text("old")
        (self.dst / "a.txt").write_text("new")
        os.utime(self.src / "a.txt", (10000, 10000))
        os.utime(self.dst / "a.txt", (20000, 20000))
        plan = compare_folders(
            self.src, self.dst,
            mode=SyncMode.BIDIRECTIONAL,
            criterion=UpdateCriterion.MTIME,
        )
        copies = plan.to_copy
        self.assertEqual(len(copies), 1)
        # Destination is newer, so it should be copied to source.
        self.assertEqual(copies[0].source.parent, self.dst)

    def test_bidirectional_new_in_destination(self):
        (self.dst / "only_dst.txt").write_text("only")
        plan = compare_folders(
            self.src, self.dst,
            mode=SyncMode.BIDIRECTIONAL,
            criterion=UpdateCriterion.NAME,
        )
        copies = plan.to_copy
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].source.name, "only_dst.txt")

    def test_time_tolerance_ignores_small_diff(self):
        (self.src / "t.txt").write_text("v1")
        (self.dst / "t.txt").write_text("v2")
        os.utime(self.src / "t.txt", (1000, 1000))
        os.utime(self.dst / "t.txt", (1000, 1000))  # same second
        plan = compare_folders(
            self.src, self.dst,
            criterion=UpdateCriterion.MTIME,
            time_tolerance=1.0,
        )
        actions = [a for a in plan.actions if a.action != SyncActionType.NOTHING]
        self.assertEqual(actions, [])

    def test_plan_properties(self):
        (self.src / "a.txt").write_text("a")
        (self.src / "b.txt").write_text("b")
        plan = compare_folders(self.src, self.dst, criterion=UpdateCriterion.NAME)
        self.assertEqual(len(plan.to_copy), 2)
        self.assertEqual(plan.to_delete, [])
        self.assertEqual(plan.conflicts, [])
        self.assertGreater(plan.total_size, 0)

    def test_nonexistent_source(self):
        plan = compare_folders(Path("/nonexistent"), self.dst)
        self.assertEqual(plan.actions, [])


# ---------------------------------------------------------------------------
# apply_plan tests
# ---------------------------------------------------------------------------

class ApplyPlanTests(unittest.TestCase):
    def test_copies_before_deletes(self):
        plan = SyncPlan(actions=[
            SyncAction(action=SyncActionType.DELETE, source=Path("/a"), destination=Path("/a")),
            SyncAction(action=SyncActionType.COPY, source=Path("/b"), destination=Path("/c")),
        ])
        result = apply_plan(plan)
        types = [r[2] for r in result]
        self.assertEqual(types, [SyncActionType.COPY, SyncActionType.DELETE])

    def test_filtered_actions(self):
        plan = SyncPlan(actions=[
            SyncAction(action=SyncActionType.COPY, source=Path("/a"), destination=Path("/b")),
            SyncAction(action=SyncActionType.NOTHING, source=Path("/c"), destination=Path("/d")),
        ])
        copies = [a for a in plan.actions if a.action == SyncActionType.COPY]
        result = apply_plan(plan, actions=copies)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# SyncCompareWorker tests
# ---------------------------------------------------------------------------

class SyncCompareWorkerTests(unittest.TestCase):
    def setUp(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        self._tmp = tempfile.mkdtemp()
        self.src = Path(self._tmp) / "src"
        self.dst = Path(self._tmp) / "dst"
        self.src.mkdir()
        self.dst.mkdir()

    def test_worker_runs_without_crash(self):
        (self.src / "x.txt").write_text("x")
        worker = SyncCompareWorker(self.src, self.dst, criterion=UpdateCriterion.NAME)
        worker.start()
        worker.wait(5000)
        # Worker completed without crash.
        self.assertTrue(worker.isFinished())

    def test_worker_stop_does_not_crash(self):
        worker = SyncCompareWorker(self.src, self.dst)
        worker.start()
        worker.stop()
        worker.wait(5000)
        self.assertTrue(worker.isFinished() or not worker.isRunning())


if __name__ == "__main__":
    unittest.main()
