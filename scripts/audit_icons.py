#!/usr/bin/env python3
"""Audit named icon themes used by the application."""

from __future__ import annotations

import re
from pathlib import Path
import sys

ICON_CALL_REGEX = re.compile(r'app_icon\(([^)]*)\)')


def extract_icon_names(source: str) -> list[str]:
    parts = re.findall(r'"([^"]+)"|\'([^\']+)\'', source)
    return [a or b for a, b in parts]


def scan_source(root: Path) -> list[str]:
    icons = []
    for file_path in root.rglob('*.py'):
        text = file_path.read_text(encoding='utf-8')
        for match in ICON_CALL_REGEX.finditer(text):
            icons.extend(extract_icon_names(match.group(1)))
    return sorted(set(icons))


def query_system_icons(theme_name: str | None = None) -> tuple[str, list[str], dict[str, bool]]:
    import os
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon

    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    app = QApplication([])
    if theme_name:
        QIcon.setThemeName(theme_name)
    theme = QIcon.themeName()
    paths = QIcon.themeSearchPaths()
    result = {}
    for name in scan_source(Path(__file__).resolve().parent.parent):
        result[name] = not QIcon.fromTheme(name).isNull()
    return theme, paths, result


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    icon_names = scan_source(project_root)
    if not icon_names:
        print('No app_icon calls found.')
        return 0

    print('Icon names found in app_icon calls:')
    for name in icon_names:
        print(f'  {name}')

    try:
        theme, paths, available = query_system_icons()
        print(f'\nCurrent Qt icon theme: {theme}')
        print('Qt icon theme search paths:')
        for path in paths:
            print(f'  {path}')
        print('\nIcon availability in current Qt theme:')
        for name, ok in available.items():
            print(f'  {name}: {"yes" if ok else "no"}')
        missing = [name for name, ok in available.items() if not ok]
        print(f'\nMissing icons: {len(missing)} / {len(available)}')
        if missing:
            for name in missing:
                print(f'  - {name}')
        # Try a common fallback theme if available and different
        fallback_theme = 'Breeze'
        if theme != fallback_theme:
            fb_theme, fb_paths, fb_available = query_system_icons(fallback_theme)
            if fb_theme == fallback_theme:
                print(f'\nIcon availability with fallback theme: {fb_theme}')
                for name, ok in fb_available.items():
                    print(f'  {name}: {"yes" if ok else "no"}')
                fb_missing = [name for name, ok in fb_available.items() if not ok]
                print(f'\nFallback missing icons: {len(fb_missing)} / {len(fb_available)}')
    except Exception as exc:
        print('Could not query Qt icon theme:', exc)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())