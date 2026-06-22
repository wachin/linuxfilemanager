from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPalette
from PyQt6.QtWidgets import QWidget


TABLER_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons" / "tabler"


def _palette_for(widget: QWidget | None = None) -> QPalette | None:
    if widget is not None:
        return widget.palette()
    app = QGuiApplication.instance()
    if app is None:
        return None
    return app.palette()


def _is_dark_color(color: QColor) -> bool:
    return color.lightness() < 128


def preferred_tabler_variant(widget: QWidget | None = None) -> str:
    palette = _palette_for(widget)
    if palette is None:
        return "outline"
    return "filled" if _is_dark_color(palette.color(QPalette.ColorRole.Window)) else "outline"


def tabler_icon_path(
    name: str,
    *,
    variant: str | None = None,
    widget: QWidget | None = None,
) -> Path | None:
    icon_name = str(name or "").strip()
    if not icon_name:
        return None

    variants = []
    preferred = variant or preferred_tabler_variant(widget)
    for candidate in (preferred, "outline", "filled"):
        if candidate not in variants:
            variants.append(candidate)

    for candidate in variants:
        path = TABLER_ICONS_DIR / candidate / f"{icon_name}.svg"
        if path.is_file():
            return path
    return None


def app_icon(
    tabler_name: str | None = None,
    *theme_names: str,
    widget: QWidget | None = None,
    variant: str | None = None,
) -> QIcon:
    if tabler_name:
        icon_path = tabler_icon_path(tabler_name, variant=variant, widget=widget)
        if icon_path is not None:
            return QIcon(str(icon_path))

    for theme_name in theme_names:
        if not theme_name:
            continue
        icon = QIcon.fromTheme(theme_name)
        if not icon.isNull():
            return icon
    return QIcon()
