import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TranslationSourceTests(unittest.TestCase):
    def test_translation_sources_are_parseable(self):
        for filename in ("app_en.ts", "app_es.ts"):
            with self.subTest(filename=filename):
                root = ET.parse(PROJECT_ROOT / "translations" / filename).getroot()

                self.assertEqual(root.tag, "TS")
                self.assertEqual(root.attrib["version"], "2.1")

    def test_translation_sources_include_dialog_contexts(self):
        root = ET.parse(PROJECT_ROOT / "translations" / "app_en.ts").getroot()
        contexts = {context.findtext("name") for context in root.findall("context")}
        sources = {
            message.findtext("source")
            for message in root.findall("context/message")
        }

        self.assertIn("CreateMultipleDialog", contexts)
        self.assertIn("SearchFilterDialog", contexts)
        self.assertIn("Create Multiple Items", sources)
        self.assertIn("Search Filters", sources)

    def test_translation_sources_include_operation_history_ui_strings(self):
        root = ET.parse(PROJECT_ROOT / "translations" / "app_en.ts").getroot()
        sources = {
            message.findtext("source")
            for message in root.findall("context/message")
        }

        self.assertIn("Undo {operation}", sources)
        self.assertIn("Redo {operation}", sources)
        self.assertIn("Rename {original} to {renamed}", sources)


if __name__ == "__main__":
    unittest.main()
