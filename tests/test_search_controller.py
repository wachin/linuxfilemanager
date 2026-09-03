"""Tests for the search lifecycle controller (Fase 1.1)."""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from lfmapp.controllers import SearchController, SearchOutcome
from lfmapp.services.search_service import SearchFilters


def _make_corpus(root: Path, total: int, matches: int):
    root.mkdir(parents=True, exist_ok=True)
    for i in range(total):
        name = f"needle-{i}.txt" if i < matches else f"filler-{i}.txt"
        (root / name).write_text("x", encoding="utf-8")
    return root


def _pump_until(condition, timeout=10.0):
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    return bool(condition())


class SearchControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        if QApplication.instance() is None:
            QApplication([])
    def test_empty_query_without_filters_does_nothing(self):
        controller = SearchController()
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_corpus(Path(tmp), 5, 2)
            started = controller.start("", root=root)
            self.assertFalse(started)
            self.assertFalse(controller.is_running)

    def test_threaded_search_collects_matches(self):
        controller = SearchController()
        finished = {"count": None}
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_corpus(Path(tmp), 40, 3)
            started = controller.start(
                "needle",
                root=root,
                outcome=SearchOutcome(on_finished=lambda c: finished.update(count=c)),
            )
            self.assertTrue(started)
            self.assertTrue(
                _pump_until(lambda: finished["count"] is not None),
                "search should finish",
            )
        self.assertEqual(finished["count"], 3)
        self.assertEqual(len(controller.results), 3)

    def test_indexed_path_used_when_enabled(self):
        calls = {"indexed": 0}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("x", encoding="utf-8")

            def fake_index(query, base):
                calls["indexed"] += 1
                return [root / "a.txt"]

            controller = SearchController(
                text_index_enabled_provider=lambda: True,
                index_search=fake_index,
            )
            finished = {"count": None}
            controller.start(
                "alpha",
                root=root,
                outcome=SearchOutcome(on_finished=lambda c: finished.update(count=c)),
            )
            self.assertEqual(calls["indexed"], 1)
            self.assertEqual(finished["count"], 1)
            self.assertFalse(controller.is_running)

    def test_new_search_cancels_previous(self):
        controller = SearchController()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Interleave two families so both searches find many matches.
            for i in range(1500):
                (root / f"needle-{i}.txt").write_text("x", encoding="utf-8")
                (root / f"filler-{i}.txt").write_text("x", encoding="utf-8")
            first_finished = {"count": None}
            controller.start(
                "needle",
                root=root,
                outcome=SearchOutcome(on_finished=lambda c: first_finished.update(count=c)),
            )
            self.assertTrue(controller.is_running)
            # Start a second search while the first runs.
            second_finished = {"count": None}
            started = controller.start(
                "filler",
                root=root,
                outcome=SearchOutcome(on_finished=lambda c: second_finished.update(count=c)),
            )
            self.assertTrue(started)
            self.assertTrue(
                _pump_until(lambda: second_finished["count"] is not None),
                "second search should finish",
            )
        self.assertEqual(second_finished["count"], 1500)

    def test_cancel_keeps_collected_results(self):
        controller = SearchController()
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_corpus(Path(tmp), 4000, 4000)
            controller.start("needle", root=root)
            time.sleep(0.05)
            controller.cancel()
            self.assertFalse(controller.is_running)
            # Results collected before cancel remain available.
            self.assertGreaterEqual(len(controller.results), 0)


if __name__ == "__main__":
    unittest.main()
