"""Search lifecycle controller (Fase 1.1).

MainWindow currently owns the whole search lifecycle inline: cancelling the
previous thread, deciding indexed vs threaded search, accumulating results,
and reporting completion.  SearchController extracts that orchestration so it
can be reasoned about and tested without a QMainWindow.  The controller is
Qt-adjacent only through SearchThread (a QThread from lfmapp.services); all
state transitions and policy live here.

The controller never touches widgets: it emits outcomes through plain
callbacks that MainWindow wires to the preview panel / status bar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from lfmapp.services.search_service import SearchFilters, SearchThread


@dataclass
class SearchOutcome:
    """Callbacks invoked by the controller during a search lifecycle.

    All callbacks are optional; MainWindow supplies the ones it cares about.
    """

    on_result: Callable[[Path], None] | None = None
    on_finished: Callable[[int], None] | None = None
    on_cancel: Callable[[], None] | None = None


class SearchController:
    """Starts, cancels and tracks one search at a time.

    Policy decisions (previously spread across MainWindow methods):
    - An empty query with no active filters does nothing.
    - Starting a new search cancels a still-running previous one.
    - When the text index is enabled and no filters are active, the search is
      answered from the index instead of a threaded scan.
    """

    def __init__(
        self,
        *,
        text_index_enabled_provider: Callable[[], bool] = lambda: False,
        index_search: Callable[[str, Path], list[Path]] | None = None,
    ) -> None:
        self._text_index_enabled = text_index_enabled_provider
        self._index_search = index_search
        self._thread: SearchThread | None = None
        self.results: list[Path] = []
        self.filters: SearchFilters = SearchFilters()
        self.query: str = ""
        self.outcome: SearchOutcome = SearchOutcome()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(
        self,
        query: str,
        filters: SearchFilters | None = None,
        *,
        root: Path,
        outcome: SearchOutcome | None = None,
    ) -> bool:
        """Begin a search; returns False when there is nothing to search."""
        query = (query or "").strip()
        filters = filters or SearchFilters()
        if not query and not filters.is_active():
            return False
        if root is None:
            return False
        if outcome is not None:
            self.outcome = outcome
        self._cancel_running()
        self.query = query
        self.filters = filters
        self.results = []

        # Indexed search path (no filters: text index answers directly).
        if self._text_index_enabled() and not filters.is_active() and self._index_search is not None:
            try:
                found = self._index_search(query, root)
            except Exception:
                found = []
            found = [Path(p) for p in found]
            self.results = list(found)
            if self.outcome.on_result is not None:
                for path in found:
                    self.outcome.on_result(path)
            if self.outcome.on_finished is not None:
                self.outcome.on_finished(len(self.results))
            return True

        self._thread = SearchThread(
            root, query, recursive=False, filters=filters
        )
        self._thread.found.connect(
            lambda path, t=self._thread: self._on_found(t, path)
        )
        self._thread.finished.connect(
            lambda count, t=self._thread: self._on_finished(t, count)
        )
        self._thread.start()
        return True

    def cancel(self) -> None:
        """Cancel any running search (results already found are kept)."""
        self._cancel_running()
        if self.outcome.on_cancel is not None:
            self.outcome.on_cancel()

    def _cancel_running(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            try:
                self._thread.stop()
                self._thread.wait()
            except RuntimeError:
                # Thread may have been destroyed already; nothing left to do.
                pass
        self._thread = None

    def _on_found(self, thread, path) -> None:
        # Ignore results emitted by a previous search that was cancelled.
        if thread is not self._thread:
            return
        self.results.append(Path(path))
        if self.outcome.on_result is not None:
            self.outcome.on_result(Path(path))

    def _on_finished(self, thread, count: int) -> None:
        if thread is not self._thread:
            return
        if self.outcome.on_finished is not None:
            self.outcome.on_finished(count)
