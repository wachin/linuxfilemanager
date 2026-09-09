"""Keyboard-shortcut reference (Phase 8: accessible, searchable shortcuts view).

Lists every registered command grouped by category with its shortcut, and a
filter box that matches on title, shortcut or category — the same data the
command palette uses, but read-only and organised so a keyboard learner (or a
screen reader walking the tree) can browse every binding without triggering
anything.

It is intentionally fed a plain list of ``{title, shortcut, category}``
mappings (from ``ShortcutMap.commands()``) so the dialog has no dependency on
the window and can be tested headless.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QVBoxLayout,
)


def _norm(s: str) -> str:
    return (s or "").casefold()


class KeyboardShortcutsDialog(QDialog):
    """Read-only, searchable list of keyboard shortcuts grouped by category."""

    def __init__(self, commands: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Keyboard Shortcuts"))
        self.setMinimumSize(560, 480)
        self.resize(640, 560)
        # Normalise to dicts with the three fields we show.
        self._commands: list[dict] = [
            {
                "title": c.get("title", ""),
                "shortcut": c.get("shortcut", ""),
                "category": c.get("category", "") or self.tr("General"),
            }
            for c in commands
            if c.get("title")
        ]
        self._build()
        self._populate("")

    def _build(self) -> None:
        root = QVBoxLayout(self)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(self.tr("Search commands or shortcuts…"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._populate)
        root.addWidget(self.search_edit)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([self.tr("Command"), self.tr("Shortcut")])
        self.tree.setRootIsDecorated(True)
        self.tree.setColumnWidth(0, 380)
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.tree, 1)

    def _populate(self, query: str) -> None:
        self.tree.clear()
        q = _norm(query)
        # Group by category, sorting both categories and commands.
        by_category: dict[str, list[dict]] = {}
        for cmd in self._commands:
            if q:
                haystack = " ".join(
                    (_norm(cmd["title"]), _norm(cmd["shortcut"]), _norm(cmd["category"]))
                )
                tokens = q.split()
                if not all(tok in haystack for tok in tokens):
                    continue
            by_category.setdefault(cmd["category"], []).append(cmd)

        for category in sorted(by_category):
            top = QTreeWidgetItem(self.tree, [category, ""])
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            top.setExpanded(True)
            for cmd in sorted(by_category[category], key=lambda c: c["title"].lower()):
                child = QTreeWidgetItem(top, [cmd["title"], cmd["shortcut"]])
                # Expose the accessible full description for screen readers.
                child.setText(0, cmd["title"])
                child.setText(1, cmd["shortcut"])

    def match_count(self) -> int:
        """Total visible command rows (used by tests and for an info label)."""
        total = 0
        for i in range(self.tree.topLevelItemCount()):
            total += self.tree.topLevelItem(i).childCount()
        return total
