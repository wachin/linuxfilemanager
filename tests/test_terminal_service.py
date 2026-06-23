import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lfmapp.services.terminal_service import TerminalService


class TerminalServiceTests(unittest.TestCase):
    @patch("lfmapp.services.terminal_service.shutil.which")
    def test_detect_terminals_uses_preferred_order(self, mock_which):
        installed = {
            "xfce4-terminal": "/usr/bin/xfce4-terminal",
            "konsole": "/usr/bin/konsole",
            "qterminal": "/usr/bin/qterminal",
        }
        mock_which.side_effect = lambda name: installed.get(name)

        service = TerminalService()

        self.assertEqual(
            service.available_terminals,
            ["konsole", "qterminal", "xfce4-terminal"],
        )

    @patch("lfmapp.services.terminal_service.subprocess.Popen")
    @patch("lfmapp.services.terminal_service.shutil.which")
    def test_open_terminal_uses_konsole_without_geometry_flags(self, mock_which, mock_popen):
        mock_which.side_effect = lambda name: "/usr/bin/konsole" if name == "konsole" else None

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            service = TerminalService()

            result = service.open_terminal(path)

        self.assertTrue(result)
        cmd = mock_popen.call_args.args[0]
        self.assertEqual(cmd, ["konsole", "--workdir", str(path)])
        self.assertEqual(mock_popen.call_args.kwargs["cwd"], str(path))
        self.assertNotIn("--geometry", cmd)
        self.assertNotIn("--maximize", cmd)
        self.assertNotIn("--fullscreen", cmd)

    @patch("lfmapp.services.terminal_service.subprocess.Popen")
    @patch("lfmapp.services.terminal_service.shutil.which")
    def test_open_terminal_uses_qterminal_when_requested(self, mock_which, mock_popen):
        mock_which.side_effect = lambda name: "/usr/bin/qterminal" if name == "qterminal" else None

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            service = TerminalService()

            result = service.open_terminal(path, terminal="qterminal")

        self.assertTrue(result)
        self.assertEqual(
            mock_popen.call_args.args[0],
            ["qterminal", "--workdir", str(path)],
        )

    @patch("lfmapp.services.terminal_service.subprocess.Popen")
    @patch("lfmapp.services.terminal_service.shutil.which")
    def test_open_terminal_uses_xfce4_terminal_when_requested(self, mock_which, mock_popen):
        mock_which.side_effect = lambda name: "/usr/bin/xfce4-terminal" if name == "xfce4-terminal" else None

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            service = TerminalService()

            result = service.open_terminal(path, terminal="xfce4-terminal")

        self.assertTrue(result)
        self.assertEqual(
            mock_popen.call_args.args[0],
            ["xfce4-terminal", "--working-directory", str(path)],
        )

    @patch("lfmapp.services.terminal_service.subprocess.Popen")
    @patch("lfmapp.services.terminal_service.shutil.which")
    def test_open_terminal_uses_parent_for_file_paths(self, mock_which, mock_popen):
        mock_which.side_effect = lambda name: "/usr/bin/konsole" if name == "konsole" else None

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_path = root / "file.txt"
            file_path.write_text("hello", encoding="utf-8")
            service = TerminalService()

            result = service.open_terminal(file_path)

        self.assertTrue(result)
        self.assertEqual(
            mock_popen.call_args.args[0],
            ["konsole", "--workdir", str(root)],
        )
        self.assertEqual(mock_popen.call_args.kwargs["cwd"], str(root))

    @patch("lfmapp.services.terminal_service.subprocess.Popen")
    @patch("lfmapp.services.terminal_service.shutil.which")
    def test_open_terminal_falls_back_to_x_terminal_emulator_with_cwd(self, mock_which, mock_popen):
        mock_which.side_effect = (
            lambda name: "/usr/bin/x-terminal-emulator" if name == "x-terminal-emulator" else None
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            service = TerminalService()

            result = service.open_terminal(path)

        self.assertTrue(result)
        self.assertEqual(mock_popen.call_args.args[0], ["x-terminal-emulator"])
        self.assertEqual(mock_popen.call_args.kwargs["cwd"], str(path))

    @patch("lfmapp.services.terminal_service.subprocess.Popen")
    @patch("lfmapp.services.terminal_service.shutil.which")
    def test_open_terminal_uses_shared_config_preference(self, mock_which, mock_popen):
        installed = {
            "konsole": "/usr/bin/konsole",
            "qterminal": "/usr/bin/qterminal",
            "xfce4-terminal": "/usr/bin/xfce4-terminal",
        }
        mock_which.side_effect = lambda name: installed.get(name)

        class FakeConfig:
            def __init__(self):
                self.data = {"preferred_terminal": "qterminal"}

            def save(self):
                pass

        with tempfile.TemporaryDirectory() as tmpdir:
            service = TerminalService(FakeConfig())
            path = Path(tmpdir)

            result = service.open_terminal(path)

        self.assertTrue(result)
        self.assertEqual(
            mock_popen.call_args.args[0],
            ["qterminal", "--workdir", str(path)],
        )


if __name__ == "__main__":
    unittest.main()
