"""Tests for advanced selection + batch action bar (backlog P2, Phase 6.1).

Covers:
- Pure SelectionCriteria / SelectionController.select_by (glob, extension,
  type, size, inactive-criteria-returns-empty).
- AppState identity-based selection change detection.
- FileSystemModel checkbox API (set/check/toggle/checked_count).
- GUI: batch action bar visibility + summary, invert T16 fix, Space-to-check,
  select_by_dialog end-to-end.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import lfmapp.core.config as config_module
from lfmapp.controllers import (
    AppState,
    SelectionController,
    SelectionCriteria,
)


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return app


def _write(root: Path, name: str, content: str = "x") -> Path:
    p = root / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Pure criteria + select_by
# ---------------------------------------------------------------------------

class SelectByTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.a = _write(self.root, "a.jpg", "data1")
        self.b = _write(self.root, "notes.txt", "hello world")
        self.c = _write(self.root, "big.png", "Z" * 5000)
        self.d = self.root / "subdir"
        self.d.mkdir()
        self.all = [self.a, self.b, self.c, self.d]

    def test_glob(self):
        got = SelectionController.select_by(self.all, SelectionCriteria(name_glob="*.jpg"))
        self.assertEqual(got, [self.a])

    def test_glob_case_insensitive(self):
        up = _write(self.root, "UP.JPG", "z")
        got = SelectionController.select_by(self.all + [up], SelectionCriteria(name_glob="*.jpg"))
        self.assertIn(up, got)
        self.assertIn(self.a, got)

    def test_glob_case_sensitive(self):
        up = _write(self.root, "UP.JPG", "z")
        got = SelectionController.select_by(
            self.all + [up],
            SelectionCriteria(name_glob="*.jpg", case_sensitive=True),
        )
        self.assertIn(self.a, got)
        self.assertNotIn(up, got)

    def test_extensions(self):
        got = SelectionController.select_by(
            self.all, SelectionCriteria(extensions=(".jpg", ".png"))
        )
        self.assertEqual(set(got), {self.a, self.c})

    def test_type_image(self):
        got = SelectionController.select_by(self.all, SelectionCriteria(file_type="image"))
        self.assertEqual(set(got), {self.a, self.c})

    def test_type_folder(self):
        got = SelectionController.select_by(self.all, SelectionCriteria(file_type="folder"))
        self.assertEqual(got, [self.d])

    def test_min_size(self):
        got = SelectionController.select_by(self.all, SelectionCriteria(min_size=1000))
        self.assertEqual(got, [self.c])

    def test_inactive_returns_empty(self):
        # Empty criteria deliberately selects nothing (caller decides).
        got = SelectionController.select_by(self.all, SelectionCriteria())
        self.assertEqual(got, [])

    def test_combined(self):
        got = SelectionController.select_by(
            self.all, SelectionCriteria(name_glob="*.png", file_type="image")
        )
        self.assertEqual(got, [self.c])


# ---------------------------------------------------------------------------
# AppState identity change detection
# ---------------------------------------------------------------------------

class AppStateSelectionIdentityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.f1 = _write(self.root, "f1.txt", "1")
        self.f2 = _write(self.root, "f2.txt", "2")
        self.state = AppState()

    def test_notify_on_identity_change_same_count(self):
        calls = []
        self.state.subscribe("selection", lambda key: calls.append(key))
        self.state.set_selection_paths([self.f1])
        # Same count (1) but different identity -> must notify.
        self.state.set_selection_paths([self.f2])
        self.assertEqual(len(calls), 2)

    def test_no_notify_on_identical(self):
        calls = []
        self.state.subscribe("selection", lambda key: calls.append(key))
        self.state.set_selection_paths([self.f1])
        self.state.set_selection_paths([self.f1])
        self.assertEqual(len(calls), 1)


# ---------------------------------------------------------------------------
# Model checkbox API
# ---------------------------------------------------------------------------

class ModelCheckboxApiTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        from lfmapp.models import FileSystemModel
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.p1 = _write(self.root, "one.txt")
        self.p2 = _write(self.root, "two.txt")
        self.model = FileSystemModel(root_path=self.root)

    def test_set_and_count(self):
        self.model.set_checked_paths([self.p1, self.p2])
        self.assertEqual(self.model.checked_count(), 2)

    def test_toggle(self):
        self.model.toggle_checked(self.p1)
        self.assertEqual(self.model.checked_paths(), [self.p1])
        self.model.toggle_checked(self.p1)
        self.assertEqual(self.model.checked_paths(), [])

    def test_check_union(self):
        self.model.set_checked_paths([self.p1])
        self.model.check_paths([self.p2])
        self.assertEqual(self.model.checked_count(), 2)

    def test_set_replaces(self):
        self.model.set_checked_paths([self.p1])
        self.model.set_checked_paths([self.p2])
        self.assertEqual(self.model.checked_paths(), [self.p2])


# ---------------------------------------------------------------------------
# GUI: batch action bar + invert + space + select-by
# ---------------------------------------------------------------------------

class SelectionBarGuiTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        self._tmp = tempfile.mkdtemp()
        config_module.CONFIG_DIR = Path(self._tmp)
        config_module.CONFIG_FILE = Path(self._tmp) / "config.json"
        from lfmapp.core.config import Config
        self.config = Config()
        self.config.data["first_run_done"] = True
        self.root = Path(self._tmp) / "files"
        self.root.mkdir()
        self.a = _write(self.root, "a.jpg", "111")
        self.b = _write(self.root, "b.txt", "22222")
        self.c = _write(self.root, "c.jpg", "33")
        from lfmapp.ui.main_window import MainWindow
        self.window = MainWindow(self.config)
        self.window.workspace.set_root_path(self.root)
        view = self.window.workspace.details_view
        model = view.model()
        deadline = time.monotonic() + 8
        while model.rowCount(view.rootIndex()) < 3 and time.monotonic() < deadline:
            QApplication.processEvents()

    def tearDown(self):
        self.window.close()
        QApplication.processEvents()
        config_module.CONFIG_DIR = Path(os.path.expanduser("~/.local/share/linux-file-manager"))
        config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"

    def _select_by_name(self, names):
        view = self.window.workspace.details_view
        model = view.model()
        sm = self.window.workspace.selectionModel()
        sm.clearSelection()
        for r in range(model.rowCount(view.rootIndex())):
            idx = model.index(r, 0, view.rootIndex())
            if Path(model.filePath(idx)).name in names:
                sm.select(idx, sm.SelectionFlag.Select | sm.SelectionFlag.Rows)
        QApplication.processEvents()

    def _index_for(self, name):
        view = self.window.workspace.details_view
        model = view.model()
        for r in range(model.rowCount(view.rootIndex())):
            idx = model.index(r, 0, view.rootIndex())
            if Path(model.filePath(idx)).name == name:
                return idx
        return None

    def test_bar_hidden_when_no_selection(self):
        self.assertTrue(self.window.selection_bar.isHidden())

    def test_bar_visible_on_selection(self):
        self._select_by_name({"a.jpg", "c.jpg"})
        self.window.on_selection_changed()
        self.assertFalse(self.window.selection_bar.isHidden())
        self.assertIn("2 file", self.window.selection_bar.summary_label.text())

    def test_bar_reacts_to_select_by(self):
        from lfmapp.controllers import SelectionCriteria
        matches = SelectionController.select_by([self.a, self.b, self.c], SelectionCriteria(name_glob="*.jpg"))
        view = self.window.workspace.details_view
        sm = self.window.workspace.selectionModel()
        sm.clearSelection()
        for path in matches:
            idx = self._index_for(path.name)
            if idx:
                sm.select(idx, sm.SelectionFlag.Select | sm.SelectionFlag.Rows)
        QApplication.processEvents()
        self.window.on_selection_changed()
        self.assertFalse(self.window.selection_bar.isHidden())

    def test_invert_uses_active_view_root(self):
        self._select_by_name({"a.jpg"})
        self.window.invert_selection()
        QApplication.processEvents()
        names = {p.name for p in self.window.workspace.selected_paths()}
        self.assertEqual(names, {"b.txt", "c.jpg"})

    def test_invert_syncs_checks_in_checkbox_mode(self):
        # T16: with checkboxes on, invert must rewrite checks, not leave stale.
        self.window.workspace.model.show_selection_checkboxes = True
        self.window.workspace.model.set_checked_paths([self.a])
        self.window.invert_selection()
        QApplication.processEvents()
        checked = {p.name for p in self.window.workspace.model.checked_paths()}
        self.assertEqual(checked, {"b.txt", "c.jpg"})

    def test_space_toggles_check(self):
        self.window.workspace.model.show_selection_checkboxes = True
        idx = self._index_for("b.txt")
        view = self.window.workspace.details_view
        view.setCurrentIndex(idx)
        QApplication.processEvents()
        handled = self.window.toggle_checked_for_current()
        self.assertTrue(handled)
        self.assertEqual([p.name for p in self.window.workspace.model.checked_paths()], ["b.txt"])
        self.window.toggle_checked_for_current()
        self.assertEqual(self.window.workspace.model.checked_count(), 0)

    def test_space_noop_when_checkboxes_off(self):
        self.window.workspace.model.show_selection_checkboxes = False
        idx = self._index_for("a.jpg")
        self.window.workspace.details_view.setCurrentIndex(idx)
        QApplication.processEvents()
        self.assertFalse(self.window.toggle_checked_for_current())


class SelectByDialogTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()

    def test_parse_extensions(self):
        from lfmapp.ui.select_by_dialog import SelectByDialog
        dlg = SelectByDialog()
        dlg._ext_edit.setText("jpg, .png, gif")
        self.assertEqual(dlg._parse_extensions(), (".jpg", ".png", ".gif"))

    def test_criteria_reflects_type_combo(self):
        from lfmapp.ui.select_by_dialog import SelectByDialog
        dlg = SelectByDialog()
        dlg._type_combo.setCurrentIndex(3)  # Images
        self.assertEqual(dlg.criteria().file_type, "image")

    def test_criteria_size_scaling(self):
        from lfmapp.ui.select_by_dialog import SelectByDialog
        dlg = SelectByDialog()
        dlg._use_size_cb.setChecked(True)
        dlg._min_size.setValue(10)  # KB
        crit = dlg.criteria()
        self.assertEqual(crit.min_size, 10 * 1024)


if __name__ == "__main__":
    unittest.main()
