import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget

from lfmapp.core.app_data import ensure_app_data
from lfmapp.core.config import Config
from lfmapp.core.translator import load_translator
from lfmapp.ui.icons import application_icon, discover_system_icons, initialize_icon_cache
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

    initialize_icon_cache(config)
    if not config.icon_search_complete:
        splash_widget = QWidget()
        splash_widget.setWindowFlags(
            splash_widget.windowFlags()
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
        )
        splash_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout = QVBoxLayout(splash_widget)
        logo_label = QLabel(splash_widget)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_pixmap = application_icon(config).pixmap(64, 64)
        if not icon_pixmap.isNull():
            logo_label.setPixmap(icon_pixmap)
        layout.addWidget(logo_label)
        label = QLabel("Buscando iconos del sistema...", splash_widget)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress = QProgressBar(splash_widget)
        progress.setRange(0, 100)
        progress.setValue(0)
        layout.addWidget(label)
        layout.addWidget(progress)
        splash_widget.resize(420, 160)
        screen = app.primaryScreen()
        if screen is not None:
            screen_geometry = screen.availableGeometry()
            splash_widget.move(
                screen_geometry.center().x() - splash_widget.width() // 2,
                screen_geometry.center().y() - splash_widget.height() // 2,
            )
        splash_widget.show()
        app.processEvents()

        def on_progress(value: int, name: str):
            progress.setValue(value)
            if name:
                label.setText(f"Buscando icono: {name}")
            app.processEvents()

        discover_system_icons(config, progress_callback=on_progress)
        splash_widget.close()

    app.setWindowIcon(application_icon(config))
    window = MainWindow(config=config)
    window.show()
    return app.exec()
