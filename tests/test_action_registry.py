"""Unit tests for the UI-agnostic action registry."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QApplication

from lfmapp.actions import (
    ActionRegistry,
    ActionSpec,
    DuplicateActionError,
    UnknownActionError,
)
from lfmapp.actions.qt import apply_enablement, spec_to_action

_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


class ActionRegistryTests(unittest.TestCase):
    def test_register_and_get_roundtrip(self):
        registry = ActionRegistry()
        calls = []
        spec = ActionSpec(
            action_id="nav.back",
            title="Back",
            category="Navigation",
            shortcut="Alt+Left",
            callback=lambda: calls.append("back"),
            aliases=("previous",),
        )
        registry.register(spec)
        self.assertIn("nav.back", registry)
        self.assertEqual(registry.get("nav.back").action_id, "nav.back")
        self.assertEqual(registry.get("nav.back").title, "Back")
        self.assertEqual(len(registry), 1)

    def test_duplicate_id_is_rejected(self):
        registry = ActionRegistry()
        registry.register(ActionSpec(action_id="clip.copy", title="Copy"))
        with self.assertRaises(DuplicateActionError):
            registry.register(ActionSpec(action_id="clip.copy", title="Copy 2"))

    def test_unknown_id_raises(self):
        registry = ActionRegistry()
        with self.assertRaises(UnknownActionError):
            registry.get("does.not.exist")

    def test_all_sorted_by_category_then_title(self):
        registry = ActionRegistry()
        registry.register(ActionSpec(action_id="b", title="Zulu", category="Zed"))
        registry.register(ActionSpec(action_id="a", title="Alpha", category="Alpha"))
        titles = [spec.title for spec in registry.all()]
        self.assertEqual(titles, ["Alpha", "Zulu"])
        self.assertEqual(registry.categories(), ["Alpha", "Zed"])

    def test_enablement_predicate_uses_context(self):
        registry = ActionRegistry()
        registry.register(
            ActionSpec(
                action_id="clip.paste",
                title="Paste",
                enabled_when=lambda ctx: bool(ctx.get("has_selection")),
            )
        )
        registry.register(ActionSpec(action_id="file.new", title="New File"))
        self.assertTrue(registry.enabled("clip.paste", {"has_selection": True}))
        self.assertFalse(registry.enabled("clip.paste", {"has_selection": False}))
        # No predicate -> enabled unless context forces off.
        self.assertTrue(registry.enabled("file.new", {}))
        self.assertFalse(registry.enabled("file.new", {"enabled": False}))

    def test_broken_predicate_disables_instead_of_crashing(self):
        registry = ActionRegistry()

        def boom(_ctx):
            raise RuntimeError("bad predicate")

        registry.register(
            ActionSpec(action_id="fragile", title="Fragile", enabled_when=boom)
        )
        self.assertFalse(registry.enabled("fragile", {}))

    def test_enablement_map_covers_all(self):
        registry = ActionRegistry()
        registry.register(
            ActionSpec(
                action_id="a",
                title="A",
                enabled_when=lambda ctx: ctx.get("flag", False),
            )
        )
        registry.register(ActionSpec(action_id="b", title="B"))
        result = registry.enablement_map({"flag": True})
        self.assertEqual(result["a"], True)
        self.assertEqual(result["b"], True)
        result = registry.enablement_map({"flag": False})
        self.assertEqual(result["a"], False)

    def test_effective_command_id_falls_back(self):
        spec = ActionSpec(action_id="nav.up", title="Up")
        self.assertEqual(spec.effective_command_id, "nav.up")
        spec2 = ActionSpec(action_id="x", title="X", command_id="legacy.id")
        self.assertEqual(spec2.effective_command_id, "legacy.id")


class ActionQtAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_qapplication()

    def test_spec_to_action_string_shortcut(self):
        calls = []
        spec = ActionSpec(
            action_id="view.refresh",
            title="Refresh",
            shortcut="F5",
            callback=lambda: calls.append(1),
        )
        action = spec_to_action(spec)
        self.assertIsInstance(action, QAction)
        self.assertEqual(action.text(), "Refresh")
        self.assertEqual(action.objectName(), "view.refresh")
        self.assertEqual(action.shortcut().toString(), "F5")
        action.trigger()
        self.assertEqual(calls, [1])

    def test_spec_to_action_standard_key(self):
        spec = ActionSpec(
            action_id="clip.copy",
            title="Copy",
            shortcut=QKeySequence.StandardKey.Copy,
        )
        action = spec_to_action(spec)
        self.assertTrue(action.shortcut() == QKeySequence(QKeySequence.StandardKey.Copy))

    def test_apply_enablement_only_touches_registered(self):
        registry = ActionRegistry()
        registry.register(
            ActionSpec(
                action_id="clip.paste",
                title="Paste",
                enabled_when=lambda ctx: bool(ctx.get("can_paste")),
            )
        )
        paste = spec_to_action(registry.get("clip.paste"))
        legacy = spec_to_action(
            ActionSpec(action_id="legacy.unregistered", title="Old")
        )
        legacy.setEnabled(False)  # must stay untouched
        actions = {"clip.paste": paste, "legacy.unregistered": legacy}
        apply_enablement(registry, actions, {"can_paste": True})
        self.assertTrue(paste.isEnabled())
        self.assertFalse(legacy.isEnabled())
        apply_enablement(registry, actions, {"can_paste": False})
        self.assertFalse(paste.isEnabled())


if __name__ == "__main__":
    unittest.main()
