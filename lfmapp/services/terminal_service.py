"""Terminal service for linux-file-manager.

Provides functionality to:
- detect available terminal emulators on the system
- open a terminal at a specific path without forcing window state
- store and retrieve the user's preferred terminal
"""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from lfmapp.core.config import Config


class TerminalService:
    """Service for managing terminal emulator operations."""

    # Only use simple cwd-aware launch patterns. Do not force geometry,
    # maximized, or fullscreen state for external terminal windows.
    TERMINAL_COMMANDS: dict[str, list[str]] = {
        "konsole": ["--workdir"],
        "qterminal": ["--workdir"],
        "xfce4-terminal": ["--working-directory"],
        "gnome-terminal": ["--working-directory"],
        "mate-terminal": ["--working-directory"],
        "lxterminal": ["--working-directory"],
        "lxqt-terminal": ["--workdir"],
        "x-terminal-emulator": [],
    }

    PREFERRED_TERMINAL_ORDER = [
        "konsole",
        "qterminal",
        "xfce4-terminal",
        "gnome-terminal",
        "mate-terminal",
        "lxterminal",
        "lxqt-terminal",
        "x-terminal-emulator",
    ]

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self._available_terminals: Optional[list[str]] = None

    @property
    def available_terminals(self) -> list[str]:
        """Get terminal emulators detected on the system in preferred order."""
        if self._available_terminals is None:
            self._available_terminals = self._detect_terminals()
        return self._available_terminals

    def _detect_terminals(self) -> list[str]:
        available = []
        for terminal in self.PREFERRED_TERMINAL_ORDER:
            if shutil.which(terminal):
                available.append(terminal)
        return available

    @property
    def preferred_terminal(self) -> Optional[str]:
        """Get the configured terminal, or the first supported installed one."""
        terminal = self.config.data.get("preferred_terminal")
        if terminal and terminal in self.available_terminals:
            return terminal
        if self.available_terminals:
            return self.available_terminals[0]
        return None

    def set_preferred_terminal(self, terminal: str) -> bool:
        if terminal not in self.available_terminals:
            return False
        self.config.data["preferred_terminal"] = terminal
        self.config.save()
        return True

    @staticmethod
    def _normalize_launch_path(path: Path) -> Path | None:
        if not path:
            return None
        candidate = Path(path)
        if not candidate.exists():
            return None
        if candidate.is_file():
            candidate = candidate.parent
        if not candidate.is_dir():
            return None
        return candidate

    def _build_command(self, terminal: str, path: Path) -> list[str]:
        args = self.TERMINAL_COMMANDS.get(terminal)
        if args is None:
            raise ValueError(f"Unsupported terminal: {terminal}")
        if not args:
            return [terminal]
        return [terminal, *args, str(path)]

    def open_terminal(self, path: Path, terminal: Optional[str] = None) -> bool:
        """Open a terminal in the given directory without forcing window state."""
        normalized_path = self._normalize_launch_path(path)
        if normalized_path is None:
            return False

        terminal_name = terminal or self.preferred_terminal
        if not terminal_name or terminal_name not in self.available_terminals:
            return False

        try:
            cmd = self._build_command(terminal_name, normalized_path)
            subprocess.Popen(
                cmd,
                cwd=str(normalized_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            return False

    def refresh_terminals(self):
        self._available_terminals = None
