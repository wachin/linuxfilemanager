from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class CommandPaletteDialog(QDialog):
    """Simple command palette for quick keyboard-driven actions."""

    def __init__(self, commands: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Command Palette"))
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText(self.tr("Type a command or shortcut..."))
        self.filter_edit.textChanged.connect(self._filter_commands)
        layout.addWidget(self.filter_edit)

        self.command_list = QListWidget(self)
        self.command_list.itemActivated.connect(self._activate_selected)
        layout.addWidget(self.command_list)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, parent=self)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._commands = [dict(command, enabled=command.get("enabled", True)) for command in commands]
        self._populate_items()
        self.filter_edit.setFocus()

    def _command_text(self, command: dict) -> str:
        title = command.get("title", "")
        category = command.get("category", "") or ""
        shortcut = command.get("shortcut") or ""
        parts = [title]
        if category:
            parts.append(f"— {category}")
        if shortcut:
            parts.append(f"({shortcut})")
        if not command.get("enabled", True):
            parts.append(self.tr("[disabled]"))
        return " ".join(parts)

    def _command_score(self, command: dict, query: str) -> int:
        title = command.get("title", "").casefold()
        shortcut = (command.get("shortcut") or "").casefold()
        category = (command.get("category") or "").casefold()
        score = 0
        if query in title:
            score += 30
        if query in shortcut:
            score += 20
        if query in category:
            score += 10
        if title.startswith(query):
            score += 20
        if shortcut.startswith(query):
            score += 10
        if category.startswith(query):
            score += 5
        return score

    def _populate_items(self, filtered_commands: list[dict] | None = None) -> None:
        self.command_list.clear()
        commands = filtered_commands if filtered_commands is not None else self._commands
        for command in commands:
            item = QListWidgetItem(self._command_text(command))
            item.setData(Qt.ItemDataRole.UserRole, command)
            if not command.get("enabled", True):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.command_list.addItem(item)
        if self.command_list.count() > 0:
            self.command_list.setCurrentRow(0)

    def _filter_commands(self, text: str) -> None:
        query = text.strip().casefold()
        if not query:
            self._populate_items()
            return

        tokens = query.split()
        filtered = []
        for command in self._commands:
            title = command.get("title", "").casefold()
            shortcut = (command.get("shortcut") or "").casefold()
            category = (command.get("category") or "").casefold()
            if all(token in title or token in shortcut or token in category for token in tokens):
                filtered.append((self._command_score(command, query), command))

        filtered.sort(key=lambda entry: (-entry[0], entry[1].get("title", "")))
        self._populate_items([command for _, command in filtered])

    def _activate_selected(self, item: QListWidgetItem) -> None:
        command = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(command, dict) or not command.get("enabled", True):
            return
        callback = command.get("callback")
        if callable(callback):
            callback()
            self.accept()

    def exec(self) -> int:
        if self.command_list.count() == 0:
            self._populate_items()
        return super().exec()
