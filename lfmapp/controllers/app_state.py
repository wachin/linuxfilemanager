"""Observable UI state model (Fase 1.3).

Widgets should read the current UI state from one place instead of querying
several services and rebuilding the same derived facts.  AppState is a small,
UI-agnostic observable store: it holds the state MainWindow already keeps as
scattered attributes (current path, selection summary, view mode, search
activity, operation counts) and notifies subscribers on change.

Surfaces (MainWindow) remain the only writers; controllers and services read
from it or subscribe.  Kept Qt-free so it can be unit-tested headless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from lfmapp.controllers.selection_controller import SelectionController, SelectionSummary

ChangeListener = Callable[[str], None]  # receives the changed key


@dataclass
class AppState:
    """Observable snapshot of the active UI state.

    Attributes are the source of truth; use the setters (or update()) so
    listeners fire.  start/stop provide a scoped listener API.
    """

    _path: Path | None = None
    _selection: SelectionSummary = field(default_factory=SelectionSummary)
    _view_mode: str = "details"
    _searching: bool = False
    _search_result_count: int | None = None
    _busy_operations: int = 0
    _hidden_files_shown: bool = False
    _listeners: dict[str, list[ChangeListener]] = field(default_factory=dict)

    # ── path ──────────────────────────────────────────────────
    @property
    def path(self) -> Path | None:
        return self._path

    def set_path(self, path: Path | None) -> None:
        if path is not None:
            path = Path(path).expanduser()
        if path == self._path:
            return
        self._path = path
        self._notify("path")

    # ── selection ─────────────────────────────────────────────
    @property
    def selection(self) -> SelectionSummary:
        return self._selection

    @property
    def selection_count(self) -> int:
        return self._selection.count

    def set_selection_paths(self, paths: list[Path]) -> None:
        summary = SelectionController.summarize(paths)
        if (
            summary.count == self._selection.count
            and summary.file_count == self._selection.file_count
            and summary.folder_count == self._selection.folder_count
        ):
            return
        self._selection = summary
        self._notify("selection")

    # ── view mode ─────────────────────────────────────────────
    @property
    def view_mode(self) -> str:
        return self._view_mode

    def set_view_mode(self, mode: str) -> None:
        if mode == self._view_mode:
            return
        self._view_mode = mode
        self._notify("view_mode")

    # ── search ────────────────────────────────────────────────
    @property
    def searching(self) -> bool:
        return self._searching

    def set_searching(self, active: bool, result_count: int | None = None) -> None:
        changed = active != self._searching
        if result_count is not None and result_count != self._search_result_count:
            self._search_result_count = result_count
            self._notify("search_results")
        if changed:
            self._searching = active
            self._notify("searching")

    @property
    def search_result_count(self) -> int | None:
        return self._search_result_count

    # ── operations (Fase 2 hooks) ─────────────────────────────
    @property
    def busy_operations(self) -> int:
        return self._busy_operations

    def operation_started(self) -> None:
        self._busy_operations += 1
        self._notify("operations")

    def operation_finished(self) -> None:
        if self._busy_operations > 0:
            self._busy_operations -= 1
            self._notify("operations")

    # ── hidden files ──────────────────────────────────────────
    @property
    def hidden_files_shown(self) -> bool:
        return self._hidden_files_shown

    def set_hidden_files_shown(self, shown: bool) -> None:
        if shown == self._hidden_files_shown:
            return
        self._hidden_files_shown = shown
        self._notify("hidden_files")

    # ── listeners ─────────────────────────────────────────────
    def subscribe(self, key: str, listener: ChangeListener) -> None:
        self._listeners.setdefault(key, []).append(listener)

    def unsubscribe(self, key: str, listener: ChangeListener) -> None:
        listeners = self._listeners.get(key)
        if listeners and listener in listeners:
            listeners.remove(listener)

    def _notify(self, key: str) -> None:
        for listener in list(self._listeners.get(key, ())):
            listener(key)


@dataclass
class LocationKind:
    """Classifier for where the UI currently is (Fase 1.3 namespace)."""

    scheme: str  # "filesystem" | "this-computer" | "home" | "quick-access" | ...
    path: Path | None = None


def classify_location(path: Path | None, xdg_home: Path) -> LocationKind:
    """Map a shown path to a logical location kind.

    The physical folders that the sidebar exposes (Quick Access members, home,
    XDG dirs, bookmarks) are still real filesystem paths; virtual namespaces
    will extend this classifier when collections/libraries/stored queries land.
    """
    if path is None:
        return LocationKind("this-computer")
    expanded = Path(path).expanduser()
    if expanded == Path.home():
        return LocationKind("home", expanded)
    if expanded == xdg_home:
        return LocationKind("home", expanded)
    try:
        if xdg_home in expanded.parents or expanded == xdg_home:
            return LocationKind("filesystem", expanded)
    except ValueError:
        pass
    return LocationKind("filesystem", expanded)
