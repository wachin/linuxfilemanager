"""Notification banner host for MainWindow (ROADMAP Phase 7.2).

Owns a thin vertical area near the top of the central widget where
``NotificationBanner`` rows stack.  Provides the single non-modal channel
the mixins use instead of blocking ``QMessageBox`` pop-ups for
informational messages, recoverable errors and — most importantly —
reversible-operation confirmations with an inline **Undo** action.

The area auto-hides when the last banner is dismissed, so it never leaves
empty space in the layout.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from lfmapp.ui.notification_banner import NotificationBanner


# Hard cap on simultaneously visible banners (oldest auto-dismissed beyond).
_MAX_VISIBLE = 4


class NotificationsMixin:
    # ─── Construction ──────────────────────────────────────────

    def build_notification_area(self, central_layout) -> None:
        """Create the (initially hidden) banner container above the views."""
        self._banner_host = QWidget(self)
        self._banners_layout = QVBoxLayout(self._banner_host)
        self._banners_layout.setContentsMargins(0, 0, 0, 0)
        self._banners_layout.setSpacing(4)
        self._banners_layout.addStretch(1)
        self._active_banners: list[NotificationBanner] = []
        # Insert just below the tab bar, above the splitter.
        central_layout.insertWidget(2, self._banner_host)
        self._banner_host.hide()

    # ─── Public API ────────────────────────────────────────────

    def show_notification(
        self,
        message: str,
        *,
        severity: str = "info",
        action_label: str | None = None,
        action_callback: Callable[[], None] | None = None,
        timeout_ms: int | None = None,
    ) -> NotificationBanner:
        """Show a banner and return it.

        ``action_callback`` (if given) runs when the action button is
        clicked.  ``timeout_ms`` of 0 keeps the banner until dismissed.
        """
        if not hasattr(self, "_banners_layout"):
            # Banner area not built yet (early call): fall back to the
            # status bar so no message is ever lost.
            self.statusBar().showMessage(message, timeout_ms or 5000)
            # Return a detached (parentless) banner that is never shown.
            banner = NotificationBanner(message, severity=severity)
            banner.setParent(None)
            return banner

        banner = NotificationBanner(
            message,
            severity=severity,
            action_label=action_label,
            timeout_ms=timeout_ms,
            parent=self._banner_host,
        )
        if action_callback is not None:
            banner.action_triggered.connect(action_callback)
        banner.dismissed.connect(lambda b=banner: self._remove_banner(b))

        # Add above the trailing stretch so newest is at the bottom.
        self._banners_layout.insertWidget(
            self._banners_layout.count() - 1, banner
        )
        banner.show()
        self._active_banners.append(banner)
        self._banner_host.show()

        # Enforce the visible cap.
        while len(self._active_banners) > _MAX_VISIBLE:
            oldest = self._active_banners[0]
            oldest.close()
            break

        return banner

    def show_undo_banner(
        self,
        message: str,
        undo_callback: Callable[[], None],
        *,
        action_label: str | None = None,
        timeout_ms: int = 8000,
    ) -> NotificationBanner:
        """Show a success banner offering an **Undo** action."""
        label = action_label or self.tr("Undo")
        return self.show_notification(
            message,
            severity="success",
            action_label=label,
            action_callback=undo_callback,
            timeout_ms=timeout_ms,
        )

    def show_info_banner(self, message: str, timeout_ms: int = 5000) -> NotificationBanner:
        return self.show_notification(message, severity="info", timeout_ms=timeout_ms)

    def show_success_banner(self, message: str, timeout_ms: int = 5000) -> NotificationBanner:
        return self.show_notification(message, severity="success", timeout_ms=timeout_ms)

    def show_warning_banner(self, message: str, timeout_ms: int = 7000) -> NotificationBanner:
        return self.show_notification(message, severity="warning", timeout_ms=timeout_ms)

    def show_error_banner(self, message: str, timeout_ms: int = 9000) -> NotificationBanner:
        return self.show_notification(message, severity="error", timeout_ms=timeout_ms)

    # ─── Internals ─────────────────────────────────────────────

    def _remove_banner(self, banner: NotificationBanner) -> None:
        if banner in self._active_banners:
            self._active_banners.remove(banner)
        try:
            self._banners_layout.removeWidget(banner)
        except Exception:
            pass
        banner.deleteLater()
        if not self._active_banners:
            self._banner_host.hide()

    def active_banner_count(self) -> int:
        """Number of banners currently shown (useful for tests/telemetry)."""
        return len(self._active_banners)
