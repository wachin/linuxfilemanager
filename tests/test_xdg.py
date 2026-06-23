import os
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

from lfmapp.core.xdg import get_xdg_directory, get_xdg_user_dirs


class XdgUserDirsTests(unittest.TestCase):
    def test_prefers_xdg_user_dir_command_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            desktop = home / "Escritorio"
            desktop.mkdir()

            with patch("lfmapp.core.xdg._read_xdg_user_dir_command") as read_command:
                read_command.side_effect = lambda key, **kwargs: desktop if key == "DESKTOP" else None
                result = get_xdg_user_dirs(home=home, user_dirs_file=home / ".config" / "missing")

            self.assertEqual(result, OrderedDict([("desktop", desktop)]))

    def test_falls_back_to_user_dirs_file_and_expands_home(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            docs = home / "Documentos"
            docs.mkdir()
            user_dirs = home / ".config" / "user-dirs.dirs"
            user_dirs.parent.mkdir()
            user_dirs.write_text(
                'XDG_DOCUMENTS_DIR="$HOME/Documentos"\n',
                encoding="utf-8",
            )

            with patch("lfmapp.core.xdg._read_xdg_user_dir_command", return_value=None):
                result = get_xdg_user_dirs(home=home, user_dirs_file=user_dirs)

            self.assertEqual(result, OrderedDict([("documents", docs)]))

    def test_expands_tilde_and_environment_variables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            pictures_root = home / "MediaRoot"
            pictures = pictures_root / "Imagenes"
            pictures.mkdir(parents=True)
            user_dirs = home / ".config" / "user-dirs.dirs"
            user_dirs.parent.mkdir()
            user_dirs.write_text(
                'XDG_PICTURES_DIR="$MEDIA_ROOT/Imagenes"\n',
                encoding="utf-8",
            )

            with patch("lfmapp.core.xdg._read_xdg_user_dir_command", return_value=None):
                result = get_xdg_user_dirs(
                    home=home,
                    user_dirs_file=user_dirs,
                    env={"MEDIA_ROOT": str(pictures_root), "HOME": str(home)},
                )

            self.assertEqual(result, OrderedDict([("pictures", pictures)]))

    def test_skips_duplicates_and_missing_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            user_dirs = home / ".config" / "user-dirs.dirs"
            user_dirs.parent.mkdir()
            existing = home / "Shared"
            existing.mkdir()
            user_dirs.write_text(
                '\n'.join(
                    [
                        'XDG_DOCUMENTS_DIR="$HOME/Shared"',
                        'XDG_DOWNLOAD_DIR="$HOME/Shared"',
                        'XDG_MUSIC_DIR="$HOME/Missing"',
                    ]
                ),
                encoding="utf-8",
            )

            with patch("lfmapp.core.xdg._read_xdg_user_dir_command", return_value=None):
                result = get_xdg_user_dirs(home=home, user_dirs_file=user_dirs)

            self.assertEqual(result, OrderedDict([("downloads", existing)]))

    def test_get_xdg_directory_returns_single_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            videos = home / "Videos"
            videos.mkdir()
            user_dirs = home / ".config" / "user-dirs.dirs"
            user_dirs.parent.mkdir()
            user_dirs.write_text('XDG_VIDEOS_DIR="$HOME/Videos"\n', encoding="utf-8")

            with patch("lfmapp.core.xdg._read_xdg_user_dir_command", return_value=None):
                result = get_xdg_directory("videos", home=home, user_dirs_file=user_dirs)

            self.assertEqual(result, videos)


if __name__ == "__main__":
    unittest.main()
