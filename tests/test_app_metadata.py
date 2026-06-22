import configparser
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AppMetadataTests(unittest.TestCase):
    def test_desktop_entry_has_required_fields(self):
        desktop_file = PROJECT_ROOT / "data" / "linux-file-manager.desktop"
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read(desktop_file, encoding="utf-8")

        self.assertIn("Desktop Entry", parser)
        entry = parser["Desktop Entry"]
        self.assertEqual(entry["Type"], "Application")
        self.assertEqual(entry["Exec"], "linuxfm %U")
        self.assertEqual(entry["Icon"], "linux-file-manager")
        self.assertIn("inode/directory;", entry["MimeType"])

    def test_metainfo_xml_is_parseable(self):
        metainfo = PROJECT_ROOT / "data" / "linux-file-manager.metainfo.xml"
        root = ET.parse(metainfo).getroot()

        self.assertEqual(root.tag, "component")
        self.assertEqual(root.findtext("id"), "io.github.wachin.LinuxFileManager")
        self.assertEqual(root.findtext("launchable"), "linux-file-manager.desktop")
        self.assertEqual(root.findtext("provides/binary"), "linuxfm")
        self.assertIsNotNone(root.find("content_rating"))

    def test_icon_svg_is_parseable(self):
        icon = PROJECT_ROOT / "data" / "icons" / "linux-file-manager.svg"
        root = ET.parse(icon).getroot()

        self.assertTrue(root.tag.endswith("svg"))
        self.assertEqual(root.attrib["viewBox"], "0 0 128 128")


if __name__ == "__main__":
    unittest.main()
