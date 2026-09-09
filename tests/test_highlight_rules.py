"""Tests for the automatic appearance-rule engine (backlog P2).

Covers:
- HighlightEffect merge/is_empty.
- HighlightRule.matches: name glob, path substring, tag, type/size/date
  (via SearchFilters).
- evaluate_rules stacking + stop-at-first-match + disabled rules.
- sanitize_rule / rules_from_config versioning + dropping empty-effect rules.
- HighlightEvaluator caching + invalidation.
- Serialization round-trip (to_dict/from_dict).
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from lfmapp.services.highlight_service import (
    HighlightEffect,
    HighlightEvaluator,
    HighlightRule,
    evaluate_rules,
    rules_from_config,
    sanitize_rule,
)


_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return app


def _write(path: Path, content: str = "x") -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class EffectTests(unittest.TestCase):
    def test_is_empty(self):
        self.assertTrue(HighlightEffect().is_empty())
        self.assertFalse(HighlightEffect(fg_color="#fff").is_empty())
        self.assertFalse(HighlightEffect(bold=True).is_empty())

    def test_merge_overrides_channels(self):
        a = HighlightEffect(fg_color="#aaa", bold=True)
        b = HighlightEffect(fg_color="#bbb", italic=True)
        m = a.merge(b)
        self.assertEqual(m.fg_color, "#bbb")   # b wins
        self.assertTrue(m.bold)                # a's bold kept (b didn't set)
        self.assertTrue(m.italic)              # b's italic added

    def test_merge_keeps_unset(self):
        a = HighlightEffect(bg_color="#111")
        m = a.merge(HighlightEffect())
        self.assertEqual(m.bg_color, "#111")


class RuleMatchesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.jpg = _write(self.root / "photo.jpg", "data")
        self.txt = _write(self.root / "notes.txt", "hello world text")
        self.folder = self.root / "mydir"
        self.folder.mkdir()

    def test_name_glob(self):
        r = HighlightRule(name_glob="*.jpg", fg_color="#000")
        self.assertTrue(r.matches(self.jpg))
        self.assertFalse(r.matches(self.txt))

    def test_name_glob_case_insensitive(self):
        r = HighlightRule(name_glob="*.JPG", fg_color="#000")
        self.assertTrue(r.matches(self.jpg))

    def test_path_contains(self):
        r = HighlightRule(path_contains="mydir", fg_color="#000")
        self.assertTrue(r.matches(self.folder))
        self.assertFalse(r.matches(self.txt))

    def test_type_image(self):
        r = HighlightRule(file_type="image", fg_color="#000")
        self.assertTrue(r.matches(self.jpg))
        self.assertFalse(r.matches(self.txt))

    def test_type_folder(self):
        r = HighlightRule(file_type="folder", fg_color="#000")
        self.assertTrue(r.matches(self.folder))
        self.assertFalse(r.matches(self.jpg))

    def test_min_size(self):
        big = _write(self.root / "big.txt", "x" * 1000)
        r = HighlightRule(min_size=500, fg_color="#000")
        self.assertTrue(r.matches(big))
        self.assertFalse(r.matches(self.txt))

    def test_tag_match_with_provider(self):
        r = HighlightRule(tag="important", fg_color="#000")
        tags = {"photo.jpg": ["important", "work"]}
        provider = lambda p: tags.get(p.name, [])
        self.assertTrue(r.matches(self.jpg, tags_for_path=provider))
        self.assertFalse(r.matches(self.txt, tags_for_path=provider))

    def test_tag_match_no_provider(self):
        r = HighlightRule(tag="x", fg_color="#000")
        self.assertFalse(r.matches(self.jpg))  # no provider -> can't match tag

    def test_empty_rule_matches_everything(self):
        r = HighlightRule(fg_color="#000")
        self.assertTrue(r.matches(self.jpg))
        self.assertTrue(r.matches(self.txt))


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.jpg = _write(self.root / "a.jpg")

    def test_no_rules_empty_effect(self):
        self.assertTrue(evaluate_rules([], self.jpg).is_empty())

    def test_single_match(self):
        rules = [HighlightRule(name_glob="*.jpg", fg_color="#ff0000")]
        eff = evaluate_rules(rules, self.jpg)
        self.assertEqual(eff.fg_color, "#ff0000")

    def test_stacking(self):
        rules = [
            HighlightRule(name_glob="*.jpg", fg_color="#111111"),
            HighlightRule(file_type="image", bold=True),
        ]
        eff = evaluate_rules(rules, self.jpg)
        self.assertEqual(eff.fg_color, "#111111")
        self.assertTrue(eff.bold)

    def test_later_rule_overrides_channel(self):
        rules = [
            HighlightRule(fg_color="#111111"),
            HighlightRule(fg_color="#222222"),
        ]
        eff = evaluate_rules(rules, self.jpg)
        self.assertEqual(eff.fg_color, "#222222")

    def test_disabled_rule_skipped(self):
        rules = [HighlightRule(fg_color="#111", enabled=False)]
        eff = evaluate_rules(rules, self.jpg)
        self.assertTrue(eff.is_empty())

    def test_stop_at_first_match(self):
        rules = [
            HighlightRule(name_glob="*.jpg", fg_color="#111111", stop=True),
            HighlightRule(name_glob="*.jpg", fg_color="#222222"),
        ]
        eff = evaluate_rules(rules, self.jpg)
        self.assertEqual(eff.fg_color, "#111111")

    def test_nonmatching_rule_no_effect(self):
        rules = [HighlightRule(name_glob="*.png", fg_color="#111")]
        self.assertTrue(evaluate_rules(rules, self.jpg).is_empty())


class SanitizeTests(unittest.TestCase):
    def test_sanitize_valid(self):
        d = HighlightRule(name_glob="*.jpg", fg_color="#111").to_dict()
        self.assertIsNotNone(sanitize_rule(d))

    def test_sanitize_drops_empty_effect(self):
        d = HighlightRule(name_glob="*.jpg").to_dict()  # no effect
        self.assertIsNone(sanitize_rule(d))

    def test_sanitize_drops_foreign_version(self):
        d = HighlightRule(fg_color="#1").to_dict()
        d["version"] = 999
        self.assertIsNone(sanitize_rule(d))

    def test_sanitize_non_dict(self):
        self.assertIsNone(sanitize_rule("not a dict"))
        self.assertIsNone(sanitize_rule(None))

    def test_rules_from_config(self):
        raw = [
            HighlightRule(fg_color="#1").to_dict(),
            HighlightRule().to_dict(),            # empty effect -> dropped
            {"version": 999, "fg_color": "#2"},   # foreign -> dropped
            "garbage",
        ]
        rules = rules_from_config(raw)
        self.assertEqual(len(rules), 1)

    def test_roundtrip(self):
        r = HighlightRule(name="x", name_glob="*.jpg", fg_color="#1", bold=True, stop=True)
        r2 = HighlightRule.from_dict(r.to_dict())
        self.assertEqual(r2.name, "x")
        self.assertEqual(r2.name_glob, "*.jpg")
        self.assertEqual(r2.fg_color, "#1")
        self.assertTrue(r2.bold)
        self.assertTrue(r2.stop)


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.jpg = _write(Path(self._tmp) / "a.jpg")
        self.txt = _write(Path(self._tmp) / "b.txt")
        self.rules = [HighlightRule(name_glob="*.jpg", fg_color="#ff0000")]
        self.ev = HighlightEvaluator(self.rules)

    def test_returns_effect(self):
        self.assertEqual(self.ev.effect_for(self.jpg).fg_color, "#ff0000")

    def test_cache_hit(self):
        self.ev.effect_for(self.jpg)
        # Second call served from cache.
        self.assertIn(str(self.jpg), self.ev._cache)

    def test_disabled_returns_empty(self):
        self.ev.set_enabled(False)
        self.assertTrue(self.ev.effect_for(self.jpg).is_empty())

    def test_invalidate_clears_cache(self):
        self.ev.effect_for(self.jpg)
        self.ev.invalidate()
        self.assertEqual(self.ev._cache, {})

    def test_set_rules_invalidates(self):
        self.ev.effect_for(self.jpg)
        self.ev.set_rules([HighlightRule(name_glob="*.txt", fg_color="#00ff00")])
        self.assertEqual(self.ev.effect_for(self.txt).fg_color, "#00ff00")

    def test_empty_rules_returns_empty(self):
        ev = HighlightEvaluator([])
        self.assertTrue(ev.effect_for(self.jpg).is_empty())


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------

class HighlightConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        import lfmapp.core.config as cm
        self._cm = cm
        self._orig_dir = cm.CONFIG_DIR
        self._orig_file = cm.CONFIG_FILE
        cm.CONFIG_DIR = Path(self._tmp)
        cm.CONFIG_FILE = Path(self._tmp) / "config.json"
        from lfmapp.core.config import Config
        self.config = Config()

    def tearDown(self):
        self._cm.CONFIG_DIR = self._orig_dir
        self._cm.CONFIG_FILE = self._orig_file

    def test_default_empty_rules(self):
        self.assertEqual(self.config.get_highlight_rules(), [])

    def test_default_enabled_true(self):
        self.assertTrue(self.config.highlighting_enabled)

    def test_set_get_rules(self):
        rules = [HighlightRule(name="x", name_glob="*.jpg", fg_color="#1").to_dict()]
        self.config.set_highlight_rules(rules)
        self.assertEqual(len(self.config.get_highlight_rules()), 1)

    def test_set_rules_drops_non_dicts(self):
        self.config.set_highlight_rules([{"fg_color": "#1"}, "garbage", 42])
        self.assertEqual(len(self.config.get_highlight_rules()), 1)

    def test_rules_persist(self):
        self.config.set_highlight_rules([HighlightRule(fg_color="#1").to_dict()])
        self.config.set_highlighting_enabled(False)
        from lfmapp.core.config import Config
        c2 = Config()
        self.assertEqual(len(c2.get_highlight_rules()), 1)
        self.assertFalse(c2.highlighting_enabled)


# ---------------------------------------------------------------------------
# Delegate + MainWindow integration (GUI)
# ---------------------------------------------------------------------------

class HighlightDelegateGuiTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        import lfmapp.core.config as cm
        self._cm = cm
        self._orig_dir = cm.CONFIG_DIR
        self._orig_file = cm.CONFIG_FILE
        self._tmp = tempfile.mkdtemp()
        cm.CONFIG_DIR = Path(self._tmp)
        cm.CONFIG_FILE = Path(self._tmp) / "config.json"
        from lfmapp.core.config import Config
        self.config = Config()
        self.config.data["first_run_done"] = True
        self.config.set_highlight_rules([
            HighlightRule(name="jpgs", name_glob="*.jpg", fg_color="#ff0000", bold=True).to_dict()
        ])
        self.root = Path(self._tmp) / "files"
        self.root.mkdir()
        (self.root / "a.jpg").write_text("x", encoding="utf-8")
        (self.root / "b.txt").write_text("y", encoding="utf-8")
        from lfmapp.ui.main_window import MainWindow
        self.window = MainWindow(self.config)

    def tearDown(self):
        self.window.close()
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        self._cm.CONFIG_DIR = self._orig_dir
        self._cm.CONFIG_FILE = self._orig_file

    def test_evaluator_built_from_config(self):
        self.assertIsNotNone(self.window.highlight_evaluator)
        self.assertEqual(len(self.window.highlight_evaluator.rules()), 1)

    def test_delegate_installed_on_views(self):
        self.assertIsNotNone(self.window.workspace._highlight_delegate)
        self.assertIs(
            self.window.workspace.details_view.itemDelegate(),
            self.window.workspace._highlight_delegate,
        )

    def test_delegate_effect_for_path(self):
        eff = self.window.highlight_evaluator.effect_for(self.root / "a.jpg")
        self.assertEqual(eff.fg_color, "#ff0000")
        self.assertTrue(eff.bold)
        self.assertTrue(self.window.highlight_evaluator.effect_for(self.root / "b.txt").is_empty())

    def test_toggle_off_disables_effect(self):
        self.window.toggle_highlighting(False)
        self.assertFalse(self.window.highlight_evaluator.enabled)
        self.assertTrue(self.window.highlight_evaluator.effect_for(self.root / "a.jpg").is_empty())
        self.window.toggle_highlighting(True)
        self.assertEqual(self.window.highlight_evaluator.effect_for(self.root / "a.jpg").fg_color, "#ff0000")

    def test_reload_picks_up_new_rules(self):
        self.config.set_highlight_rules([
            HighlightRule(name="txts", name_glob="*.txt", bg_color="#00ff00").to_dict()
        ])
        self.window.reload_highlighting()
        self.assertEqual(self.window.highlight_evaluator.effect_for(self.root / "b.txt").bg_color, "#00ff00")

    def test_delegate_paint_does_not_crash(self):
        """Rendering a row through the delegate must not raise."""
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QImage, QPainter
        from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem
        view = self.window.workspace.details_view
        model = view.model()
        # Wait for the model to populate.
        deadline = time.monotonic() + 8
        while model.rowCount(view.rootIndex()) < 1 and time.monotonic() < deadline:
            QApplication.processEvents()
        self.assertGreaterEqual(model.rowCount(view.rootIndex()), 1)
        idx = model.index(0, 0, view.rootIndex())
        img = QImage(200, 30, QImage.Format.Format_ARGB32)
        img.fill(0xFFFFFFFF)
        painter = QPainter(img)
        opt = QStyleOptionViewItem()
        opt.rect = QRect(0, 0, 200, 30)
        opt.widget = view
        opt.state |= QStyle.StateFlag.State_Enabled
        delegate = self.window.workspace._highlight_delegate
        delegate.paint(painter, opt, idx)
        painter.end()
        self.assertTrue(True)  # no exception


if __name__ == "__main__":
    unittest.main()
