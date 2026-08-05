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
        alias = " ".join(command.get("alias", [])).casefold()
        enabled = command.get("enabled", True)
        score = 0
        title_tokens = title.split()
        alias_tokens = alias.split()
        if query == title or query == alias or query == category:
            score += 40
        if query in title:
            score += 30
        if query in alias:
            score += 20
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
        if alias.startswith(query):
            score += 8
        if query in title_tokens or query in alias_tokens:
            score += 25
        if any(token.startswith(query) for token in alias_tokens):
            score += 12
        if not enabled:
            score -= 50
        return score

    def _populate_items(self, filtered_commands: list[dict] | None = None) -> None:
        self.command_list.clear()
        if filtered_commands is None:
            commands = sorted(
                self._commands,
                key=lambda command: (
                    not command.get("enabled", True),
                    command.get("category", ""),
                    command.get("title", ""),
                ),
            )
        else:
            commands = filtered_commands
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
            alias = " ".join(command.get("alias", [])).casefold()
            if all(
                token in title or token in shortcut or token in category or token in alias
                for token in tokens
            ):
                filtered.append((self._command_score(command, query), command))

        filtered.sort(
            key=lambda entry: (
                -entry[0],
                not entry[1].get("enabled", True),
                entry[1].get("category", ""),
                entry[1].get("title", ""),
            )
        )
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
