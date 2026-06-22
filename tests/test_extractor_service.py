import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from lfmapp.services.extractor_service import create_zip, extract_to


class ExtractorServiceTests(unittest.TestCase):
    def test_tar_extraction_skips_path_traversal_members(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive.tar"
            destination = root / "out"
            outside = root / "evil.txt"

            with tarfile.open(archive, "w") as tf:
                safe_data = b"safe"
                safe = tarfile.TarInfo("safe.txt")
                safe.size = len(safe_data)
                tf.addfile(safe, io.BytesIO(safe_data))

                evil_data = b"evil"
                evil = tarfile.TarInfo("../evil.txt")
                evil.size = len(evil_data)
                tf.addfile(evil, io.BytesIO(evil_data))

            extract_to(archive, destination)

            self.assertEqual((destination / "safe.txt").read_text(encoding="utf-8"), "safe")
            self.assertFalse(outside.exists())

    def test_tar_extraction_skips_symlinks_outside_destination(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive.tar"
            destination = root / "out"

            with tarfile.open(archive, "w") as tf:
                unsafe_link = tarfile.TarInfo("unsafe-link")
                unsafe_link.type = tarfile.SYMTYPE
                unsafe_link.linkname = "../outside.txt"
                tf.addfile(unsafe_link)

                safe_link = tarfile.TarInfo("safe-link")
                safe_link.type = tarfile.SYMTYPE
                safe_link.linkname = "safe-target.txt"
                tf.addfile(safe_link)

            extract_to(archive, destination)

            self.assertFalse((destination / "unsafe-link").exists())
            self.assertTrue((destination / "safe-link").is_symlink())

    def test_create_zip_from_single_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "folder"
            source.mkdir()
            (source / "inside.txt").write_text("content", encoding="utf-8")

            archive = create_zip(source)

            with zipfile.ZipFile(archive) as zf:
                self.assertEqual(zf.read("folder/inside.txt").decode("utf-8"), "content")

    def test_create_zip_from_multiple_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_path = root / "one.txt"
            file_path.write_text("one", encoding="utf-8")
            folder = root / "folder"
            folder.mkdir()
            (folder / "two.txt").write_text("two", encoding="utf-8")
            archive = root / "bundle.zip"

            result = create_zip([file_path, folder], archive)

            self.assertEqual(result, archive)
            with zipfile.ZipFile(archive) as zf:
                self.assertEqual(zf.read("one.txt").decode("utf-8"), "one")
                self.assertEqual(zf.read("folder/two.txt").decode("utf-8"), "two")


if __name__ == "__main__":
    unittest.main()
