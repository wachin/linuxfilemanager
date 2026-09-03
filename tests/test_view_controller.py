"""Tests for the view policy controller (Fase 1.1)."""

import unittest
from pathlib import Path

from lfmapp.controllers.view_controller import ViewController
from lfmapp.ui.workspace import ViewMode


class FakeConfig:
    """Minimal in-memory config exposing only the folder-view API."""

    def __init__(self):
        self._remember = False
        self._views = {}

    def remember_folder_view(self) -> bool:
        return self._remember

    def set_remember_folder_view(self, value: bool):
        self._remember = bool(value)

    def get_folder_view(self, path: str) -> str | None:
        return self._views.get(path)

    def set_folder_view(self, path: str | None, view: str):
        if path:
            self._views[path] = view

    def clear_folder_view(self, path: str | None):
        self._views.pop(path, None)

    def clear_all_folder_views(self):
        self._views.clear()


class ViewControllerTests(unittest.TestCase):
    def setUp(self):
        self.config = FakeConfig()
        self.controller = ViewController(self.config)

    def test_disabled_by_default_returns_fallback(self):
        path = Path("/tmp/example")
        self.assertEqual(self.controller.view_to_restore(path), "details")

    def test_remember_only_when_enabled(self):
        path = Path("/tmp/example")
        self.controller.remember(path, ViewMode.ICON)
        self.assertIsNone(self.config.get_folder_view(str(path)))
        self.controller.set_enabled(True)
        self.controller.remember(path, ViewMode.LIST)
        self.assertEqual(self.config.get_folder_view(str(path)), "list")

    def test_restore_returns_saved_view(self):
        self.controller.set_enabled(True)
        path = Path("/tmp/example")
        self.controller.remember(path, ViewMode.DETAILS)
        self.assertEqual(self.controller.view_to_restore(path), "details")
        self.controller.remember(path, ViewMode.ICON)
        self.assertEqual(self.controller.view_to_restore(path), "icon")

    def test_clear_removes_single_folder(self):
        self.controller.set_enabled(True)
        path = Path("/tmp/example")
        other = Path("/tmp/other")
        self.controller.remember(path, ViewMode.ICON)
        self.controller.remember(other, ViewMode.LIST)
        self.controller.clear(path)
        self.assertEqual(self.controller.view_to_restore(path), "details")
        self.assertEqual(self.controller.view_to_restore(other), "list")

    def test_clear_all(self):
        self.controller.set_enabled(True)
        self.controller.remember(Path("/tmp/a"), ViewMode.ICON)
        self.controller.remember(Path("/tmp/b"), ViewMode.LIST)
        self.controller.clear_all()
        self.assertEqual(self.config._views, {})

    def test_remember_accepts_string_mode(self):
        self.controller.set_enabled(True)
        self.controller.remember(Path("/tmp/x"), "compact")
        self.assertEqual(self.config.get_folder_view("/tmp/x"), "compact")

    def test_coerce_uses_fallback_for_unknown(self):
        self.assertEqual(
            ViewController.coerce("bogus", ViewMode.DETAILS), ViewMode.DETAILS
        )
        self.assertEqual(
            ViewController.coerce("icon", ViewMode.DETAILS), ViewMode.ICON
        )


if __name__ == "__main__":
    unittest.main()
