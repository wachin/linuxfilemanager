from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("About Linux File Manager"))
        self.resize(760, 360)

        root_layout = QVBoxLayout(self)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(24)
        root_layout.addLayout(content_layout)

        content_layout.addWidget(self._build_icon_panel())
        content_layout.addWidget(self._build_text_panel(), 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root_layout.addWidget(buttons)

    def _build_icon_panel(self):
        panel = QWidget(self)
        panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)

        icon_label = QLabel(panel)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setMinimumWidth(240)
        icon = QIcon(str(self._icon_path()))
        pixmap = icon.pixmap(192, 192)
        icon_label.setPixmap(pixmap)

        layout.addStretch(1)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        return panel

    def _build_text_panel(self):
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(10)

        text_label = QLabel(panel)
        text_label.setWordWrap(True)
        text_label.setTextFormat(Qt.TextFormat.RichText)
        text_label.setOpenExternalLinks(True)
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        text_label.setText(
            self.tr(
                "<h2>Linux File Manager</h2>"
                "<p>A modular Linux file manager focused on practical, efficient everyday file management.</p>"
                "<p><b>Email:</b> <a href='mailto:linuxfrontier@proton.me'>linuxfrontier@proton.me</a></p>"
                "<p><b>Web page:</b> <a href='https://github.com/wachin/linuxfilemanager'>https://github.com/wachin/linuxfilemanager</a></p>"
                "<p><b>Copyright:</b> © 2026 Washington Indacochea Delgado</p>"
                "<p><b>License:</b> GPL3</p>"
                "<p><b>Technologies used:</b> Python 3, PyQt6, Qt 6, XDG desktop integration, GVfs, and standard Linux filesystem services.</p>"
            )
        )
        layout.addWidget(text_label)
        layout.addStretch(1)
        return panel

    def _icon_path(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent / "data" / "icons" / "linux-file-manager.svg"
