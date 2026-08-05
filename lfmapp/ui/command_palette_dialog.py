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

        self._commands = commands
        self._populate_items()
        self.filter_edit.setFocus()

    def _command_text(self, command: dict) -> str:
        text = command.get("title", "")
        shortcut = command.get("shortcut")
        if shortcut:
            text = f"{text}    ({shortcut})"
        return text

    def _populate_items(self) -> None:
        self.command_list.clear()
        for command in self._commands:
            item = QListWidgetItem(self._command_text(command))
            item.setData(Qt.ItemDataRole.UserRole, command)
            self.command_list.addItem(item)
        if self.command_list.count() > 0:
            self.command_list.setCurrentRow(0)

    def _filter_commands(self, text: str) -> None:
        query = text.strip().casefold()
        self.command_list.clear()
        for command in self._commands:
            title = command.get("title", "")
            shortcut = command.get("shortcut", "") or ""
            category = command.get("category", "") or ""
            if (
                query in title.casefold()
                or query in shortcut.casefold()
                or query in category.casefold()
            ):
                item = QListWidgetItem(self._command_text(command))
                item.setData(Qt.ItemDataRole.UserRole, command)
                self.command_list.addItem(item)
        if self.command_list.count() > 0:
            self.command_list.setCurrentRow(0)

    def _activate_selected(self, item: QListWidgetItem) -> None:
        command = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(command, dict):
            return
        callback = command.get("callback")
        if callable(callback):
            callback()
            self.accept()

    def exec(self) -> int:
        if self.command_list.count() == 0:
            self._populate_items()
        return super().exec()
