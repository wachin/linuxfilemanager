import importlib
import shutil
import tempfile
import unittest
from pathlib import Path

from PyQt6.QtCore import QObject, QCoreApplication, pyqtSignal

from lfmapp.services.operation_queue import BackgroundOperationQueue
from lfmapp.services.worker_threads import CopyWorker, MoveWorker


def ensure_qcore_application():
    app = QCoreApplication.instance()
    if app is None:
        QCoreApplication([])


class WorkerThreadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qcore_application()

    def test_copy_worker_runs_and_copies_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()
            file_path = source_dir / "hello.txt"
            file_path.write_text("hello world", encoding="utf-8")

            worker = CopyWorker(source_dir, dest_dir)
            worker.run()

            copied_file = dest_dir / "source" / "hello.txt"
            self.assertTrue(copied_file.exists())
            self.assertEqual(copied_file.read_text(encoding="utf-8"), "hello world")

    def test_move_worker_runs_and_removes_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir)
            file_path = source_dir / "move_me.txt"
            file_path.write_text("move data", encoding="utf-8")
            dest_dir = source_dir / "destination"

            worker = MoveWorker(file_path, dest_dir)
            worker.run()

            moved_file = dest_dir / "move_me.txt"
            self.assertTrue(moved_file.exists())
            self.assertEqual(moved_file.read_text(encoding="utf-8"), "move data")
            self.assertFalse(file_path.exists())

    def test_move_worker_stop_before_run_keeps_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir)
            file_path = source_dir / "cancel.txt"
            file_path.write_text("cancel me", encoding="utf-8")
            dest_dir = source_dir / "destination"

            worker = MoveWorker(file_path, dest_dir)
            worker.stop()
            worker.run()

            self.assertTrue(file_path.exists())
            self.assertFalse((dest_dir / "cancel.txt").exists())

    def test_background_operation_queue_runs_one_worker_at_a_time(self):
        class ManualWorker(QObject):
            finished = pyqtSignal(bool, str)

            def __init__(self, name):
                super().__init__()
                self.name = name
                self.started = False

            def start(self):
                self.started = True

        queue = BackgroundOperationQueue(max_concurrent=1)
        first = ManualWorker("first")
        second = ManualWorker("second")
        started = []
        completed = []
        queue.operation_started.connect(lambda worker: started.append(worker.name))
        queue.operation_finished.connect(lambda worker: completed.append(worker.name))

        queue.enqueue(first)
        queue.enqueue(second)

        self.assertTrue(first.started)
        self.assertFalse(second.started)
        self.assertEqual(queue.active_count, 1)
        self.assertEqual(queue.pending_count, 1)

        first.finished.emit(True, "done")

        self.assertTrue(second.started)
        self.assertEqual(started, ["first", "second"])
        self.assertEqual(completed, ["first"])
        self.assertEqual(queue.active_count, 1)
        self.assertEqual(queue.pending_count, 0)

        second.finished.emit(True, "done")

        self.assertEqual(completed, ["first", "second"])
        self.assertEqual(queue.total_count, 0)

    def test_background_operation_queue_can_cancel_pending_workers(self):
        class ManualWorker(QObject):
            finished = pyqtSignal(bool, str)

            def __init__(self):
                super().__init__()
                self.started = False

            def start(self):
                self.started = True

        queue = BackgroundOperationQueue(max_concurrent=1)
        first = ManualWorker()
        second = ManualWorker()
        queue.enqueue(first)
        queue.enqueue(second)

        canceled = queue.cancel_pending()

        self.assertEqual(canceled, [second])
        self.assertTrue(first.started)
        self.assertFalse(second.started)
        self.assertEqual(queue.pending_count, 0)


if __name__ == "__main__":
    unittest.main()
