"""Automatic appearance rules (backlog P2, "highlighting by rules").

A rule pairs a **condition** (name pattern, type, size, date, path or tag)
with an **effect** (foreground / background colour, bold/italic, an overlay
icon).  Rules are evaluated in order and **stack** — later rules override
the channels they set — with an optional *stop at the first match* flag.

This module is deliberately **pure and Qt-free**: it never touches the item
model.  The resolved effect is applied only in the view's paint delegate
(`lfmapp/ui/highlight_delegate.py`), per the architecture rule that data
(rules) must stay separate from the visual effect (how each row is painted).

The condition fields mirror `services.search_service.SearchFilters` (and
reuse its extension taxonomy) so the same matching language powers both
search and highlighting; highlighting additionally supports a name glob, a
path substring and a tag membership.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lfmapp.services.search_service import SearchFilters


RULE_VERSION = 1


# ---------------------------------------------------------------------------
# Effect
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HighlightEffect:
    """The visual effect resolved for one path (empty channels = inherit)."""

    fg_color: str | None = None
    bg_color: str | None = None
    bold: bool = False
    italic: bool = False
    overlay_icon: str | None = None

    def is_empty(self) -> bool:
        return not (
            self.fg_color
            or self.bg_color
            or self.bold
            or self.italic
            or self.overlay_icon
        )

    def merge(self, other: "HighlightEffect") -> "HighlightEffect":
        """Return this effect with *other*'s set channels overriding it."""
        return HighlightEffect(
            fg_color=other.fg_color or self.fg_color,
            bg_color=other.bg_color or self.bg_color,
            bold=self.bold or other.bold,
            italic=self.italic or other.italic,
            overlay_icon=other.overlay_icon or self.overlay_icon,
        )


# ---------------------------------------------------------------------------
# Rule (condition + effect)
# ---------------------------------------------------------------------------

@dataclass
class HighlightRule:
    """One appearance rule: when *matches(path)* is true, apply *effect()*."""

    name: str = ""
    enabled: bool = True
    # conditions (all present ones must match; blanks/None are wildcards)
    name_glob: str = ""
    file_type: str = "any"
    min_size: int | None = None
    max_size: int | None = None
    modified_after: float | None = None
    modified_before: float | None = None
    path_contains: str = ""
    tag: str = ""
    # effect
    fg_color: str = ""
    bg_color: str = ""
    bold: bool = False
    italic: bool = False
    overlay_icon: str = ""
    # behaviour
    stop: bool = False

    def effect(self) -> HighlightEffect:
        return HighlightEffect(
            fg_color=self.fg_color or None,
            bg_color=self.bg_color or None,
            bold=self.bold,
            italic=self.italic,
            overlay_icon=self.overlay_icon or None,
        )

    def has_effect(self) -> bool:
        return not self.effect().is_empty()

    def matches(self, path: Path, *, tags_for_path: Callable[[Path], list[str]] | None = None) -> bool:
        """Return True if *path* satisfies every non-empty condition."""
        # Name glob (fnmatch on the base name, case-insensitive).
        if self.name_glob:
            if not fnmatch.fnmatch(path.name.lower(), self.name_glob.lower()):
                return False
        # Path substring.
        if self.path_contains:
            if self.path_contains.lower() not in str(path).lower():
                return False
        # Tag membership.
        if self.tag:
            if tags_for_path is None:
                return False
            wanted = self.tag.lower()
            try:
                file_tags = [t.lower() for t in tags_for_path(path)]
            except Exception:
                file_tags = []
            if wanted not in file_tags:
                return False
        # Type / size / date via the shared SearchFilters predicate.
        if (
            self.file_type != "any"
            or self.min_size is not None
            or self.max_size is not None
            or self.modified_after is not None
            or self.modified_before is not None
        ):
            filters = SearchFilters(
                file_type=self.file_type,
                min_size=self.min_size,
                max_size=self.max_size,
                modified_after=self.modified_after,
                modified_before=self.modified_before,
            )
            if not filters.matches(path):
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "version": RULE_VERSION,
            "name": self.name,
            "enabled": self.enabled,
            "name_glob": self.name_glob,
            "file_type": self.file_type,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "modified_after": self.modified_after,
            "modified_before": self.modified_before,
            "path_contains": self.path_contains,
            "tag": self.tag,
            "fg_color": self.fg_color,
            "bg_color": self.bg_color,
            "bold": self.bold,
            "italic": self.italic,
            "overlay_icon": self.overlay_icon,
            "stop": self.stop,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "HighlightRule":
        if not isinstance(data, dict):
            return cls()
        return cls(
            name=str(data.get("name", "")),
            enabled=bool(data.get("enabled", True)),
            name_glob=str(data.get("name_glob", "")),
            file_type=str(data.get("file_type", "any")),
            min_size=data.get("min_size"),
            max_size=data.get("max_size"),
            modified_after=data.get("modified_after"),
            modified_before=data.get("modified_before"),
            path_contains=str(data.get("path_contains", "")),
            tag=str(data.get("tag", "")),
            fg_color=str(data.get("fg_color", "")),
            bg_color=str(data.get("bg_color", "")),
            bold=bool(data.get("bold", False)),
            italic=bool(data.get("italic", False)),
            overlay_icon=str(data.get("overlay_icon", "")),
            stop=bool(data.get("stop", False)),
        )


