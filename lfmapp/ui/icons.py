from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtGui import QIcon

from lfmapp.core.config import Config

_ICON_CACHE: dict[str, QIcon] = {}
_ICON_PATH_CACHE: dict[str, Path | None] = {}
_LAST_THEME_NAME: str | None = None
_ICON_ALIASES: dict[str, list[str]] = {
    "go-previous": ["arrow-left", "go-previous"],
    "go-next": ["arrow-right", "go-next"],
    "go-up": ["arrow-up", "go-up"],
    "go-home": ["user-home", "go-home"],
    "document-open": ["folder-open", "document-open"],
    "document-save-as": ["edit-rename", "document-save-as"],
    "document-print": ["printer", "document-print"],
    "document-properties": ["settings", "document-properties"],
    "document-share": ["emblem-shared", "mail-send", "document-share"],
    "package-x-generic": ["folder-compressed", "package-x-generic"],
    "utilities-terminal": ["terminal", "utilities-terminal"],
    "trash-empty": ["user-trash", "trash-empty"],
    "folder-open": ["folder-open", "folder"],
    "folder-bookmarks": ["bookmarks", "folder-bookmarks"],
    "folder-remote": ["network-server", "folder-remote"],
    "document-open-recent": ["view-history", "document-open-recent"],
    "emblem-favorite": ["bookmark-new", "emblem-favorite"],
}

_ADDITIONAL_ICON_NAMES: set[str] = {
    "linux-file-manager",
    "dialog-information",
    "view-preview",
    "view-sidebar",
    "edit-cut",
    "edit-copy",
    "edit-paste",
    "edit-rename",
    "security-medium",
    "folder-open",
    "utilities-terminal",
    "terminal",
    "document-open",
    "document-print",
    "printer",
    "bookmark-new",
    "user-bookmarks",
    "computer",
    "drive-harddisk",
    "computer-symbolic",
    "network-workgroup",
    "network-server",
    "folder-remote",
    "bookmarks",
    "folder-bookmarks",
    "folder-recent",
    "view-history",
    "folder",
}


def _find_system_icon_file(theme_name: str) -> Path | None:
    if theme_name in _ICON_PATH_CACHE:
        return _ICON_PATH_CACHE[theme_name]

    for search_path in QIcon.themeSearchPaths():
        root = Path(search_path)
        if not root.exists():
            continue
        for ext in ("svg", "png", "xpm", "ico"):
            found = next(root.rglob(f"{theme_name}.{ext}"), None)
            if found is not None:
                _ICON_PATH_CACHE[theme_name] = found
                return found

    symbolic_name = f"{theme_name}-symbolic"
    for search_path in QIcon.themeSearchPaths():
        root = Path(search_path)
        if not root.exists():
            continue
        for ext in ("svg", "png", "xpm", "ico"):
            found = next(root.rglob(f"{symbolic_name}.{ext}"), None)
            if found is not None:
                _ICON_PATH_CACHE[theme_name] = found
                return found

    _ICON_PATH_CACHE[theme_name] = None
    return None


def _collect_icon_candidate_names() -> list[str]:
    names: set[str] = set(_ADDITIONAL_ICON_NAMES)
    names.update(_ICON_ALIASES.keys())
    for aliases in _ICON_ALIASES.values():
        names.update(aliases)
    return sorted(names)


def _load_cached_icon_paths(config: Config) -> dict[str, Path]:
    cached_paths: dict[str, Path] = {}
    for icon_name, path_str in config.cached_icon_paths.items():
        try:
            path = Path(path_str)
            if path.exists():
                cached_paths[icon_name] = path
        except Exception:
            continue
    return cached_paths


def initialize_icon_cache(config: Config) -> None:
    cached_paths = _load_cached_icon_paths(config)
    _ICON_PATH_CACHE.update(cached_paths)
    for icon_name in config.icon_search_misses:
        _ICON_PATH_CACHE.setdefault(icon_name, None)


def pending_icon_searches() -> list[str]:
    """Candidate icon names still unresolved (no cached hit and no persisted miss).

    Scanning the icon theme trees is expensive (~seconds per missing name), so it
    must only happen for names not yet resolved and never on every process start.
    """
    return [name for name in _collect_icon_candidate_names() if name not in _ICON_PATH_CACHE]


