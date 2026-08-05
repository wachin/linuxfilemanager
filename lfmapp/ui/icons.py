from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QIcon

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


def app_icon(*theme_names: str) -> QIcon:
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

            path = _find_system_icon_file(resolved_name)
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


def application_icon() -> QIcon:
    icon = app_icon("linux-file-manager")
    if not icon.isNull():
        return icon
    icon_path = (
        Path(__file__).resolve().parent.parent.parent
        / "data"
        / "icons"
        / "linux-file-manager.svg"
    )
    return QIcon(str(icon_path))
