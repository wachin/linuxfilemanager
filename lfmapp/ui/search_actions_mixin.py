"""Search methods extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from lfmapp.services import SearchFilters
from lfmapp.controllers import SearchOutcome
from lfmapp.ui.search_filter_dialog import SearchFilterDialog


class SearchActionsMixin:
    # ─── Search ────────────────────────────────────────────────

    def on_search_requested(self):
        query = self.search_edit.text().strip()
        self._start_search(query, SearchFilters())

    def on_search_filters_requested(self):
        dialog = SearchFilterDialog(self.search_edit.text().strip(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        query = dialog.query()
        filters = dialog.filters()
        self.search_edit.setText(query)
        self._start_search(query, filters)

    def _start_search(self, query: str, filters: SearchFilters):
        current_dir = self.workspace.current_path()
        if not current_dir:
            return
        self._current_search_results = []
        self._active_search_filters = filters
        # Clear previous results so stale entries never linger in the panel.
        self.preview.show_search_results([])
        self._search_controller.start(
            query,
            filters,
            root=current_dir,
            outcome=SearchOutcome(
                on_result=lambda path: self.on_search_result(path),
                on_finished=lambda count: self.on_search_finished(count),
            ),
        )

    def on_search_result(self, path):
        path = Path(path)
        self._current_search_results.append(path)
        self.preview.add_search_result(path)
        self.app_state.set_searching(True, result_count=len(self._current_search_results))

    def on_search_finished(self, count):
        self.app_state.set_searching(False, result_count=count)
        if self._active_search_filters.is_active():
            message = self.tr("Search complete with filters: {count} results").format(count=count)
        else:
            message = self.tr("Search complete: {count} results").format(count=count)
        self.statusBar().showMessage(message, 5000)

    def on_index_current_folder(self):
        current_dir = self.workspace.current_path()
        if not current_dir or not current_dir.exists():
            return
        reply = QMessageBox.question(
            self,
            self.tr("Index Folder"),
            self.tr(
                "Index all files in {path}? This will enable text index search for this folder."
            ).format(path=current_dir),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.statusBar().showMessage(self.tr("Indexing folder..."), 0)
            thread = self.indexer_service.start_index(current_dir, recursive=True)

            # Show a small progress dialog with cancel
            dlg = QDialog(self)
            dlg.setWindowTitle(self.tr("Indexing folder"))
            vlayout = QVBoxLayout(dlg)
            label = QLabel(self.tr("Indexing {path}...").format(path=current_dir))
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            cancel_btn = QPushButton(self.tr("Cancel"))
            vlayout.addWidget(label)
            vlayout.addWidget(progress_bar)
            vlayout.addWidget(cancel_btn)
            dlg.setModal(False)
            dlg.setMinimumWidth(360)

            def on_progress(v):
                try:
                    progress_bar.setValue(int(v))
                except Exception:
                    pass

            def on_finished(count):
                self.config.set_text_index_enabled(True)
                progress_bar.setValue(100)
                self.statusBar().showMessage(
                    self.tr("Indexed {count} files in {path}").format(count=count, path=current_dir),
                    5000,
                )
                dlg.accept()
                QMessageBox.information(
                    self,
                    self.tr("Index Complete"),
                    self.tr("Indexed {count} files in {path}.\nText index search is now enabled.").format(
                        count=count,
                        path=current_dir,
                    ),
                )

            def on_cancel():
                cancel_btn.setEnabled(False)
                try:
                    thread.stop()
                except Exception:
                    pass

            thread.progress.connect(on_progress)
            thread.finished.connect(on_finished)
            cancel_btn.clicked.connect(on_cancel)
            dlg.show()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr("Index Error"),
                self.tr("Could not index folder:\n{error}").format(error=exc),
            )

    def on_toggle_text_index(self):
        next_state = not self.config.text_index_enabled
        self.config.set_text_index_enabled(next_state)
        state_text = self.tr("enabled") if next_state else self.tr("disabled")
        self.statusBar().showMessage(
            self.tr("Text index search {state}").format(state=state_text),
            5000,
        )
