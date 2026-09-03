"""Action registry: single source of truth for the command vocabulary.

The ActionRegistry is deliberately UI-agnostic.  It stores the *definition*
of every action (stable id, title, category, aliases, shortcut, enabled
condition and a callback) so that menus, toolbars, context menus, shortcuts
and the command palette all consume the same records instead of building
duplicated QActions with contradictory state.

Qt wiring lives in lfmapp.ui (e.g. MainWindow builds QAction objects from
ActionSpec); this module only manages identity, lookup and declarative
enablement so it can be unit-tested without a QApplication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# A condition receives a small read-only context dict (keys vary by surface:
# "selection", "clipboard_mode", "current_path", "view_mode", "has_selection",
# ...) and returns True when the action should be enabled.
EnabledPredicate = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class ActionSpec:
    """Stable definition of one command.

    Attributes:
        action_id: Stable logical identifier, e.g. "nav.back", "clip.copy".
        title: User-facing, translatable text (no "&" mnemonic marker).
        category: Grouping used by the palette and shortcut dialogs.
        callback: Zero-argument callable that executes the command.
        shortcut: Optional QKeySequence, string or QKeySequence.StandardKey.
        aliases: Extra search words for the palette.
        icon: Optional icon theme name or QIcon (kept as Any to stay Qt-free
            at the definition level; callers may store a string).
        enabled_when: Optional predicate over the context dict.  None means
            "always enabled" (still overridable at runtime via context).
        command_id: Backwards-compatible explicit id; falls back to action_id.
    """

    action_id: str
    title: str
    category: str = ""
    callback: Callable[[], Any] | None = None
    shortcut: Any = None
    aliases: tuple[str, ...] = ()
    icon: Any = None
    enabled_when: EnabledPredicate | None = None
    command_id: str | None = None

    @property
    def effective_command_id(self) -> str:
        return self.command_id or self.action_id


class DuplicateActionError(ValueError):
    """Raised when an action_id is registered twice."""


class UnknownActionError(KeyError):
    """Raised when looking up an action_id that was never registered."""


class ActionRegistry:
    """Registry of action definitions keyed by stable id."""

    def __init__(self) -> None:
        self._actions: dict[str, ActionSpec] = {}

    def register(self, spec: ActionSpec) -> ActionSpec:
        """Register one action definition.

        Raises DuplicateActionError when the id already exists so that
        duplicated definitions are caught loudly instead of silently
        overwriting each other.
        """
        if spec.action_id in self._actions:
            raise DuplicateActionError(
                f"Action {spec.action_id!r} is already registered"
            )
        self._actions[spec.action_id] = spec
        return spec

    def unregister(self, action_id: str) -> None:
        """Remove an action (used in tests or when extensions are disabled)."""
        self._actions.pop(action_id, None)

    def get(self, action_id: str) -> ActionSpec:
        """Return the spec for an id; raises UnknownActionError if absent."""
        try:
            return self._actions[action_id]
        except KeyError:
            raise UnknownActionError(action_id) from None

    def __contains__(self, action_id: str) -> bool:
        return action_id in self._actions

    def all(self) -> list[ActionSpec]:
        """All registered actions sorted by category, then title."""
        return sorted(
            self._actions.values(),
            key=lambda spec: (spec.category.casefold(), spec.title.casefold()),
        )

    def by_category(self, category: str) -> list[ActionSpec]:
        return [
            spec for spec in self._actions.values() if spec.category == category
        ]

    def categories(self) -> list[str]:
        """Distinct categories in stable alphabetical order."""
        return sorted(
            {spec.category for spec in self._actions.values() if spec.category}
        )

    def __len__(self) -> int:
        return len(self._actions)

    # ── Enablement ─────────────────────────────────────────────

    def enabled(self, action_id: str, context: dict[str, Any]) -> bool:
        """Evaluate the declarative enablement of one action.

        An action with no enabled_when predicate is enabled unless the
        context explicitly forces it off with "enabled": False.
        """
        spec = self.get(action_id)
        if context.get("enabled") is False:
            return False
        if spec.enabled_when is None:
            return True
        try:
            return bool(spec.enabled_when(context))
        except Exception:
            # A broken predicate must disable, never crash the surface.
            return False

    def enablement_map(self, context: dict[str, Any]) -> dict[str, bool]:
        """Evaluate every registered action against one context.

        Useful for surfaces that refresh enablement in bulk (menus, palette).
        """
        return {
            spec.action_id: self.enabled(spec.action_id, context)
            for spec in self.all()
        }
