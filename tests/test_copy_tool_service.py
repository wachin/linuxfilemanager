"""Unit and GUI tests for Ultracopier copy/move delegation (ROADMAP 10.2)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from lfmapp.core import config as config_module
from lfmapp.core.config import Config
from lfmapp.services.copy_tool_service import CopyToolService, UltracopierBackend

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


class UltracopierCommandTests(unittest.TestCase):
    def setUp(self):
        self.backend = UltracopierBackend()

    def test_copy_command_single_source(self):
        self.assertEqual(
            self.backend.copy_command([Path("/tmp/a.txt")], Path("/dst")),
            ["ultracopier", "cp", "/tmp/a.txt", "/dst"],
        )

    def test_move_command_multiple_sources(self):
        self.assertEqual(
            self.backend.move_command(
                [Path("/tmp/a"), Path("/tmp/b")], Path("/dst")
            ),
            ["ultracopier", "mv", "/tmp/a", "/tmp/b", "/dst"],
        )

    def test_paths_with_spaces_stay_single_arguments(self):
        command = self.backend.copy_command(
            [Path("/tmp/my file.txt")], Path("/tmp/target dir")
        )
        self.assertEqual(
            command,
            ["ultracopier", "cp", "/tmp/my file.txt", "/tmp/target dir"],
        )

    def test_none_destination_makes_ultracopier_ask(self):
        self.assertEqual(
            self.backend.copy_command([Path("/tmp/a")], None)[-1], "?"
        )
        self.assertEqual(
            self.backend.move_command([Path("/tmp/a")], None)[-1], "?"
        )

    def test_empty_sources_rejected(self):
        with self.assertRaises(ValueError):
            self.backend.copy_command([], Path("/dst"))
        with self.assertRaises(ValueError):
            self.backend.move_command([], None)


class CopyToolServiceResolutionTests(unittest.TestCase):
    def _config(self, tmpdir, tool=None):
        old_dir = config_module.CONFIG_DIR
        old_file = config_module.CONFIG_FILE
        config_module.CONFIG_DIR = Path(tmpdir)
        config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
        try:
            config = Config()
            if tool is not None:
                config.set_copy_tool(tool)
            return config
        finally:
            config_module.CONFIG_DIR = old_dir
            config_module.CONFIG_FILE = old_file

    def test_default_tool_is_native(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config(tmpdir)
            service = CopyToolService(config)
            self.assertEqual(service.tool_id, "native")
            self.assertFalse(service.delegate)

    def test_ultracopier_selected_and_installed_delegates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config(tmpdir, "ultracopier")
            service = CopyToolService(config)
            with patch("shutil.which", return_value="/usr/bin/ultracopier"):
                self.assertTrue(service.delegate)

    def test_ultracopier_selected_but_missing_does_not_delegate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config(tmpdir, "ultracopier")
            service = CopyToolService(config)
            with patch("shutil.which", return_value=None):
                self.assertFalse(service.delegate)

    def test_invalid_value_falls_back_to_native(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config(tmpdir)
            config.data["copy_tool"] = "rsync"
            self.assertEqual(CopyToolService(config).tool_id, "native")

    def test_copy_tool_config_persists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_dir = config_module.CONFIG_DIR
            old_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir)
            config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
            try:
                config = Config()
                config.set_copy_tool("ultracopier")
                self.assertEqual(Config().copy_tool, "ultracopier")
                config.set_copy_tool("invalid")
                self.assertEqual(config.copy_tool, "ultracopier")
            finally:
                config_module.CONFIG_DIR = old_dir
                config_module.CONFIG_FILE = old_file

    def test_launcher_receives_command(self):
        launched = []
        service = CopyToolService(launcher=lambda cmd: launched.append(cmd) or True)
        self.assertTrue(service.copy([Path("/tmp/a")], Path("/dst")))
        self.assertEqual(launched, [["ultracopier", "cp", "/tmp/a", "/dst"]])
        self.assertTrue(service.move([Path("/tmp/a")]))
        self.assertEqual(launched[-1], ["ultracopier", "mv", "/tmp/a", "?"])

    def test_empty_sources_do_not_launch(self):
        service = CopyToolService(launcher=lambda cmd: True)
        self.assertFalse(service.copy([], Path("/dst")))


class MainWindowUltracopierDelegationTests(unittest.TestCase):
    """GUI tests: with copy_tool=ultracopier the UI delegates transfers."""

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
                window.config.set_copy_tool(tool)
            return window
        finally:
            config_module.CONFIG_DIR = old_dir
            config_module.CONFIG_FILE = old_file

    def _instrument(self, window):
        launched = []
        window.copy_tool_service._launcher = lambda cmd: launched.append(cmd) or True
        return launched

    def test_paste_delegates_copy_when_configured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "file.txt"
            source.write_text("data")
            window = self._make_window(tmpdir, tool="ultracopier")
            try:
                launched = self._instrument(window)
                window._clipboard_paths = [source]
                window._clipboard_mode = "copy"
                with (
                    patch("shutil.which", return_value="/usr/bin/ultracopier"),
                    patch.object(
                        window.workspace, "current_path", return_value=Path(tmpdir)
                    ),
                    patch.object(window, "_register_worker") as register_mock,
                ):
                    window.paste_from_clipboard()
                self.assertEqual(
                    launched, [["ultracopier", "cp", str(source), tmpdir]]
                )
                register_mock.assert_not_called()
                # Clipboard kept for copy mode
                self.assertEqual(window._clipboard_mode, "copy")
            finally:
                window.deleteLater()

    def test_paste_delegates_move_and_clears_clipboard(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "file.txt"
            source.write_text("data")
            window = self._make_window(tmpdir, tool="ultracopier")
            try:
                launched = self._instrument(window)
                window._clipboard_paths = [source]
                window._clipboard_mode = "cut"
                with (
                    patch("shutil.which", return_value="/usr/bin/ultracopier"),
                    patch.object(
                        window.workspace, "current_path", return_value=Path(tmpdir)
                    ),
                ):
                    window.paste_from_clipboard()
                self.assertEqual(
                    launched, [["ultracopier", "mv", str(source), tmpdir]]
                )
                self.assertEqual(window._clipboard_paths, [])
                self.assertIsNone(window._clipboard_mode)
            finally:
                window.deleteLater()

    def test_native_default_keeps_worker_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "file.txt"
            source.write_text("data")
            window = self._make_window(tmpdir)
            try:
                launched = self._instrument(window)
                window._clipboard_paths = [source]
                window._clipboard_mode = "copy"
                with (
                    patch.object(
                        window.workspace, "current_path", return_value=Path(tmpdir)
                    ),
                    patch.object(window, "_register_worker") as register_mock,
                ):
                    window.paste_from_clipboard()
                self.assertEqual(launched, [])
                register_mock.assert_called_once()
            finally:
                window.deleteLater()

    def test_explicit_copy_with_ultracopier_asks_destination(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "file.txt"
            source.write_text("data")
            window = self._make_window(tmpdir)  # native preference!
            try:
                launched = self._instrument(window)
                with (
                    patch("shutil.which", return_value="/usr/bin/ultracopier"),
                    patch.object(
                        window.workspace, "selected_paths", return_value=[source]
                    ),
                ):
                    window.copy_selection_with_ultracopier()
                self.assertEqual(
                    launched, [["ultracopier", "cp", str(source), "?"]]
                )
            finally:
                window.deleteLater()


if __name__ == "__main__":
    unittest.main()
