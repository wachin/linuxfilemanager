"""Terminal service for linux-file-manager.

Provides functionality to:
- Detect available terminal emulators on the system
- Open a terminal at a specific path
- Store and retrieve user's preferred terminal
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from lfmapp.core.config import Config


class TerminalService:
    """Service for managing terminal emulator operations."""

    # Common terminal emulators and their command-line arguments to open in a directory
    TERMINAL_EMULATORS: Dict[str, List[str]] = {
        "gnome-terminal": ["--working-directory="],
        "konsole": ["--workdir", ""],
        "xfce4-terminal": ["--working-directory="],
        "mate-terminal": ["--working-directory="],
        "lxterminal": ["--working-directory="],
        "xterm": ["-e", "cd "],
        "urxvt": ["-e", "cd "],
        "rxvt": ["-e", "cd "],
        "terminator": ["--working-directory="],
        "tilix": ["--working-directory="],
        "alacritty": ["--working-directory="],
        "kitty": ["--directory="],
        "wezterm": ["start", "--cwd", ""],
        "foot": ["--working-directory="],
        "deepin-terminal": ["--work-directory="],
        "qterminal": ["--workdir", ""],
        "lxqt-terminal": ["--workdir", ""],
        "eterm": ["-e", "cd "],
        "mlterm": ["--working-directory="],
        "sakura": ["--directory="],
        "guake": ["-n", "", "--new-tab-with-cwd="],
        "yakuake": ["-e", "cd "],
        "cool-retro-term": ["--workdir", ""],
    }
    
    # Default terminal window size (columns x rows)
    DEFAULT_TERMINAL_SIZE = "80x24"

    def __init__(self):
        self.config = Config()
        self._available_terminals: Optional[List[str]] = None

    @property
    def available_terminals(self) -> List[str]:
        """Get list of available terminal emulators on the system."""
        if self._available_terminals is None:
            self._available_terminals = self._detect_terminals()
        return self._available_terminals

    def _detect_terminals(self) -> List[str]:
        """Detect which terminal emulators are installed on the system."""
        available = []
        for terminal in self.TERMINAL_EMULATORS:
            if shutil.which(terminal):
                available.append(terminal)
        return sorted(available)

    @property
    def preferred_terminal(self) -> Optional[str]:
        """Get the user's preferred terminal emulator."""
        terminal = self.config.data.get("preferred_terminal")
        if terminal and terminal in self.available_terminals:
            return terminal
        # If no preferred terminal set or it's not available, return the first available
        if self.available_terminals:
            return self.available_terminals[0]
        return None

    def set_preferred_terminal(self, terminal: str) -> bool:
        """Set the user's preferred terminal emulator.

        Args:
            terminal: Name of the terminal emulator

        Returns:
            True if successful, False if terminal is not available
        """
        if terminal not in self.available_terminals:
            return False
        self.config.data["preferred_terminal"] = terminal
        self.config.save()
        return True

    def open_terminal(self, path: Path, terminal: Optional[str] = None) -> bool:
        """Open a terminal emulator at the specified path.

        Args:
            path: Directory path where terminal should open
            terminal: Terminal emulator to use (None for preferred)

        Returns:
            True if terminal was launched successfully, False otherwise
        """
        if not path or not path.exists():
            return False

        if not path.is_dir():
            path = path.parent

        terminal = terminal or self.preferred_terminal
        if not terminal:
            return False

        if terminal not in self.available_terminals:
            return False

        args = self.TERMINAL_EMULATORS.get(terminal, [])
        if not args:
            return False

        try:
            # Build command based on terminal's argument pattern
            if terminal in ["xterm", "urxvt", "rxvt", "eterm", "yakuake"]:
                # These terminals need a shell command
                cmd = [terminal, "-geometry", self.DEFAULT_TERMINAL_SIZE, "-e", f"cd '{path}' && exec $SHELL"]
            else:
                # Most terminals accept a directory argument directly
                cmd = [terminal]
                
                # Add window size for terminals that support it
                if terminal in ["konsole", "xfce4-terminal", "mate-terminal", "terminator", "tilix"]:
                    # These terminals support --geometry or similar
                    cmd.extend(["--geometry", self.DEFAULT_TERMINAL_SIZE])
                elif terminal in ["gnome-terminal"]:
                    # gnome-terminal uses --geometry
                    cmd.extend(["--geometry", self.DEFAULT_TERMINAL_SIZE])
                elif terminal in ["alacritty"]:
                    # alacritty uses --dimensions
                    cols, rows = self.DEFAULT_TERMINAL_SIZE.split("x")
                    cmd.extend(["--dimensions", f"{cols},{rows}"])
                elif terminal in ["kitty"]:
                    # kitty uses --override
                    cols, rows = self.DEFAULT_TERMINAL_SIZE.split("x")
                    cmd.extend(["--override", f"initial_window_width={cols}c", "--override", f"initial_window_height={rows}c"])
                
                if len(args) == 1:
                    # Single argument with directory appended
                    cmd.append(args[0] + str(path))
                elif len(args) == 2:
                    # Two arguments with directory in between
                    cmd.extend([args[0], str(path), args[1]])
                else:
                    # Fallback: try to pass directory as argument
                    cmd.append(str(path))

            # Launch terminal in background using subprocess
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )
            return True
        except Exception:
            return False

    def refresh_terminals(self):
        """Refresh the list of available terminals."""
        self._available_terminals = None
