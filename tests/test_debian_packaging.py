import configparser
import stat
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEBIAN_DIR = PROJECT_ROOT / "debian"


class DebianPackagingTests(unittest.TestCase):
    def test_required_packaging_files_exist(self):
        required_files = [
            "changelog",
            "control",
            "copyright",
            "rules",
            "watch",
            "source/format",
            "upstream/metadata",
            "linux-file-manager.desktop",
            "linux-file-manager.metainfo.xml",
            "linux-file-manager.lintian-overrides",
            "linuxfm",
            "linuxfm.1",
        ]

        for relative_path in required_files:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((DEBIAN_DIR / relative_path).is_file())

    def test_control_declares_expected_package_and_dependencies(self):
        control = (DEBIAN_DIR / "control").read_text(encoding="utf-8")

        self.assertIn("Source: linux-file-manager", control)
        self.assertIn("Package: linux-file-manager", control)
        self.assertIn("debhelper-compat (= 13)", control)
        self.assertIn("python3-pyqt6", control)
        self.assertIn("python3-pyqt6.qtsvg", control)
        self.assertIn("qt6ct", control)
        self.assertIn("gvfs", control)
        self.assertIn("gvfs-backends", control)
        self.assertIn("gvfs-common", control)
        self.assertIn("gvfs-daemons", control)
        self.assertIn("gvfs-fuse", control)
        self.assertIn("gvfs-libs", control)
        self.assertIn("xdg-utils", control)
        self.assertIn("shared-mime-info", control)
        self.assertIn("desktop-file-utils", control)
        self.assertIn("cifs-utils", control)
        self.assertIn("nfs-common", control)
        self.assertIn("sshfs", control)
        self.assertIn("davfs2", control)
        self.assertIn("p7zip-full", control)
        self.assertIn("unrar-free", control)

    def test_rules_is_executable_and_installs_expected_paths(self):
        rules = DEBIAN_DIR / "rules"
        mode = rules.stat().st_mode
        content = rules.read_text(encoding="utf-8")

        self.assertTrue(mode & stat.S_IXUSR)
        self.assertIn("usr/bin/linuxfm", content)
        self.assertIn("usr/lib/python3/dist-packages", content)
        self.assertIn("usr/share/linux-file-manager/i18n", content)
        self.assertIn("usr/share/man/man1/linuxfm.1", content)
        self.assertNotIn("usr/share/linux-file-manager/main.py", content)

    def test_debian_desktop_file_is_valid_application_entry(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read(DEBIAN_DIR / "linux-file-manager.desktop", encoding="utf-8")

        self.assertIn("Desktop Entry", parser)
        entry = parser["Desktop Entry"]
        self.assertEqual(entry["Type"], "Application")
        self.assertEqual(entry["Exec"], "linuxfm %U")
        self.assertEqual(entry["Icon"], "linux-file-manager")

    def test_debian_metainfo_is_parseable(self):
        root = ET.parse(DEBIAN_DIR / "linux-file-manager.metainfo.xml").getroot()

        self.assertEqual(root.tag, "component")
        self.assertEqual(root.findtext("id"), "io.github.wachin.LinuxFileManager")
        self.assertEqual(root.findtext("provides/binary"), "linuxfm")
        self.assertIsNotNone(root.find("content_rating"))

    def test_source_format_is_quilt(self):
        source_format = (DEBIAN_DIR / "source" / "format").read_text(encoding="utf-8").strip()

        self.assertEqual(source_format, "3.0 (quilt)")

    def test_upstream_metadata_declares_repository_and_bug_tracker(self):
        metadata = (DEBIAN_DIR / "upstream" / "metadata").read_text(encoding="utf-8")

        self.assertIn("Bug-Database: https://github.com/wachin/linuxfilemanager/issues", metadata)
        self.assertIn("Bug-Submit: https://github.com/wachin/linuxfilemanager/issues/new", metadata)
        self.assertIn("Repository: https://github.com/wachin/linuxfilemanager.git", metadata)
        self.assertIn("Repository-Browse: https://github.com/wachin/linuxfilemanager", metadata)

if __name__ == "__main__":
    unittest.main()
