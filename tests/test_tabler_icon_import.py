import tempfile
import unittest
from pathlib import Path

from scripts import import_tabler_icon


class TablerIconImportTests(unittest.TestCase):
    def test_import_icon_copies_svg_into_variant_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "source"
            destination_root = root / "dest"
            (source_root / "outline").mkdir(parents=True)
            source_file = source_root / "outline" / "folder.svg"
            source_file.write_text("<svg/>", encoding="utf-8")

            old_source_root = import_tabler_icon.SOURCE_ROOT
            old_destination_root = import_tabler_icon.DESTINATION_ROOT
            import_tabler_icon.SOURCE_ROOT = source_root
            import_tabler_icon.DESTINATION_ROOT = destination_root
            try:
                copied_path = import_tabler_icon.import_icon(
                    icon_name="folder",
                    variant="outline",
                    dest_name="sidebar-folder",
                )
            finally:
                import_tabler_icon.SOURCE_ROOT = old_source_root
                import_tabler_icon.DESTINATION_ROOT = old_destination_root

            self.assertEqual(copied_path, destination_root / "outline" / "sidebar-folder.svg")
            self.assertTrue(copied_path.is_file())
            self.assertEqual(copied_path.read_text(encoding="utf-8"), "<svg/>")

    def test_import_icon_requires_force_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "source"
            destination_root = root / "dest"
            (source_root / "filled").mkdir(parents=True)
            source_file = source_root / "filled" / "star.svg"
            source_file.write_text("<svg new/>", encoding="utf-8")
            destination_file = destination_root / "filled" / "star.svg"
            destination_file.parent.mkdir(parents=True)
            destination_file.write_text("<svg old/>", encoding="utf-8")

            old_source_root = import_tabler_icon.SOURCE_ROOT
            old_destination_root = import_tabler_icon.DESTINATION_ROOT
            import_tabler_icon.SOURCE_ROOT = source_root
            import_tabler_icon.DESTINATION_ROOT = destination_root
            try:
                with self.assertRaises(FileExistsError):
                    import_tabler_icon.import_icon(
                        icon_name="star",
                        variant="filled",
                        dest_name="star",
                    )

                copied_path = import_tabler_icon.import_icon(
                    icon_name="star",
                    variant="filled",
                    dest_name="star",
                    force=True,
                )
            finally:
                import_tabler_icon.SOURCE_ROOT = old_source_root
                import_tabler_icon.DESTINATION_ROOT = old_destination_root

            self.assertEqual(copied_path.read_text(encoding="utf-8"), "<svg new/>")


if __name__ == "__main__":
    unittest.main()
