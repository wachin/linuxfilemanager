"""Controllers package: logic extracted from MainWindow.

Each controller owns one concern (navigation history, selection state, file
actions, view state...) and is testable without a full QMainWindow.  Fase 1.1
migrates MainWindow methods here progressively; surfaces keep thin delegates.
"""

from .app_state import AppState, classify_location
from .navigation_controller import NavigationController
from .search_controller import SearchController, SearchOutcome
from .selection_controller import SelectionController, SelectionCriteria, SelectionSummary
from .shortcut_map import CommandRecord, ShortcutMap, normalize_shortcut
from .view_controller import ViewController

__all__ = [
    "AppState",
    "NavigationController",
    "SearchController",
    "SearchOutcome",
    "SelectionController",
    "SelectionCriteria",
    "SelectionSummary",
    "CommandRecord",
    "ShortcutMap",
    "normalize_shortcut",
    "ViewController",
    "classify_location",
]
