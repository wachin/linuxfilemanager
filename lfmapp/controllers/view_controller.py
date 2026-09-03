"""View state policy controller (Fase 1.1).

Centralises the *policy* of per-folder view persistence that used to be
duplicated between go_to() (restore on navigation) and set_view_mode() (save
on change).  The controller is UI-agnostic: it decides *what* should be
restored/remembered given a folder and the config; the surfaces apply it to
the real widgets.
"""

from __future__ import annotations

from pathlib import Path

from lfmapp.ui.workspace import ViewMode


class ViewController:
    """Decides which view mode a folder should use and whether to remember it.

    The workspace itself owns the actual switching; this controller owns the
    "remember per folder / restore on navigation / clear" policy so it can be
    tested without a QMainWindow.  ``config`` only needs the four folder-view
    methods used here (get/set/clear/clear_all + remember_folder_view), so a
    lightweight fake works in tests.
    """

    def __init__(self, config=None) -> None:
        self.config = config

    @property
    def enabled(self) -> bool:
        """Read from config each time so hot changes stay in sync."""
        if self.config is None:
            return False
        try:
            return bool(self.config.remember_folder_view())
        except TypeError:
            return bool(self.config.remember_folder_view)

    def set_enabled(self, value: bool) -> None:
        if self.config is not None:
            self.config.set_remember_folder_view(bool(value))

    def view_to_restore(self, path: Path, fallback: str = "details") -> str:
        """The saved view name for a folder, or the fallback when absent."""
        if not self.enabled or path is None:
            return fallback
        try:
            saved = self.config.get_folder_view(str(path))
        except Exception:
            return fallback
        return saved or fallback

    def remember(self, path: Path | None, view_mode: ViewMode | str) -> None:
        """Persist the current view for a folder when remembering is on."""
        if not self.enabled or path is None:
            return
        name = view_mode.value if isinstance(view_mode, ViewMode) else str(view_mode)
        try:
            self.config.set_folder_view(str(path), name)
        except Exception:
            pass

    def clear(self, path: Path | None) -> None:
        if self.enabled and path is not None:
            try:
                self.config.clear_folder_view(str(path))
            except Exception:
                pass

    def clear_all(self) -> None:
        try:
            self.config.clear_all_folder_views()
        except Exception:
            pass

    @staticmethod
    def coerce(saved: str, fallback_mode: ViewMode) -> ViewMode:
        """Convert a saved view name to a ViewMode with a safe fallback."""
        return ViewMode.from_string(saved, fallback_mode)
