"""Archive extractor service for linux-file-manager.

Supports: zip, tar, tar.gz, tar.xz, tar.bz2, rar (via unrar), 7z (via 7z command).
Uses Python standard library where possible.
External tools are optional dependencies for rar and 7z.
"""

import shutil
import subprocess
import tarfile
import zipfile
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal


# Supported extensions mapping
ARCHIVE_EXTENSIONS = {
    ".zip": "zip",
    ".tar": "tar",
    ".tar.gz": "tar",
    ".tgz": "tar",
    ".tar.xz": "tar",
    ".txz": "tar",
    ".tar.bz2": "tar",
    ".tbz2": "tar",
    ".tar.gz2": "tar",
    ".rar": "rar",
    ".7z": "7z",
    ".deb": "deb",
}


def detect_archive_type(path: Path) -> Optional[str]:
    """Detect archive type from file extension.

    Returns the archive type string or None if not recognized.
    """
    name = path.name.lower()
    # Check multi-part extensions first
    for ext in sorted(ARCHIVE_EXTENSIONS.keys(), key=len, reverse=True):
        if name.endswith(ext):
            return ARCHIVE_EXTENSIONS[ext]
    return None


def is_archive(path: Path) -> bool:
    """Check if a file is a supported archive."""
    return detect_archive_type(path) is not None


def extract_here(path: Path) -> Path:
    """Extract an archive in its parent directory.

    Returns the extraction directory path.
    """
    extract_dir = _get_extract_dir(path)
    extract_to(path, extract_dir)
    return extract_dir


def extract_to(path: Path, destination: Path) -> None:
    """Extract an archive to a specific directory."""
    archive_type = detect_archive_type(path)
    if archive_type is None:
        raise ValueError(f"Unsupported archive format: {path.suffix}")

    destination.mkdir(parents=True, exist_ok=True)

    if archive_type == "zip":
        _extract_zip(path, destination)
    elif archive_type == "tar":
        _extract_tar(path, destination)
    elif archive_type == "rar":
        _extract_rar(path, destination)
    elif archive_type == "7z":
        _extract_7z(path, destination)
    elif archive_type == "deb":
        _extract_deb(path, destination)
    else:
        raise ValueError(f"Extraction not implemented for: {archive_type}")


def _get_extract_dir(path: Path) -> Path:
    """Generate extraction directory name from archive name."""
    name = path.name
    # Remove all known extensions
    for ext in sorted(ARCHIVE_EXTENSIONS.keys(), key=len, reverse=True):
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    if not name:
        name = path.stem
    return path.parent / name


def _extract_zip(path: Path, destination: Path) -> None:
    """Extract a ZIP archive."""
    with zipfile.ZipFile(str(path), "r") as zf:
        zf.extractall(str(destination))


def _extract_tar(path: Path, destination: Path) -> None:
    """Extract a TAR archive (gz, xz, bz2)."""
    with tarfile.open(str(path), "r:*") as tf:
        members = [
            member
            for member in tf.getmembers()
            if _is_safe_tar_member(member, destination)
        ]
        tf.extractall(str(destination), members=members)


def _is_safe_tar_member(member: tarfile.TarInfo, destination: Path) -> bool:
    """Return True when a tar member cannot escape the destination."""
    target = destination / member.name
    if not _is_within_directory(destination, target):
        return False

    if member.issym() or member.islnk():
        link_target = Path(member.linkname)
        if link_target.is_absolute():
            resolved_link_target = link_target
        else:
            resolved_link_target = target.parent / link_target
        if not _is_within_directory(destination, resolved_link_target):
            return False

    return True


def _is_within_directory(directory: Path, target: Path) -> bool:
    """Check whether target resolves inside directory."""
    try:
        directory = directory.resolve()
        target = target.resolve()
        return os.path.commonpath([str(directory), str(target)]) == str(directory)
    except (OSError, ValueError):
        return False


def _extract_rar(path: Path, destination: Path) -> None:
    """Extract a RAR archive using unrar or rar command."""
    cmd = _find_command(["unrar", "rar"])
    if cmd is None:
        raise RuntimeError(
            "RAR extraction requires 'unrar' or 'rar' to be installed.\n"
            "Install with: sudo apt install unrar-free or p7zip-full"
        )
    result = subprocess.run(
        [cmd, "x", "-o+", str(path), str(destination) + "/"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"RAR extraction failed: {result.stderr}")


def _extract_7z(path: Path, destination: Path) -> None:
    """Extract a 7z archive using 7z command."""
    cmd = _find_command(["7z", "7za"])
    if cmd is None:
        raise RuntimeError(
            "7z extraction requires 'p7zip-full' to be installed.\n"
            "Install with: sudo apt install p7zip-full"
        )
    result = subprocess.run(
        [cmd, "x", f"-o{destination}", str(path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"7z extraction failed: {result.stderr}")


def _extract_deb(path: Path, destination: Path) -> None:
    """Extract a DEB package (ar archive with data.tar inside)."""
    # DEB is an ar archive; use ar command or treat as tar
    cmd = _find_command(["ar"])
    if cmd:
        result = subprocess.run(
            [cmd, "x", str(path)],
            capture_output=True, text=True,
            cwd=str(destination)
        )
        if result.returncode != 0:
            raise RuntimeError(f"DEB extraction failed: {result.stderr}")
    else:
        # Fallback: try dpkg-deb
        cmd = _find_command(["dpkg-deb"])
        if cmd:
            result = subprocess.run(
                [cmd, "--extract", str(path), str(destination)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"DEB extraction failed: {result.stderr}")
        else:
            raise RuntimeError(
                "DEB extraction requires 'ar' or 'dpkg-deb' to be installed."
            )


def _find_command(names: list[str]) -> Optional[str]:
    """Find an available command from a list of names."""
    for name in names:
        if shutil.which(name):
            return name
    return None


def create_zip(source: Path | Sequence[Path], destination: Path = None) -> Path:
    """Create a ZIP archive from one or more files/directories.

    Args:
        source: File/directory or sequence of files/directories to compress.
        destination: Path for the new ZIP file. If None, creates next to source.

    Returns:
        Path to the created ZIP file.
    """
    sources = list(source) if isinstance(source, Sequence) and not isinstance(source, Path) else [source]
    sources = [Path(item) for item in sources]
    if not sources:
        raise ValueError("No sources provided for ZIP archive")

    if destination is None:
        first_source = sources[0]
        destination = first_source.parent / f"{first_source.name}.zip"

    with zipfile.ZipFile(str(destination), "w", zipfile.ZIP_DEFLATED) as zf:
        for source_path in sources:
            if source_path.is_file():
                zf.write(str(source_path), source_path.name)
            elif source_path.is_dir():
                for file_path in source_path.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(source_path.parent)
                        zf.write(str(file_path), str(arcname))

    return destination


class CompressThread(QThread):
    """Background thread for ZIP archive creation."""

    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, source: Path | Sequence[Path], destination: Path = None, parent=None):
        super().__init__(parent)
        self.source = source
        self.destination = destination

    def run(self):
        try:
            result = create_zip(self.source, self.destination)
            self.finished.emit(True, f"Created archive: {result}")
        except Exception as exc:
            self.finished.emit(False, str(exc))


class ExtractThread(QThread):
    """Background thread for archive extraction."""

    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, path: Path, destination: Path, parent=None):
        super().__init__(parent)
        self.path = path
        self.destination = destination

    def run(self):
        try:
            extract_to(self.path, self.destination)
            self.finished.emit(True, f"Extracted to {self.destination}")
        except Exception as exc:
            self.finished.emit(False, str(exc))
