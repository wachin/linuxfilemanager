import shutil
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QFileDialog

from lfmapp.core.paths import VAULT_DIR


class FileOperations:
    @staticmethod
    def desktop_directory(home: Path | None = None, user_dirs_file: Path | None = None) -> Path:
        """Return the XDG desktop directory, falling back to ~/Desktop."""
        home = Path(home) if home is not None else Path.home()
        user_dirs_file = user_dirs_file or home / ".config" / "user-dirs.dirs"
        desktop = FileOperations._read_xdg_desktop_dir(user_dirs_file, home)
        return desktop or home / "Desktop"

    @staticmethod
    def ensure_desktop_directory(home: Path | None = None, user_dirs_file: Path | None = None) -> Path:
        desktop = FileOperations.desktop_directory(home, user_dirs_file)
        desktop.mkdir(parents=True, exist_ok=True)
        return desktop

    @staticmethod
    def _read_xdg_desktop_dir(path: Path, home: Path) -> Path | None:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None

        for line in lines:
            line = line.strip()
            if not line.startswith("XDG_DESKTOP_DIR="):
                continue
            value = line.split("=", 1)[1].strip().strip('"')
            if not value:
                return None
            value = value.replace("$HOME", str(home))
            return Path(value).expanduser()
        return None

    @staticmethod
    def create_folder(parent, folder_name: str) -> bool:
        if not folder_name.strip():
            return False
        target = Path(parent) / folder_name.strip()
        target.mkdir(parents=False, exist_ok=False)
        return True

    @staticmethod
    def create_file(parent, file_name: str) -> bool:
        if not file_name.strip():
            return False
        target = Path(parent) / file_name.strip()
        target.touch(exist_ok=False)
        return True

    @staticmethod
    def create_multiple(parent, names: list[str], item_type: str) -> list[Path]:
        """Create multiple files or folders and return their paths."""
        parent = Path(parent)
        item_type = item_type.lower()
        if item_type not in {"file", "folder"}:
            raise ValueError("item_type must be 'file' or 'folder'")

        normalized_names = FileOperations.normalize_multiple_names(names)
        created = []
        for name in normalized_names:
            target = parent / name
            if item_type == "folder":
                target.mkdir(parents=False, exist_ok=False)
            else:
                target.touch(exist_ok=False)
            created.append(target)
        return created

    @staticmethod
    def normalize_multiple_names(names: list[str]) -> list[str]:
        """Clean a list of proposed names for bulk creation."""
        normalized = []
        seen = set()
        for raw_name in names:
            name = raw_name.strip()
            if not name:
                continue
            if Path(name).name != name:
                raise ValueError(f"Nested paths are not allowed: {name}")
            if name in seen:
                raise ValueError(f"Duplicate name: {name}")
            seen.add(name)
            normalized.append(name)
        return normalized

    @staticmethod
    def rename(path: Path, new_name: str) -> bool:
        if not new_name.strip():
            return False
        target = path.with_name(new_name.strip())
        path.rename(target)
        return True

    @staticmethod
    def delete(path: Path) -> bool:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True

    @staticmethod
    def move(path: Path, destination: Path) -> bool:
        destination = destination / path.name
        shutil.move(str(path), str(destination))
        return True

    @staticmethod
    def copy(path: Path, destination: Path) -> bool:
        destination = destination / path.name
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)
        return True

    @staticmethod
    def trash(path: Path) -> bool:
        TRASH_DIR = Path.home() / ".local" / "share" / "Trash" / "files"
        TRASH_DIR.mkdir(parents=True, exist_ok=True)
        destination = TRASH_DIR / path.name
        if destination.exists():
            destination = TRASH_DIR / f"{path.stem}_{path.stat().st_mtime:.0f}{path.suffix}"
        shutil.move(str(path), str(destination))
        return True

    @staticmethod
    def choose_folder(parent, caption: str, directory: str = None) -> Optional[Path]:
        selected = QFileDialog.getExistingDirectory(parent, caption, directory or str(Path.home()))
        return Path(selected) if selected else None
