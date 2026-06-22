"""Bookmark service for linux-file-manager.

Manages persistent bookmarks saved in the config directory.
"""

import json
from pathlib import Path
from typing import Optional

from lfm.core.paths import CONFIG_DIR

BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"


class BookmarkService:
    """Manages user bookmarks with persistence."""

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._bookmarks: list[dict] = self._load()

    def _load(self) -> list[dict]:
        """Load bookmarks from disk."""
        if BOOKMARKS_FILE.exists():
            try:
                data = json.loads(BOOKMARKS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_bookmarks()

    def _default_bookmarks(self) -> list[dict]:
        """Return default bookmarks based on XDG user dirs."""
        home = Path.home()
        defaults = [
            ("Home", str(home)),
        ]
        xdg_dirs = [
            ("Desktop", "Desktop"),
            ("Documents", "Documents"),
            ("Downloads", "Downloads"),
            ("Music", "Music"),
            ("Pictures", "Pictures"),
            ("Videos", "Videos"),
        ]
        for label, dirname in xdg_dirs:
            path = home / dirname
            if path.exists():
                defaults.append((label, str(path)))

        return [{"label": label, "path": path, "pinned": True} for label, path in defaults]

    def save(self):
        """Save bookmarks to disk."""
        BOOKMARKS_FILE.write_text(
            json.dumps(self._bookmarks, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    @property
    def bookmarks(self) -> list[dict]:
        """Return list of bookmark dicts with keys: label, path, pinned."""
        return self._bookmarks

    def add(self, path: str, label: Optional[str] = None, pinned: bool = False) -> bool:
        """Add a bookmark. Returns True if added, False if already exists."""
        # Check for duplicate
        for bm in self._bookmarks:
            if bm["path"] == path:
                if pinned and not bm.get("pinned", False):
                    bm["pinned"] = True
                    self.save()
                return False

        if label is None:
            label = Path(path).name or path

        self._bookmarks.append({"label": label, "path": path, "pinned": pinned})
        self.save()
        return True

    def remove(self, path: str) -> bool:
        """Remove a bookmark by path. Returns True if removed."""
        for i, bm in enumerate(self._bookmarks):
            if bm["path"] == path:
                self._bookmarks.pop(i)
                self.save()
                return True
        return False

    def rename(self, path: str, new_label: str) -> bool:
        """Rename a bookmark. Returns True if found and renamed."""
        for bm in self._bookmarks:
            if bm["path"] == path:
                bm["label"] = new_label
                self.save()
                return True
        return False

    def toggle_pin(self, path: str) -> bool:
        """Toggle pinned status. Returns new pinned state."""
        for bm in self._bookmarks:
            if bm["path"] == path:
                bm["pinned"] = not bm["pinned"]
                self.save()
                return bm["pinned"]
        return False

    def is_pinned(self, path: str) -> bool:
        """Return True when the bookmark exists and is pinned to Quick Access."""
        for bm in self._bookmarks:
            if bm["path"] == path:
                return bool(bm.get("pinned", False))
        return False

    def exists(self, path: str) -> bool:
        """Check if a bookmark exists."""
        return any(bm["path"] == path for bm in self._bookmarks)

    def paths(self) -> list[str]:
        """Return list of bookmark paths only."""
        return [bm["path"] for bm in self._bookmarks]
