"""Qt adapter: build QAction objects from registry ActionSpec.

Kept separate from lfmapp.actions.registry so the registry itself stays
UI-agnostic and unit-testable without a QApplication.  Menus, toolbars and
shortcut surfaces call spec_to_action() and keep the resulting QAction; the
enablement predicates are (re)applied in bulk by apply_enablement() whenever
the context changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction, QKeySequence

if TYPE_CHECKING:
    from lfmapp.actions.registry import ActionRegistry, ActionSpec


def spec_to_action(
    spec: "ActionSpec",
    parent=None,
    *,
    translate: bool = True,
) -> QAction:
    """Create a QAction from an ActionSpec.

    The spec title is treated as translatable text (self.tr semantics belong
    to the QObject owner); pass translate=False when the title was already
    translated before building the spec.
    """
    title = spec.title
    action = QAction(title, parent)
    if spec.icon is not None:
        from PyQt6.QtGui import QIcon

        if isinstance(spec.icon, str):
            icon = QIcon.fromTheme(spec.icon)
            if icon.isNull():
                icon = QIcon(spec.icon)
            action.setIcon(icon)
        else:
            action.setIcon(spec.icon)
    if spec.shortcut is not None:
        if isinstance(spec.shortcut, QKeySequence):
            action.setShortcut(spec.shortcut)
        elif isinstance(spec.shortcut, str):
            action.setShortcut(QKeySequence(spec.shortcut))
        else:  # QKeySequence.StandardKey
            action.setShortcut(spec.shortcut)
    action.setObjectName(spec.action_id)
    if spec.callback is not None:
        action.triggered.connect(spec.callback)
    return action


def apply_enablement(
    registry: "ActionRegistry",
    actions: dict[str, QAction],
    context: dict,
) -> None:
    """Apply registry enablement to a map of action_id -> QAction.

    Actions whose id is not registered are left untouched so incremental
    migrations do not break existing surfaces.
    """
    for action_id, action in actions.items():
        if action_id not in registry:
            continue
        action.setEnabled(registry.enabled(action_id, context))
