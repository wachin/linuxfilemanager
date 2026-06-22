from __future__ import annotations

from PyQt6.QtGui import QIcon


def app_icon(*theme_names: str) -> QIcon:
    for theme_name in theme_names:
        if not theme_name:
            continue
        icon = QIcon.fromTheme(theme_name)
        if not icon.isNull():
            return icon
    return QIcon()
