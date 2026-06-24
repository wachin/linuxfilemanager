import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from lfmapp.core.app_data import ensure_app_data
from lfmapp.core.config import Config
from lfmapp.core.translator import load_translator
from lfmapp.ui.icons import application_icon
from lfmapp.ui.main_window import MainWindow


def main(argv=None):
    app = QApplication(argv or sys.argv)
    app.setApplicationName("linux-file-manager")
    app.setDesktopFileName("linux-file-manager")
    app.setWindowIcon(application_icon())

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

    window = MainWindow(config=config)
    window.show()
    return app.exec()
