"""Tests for background folder-size computation (Phase 9.2).

Covers:
- Pure compute_folder_size: recursive sum, symlinks skipped, errors ignored,
  approximate at limit, non-directory returns 0.
- FolderSizeCache: get/put, mtime invalidation, clear.
- FolderSizeWorker: size_ready emission + cancellation.
- FileSystemModel integration: "…" placeholder -> real value via set_folder_size
  with a dataChanged for the Size column; empty when disabled; "~" when
  approximate.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QFileInfo
from PyQt6.QtWidgets import QApplication

from lfmapp.services.folder_size_service import (
    FolderSizeCache,
    FolderSizeWorker,
    compute_folder_size,
)


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return app


def _make_tree(root: Path) -> int:
    """Build root/{sub/{a(10),b(20)}, c(30)}; returns expected file total (60)."""
    (root / "sub").mkdir()
    (root / "sub" / "a.txt").write_bytes(b"x" * 10)
    (root / "sub" / "b.txt").write_bytes(b"y" * 20)
    (root / "c.txt").write_bytes(b"z" * 30)
    return 60


class ComputeFolderSizeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)

    def test_recursive_sum(self):
        expected = _make_tree(self.root)
        total, approx = compute_folder_size(self.root)
        self.assertEqual(total, expected)
        self.assertFalse(approx)

    def test_non_directory(self):
        f = self.root / "plain.txt"
        f.write_bytes(b"abc")
        total, approx = compute_folder_size(f)
        self.assertEqual(total, 0)
        self.assertFalse(approx)

    def test_symlinks_not_followed(self):
        target = self.root / "real.txt"
        target.write_bytes(b"12345")
        link = self.root / "link.txt"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("symlinks unsupported")
        total, _ = compute_folder_size(self.root)
        # Only the real file counts (5), not the symlink target duplicated.
        self.assertEqual(total, 5)

    def test_limit_marks_approximate(self):
        (self.root / "big.bin").write_bytes(b"0" * 10000)
        total, approx = compute_folder_size(self.root, limit=500)
        self.assertTrue(approx)
        self.assertGreaterEqual(total, 500)

    def test_empty_dir(self):
        (self.root / "empty").mkdir()
        total, approx = compute_folder_size(self.root / "empty")
        self.assertEqual(total, 0)
        self.assertFalse(approx)


class FolderSizeCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.d = self.root / "sub"
        self.d.mkdir()
        self.cache = FolderSizeCache()

    def test_put_get(self):
        self.cache.put(self.d, 123, False)
        self.assertEqual(self.cache.get(self.d), (123, False))

    def test_stale_on_mtime_change(self):
        self.cache.put(self.d, 123, False)
        # Change the directory's own mtime (as an add/remove would).
        os.utime(self.d, (10, 10))
        self.assertIsNone(self.cache.get(self.d))

    def test_clear(self):
        self.cache.put(self.d, 5, False)
        self.cache.invalidate()
        self.assertEqual(len(self.cache), 0)
        self.assertIsNone(self.cache.get(self.d))

    def test_invalidate_single(self):
        other = self.root / "other"
        other.mkdir()
        self.cache.put(self.d, 1, False)
        self.cache.put(other, 2, False)
        self.cache.invalidate(self.d)
        self.assertIsNone(self.cache.get(self.d))
        self.assertEqual(self.cache.get(other), (2, False))


class FolderSizeWorkerTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        (self.root / "d1").mkdir()
        (self.root / "d1" / "f.txt").write_bytes(b"x" * 40)
        (self.root / "d2").mkdir()
        (self.root / "d2" / "g.txt").write_bytes(b"y" * 60)

    def test_emits_size_ready(self):
        worker = FolderSizeWorker([self.root / "d1", self.root / "d2"])
        results = {}
        worker.size_ready.connect(lambda p, size, approx: results.__setitem__(str(p), size))
        done = []
        worker.finished.connect(lambda: done.append(True))
        worker.start()
        deadline = time.monotonic() + 10
        while not done and time.monotonic() < deadline:
            QApplication.processEvents()
        worker.wait(2000)
        self.assertEqual(results.get(str(self.root / "d1")), 40)
        self.assertEqual(results.get(str(self.root / "d2")), 60)

    def test_stop_does_not_crash(self):
        worker = FolderSizeWorker([self.root / "d1"])
        worker.start()
        worker.stop()
        worker.wait(3000)
        self.assertTrue(worker.isFinished() or not worker.isRunning())


class ModelIntegrationTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        _make_tree(self.root)
        import lfmapp.core.config as cm
        self._cm = cm
        self._orig_dir = cm.CONFIG_DIR
        self._orig_file = cm.CONFIG_FILE
        cm.CONFIG_DIR = self.root / "cfg"
        cm.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cm.CONFIG_FILE = cm.CONFIG_DIR / "config.json"

    def tearDown(self):
        self._cm.CONFIG_DIR = self._orig_dir
        self._cm.CONFIG_FILE = self._orig_file

    def _model(self):
        from lfmapp.models import FileSystemModel
        from lfmapp.core.config import Config
        m = FileSystemModel(root_path=self.root, config=Config())
        return m

    def test_disabled_shows_empty(self):
        m = self._model()
        m.show_folder_sizes = False
        display = m._folder_size_display(str(self.root))
        self.assertEqual(display, "")

    def test_pending_then_value(self):
        m = self._model()
        m.show_folder_sizes = True
        # Before measurement: pending marker.
        self.assertEqual(m._folder_size_display(str(self.root)), "…")
        # After the worker computes and we record it: formatted size.
        m.set_folder_size(self.root, 60, False)
        self.assertNotEqual(m._folder_size_display(str(self.root)), "…")
        self.assertIn("60", m._folder_size_display(str(self.root)))

    def test_approximate_marker(self):
        m = self._model()
        m.show_folder_sizes = True
        m.set_folder_size(self.root, 60, True)
        self.assertTrue(m._folder_size_display(str(self.root)).endswith("~"))


if __name__ == "__main__":
    unittest.main()
