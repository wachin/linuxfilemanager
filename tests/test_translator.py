import unittest
from pathlib import Path

from lfmapp.core.translator import locale_candidates, translation_file_candidates


class TranslatorTests(unittest.TestCase):
    def test_locale_candidates_include_specific_and_language_code(self):
        self.assertEqual(locale_candidates("es_EC"), ["es_EC", "es"])
        self.assertEqual(locale_candidates("pt-BR"), ["pt_BR", "pt"])

    def test_locale_candidates_do_not_duplicate_language_only_locale(self):
        self.assertEqual(locale_candidates("en"), ["en"])

    def test_translation_file_candidates_search_all_dirs_in_locale_order(self):
        dirs = [Path("/tmp/app-i18n"), Path("/opt/app-i18n")]

        self.assertEqual(
            translation_file_candidates("es_EC", dirs),
            [
                Path("/tmp/app-i18n/app_es_EC.qm"),
                Path("/tmp/app-i18n/app_es.qm"),
                Path("/opt/app-i18n/app_es_EC.qm"),
                Path("/opt/app-i18n/app_es.qm"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
