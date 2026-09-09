"""Editor dialog for automatic appearance rules (backlog P2).

Left: the ordered list of rules (drag order = evaluation order). Right: a
form to edit the selected rule's condition and effect. The dialog loads the
current `highlight_rules` from config, lets the user edit them, and on
accept writes the (sanitized) list back and triggers a repaint.

The rule *evaluation* lives in `lfmapp/services/highlight_service.py`; this
class is pure wiring between that model and the widgets.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from lfmapp.services.highlight_service import (
    HighlightRule,
    rules_from_config,
)


# file_type values offered by the condition combo (mirrors SearchFilters).
_FILE_TYPES = ["any", "file", "folder", "image", "document", "audio", "video", "archive"]


def _color_button(initial: str) -> QPushButton:
    btn = QPushButton(initial or "")
    btn.setProperty("hex", initial or "")
    if initial:
        btn.setStyleSheet(f"background: {initial};")
    btn.setFixedWidth(60)
    return btn


def _open_color_picker(parent, initial: str) -> str:
    start = QColor(initial) if initial else QColor("#4a90e2")
    chosen = QColorDialog.getColor(start, parent, parent.tr("Pick color"))
    return chosen.name() if chosen.isValid() else ""


class HighlightRulesDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle(self.tr("Highlighting Rules"))
        self.setMinimumSize(640, 460)
        self.resize(720, 520)

        self._rules: list[HighlightRule] = rules_from_config(
            config.get_highlight_rules()
        )
        self._loading = False

        self._build_ui()
        self._reload_list()

    # -- UI ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        self._enable_cb = QCheckBox(self.tr("Enable appearance highlighting"))
        self._enable_cb.setChecked(self._config.highlighting_enabled)
        root.addWidget(self._enable_cb)

        body = QHBoxLayout()
        root.addLayout(body, 1)

        # --- left: rule list + add/remove/move buttons ---
        left = QVBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list, 1)

        btns = QHBoxLayout()
        add_btn = QPushButton(self.tr("Add"))
        add_btn.clicked.connect(self._add_rule)
        del_btn = QPushButton(self.tr("Delete"))
        del_btn.clicked.connect(self._delete_rule)
        up_btn = QPushButton(self.tr("Up"))
        up_btn.clicked.connect(lambda: self._move_rule(-1))
        down_btn = QPushButton(self.tr("Down"))
        down_btn.clicked.connect(lambda: self._move_rule(1))
        for b in (add_btn, del_btn, up_btn, down_btn):
            btns.addWidget(b)
        left.addLayout(btns)
        body.addLayout(left)

        # --- right: detail editor ---
        self._editor = QWidget()
        self._editor.setEnabled(False)
        form = QFormLayout(self._editor)

        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._capture)
        form.addRow(self.tr("Rule name"), self._name_edit)

        self._enabled_cb = QCheckBox(self.tr("This rule is active"))
        self._enabled_cb.stateChanged.connect(self._capture)
        form.addRow(self._enabled_cb)

        cond = QGroupBox(self.tr("Condition (blank = any)"))
        cform = QFormLayout(cond)
        self._glob_edit = QLineEdit()
        self._glob_edit.setPlaceholderText("*.jpg, report_??.pdf")
        self._glob_edit.textChanged.connect(self._capture)
        cform.addRow(self.tr("Name pattern"), self._glob_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItems(_FILE_TYPES)
        self._type_combo.currentTextChanged.connect(self._capture)
        cform.addRow(self.tr("Type"), self._type_combo)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(self.tr("substring of the path"))
        self._path_edit.textChanged.connect(self._capture)
        cform.addRow(self.tr("Path contains"), self._path_edit)

        self._tag_edit = QLineEdit()
        self._tag_edit.textChanged.connect(self._capture)
        cform.addRow(self.tr("Tag"), self._tag_edit)

        self._min_size = QSpinBox()
        self._min_size.setRange(0, 1_000_000_000)
        self._min_size.setSuffix(" B")
        self._min_size.valueChanged.connect(self._capture)
        cform.addRow(self.tr("Min size"), self._min_size)

        self._max_size = QSpinBox()
        self._max_size.setRange(0, 1_000_000_000)
        self._max_size.setSuffix(" B")
        self._max_size.valueChanged.connect(self._capture)
        cform.addRow(self.tr("Max size"), self._max_size)
        form.addRow(cond)

        eff = QGroupBox(self.tr("Effect"))
        eform = QFormLayout(eff)
        self._fg_btn = _color_button("")
        self._fg_btn.clicked.connect(lambda: self._pick_color(self._fg_btn))
        eform.addRow(self.tr("Text color"), self._fg_btn)
        self._bg_btn = _color_button("")
        self._bg_btn.clicked.connect(lambda: self._pick_color(self._bg_btn))
        eform.addRow(self.tr("Background"), self._bg_btn)
        self._bold_cb = QCheckBox()
        self._bold_cb.stateChanged.connect(self._capture)
        eform.addRow(self.tr("Bold"), self._bold_cb)
        self._italic_cb = QCheckBox()
        self._italic_cb.stateChanged.connect(self._capture)
        eform.addRow(self.tr("Italic"), self._italic_cb)
        self._icon_edit = QLineEdit()
        self._icon_edit.setPlaceholderText("overlay icon name, e.g. emblem-important")
        self._icon_edit.textChanged.connect(self._capture)
        eform.addRow(self.tr("Overlay icon"), self._icon_edit)
        self._stop_cb = QCheckBox(self.tr("Stop at first match"))
        self._stop_cb.stateChanged.connect(self._capture)
        eform.addRow(self._stop_cb)
        form.addRow(eff)

        body.addWidget(self._editor, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # -- list management -----------------------------------------------------

    def _display_name(self, rule: HighlightRule, index: int) -> str:
        if rule.name:
            label = rule.name
        else:
            label = rule.name_glob or rule.file_type or rule.tag or self.tr("(all files)")
        if not rule.enabled:
            label = f"({label})"
        return f"{index + 1}. {label}"

    def _reload_list(self, keep: int = -1):
        self._list.clear()
        for i, rule in enumerate(self._rules):
            item = QListWidgetItem(self._display_name(rule, i))
            if rule.has_effect():
                item.setForeground(QColor(rule.fg_color)) if rule.fg_color else None
            self._list.addItem(item)
        if 0 <= keep < len(self._rules):
            self._list.setCurrentRow(keep)

    def _current_index(self) -> int:
        return self._list.currentRow()

    def _add_rule(self):
        self._rules.append(HighlightRule(name=self.tr("New rule"), fg_color="#d32f2f", bold=True))
        self._reload_list(keep=len(self._rules) - 1)

    def _delete_rule(self):
        idx = self._current_index()
        if idx < 0:
            return
        del self._rules[idx]
        self._reload_list(keep=min(idx, len(self._rules) - 1))

    def _move_rule(self, delta: int):
        idx = self._current_index()
        new = idx + delta
        if idx < 0 or new < 0 or new >= len(self._rules):
            return
        self._rules[idx], self._rules[new] = self._rules[new], self._rules[idx]
        self._reload_list(keep=new)

    def _on_select(self, row: int):
        self._loading = True
        if 0 <= row < len(self._rules):
            self._editor.setEnabled(True)
            self._load_rule(self._rules[row])
        else:
            self._editor.setEnabled(False)
            self._clear_editor()
        self._loading = False

    # -- editor <-> rule -----------------------------------------------------

    def _load_rule(self, rule: HighlightRule):
        self._name_edit.setText(rule.name)
        self._enabled_cb.setChecked(rule.enabled)
        self._glob_edit.setText(rule.name_glob)
        self._type_combo.setCurrentText(rule.file_type if rule.file_type in _FILE_TYPES else "any")
        self._path_edit.setText(rule.path_contains)
        self._tag_edit.setText(rule.tag)
        self._min_size.setValue(rule.min_size or 0)
        self._max_size.setValue(rule.max_size or 0)
        self._set_color_button(self._fg_btn, rule.fg_color)
        self._set_color_button(self._bg_btn, rule.bg_color)
        self._bold_cb.setChecked(rule.bold)
        self._italic_cb.setChecked(rule.italic)
        self._icon_edit.setText(rule.overlay_icon)
        self._stop_cb.setChecked(rule.stop)

    def _clear_editor(self):
        self._name_edit.clear()
        self._glob_edit.clear()
        self._path_edit.clear()
        self._tag_edit.clear()
        self._icon_edit.clear()

    def _capture(self, *_args):
        if self._loading:
            return
        idx = self._current_index()
        if idx < 0 or idx >= len(self._rules):
            return
        rule = HighlightRule(
            name=self._name_edit.text().strip(),
            enabled=self._enabled_cb.isChecked(),
            name_glob=self._glob_edit.text().strip(),
            file_type=self._type_combo.currentText(),
            path_contains=self._path_edit.text().strip(),
            tag=self._tag_edit.text().strip(),
            min_size=self._min_size.value() or None,
            max_size=self._max_size.value() or None,
            fg_color=self._fg_btn.property("hex") or "",
            bg_color=self._bg_btn.property("hex") or "",
            bold=self._bold_cb.isChecked(),
            italic=self._italic_cb.isChecked(),
            overlay_icon=self._icon_edit.text().strip(),
            stop=self._stop_cb.isChecked(),
        )
        self._rules[idx] = rule
        self._list.item(idx).setText(self._display_name(rule, idx))

    def _pick_color(self, button: QPushButton):
        chosen = _open_color_picker(self, button.property("hex") or "")
        if chosen:
            self._set_color_button(button, chosen)
            self._capture()

    def _set_color_button(self, button: QPushButton, hex_color: str):
        button.setProperty("hex", hex_color or "")
        button.setText(hex_color)
        button.setStyleSheet(f"background: {hex_color};" if hex_color else "")

    # -- accept --------------------------------------------------------------

    def _on_accept(self):
        for i, rule in enumerate(self._rules):
            if not rule.has_effect():
                QMessageBox.warning(
                    self,
                    self.tr("Invalid rule"),
                    self.tr("Rule {n} has no visible effect; give it a color, font or icon.").format(n=i + 1),
                )
                return
        payload = [r.to_dict() for r in self._rules]
        self._config.set_highlight_rules(payload)
        self._config.set_highlighting_enabled(self._enable_cb.isChecked())
        self.accept()

    @staticmethod
    def rules_summary(rules: list[HighlightRule]) -> str:
        return ", ".join(r.name or r.name_glob or r.file_type for r in rules)