def sanitize_rule(raw: dict) -> dict | None:
    """Return a cleaned rule dict, or *None* if it is unusable/foreign."""
    if not isinstance(raw, dict):
        return None
    if raw.get("version") not in (None, RULE_VERSION):
        return None
    rule = HighlightRule.from_dict(raw)
    if not rule.has_effect():
        return None  # a rule that paints nothing is pointless
    return rule.to_dict()


# ---------------------------------------------------------------------------
# Evaluation (stacking with stop-at-first-match) + caching
# ---------------------------------------------------------------------------

def evaluate_rules(
    rules: list[HighlightRule],
    path: Path,
    *,
    tags_for_path: Callable[[Path], list[str]] | None = None,
) -> HighlightEffect:
    """Apply all matching enabled rules in order, stacking their effects.

    The first matching rule with ``stop`` short-circuits further evaluation.
    Returns an empty `HighlightEffect` when nothing applies.
    """
    accumulated = HighlightEffect()
    for rule in rules:
        if not rule.enabled:
            continue
        if rule.matches(path, tags_for_path=tags_for_path):
            accumulated = accumulated.merge(rule.effect())
            if rule.stop:
                break
    return accumulated


class HighlightEvaluator:
    """Stateful holder of the active rules with a per-path result cache.

    Views call `effect_for(path)` on every paint of a visible row; a dict
    cache keyed by the canonical path avoids re-running the rule list. The
    cache is dropped wholesale on `invalidate()` (rule-set change, folder
    refresh, tag change) — a coarser but safe policy given tags and mtimes.
    """

    def __init__(
        self,
        rules: list[HighlightRule] | None = None,
        *,
        enabled: bool = True,
        tags_for_path: Callable[[Path], list[str]] | None = None,
    ):
        self._rules: list[HighlightRule] = list(rules or [])
        self._enabled = enabled
        self._tags_for_path = tags_for_path
        self._cache: dict[str, HighlightEffect] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> None:
        self._enabled = bool(value)
        self.invalidate()

    def set_rules(self, rules: list[HighlightRule]) -> None:
        self._rules = list(rules)
        self.invalidate()

    def rules(self) -> list[HighlightRule]:
        return list(self._rules)

    def set_tags_provider(self, fn: Callable[[Path], list[str]] | None) -> None:
        self._tags_for_path = fn
        self.invalidate()

    def invalidate(self) -> None:
        self._cache.clear()

    def effect_for(self, path: Path) -> HighlightEffect:
        if not self._enabled or not self._rules:
            return HighlightEffect()
        key = str(path)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        effect = evaluate_rules(
            self._rules, path, tags_for_path=self._tags_for_path
        )
        self._cache[key] = effect
        return effect


def rules_from_config(raw: list | None) -> list[HighlightRule]:
    """Build the active rule list from a (possibly dirty) config list."""
    rules: list[HighlightRule] = []
    if not isinstance(raw, list):
        return rules
    for item in raw:
        cleaned = sanitize_rule(item)
        if cleaned is not None:
            rules.append(HighlightRule.from_dict(cleaned))
    return rules
