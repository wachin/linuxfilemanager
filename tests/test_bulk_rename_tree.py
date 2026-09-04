"""Tests for the recursive/template bulk rename engine and dialog."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from lfmapp.services.bulk_rename_tree import (
    TreePlan,
    apply_tree_plan,
    build_tree_plan,
    collect_tree,
    render_template,
)

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


class RenderTemplateTests(unittest.TestCase):
    def _file(self, tmpdir, name="a.txt"):
        p = Path(tmpdir) / name
        p.write_text("x")
        return p

    def test_name_token(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(render_template("{name}", self._file(tmpdir), 0, is_folder=False), "a.txt")

    def test_number_token_no_pad(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(render_template("{n}_{name}", self._file(tmpdir), 3, is_folder=False), "3_a.txt")

    def test_number_token_padded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(render_template("{n:03}", self._file(tmpdir), 7, is_folder=False), "007")

    def test_parent_and_ext_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = self._file(tmpdir, "a.txt")
            self.assertEqual(render_template("{parent}-{ext}", p, 0, is_folder=False), f"{Path(tmpdir).name}-.txt")

    def test_subfolder_generation_preserves_slash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = self._file(tmpdir, "a.txt")
            self.assertEqual(render_template("sub/{name}", p, 0, is_folder=False), "sub/a.txt")

    def test_invalid_chars_sanitized_per_component(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = self._file(tmpdir, "a.txt")
            self.assertEqual(render_template("bad*n/{name}", p, 0, is_folder=False), "bad_n/a.txt")


class CollectTreeTests(unittest.TestCase):
    def test_collect_files_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("x")
            sub = root / "sub"
            sub.mkdir()
            (sub / "b.txt").write_text("y")
            files = collect_tree(root, include_folders=False)
            self.assertNotIn(sub, files)
            self.assertEqual(len(files), 2)

    def test_collect_includes_folders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sub = root / "sub"
            sub.mkdir()
            (sub / "b.txt").write_text("y")
            items = collect_tree(root, include_folders=True)
            self.assertIn(sub, items)


class TreePlanTests(unittest.TestCase):
    def test_plan_renames_flat(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("x")
            (root / "b.txt").write_text("y")
            plan = build_tree_plan(root, "doc_{n:02}{ext}")
            by_orig = {i.original: i.target for i in plan.items}
            names = {v.name for v in by_orig.values()}
            self.assertIn("doc_01.txt", names)
            self.assertIn("doc_02.txt", names)
            # no conflicts: targets differ from originals and neither exists
            self.assertEqual(len(plan.conflicts), 0)

    def test_plan_detects_existing_target_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("x")
            (root / "doc_01.txt").write_text("existing")
            plan = build_tree_plan(root, "doc_{n:02}.txt")
            # First file "a.txt" maps to doc_01.txt which already exists.
            self.assertTrue(any(str(c.target).endswith("doc_01.txt") for c in plan.conflicts))

    def test_plan_builds_subfolders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("x")
            plan = build_tree_plan(root, "out/{name}")
            self.assertEqual(plan.items[0].target, root / "out" / "a.txt")
            self.assertTrue(plan.items[0].moved_to_subfolder)


class ApplyTreePlanTests(unittest.TestCase):
    def test_apply_renames_and_creates_subfolders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("x")
            (root / "b.txt").write_text("y")
            plan = build_tree_plan(root, "organized/{name}")
            renamed = apply_tree_plan(plan)
            self.assertEqual(len(renamed), 2)
            self.assertTrue((root / "organized" / "a.txt").exists())
            self.assertTrue((root / "organized" / "b.txt").exists())
            self.assertFalse((root / "a.txt").exists())

    def test_apply_refuses_existing_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("x")
            (root / "doc_01.txt").write_text("existing")
            plan = build_tree_plan(root, "doc_{n:02}.txt")
            with self.assertRaises(ValueError):
                apply_tree_plan(plan)


class BulkRenameTreeDialogTests(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def test_dialog_previews_and_applies(self):
        from lfmapp.ui.bulk_rename_tree_dialog import BulkRenameTreeDialog

        recorded = []
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("x")
            (root / "b.txt").write_text("y")
            dialog = BulkRenameTreeDialog(root, record_callback=recorded.append)
            dialog.template_edit.setText("{n:02}_{name}")
            dialog.rebuild_plan()
            self.assertEqual(dialog.table.rowCount(), 2)
            dialog.apply_batch()
            self.assertEqual(len(recorded), 1)
            self.assertEqual(len(recorded[0].operations), 2)
            self.assertTrue(sorted(p.name for p in root.iterdir()) == ["01_a.txt", "02_b.txt"])
            dialog.deleteLater()

    def test_dialog_undo_batch(self):
        from lfmapp.ui.bulk_rename_tree_dialog import BulkRenameTreeDialog

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("x")
            dialog = BulkRenameTreeDialog(root, record_callback=None)
            dialog.template_edit.setText("renamed_{name}")
            dialog.rebuild_plan()
            dialog.apply_batch()
            self.assertTrue((root / "renamed_a.txt").exists())
            dialog.undo_last_batch()
            self.assertTrue((root / "a.txt").exists())
            self.assertFalse((root / "renamed_a.txt").exists())
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()