"""Reusable non-modal notification banner (ROADMAP Phase 7.1 component).

A banner is a slim horizontal strip that shows a short message with a
severity icon, an optional action button (e.g. **Undo**) and a close
button.  It is the house replacement for informational `QMessageBox`
pop-ups and for reversible-operation confirmations: instead of blocking
the user with a modal, it slides in, offers the one action that matters
and dismisses itself after a timeout (paused while hovered so the user
can read or click it).

Severities follow freedesktop icon names so they degrade gracefully when
a theme lacks a glyph.
"""

from __future__ import annotations

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from lfmapp.ui.icons import app_icon


# Severity → (theme icon names, background tint, default timeout ms).
_SEVERITY_STYLE = {
    "info": (
        ("dialog-information", "information", "help-about"),
        "#2d5a7b",
        5000,
    ),
    "success": (
        ("emblem-default", "dialog-ok", "object-select"),
        "#2e7d32",
        5000,
    ),
    "warning": (
        ("dialog-warning", "emblem-important", "sign-orange"),
        "#9a6b00",
        7000,
    ),
    "error": (
        ("dialog-error", "process-stop", "emblem-unreadable"),
        "#a31515",
        9000,
    ),
}


class NotificationBanner(QFrame):
    """A single dismissible banner row.

    Signals
    -------
    action_triggered()
        Emitted when the optional action button is clicked (afterwards the
        banner dismisses itself).
    dismissed()
        Emitted when the banner is closed by the timeout or the close
        button.
    """

    action_triggered = pyqtSignal()
    dismissed = pyqtSignal()

    def __init__(
        self,
        message: str,
        *,
        severity: str = "info",
        action_label: str | None = None,
        timeout_ms: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("notificationBanner")
        icons, tint, default_timeout = _SEVERITY_STYLE.get(
            severity, _SEVERITY_STYLE["info"]
        )
        self._timeout_ms = default_timeout if timeout_ms is None else timeout_ms

        self.setStyleSheet(
            f"QFrame#notificationBanner {{ background: {tint}; color: white; "
            "border-radius: 6px; }"
            "QLabel { color: white; }"
            "QPushButton { background: rgba(255,255,255,0.18); color: white; "
            "border: none; border-radius: 4px; padding: 3px 10px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.32); }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(8)

        self.icon_label = QLabel(self)
        self.icon_label.setPixmap(
            app_icon(*icons).pixmap(16, 16)
        )
        layout.addWidget(self.icon_label)

        self.message_label = QLabel(message, self)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)

        self.action_button = None
        if action_label:
            self.action_button = QPushButton(action_label, self)
            self.action_button.clicked.connect(self._on_action_clicked)
            layout.addWidget(self.action_button)

        self.close_button = QPushButton("\u2715", self)
        self.close_button.setFixedWidth(22)
        self.close_button.setToolTip(self.tr("Dismiss"))
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)

        # Auto-dismiss timer; 0 disables it (permanent until dismissed).
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)
        if self._timeout_ms > 0:
            self._timer.start(self._timeout_ms)

    # -- interaction --------------------------------------------------------

    def _on_action_clicked(self) -> None:
        self.action_triggered.emit()
        self.close()

    def reset_timeout(self) -> None:
        """(Re)start the auto-dismiss countdown from the configured timeout."""
        if self._timeout_ms > 0:
            self._timer.start(self._timeout_ms)

    # Pause the countdown while the pointer is over the banner so the user
    # has time to read or act; resume when it leaves.
    def enterEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._timeout_ms > 0:
            self._timer.start(self._timeout_ms // 2)
        super().leaveEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.dismissed.emit()
        super().closeEvent(event)
