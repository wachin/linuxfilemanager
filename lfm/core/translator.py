from pathlib import Path
from PyQt6.QtCore import QLocale, QTranslator

from lfm.core.paths import TRANSLATIONS_DIR


INSTALLED_TRANSLATION_DIRS = (
    Path("/usr/share/linux-file-manager/i18n"),
    Path("/usr/local/share/linux-file-manager/i18n"),
)


def locale_candidates(locale_name=None):
    """Return locale codes from most specific to least specific."""
    locale_code = locale_name or QLocale.system().name()
    normalized = locale_code.replace("-", "_")
    candidates = []
    for code in (normalized, normalized.split("_", 1)[0]):
        if code and code not in candidates:
            candidates.append(code)
    return candidates


def translation_file_candidates(locale_name=None, translation_dirs=None):
    """Return possible app translation files for a locale."""
    dirs = tuple(translation_dirs or (TRANSLATIONS_DIR, *INSTALLED_TRANSLATION_DIRS))
    return [
        translation_dir / f"app_{locale_code}.qm"
        for translation_dir in dirs
        for locale_code in locale_candidates(locale_name)
    ]


def load_translator(locale_name=None):
    for qm_file in translation_file_candidates(locale_name):
        translator = QTranslator()
        if qm_file.exists() and translator.load(str(qm_file)):
            return translator
    return None
