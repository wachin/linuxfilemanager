from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QIcon


def app_icon(*theme_names: str) -> QIcon:
    for theme_name in theme_names:
        if not theme_name:
            continue
        icon = QIcon.fromTheme(theme_name)
        if not icon.isNull():
            return icon
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
