"""Tests for the non-modal Operation Center (ROADMAP Phase 2.2)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QMessageBox

from lfmapp.core import config as config_module

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


class FakeWorker(QThread):
    """Minimal worker that never starts a real thread unless told to."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._paused = False
        self.started_as_thread = False

    @property
    def is_paused(self):
        return self._paused

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._running = False


class OperationCenterTestCase(unittest.TestCase):
    def setUp(self):
        _ensure_app()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        old_dir = config_module.CONFIG_DIR
        old_file = config_module.CONFIG_FILE
        config_module.CONFIG_DIR = Path(self._tmpdir.name)
        config_module.CONFIG_FILE = Path(self._tmpdir.name) / "config.json"
        self.addCleanup(setattr, config_module, "CONFIG_DIR", old_dir)
        self.addCleanup(setattr, config_module, "CONFIG_FILE", old_file)

        from lfmapp.ui.main_window import MainWindow

        self.window = MainWindow()
        self.addCleanup(self.window.deleteLater)
        # Prevent real QThread starts: the queue records jobs but never runs them.
        self.enqueued = []
        self.patcher = patch.object(
            self.window._operation_queue, "enqueue", side_effect=self.enqueued.append
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _register(self, label="Copying a.txt", retry_factory=None):
        worker = FakeWorker()
        self.window._register_worker(worker, label, retry_factory=retry_factory)
        return worker

    def test_register_shows_panel_and_row(self):
        worker = self._register()
        self.assertTrue(self.window.operation_center_panel.isVisibleTo(self.window))
        self.assertIn(worker, self.window._job_rows)
        self.assertEqual(self.window._job_states[worker], "queued")
        self.assertTrue(self.window.jobs_status_button.isVisibleTo(self.window))
        self.assertIn("1", self.window.jobs_status_button.text())

    def test_hiding_panel_does_not_cancel_job(self):
        worker = self._register()
        self.window.hide_operation_center()
        self.assertFalse(self.window.operation_center_panel.isVisibleTo(self.window))
        self.assertEqual(self.window._job_states[worker], "queued")
        self.assertIn(worker, self.enqueued)

    def test_running_job_offers_pause_and_resume(self):
        worker = self._register()
        self.window._on_queued_worker_started(worker)
        self.assertEqual(self.window._job_states[worker], "running")
        self.window._toggle_pause(worker)
        self.assertTrue(worker.is_paused)
        self.assertEqual(self.window._job_states[worker], "paused")
        self.assertIn("Paused", self.window._job_rows[worker][1].text())
        self.window._toggle_pause(worker)
        self.assertFalse(worker.is_paused)
        self.assertEqual(self.window._job_states[worker], "running")

    def test_cancel_queued_job_uses_queue(self):
        worker = self._register()
        with patch.object(
            self.window._operation_queue, "cancel_worker", return_value=True
        ) as cancel_mock:
            self.window._cancel_job(worker)
        cancel_mock.assert_called_once_with(worker)
        self.assertEqual(self.window._job_states[worker], "cancelling")

    def test_finish_success_marks_completed(self):
        worker = self._register()
        self.window._on_queued_worker_started(worker)
        self.window._on_worker_finished(worker, True, "done")
        self.assertEqual(self.window._job_states[worker], "completed")
        name, retry = self.window._job_rows[worker][1], self.window._job_rows[worker][4]
        self.assertIn("Completed", name.text())
        self.assertFalse(retry.isVisible())

    def test_finish_failure_offers_retry_with_factory(self):
        retried = []
        worker = self._register(retry_factory=lambda: retried.append(True) or FakeWorker())
        self.window._on_queued_worker_started(worker)
        self.window._on_worker_finished(worker, False, "boom")
        self.assertEqual(self.window._job_states[worker], "failed")
        retry_button = self.window._job_rows[worker][4]
        self.assertTrue(retry_button.isVisibleTo(self.window.operation_center_panel))
        self.window._retry_job(worker)
        self.assertEqual(len(retried), 1)
        # The replacement worker was queued again with the same label
        self.assertEqual(len(self.enqueued), 2)

    def test_clear_completed_keeps_running(self):
        done = self._register()
        running = self._register("Moving b.txt")
        self.window._on_queued_worker_started(done)
        self.window._on_worker_finished(done, True, "ok")
        self.window._on_queued_worker_started(running)
        self.window.clear_completed_operations()
        self.assertNotIn(done, self.window._job_states)
        self.assertIn(running, self.window._job_states)
        self.assertIn("1 active", self.window._ops_summary_label.text())

    def test_progress_updates_aggregate(self):
        worker = self._register()
        self.window._on_queued_worker_started(worker)
        self.window._on_worker_progress(worker, 40)
        self.assertIn("40%", self.window._ops_summary_label.text())
        self.assertEqual(self.window._job_rows[worker][2].value(), 40)

    def test_close_with_running_jobs_asks_first(self):
        worker = self._register()
        self.window._on_queued_worker_started(worker)
        event = QCloseEvent()
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.No
        ):
            self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())

        event2 = QCloseEvent()
        with (
            patch.object(
                QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
            ),
            patch.object(self.window._operation_queue, "stop_active") as stop_mock,
            patch.object(
                self.window._operation_queue, "cancel_pending", return_value=[]
            ) as cancel_mock,
        ):
            self.window.closeEvent(event2)
        # Window may already be closed by the real closeEvent machinery; the
        # important part is the queue was asked to stop before accepting.
        stop_mock.assert_called_once()
        cancel_mock.assert_called_once()

    def test_cancel_all_cancels_active_jobs(self):
        first = self._register()
        second = self._register("Moving b.txt")
        with patch.object(
            self.window._operation_queue, "cancel_worker", return_value=True
        ) as cancel_mock:
            self.window.cancel_all_operations()
        self.assertEqual(cancel_mock.call_count, 2)
        self.assertEqual(self.window._job_states[first], "cancelling")
        self.assertEqual(self.window._job_states[second], "cancelling")

    def test_close_without_jobs_does_not_ask(self):
        event = QCloseEvent()
        with patch.object(QMessageBox, "question") as question_mock:
            self.window.closeEvent(event)
        question_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
