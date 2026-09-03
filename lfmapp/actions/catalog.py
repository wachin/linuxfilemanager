"""Core command catalog: the stable vocabulary of the file manager.

Every entry here is the definition of one command that surfaces (menus,
toolbars, shortcuts, palette, context menus) are expected to expose with a
stable logical id.  The titles are the base English text; QObject.tr() is
applied when building the QAction so existing i18n keeps working.
"""

from __future__ import annotations

from lfmapp.actions.registry import ActionRegistry, ActionSpec


def has_selection(context: dict) -> bool:
    return bool(context.get("selection_count", 0) > 0)


def can_paste(context: dict) -> bool:
    return bool(context.get("clipboard_mode") in {"copy", "cut"})


def is_undo_available(context: dict) -> bool:
    return bool(context.get("can_undo"))


def is_redo_available(context: dict) -> bool:
    return bool(context.get("can_redo"))


def build_core_registry() -> ActionRegistry:
    """Create a registry populated with the core command vocabulary.

    Callbacks are intentionally None here: MainWindow supplies the real
    callbacks when it instantiates its registry, keeping this catalog pure
    and reusable by tests.  Use :func:`with_callbacks` to bind them.
    """
    registry = ActionRegistry()
    specs = [
        # ── Navigation ────────────────────────────────────────
        ActionSpec("nav.back", "Back", category="Navigation", shortcut="Alt+Left"),
        ActionSpec("nav.forward", "Forward", category="Navigation", shortcut="Alt+Right"),
        ActionSpec("nav.up", "Up", category="Navigation", shortcut="Alt+Up"),
        ActionSpec("nav.home", "Home", category="Navigation", shortcut="Alt+Home"),
        ActionSpec("nav.refresh", "Refresh", category="Navigation", shortcut="F5"),
        # ── Clipboard / selection transfer ───────────────────
        ActionSpec(
            "clip.copy",
            "Copy",
            category="Clipboard",
            shortcut="Ctrl+C",
            enabled_when=has_selection,
        ),
        ActionSpec(
            "clip.cut",
            "Cut",
            category="Clipboard",
            shortcut="Ctrl+X",
            enabled_when=has_selection,
        ),
        ActionSpec(
            "clip.paste",
            "Paste",
            category="Clipboard",
            shortcut="Ctrl+V",
            enabled_when=can_paste,
        ),
        ActionSpec("clip.copy_path", "Copy Path", category="Clipboard", shortcut="Ctrl+Shift+C"),
        # ── Selection ─────────────────────────────────────────
        ActionSpec("sel.all", "Select All", category="Selection", shortcut="Ctrl+A"),
        ActionSpec("sel.none", "Deselect All", category="Selection", shortcut="Ctrl+Shift+A"),
        ActionSpec("sel.invert", "Invert Selection", category="Selection", shortcut="Ctrl+Shift+I"),
        # ── File operations ───────────────────────────────────
        ActionSpec("file.new_folder", "New Folder", category="File", shortcut="Ctrl+Shift+N"),
        ActionSpec("file.new_file", "New File", category="File", shortcut="Ctrl+N"),
        ActionSpec("file.rename", "Rename", category="File", shortcut="F2", enabled_when=has_selection),
        ActionSpec(
            "file.trash",
            "Move to Trash",
            category="File",
            shortcut="Delete",
            enabled_when=has_selection,
        ),
        ActionSpec(
            "file.delete",
            "Delete",
            category="File",
            shortcut="Shift+Delete",
            enabled_when=has_selection,
        ),
        # ── History ───────────────────────────────────────────
        ActionSpec("hist.undo", "Undo", category="History", shortcut="Ctrl+Z", enabled_when=is_undo_available),
        ActionSpec("hist.redo", "Redo", category="History", shortcut="Ctrl+Y", enabled_when=is_redo_available),
        # ── Window / views ────────────────────────────────────
        ActionSpec("win.preferences", "Preferences...", category="Window", shortcut="Ctrl+,"),
        ActionSpec("win.palette", "Command Palette...", category="Window", shortcut="Ctrl+Shift+P"),
        ActionSpec("win.new_tab", "New Tab", category="Window", shortcut="Ctrl+T"),
        ActionSpec("win.close_tab", "Close Tab", category="Window", shortcut="Ctrl+W"),
        ActionSpec("win.close_window", "Close Window", category="Window", shortcut="Ctrl+Shift+W"),
        ActionSpec("win.toggle_preview", "Toggle Preview Panel", category="View"),
        ActionSpec("win.toggle_sidebar", "Toggle Sidebar", category="View"),
        ActionSpec("view.mode.icons", "Icons View", category="View", shortcut="Ctrl+1"),
        ActionSpec("view.mode.list", "List View", category="View", shortcut="Ctrl+2"),
        ActionSpec("view.mode.details", "Details View", category="View", shortcut="Ctrl+3"),
        ActionSpec("view.mode.compact", "Compact View", category="View", shortcut="Ctrl+4"),
        ActionSpec("view.hidden", "Hidden Files", category="View", shortcut="Ctrl+H"),
        ActionSpec("view.extensions", "File Extensions", category="View"),
        ActionSpec("view.checkboxes", "Selection Checkboxes", category="View"),
        ActionSpec("view.remember", "Remember folder view", category="View"),
    ]
    for spec in specs:
        registry.register(spec)
    return registry


def with_callbacks(registry: ActionRegistry, callbacks: dict[str, callable]) -> ActionRegistry:
    """Return a copy-like registry whose specs carry real callbacks.

    callbacks maps action_id -> zero-argument callable.  Unknown ids are
    ignored; ids without a callback keep callback=None.
    """
    for action_id, callback in callbacks.items():
        try:
            spec = registry.get(action_id)
        except Exception:
            continue
        bound = ActionSpec(
            action_id=spec.action_id,
            title=spec.title,
            category=spec.category,
            callback=callback,
            shortcut=spec.shortcut,
            aliases=spec.aliases,
            icon=spec.icon,
            enabled_when=spec.enabled_when,
            command_id=spec.command_id,
        )
        registry.unregister(action_id)
        registry.register(bound)
    return registry
