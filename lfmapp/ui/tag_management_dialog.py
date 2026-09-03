from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QInputDialog,
    QMessageBox,
)


class TagManagementDialog(QDialog):
    def __init__(self, tag_service, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Manage Tags"))
        self.resize(420, 420)

        self.tag_service = tag_service

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Tags are shared across files. Rename or delete tags below.")))

        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.tag_list, 1)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton(self.tr("Add Tag"))
        self.rename_button = QPushButton(self.tr("Rename Tag"))
        self.color_button = QPushButton(self.tr("Set Color"))
        self.delete_button = QPushButton(self.tr("Delete Tag"))
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.color_button)
        button_layout.addWidget(self.delete_button)
        layout.addLayout(button_layout)

        action_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        action_buttons.rejected.connect(self.reject)
        layout.addWidget(action_buttons)

        self.add_button.clicked.connect(self.add_tag)
        self.rename_button.clicked.connect(self.rename_tag)
        self.color_button.clicked.connect(self.set_tag_color)
        self.delete_button.clicked.connect(self.delete_tag)

        self.reload_tags()

    def reload_tags(self):
        self.tag_list.clear()
        for tag in self.tag_service.list_tags():
            display = f"{tag['name']} ({tag.get('count', 0)})"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, {
                "id": tag["id"],
                "name": tag["name"],
                "color": tag.get("color"),
            })
            if tag.get("color"):
                color = QColor(tag["color"])
                if color.isValid():
                    item.setBackground(color)
                    if color.lightness() < 128:
                        item.setForeground(QColor("#ffffff"))
            self.tag_list.addItem(item)

        self.rename_button.setEnabled(self.tag_list.count() > 0)
        self.color_button.setEnabled(self.tag_list.count() > 0)
        self.delete_button.setEnabled(self.tag_list.count() > 0)

    def selected_tag(self) -> dict[str, object] | None:
        item = self.tag_list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def add_tag(self):
        name, ok = QInputDialog.getText(self, self.tr("Add Tag"), self.tr("Tag name:"))
        if not ok or not name.strip():
            return
        self.tag_service.create_tag(name.strip())
        self.reload_tags()

    def rename_tag(self):
        selected = self.selected_tag()
        if not selected:
            return
        new_name, ok = QInputDialog.getText(
            self,
            self.tr("Rename Tag"),
            self.tr("New tag name:"),
            text=selected["name"],
        )
        if not ok or not new_name.strip():
            return
        if self.tag_service.rename_tag(int(selected["id"]), new_name.strip()):
            self.reload_tags()
        else:
            QMessageBox.warning(
                self,
                self.tr("Rename Failed"),
                self.tr("Could not rename tag. The name may already exist."),
            )

    def set_tag_color(self):
        selected = self.selected_tag()
        if not selected:
            return
        initial = QColor(selected.get("color") or "#4a90e2")
        color = QColorDialog.getColor(initial, self, self.tr("Set Tag Color"))
        if not color.isValid():
            return
        if self.tag_service.set_tag_color(int(selected["id"]), color.name()):
            self.reload_tags()
        else:
            QMessageBox.warning(
                self,
                self.tr("Color Failed"),
                self.tr("Could not update the selected tag color."),
            )

    def delete_tag(self):
        selected = self.selected_tag()
        if not selected:
            return
        confirm = QMessageBox.question(
            self,
            self.tr("Delete Tag"),
            self.tr("Delete the tag '{name}' from all files?").format(name=selected["name"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if self.tag_service.delete_tag(int(selected["id"])):
            self.reload_tags()
        else:
            QMessageBox.warning(
                self,
                self.tr("Delete Failed"),
                self.tr("Could not delete the selected tag."),
            )
