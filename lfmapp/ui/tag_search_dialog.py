from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class TagSearchDialog(QDialog):
    def __init__(self, tags: list[dict], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Search by Tag"))
        self.resize(420, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Select one or more tags to search for:")))

        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for tag in tags:
            label = f"{tag['name']} ({tag.get('count', 0)})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, tag["name"])
            self.tag_list.addItem(item)
        layout.addWidget(self.tag_list, 1)

        radio_layout = QHBoxLayout()
        self.any_radio = QRadioButton(self.tr("Match any selected tag"))
        self.all_radio = QRadioButton(self.tr("Match all selected tags"))
        self.any_radio.setChecked(True)
        radio_layout.addWidget(self.any_radio)
        radio_layout.addWidget(self.all_radio)
        layout.addLayout(radio_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def selected_tags(self) -> list[str]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.tag_list.selectedItems()
            if item.data(Qt.ItemDataRole.UserRole)
        ]

    def match_all(self) -> bool:
        return self.all_radio.isChecked()
