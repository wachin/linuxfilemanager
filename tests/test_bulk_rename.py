"""Tests for the bulk rename engine and dialog (ROADMAP Phase 6.2)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from lfmapp.services.bulk_rename import (
    BulkRenamePreset,
    RenamePlan,
    Transform,
    TransformType,
    apply_names_list,
    apply_plan,
    build_plan,
    sanitize_filename,
    split_name,
)

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


def _make_files(tmpdir, *names):
    root = Path(tmpdir)
    paths = []
    for name in names:
        p = root / name
        p.write_text("x")
        paths.append(p)
    return paths


class NameSplittingTests(unittest.TestCase):
    def test_simple_extension(self):
        self.assertEqual(split_name("report.pdf").stem, "report")
        self.assertEqual(split_name("report.pdf").extension, ".pdf")

    def test_multi_part_extension(self):
        parts = split_name("archive.tar.gz")
        self.assertEqual(parts.stem, "archive")
        self.assertEqual(parts.extension, ".tar.gz")

    def test_no_extension(self):
        parts = split_name("Makefile")
        self.assertEqual(parts.stem, "Makefile")
        self.assertEqual(parts.extension, "")


class BuildPlanTests(unittest.TestCase):
    def test_search_replace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt")
            transforms = [Transform(TransformType.SEARCH_REPLACE, search="t", replace="z")]
            plan = build_plan(paths, transforms)
            result = {i.original_name: i.new_name for i in plan.items}
            # "t" -> "z" everywhere in the full name (case-insensitive).
            self.assertEqual(result["a.txt"], "a.zxz")
            self.assertEqual(result["b.txt"], "b.zxz")

    def test_search_replace_ignore_extension_by_default(self):
        # Search/replace applies to the whole name; case-insensitive default.
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "Photo.JPG")
            transforms = [Transform(TransformType.SEARCH_REPLACE, search="photo", replace="pic")]
            plan = build_plan(paths, transforms)
            self.assertEqual(plan.items[0].new_name, "pic.JPG")

    def test_prefix_and_suffix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt")
            transforms = [
                Transform(TransformType.PREFIX, value="pre_"),
                Transform(TransformType.SUFFIX, value="_post"),
            ]
            plan = build_plan(paths, transforms)
            self.assertEqual(plan.items[0].new_name, "pre_a_post.txt")

    def test_numbering(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt", "c.txt")
            transforms = [
                Transform(TransformType.SEARCH_REPLACE, search="", replace=""),
                Transform(TransformType.NUMBERING, start=1, digits=2),
            ]
            # No-op search then numbering
            transforms = [Transform(TransformType.NUMBERING, start=1, digits=2)]
            plan = build_plan(paths, transforms)
            self.assertEqual(plan.items[0].new_name, "a01.txt")
            self.assertEqual(plan.items[1].new_name, "b02.txt")
            self.assertEqual(plan.items[2].new_name, "c03.txt")

    def test_case_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "hello.txt")
            transforms = [Transform(TransformType.CASE, value="upper")]
            plan = build_plan(paths, transforms)
            self.assertEqual(plan.items[0].new_name, "HELLO.TXT")

    def test_regex_rename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "img_001.jpg")
            transforms = [
                Transform(
                    TransformType.REGEX,
                    search=r"img_(\d+)",
                    replace=r"photo_\1",
                )
            ]
            plan = build_plan(paths, transforms)
            self.assertEqual(plan.items[0].new_name, "photo_001.jpg")

    def test_duplicate_conflict_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt")
            # Regex maps every name to the same target -> second becomes duplicate.
            transforms = [Transform(TransformType.REGEX, search=".*", replace="same.txt")]
            plan = build_plan(paths, transforms)
            conflicts = [i.conflict for i in plan.items if i.conflict]
            self.assertEqual(conflicts, ["duplicate"])

    def test_invalid_name_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt")
            transforms = [Transform(TransformType.PREFIX, value="sub/")]
            plan = build_plan(paths, transforms)
            self.assertEqual(plan.items[0].conflict, "invalid")


class MetadataTests(unittest.TestCase):
    def test_date_uses_modification_time(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt")
            import os

            stamp = 1600000000
            os.utime(paths[0], (stamp, stamp))
            transforms = [Transform(TransformType.DATE, value="-", format="%Y")]
            plan = build_plan(paths, transforms)
            # 1600000000 -> 2020
            self.assertEqual(plan.items[0].new_name, "a-2020.txt")

    def test_exif_missing_keeps_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt")  # not an image -> no EXIF
            transforms = [Transform(TransformType.EXIF, format="%Y")]
            plan = build_plan(paths, transforms)
            self.assertEqual(plan.items[0].new_name, "a.txt")

    def test_audio_missing_keeps_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt")
            transforms = [Transform(TransformType.AUDIO, value="_", field="title")]
            plan = build_plan(paths, transforms)
            self.assertEqual(plan.items[0].new_name, "a.txt")


class GroupedNumberingTests(unittest.TestCase):
    def test_paired_files_share_number(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "photo.jpg", "photo.raw", "other.jpg")
            transforms = [
                Transform(
                    TransformType.NUMBERING,
                    start=1,
                    digits=2,
                    value="-",
                    grouped=True,
                )
            ]
            plan = build_plan(paths, transforms)
            by_name = {i.original_name: i.new_name for i in plan.items}
            # photo.jpg and photo.raw share base -> both get "01"; other -> "02".
            self.assertEqual(by_name["photo.jpg"], "photo-01.jpg")
            self.assertEqual(by_name["photo.raw"], "photo-01.raw")
            self.assertEqual(by_name["other.jpg"], "other-02.jpg")


class PresetTests(unittest.TestCase):
    def test_transform_roundtrip(self):
        t = Transform(TransformType.CASE, value="upper", search="extension")
        t2 = Transform.from_dict(t.to_dict())
        self.assertEqual(t2.type, TransformType.CASE)
        self.assertEqual(t2.value, "upper")
        self.assertEqual(t2.search, "extension")

    def test_preset_roundtrip(self):
        preset = BulkRenamePreset(
            name="strip",
            transforms=[
                Transform(TransformType.SEARCH_REPLACE, search="_", replace=" "),
                Transform(TransformType.CASE, value="title"),
            ],
        )
        restored = BulkRenamePreset.from_dict(preset.to_dict())
        self.assertEqual(restored.name, "strip")
        self.assertEqual(len(restored.transforms), 2)
        self.assertEqual(restored.transforms[0].search, "_")

    def test_apply_names_list_modes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt")
            names = ["x.md", "y.md"]
            self.assertEqual(
                apply_names_list(names, "replace", paths)[paths[0]], "x.md"
            )
            self.assertEqual(
                apply_names_list(["pre_", "pre_"], "prefix", paths)[paths[1]], "pre_b.txt"
            )
            self.assertEqual(
                apply_names_list(["_suf", "_suf"], "suffix", paths)[paths[0]], "a_suf.txt"
            )


class SanitizeTests(unittest.TestCase):
    def test_sanitize_removes_invalid_chars(self):
        self.assertEqual(sanitize_filename("a/b:c.txt"), "a_b_c.txt")
        self.assertEqual(sanitize_filename('x*y?"z.png'), "x_y__z.png")

    def test_sanitize_trims_trailing_dots_spaces(self):
        self.assertEqual(sanitize_filename("name  "), "name")
        self.assertEqual(sanitize_filename("name..."), "name")

    def test_sanitize_neutralizes_reserved_names(self):
        self.assertEqual(sanitize_filename("CON.txt"), "CON_.txt")
        self.assertEqual(sanitize_filename("con.txt"), "con_.txt")

    def test_sanitize_transform_in_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a:b.txt")
            transforms = [Transform(TransformType.SANITIZE)]
            plan = build_plan(paths, transforms)
            self.assertEqual(plan.items[0].new_name, "a_b.txt")

    def test_last_batch_roundtrip(self):
        transforms = [
            Transform(TransformType.SEARCH_REPLACE, search="_", replace=" "),
            Transform(TransformType.SANITIZE),
            Transform(TransformType.NUMBERING, start=1, digits=2, grouped=True),
        ]
        restored = [Transform.from_dict(t.to_dict()) for t in transforms]
        self.assertEqual([t.type for t in restored], [t.type for t in transforms])
        self.assertTrue(restored[-1].grouped)
        self.assertEqual(restored[0].search, "_")


class ApplyPlanTests(unittest.TestCase):
    def test_apply_renames_files_and_reports_pairs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt")
            transforms = [Transform(TransformType.SEARCH_REPLACE, search=".txt", replace=".md")]
            plan = build_plan(paths, transforms)
            renamed = apply_plan(plan)
            self.assertEqual(len(renamed), 2)
            self.assertTrue((Path(tmpdir) / "a.md").exists())
            self.assertTrue((Path(tmpdir) / "b.md").exists())
            self.assertFalse((Path(tmpdir) / "a.txt").exists())

    def test_apply_skips_disabled_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt")
            transforms = [Transform(TransformType.SEARCH_REPLACE, search=".txt", replace=".md")]
            plan = build_plan(paths, transforms)
            plan.items[1].enabled = False
            renamed = apply_plan(plan)
            self.assertEqual(len(renamed), 1)
            self.assertTrue((Path(tmpdir) / "a.md").exists())
            self.assertTrue((Path(tmpdir) / "b.txt").exists())

    def test_apply_refuses_unresolved_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt")
            transforms = [Transform(TransformType.REGEX, search=".*", replace="same.txt")]
            plan = build_plan(paths, transforms)
            with self.assertRaises(ValueError):
                apply_plan(plan)


class BulkRenameDialogTests(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def test_dialog_previews_search_replace(self):
        from lfmapp.ui.bulk_rename_dialog import BulkRenameDialog

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt")
            dialog = BulkRenameDialog(paths, record_callback=None)
            dialog.search_edit.setText("txt")
            dialog.replace_edit.setText("md")
            dialog.rebuild_plan()
            self.assertEqual(dialog.table.rowCount(), 2)
            after_values = {
                dialog.table.item(r, 1).text(): dialog.table.item(r, 2).text()
                for r in range(dialog.table.rowCount())
            }
            self.assertEqual(after_values["a.txt"], "a.md")
            self.assertEqual(after_values["b.txt"], "b.md")
            dialog.deleteLater()

    def test_dialog_apply_records_composite_operation(self):
        from lfmapp.ui.bulk_rename_dialog import BulkRenameDialog

        recorded = []

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt")
            dialog = BulkRenameDialog(paths, record_callback=recorded.append)
            dialog.search_edit.setText("txt")
            dialog.replace_edit.setText("md")
            dialog.rebuild_plan()
            dialog.apply_batch()
            self.assertEqual(len(recorded), 1)
            self.assertEqual(len(recorded[0].operations), 2)
            self.assertTrue((Path(tmpdir) / "a.md").exists())
            self.assertTrue((Path(tmpdir) / "b.md").exists())
            dialog.deleteLater()

    def test_dialog_undo_last_batch(self):
        from lfmapp.ui.bulk_rename_dialog import BulkRenameDialog

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _make_files(tmpdir, "a.txt", "b.txt")
            dialog = BulkRenameDialog(paths, record_callback=None)
            dialog.search_edit.setText("txt")
            dialog.replace_edit.setText("md")
            dialog.rebuild_plan()
            dialog.apply_batch()
            self.assertTrue((Path(tmpdir) / "a.md").exists())
            dialog.undo_last_batch()
            self.assertTrue((Path(tmpdir) / "a.txt").exists())
            self.assertFalse((Path(tmpdir) / "a.md").exists())
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()