import shutil
import tempfile
import unittest
from pathlib import Path

from lfm.services.file_operations import FileOperations


class FileOperationsTests(unittest.TestCase):
    def test_copy_file_and_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            dest_dir = Path(tmpdir) / "dest"
            src_dir.mkdir()
            (src_dir / "file1.txt").write_text("hello", encoding="utf-8")
            nested = src_dir / "nested"
            nested.mkdir()
            (nested / "file2.txt").write_text("world", encoding="utf-8")

            FileOperations.copy(src_dir, dest_dir)

            copied_dir = dest_dir / "src"
            self.assertTrue(copied_dir.exists())
            self.assertEqual((copied_dir / "file1.txt").read_text(encoding="utf-8"), "hello")
            self.assertEqual((copied_dir / "nested" / "file2.txt").read_text(encoding="utf-8"), "world")

    def test_move_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "move.txt"
            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()
            src_file.write_text("move me", encoding="utf-8")

            FileOperations.move(src_file, dest_dir)

            moved_file = dest_dir / "move.txt"
            self.assertTrue(moved_file.exists())
            self.assertEqual(moved_file.read_text(encoding="utf-8"), "move me")
            self.assertFalse(src_file.exists())

    def test_desktop_directory_uses_xdg_user_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            user_dirs = home / ".config" / "user-dirs.dirs"
            user_dirs.parent.mkdir()
            user_dirs.write_text('XDG_DESKTOP_DIR="$HOME/Escritorio"\n', encoding="utf-8")

            self.assertEqual(
                FileOperations.desktop_directory(home=home, user_dirs_file=user_dirs),
                home / "Escritorio",
            )

    def test_desktop_directory_falls_back_to_home_desktop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)

            self.assertEqual(
                FileOperations.desktop_directory(home=home, user_dirs_file=home / "missing"),
                home / "Desktop",
            )

    def test_ensure_desktop_directory_creates_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            desktop = FileOperations.ensure_desktop_directory(
                home=home,
                user_dirs_file=home / "missing",
            )

            self.assertTrue(desktop.is_dir())
            self.assertEqual(desktop, home / "Desktop")

    def test_create_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            created = FileOperations.create_multiple(
                root,
                ["one.txt", "", "two.txt"],
                "file",
            )

            self.assertEqual(created, [root / "one.txt", root / "two.txt"])
            self.assertTrue((root / "one.txt").is_file())
            self.assertTrue((root / "two.txt").is_file())

    def test_create_multiple_folders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            created = FileOperations.create_multiple(
                root,
                ["alpha", "beta"],
                "folder",
            )

            self.assertEqual(created, [root / "alpha", root / "beta"])
            self.assertTrue((root / "alpha").is_dir())
            self.assertTrue((root / "beta").is_dir())

    def test_create_multiple_rejects_duplicate_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                FileOperations.create_multiple(
                    Path(tmpdir),
                    ["same.txt", "same.txt"],
                    "file",
                )

    def test_create_multiple_rejects_nested_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                FileOperations.create_multiple(
                    Path(tmpdir),
                    ["nested/item.txt"],
                    "file",
                )


if __name__ == "__main__":
    unittest.main()
