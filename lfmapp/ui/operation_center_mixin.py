"""Non-modal Operation Center (workers & progress) (ROADMAP Phase 2.2).

Replaces the old modal progress dialog with a collapsible panel at the
bottom of the main window: the user keeps navigating while transfers run,
closing/hiding the panel never cancels operations, and each job offers
pause/resume/cancel plus retry for failed ones.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from lfmapp.ui.icons import app_icon


class OperationCenterMixin:
    # ─── Panel construction ────────────────────────────────────

    def build_operation_center_panel(self, central_layout):
        """Create the bottom operations panel (hidden until a job starts)."""
        panel = QFrame(self)
        panel.setObjectName("operationCenterPanel")
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 4, 6, 4)
        panel_layout.setSpacing(4)

        header = QHBoxLayout()
        self._ops_summary_label = QLabel(self.tr("Operations"), panel)
        header.addWidget(self._ops_summary_label, 1)
        self._ops_clear_button = QPushButton(self.tr("Clear completed"), panel)
        self._ops_clear_button.clicked.connect(self.clear_completed_operations)
        header.addWidget(self._ops_clear_button)
        self._ops_cancel_all_button = QPushButton(self.tr("Cancel all"), panel)
        self._ops_cancel_all_button.clicked.connect(self.cancel_all_operations)
        header.addWidget(self._ops_cancel_all_button)
        self._ops_hide_button = QPushButton(self.tr("Hide panel"), panel)
        self._ops_hide_button.clicked.connect(lambda: self.hide_operation_center())
        header.addWidget(self._ops_hide_button)
        panel_layout.addLayout(header)

        scroll = QScrollArea(panel)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(180)
        container = QWidget()
        self._ops_rows_layout = QVBoxLayout(container)
        self._ops_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._ops_rows_layout.setSpacing(4)
        self._ops_rows_layout.addStretch(1)
        scroll.setWidget(container)
        panel_layout.addWidget(scroll)

        central_layout.addWidget(panel)
        panel.hide()
        self.operation_center_panel = panel

    def build_jobs_status_button(self):
        """Small jobs indicator in the status bar; toggles the panel."""
        button = QPushButton("")
        button.setFlat(True)
        button.setVisible(False)
        button.clicked.connect(self.toggle_operation_center)
        return button

    def toggle_operation_center(self):
        panel = getattr(self, "operation_center_panel", None)
        if panel is None:
            return
        panel.setVisible(not panel.isVisible())

    def hide_operation_center(self):
        """Hiding never cancels: jobs keep running in the background."""
        panel = getattr(self, "operation_center_panel", None)
        if panel is not None:
            panel.hide()

    def show_operation_center(self):
        panel = getattr(self, "operation_center_panel", None)
        if panel is not None:
            panel.show()

    # ─── Job registration ──────────────────────────────────────

    def _register_worker(self, worker, label: str, finished_callback=None, retry_factory=None):
        """Register a worker, draw its row and queue it.

        ``retry_factory`` (optional callable returning a new equivalent
        worker) enables a Retry button when the job fails.
        """
        self._worker_labels[worker] = label
        self._worker_progress[worker] = 0
        self._job_states[worker] = "queued"
        if retry_factory is not None:
            self._retry_factories[worker] = retry_factory

        if hasattr(worker, "progress"):
            worker.progress.connect(lambda v, w=worker: self._on_worker_progress(w, v))
        for signal_name in ("file_copied", "file_deleted"):
            signal = getattr(worker, signal_name, None)
            if signal is not None:
                try:
                    signal.connect(lambda p, w=worker: self._on_worker_file_event(w, p))
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

        self._add_job_row(worker, label)
        self.show_operation_center()
        self._update_jobs_summary()
        self.statusBar().showMessage(self.tr("Queued: {label}").format(label=label), 3000)
        self._operation_queue.enqueue(worker)

    def _add_job_row(self, worker, label: str):
        row = QFrame()
        row.setObjectName("operationRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 2, 2, 2)
        name = QLabel(label, row)
        bar = QProgressBar(row)
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setMinimumWidth(140)
        pause_button = QPushButton(app_icon("media-playback-pause", "media-playback-start"), "", row)
        pause_button.setToolTip(self.tr("Pause"))
        pause_button.setFlat(True)
        pause_button.setFixedWidth(28)
        pause_button.clicked.connect(lambda checked=False, w=worker: self._toggle_pause(w))
        retry_button = QPushButton(app_icon("view-refresh", "edit-redo"), "", row)
        retry_button.setToolTip(self.tr("Retry"))
        retry_button.setFlat(True)
        retry_button.setFixedWidth(28)
        retry_button.setVisible(False)
        retry_button.clicked.connect(lambda checked=False, w=worker: self._retry_job(w))
        cancel_button = QPushButton(app_icon("process-stop", "dialog-cancel"), "", row)
        cancel_button.setToolTip(self.tr("Cancel"))
        cancel_button.setFlat(True)
        cancel_button.setFixedWidth(28)
        cancel_button.clicked.connect(lambda checked=False, w=worker: self._cancel_job(w))
        layout.addWidget(name, 2)
        layout.addWidget(bar, 3)
        layout.addWidget(pause_button)
        layout.addWidget(retry_button)
        layout.addWidget(cancel_button)
        self._ops_rows_layout.insertWidget(self._ops_rows_layout.count() - 1, row)
        self._job_rows[worker] = (row, name, bar, pause_button, retry_button, cancel_button)

    def _remove_job_row(self, worker):
        row_pack = self._job_rows.pop(worker, None)
        if not row_pack:
            return
        row = row_pack[0]
        self._ops_rows_layout.removeWidget(row)
        row.deleteLater()

    # ─── Job control ───────────────────────────────────────────

    def _toggle_pause(self, worker):
        if not hasattr(worker, "pause"):
            return
        if getattr(worker, "is_paused", False):
            worker.resume()
            self._job_states[worker] = "running"
        else:
            worker.pause()
            self._job_states[worker] = "paused"
        self._refresh_job_row(worker)
        self._update_jobs_summary()

    def _cancel_job(self, worker):
        self._operation_queue.cancel_worker(worker)
        self._job_states[worker] = "cancelling"
        self.statusBar().showMessage(self.tr("Cancelling {label}...").format(label=self._worker_labels.get(worker, "")), 3000)

    def _retry_job(self, worker):
        factory = self._retry_factories.pop(worker, None)
        label = self._worker_labels.get(worker, self.tr("Operation"))
        owned_by_row = worker in self._job_rows
        if factory is None:
            return
        if owned_by_row:
            self._remove_job_row(worker)
        self._worker_labels.pop(worker, None)
        self._worker_progress.pop(worker, None)
        self._job_states.pop(worker, None)
        new_worker = factory()
        self._register_worker(new_worker, label, retry_factory=factory)

    def cancel_all_operations(self):
        for worker in list(self._job_states):
            if self._job_states.get(worker) in {"queued", "running", "paused", "cancelling"}:
                self._cancel_job(worker)
        self.statusBar().showMessage(self.tr("Cancelling all operations..."), 3000)

    def clear_completed_operations(self):
        """Remove rows of finished jobs; keep queued/running/paused rows."""
        for worker, state in list(self._job_states.items()):
            if state not in {"queued", "running", "paused", "cancelling"}:
                self._remove_job_row(worker)
                del self._job_states[worker]
                self._worker_labels.pop(worker, None)
                self._worker_progress.pop(worker, None)
                self._retry_factories.pop(worker, None)
        self._update_jobs_summary()
        if not self._job_states:
            self.hide_operation_center()

    # ─── Progress plumbing ─────────────────────────────────────

    def _on_queued_worker_started(self, worker):
        if worker not in self._active_workers:
            self._active_workers.append(worker)
        self.app_state.operation_started()
        self._job_states[worker] = "running"
        self._refresh_job_row(worker)
        self._update_jobs_summary()

    def _on_worker_progress(self, worker, value: int):
        self._worker_progress[worker] = int(value)
        row_pack = self._job_rows.get(worker)
        if row_pack:
            row_pack[2].setValue(int(value))
        self._update_jobs_summary()

    def _on_worker_file_event(self, worker, path: str):
        self._current_file = path

    def _on_worker_finished(self, worker, success, message):
        try:
            self._active_workers.remove(worker)
        except ValueError:
            pass
        self.app_state.operation_finished()
        self._worker_progress[worker] = 100 if success else self._worker_progress.get(worker, 0)
        if self._job_states.get(worker) == "cancelling":
            self._job_states[worker] = "cancelled"
        else:
            self._job_states[worker] = "completed" if success else "failed"
        self._refresh_job_row(worker)
        self._update_jobs_summary()
        # Discreet completion/error notice
        if self._job_states[worker] == "failed":
            self.statusBar().showMessage(self.tr("Failed: {label}").format(label=self._worker_labels.get(worker, "")), 5000)
        elif not self._active_workers and self._operation_queue.pending_count == 0:
            self.statusBar().showMessage(self.tr("All operations completed"), 5000)

    def _refresh_job_row(self, worker):
        row_pack = self._job_rows.get(worker)
        if not row_pack:
            return
        _row, name, bar, pause_button, retry_button, cancel_button = row_pack
        state = self._job_states.get(worker, "queued")
        label = self._worker_labels.get(worker, self.tr("Operation"))
        state_text = {
            "queued": self.tr("Queued"),
            "running": self.tr("Running"),
            "paused": self.tr("Paused"),
            "cancelling": self.tr("Cancelling"),
            "completed": self.tr("Completed"),
            "failed": self.tr("Failed"),
            "cancelled": self.tr("Cancelled"),
        }.get(state, "")
        name.setText(f"{label} — {state_text}")
        pause_button.setVisible(state in {"running", "paused"})
        pause_button.setToolTip(self.tr("Resume") if state == "paused" else self.tr("Pause"))
        retry_button.setVisible(
            state in {"failed", "cancelled"} and worker in self._retry_factories
        )
        cancel_button.setVisible(state in {"queued", "running", "paused"})
        bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #d0743c; }" if state == "failed"
            else ""
        )

    def _update_jobs_summary(self):
        states = list(self._job_states.values())
        active = sum(1 for s in states if s in {"queued", "running", "paused", "cancelling"})
        done = sum(1 for s in states if s in {"completed", "failed", "cancelled"})
        if self._worker_progress:
            avg = int(sum(self._worker_progress.values()) / len(self._worker_progress))
        else:
            avg = 0
        text = self.tr("Operations: {active} active, {done} finished").format(
            active=active, done=done
        )
        if active:
            text += self.tr(" — overall {percent}%").format(percent=avg)
        self._ops_summary_label.setText(text)
        button = getattr(self, "jobs_status_button", None)
        if button is not None:
            button.setVisible(bool(self._job_states))
            button.setText(self.tr("Jobs {active}").format(active=active))

    # Legacy kept-API compatibility shim (unused internally now).
    def _show_progress(self, title: str, label: str):
        self.show_operation_center()
