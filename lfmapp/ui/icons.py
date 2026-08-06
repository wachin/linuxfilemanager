from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtGui import QIcon

from lfmapp.core.config import Config

_ICON_CACHE: dict[str, QIcon] = {}
_ICON_PATH_CACHE: dict[str, Path | None] = {}
_FALLBACK_ICON_THEMES = ["Papirus", "Breeze", "hicolor"]
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


def discover_system_icons(config: Config, progress_callback: Callable[[int, str], None] | None = None) -> None:
    candidate_names = _collect_icon_candidate_names()
    total = len(candidate_names)
    if total == 0:
        config.set_icon_search_complete(True)
        return

    for index, name in enumerate(candidate_names, start=1):
        if progress_callback is not None:
            progress_callback(int((index - 1) / total * 100), name)
        _search_for_icon_path(name, config)
    if progress_callback is not None:
        progress_callback(100, "")
    config.set_icon_search_complete(True)


def _search_for_icon_path(theme_name: str, config: Config | None = None) -> Path | None:
    if config is not None:
        cached_paths = _load_cached_icon_paths(config)
        if theme_name in cached_paths:
            path = cached_paths[theme_name]
            _ICON_PATH_CACHE[theme_name] = path
            return path

    path = _find_system_icon_file(theme_name)
    if path is not None and config is not None:
        config.set_cached_icon_path(theme_name, str(path))
    return path


def _try_with_fallback_themes(theme_name: str) -> QIcon:
    original_theme = QIcon.themeName()
    for theme in _FALLBACK_ICON_THEMES:
        if theme == original_theme:
            continue
        QIcon.setThemeName(theme)
        icon = QIcon.fromTheme(theme_name)
        if not icon.isNull():
            QIcon.setThemeName(original_theme)
            return icon
    QIcon.setThemeName(original_theme)
    return QIcon()


def _resolve_aliases(theme_name: str) -> list[str]:
    return _ICON_ALIASES.get(theme_name, [theme_name])


def app_icon(*theme_names: str, config: Config | None = None) -> QIcon:
    for theme_name in theme_names:
        if not theme_name:
            continue

        resolved_names = _resolve_aliases(theme_name)
        for resolved_name in resolved_names:
            if resolved_name in _ICON_CACHE:
                return _ICON_CACHE[resolved_name]

            icon = QIcon.fromTheme(resolved_name)
            if not icon.isNull():
                _ICON_CACHE[resolved_name] = icon
                return icon

            path = _search_for_icon_path(resolved_name, config)
            if path is not None:
                icon = QIcon(str(path))
                if not icon.isNull():
                    _ICON_CACHE[resolved_name] = icon
                    return icon

            fallback_icon = _try_with_fallback_themes(resolved_name)
            if not fallback_icon.isNull():
                _ICON_CACHE[resolved_name] = fallback_icon
                return fallback_icon

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
