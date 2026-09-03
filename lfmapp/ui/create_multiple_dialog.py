from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QTextEdit,
)


class CreateMultipleDialog(QDialog):
    """Dialog for creating several files or folders at once."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Create Multiple Items"))
        self.resize(420, 320)

        layout = QFormLayout(self)

        self.item_type_combo = QComboBox()
        self.item_type_combo.addItem(self.tr("Folders"), "folder")
        self.item_type_combo.addItem(self.tr("Files"), "file")
        layout.addRow(self.tr("Create:"), self.item_type_combo)

        self.names_edit = QTextEdit()
        self.names_edit.setPlaceholderText(self.tr("One name per line"))
        layout.addRow(self.tr("Names:"), self.names_edit)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def item_type(self) -> str:
        return self.item_type_combo.currentData()

    def names(self) -> list[str]:
        return self.names_edit.toPlainText().splitlines()
