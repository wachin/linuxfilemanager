"""Navigation history controller.

Owns the back/forward history stack that MainWindow currently keeps as plain
attributes (``self.history`` / ``self.history_index``).  Extracted so the
stack semantics — truncation of the forward list on new navigation, bounds
checking for back/forward, serializable state per tab — live in one testable
place without a QMainWindow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NavigationController:
    """Back/forward history for one navigation context (window or tab).

    Mirrors the semantics currently implemented in MainWindow:

    - :meth:`navigate_to` appends a new location and clears any forward
      history (standard "new navigation resets redo" behaviour).
    - :meth:`back` / :meth:`forward` move within the stack without recording.
    """

    history: list[Path] = field(default_factory=list)
    index: int = -1

    @property
    def current(self) -> Path | None:
        if 0 <= self.index < len(self.history):
            return self.history[self.index]
        return None

    @property
    def can_go_back(self) -> bool:
        return self.index > 0

    @property
    def can_go_forward(self) -> bool:
        return self.index >= 0 and self.index < len(self.history) - 1

    def navigate_to(self, path: Path) -> bool:
        """Record a navigation.  Returns True when the stack changed."""
        path = Path(path).expanduser()
        # If we are not at the tip of history, drop the forward entries.
        if self.index >= 0 and self.index < len(self.history) - 1:
            self.history = self.history[: self.index + 1]
        if not self.history or self.history[self.index] != path:
            self.history.append(path)
            self.index = len(self.history) - 1
            return True
        return False

    def back(self) -> Path | None:
        """Move one step back; returns the target or None at the boundary."""
        if not self.can_go_back:
            return None
        self.index -= 1
        return self.history[self.index]

    def forward(self) -> Path | None:
        """Move one step forward; returns the target or None at the tip."""
        if not self.can_go_forward:
            return None
        self.index += 1
        return self.history[self.index]

    def go_up_from(self, current: Path | None) -> Path | None:
        """Parent of a location, or None when already at the filesystem root."""
        if current is None:
            return None
        current = Path(current).expanduser()
        if current.parent == current:
            return None
        return current.parent

    # ── Serialization for per-tab state ───────────────────────

    def state(self) -> dict:
        """Serializable snapshot used by MainWindow per-tab persistence."""
        return {
            "history": [str(path) for path in self.history],
            "history_index": self.index,
        }

    @classmethod
    def from_state(cls, state: dict | None) -> "NavigationController":
        if not state:
            return cls()
        raw_history = state.get("history") or []
        return cls(
            history=[Path(item) for item in raw_history],
            index=int(state.get("history_index", -1)),
        )
