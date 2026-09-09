import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from lfmapp.core.app_data import ensure_app_data
from lfmapp.core.config import Config
from lfmapp.core.translator import load_translator
from lfmapp.ui.icons import (
    application_icon,
    initialize_icon_cache,
)
from lfmapp.ui.main_window import MainWindow


def main(argv=None):
    app = QApplication(argv or sys.argv)
    app.setApplicationName("linux-file-manager")
    app.setDesktopFileName("linux-file-manager")

    config = ensure_app_data(Config())
    base_font = app.font()
    if config.ui_font_family.strip():
        base_font.setFamily(config.ui_font_family.strip())
    base_font.setPointSize(config.ui_font_size)
    base_font.setWeight(config.ui_font_weight)
    base_font.setItalic(config.ui_font_italic)
    app.setFont(QFont(base_font))

    translator = load_translator()
    if translator is not None:
        app.installTranslator(translator)

    # Icon strategy (the way Thunar/GTK actually do it): resolve every icon
    # through the toolkit's own theme engine (QIcon.fromTheme), which reads the
    # user's active icon theme through its indexed cache — the same
    # `gtk_icon_theme_lookup` + `gtk-update-icon-cache` machinery Thunar relies
    # on — so it is fast, theme-following, and NEVER walks the icon trees.
    # `initialize_icon_cache` only restores paths found in earlier sessions as a
    # last-resort fallback for names the active theme does not provide (e.g. a
    # bare `hicolor` theme under qt6ct); that fallback is resolved lazily and
    # memoized on first use. Nothing scans the icon theme trees during startup,
    # so the window appears immediately.
    initialize_icon_cache(config)

    app.setWindowIcon(application_icon(config))
    window = MainWindow(config=config)
    window.show()
    return app.exec()
