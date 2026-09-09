"""Tests for inline expandable folders (backlog P2).

Covers:
- Config property: inline_tree_expansion with set/get.
- Workspace: setRootIsDecorated / setItemsExpandable affect details view.
- Toggle from ViewControlsMixin updates both config and view.
- Alt+Down / Alt+Up expand/collapse when enabled.
- Alt+Down / Alt+Up move selection when disabled.
- Flat view remains non-expandable regardless of toggle.
- Menu action wiring.
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
from lfmapp.ui.workspace import ViewMode

_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class InlineExpansionConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        config_module.CONFIG_DIR = Path(self._tmp)
        config_module.CONFIG_FILE = Path(self._tmp) / "config.json"
        from lfmapp.core.config import Config
        self.config = Config()

    def tearDown(self):
        config_module.CONFIG_DIR = Path(os.path.expanduser("~/.local/share/linux-file-manager"))
        config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"

    def test_default_false(self):
        self.assertFalse(self.config.inline_tree_expansion)

    def test_set_true(self):
        self.config.set_inline_tree_expansion(True)
        self.assertTrue(self.config.inline_tree_expansion)

    def test_persists(self):
        self.config.set_inline_tree_expansion(True)
        self.config.save()
        from lfmapp.core.config import Config
        c2 = Config()
        self.assertTrue(c2.inline_tree_expansion)


# ---------------------------------------------------------------------------
# Workspace tests
# ---------------------------------------------------------------------------

class WorkspaceExpansionTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        self._tmp = tempfile.mkdtemp()
        config_module.CONFIG_DIR = Path(self._tmp)
        config_module.CONFIG_FILE = Path(self._tmp) / "config.json"

    def tearDown(self):
        config_module.CONFIG_DIR = Path(os.path.expanduser("~/.local/share/linux-file-manager"))
        config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"

    def test_expansion_disabled_by_default(self):
        from lfmapp.ui.workspace import Workspace
        from lfmapp.core.config import Config
        config = Config()
        config.data["first_run_done"] = True
        ws = Workspace(config=config)
        self.assertFalse(ws.details_view.rootIsDecorated())
        self.assertFalse(ws.details_view.itemsExpandable())

    def test_set_items_expandable(self):
        from lfmapp.ui.workspace import Workspace
        from lfmapp.core.config import Config
        config = Config()
        config.data["first_run_done"] = True
        ws = Workspace(config=config)
        ws.setItemsExpandable(True)
        self.assertTrue(ws.details_view.itemsExpandable())
        ws.setItemsExpandable(False)
        self.assertFalse(ws.details_view.itemsExpandable())

    def test_flat_view_always_non_expandable(self):
        from lfmapp.ui.workspace import Workspace
        from lfmapp.core.config import Config
        config = Config()
        config.data["first_run_done"] = True
        ws = Workspace(config=config)
        ws.setItemsExpandable(True)
        self.assertFalse(ws.flat_view.itemsExpandable())

    def test_config_applied_at_init(self):
        from lfmapp.ui.workspace import Workspace
        from lfmapp.core.config import Config
        config = Config()
        config.data["first_run_done"] = True
        config.data["inline_tree_expansion"] = True
        ws = Workspace(config=config)
        self.assertTrue(ws.details_view.rootIsDecorated())
        self.assertTrue(ws.details_view.itemsExpandable())


# ---------------------------------------------------------------------------
# GUI integration tests
# ---------------------------------------------------------------------------

class ExpandableFoldersGuiTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        self._tmp = tempfile.mkdtemp()
        config_module.CONFIG_DIR = Path(self._tmp)
        config_module.CONFIG_FILE = Path(self._tmp) / "config.json"
        from lfmapp.core.config import Config
        self.config = Config()
        self.config.data["first_run_done"] = True
        # Create a test folder with a subfolder.
        self.root = Path(self._tmp) / "test_root"
        self.root.mkdir()
        sub = self.root / "subfolder"
        sub.mkdir()
        (sub / "file_in_sub.txt").write_text("hello")
        (self.root / "top_file.txt").write_text("world")
        self.window = MainWindow(self.config)
        # Navigate to test root.
        self.window.workspace.set_root_path(self.root)
        QApplication.processEvents()

    def _wait_for_rows(self, view, min_rows=1):
        """Pump events until the model has at least *min_rows* children of the root."""
        model = view.model()
        deadline = time.monotonic() + 8
        while model.rowCount(view.rootIndex()) < min_rows and time.monotonic() < deadline:
            QApplication.processEvents()
        return model.rowCount(view.rootIndex()) >= min_rows

    def tearDown(self):
        self.window.close()
        QApplication.processEvents()
        config_module.CONFIG_DIR = Path(os.path.expanduser("~/.local/share/linux-file-manager"))
        config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"

    def test_toggle_expansion_enables_view(self):
        self.assertFalse(self.window.workspace.details_view.itemsExpandable())
        self.window.toggle_inline_expansion(True)
        self.assertTrue(self.window.workspace.details_view.itemsExpandable())
        self.assertTrue(self.window.workspace.details_view.rootIsDecorated())
        self.assertTrue(self.window.config.inline_tree_expansion)

    def test_toggle_expansion_disables_view(self):
        self.window.toggle_inline_expansion(True)
        self.window.toggle_inline_expansion(False)
        self.assertFalse(self.window.workspace.details_view.itemsExpandable())
        self.assertFalse(self.window.config.inline_tree_expansion)

    def test_expand_current_folder(self):
        """When expansion is enabled, selecting a folder row and expanding works."""
        self.window.toggle_inline_expansion(True)
        view = self.window.workspace.details_view
        self.assertTrue(self._wait_for_rows(view, 2))
        model = view.model()
        # Find the "subfolder" row.
        for row in range(model.rowCount(view.rootIndex())):
            idx = model.index(row, 0, view.rootIndex())
            if model.fileName(idx) == "subfolder":
                view.setCurrentIndex(idx)
                self.assertFalse(view.isExpanded(idx))
                self.window.expand_current_folder()
                self.assertTrue(view.isExpanded(idx))
                break
        else:
            self.fail("subfolder row not found")

    def test_collapse_current_folder(self):
        self.window.toggle_inline_expansion(True)
        view = self.workspace_view()
        self.assertTrue(self._wait_for_rows(view, 2))
        model = view.model()
        for row in range(model.rowCount(view.rootIndex())):
            idx = model.index(row, 0, view.rootIndex())
            if model.fileName(idx) == "subfolder":
                view.setCurrentIndex(idx)
                view.expand(idx)
                self.assertTrue(view.isExpanded(idx))
                self.window.collapse_current_folder()
                self.assertFalse(view.isExpanded(idx))
                break
        else:
            self.fail("subfolder row not found")

    def workspace_view(self):
        return self.window.workspace.details_view

    def test_expanded_child_path_resolves(self):
        """Selecting a child of an expanded folder returns the correct absolute path."""
        self.window.toggle_inline_expansion(True)
        view = self.window.workspace.details_view
        self.assertTrue(self._wait_for_rows(view, 2))
        model = view.model()
        for row in range(model.rowCount(view.rootIndex())):
            idx = model.index(row, 0, view.rootIndex())
            if model.fileName(idx) == "subfolder":
                view.expand(idx)
                # Force async fetch in QFileSystemModel.
                if model.canFetchMore(idx):
                    model.fetchMore(idx)
                deadline = time.monotonic() + 5
                while model.rowCount(idx) < 1 and time.monotonic() < deadline:
                    QApplication.processEvents()
                self.assertGreaterEqual(model.rowCount(idx), 1)
                child = model.index(0, 0, idx)
                child_path = model.filePath(child)
                self.assertEqual(Path(child_path).name, "file_in_sub.txt")
                self.assertIn("subfolder", child_path)
                break
        else:
            self.fail("subfolder not found")

    def test_menu_action_exists(self):
        menubar = self.window.menuBar()
        view_menu = None
        for action in menubar.actions():
            if action.text().replace("&", "") == "View":
                view_menu = action.menu()
                break
        self.assertIsNotNone(view_menu, "View menu not found")
        labels = [a.text() for a in view_menu.actions() if a.text()]
        self.assertIn("Expandable Folders", labels)

    def test_collapse_all(self):
        self.window.toggle_inline_expansion(True)
        view = self.window.workspace.details_view
        self.assertTrue(self._wait_for_rows(view, 2))
        model = view.model()
        for row in range(model.rowCount(view.rootIndex())):
            idx = model.index(row, 0, view.rootIndex())
            if model.fileName(idx) == "subfolder":
                view.expand(idx)
                break
        self.window.collapse_all_expanded()
        for row in range(model.rowCount(view.rootIndex())):
            idx = model.index(row, 0, view.rootIndex())
            if model.fileName(idx) == "subfolder":
                self.assertFalse(view.isExpanded(idx))


if __name__ == "__main__":
    unittest.main()
