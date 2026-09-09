"""Paint delegate for automatic appearance rules (backlog P2).

The **only** place highlighting is rendered: it reads the resolved
`HighlightEffect` from a `HighlightEvaluator` and paints the row with the
chosen colour / font / overlay icon.  The item model is never modified
(architecture rule: data — the rules — stays separate from the visual
effect — how each row is painted), so enabling, disabling or editing the
rules only needs a view repaint, not a model reload.

Selected rows keep the selection palette (selection always wins over a
rule colour) so readability is never compromised.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPalette
from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem, QStyledItemDelegate

from lfmapp.services.highlight_service import HighlightEffect, HighlightEvaluator
from lfmapp.ui.icons import app_icon


class HighlightDelegate(QStyledItemDelegate):
    """Delegate that paints rule-based colour / font / overlay on file rows."""

    def __init__(self, model, evaluator: HighlightEvaluator, parent=None):
        super().__init__(parent)
        self._model = model
        self._evaluator = evaluator

    def _effect_for(self, index) -> HighlightEffect:
        if self._model is None or self._evaluator is None:
            return HighlightEffect()
        if not self._evaluator.enabled:
            return HighlightEffect()
        try:
            path_str = self._model.filePath(index)
        except Exception:
            return HighlightEffect()
        if not path_str:
            return HighlightEffect()
        return self._evaluator.effect_for(Path(path_str))

    def paint(self, painter, option, index):
        effect = self._effect_for(index)
        if effect.is_empty():
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)  # copy what the view prepared
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)

        if not selected:
            if effect.fg_color:
                color = QColor(effect.fg_color)
                opt.palette.setColor(QPalette.ColorRole.Text, color)
                opt.palette.setColor(QPalette.ColorRole.WindowText, color)
            if effect.bg_color:
                opt.backgroundBrush = QBrush(QColor(effect.bg_color))

        if effect.bold or effect.italic:
            font = QFont(opt.font)
            font.setBold(effect.bold)
            font.setItalic(effect.italic)
            opt.fontMetrics = QFontMetrics(font)
            opt.font = font

        widget = opt.widget
        style = widget.style() if widget is not None else self.parent().style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        if effect.overlay_icon:
            self._paint_overlay(painter, opt, effect.overlay_icon)

    def _paint_overlay(self, painter, opt, icon_name: str) -> None:
        icon = app_icon(icon_name)
        if icon.isNull():
            return
        size = 14
        pixmap = icon.pixmap(QSize(size, size))
        rect = opt.rect
        x = rect.left() + max(0, rect.width() - size - 3)
        y = rect.bottom() - size - 2
        painter.drawPixmap(x, y, pixmap)
