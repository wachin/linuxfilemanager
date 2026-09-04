"""Shortcut map: single source of truth for commands and their key bindings.

ROADMAP Phase 4.2 — "Command palette and consistent shortcut map".

UI-agnostic (Qt-free) registry so it can be unit-tested headless. The UI
surfaces (menu bar, toolbar, context menu, palette and window-level
QShortcut) register every command here with a stable ``command_id`` and its
shortcut; this controller then:

* normalises command records for the palette (title, shortcut, category,
  enabled + reason, aliases),
* detects **collisions** (two different commands bound to the same sequence),
* exposes ``by_shortcut`` and ``collisions`` for auditing consistency.

The surfaces remain the only writers; the palette reads from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


def normalize_shortcut(shortcut: str) -> str:
    """Return a stripped, sortable key for a shortcut string ('' stays '')."""
    if shortcut is None:
        return ""
    return shortcut.strip()


@dataclass
class CommandRecord:
    command_id: str
    title: str
    shortcut: str = ""
    category: str = ""
    enabled: bool = True
    disabled_reason: str = ""
    callback: Callable[[], None] | None = None
    aliases: list[str] = field(default_factory=list)

    @property
    def shortcut_key(self) -> str:
        return normalize_shortcut(self.shortcut)


class ShortcutMap:
    """Registry of commands and shortcuts with collision detection."""

    def __init__(self):
        self._commands: dict[str, CommandRecord] = {}
        self._by_shortcut: dict[str, list[str]] = {}

    # ── Registration ───────────────────────────────────────────

    def register(
        self,
        command_id: str,
        title: str,
        shortcut: str = "",
        category: str = "",
        enabled: bool = True,
        disabled_reason: str = "",
        callback: Callable[[], None] | None = None,
        aliases: list[str] | None = None,
    ) -> CommandRecord:
        """Add or update a command. Returns the stored record."""
        command_id = str(command_id or "").strip()
        shortcut = normalize_shortcut(shortcut)
        aliases = list(dict.fromkeys(aliases or []))

        # If the command already exists, update in place (keep id stability).
        if command_id and command_id in self._commands:
            record = self._commands[command_id]
            self._unlink_shortcut(record.command_id, record.shortcut)
            record.title = title
            record.shortcut = shortcut
            record.category = category
            record.enabled = enabled
            record.disabled_reason = disabled_reason
            record.callback = callback
            record.aliases = aliases
        else:
            if not command_id:
                command_id = self._next_id()
            record = CommandRecord(
                command_id=command_id,
                title=title,
                shortcut=shortcut,
                category=category,
                enabled=enabled,
                disabled_reason=disabled_reason,
                callback=callback,
                aliases=aliases,
            )
            self._commands[command_id] = record

        self._link_shortcut(command_id, shortcut)
        return record

    def _next_id(self) -> str:
        base = 0
        while f"__auto_{base}" in self._commands:
            base += 1
        return f"__auto_{base}"

    def _unlink_shortcut(self, command_id: str, shortcut: str):
        key = normalize_shortcut(shortcut)
        ids = self._by_shortcut.get(key)
        if ids and command_id in ids:
            ids.remove(command_id)
        if ids is not None and not ids:
            self._by_shortcut.pop(key, None)

    def _link_shortcut(self, command_id: str, shortcut: str):
        key = normalize_shortcut(shortcut)
        if not key:
            return
        self._by_shortcut.setdefault(key, [])
        if command_id not in self._by_shortcut[key]:
            self._by_shortcut[key].append(command_id)

    # ── Queries ────────────────────────────────────────────────

    def commands(self) -> list[CommandRecord]:
        return list(self._commands.values())

    def get(self, command_id: str) -> CommandRecord | None:
        return self._commands.get(command_id)

    @property
    def collisions(self) -> dict[str, list[CommandRecord]]:
        """Shortcut -> conflicting commands (only when 2+ share the key)."""
        result: dict[str, list[CommandRecord]] = {}
        for key, ids in self._by_shortcut.items():
            if len(ids) >= 2:
                result[key] = [self._commands[i] for i in ids if i in self._commands]
        return result

    def commands_by_shortcut(self, shortcut: str) -> list[CommandRecord]:
        key = normalize_shortcut(shortcut)
        return [self._commands[i] for i in self._by_shortcut.get(key, []) if i in self._commands]

    # ── Palette projection ─────────────────────────────────────

    def palette_entries(self) -> list[dict]:
        """Return the normalized command list for the palette dialog."""
        entries: list[dict[str, Any]] = []
        for record in self._commands.values():
            entries.append(
                {
                    "command_id": record.command_id,
                    "title": record.title,
                    "callback": record.callback,
                    "shortcut": record.shortcut,
                    "category": record.category,
                    "enabled": record.enabled,
                    "disabled_reason": record.disabled_reason,
                    "alias": list(record.aliases),
                }
            )
        return entries