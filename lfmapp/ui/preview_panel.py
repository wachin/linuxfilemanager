"""Preview panel for linux-file-manager.

Right-side panel that shows file previews:
- Images: scaled thumbnail
- Videos: thumbnail frame when ffmpeg is available
- Documents: first pages or text excerpt when supported
- Text files: content preview
- Other files: metadata display

Uses PreviewWorker for background loading to avoid UI freezing.
"""

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QTextEdit, QVBoxLayout, QWidget

from lfmapp.services.preview_worker import PreviewWorker


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(360)

        self.title = QLabel(self.tr("Preview"))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-weight: bold; margin-bottom: 8px;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setVisible(False)
        self.image_label.setScaledContents(True)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText(self.tr("Select a file to preview."))

        self.details_title = QLabel(self.tr("Details"))
        self.details_title.setStyleSheet("font-weight: bold; margin-top: 4px;")
        self.details_title.setVisible(False)

        self.metadata_edit = QTextEdit()
        self.metadata_edit.setReadOnly(True)
        self.metadata_edit.setMaximumHeight(180)
        self.metadata_edit.setVisible(False)

        self.search_results = QListWidget()
        self.search_results.setVisible(False)
        self.search_results.itemActivated.connect(self._open_search_result)
        self.search_results.itemDoubleClicked.connect(self._open_search_result)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(self.title)
        layout.addWidget(self.image_label)
        layout.addWidget(self.text_edit, 1)
        layout.addWidget(self.details_title)
        layout.addWidget(self.metadata_edit)
        layout.addWidget(self.search_results, 1)

        self._preview_worker = None
        self._current_path = None

    def show_path(self, path: Path):
        """Start loading a file preview in the background."""
        self.clear()
        if not path or not path.exists():
            return

        self._current_path = path
        self.text_edit.setVisible(not path.is_dir())
        self.search_results.setVisible(False)
        self.metadata_edit.setVisible(path.is_dir())
        self.details_title.setVisible(path.is_dir())
        self.title.setText(self.tr("Preview"))
        self.text_edit.setPlainText(self.tr("Loading preview...") if not path.is_dir() else "")
        self.metadata_edit.setPlainText(self.tr("Loading details...") if path.is_dir() else "")

        # Stop any running preview worker
        if self._preview_worker is not None and self._preview_worker.isRunning():
            self._preview_worker.stop()
            self._preview_worker.wait(500)

        self._preview_worker = PreviewWorker(path)
        self._preview_worker.image_ready.connect(self._on_image_ready)
        self._preview_worker.text_ready.connect(self._on_text_ready)
        self._preview_worker.metadata_ready.connect(self._on_metadata_ready)
        self._preview_worker.start()

    def _on_image_ready(self, pixmap: QPixmap):
        """Handle image loaded by the preview worker."""
        self.image_label.setPixmap(pixmap)
        self.image_label.setVisible(True)
        self.text_edit.setVisible(False)

    def _on_text_ready(self, content: str):
        """Handle text loaded by the preview worker."""
        # Only update if this is still the current file
        self.text_edit.setVisible(True)
        self.text_edit.setPlainText(content)

    def _on_metadata_ready(self, metadata: str):
        """Handle metadata loaded by the preview worker."""
        self.details_title.setVisible(True)
        self.metadata_edit.setVisible(True)
        self.metadata_edit.setPlainText(metadata)
        if self.text_edit.toPlainText() == self.tr("Loading preview...") and not self.image_label.isVisible():
            self.text_edit.setVisible(False)

    def show_search_results(self, paths):
        """Display search results in the preview pane."""
        self.clear()
        self.title.setText(self.tr("Search Results"))
        self.image_label.setVisible(False)
        self.text_edit.setVisible(False)
        self.details_title.setVisible(False)
        self.metadata_edit.setVisible(False)
        self.search_results.setVisible(True)
        self.search_results.clear()

        if not paths:
            placeholder = QListWidgetItem(self.tr("No results found."))
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.search_results.addItem(placeholder)
            self.search_results.setEnabled(False)
            return

        self.search_results.setEnabled(True)
        for path in paths:
            item = QListWidgetItem(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.search_results.addItem(item)

    def add_search_result(self, path: Path):
        """Add a single result to the current search results list."""
        if not self.search_results.isVisible():
            self.show_search_results([path])
            return

        if not self.search_results.isEnabled():
            self.search_results.clear()
            self.search_results.setEnabled(True)

        item = QListWidgetItem(str(path))
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        self.search_results.addItem(item)

    def _open_search_result(self, item: QListWidgetItem):
        path_str = item.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path_str))

    def clear(self):
        """Clear all preview content."""
        if self._preview_worker is not None and self._preview_worker.isRunning():
            self._preview_worker.stop()
            self._preview_worker.wait(500)
            self._preview_worker = None
        self._current_path = None
        self.image_label.clear()
        self.image_label.setVisible(False)
        self.text_edit.clear()
        self.text_edit.setVisible(True)
        self.metadata_edit.clear()
        self.metadata_edit.setVisible(False)
        self.details_title.setVisible(False)
