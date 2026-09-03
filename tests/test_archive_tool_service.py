"""Unit tests for the delegated archive tool service (ROADMAP Phase 10.1)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from lfmapp.core import config as config_module
from lfmapp.core.config import Config
from lfmapp.services.archive_tool_service import (
    ArchiveToolService,
    ArkBackend,
    PeaZipBackend,
)

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


class ArkBackendCommandTests(unittest.TestCase):
    def setUp(self):
        self.backend = ArkBackend()
        self.archive = Path("/tmp/photos.zip")

    def test_extract_here_uses_batch_mode(self):
        self.assertEqual(
            self.backend.extract_here_command(self.archive),
            ["ark", "-b", "/tmp/photos.zip"],
        )

    def test_extract_into_new_folder_uses_autosubfolder(self):
        self.assertEqual(
            self.backend.extract_into_new_folder_command(self.archive),
            ["ark", "-b", "-a", "/tmp/photos.zip"],
        )

    def test_extract_to_passes_destination(self):
        self.assertEqual(
            self.backend.extract_to_command(self.archive, Path("/tmp/out")),
            ["ark", "-b", "/tmp/photos.zip", "-o", "/tmp/out"],
        )

    def test_open_and_create_commands(self):
        self.assertEqual(self.backend.open_command(self.archive), ["ark", "/tmp/photos.zip"])
        self.assertEqual(
            self.backend.create_archive_command([Path("/tmp/a"), Path("/tmp/b")]),
            ["ark", "-c", "/tmp/a", "/tmp/b"],
        )
        self.assertEqual(
            self.backend.quick_add_command([Path("/tmp/a")], Path("/tmp/a.zip")),
            ["ark", "-t", "/tmp/a.zip", "/tmp/a"],
        )

    def test_ark_has_no_integrity_test(self):
        self.assertIsNone(self.backend.test_command(self.archive))
        self.assertTrue(self.backend.needs_destination_arg())


class PeaZipBackendCommandTests(unittest.TestCase):
    def setUp(self):
        self.backend = PeaZipBackend()
        self.archive = Path("/tmp/photos.zip")

    def test_extract_commands(self):
        self.assertEqual(
            self.backend.extract_here_command(self.archive),
            ["peazip", "-ext2here", "/tmp/photos.zip"],
        )
        self.assertEqual(
            self.backend.extract_into_new_folder_command(self.archive),
            ["peazip", "-ext2folder", "/tmp/photos.zip"],
        )
        self.assertEqual(
            self.backend.extract_to_command(self.archive, None),
            ["peazip", "-ext2full", "/tmp/photos.zip"],
        )

    def test_create_open_and_test_commands(self):
        self.assertEqual(
            self.backend.create_archive_command([Path("/tmp/a")]),
            ["peazip", "-add2archive", "/tmp/a"],
        )
        self.assertEqual(
            self.backend.open_command(self.archive),
            ["peazip", "-ext2browse", "/tmp/photos.zip"],
        )
        self.assertEqual(
            self.backend.test_command(self.archive),
            ["peazip", "-ext2test", "/tmp/photos.zip"],
        )
        self.assertFalse(self.backend.needs_destination_arg())

    def test_quick_add_format_flags(self):
        files = [Path("/tmp/a")]
        self.assertEqual(
            self.backend.quick_add_command(files, Path("/tmp/x.zip"))[1], "-add2zip"
        )
        self.assertEqual(
            self.backend.quick_add_command(files, Path("/tmp/x.7z"))[1], "-add27z"
        )


class ArchiveToolServiceTests(unittest.TestCase):
    def _config_with_tool(self, tmpdir, tool=None):
        old_dir = config_module.CONFIG_DIR
        old_file = config_module.CONFIG_FILE
        config_module.CONFIG_DIR = Path(tmpdir)
        config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
        try:
            config = Config()
            if tool is not None:
                config.set_archive_tool(tool)
            return config
        finally:
            config_module.CONFIG_DIR = old_dir
            config_module.CONFIG_FILE = old_file

    def test_default_tool_is_ark(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config_with_tool(tmpdir)
            service = ArchiveToolService(config)
            self.assertEqual(service.tool_id, "ark")
            self.assertIsInstance(service.backend, ArkBackend)

    def test_peazip_selection_from_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config_with_tool(tmpdir, "peazip")
            service = ArchiveToolService(config)
            self.assertIsInstance(service.backend, PeaZipBackend)

    def test_invalid_tool_falls_back_to_ark(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config_with_tool(tmpdir)
            config.data["archive_tool"] = "winrar"
            service = ArchiveToolService(config)
            self.assertEqual(service.tool_id, "ark")

    def test_archive_tool_config_property_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config_with_tool(tmpdir)
            self.assertEqual(config.archive_tool, "ark")
            config.set_archive_tool("peazip")
            self.assertEqual(config.archive_tool, "peazip")
            reloaded = Config()
            self.assertEqual(reloaded.archive_tool, "peazip")
            config.set_archive_tool("not-a-tool")
            self.assertEqual(config.archive_tool, "peazip")

    def test_launcher_receives_command_and_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config_with_tool(tmpdir)
            launched = []
            service = ArchiveToolService(
                config, launcher=lambda cmd, cwd=None: launched.append((cmd, cwd)) or True
            )
            archive = Path(tmpdir) / "data.zip"
            self.assertTrue(service.extract_here(archive))
            self.assertEqual(
                launched, [(["ark", "-b", str(archive)], archive.parent)]
            )

    def test_extract_to_launches_destination_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config_with_tool(tmpdir)
            launched = []
            service = ArchiveToolService(
                config, launcher=lambda cmd, cwd=None: launched.append(cmd) or True
            )
            archive = Path(tmpdir) / "data.zip"
            destination = Path(tmpdir) / "out"
            self.assertTrue(service.extract_to(archive, destination))
            self.assertEqual(launched[0][-2:], ["-o", str(destination)])

    def test_quick_add_computes_default_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config_with_tool(tmpdir)
            launched = []
            service = ArchiveToolService(
                config, launcher=lambda cmd, cwd=None: launched.append(cmd) or True
            )
            source = Path(tmpdir) / "report.txt"
            self.assertTrue(service.quick_add([source]))
            self.assertEqual(
                launched[0], ["ark", "-t", str(Path(tmpdir) / "report.txt.zip"), str(source)]
            )
            self.assertFalse(service.quick_add([]))

    def test_test_archive_returns_false_for_ark(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config_with_tool(tmpdir)
            service = ArchiveToolService(config, launcher=lambda cmd, cwd=None: True)
            self.assertFalse(service.test_archive(Path(tmpdir) / "a.zip"))

    def test_availability_uses_which(self):
        service = ArchiveToolService()
        with patch("shutil.which", return_value="/usr/bin/ark"):
            self.assertTrue(service.is_available())
        with patch("shutil.which", return_value=None):
            self.assertFalse(service.is_available())
        self.assertIn("apt install ark", service.install_hint)


class ArchiveToolMenuTests(unittest.TestCase):
    """GUI tests for the delegated submenu on the main window."""

    def setUp(self):
        _ensure_app()

    def _make_window(self, tmpdir, tool=None):
        old_dir = config_module.CONFIG_DIR
        old_file = config_module.CONFIG_FILE
        config_module.CONFIG_DIR = Path(tmpdir)
        config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
        try:
            from lfmapp.ui.main_window import MainWindow

            window = MainWindow()
            if tool:
                window.config.set_archive_tool(tool)
            return window
        finally:
            config_module.CONFIG_DIR = old_dir
            config_module.CONFIG_FILE = old_file

    def test_menu_titles_and_archive_actions(self):
        from lfmapp.services import is_archive

        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "sample.zip"
            archive.write_bytes(b"PK\x05\x06" + b"\0" * 18)
            self.assertTrue(is_archive(archive))

            window = self._make_window(tmpdir)
            try:
                with patch.object(
                    window.archive_service.__class__, "is_available", return_value=True
                ):
                    menu = window._archive_tool_menu(window, [archive])
                self.assertEqual(menu.title(), "Ark")
                texts = [a.text() for a in menu.actions()]
                self.assertIn("Extract Here", texts)
                self.assertIn("Extract Into New Folder", texts)
                self.assertIn("Extract to...", texts)
                self.assertIn("Open with Ark", texts)
                self.assertIn("Add to Archive...", texts)
                self.assertIn("Add to ZIP", texts)
                # Ark has no integrity test
                self.assertNotIn("Check Integrity", texts)
            finally:
                window.deleteLater()

    def test_peazip_menu_includes_integrity_test(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "sample.zip"
            archive.write_bytes(b"PK\x05\x06" + b"\0" * 18)

            window = self._make_window(tmpdir, tool="peazip")
            try:
                with patch.object(
                    window.archive_service.__class__, "is_available", return_value=True
                ):
                    menu = window._archive_tool_menu(window, [archive])
                self.assertEqual(menu.title(), "PeaZip")
                texts = [a.text() for a in menu.actions()]
                self.assertIn("Open with PeaZip", texts)
                self.assertIn("Check Integrity", texts)
            finally:
                window.deleteLater()

    def test_missing_tool_shows_notice_not_empty_menu(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "sample.zip"
            archive.write_bytes(b"PK\x05\x06" + b"\0" * 18)

            window = self._make_window(tmpdir)
            try:
                with patch.object(
                    window.archive_service.__class__, "is_available", return_value=False
                ):
                    menu = window._archive_tool_menu(window, [archive])
                actions = menu.actions()
                self.assertEqual(len(actions), 1)
                self.assertFalse(actions[0].isEnabled())
                self.assertIn("not installed", actions[0].text())
            finally:
                window.deleteLater()


if __name__ == "__main__":
    unittest.main()
