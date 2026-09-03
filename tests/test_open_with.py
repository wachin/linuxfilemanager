import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import lfmapp.utils.open_with as open_with_module


class OpenWithTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.apps_dir = self.temp_dir / "applications"
        self.apps_dir.mkdir(parents=True, exist_ok=True)
        self.desktop_file = self.apps_dir / "testapp.desktop"
        self.desktop_file.write_text(
            "[Desktop Entry]\n"
            "Name=Test App\n"
            "Exec=testapp %f\n"
            "MimeType=text/plain;application/octet-stream;\n"
            "Type=Application\n",
            encoding="utf-8",
        )
        self.path = self.temp_dir / "file.txt"
        self.path.write_text("hello", encoding="utf-8")

    def tearDown(self):
        for file in self.temp_dir.rglob("*"):
            if file.is_file():
                file.unlink()
        for folder in sorted(self.temp_dir.rglob("*"), reverse=True):
            if folder.is_dir():
                folder.rmdir()
        if self.temp_dir.exists():
            self.temp_dir.rmdir()

    @patch("lfmapp.utils.open_with.subprocess.run")
    def test_get_available_applications_returns_desktop_entries(self, mock_run):
        with patch.dict(open_with_module.os.environ, {"XDG_DATA_HOME": str(self.temp_dir), "XDG_DATA_DIRS": ""}, clear=True):
            mock_run.return_value = Mock(returncode=0, stdout="testapp.desktop\n")
            with patch.object(open_with_module, "_get_mime_type", return_value="text/plain"):
                apps = open_with_module.get_available_applications(self.path)

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0][0], "testapp.desktop")
        self.assertEqual(apps[0][1], "Test App")

    @patch("lfmapp.utils.open_with.subprocess.run")
    def test_get_available_applications_returns_empty_when_no_mime(self, mock_run):
        with patch.dict(open_with_module.os.environ, {"XDG_DATA_HOME": str(self.temp_dir), "XDG_DATA_DIRS": ""}, clear=True):
            with patch.object(open_with_module, "_get_mime_type", return_value=None):
                apps = open_with_module.get_available_applications(self.path)

        self.assertEqual(apps, [])

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0][0], "testapp.desktop")
        self.assertEqual(apps[0][1], "Test App")

    @patch("lfmapp.utils.open_with.os.environ", new_callable=dict)
    @patch("lfmapp.utils.open_with.subprocess.run")
    def test_get_available_applications_returns_empty_when_no_mime(self, mock_run, mock_environ):
        mock_environ.update({"XDG_DATA_HOME": str(self.temp_dir), "XDG_DATA_DIRS": ""})
        with patch.object(open_with_module, "_get_mime_type", return_value=None):
            apps = open_with_module.get_available_applications(self.path)

        self.assertEqual(apps, [])

    def test_build_xdg_email_command(self):
        second_path = self.temp_dir / "second.txt"
        second_path.write_text("second", encoding="utf-8")

        command = open_with_module.build_xdg_email_command(
            [self.path, second_path],
            "Shared files",
        )

        self.assertEqual(
            command,
            [
                "xdg-email",
                "--subject",
                "Shared files",
                "--attach",
                str(self.path),
                "--attach",
                str(second_path),
            ],
        )

    @patch("lfmapp.utils.open_with.subprocess.Popen")
    @patch("lfmapp.utils.open_with.shutil.which", return_value="/usr/bin/xdg-email")
    def test_send_email_with_attachments_launches_xdg_email(self, _mock_which, mock_popen):
        result = open_with_module.send_email_with_attachments([self.path])

        self.assertTrue(result)
        mock_popen.assert_called_once()
        self.assertEqual(mock_popen.call_args.args[0][0], "xdg-email")

    @patch("lfmapp.utils.open_with.shutil.which", return_value="/usr/bin/xdg-email")
    def test_send_email_with_attachments_rejects_directories(self, _mock_which):
        result = open_with_module.send_email_with_attachments([self.temp_dir])

        self.assertFalse(result)

    @patch("lfmapp.utils.open_with.shutil.which", return_value=None)
    def test_send_email_with_attachments_returns_false_without_xdg_email(self, _mock_which):
        result = open_with_module.send_email_with_attachments([self.path])

        self.assertFalse(result)

    @patch("lfmapp.utils.open_with.set_default_application", return_value=True)
    def test_set_default_application_for_file_uses_file_mime_type(self, mock_set_default):
        with patch.object(open_with_module, "get_mime_type", return_value="text/plain"):
            result = open_with_module.set_default_application_for_file(
                self.path,
                "testapp.desktop",
            )

        self.assertTrue(result)
        mock_set_default.assert_called_once_with("text/plain", "testapp.desktop")

    @patch("lfmapp.utils.open_with.set_default_application")
    def test_set_default_application_for_file_returns_false_without_mime(self, mock_set_default):
        with patch.object(open_with_module, "get_mime_type", return_value=None):
            result = open_with_module.set_default_application_for_file(
                self.path,
                "testapp.desktop",
            )

        self.assertFalse(result)
        mock_set_default.assert_not_called()

    def test_build_desktop_entry_command(self):
        launcher = self.temp_dir / "launcher.desktop"
        launcher.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Launcher\n"
            "Exec=testapp --open %f %c %%\n",
            encoding="utf-8",
        )

        command = open_with_module.build_desktop_entry_command(launcher, self.path)

        self.assertEqual(command, ["testapp", "--open", str(self.path), "%"])

    @patch("lfmapp.utils.open_with.subprocess.Popen")
    def test_open_desktop_entry_launches_application_entries(self, mock_popen):
        launcher = self.temp_dir / "launcher.desktop"
        launcher.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Launcher\n"
            "Exec=testapp %f\n",
            encoding="utf-8",
        )

        result = open_with_module.open_desktop_entry(launcher)

        self.assertTrue(result)
        self.assertEqual(mock_popen.call_args.args[0], ["testapp", str(launcher)])

    @patch("lfmapp.utils.open_with.subprocess.Popen")
    def test_open_desktop_entry_launches_link_entries(self, mock_popen):
        launcher = self.temp_dir / "link.desktop"
        launcher.write_text(
            "[Desktop Entry]\n"
            "Type=Link\n"
            "Name=Link\n"
            "URL=https://example.test\n",
            encoding="utf-8",
        )

        result = open_with_module.open_desktop_entry(launcher)

        self.assertTrue(result)
        self.assertEqual(mock_popen.call_args.args[0], ["xdg-open", "https://example.test"])

    @patch("lfmapp.utils.open_with.subprocess.Popen")
    def test_launch_application_for_path_launches_gtk_launch(self, mock_popen):
        result = open_with_module.launch_application_for_path("testapp.desktop", self.path)

        self.assertTrue(result)
        self.assertEqual(
            mock_popen.call_args.args[0],
            ["gtk-launch", "testapp.desktop", str(self.path)],
        )


if __name__ == "__main__":
    unittest.main()
