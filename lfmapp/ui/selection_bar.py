"""Batch action bar shown while a selection or checkbox set is active (P2).

A slim horizontal strip that reports "N files · M folders · SIZE" and offers
the operations that act on that set: Copy, Cut, Trash, Delete, Rename,
Invert, Select By… and a Clear.  It appears just under the tabs whenever the
effective selection is non-empty and hides itself otherwise, so it never
takes space when there is nothing to batch.

The bar is intentionally thin: it emits signals and delegates every action to
MainWindow's existing operation methods (the same ones the menu / toolbar /
context menu / palette use), so all surfaces keep consuming the same action
registry and selection source (per the architecture rules).
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from lfmapp.ui.icons import app_icon


class SelectionBar(QFrame):
    """Non-modal batch action bar."""

    copy_requested = pyqtSignal()
    cut_requested = pyqtSignal()
    trash_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    rename_requested = pyqtSignal()
    invert_requested = pyqtSignal()
    select_by_requested = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("selectionBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "QFrame#selectionBar { background: rgba(96,140,190,0.20); "
            "border-radius: 6px; }"
            "QLabel { padding: 0 6px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 4)
        layout.setSpacing(6)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)
        layout.addStretch(1)

        self.select_by_button = self._button(self.tr("Select By…"), self.select_by_requested, "edit-select-all")
        self.invert_button = self._button(self.tr("Invert"), self.invert_requested, "object-flip-horizontal")
        self.copy_button = self._button(self.tr("Copy"), self.copy_requested, "edit-copy")
        self.cut_button = self._button(self.tr("Cut"), self.cut_requested, "edit-cut")
        self.rename_button = self._button(self.tr("Rename"), self.rename_requested, "edit-rename")
        self.trash_button = self._button(self.tr("Trash"), self.trash_requested, "user-trash")
        self.delete_button = self._button(self.tr("Delete"), self.delete_requested, "edit-delete")
        self.clear_button = self._button(self.tr("Clear"), self.clear_requested, "dialog-cancel")

        self.hide()

    def _button(self, text, signal, icon_name) -> QPushButton:
        btn = QPushButton(text, self)
        icon = app_icon(icon_name)
        if not icon.isNull():
            btn.setIcon(icon)
        btn.setFlat(True)
        btn.clicked.connect(lambda _=False, s=signal: s.emit())
        self.layout().addWidget(btn)
        return btn

    def update_for(self, file_count: int, folder_count: int, size_text: str) -> None:
        """Refresh the summary text and visibility from a selection summary."""
        total = file_count + folder_count
        if total == 0:
            self.hide()
            return
        parts = []
        if file_count:
            parts.append(self.tr("{n} file(s)").format(n=file_count))
        if folder_count:
            parts.append(self.tr("{n} folder(s)").format(n=folder_count))
        text = "  ·  ".join(parts)
        if size_text:
            text = f"{text}  ·  {size_text}"
        self.summary_label.setText(text)
        # Permanent destructive actions are gated by the caller (registry);
        # the bar always shows them and lets MainWindow decide enablement.
        self.show()
