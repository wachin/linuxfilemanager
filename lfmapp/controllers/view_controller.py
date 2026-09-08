"""View state policy controller (Fase 1.1 / P2 folder format).

Centralises the *policy* of per-folder view persistence that used to be
duplicated between go_to() (restore on navigation) and set_view_mode() (save
on change).  The controller is UI-agnostic: it decides *what* should be
restored/remembered given a folder and the config; the surfaces apply it to
the real widgets.

Phase 7.3 / backlog P2 extends the remembered view *mode* to a complete
**folder format**: view mode + sort key/order + group key + icon grid size.
The format is a serializable dict (with a ``version``) stored per folder,
optionally inherited from the closest saved ancestor, and ignored entirely
when the user disables per-folder preferences.
"""

from __future__ import annotations

from pathlib import Path

from lfmapp.ui.workspace import ViewMode

FORMAT_VERSION = 1

# Sort/group keys the workspace understands (mirrors Workspace.sort_by/group_by).
_SORT_KEYS = {"name", "size", "type", "modified"}
_GROUP_KEYS = {"none", "name", "type", "size", "modified"}
_GRID_KEYS = {"small", "medium", "large"}
_VIEW_KEYS = {"icon", "list", "details", "compact", "flat"}
# Degrees of the flat view (lfmapp.services.flat_view_service.FlatViewMode).
_FLAT_MODES = {"mixed", "files_only", "grouped"}


class ViewController:
    """Decides which view mode a folder should use and whether to remember it.

    The workspace itself owns the actual switching; this controller owns the
    "remember per folder / restore on navigation / clear" policy so it can be
    tested without a QMainWindow.  ``config`` only needs the folder-view and
    folder-format methods used here, so a lightweight fake works in tests.
    """

    def __init__(self, config=None) -> None:
        self.config = config

    # ── Enablement ─────────────────────────────────────────────

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

    @property
    def per_folder_enabled(self) -> bool:
        """Whether per-folder preferences apply at all (global ignore flag)."""
        try:
            return not bool(self.config.data.get("ignore_per_folder_view_preferences", False))
        except AttributeError:
            return True

    @property
    def inherit_from_parent(self) -> bool:
        try:
            return bool(self.config.folder_format_inherit_from_parent)
        except AttributeError:
            return True

    def set_inherit_from_parent(self, value: bool) -> None:
        setter = getattr(self.config, "set_folder_format_inherit_from_parent", None)
        if setter is not None:
            setter(bool(value))

    # ── View mode (legacy, kept for compatibility) ──────────────

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
                self.config.clear_folder_format(str(path))
            except Exception:
                pass

    def clear_all(self) -> None:
        try:
            self.config.clear_all_folder_views()
            clear_formats = getattr(self.config, "clear_all_folder_formats", None)
            if clear_formats is not None:
                clear_formats()
        except Exception:
            pass

    # ── Folder format (P2) ──────────────────────────────────────

    @staticmethod
    def sanitize_format(fmt: dict | None) -> dict | None:
        """Validate/copy a format dict; return None when unusable.

        Unknown keys are dropped so a corrupt or foreign entry can never
        break the workspace when applied.
        """
        if not isinstance(fmt, dict):
            return None
        if fmt.get("version") != FORMAT_VERSION:
            return None
        clean = {"version": FORMAT_VERSION}
        if isinstance(fmt.get("view"), str) and fmt["view"] in _VIEW_KEYS:
            clean["view"] = fmt["view"]
        if isinstance(fmt.get("sort"), str) and fmt["sort"] in _SORT_KEYS:
            clean["sort"] = fmt["sort"]
        if isinstance(fmt.get("group"), str) and fmt["group"] in _GROUP_KEYS:
            clean["group"] = fmt["group"]
        if isinstance(fmt.get("grid"), str) and fmt["grid"] in _GRID_KEYS:
            clean["grid"] = fmt["grid"]
        if isinstance(fmt.get("flat_mode"), str) and fmt["flat_mode"] in _FLAT_MODES:
            clean["flat_mode"] = fmt["flat_mode"]
        return clean

    def remember_format(self, path: Path | None, view_mode: ViewMode | str,
                        sort_key: str, group_key: str, grid_size: str,
                        flat_mode: str | None = None) -> None:
        """Persist the complete visual format of a folder (when enabled)."""
        if not self.enabled or not self.per_folder_enabled or path is None:
            return
        view = view_mode.value if isinstance(view_mode, ViewMode) else str(view_mode)
        raw = {
            "version": FORMAT_VERSION,
            "view": view,
            "sort": sort_key,
            "group": group_key,
            "grid": grid_size,
        }
        if flat_mode is not None:
            raw["flat_mode"] = flat_mode
        fmt = self.sanitize_format(raw)
        if fmt is None:
            return
        try:
            self.config.set_folder_format(str(path), fmt)
            # Keep the legacy view store in sync so both surfaces agree.
            self.config.set_folder_view(str(path), fmt.get("view"))
        except Exception:
            pass

    def format_to_restore(self, path: Path | None) -> dict | None:
        """Resolve the folder format for a path.

        Resolution order:
        1. an exact format saved for the path;
        2. when inheritance is on, the closest saved ancestor's format;
        3. ``None`` (the caller keeps its current/global defaults).
        """
        if not self.enabled or not self.per_folder_enabled or path is None:
            return None
        try:
            return self._resolve_format(Path(path))
        except Exception:
            return None

    def _resolve_format(self, path: Path) -> dict | None:
        exact = self.sanitize_format(self.config.get_folder_format(str(path)))
        if exact is not None:
            return exact
        if not self.inherit_from_parent:
            return None
        # Walk upward looking for the closest saved ancestor format.
        current = Path(path).parent
        root = Path(path).anchor or None
        while current != root and str(current) not in ("", "/"):
            inherited = self.sanitize_format(
                self.config.get_folder_format(str(current))
            )
            if inherited is not None:
                return inherited
            if current.parent == current:
                break
            current = current.parent
        return None

    @staticmethod
    def coerce(saved: str, fallback_mode: ViewMode) -> ViewMode:
        """Convert a saved view name to a ViewMode with a safe fallback."""
        return ViewMode.from_string(saved, fallback_mode)
