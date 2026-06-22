import tempfile
import unittest
from pathlib import Path

import lfm.services.operation_history as operation_history
import lfm.services.trash_service as trash_service
from lfm.services.operation_history import (
    CompositeOperation,
    CopyOperation,
    CreateOperation,
    MoveOperation,
    OperationHistory,
    RenameOperation,
    TrashOperation,
)


class OperationHistoryTests(unittest.TestCase):
    def test_rename_operation_undo_and_redo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original = Path(tmpdir) / "old.txt"
            renamed = Path(tmpdir) / "new.txt"
            original.write_text("data", encoding="utf-8")

            operation = RenameOperation(original, renamed)
            operation.redo()
            self.assertFalse(original.exists())
            self.assertEqual(renamed.read_text(encoding="utf-8"), "data")

            operation.undo()
            self.assertEqual(original.read_text(encoding="utf-8"), "data")
            self.assertFalse(renamed.exists())

    def test_history_moves_operations_between_undo_and_redo_stacks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original = Path(tmpdir) / "old.txt"
            renamed = Path(tmpdir) / "new.txt"
            original.write_text("data", encoding="utf-8")

            history = OperationHistory()
            operation = RenameOperation(original, renamed)
            operation.redo()
            history.push(operation)

            self.assertTrue(history.can_undo())
            self.assertFalse(history.can_redo())
            self.assertEqual(history.next_undo_operation_label(), "Rename old.txt to new.txt")
            self.assertIsNone(history.next_redo_operation_label())

            undone = history.undo()
            self.assertEqual(undone, operation)
            self.assertTrue(original.exists())
            self.assertFalse(renamed.exists())
            self.assertFalse(history.can_undo())
            self.assertTrue(history.can_redo())
            self.assertIsNone(history.next_undo_operation_label())
            self.assertEqual(history.next_redo_operation_label(), "Rename old.txt to new.txt")

            redone = history.redo()
            self.assertEqual(redone, operation)
            self.assertFalse(original.exists())
            self.assertTrue(renamed.exists())
            self.assertTrue(history.can_undo())
            self.assertFalse(history.can_redo())
            self.assertEqual(history.next_undo_operation_label(), "Rename old.txt to new.txt")
            self.assertIsNone(history.next_redo_operation_label())

    def test_create_file_operation_undo_and_redo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "created.txt"
            path.touch()

            operation = CreateOperation(path, "file")
            operation.undo()
            self.assertFalse(path.exists())

            operation.redo()
            self.assertTrue(path.is_file())

    def test_create_file_operation_refuses_to_undo_modified_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "created.txt"
            path.write_text("user data", encoding="utf-8")

            operation = CreateOperation(path, "file")
            with self.assertRaises(OSError):
                operation.undo()
            self.assertEqual(path.read_text(encoding="utf-8"), "user data")

    def test_create_folder_operation_refuses_to_undo_non_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "created"
            path.mkdir()
            (path / "nested.txt").write_text("data", encoding="utf-8")

            operation = CreateOperation(path, "folder")
            with self.assertRaises(OSError):
                operation.undo()
            self.assertTrue(path.exists())

    def test_move_operation_undo_and_redo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original = Path(tmpdir) / "source.txt"
            destination_dir = Path(tmpdir) / "destination"
            destination_dir.mkdir()
            moved = destination_dir / "source.txt"
            original.write_text("data", encoding="utf-8")

            operation = MoveOperation(original, moved)
            operation.redo()
            self.assertFalse(original.exists())
            self.assertEqual(moved.read_text(encoding="utf-8"), "data")

            operation.undo()
            self.assertEqual(original.read_text(encoding="utf-8"), "data")
            self.assertFalse(moved.exists())

    def test_move_operation_refuses_to_overwrite_on_undo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original = Path(tmpdir) / "source.txt"
            destination_dir = Path(tmpdir) / "destination"
            destination_dir.mkdir()
            moved = destination_dir / "source.txt"
            moved.write_text("moved", encoding="utf-8")
            original.write_text("new file", encoding="utf-8")

            operation = MoveOperation(original, moved)
            with self.assertRaises(FileExistsError):
                operation.undo()
            self.assertEqual(original.read_text(encoding="utf-8"), "new file")
            self.assertEqual(moved.read_text(encoding="utf-8"), "moved")

    def test_copy_operation_undo_and_redo_regular_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.txt"
            copied = Path(tmpdir) / "copy.txt"
            source.write_text("data", encoding="utf-8")
            copied.write_text("data", encoding="utf-8")

            operation = CopyOperation.from_completed_copy(source, copied)
            operation.undo()
            self.assertFalse(copied.exists())

            operation.redo()
            self.assertEqual(copied.read_text(encoding="utf-8"), "data")

    def test_copy_operation_refuses_to_undo_modified_copy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.txt"
            copied = Path(tmpdir) / "copy.txt"
            source.write_text("data", encoding="utf-8")
            copied.write_text("data", encoding="utf-8")

            operation = CopyOperation.from_completed_copy(source, copied)
            copied.write_text("changed", encoding="utf-8")

            with self.assertRaises(OSError):
                operation.undo()
            self.assertEqual(copied.read_text(encoding="utf-8"), "changed")

    def test_copy_operation_undo_and_redo_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source"
            copied = Path(tmpdir) / "copy"
            source.mkdir()
            copied.mkdir()
            (source / "nested").mkdir()
            (source / "nested" / "file.txt").write_text("data", encoding="utf-8")
            (copied / "nested").mkdir()
            (copied / "nested" / "file.txt").write_text("data", encoding="utf-8")

            operation = CopyOperation.from_completed_copy(source, copied)
            operation.undo()
            self.assertFalse(copied.exists())

            operation.redo()
            self.assertEqual((copied / "nested" / "file.txt").read_text(encoding="utf-8"), "data")

    def test_copy_operation_refuses_to_undo_modified_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source"
            copied = Path(tmpdir) / "copy"
            source.mkdir()
            copied.mkdir()
            (copied / "file.txt").write_text("data", encoding="utf-8")

            operation = CopyOperation.from_completed_copy(source, copied)
            (copied / "extra.txt").write_text("changed", encoding="utf-8")

            with self.assertRaises(OSError):
                operation.undo()
            self.assertTrue((copied / "extra.txt").exists())

    def test_trash_operation_undo_restores_original_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original = Path(tmpdir) / "document.txt"
            trash_file = Path(tmpdir) / "Trash" / "files" / "document.txt"
            trash_info = Path(tmpdir) / "Trash" / "info" / "document.txt.trashinfo"
            trash_file.parent.mkdir(parents=True)
            trash_info.parent.mkdir(parents=True)
            trash_file.write_text("data", encoding="utf-8")
            trash_info.write_text("[Trash Info]\n", encoding="utf-8")

            operation = TrashOperation(original, trash_file, trash_info)
            operation.undo()

            self.assertEqual(original.read_text(encoding="utf-8"), "data")
            self.assertFalse(trash_file.exists())
            self.assertFalse(trash_info.exists())

    def test_trash_operation_refuses_to_overwrite_on_undo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original = Path(tmpdir) / "document.txt"
            trash_file = Path(tmpdir) / "Trash" / "files" / "document.txt"
            trash_info = Path(tmpdir) / "Trash" / "info" / "document.txt.trashinfo"
            trash_file.parent.mkdir(parents=True)
            trash_info.parent.mkdir(parents=True)
            original.write_text("new data", encoding="utf-8")
            trash_file.write_text("trashed data", encoding="utf-8")
            trash_info.write_text("[Trash Info]\n", encoding="utf-8")

            operation = TrashOperation(original, trash_file, trash_info)
            with self.assertRaises(FileExistsError):
                operation.undo()
            self.assertEqual(original.read_text(encoding="utf-8"), "new data")
            self.assertEqual(trash_file.read_text(encoding="utf-8"), "trashed data")

    def test_trash_operation_redo_updates_trash_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_files_dir = trash_service.TRASH_FILES_DIR
            old_info_dir = trash_service.TRASH_INFO_DIR
            old_history_files_dir = operation_history.TRASH_FILES_DIR
            old_history_info_dir = operation_history.TRASH_INFO_DIR
            try:
                files_dir = Path(tmpdir) / "Trash" / "files"
                info_dir = Path(tmpdir) / "Trash" / "info"
                trash_service.TRASH_FILES_DIR = files_dir
                trash_service.TRASH_INFO_DIR = info_dir
                operation_history.TRASH_FILES_DIR = files_dir
                operation_history.TRASH_INFO_DIR = info_dir

                original = Path(tmpdir) / "document.txt"
                original.write_text("data", encoding="utf-8")
                operation = TrashOperation(
                    original,
                    files_dir / "old-document.txt",
                    info_dir / "old-document.txt.trashinfo",
                )

                operation.redo()

                self.assertFalse(original.exists())
                self.assertTrue(operation.trashed_path.exists())
                self.assertTrue(operation.trashinfo_path.exists())
                self.assertEqual(operation.trashed_path.read_text(encoding="utf-8"), "data")
            finally:
                trash_service.TRASH_FILES_DIR = old_files_dir
                trash_service.TRASH_INFO_DIR = old_info_dir
                operation_history.TRASH_FILES_DIR = old_history_files_dir
                operation_history.TRASH_INFO_DIR = old_history_info_dir

    def test_composite_operation_undoes_in_reverse_order_and_redoes_in_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "first.txt"
            second = Path(tmpdir) / "second.txt"
            first.touch()
            second.touch()

            operation = CompositeOperation.from_operations(
                "Create 2 files",
                [
                    CreateOperation(first, "file"),
                    CreateOperation(second, "file"),
                ],
            )
            operation.undo()
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())

            operation.redo()
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_composite_operation_requires_operations(self):
        with self.assertRaises(ValueError):
            CompositeOperation.from_operations("Empty", [])


if __name__ == "__main__":
    unittest.main()