def discover_system_icons(config: Config, progress_callback: Callable[[int, str], None] | None = None) -> None:
    # Seed the per-process cache from the persisted profile (found paths and
    # known misses) so that already-resolved names are never scanned again.
    initialize_icon_cache(config)
    candidate_names = _collect_icon_candidate_names()
    total = len(candidate_names)
    if total == 0:
        config.set_icon_search_complete(True)
        return

    for index, name in enumerate(candidate_names, start=1):
        if progress_callback is not None:
            progress_callback(int((index - 1) / total * 100), name)
        _discover_one(name, config)
    if progress_callback is not None:
        progress_callback(100, "")
    config.set_icon_search_complete(True)


def _discover_one(theme_name: str, config: Config) -> Path | None:
    """Resolve one candidate during the one-time discovery: scan the filesystem
    and persist the outcome (found path or known miss) for future processes."""
    if theme_name in _ICON_PATH_CACHE:
        return _ICON_PATH_CACHE[theme_name]
    path = _find_system_icon_file(theme_name)
    if path is not None:
        config.set_cached_icon_path(theme_name, str(path))
    else:
        config.add_icon_search_miss(theme_name)
    return path


def _search_for_icon_path(theme_name: str, config: Config | None = None) -> Path | None:
    # Consult-only lookup: never walk the icon theme trees from the UI thread.
    # A full recursive scan can take seconds per missing name, so it is allowed
    # exclusively inside discover_system_icons() (see _discover_one). The module
    # cache is seeded from the persisted profile by initialize_icon_cache().
    return _ICON_PATH_CACHE.get(theme_name)


def _resolve_aliases(theme_name: str) -> list[str]:
    return _ICON_ALIASES.get(theme_name, [theme_name])


def _current_theme_name() -> str:
    return QIcon.themeName()


def _refresh_cache_on_theme_change() -> None:
    """Drop the resolved-icon cache when the active system theme changes.

    Mirror of Thunar's theme "changed" hook: icon lookups must follow the user's
    current icon theme, not a theme chosen in a previous session.
    """
    global _LAST_THEME_NAME
    current = _current_theme_name()
    if _LAST_THEME_NAME is None:
        _LAST_THEME_NAME = current
    elif current != _LAST_THEME_NAME:
        _ICON_CACHE.clear()
        _LAST_THEME_NAME = current


def app_icon(*theme_names: str, config: Config | None = None) -> QIcon:
    _refresh_cache_on_theme_change()

    for theme_name in theme_names:
        if not theme_name:
            continue

        resolved_names = _resolve_aliases(theme_name)
        for resolved_name in resolved_names:
            if resolved_name in _ICON_CACHE:
                cached = _ICON_CACHE[resolved_name]
                if cached.isNull():
                    # Known miss in the active theme: keep looking through the
                    # remaining aliases and requested names.
                    continue
                return cached

            # Primary source: the toolkit's own theme engine (indexed, fast and
            # theme-following), like gtk_icon_theme_lookup_icon in Thunar.
            icon = QIcon.fromTheme(resolved_name)
            if not icon.isNull():
                _ICON_CACHE[resolved_name] = icon
                return icon

            # Secondary source: a path persisted from an earlier session. Used
            # only when the active theme lacks the name (never to override it).
            path = _search_for_icon_path(resolved_name, config)
            if path is not None:
                icon = QIcon(str(path))
                if not icon.isNull():
                    _ICON_CACHE[resolved_name] = icon
                    return icon

            # Like Thunar, do not hunt for the icon in other icon themes: the
            # active system theme is the only source, so the UI follows the
            # user's theme choice. Remember the miss so later lookups are cheap
            # (the cache is dropped when the theme changes).
            _ICON_CACHE[resolved_name] = QIcon()

    return QIcon()


def application_icon(config: Config | None = None) -> QIcon:
    icon = app_icon("linux-file-manager", config=config)
    if not icon.isNull():
        return icon
    icon_path = (
        Path(__file__).resolve().parent.parent.parent
        / "data"
        / "icons"
        / "linux-file-manager.svg"
    )
    return QIcon(str(icon_path))
