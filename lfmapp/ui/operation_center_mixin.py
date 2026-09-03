"""Operation center (workers & progress) extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class OperationCenterMixin:
    def _show_progress(self, title: str, label: str):
        # Create a custom dialog with per-worker rows
        if self._progress_dialog is None:
            dlg = QDialog(self)
            dlg.setWindowTitle(title)
            dlg.setModal(True)
            vlayout = QVBoxLayout(dlg)
            self._progress_main_label = QLabel(label)
            vlayout.addWidget(self._progress_main_label)

            scroll = QScrollArea(dlg)
            scroll.setWidgetResizable(True)
            container = QWidget()
            self._progress_container_layout = QVBoxLayout(container)
            self._progress_container_layout.setSpacing(6)
            self._progress_container_layout.setContentsMargins(0, 0, 0, 0)
            scroll.setWidget(container)
            vlayout.addWidget(scroll)

            # Cancel button
            btn = QPushButton(self.tr("Cancel"))
            btn.clicked.connect(self._on_progress_canceled)
            vlayout.addWidget(btn)

            self._progress_dialog = dlg
            dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            dlg.setStyleSheet(
                "QDialog { background: #f9f9f9; }"
                "QLabel { font-weight: bold; padding: 4px; }"
                "QProgressBar { min-height: 18px; }"
                "QPushButton { min-width: 80px; padding: 4px; }"
            )
            dlg.resize(520, 320)
        # Update label and show
        try:
            self._progress_main_label.setText(label)
        except Exception:
            pass
        self._progress_dialog.show()

    def _register_worker(self, worker, label: str, finished_callback=None):
        """Register a worker for aggregated progress and queue it.

        finished_callback will be invoked after internal cleanup with signature (success, message).
        """
        self._worker_labels[worker] = label
        self._worker_progress[worker] = 0
        self._batch_total += 1

        if hasattr(worker, "progress"):
            worker.progress.connect(lambda v, w=worker: self._on_worker_progress(w, v))

        if hasattr(worker, "file_copied"):
            try:
                worker.file_copied.connect(lambda p, w=worker: self._on_worker_file_event(w, p))
            except Exception:
                pass
        if hasattr(worker, "file_deleted"):
            try:
                worker.file_deleted.connect(lambda p, w=worker: self._on_worker_file_event(w, p))
            except Exception:
                pass

        def _on_finished(success, message, w=worker):
            self._on_worker_finished(w, success, message)
            if finished_callback:
                try:
                    finished_callback(success, message)
                except Exception:
                    pass

        worker.finished.connect(_on_finished)

        self._show_progress(self.tr("Operation"), label)
        try:
            self._add_progress_row(worker, label)
        except Exception:
            pass
        self._update_progress_label(label)
        self.statusBar().showMessage(self.tr("Queued: {label}").format(label=label), 3000)
        self._operation_queue.enqueue(worker)

    def _on_queued_worker_started(self, worker):
        if worker not in self._active_workers:
            self._active_workers.append(worker)
        self.app_state.operation_started()
        label = self._worker_labels.get(worker, self.tr("Operation"))
        self.statusBar().showMessage(label, 0)
        row = self._progress_rows.get(worker)
        if row:
            row[0].setText(self.tr("Running: {label}").format(label=label))
        self._update_progress_label(label)

    def _on_worker_progress(self, worker, value: int):
        # Update per-worker value and aggregate (average)
        self._worker_progress[worker] = int(value)
        if self._progress_dialog is None:
            return
        if not self._worker_progress:
            return
        total = sum(self._worker_progress.values())
        avg = int(total / len(self._worker_progress))
        # Update aggregated UI (show percent)
        self._update_progress_label(None, percent=avg)
        # Update per-worker bar if present
        try:
            row = self._progress_rows.get(worker)
            if row:
                _, bar = row
                bar.setValue(int(value))
        except Exception:
            pass

    def _on_worker_finished(self, worker, success, message):
        # Remove worker from tracking
        if worker in self._active_workers:
            try:
                self._active_workers.remove(worker)
            except ValueError:
                pass
        self.app_state.operation_finished()
        if worker in self._worker_progress:
            try:
                del self._worker_progress[worker]
            except KeyError:
                pass
        # Mark one completed for batch and update label
        self._batch_done += 1
        self._update_progress_label()
        # Remove per-worker UI row
        try:
            self._remove_progress_row(worker)
        except Exception:
            pass
        self._worker_labels.pop(worker, None)
        # If no more active workers, close progress and reset counters
        if not self._active_workers and self._operation_queue.pending_count == 0:
            self._close_progress()

    def _add_progress_row(self, worker, label: str):
        """Add a labelled progress bar row for a worker."""
        if not hasattr(self, "_progress_container_layout"):
            return
        frame = QFrame()
        layout = QHBoxLayout(frame)
        lbl = QLabel(label)
        bar = QProgressBar()
        if hasattr(worker, "progress"):
            bar.setRange(0, 100)
            bar.setValue(0)
        else:
            bar.setRange(0, 0)
        layout.addWidget(lbl)
        layout.addWidget(bar)
        self._progress_container_layout.addWidget(frame)
        self._progress_rows[worker] = (lbl, bar)

    def _remove_progress_row(self, worker):
        try:
            row = self._progress_rows.pop(worker)
            lbl, bar = row
            widget = lbl.parent()
            if widget is not None:
                widget.setParent(None)
        except Exception:
            pass

    def _on_progress_canceled(self):
        self._operation_queue.stop_active()
        for worker in self._operation_queue.cancel_pending():
            self._worker_progress.pop(worker, None)
            self._worker_labels.pop(worker, None)
            self._batch_done += 1
            try:
                self._remove_progress_row(worker)
            except Exception:
                pass
        self._update_progress_label(self.tr("Canceling operations..."))

    def _update_progress_label(self, base_label: str | None = None, percent: int | None = None):
        """Update the progress dialog label to include completed/total batch counts."""
        if self._progress_dialog is None:
            return
        label = base_label or (getattr(self, "_progress_main_label", None).text() if getattr(self, "_progress_main_label", None) is not None else "")
        # Normalize label (strip existing suffix like "(x/y)")
        if "(" in label:
            label = label.split("(", 1)[0].strip()
        if self._batch_total > 0:
            label = f"{label} ({self._batch_done}/{self._batch_total})"
        # Append percent and current file if present
        if percent is not None:
            label = f"{label} {percent}%"
        if self._current_file:
            try:
                short = Path(self._current_file).name
                label = f"{label}: {short}"
            except Exception:
                pass
        try:
            self._progress_main_label.setText(label)
        except Exception:
            pass

    def _on_worker_file_event(self, worker, path: str):
        try:
            self._current_file = path
            self._update_progress_label()
        except Exception:
            pass

    def _close_progress(self):
        if self._progress_dialog is not None:
            try:
                self._progress_dialog.reset()
            except Exception:
                pass
            self._progress_dialog = None
        # Reset batch counters
        self._batch_total = 0
        self._batch_done = 0
        self._worker_progress.clear()
