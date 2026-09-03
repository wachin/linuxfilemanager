"""Delegated archive tool service for linux-file-manager.

Product decision (ROADMAP Phase 10.1): compression and extraction are not
performed by the file manager's internal code but by an external desktop
archiver chosen by the user. This module abstracts the active tool and
implements two interchangeable backends:

- ``ArkBackend`` → KDE Ark (``ark`` CLI, default)
- ``PeaZipBackend`` → PeaZip (``peazip`` CLI)

Both backends build the real command lines verified on the reference
system and launch them detached in the background, so the UI never blocks
and the file manager's internal ``extractor_service`` is no longer exposed
on any menu surface.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Sequence


class ArchiveToolBackend:
    """Base interface for an external archive tool backend."""

    tool_id: str = ""
    label: str = ""
    executable: str = ""
    install_hint: str = ""

    def is_installed(self) -> bool:
        return shutil.which(self.executable) is not None

    # ─── Command builders ──────────────────────────────────────

    def open_command(self, path: Path) -> list[str]:
        raise NotImplementedError

    def extract_here_command(self, path: Path) -> list[str]:
        raise NotImplementedError

    def extract_into_new_folder_command(self, path: Path) -> list[str]:
        raise NotImplementedError

    def extract_to_command(self, path: Path, destination: Path | None) -> list[str]:
        """Extract into a destination.

        Backends with their own destination dialog (PeaZip) may ignore
        ``destination``; others (Ark) receive the user-chosen directory.
        """
        raise NotImplementedError

    def create_archive_command(self, paths: Sequence[Path]) -> list[str]:
        """Interactive 'add to archive…' command (tool asks for the target)."""
        raise NotImplementedError

    def quick_add_command(self, paths: Sequence[Path], target: Path) -> list[str]:
        """Non-interactive add of ``paths`` into a new archive at ``target``."""
        raise NotImplementedError

    def test_command(self, path: Path) -> list[str] | None:
        """Integrity test command, or ``None`` when the tool cannot test."""
        return None

    def needs_destination_arg(self) -> bool:
        """True when extract_to requires the file manager to ask for a folder."""
        return True


class ArkBackend(ArchiveToolBackend):
    """KDE Ark backend (see ROADMAP 10.1.1 for the verified CLI)."""

    tool_id = "ark"
    label = "Ark"
    executable = "ark"
    install_hint = "sudo apt install ark"

    def open_command(self, path: Path) -> list[str]:
        return [self.executable, str(path)]

    def extract_here_command(self, path: Path) -> list[str]:
        return [self.executable, "-b", str(path)]

    def extract_into_new_folder_command(self, path: Path) -> list[str]:
        return [self.executable, "-b", "-a", str(path)]

    def extract_to_command(self, path: Path, destination: Path | None) -> list[str]:
        command = [self.executable, "-b", str(path)]
        if destination is not None:
            command += ["-o", str(destination)]
        return command

    def create_archive_command(self, paths: Sequence[Path]) -> list[str]:
        return [self.executable, "-c", *[str(p) for p in paths]]

    def quick_add_command(self, paths: Sequence[Path], target: Path) -> list[str]:
        return [self.executable, "-t", str(target), *[str(p) for p in paths]]


class PeaZipBackend(ArchiveToolBackend):
    """PeaZip backend (command table from its KDE service menu)."""

    tool_id = "peazip"
    label = "PeaZip"
    executable = "peazip"
    install_hint = "sudo apt install peazip"

    QUICK_ADD_FLAGS = {
        "7z": "-add27z",
        "zip": "-add2zip",
        "gzip": "-add2gzip",
    }

    def open_command(self, path: Path) -> list[str]:
        return [self.executable, "-ext2browse", str(path)]

    def extract_here_command(self, path: Path) -> list[str]:
        return [self.executable, "-ext2here", str(path)]

    def extract_into_new_folder_command(self, path: Path) -> list[str]:
        return [self.executable, "-ext2folder", str(path)]

    def extract_to_command(self, path: Path, destination: Path | None) -> list[str]:
        # PeaZip shows its own full extraction dialog with destination choice.
        return [self.executable, "-ext2full", str(path)]

    def create_archive_command(self, paths: Sequence[Path]) -> list[str]:
        return [self.executable, "-add2archive", *[str(p) for p in paths]]

    def quick_add_command(self, paths: Sequence[Path], target: Path) -> list[str]:
        fmt = target.suffix.lstrip(".").lower() or "zip"
        flag = self.QUICK_ADD_FLAGS.get(fmt, "-add2zip")
        return [self.executable, flag, *[str(p) for p in paths]]

    def test_command(self, path: Path) -> list[str] | None:
        return [self.executable, "-ext2test", str(path)]

    def needs_destination_arg(self) -> bool:
        return False


BACKENDS: dict[str, type[ArchiveToolBackend]] = {
    ArkBackend.tool_id: ArkBackend,
    PeaZipBackend.tool_id: PeaZipBackend,
}

DEFAULT_TOOL = ArkBackend.tool_id


class ArchiveToolService:
    """Resolves the configured archive tool and launches its commands."""

    def __init__(self, config=None, launcher=None):
        self.config = config
        # Injectable for tests; defaults to subprocess.Popen.
        self._launcher = launcher

    # ─── Tool resolution ───────────────────────────────────────

    @property
    def tool_id(self) -> str:
        tool = ""
        if self.config is not None:
            getter = getattr(self.config, "archive_tool", None)
            if callable(getter):
                tool = str(getter() or "")
            else:
                tool = str(getattr(self.config, "data", {}).get("archive_tool", ""))
        if tool not in BACKENDS:
            return DEFAULT_TOOL
        return tool

    @property
    def backend(self) -> ArchiveToolBackend:
        return BACKENDS[self.tool_id]()

    def backend_for(self, tool_id: str) -> ArchiveToolBackend | None:
        backend_class = BACKENDS.get(str(tool_id))
        return backend_class() if backend_class else None

    def is_available(self) -> bool:
        return self.backend.is_installed()

    @property
    def install_hint(self) -> str:
        return self.backend.install_hint

    # ─── Launch helpers ────────────────────────────────────────

    def _launch(self, command: list[str], cwd: Path | None = None) -> bool:
        if not command:
            return False
        launcher = self._launcher
        if launcher is None:
            def launcher(cmd, cwd=None):
                subprocess.Popen(
                    cmd,
                    cwd=str(cwd) if cwd else None,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return True

        try:
            return bool(launcher(command, cwd=cwd))
        except (OSError, subprocess.SubprocessError):
            return False

    # ─── Public operations ─────────────────────────────────────

    def open_archive(self, path: Path) -> bool:
        return self._launch(self.backend.open_command(Path(path)))

    def extract_here(self, path: Path) -> bool:
        path = Path(path)
        return self._launch(self.backend.extract_here_command(path), cwd=path.parent)

    def extract_into_new_folder(self, path: Path) -> bool:
        path = Path(path)
        return self._launch(
            self.backend.extract_into_new_folder_command(path), cwd=path.parent
        )

    def extract_to(self, path: Path, destination: Path | None = None) -> bool:
        path = Path(path)
        return self._launch(
            self.backend.extract_to_command(path, destination), cwd=path.parent
        )

    def create_archive(self, paths: Sequence[Path]) -> bool:
        paths = [Path(p) for p in paths]
        if not paths:
            return False
        return self._launch(
            self.backend.create_archive_command(paths), cwd=paths[0].parent
        )

    def default_quick_add_target(self, paths: Sequence[Path], fmt: str = "zip") -> Path | None:
        """Compute the default target archive for a quick add of ``paths``."""
        paths = [Path(p) for p in paths]
        if not paths:
            return None
        first = paths[0]
        base = first.name or "archive"
        return first.parent / f"{base}.{fmt.lstrip('.')}"

    def quick_add(self, paths: Sequence[Path], fmt: str = "zip") -> bool:
        paths = [Path(p) for p in paths]
        if not paths:
            return False
        target = self.default_quick_add_target(paths, fmt)
        return self._launch(
            self.backend.quick_add_command(paths, target), cwd=paths[0].parent
        )

    def test_archive(self, path: Path) -> bool:
        command = self.backend.test_command(Path(path))
        if command is None:
            return False
        return self._launch(command)
