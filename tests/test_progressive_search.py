"""Tests for progressive search (ROADMAP Phase 5.1)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from lfmapp.controllers.search_controller import SearchController, SearchOutcome
from lfmapp.services.search_service import (
    SearchFilters,
    SearchQuery,
    SearchThread,
)

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


class SearchQuerySerializationTests(unittest.TestCase):
    def test_roundtrip(self):
        query = SearchQuery(
            query="report",
            mode="content",
            recursive=True,
            filters=SearchFilters(file_type="document", min_size=10),
        )
        restored = SearchQuery.from_dict(query.to_dict())
        self.assertEqual(restored.query, "report")
        self.assertEqual(restored.mode, "content")
        self.assertTrue(restored.recursive)
        self.assertEqual(restored.filters.file_type, "document")
        self.assertEqual(restored.filters.min_size, 10)

    def test_defaults(self):
        query = SearchQuery.from_dict(None)
        self.assertEqual(query.query, "")
        self.assertEqual(query.mode, "name")
        self.assertFalse(query.recursive)

    def test_filters_roundtrip(self):
        filters = SearchFilters(file_type="image", min_size=5, max_size=100)
        restored = SearchFilters.from_dict(filters.to_dict())
        self.assertEqual(restored, filters)


class SearchThreadTests(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def _run(self, thread):
        batches = []
        found = []
        final = {}
        thread.batch.connect(lambda b: batches.append(b))
        thread.found.connect(lambda p: found.append(p))
        thread.finished.connect(lambda c: final.setdefault("count", c))
        thread.run()  # synchronous body
        return found, batches, final.get("count", 0)

    def test_content_search_matches_file_body(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "notes.txt").write_text("hello world")
            (root / "other.txt").write_text("nothing here")
            thread = SearchThread(root, "hello", recursive=False, mode="content")
            found, _batches, _count = self._run(thread)
            names = {p.name for p in found}
            self.assertIn("notes.txt", names)
            self.assertNotIn("other.txt", names)

    def test_content_search_ignores_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "subdir").mkdir()
            thread = SearchThread(root, "sub", recursive=False, mode="content")
            found, _b, _c = self._run(thread)
            self.assertEqual(found, [])

    def test_recursive_name_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sub = root / "sub"
            sub.mkdir()
            (sub / "needle.txt").write_text("x")
            thread = SearchThread(root, "needle", recursive=True, mode="name")
            found, _b, _c = self._run(thread)
            self.assertEqual({p.name for p in found}, {"needle.txt"})

    def test_batch_progressive_emission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for i in range(5):
                (root / f"target_{i}.txt").write_text(f"data {i}")
            thread = SearchThread(root, "target", recursive=False, mode="name", batch_size=2)
            found, batches, count = self._run(thread)
            self.assertEqual(count, 5)
            self.assertTrue(all(len(b) <= 2 for b in batches))
            # All batches together equal the found set.
            self.assertEqual(sum(len(b) for b in batches), 5)


class SearchControllerProgressTests(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def test_query_driven_search_tracks_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("x")

            batch_results = []
            finished_count = []
            controller = SearchController()
            outcome = SearchOutcome(
                on_batch=lambda batch: batch_results.extend(batch),
                on_finished=lambda c: finished_count.append(c),
            )
            controller.start_query(
                SearchQuery(query="a", mode="name", recursive=False),
                root=root,
                outcome=outcome,
            )
            # Pump the event loop so queued signal delivery completes.
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            for _ in range(500):
                app.processEvents()
                if finished_count:
                    break
            self.assertEqual(controller.result_count, 1)
            self.assertEqual(controller.status, "done")
            self.assertTrue(finished_count)

    def test_indexed_path_when_enabled_and_name_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = SearchController(
                text_index_enabled_provider=lambda: True,
                index_search=lambda q, r: [Path(r) / f"{q}.txt"],
            )
            finished = []
            controller.start_query(
                SearchQuery(query="x", mode="name"),
                root=root,
                outcome=SearchOutcome(on_finished=lambda c: finished.append(c)),
            )
            self.assertEqual(controller.status, "done")
            self.assertEqual(finished, [1])

    def test_running_query_serializes_state(self):
        controller = SearchController()
        controller.query = "abc"
        controller.mode = "content"
        controller.recursive = True
        controller.filters = SearchFilters(file_type="video")
        self.assertEqual(controller.running_query.query, "abc")
        self.assertEqual(controller.running_query.mode, "content")
        self.assertTrue(controller.running_query.recursive)


if __name__ == "__main__":
    unittest.main()