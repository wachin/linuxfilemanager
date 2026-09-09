"""Conflict dialog for copy/move (ROADMAP Phase 3.2).

Side-by-side comparison of the incoming item and the existing destination,
with only the actions that apply to the conflict kind, an "apply to all"
checkbox whose label states its scope, and an inline rename field.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from lfmapp.services.conflict_resolution import (
    Conflict,
    ConflictAnswer,
    ConflictResolver,
    Resolution,
    files_identical,
    source_is_newer,
    suggest_free_name,
    _validate_new_name,
)
from lfmapp.ui.icons import app_icon


def _human_size(size) -> str:
    if size is None:
        return "-"
    size = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _human_date(timestamp) -> str:
    if timestamp is None:
        return "-"
    try:
        return datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return "-"


class ConflictDialog(QDialog):
    """Ask the user how to resolve a single name conflict."""

    def __init__(self, conflict: Conflict, parent=None):
        super().__init__(parent)
        self.conflict = conflict
        self.answer = ConflictAnswer(Resolution.CANCEL)

        is_folder = conflict.kind == "folder"
        self.setWindowTitle(
            self.tr("Folder Already Exists") if is_folder else self.tr("File Already Exists")
        )
        layout = QVBoxLayout(self)

        message = QLabel(
            self.tr(
                "A folder named “{name}” already exists at the destination."
            ).format(name=conflict.existing.name)
            if is_folder
            else self.tr(
                "A file named “{name}” already exists at the destination."
            ).format(name=conflict.existing.name)
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        layout.addLayout(self._build_comparison())

        # Keep Both preview / inline rename
        self._suggested_name = suggest_free_name(
            Path(conflict.source.name), Path(conflict.existing.parent)
        )
        name_form = QFormLayout()
        self.keep_both_label = QLabel(self.tr("Will be saved as: {name}").format(name=self._suggested_name))
        self.rename_edit = QLineEdit(conflict.existing.name)
        name_form.addRow(self.tr("New name:"), self.rename_edit)
        layout.addWidget(self.keep_both_label)
        layout.addLayout(name_form)
        self.rename_edit.textChanged.connect(self._on_name_changed)

        scope = self.tr("folders") if is_folder else self.tr("files")
        self.apply_all_checkbox = QCheckBox(
            self.tr("Apply to all remaining {scope} conflicts").format(scope=scope)
        )
        layout.addWidget(self.apply_all_checkbox)

        # Buttons: only the ones that apply to this conflict kind.
        buttons = QGridLayout()
        identical = (not is_folder) and files_identical(
            Path(conflict.source), Path(conflict.existing)
        )
        newer_source = source_is_newer(Path(conflict.source), Path(conflict.existing))
        if is_folder:
            self._add_button(buttons, 0, self.tr("Merge"), self._on_merge, "document-merge", "Ctrl+M", row=1)
            self._add_button(buttons, 1, self.tr("Skip"), self._on_skip, "process-stop", "Ctrl+S", row=1)
            self._add_button(buttons, 2, self.tr("Keep Both"), self._on_keep_both, "edit-copy", "Ctrl+K", row=1)
            self._add_button(buttons, 3, self.tr("Rename"), self._on_rename, "edit-rename", "Ctrl+R", row=1)
            self._add_button(buttons, 4, self.tr("Cancel"), self.reject, "dialog-cancel", "Esc", row=1)
            self._add_button(buttons, 0, self.tr("Keep Newer"), self._on_keep_newer, "chronometer", "Ctrl+N", row=2)
            self._add_button(buttons, 1, self.tr("Rename Old"), self._on_rename_old, "document-save-as", "Ctrl+O", row=2)
        else:
            self._add_button(buttons, 0, self.tr("Replace"), self._on_replace, "edit-redo", "Ctrl+P", row=1)
            self._add_button(buttons, 1, self.tr("Skip"), self._on_skip, "process-stop", "Ctrl+S", row=1)
            self._add_button(buttons, 2, self.tr("Keep Both"), self._on_keep_both, "edit-copy", "Ctrl+K", row=1)
            self._add_button(buttons, 3, self.tr("Rename"), self._on_rename, "edit-rename", "Ctrl+R", row=1)
            self._add_button(buttons, 4, self.tr("Cancel"), self.reject, "dialog-cancel", "Esc", row=1)
            # Keep Newer only makes sense when the two sides differ in date.
            self._keep_newer_button = self._add_button(
                buttons, 0, self.tr("Keep Newer"), self._on_keep_newer,
                "chronometer", "Ctrl+N", row=2,
            )
            self._keep_newer_button.setToolTip(
                self.tr("The source is newer — overwrite") if newer_source
                else self.tr("The existing file is newer — keep it (skip)")
            )
            # Skip Identical only applies when the two files are the same.
            self._skip_identical_button = self._add_button(
                buttons, 1, self.tr("Skip Identical"), self._on_skip_identical,
                "dialog-check-outline", "Ctrl+I", row=2,
            )
            self._skip_identical_button.setEnabled(identical)
            self._skip_identical_button.setToolTip(
                self.tr("These files are identical (same size and date)") if identical
                else self.tr("Disabled: the files are not identical")
            )
            self._add_button(buttons, 2, self.tr("Rename Old"), self._on_rename_old, "document-save-as", "Ctrl+O", row=2)
        layout.addLayout(buttons)

    # ─── UI construction ───────────────────────────────────────

    def _build_comparison(self) -> QGridLayout:
        grid = QGridLayout()
        source = self.conflict.source_info
        existing = self.conflict.existing_info

        source_group = QGroupBox(self.tr("Source"), self)
        existing_group = QGroupBox(self.tr("Destination (will be replaced)"), self)
        for group, info, icon in (
            (source_group, source, "document-import"),
            (existing_group, existing, "dialog-warning"),
        ):
            form = QFormLayout(group)
            form.addRow(self.tr("Name:"), QLabel(info["name"]))
            location = QLabel(info["location"])
            location.setWordWrap(True)
            form.addRow(self.tr("Location:"), location)
            form.addRow(self.tr("Size:"), QLabel(_human_size(info["size"])))
            form.addRow(self.tr("Modified:"), QLabel(_human_date(info["modified"])))
        grid.addWidget(source_group, 0, 0)
        grid.addWidget(existing_group, 0, 1)
        return grid

    def _add_button(self, layout: QGridLayout, column: int, text, slot, icon, shortcut, row: int = 1):
        button = QPushButton(app_icon(icon), text, self)
        button.setShortcut(shortcut)
        button.clicked.connect(slot)
        layout.addWidget(button, row, column)
        return button

    # ─── Decisions ─────────────────────────────────────────────

    def _accept_with(self, resolution: Resolution, new_name: str | None = None):
        self.answer = ConflictAnswer(resolution, new_name)
        self.accept()

    def _on_replace(self):
        self._accept_with(Resolution.REPLACE)

    def _on_skip(self):
        self._accept_with(Resolution.SKIP)

    def _on_merge(self):
        self._accept_with(Resolution.MERGE)

    def _on_keep_both(self):
        self._accept_with(Resolution.KEEP_BOTH, self._suggested_name)

    def _on_rename(self):
        name = self.rename_edit.text().strip()
        if not _validate_new_name(name):
            self.rename_edit.setStyleSheet("border: 1px solid red;")
            return
        self._accept_with(Resolution.RENAME, name)

    def _on_keep_newer(self):
        self._accept_with(Resolution.KEEP_NEWER)

    def _on_skip_identical(self):
        self._accept_with(Resolution.SKIP_IDENTICAL)

    def _on_rename_old(self):
        self._accept_with(Resolution.RENAME_OLD)

    def _on_name_changed(self, text: str):
        _ = text
        self.rename_edit.setStyleSheet("")

    def reject(self):
        # Closing the dialog (Esc / X) cancels the whole operation.
        self.answer = ConflictAnswer(Resolution.CANCEL)
        super().reject()

    @property
    def apply_to_all(self) -> bool:
        return self.apply_all_checkbox.isChecked()


__all__ = ["ConflictDialog", "GuiConflictResolver"]


class GuiConflictResolver(QObject):
    """Thread bridge between workers and the conflict dialog.

    The workers run in their own threads; this object lives in the GUI
    thread. Its callable is safe to use from the worker thread: the
    ``requested`` signal is connected with a BlockingQueuedConnection, so
    the worker blocks until the user decides. "Apply to all" answers are
    remembered for the current operation only (a new resolver is created
    per user action).
    """

    requested = pyqtSignal(object)

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._memory = ConflictResolver()
        self._result: ConflictAnswer | None = None
        self.requested.connect(
            self._show_dialog, Qt.ConnectionType.BlockingQueuedConnection
        )

    def __call__(self, conflict: Conflict) -> ConflictAnswer:
        remembered = self._memory.remembered(conflict)
        if remembered is not None:
            return remembered
        self._result = None
        self.requested.emit(conflict)
        return self._result or ConflictAnswer(Resolution.CANCEL)

    def _show_dialog(self, conflict: Conflict):
        dialog = ConflictDialog(conflict, self._window)
        dialog.exec()
        answer = dialog.answer
        if dialog.apply_to_all:
            self._memory.remember(conflict, answer)
        self._result = answer
