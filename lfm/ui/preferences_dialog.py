from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class PreferencesDialog(QDialog):
    STYLE_OPTIONS = [
        ("Normal", 400, False),
        ("Bold", 700, False),
        ("Italic", 400, True),
        ("Bold Italic", 700, True),
    ]

    def __init__(self, config, terminal_service, parent=None):
        super().__init__(parent)
        self.config = config
        self.terminal_service = terminal_service
        self.setWindowTitle(self.tr("Preferences"))
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_interface_group())
        layout.addWidget(self._build_window_group())
        layout.addWidget(self._build_font_group())
        layout.addWidget(self._build_terminal_group())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_from_config()
        self._update_font_preview()

    def _build_interface_group(self):
        group = QGroupBox(self.tr("Interface"))
        layout = QVBoxLayout(group)
        self.sidebar_checkbox = QCheckBox(self.tr("Show sidebar"))
        self.preview_checkbox = QCheckBox(self.tr("Show preview panel"))
        self.hidden_files_checkbox = QCheckBox(self.tr("Show hidden files"))
        self.file_extensions_checkbox = QCheckBox(self.tr("Show file extensions"))
        self.selection_checkboxes_checkbox = QCheckBox(self.tr("Show selection checkboxes"))
        self.remember_folder_view_checkbox = QCheckBox(self.tr("Remember folder view"))

        for widget in (
            self.sidebar_checkbox,
            self.preview_checkbox,
            self.hidden_files_checkbox,
            self.file_extensions_checkbox,
            self.selection_checkboxes_checkbox,
            self.remember_folder_view_checkbox,
        ):
            layout.addWidget(widget)
        return group

    def _build_window_group(self):
        group = QGroupBox(self.tr("Window"))
        layout = QFormLayout(group)

        self.remember_window_size_checkbox = QCheckBox(self.tr("Remember window size"))
        window_size_row = QWidget(self)
        window_size_layout = QHBoxLayout(window_size_row)
        window_size_layout.setContentsMargins(0, 0, 0, 0)
        window_size_layout.setSpacing(8)

        self.window_width_spin = QSpinBox(self)
        self.window_width_spin.setRange(640, 8192)
        self.window_width_spin.setSuffix(" px")
        self.window_height_spin = QSpinBox(self)
        self.window_height_spin.setRange(420, 8192)
        self.window_height_spin.setSuffix(" px")

        window_size_layout.addWidget(self.window_width_spin)
        window_size_layout.addWidget(QLabel("x", self))
        window_size_layout.addWidget(self.window_height_spin)

        layout.addRow(self.remember_window_size_checkbox)
        layout.addRow(self.tr("Default size"), window_size_row)
        return group

    def _build_font_group(self):
        group = QGroupBox(self.tr("Font"))
        layout = QFormLayout(group)

        self.font_family_combo = QFontComboBox(self)
        self.font_style_combo = QComboBox(self)
        self.font_size_spin = QSpinBox(self)
        self.font_size_spin.setRange(6, 48)

        for label, _weight, _italic in self.STYLE_OPTIONS:
            self.font_style_combo.addItem(self.tr(label))

        self.font_preview_label = QLabel(self.tr("Preview: The quick brown fox jumps over the lazy dog."))
        self.font_preview_label.setWordWrap(True)
        self.font_preview_label.setMinimumHeight(48)

        self.font_family_combo.currentFontChanged.connect(self._update_font_preview)
        self.font_style_combo.currentIndexChanged.connect(self._update_font_preview)
        self.font_size_spin.valueChanged.connect(self._update_font_preview)

        layout.addRow(self.tr("Family"), self.font_family_combo)
        layout.addRow(self.tr("Style"), self.font_style_combo)
        layout.addRow(self.tr("Size"), self.font_size_spin)
        layout.addRow(self.font_preview_label)
        return group

    def _build_terminal_group(self):
        group = QGroupBox(self.tr("Terminal"))
        layout = QFormLayout(group)

        self.terminal_combo = QComboBox(self)
        terminals = self.terminal_service.available_terminals
        if terminals:
            self.terminal_combo.addItem(self.tr("System default"), "")
            for terminal in terminals:
                self.terminal_combo.addItem(terminal, terminal)
        else:
            self.terminal_combo.addItem(self.tr("No terminal detected"), "")
            self.terminal_combo.setEnabled(False)

        layout.addRow(self.tr("Preferred terminal"), self.terminal_combo)
        return group

    def _load_from_config(self):
        self.sidebar_checkbox.setChecked(self.config.sidebar_visible)
        self.preview_checkbox.setChecked(self.config.preview_visible)
        self.hidden_files_checkbox.setChecked(self.config.show_hidden_files)
        self.file_extensions_checkbox.setChecked(self.config.show_file_extensions)
        self.selection_checkboxes_checkbox.setChecked(self.config.selection_checkboxes)
        self.remember_folder_view_checkbox.setChecked(self.config.remember_folder_view)
        self.remember_window_size_checkbox.setChecked(self.config.window_remember_size)
        self.window_width_spin.setValue(self.config.window_width)
        self.window_height_spin.setValue(self.config.window_height)

        font = QFont()
        if self.config.ui_font_family.strip():
            font.setFamily(self.config.ui_font_family.strip())
        font.setPointSize(self.config.ui_font_size)
        font.setWeight(self.config.ui_font_weight)
        font.setItalic(self.config.ui_font_italic)
        self.font_family_combo.setCurrentFont(font)
        self.font_size_spin.setValue(max(6, self.config.ui_font_size))

        style_index = 0
        for index, (_label, weight, italic) in enumerate(self.STYLE_OPTIONS):
            if weight == self.config.ui_font_weight and italic == self.config.ui_font_italic:
                style_index = index
                break
        self.font_style_combo.setCurrentIndex(style_index)

        preferred_terminal = self.config.preferred_terminal
        index = self.terminal_combo.findData(preferred_terminal)
        if index >= 0:
            self.terminal_combo.setCurrentIndex(index)

    def _update_font_preview(self):
        font = self.selected_font()
        self.font_preview_label.setFont(font)

    def selected_font(self):
        font = QFont(self.font_family_combo.currentFont())
        _label, weight, italic = self.STYLE_OPTIONS[self.font_style_combo.currentIndex()]
        font.setPointSize(self.font_size_spin.value())
        font.setWeight(weight)
        font.setItalic(italic)
        return font

    def preferences(self):
        font = self.selected_font()
        return {
            "sidebar_visible": self.sidebar_checkbox.isChecked(),
            "preview_visible": self.preview_checkbox.isChecked(),
            "show_hidden_files": self.hidden_files_checkbox.isChecked(),
            "show_file_extensions": self.file_extensions_checkbox.isChecked(),
            "selection_checkboxes": self.selection_checkboxes_checkbox.isChecked(),
            "remember_folder_view": self.remember_folder_view_checkbox.isChecked(),
            "window_remember_size": self.remember_window_size_checkbox.isChecked(),
            "window_width": self.window_width_spin.value(),
            "window_height": self.window_height_spin.value(),
            "ui_font_family": font.family(),
            "ui_font_size": font.pointSize(),
            "ui_font_weight": font.weight(),
            "ui_font_italic": font.italic(),
            "preferred_terminal": self.terminal_combo.currentData(),
        }
