import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtGui import QIcon

from lfmapp.ui.icons import app_icon, application_icon


class UiIconsTests(unittest.TestCase):
    def setUp(self):
        import lfmapp.ui.icons as icons_module

        self.icons = icons_module
        self._old_icon_cache = dict(self.icons._ICON_CACHE)
        self._old_path_cache = dict(self.icons._ICON_PATH_CACHE)
        self.icons._ICON_CACHE.clear()
        self.icons._ICON_PATH_CACHE.clear()

    def tearDown(self):
        self.icons._ICON_CACHE.clear()
        self.icons._ICON_PATH_CACHE.clear()
        self.icons._ICON_CACHE.update(self._old_icon_cache)
        self.icons._ICON_PATH_CACHE.update(self._old_path_cache)
        self.icons._LAST_THEME_NAME = None

    def test_app_icon_uses_active_theme_then_next_requested_name(self):
        import tempfile

        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp.write(svg.encode("utf-8"))
            tmp_path = tmp.name

        try:
            # Like Thunar: resolve from the active theme only; when a name is
            # absent there, move on to the next requested name/alias instead of
            # hunting in other icon themes.
            with patch("lfmapp.ui.icons.QIcon.fromTheme") as from_theme:
                from_theme.side_effect = [QIcon(), QIcon(tmp_path)]

                icon = app_icon("missing", "document-open")

            self.assertFalse(icon.isNull())
            self.assertEqual(from_theme.call_args_list[0].args, ("missing",))
            self.assertEqual(from_theme.call_args_list[1].args, ("folder-open",))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_app_icon_returns_empty_icon_when_none_are_available(self):
        with patch("lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon()) as from_theme:
            icon = app_icon("missing-one", "missing-two")

        self.assertTrue(icon.isNull())
        self.assertGreaterEqual(from_theme.call_count, 2)

    def test_app_icon_caches_missed_names(self):
        # A name absent from the active theme is only asked once; later lookups
        # return the cached empty icon without touching the theme engine again.
        with patch("lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon()) as from_theme:
            first = app_icon("not-in-any-theme")
            second = app_icon("not-in-any-theme")

        self.assertTrue(first.isNull())
        self.assertTrue(second.isNull())
        self.assertEqual(from_theme.call_count, 1)

    def test_app_icon_keeps_looking_after_a_cached_miss_on_an_alias(self):
        # A known-miss alias must not stop resolution: later aliases can still
        # provide an icon from the active theme.
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp.write(svg.encode("utf-8"))
            tmp_path = tmp.name
        try:
            import lfmapp.ui.icons as icons_module

            icons_module._ICON_CACHE["arrow-left"] = QIcon()  # known miss
            with patch(
                "lfmapp.ui.icons.QIcon.fromTheme",
                side_effect=[QIcon(tmp_path)],
            ) as from_theme:
                icon = app_icon("go-previous")

            self.assertFalse(icon.isNull())
            self.assertEqual(from_theme.call_args_list[0].args, ("go-previous",))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_application_icon_falls_back_to_svg_asset(self):
        with patch("lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon()):
            icon = application_icon()

        self.assertFalse(icon.isNull())


class IconResolutionTests(unittest.TestCase):
    """Behaviour of the startup icon cache (Fase 0.2 finding #1)."""

    def setUp(self):
        import lfmapp.ui.icons as icons_module

        self.icons = icons_module
        self._old_icon_cache = dict(self.icons._ICON_CACHE)
        self._old_path_cache = dict(self.icons._ICON_PATH_CACHE)
        self.icons._ICON_CACHE.clear()
        self.icons._ICON_PATH_CACHE.clear()

    def tearDown(self):
        self.icons._ICON_CACHE.clear()
        self.icons._ICON_PATH_CACHE.clear()
        self.icons._ICON_CACHE.update(self._old_icon_cache)
        self.icons._ICON_PATH_CACHE.update(self._old_path_cache)
        self.icons._LAST_THEME_NAME = None

    @staticmethod
    def _make_config():
        """Duck-typed config with the icon-search surface used by icons.py."""
        class _FakeConfig:
            def __init__(self):
                self._found = {}
                self._misses = []
                self.complete = False

            @property
            def cached_icon_paths(self):
                return dict(self._found)

            @property
            def icon_search_misses(self):
                return list(self._misses)

            def set_cached_icon_path(self, name, path):
                self._found[str(name)] = str(path)

            def add_icon_search_miss(self, name):
                if name not in self._misses:
                    self._misses.append(str(name))

            def set_icon_search_complete(self, ready):
                self.complete = bool(ready)

        return _FakeConfig()

    def test_runtime_lookup_uses_cached_index_not_per_name_scans(self):
        # A bare theme (null fromTheme) + an empty file index => still a null
        # icon, and the (expensive) full index is only consulted lazily once.
        with patch("lfmapp.ui.icons._icon_file_index", return_value={}), patch(
            "lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon()
        ):
            icon = self.icons.app_icon("missing-name-that-is-not-cached")

        self.assertTrue(icon.isNull())

    def test_index_fallback_resolves_names_missing_from_theme(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp.write(svg.encode("utf-8"))
            tmp_path = tmp.name
        try:
            self.icons._ICON_FILE_INDEX = {"text-x-python": tmp_path}
            with patch("lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon()):
                icon = self.icons.app_icon("text-x-python")

            self.assertFalse(icon.isNull())
        finally:
            self.icons._ICON_FILE_INDEX = None
            Path(tmp_path).unlink(missing_ok=True)

    def test_discovery_lookup_uses_index_not_rglob(self):
        # Cold-startup performance guard: `_find_system_icon_file` (used only by
        # the one-time discovery) must resolve from the memoized index, never by
        # rglob-scanning the whole theme tree per name — that scan is what made
        # the first launch take 8-27s on large icon themes. If any rglob happens
        # here, the patch below raises.
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp.write(svg.encode("utf-8"))
            tmp_path = tmp.name
        try:
            self.icons._ICON_FILE_INDEX = {"go-previous": tmp_path}
            self.icons._ICON_PATH_CACHE.clear()
            with patch("pathlib.Path.rglob", side_effect=AssertionError("rglob used in discovery")):
                found = self.icons._find_system_icon_file("go-previous")
                miss = self.icons._find_system_icon_file("totally-absent-name-xyz")
            self.assertEqual(found, Path(tmp_path))
            self.assertIsNone(miss)
        finally:
            self.icons._ICON_FILE_INDEX = None
            Path(tmp_path).unlink(missing_ok=True)

    def test_initialize_icon_cache_loads_found_paths_and_known_misses(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp.write(svg.encode("utf-8"))
            tmp_path = tmp.name
        try:
            config = self._make_config()
            config._found["arrow-left"] = tmp_path
            config._misses.append("linux-file-manager")

            self.icons.initialize_icon_cache(config)

            self.assertEqual(self.icons._ICON_PATH_CACHE["arrow-left"], Path(tmp_path))
            self.assertIsNone(self.icons._ICON_PATH_CACHE["linux-file-manager"])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_discovery_persists_found_paths_and_misses(self):
        config = self._make_config()

        def fake_find(name):
            if name == "arrow-left":
                return Path("/usr/share/icons/example/arrow-left.svg")
            return None

        with patch("lfmapp.ui.icons._find_system_icon_file", side_effect=fake_find):
            self.icons.discover_system_icons(config)

        self.assertTrue(config.complete)
        self.assertEqual(config._found.get("arrow-left"), "/usr/share/icons/example/arrow-left.svg")
        self.assertIn("linux-file-manager", config._misses)
        candidates = self.icons._collect_icon_candidate_names()
        self.assertEqual(len(config._found) + len(config._misses), len(candidates))

    def test_candidate_names_cover_operation_and_archive_icons(self):
        """Regression: these names are used in the UI and must be included in
        the one-time discovery so the persisted fallback cache covers them."""
        candidates = set(self.icons._collect_icon_candidate_names())
        for name in (
            "view-refresh",
            "process-stop",
            "media-playback-pause",
            "media-playback-start",
            "archive-extract",
            "archive-insert",
            "package-x-generic",
        ):
            self.assertIn(name, candidates)

    def test_search_for_icon_path_persists_misses_for_self_healing(self):
        # A name the active theme lacks must be persisted as a miss so the next
        # launch seeds it via initialize_icon_cache and never rebuilds the
        # (expensive) whole-tree index for it again.
        config = self._make_config()
        self.icons._ICON_FILE_INDEX = {}  # index built but name absent
        self.icons._ICON_PATH_CACHE.clear()
        result = self.icons._search_for_icon_path("definitely-not-here", config)
        self.assertIsNone(result)
        self.assertIn("definitely-not-here", config._misses)
        # A later launch (seeded cache) resolves from memory without a rebuild.
        self.icons._ICON_PATH_CACHE.clear()
        self.icons.initialize_icon_cache(config)
        self.assertIsNone(self.icons._search_for_icon_path("definitely-not-here", config))
        self.icons._ICON_FILE_INDEX = None

    def test_pending_icon_searches_reflects_unresolved_names_only(self):
        config = self._make_config()
        # All candidates known as misses -> nothing pending (no re-scan on start).
        for name in self.icons._collect_icon_candidate_names():
            config._misses.append(name)
        self.icons.initialize_icon_cache(config)
        self.assertEqual(self.icons.pending_icon_searches(), [])

        # Unknown name is pending until resolved.
        self.icons._ICON_PATH_CACHE.clear()
        self.assertIn("arrow-left", self.icons.pending_icon_searches())

    def test_resolved_icon_cache_dropped_when_system_theme_changes(self):
        # Mirrors Thunar's theme "changed" hook: after a theme switch the cache
        # must be cleared so lookups follow the new system icon theme.
        with patch("lfmapp.ui.icons._current_theme_name", return_value="Theme-A"):
            self.icons._refresh_cache_on_theme_change()
        self.icons._ICON_CACHE["folder"] = QIcon()
        self.assertIn("folder", self.icons._ICON_CACHE)

        with patch("lfmapp.ui.icons._current_theme_name", return_value="Theme-B"):
            self.icons._refresh_cache_on_theme_change()

        self.assertEqual(self.icons._ICON_CACHE, {})
        self.assertEqual(self.icons._LAST_THEME_NAME, "Theme-B")

    def test_app_icon_uses_active_theme_first_then_persisted_path(self):
        # fromTheme (active theme) wins over the persisted path cache.
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp.write(svg.encode("utf-8"))
            tmp_path = tmp.name
        try:
            config = self._make_config()
            config._found["some-name"] = tmp_path
            self.icons.initialize_icon_cache(config)

            with patch("lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon(tmp_path)):
                icon = self.icons.app_icon("some-name", config=config)

            self.assertFalse(icon.isNull())
            self.assertIsNone(self.icons._ICON_PATH_CACHE.get("other-name"))
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class IconLoadingIsLockedTests(unittest.TestCase):
    """Guardrails for ADR-0002: system icons resolve through the theme engine.

    These are the "rule" that prevents reintroducing the 8-27s cold-startup
    regression (a startup scan of the icon trees). If they fail, restore the
    theme-engine approach — do NOT weaken the tests. See
    docs/adr/ADR-0002-system-icon-loading.md.
    """

    def test_startup_entry_point_does_not_scan_icon_trees(self):
        import inspect

        import lfmapp.app as app_module

        src = inspect.getsource(app_module.main)
        # The entry point must only restore persisted paths (non-scanning), and
        # must never call the one-time tree scan at startup.
        self.assertIn("initialize_icon_cache", src)
        self.assertNotIn("discover_system_icons", src)
        self.assertNotIn("pending_icon_searches", src)

    def test_themed_lookup_never_walks_icon_dirs(self):
        # The real-desktop case: the active theme provides the icon, so a
        # lookup must be satisfied by the theme engine alone — no file index,
        # no rglob, no os.walk. Any of those paths raises if touched.
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp.write(svg.encode("utf-8"))
            tmp_path = tmp.name
        try:
            import lfmapp.ui.icons as icons_module

            icons_module._ICON_CACHE.clear()
            icons_module._ICON_PATH_CACHE.clear()
            with patch(
                "lfmapp.ui.icons.QIcon.fromTheme", return_value=QIcon(tmp_path)
            ), patch(
                "lfmapp.ui.icons._icon_file_index",
                side_effect=AssertionError("theme lookup must not build the file index"),
            ), patch(
                "pathlib.Path.rglob",
                side_effect=AssertionError("theme lookup must not rglob"),
            ):
                icon = icons_module.app_icon("folder")
            self.assertFalse(icon.isNull())
        finally:
            icons_module._ICON_CACHE.clear()
            icons_module._ICON_PATH_CACHE.clear()
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
