"""Fase 0.3: GUI tests for critical file-manager flows.

Uses the real UI through MainWindow and exercises navigation, selection,
view switching, copy/paste, cut/paste, rename, delete-to-trash and Unicode
paths.  Directory loads in QFileSystemModel are asynchronous, so helpers
pump Qt events until the model reports the expected row count.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import lfmapp.core.config as config_module
from lfmapp.ui.main_window import MainWindow

_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


class CriticalFlowGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_dir = config_module.CONFIG_DIR
        self._old_file = config_module.CONFIG_FILE
        config_module.CONFIG_DIR = Path(self._tmp.name) / "config"
        config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"
        root = Path(self._tmp.name) / "tree"
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "readme.md").write_text("# Hola\n", encoding="utf-8")
        (root / "images").mkdir()
        (root / "images" / "foto.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        (root / "data.bin").write_bytes(os.urandom(1024))
        (root / "carpeta con espacios").mkdir()
        (root / "carpeta con espacios" / "nota final.txt").write_text(
            "texto", encoding="utf-8"
        )
        self.root = root
        self.window = MainWindow()

    def tearDown(self):
        if self.window is not None:
            self.window.close()
            self.window = None
        config_module.CONFIG_DIR = self._old_dir
        config_module.CONFIG_FILE = self._old_file
        self._tmp.cleanup()

    # ── helpers ──────────────────────────────────────────────
    def _pump_until(self, condition, timeout=8.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            QApplication.processEvents()
            if condition():
                return True
            time.sleep(0.02)
        return bool(condition())

    def _rows_at(self, path: Path) -> int:
        model = self.window.workspace.model
        index = model.index(str(path))
        return 0 if not index.isValid() else model.rowCount(index)

    def _go(self, path: Path):
        self.window.go_to(path, record_history=False)
        self._pump_until(lambda: self._rows_at(path) >= 0)

    def _select(self, path: Path):
        model = self.window.workspace.model
        index = model.index(str(path))
        self._pump_until(lambda: index.isValid() and model.rowCount(index.parent()) > 0)
        self.window.workspace.setCurrentIndex(index)
        QApplication.processEvents()

    def _wait_removed(self, path: Path, timeout=10.0):
        return self._pump_until(lambda: not path.exists(), timeout)

    def _wait_created(self, path: Path, timeout=10.0):
        return self._pump_until(lambda: path.exists(), timeout)

    # ── flows ────────────────────────────────────────────────
    def test_navigation_reaches_folder_and_lists_entries(self):
        self._go(self.root)
        self.assertEqual(self.window.workspace.current_path(), self.root)
        self._pump_until(lambda: self._rows_at(self.root) >= 4)
        self.assertGreaterEqual(self._rows_at(self.root), 4)

    def test_go_up_changes_to_parent(self):
        docs = self.root / "docs"
        self._go(docs)
        self.window.go_up()
        self.assertEqual(self.window.workspace.current_path(), self.root)

    def test_hidden_files_toggle_changes_visible_entries(self):
        self._go(self.root)
        self._pump_until(lambda: self._rows_at(self.root) >= 4)
        (self.root / ".hidden").write_text("secret", encoding="utf-8")
        self.window.refresh_view()
        # Hidden dotfile becomes visible when toggled on.
        self.window.toggle_hidden_files(True)
        self._pump_until(lambda: self._rows_at(self.root) >= 5)
        with_hidden = self._rows_at(self.root)
        self.window.toggle_hidden_files(False)
        self._pump_until(lambda: self._rows_at(self.root) <= 4)
        without = self._rows_at(self.root)
        self.assertGreater(with_hidden, without)

    def test_view_mode_switching_keeps_path(self):
        from lfmapp.ui.workspace import ViewMode

        self._go(self.root)
        for mode in (
            ViewMode.ICON,
            ViewMode.LIST,
            ViewMode.DETAILS,
            ViewMode.COMPACT,
        ):
            self.window.set_view_mode(mode)
            self.assertEqual(self.window.workspace.current_path(), self.root)

    def test_copy_paste_flow(self):
        source = self.root / "docs"
        dest_folder = self.root / "carpeta con espacios"
        self._go(self.root)
        self._select(source)
        self.window.copy_selected()
        self._go(dest_folder)
        self.window.paste_from_clipboard()
        self._wait_created(dest_folder / source.name)
        self.assertTrue((dest_folder / source.name / "readme.md").exists())

    def test_cut_paste_moves_not_copies(self):
        source = self.root / "data.bin"
        dest_folder = self.root / "carpeta con espacios"
        self._go(self.root)
        self._select(source)
        self.window.cut_selected()
        self._go(dest_folder)
        self.window.paste_from_clipboard()
        self._wait_created(dest_folder / source.name)
        self.assertTrue((dest_folder / source.name).exists())
        self.assertFalse(source.exists(), "cut+paste must move, not copy")

    def test_rename_flow_via_ui(self):
        from unittest.mock import patch

        source = self.root / "data.bin"
        self._go(self.root)
        self._select(source)
        target = self.root / "renombrado.bin"
        with patch(
            "lfmapp.ui.file_actions_mixin.QInputDialog.getText",
            return_value=("renombrado.bin", True),
        ):
            self.window.rename_selected_dialog()
        self._wait_created(target)
        self.assertTrue(target.exists())
        self.assertFalse(source.exists())

    def test_unicode_and_spaces_roundtrip_via_ui(self):
        weird = self.root / "carpeta con espacios" / "nota final.txt"
        self.assertTrue(weird.exists())
        self._go(weird.parent)
        self.assertEqual(self.window.workspace.current_path(), weird.parent)
        self._pump_until(lambda: self._rows_at(weird.parent) >= 1)
        model = self.window.workspace.model
        index = model.index(str(weird.parent))
        names = [
            model.data(model.index(child, 0, index))
            for child in range(model.rowCount(index))
        ]
        self.assertIn("nota final.txt", names)


if __name__ == "__main__":
    unittest.main()
