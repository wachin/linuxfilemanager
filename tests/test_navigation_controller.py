"""Tests for the navigation history controller (Fase 1.1)."""

import tempfile
import unittest
from pathlib import Path

from lfmapp.controllers import NavigationController


class NavigationControllerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.a = self.root / "a"
        self.b = self.root / "b"
        self.c = self.root / "c"

    def tearDown(self):
        self._tmp.cleanup()

    def test_navigate_appends_and_moves_index(self):
        nav = NavigationController()
        self.assertTrue(nav.navigate_to(self.a))
        self.assertTrue(nav.navigate_to(self.b))
        self.assertEqual(nav.current, self.b)
        self.assertEqual(nav.history, [self.a, self.b])
        self.assertFalse(nav.can_go_forward)
        self.assertTrue(nav.can_go_back)

    def test_duplicate_consecutive_location_is_not_recorded(self):
        nav = NavigationController()
        nav.navigate_to(self.a)
        self.assertFalse(nav.navigate_to(self.a))
        self.assertEqual(len(nav.history), 1)

    def test_back_forward_roundtrip(self):
        nav = NavigationController()
        nav.navigate_to(self.a)
        nav.navigate_to(self.b)
        nav.navigate_to(self.c)
        self.assertEqual(nav.back(), self.b)
        self.assertEqual(nav.back(), self.a)
        self.assertFalse(nav.can_go_back)
        self.assertIsNone(nav.back())
        self.assertEqual(nav.forward(), self.b)
        self.assertEqual(nav.forward(), self.c)
        self.assertFalse(nav.can_go_forward)
        self.assertIsNone(nav.forward())

    def test_new_navigation_truncates_forward_history(self):
        nav = NavigationController()
        nav.navigate_to(self.a)
        nav.navigate_to(self.b)
        nav.navigate_to(self.c)
        nav.back()  # now at b; forward list = [c]
        self.assertTrue(nav.can_go_forward)
        nav.navigate_to(self.a / "x")  # new navigation from b
        self.assertEqual(nav.history, [self.a, self.b, self.a / "x"])
        self.assertFalse(nav.can_go_forward)

    def test_go_up_from_returns_parent(self):
        nav = NavigationController()
        parent = nav.go_up_from(self.b)
        self.assertEqual(parent, self.root)

    def test_go_up_from_returns_none_at_filesystem_root(self):
        nav = NavigationController()
        self.assertIsNone(nav.go_up_from(Path("/")))
        self.assertIsNone(nav.go_up_from(None))

    def test_state_roundtrip(self):
        nav = NavigationController()
        nav.navigate_to(self.a)
        nav.navigate_to(self.b)
        state = nav.state()
        restored = NavigationController.from_state(state)
        self.assertEqual(restored.history, [self.a, self.b])
        self.assertEqual(restored.index, 1)
        self.assertEqual(restored.current, self.b)

    def test_from_state_empty(self):
        nav = NavigationController.from_state(None)
        self.assertEqual(nav.history, [])
        self.assertEqual(nav.index, -1)


if __name__ == "__main__":
    unittest.main()
