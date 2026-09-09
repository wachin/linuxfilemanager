"""Tests for the non-modal notification banners (backlog P2, Phase 7.1/7.2).

Covers:
- NotificationBanner widget: message, action button + signal, dismiss signal,
  timeout=0 (permanent), close button.
- NotificationsMixin via MainWindow: show_notification returns a banner, the
  host area shows/hides with the banner count, the Undo banner wires the
  callback, and the visible-count cap is enforced.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import lfmapp.core.config as config_module
from lfmapp.ui.notification_banner import NotificationBanner

_APP = None


def ensure_qapplication():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app


# ---------------------------------------------------------------------------
# Widget tests (no MainWindow needed)
# ---------------------------------------------------------------------------

class NotificationBannerWidgetTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()

    def test_message_is_set(self):
        b = NotificationBanner("Hello world")
        self.assertEqual(b.message_label.text(), "Hello world")

    def test_no_action_button_by_default(self):
        b = NotificationBanner("Plain info")
        self.assertIsNone(b.action_button)

    def test_action_button_present_when_labelled(self):
        b = NotificationBanner("Did a thing", action_label="Undo")
        self.assertIsNotNone(b.action_button)
        self.assertEqual(b.action_button.text(), "Undo")

    def test_action_button_emits_action_and_dismiss(self):
        b = NotificationBanner("Did a thing", action_label="Undo")
        fired = []
        dismissed = []
        b.action_triggered.connect(lambda: fired.append(1))
        b.dismissed.connect(lambda: dismissed.append(1))
        b.action_button.click()
        self.assertEqual(fired, [1])
        # Clicking the action also closes the banner (emits dismissed).
        self.assertEqual(dismissed, [1])

    def test_close_button_emits_dismissed(self):
        b = NotificationBanner("Close me")
        dismissed = []
        b.dismissed.connect(lambda: dismissed.append(1))
        b.close_button.click()
        self.assertEqual(dismissed, [1])

    def test_timeout_zero_is_permanent(self):
        b = NotificationBanner("Stay", timeout_ms=0)
        self.assertFalse(b._timer.isActive())

    def test_timeout_positive_starts_timer(self):
        b = NotificationBanner("Go away", timeout_ms=5000)
        self.assertTrue(b._timer.isActive())

    def test_severities_are_accepted(self):
        for sev in ("info", "success", "warning", "error"):
            b = NotificationBanner("m", severity=sev)
            self.assertIsInstance(b, NotificationBanner)


# ---------------------------------------------------------------------------
# Mixin tests (via MainWindow)
# ---------------------------------------------------------------------------

class NotificationsMixinTests(unittest.TestCase):
    def setUp(self):
        ensure_qapplication()
        self._tmp = tempfile.mkdtemp()
        config_module.CONFIG_DIR = Path(self._tmp)
        config_module.CONFIG_FILE = Path(self._tmp) / "config.json"
        from lfmapp.core.config import Config
        self.config = Config()
        self.config.data["first_run_done"] = True
        from lfmapp.ui.main_window import MainWindow
        self.window = MainWindow(self.config)
        QApplication.processEvents()

    def tearDown(self):
        self.window.close()
        QApplication.processEvents()
        config_module.CONFIG_DIR = Path(os.path.expanduser("~/.local/share/linux-file-manager"))
        config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"

    def test_host_area_hidden_initially(self):
        self.assertTrue(self.window._banner_host.isHidden())

    def test_show_notification_returns_banner(self):
        b = self.window.show_notification("Something happened")
        self.assertIsInstance(b, NotificationBanner)
        self.assertEqual(self.window.active_banner_count(), 1)

    def test_host_becomes_visible(self):
        self.window.show_notification("Now visible")
        self.assertFalse(self.window._banner_host.isHidden())

    def test_show_info_success_warning_error(self):
        for method in ("show_info_banner", "show_success_banner",
                       "show_warning_banner", "show_error_banner"):
            b = getattr(self.window, method)("m")
            self.assertIsInstance(b, NotificationBanner)
        self.assertEqual(self.window.active_banner_count(), 4)

    def test_undo_banner_wires_callback(self):
        called = []
        b = self.window.show_undo_banner("Renamed file", lambda: called.append(1))
        self.assertIsNotNone(b.action_button)
        self.assertEqual(b.action_button.text(), "Undo")
        b.action_button.click()
        self.assertEqual(called, [1])

    def test_dismiss_removes_and_hides_host(self):
        b = self.window.show_notification("Will dismiss")
        self.assertEqual(self.window.active_banner_count(), 1)
        b.close()
        QApplication.processEvents()
        self.assertEqual(self.window.active_banner_count(), 0)
        self.assertTrue(self.window._banner_host.isHidden())

    def test_max_visible_cap(self):
        for i in range(6):
            self.window.show_notification(f"m{i}", timeout_ms=0)
        # Cap is 4; oldest auto-closed when exceeded.
        self.assertLessEqual(self.window.active_banner_count(), 4)


if __name__ == "__main__":
    unittest.main()
