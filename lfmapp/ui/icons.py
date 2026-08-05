from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QIcon

_ICON_CACHE: dict[str, QIcon] = {}
_ICON_PATH_CACHE: dict[str, Path | None] = {}


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

    # Try symbolic variants if the plain name isn't found
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


def app_icon(*theme_names: str) -> QIcon:
    for theme_name in theme_names:
        if not theme_name:
            continue
        if theme_name in _ICON_CACHE:
            return _ICON_CACHE[theme_name]

        icon = QIcon.fromTheme(theme_name)
        if not icon.isNull():
            _ICON_CACHE[theme_name] = icon
            return icon

        path = _find_system_icon_file(theme_name)
        if path is not None:
            icon = QIcon(str(path))
            if not icon.isNull():
                _ICON_CACHE[theme_name] = icon
                return icon

    icon = QIcon()
    return icon


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
