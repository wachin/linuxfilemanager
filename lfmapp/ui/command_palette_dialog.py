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

    def __init__(self, commands: list[tuple[str, callable]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Command Palette"))
        self.resize(460, 380)

        layout = QVBoxLayout(self)
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText(self.tr("Type a command..."))
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

    def _populate_items(self) -> None:
        self.command_list.clear()
        for title, _callback in self._commands:
            self.command_list.addItem(QListWidgetItem(title))
        if self.command_list.count() > 0:
            self.command_list.setCurrentRow(0)

    def _filter_commands(self, text: str) -> None:
        query = text.strip().casefold()
        self.command_list.clear()
        for title, _callback in self._commands:
            if query in title.casefold():
                self.command_list.addItem(QListWidgetItem(title))
        if self.command_list.count() > 0:
            self.command_list.setCurrentRow(0)

    def _activate_selected(self, item: QListWidgetItem) -> None:
        title = item.text()
        for command_title, callback in self._commands:
            if command_title == title:
                callback()
                self.accept()
                return

    def exec(self) -> int:
        if self.command_list.count() == 0:
            self._populate_items()
        return super().exec()
