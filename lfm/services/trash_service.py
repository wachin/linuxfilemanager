"""Trash service following the FreeDesktop Trash specification.

Spec: https://specifications.freedesktop.org/trash-spec/trashspec-1.0.html
"""

import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from lfm.core.paths import HOME_DIR

TRASH_DIR = HOME_DIR / ".local" / "share" / "Trash"
TRASH_FILES_DIR = TRASH_DIR / "files"
TRASH_INFO_DIR = TRASH_DIR / "info"


def _ensure_trash_dirs():
    """Ensure trash directories exist."""
    TRASH_FILES_DIR.mkdir(parents=True, exist_ok=True)
    TRASH_INFO_DIR.mkdir(parents=True, exist_ok=True)


def _make_trash_info_content(path: Path, deletion_date: datetime) -> str:
    """Generate .trashinfo file content."""
    return (
        "[Trash Info]\n"
        f"Path={path}\n"
        f"DeletionDate={deletion_date.strftime('%Y-%m-%dT%H:%M:%S')}\n"
    )


def _unique_trash_name(name: str) -> str:
    """Generate a unique name for the trash to avoid collisions."""
    target = TRASH_FILES_DIR / name
    if not target.exists():
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    counter = 1
    while target.exists():
        new_name = f"{stem}_{counter}{suffix}"
        target = TRASH_FILES_DIR / new_name
        counter += 1
    return new_name


def send_to_trash(path: Path) -> str:
    """Send a file or directory to trash following FreeDesktop spec.

    Creates both the file in trash/files/ and a .trashinfo in trash/info/.
    """
    _ensure_trash_dirs()
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    original_path = str(path.resolve())
    deletion_date = datetime.now()

    trash_name = _unique_trash_name(path.name)
    trash_file_path = TRASH_FILES_DIR / trash_name
    trash_info_path = TRASH_INFO_DIR / f"{trash_name}.trashinfo"

    # Move the file/directory to trash/files/
    shutil.move(str(path), str(trash_file_path))

    # Create .trashinfo file
    info_content = _make_trash_info_content(Path(original_path), deletion_date)
    trash_info_path.write_text(info_content, encoding="utf-8")

    return trash_name


def restore_from_trash(trash_name: str) -> Optional[Path]:
    """Restore a file from trash to its original location.

    Returns the restored path, or None if restoration failed.
    """
    _ensure_trash_dirs()
    trash_file = TRASH_FILES_DIR / trash_name
    trash_info = TRASH_INFO_DIR / f"{trash_name}.trashinfo"

    if not trash_file.exists():
        raise FileNotFoundError(f"Trashed file not found: {trash_name}")

    # Read original path from .trashinfo
    original_path = None
    if trash_info.exists():
        for line in trash_info.read_text(encoding="utf-8").splitlines():
            if line.startswith("Path="):
                original_path = line[5:]
                break

    if not original_path:
        raise ValueError(f"No original path found in trashinfo for: {trash_name}")

    restore_path = Path(original_path)

    # If original location doesn't exist or is occupied, restore to home
    if restore_path.exists():
        restore_path = Path.home() / trash_name

    # Move file back
    shutil.move(str(trash_file), str(restore_path))

    # Remove .trashinfo file
    if trash_info.exists():
        trash_info.unlink()

    return restore_path


def empty_trash() -> bool:
    """Permanently delete all files in trash."""
    _ensure_trash_dirs()

    # Remove all files
    for item in TRASH_FILES_DIR.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception:
            pass

    # Remove all .trashinfo files
    for item in TRASH_INFO_DIR.iterdir():
        try:
            item.unlink()
        except Exception:
            pass

    return True


def list_trash() -> list[dict]:
    """List all items in trash with their info.

    Returns a list of dicts with keys: name, original_path, deletion_date, size
    """
    _ensure_trash_dirs()
    items = []

    for item in TRASH_FILES_DIR.iterdir():
        info_path = TRASH_INFO_DIR / f"{item.name}.trashinfo"
        original_path = ""
        deletion_date = ""

        if info_path.exists():
            for line in info_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("Path="):
                    original_path = line[5:]
                elif line.startswith("DeletionDate="):
                    deletion_date = line[13:]

        try:
            size = _get_size(item)
        except OSError:
            size = 0

        items.append({
            "name": item.name,
            "original_path": original_path,
            "deletion_date": deletion_date,
            "size": size,
            "is_dir": item.is_dir(),
        })

    return items


def _get_size(path: Path) -> int:
    """Get total size of a file or directory."""
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def trash_size() -> int:
    """Get total size of trash in bytes."""
    _ensure_trash_dirs()
    total = 0
    for item in TRASH_FILES_DIR.iterdir():
        try:
            total += _get_size(item)
        except OSError:
            pass
    return total


def trash_count() -> int:
    """Get number of items in trash."""
    _ensure_trash_dirs()
    return sum(1 for _ in TRASH_FILES_DIR.iterdir())
