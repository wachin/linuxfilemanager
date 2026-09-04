"""Tests for the ShortcutMap controller (ROADMAP Phase 4.2)."""

import unittest

from lfmapp.controllers.shortcut_map import ShortcutMap, normalize_shortcut


class NormalizeShortcutTests(unittest.TestCase):
    def test_normalize_strips_and_normalizes(self):
        self.assertEqual(normalize_shortcut(" Ctrl+Shift+P "), "Ctrl+Shift+P")
        self.assertEqual(normalize_shortcut(""), "")
        self.assertEqual(normalize_shortcut(None), "")


class ShortcutMapTests(unittest.TestCase):
    def setUp(self):
        self.map = ShortcutMap()

    def test_register_and_retrieve(self):
        self.map.register("cmd.open", "Open", shortcut="Enter")
        record = self.map.get("cmd.open")
        self.assertEqual(record.title, "Open")
        self.assertEqual(record.shortcut, "Enter")

    def test_update_in_place_keeps_id(self):
        self.map.register("cmd.refresh", "Refresh", shortcut="F5")
        self.map.register("cmd.refresh", "Refresh", shortcut="Ctrl+R")
        self.assertEqual(len(self.map.commands()), 1)
        self.assertEqual(self.map.get("cmd.refresh").shortcut, "Ctrl+R")

    def test_collision_detection(self):
        self.map.register("a", "Action A", shortcut="Ctrl+S")
        self.map.register("b", "Action B", shortcut="Ctrl+S")
        collisions = self.map.collisions
        self.assertIn("Ctrl+S", collisions)
        self.assertEqual(len(collisions["Ctrl+S"]), 2)

    def test_no_collision_with_distinct_shortcuts(self):
        self.map.register("a", "Action A", shortcut="Ctrl+S")
        self.map.register("b", "Action B", shortcut="Ctrl+Shift+S")
        self.assertEqual(self.map.collisions, {})

    def test_empty_shortcuts_do_not_collide(self):
        self.map.register("a", "Action A", shortcut="")
        self.map.register("b", "Action B", shortcut="")
        self.assertEqual(self.map.collisions, {})

    def test_commands_by_shortcut(self):
        self.map.register("a", "Action A", shortcut="Ctrl+K")
        self.assertEqual([r.command_id for r in self.map.commands_by_shortcut("Ctrl+K")], ["a"])

    def test_palette_entries_preserve_state(self):
        self.map.register(
            "cmd.canvas",
            "Canvas",
            shortcut="Ctrl+1",
            category="View",
            enabled=False,
            disabled_reason="no selection",
            aliases=["view", "icons"],
        )
        entries = self.map.palette_entries()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertFalse(entry["enabled"])
        self.assertEqual(entry["disabled_reason"], "no selection")
        self.assertEqual(entry["alias"], ["view", "icons"])

    def test_auto_id_when_missing(self):
        self.map.register("", "Unnamed")
        self.assertEqual(len(self.map.commands()), 1)
        self.assertTrue(self.map.commands()[0].command_id.startswith("__auto_"))


if __name__ == "__main__":
    unittest.main()