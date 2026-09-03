"""Delegated copy/move tool service for linux-file-manager.

ROADMAP Phase 10.2: the file manager's native copy/move engine stays the
default; **Ultracopier** is an optional alternative for demanding transfers
(queue with pause/resume, speed limit, advanced collision handling).

CLI (verified on the reference system, ``ultracopier --help``):

- ``ultracopier cp <sources...> <destination>`` → copy
- ``ultracopier mv <sources...> <destination>`` → move
- when ``<destination>`` is ``?`` Ultracopier asks the user itself.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Sequence


class UltracopierBackend:
    """Builds and launches ``ultracopier cp|mv`` commands."""

    tool_id = "ultracopier"
    label = "Ultracopier"
    executable = "ultracopier"
    install_hint = "sudo apt install ultracopier"

    #: Destination placeholder that makes Ultracopier ask the user.
    ASK_DESTINATION = "?"

    def is_installed(self) -> bool:
        return shutil.which(self.executable) is not None

    @staticmethod
    def _transfer_command(
        verb: str, sources: Sequence[Path], destination: Path | str | None
    ) -> list[str]:
        if verb not in {"cp", "mv"}:
            raise ValueError(f"Unsupported Ultracopier verb: {verb}")
        source_args = [str(Path(src)) for src in sources]
        if not source_args:
            raise ValueError("Ultracopier transfer needs at least one source")
        destination_arg = (
            UltracopierBackend.ASK_DESTINATION
            if destination is None
            else str(destination)
        )
        return ["ultracopier", verb, *source_args, destination_arg]

    def copy_command(
        self, sources: Sequence[Path], destination: Path | str | None = None
    ) -> list[str]:
        return self._transfer_command("cp", sources, destination)

    def move_command(
        self, sources: Sequence[Path], destination: Path | str | None = None
    ) -> list[str]:
        return self._transfer_command("mv", sources, destination)


NATIVE_TOOL = "native"


class CopyToolService:
    """Selects between the native engine and the Ultracopier delegation."""

    def __init__(self, config=None, launcher=None, backend: UltracopierBackend | None = None):
        self.config = config
        self.backend = backend or UltracopierBackend()
        # Injectable for tests; defaults to subprocess.Popen detached.
        self._launcher = launcher

    # ─── Tool resolution ───────────────────────────────────────

    @property
    def tool_id(self) -> str:
        tool = ""
        if self.config is not None:
            getter = getattr(self.config, "copy_tool", None)
            if callable(getter):
                tool = str(getter() or "")
            else:
                tool = str(getattr(self.config, "data", {}).get("copy_tool", ""))
        return tool if tool in {NATIVE_TOOL, self.backend.tool_id} else NATIVE_TOOL

    def ultracopier_available(self) -> bool:
        return self.backend.is_installed()

    @property
    def delegate(self) -> bool:
        """True when copy/move should be delegated to Ultracopier."""
        return self.tool_id == self.backend.tool_id and self.ultracopier_available()

    # ─── Launch helpers ────────────────────────────────────────

    def _launch(self, command: list[str]) -> bool:
        if not command:
            return False
        launcher = self._launcher
        if launcher is None:
            def launcher(cmd):
                subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return True

        try:
            return bool(launcher(command))
        except (OSError, subprocess.SubprocessError, ValueError):
            return False

    # ─── Public operations ─────────────────────────────────────

    def copy(self, sources: Sequence[Path], destination: Path | str | None = None) -> bool:
        """Copy ``sources`` to ``destination`` (or ask in Ultracopier when None)."""
        try:
            command = self.backend.copy_command(sources, destination)
        except ValueError:
            return False
        return self._launch(command)

    def move(self, sources: Sequence[Path], destination: Path | str | None = None) -> bool:
        """Move ``sources`` to ``destination`` (or ask in Ultracopier when None)."""
        try:
            command = self.backend.move_command(sources, destination)
        except ValueError:
            return False
        return self._launch(command)
