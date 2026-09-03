"""Tests for the conflict model, dialog decisions and worker integration."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton

from lfmapp.services.conflict_resolution import (
    Conflict,
    ConflictAnswer,
    ConflictResolver,
    Resolution,
    suggest_free_name,
    _validate_new_name,
)
from lfmapp.services.worker_threads import CopyWorker, MoveWorker

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


def _resolver_returning(resolution, new_name=None):
    seen = []

    def resolver(conflict):
        seen.append(conflict)
        return ConflictAnswer(resolution, new_name)

    return resolver, seen


def _run_worker(worker) -> tuple[bool, str]:
    results = []
    worker.finished.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()  # synchronous: the thread body runs inline
    return results[-1]


class ConflictModelTests(unittest.TestCase):
    def test_conflict_kind_by_source_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file = root / "a.txt"
            file.write_text("x")
            folder = root / "sub"
            folder.mkdir()
            self.assertEqual(Conflict(file, file).kind, "file")
            self.assertEqual(Conflict(folder, folder).kind, "folder")
            info = Conflict(file, file).source_info
            self.assertEqual(info["name"], "a.txt")
            self.assertEqual(info["size"], 1)
            self.assertEqual(info["location"], str(root))

    def test_suggest_free_name_uses_copy_suffix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir)
            source = parent / "report.pdf"
            source.write_text("x")
            self.assertEqual(suggest_free_name(source, parent), "report (copy).pdf")
            (parent / "report (copy).pdf").write_text("y")
            self.assertEqual(suggest_free_name(source, parent), "report (copy 2).pdf")

    def test_validate_new_name(self):
        self.assertTrue(_validate_new_name("new.txt"))
        for bad in ("", " ", "a/b", "..", ".", "trail "):
            self.assertFalse(_validate_new_name(bad))

    def test_resolver_remembers_apply_to_all_but_cancel(self):
        resolver = ConflictResolver()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            folder = root / "folder"
            folder.mkdir()
            file = root / "x.txt"
            file.write_text("x")
            conflict = Conflict(folder, folder)
            file_conflict = Conflict(file, file)
            resolver.remember(conflict, ConflictAnswer(Resolution.SKIP))
            self.assertEqual(resolver.remembered(conflict).resolution, Resolution.SKIP)
            self.assertIsNone(resolver.remembered(file_conflict))  # scope by kind
            resolver.remember(conflict, ConflictAnswer(Resolution.CANCEL))
            self.assertEqual(resolver.remembered(conflict).resolution, Resolution.SKIP)
            resolver.clear()
            self.assertIsNone(resolver.remembered(conflict))


class CopyWorkerConflictTests(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def _setup_conflict(self, tmpdir):
        root = Path(tmpdir)
        src_dir = root / "src"
        dst_dir = root / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "a.txt").write_text("new data")
        (dst_dir / "a.txt").write_text("old data")
        return src_dir / "a.txt", dst_dir

    def test_replace_overwrites(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src, dst = self._setup_conflict(tmpdir)
            resolver, seen = _resolver_returning(Resolution.REPLACE)
            worker = CopyWorker(src, dst, conflict_resolver=resolver)
            ok, _msg = _run_worker(worker)
            self.assertTrue(ok)
            self.assertEqual((dst / "a.txt").read_text(), "new data")
            self.assertEqual(len(seen), 1)

    def test_skip_keeps_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src, dst = self._setup_conflict(tmpdir)
            resolver, _seen = _resolver_returning(Resolution.SKIP)
            ok, msg = _run_worker(CopyWorker(src, dst, conflict_resolver=resolver))
            self.assertTrue(ok)
            self.assertIn("Skipped", msg)
            self.assertEqual((dst / "a.txt").read_text(), "old data")

    def test_keep_both_creates_copy_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src, dst = self._setup_conflict(tmpdir)
            resolver, _seen = _resolver_returning(Resolution.KEEP_BOTH)
            ok, _msg = _run_worker(CopyWorker(src, dst, conflict_resolver=resolver))
            self.assertTrue(ok)
            self.assertEqual((dst / "a.txt").read_text(), "old data")
            self.assertEqual((dst / "a (copy).txt").read_text(), "new data")

    def test_rename_copies_with_new_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src, dst = self._setup_conflict(tmpdir)
            resolver, _seen = _resolver_returning(Resolution.RENAME, "renamed.txt")
            ok, _msg = _run_worker(CopyWorker(src, dst, conflict_resolver=resolver))
            self.assertTrue(ok)
            self.assertEqual((dst / "renamed.txt").read_text(), "new data")
            self.assertEqual((dst / "a.txt").read_text(), "old data")

    def test_cancel_stops_operation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src, dst = self._setup_conflict(tmpdir)
            resolver, _seen = _resolver_returning(Resolution.CANCEL)
            ok, msg = _run_worker(CopyWorker(src, dst, conflict_resolver=resolver))
            self.assertFalse(ok)
            self.assertIn("canceled", msg)
            self.assertEqual((dst / "a.txt").read_text(), "old data")

    def test_no_conflict_no_question(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "b.txt"
            src.write_text("data")
            dst = root / "out"
            dst.mkdir()
            resolver, seen = _resolver_returning(Resolution.SKIP)
            ok, _msg = _run_worker(CopyWorker(src, dst, conflict_resolver=resolver))
            self.assertTrue(ok)
            self.assertEqual(seen, [])
            self.assertEqual((dst / "b.txt").read_text(), "data")

    def test_folder_merge_resolves_children_individually(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src_dir = root / "src" / "folder"
            dst_dir = root / "dst"
            src_dir.mkdir(parents=True)
            (dst_dir / "folder").mkdir(parents=True)
            (src_dir / "exists.txt").write_text("new")
            (src_dir / "only_here.txt").write_text("x")
            (dst_dir / "folder" / "exists.txt").write_text("old")

            answers = {
                "folder": ConflictAnswer(Resolution.MERGE),
                "file": ConflictAnswer(Resolution.SKIP),
            }

            def resolver(conflict):
                return answers[conflict.kind]

            ok, _msg = _run_worker(
                CopyWorker(src_dir, dst_dir, conflict_resolver=resolver)
            )
            self.assertTrue(ok)
            self.assertEqual(
                (dst_dir / "folder" / "exists.txt").read_text(), "old"
            )
            self.assertEqual(
                (dst_dir / "folder" / "only_here.txt").read_text(), "x"
            )

    def test_file_folder_type_mismatch_is_skipped_not_cleared(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "src" / "thing"
            src.mkdir(parents=True)
            (src / "inner.txt").write_text("keep-me")
            dst = root / "dst"
            dst.mkdir()
            (dst / "thing").write_text("conflicting file")
            resolver, _seen = _resolver_returning(Resolution.REPLACE)
            ok, _msg = _run_worker(CopyWorker(src, dst, conflict_resolver=resolver))
            self.assertTrue(ok)
            self.assertTrue((dst / "thing").is_file())
            self.assertTrue((src / "inner.txt").exists())


class MoveWorkerConflictTests(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def test_skip_never_deletes_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "a.txt"
            src.write_text("my data")
            dst = root / "dst"
            dst.mkdir()
            (dst / "a.txt").write_text("old")
            resolver, _seen = _resolver_returning(Resolution.SKIP)
            ok, _msg = _run_worker(MoveWorker(src, dst, conflict_resolver=resolver))
            self.assertTrue(ok)
            self.assertEqual(src.read_text(), "my data")
            self.assertEqual((dst / "a.txt").read_text(), "old")

    def test_move_tree_skip_keeps_only_skipped_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src_dir = root / "src" / "folder"
            src_dir.mkdir(parents=True)
            (src_dir / "moved.txt").write_text("moved")
            (src_dir / "kept.txt").write_text("kept")
            dst = root / "dst"
            (dst / "folder").mkdir(parents=True)
            (dst / "folder" / "kept.txt").write_text("old")

            def resolver(conflict):
                if conflict.kind == "folder":
                    return ConflictAnswer(Resolution.MERGE)
                return ConflictAnswer(Resolution.SKIP)

            ok, _msg = _run_worker(MoveWorker(src_dir, dst, conflict_resolver=resolver))
            self.assertTrue(ok)
            self.assertTrue((dst / "folder" / "moved.txt").exists())
            self.assertFalse((src_dir / "moved.txt").exists())
            self.assertEqual((src_dir / "kept.txt").read_text(), "kept")
            self.assertEqual((dst / "folder" / "kept.txt").read_text(), "old")


class ConflictDialogTests(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def _dialog(self, tmpdir, folder=False):
        from lfmapp.ui.conflict_dialog import ConflictDialog

        root = Path(tmpdir)
        if folder:
            source = root / "src" / "dir"
            existing = root / "dst" / "dir"
            source.mkdir(parents=True)
            existing.mkdir(parents=True)
        else:
            source = root / "src" / "a.txt"
            existing = root / "dst" / "a.txt"
            source.parent.mkdir(parents=True)
            existing.parent.mkdir(parents=True)
            source.write_text("new")
            existing.write_text("old")
        return ConflictDialog(Conflict(source, existing))

    def _button_texts(self, dialog):
        return [b.text() for b in dialog.findChildren(QPushButton)]

    def test_file_conflict_offers_file_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dialog = self._dialog(tmpdir)
            texts = self._button_texts(dialog)
            for expected in ("Replace", "Skip", "Keep Both", "Rename", "Cancel"):
                self.assertIn(expected, texts)
            self.assertNotIn("Merge", texts)
            self.assertIn(
                "a (copy).txt", dialog.keep_both_label.text()
            )

    def test_folder_conflict_offers_merge_without_replace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dialog = self._dialog(tmpdir, folder=True)
            texts = self._button_texts(dialog)
            self.assertIn("Merge", texts)
            self.assertNotIn("Replace", texts)

    def test_apply_to_all_scope_names_kind(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dialog = self._dialog(tmpdir)
            self.assertIn("files", dialog.apply_all_checkbox.text())
            dialog2 = self._dialog(tmpdir, folder=True)
            self.assertIn("folders", dialog2.apply_all_checkbox.text())

    def test_rename_button_uses_edited_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dialog = self._dialog(tmpdir)
            dialog.rename_edit.setText("better name.txt")
            dialog._on_rename()
            self.assertEqual(dialog.answer.resolution, Resolution.RENAME)
            self.assertEqual(dialog.answer.new_name, "better name.txt")

    def test_invalid_rename_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dialog = self._dialog(tmpdir)
            dialog.rename_edit.setText("bad/name.txt")
            dialog._on_rename()
            self.assertEqual(dialog.answer.resolution, Resolution.CANCEL)

    def test_closing_cancels_operation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dialog = self._dialog(tmpdir)
            dialog.reject()
            self.assertEqual(dialog.answer.resolution, Resolution.CANCEL)

    def test_keep_both_uses_suggested_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dialog = self._dialog(tmpdir)
            dialog._on_keep_both()
            self.assertEqual(dialog.answer.resolution, Resolution.KEEP_BOTH)
            self.assertEqual(dialog.answer.new_name, "a (copy).txt")


class MainWindowConflictIntegrationTests(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def test_paste_workers_receive_conflict_resolver(self):
        from unittest.mock import patch

        from lfmapp.core import config as config_module
        from lfmapp.ui.conflict_dialog import GuiConflictResolver

        with tempfile.TemporaryDirectory() as tmpdir:
            old_dir = config_module.CONFIG_DIR
            old_file = config_module.CONFIG_FILE
            config_module.CONFIG_DIR = Path(tmpdir)
            config_module.CONFIG_FILE = Path(tmpdir) / "config.json"
            try:
                from lfmapp.ui.main_window import MainWindow

                window = MainWindow()
                source = Path(tmpdir) / "a.txt"
                source.write_text("data")
                window._clipboard_paths = [source]
                window._clipboard_mode = "copy"
                captured = []
                with (
                    patch.object(
                        window.workspace, "current_path", return_value=Path(tmpdir)
                    ),
                    patch.object(
                        window,
                        "_register_worker",
                        side_effect=lambda worker, *a, **k: captured.append(worker),
                    ),
                ):
                    window.paste_from_clipboard()
                self.assertEqual(len(captured), 1)
                self.assertIsInstance(
                    captured[0].conflict_resolver, GuiConflictResolver
                )
                window.deleteLater()
            finally:
                config_module.CONFIG_DIR = old_dir
                config_module.CONFIG_FILE = old_file


if __name__ == "__main__":
    unittest.main()
