import json
from pathlib import Path

from lfm.core.paths import CONFIG_DIR, CONFIG_FILE


def _default_bookmarks():
    home = Path.home()
    return [
        str(home),
        str(home / "Downloads"),
        str(home / "Documents"),
    ]


class Config:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                # Ensure we always return a dict. Older or corrupted files
                # might contain `null` or a list of bookmarks.
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    # Migrate old-format bookmarks list to new dict shape
                    return {
                        "bookmarks": data,
                        "text_index_enabled": False,
                        "remember_folder_view": True,
                        "selection_checkboxes": False,
                        "show_hidden_files": True,
                        "show_file_extensions": True,
                        "icon_grid_size": "medium",
                        "extensions_enabled": False,
                        "enabled_extensions": [],
                        "window_remember_size": True,
                        "window_width": 980,
                        "window_height": 620,
                        "ui_font_family": "",
                        "ui_font_size": 10,
                        "ui_font_weight": 400,
                        "ui_font_italic": False,
                        "last_visited": None,
                        "recent_locations": [],
                        "recent_files": [],
                        "folder_visit_counts": {},
                        "folder_views": {},
                    }
            except Exception:
                pass
        return {
            "bookmarks": _default_bookmarks(),
            "text_index_enabled": False,
            "remember_folder_view": True,
            "selection_checkboxes": False,
            "show_hidden_files": True,
            "show_file_extensions": True,
            "icon_grid_size": "medium",
            "extensions_enabled": False,
            "enabled_extensions": [],
            "sidebar_visible": True,
            "preview_visible": True,
            "window_remember_size": True,
            "window_width": 980,
            "window_height": 620,
            "ui_font_family": "",
            "ui_font_size": 10,
            "ui_font_weight": 400,
            "ui_font_italic": False,
            "last_visited": None,
            "recent_locations": [],
            "recent_files": [],
            "folder_visit_counts": {},
            "folder_views": {},
        }

    def save(self):
        CONFIG_FILE.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @property
    def bookmarks(self):
        return self.data.setdefault("bookmarks", [])

    def add_bookmark(self, path: str):
        if path not in self.bookmarks:
            self.bookmarks.append(path)
            self.save()

    def remove_bookmark(self, path: str):
        if path in self.bookmarks:
            self.bookmarks.remove(path)
            self.save()

    @property
    def text_index_enabled(self) -> bool:
        return bool(self.data.setdefault("text_index_enabled", False))

    def set_text_index_enabled(self, enabled: bool):
        self.data["text_index_enabled"] = bool(enabled)
        self.save()

    @property
    def sidebar_visible(self) -> bool:
        return bool(self.data.setdefault("sidebar_visible", True))

    def set_sidebar_visible(self, visible: bool):
        self.data["sidebar_visible"] = bool(visible)
        self.save()

    @property
    def preview_visible(self) -> bool:
        return bool(self.data.setdefault("preview_visible", True))

    def set_preview_visible(self, visible: bool):
        self.data["preview_visible"] = bool(visible)
        self.save()

    @property
    def last_visited(self) -> str | None:
        return self.data.get("last_visited")

    def set_last_visited(self, path: str | None):
        self.data["last_visited"] = str(path) if path is not None else None
        self.save()

    @property
    def recent_locations(self) -> list[str]:
        return list(self.data.setdefault("recent_locations", []))

    def add_recent_location(self, path: str, max_items: int = 10):
        recent = self.data.setdefault("recent_locations", [])
        path = str(path)
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        while len(recent) > max_items:
            recent.pop()
        self.save()

    @property
    def recent_files(self) -> list[str]:
        return list(self.data.setdefault("recent_files", []))

    def add_recent_file(self, path: str, max_items: int = 10):
        recent = self.data.setdefault("recent_files", [])
        path = str(path)
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        while len(recent) > max_items:
            recent.pop()
        self.save()

    def clear_recent_files(self):
        self.data["recent_files"] = []
        self.save()

    def add_folder_visit(self, path: str):
        counts = self.data.setdefault("folder_visit_counts", {})
        path = str(path)
        counts[path] = int(counts.get(path, 0)) + 1
        self.save()

    def frequent_folders(self, max_items: int = 5) -> list[str]:
        counts = self.data.setdefault("folder_visit_counts", {})
        ranked = sorted(
            counts.items(),
            key=lambda item: (-int(item[1]), item[0].casefold()),
        )
        return [path for path, _count in ranked[:max_items]]

    def clear_frequent_folders(self):
        self.data["folder_visit_counts"] = {}
        self.save()

    def get_folder_view(self, path: str) -> str | None:
        """Return the saved view mode for a folder (one of 'icon','list','details','compact')."""
        views = self.data.setdefault("folder_views", {})
        return views.get(str(path))

    def set_folder_view(self, path: str | None, view: str | None):
        """Persist a view mode for a folder. Passing `None` for view clears the entry."""
        views = self.data.setdefault("folder_views", {})
        if path is None:
            return
        key = str(path)
        if view is None:
            if key in views:
                del views[key]
        else:
            views[key] = str(view)
        self.save()

    def clear_folder_view(self, path: str | None):
        """Clear the stored view mode for a specific folder."""
        self.set_folder_view(path, None)

    def clear_all_folder_views(self):
        """Clear all persisted folder view settings."""
        self.data["folder_views"] = {}
        self.save()

    @property
    def remember_folder_view(self) -> bool:
        return bool(self.data.setdefault("remember_folder_view", True))

    def set_remember_folder_view(self, enabled: bool):
        self.data["remember_folder_view"] = bool(enabled)
        self.save()

    @property
    def selection_checkboxes(self) -> bool:
        return bool(self.data.setdefault("selection_checkboxes", False))

    def set_selection_checkboxes(self, enabled: bool):
        self.data["selection_checkboxes"] = bool(enabled)
        self.save()

    @property
    def show_hidden_files(self) -> bool:
        return bool(self.data.setdefault("show_hidden_files", True))

    def set_show_hidden_files(self, enabled: bool):
        self.data["show_hidden_files"] = bool(enabled)
        self.save()

    @property
    def show_file_extensions(self) -> bool:
        return bool(self.data.setdefault("show_file_extensions", True))

    def set_show_file_extensions(self, enabled: bool):
        self.data["show_file_extensions"] = bool(enabled)
        self.save()

    @property
    def icon_grid_size(self) -> str:
        return str(self.data.setdefault("icon_grid_size", "medium"))

    def set_icon_grid_size(self, size: str):
        self.data["icon_grid_size"] = str(size)
        self.save()

    @property
    def extensions_enabled(self) -> bool:
        return bool(self.data.setdefault("extensions_enabled", False))

    def set_extensions_enabled(self, enabled: bool):
        self.data["extensions_enabled"] = bool(enabled)
        self.save()

    @property
    def enabled_extensions(self) -> list[str]:
        enabled = self.data.setdefault("enabled_extensions", [])
        if not isinstance(enabled, list):
            enabled = []
            self.data["enabled_extensions"] = enabled
        return [str(extension_id) for extension_id in enabled]

    def set_extension_enabled(self, extension_id: str, enabled: bool):
        extension_id = str(extension_id).strip()
        if not extension_id:
            return
        enabled_extensions = self.data.setdefault("enabled_extensions", [])
        if not isinstance(enabled_extensions, list):
            enabled_extensions = []
            self.data["enabled_extensions"] = enabled_extensions
        if enabled and extension_id not in enabled_extensions:
            enabled_extensions.append(extension_id)
        elif not enabled and extension_id in enabled_extensions:
            enabled_extensions.remove(extension_id)
        self.save()

    @property
    def preferred_terminal(self) -> str:
        terminal = self.data.setdefault("preferred_terminal", "")
        return str(terminal) if terminal is not None else ""

    def set_preferred_terminal(self, terminal: str):
        self.data["preferred_terminal"] = str(terminal or "")
        self.save()

    @property
    def window_remember_size(self) -> bool:
        return bool(self.data.setdefault("window_remember_size", True))

    def set_window_remember_size(self, enabled: bool):
        self.data["window_remember_size"] = bool(enabled)
        self.save()

    @property
    def window_width(self) -> int:
        try:
            return int(self.data.setdefault("window_width", 980))
        except Exception:
            return 980

    @property
    def window_height(self) -> int:
        try:
            return int(self.data.setdefault("window_height", 620))
        except Exception:
            return 620

    def set_window_size(self, width: int, height: int):
        try:
            width = int(width)
            height = int(height)
        except Exception:
            return
        if width < 640 or height < 420:
            return
        if width > 8192 or height > 8192:
            return
        self.data["window_width"] = width
        self.data["window_height"] = height
        self.save()

    @property
    def ui_font_family(self) -> str:
        family = self.data.setdefault("ui_font_family", "")
        return str(family) if family is not None else ""

    def set_ui_font_family(self, family: str):
        self.data["ui_font_family"] = str(family or "")
        self.save()

    @property
    def ui_font_size(self) -> int:
        try:
            size = int(self.data.setdefault("ui_font_size", 10))
        except Exception:
            size = 10
        if size < 6:
            return 6
        if size > 48:
            return 48
        return size

    def set_ui_font_size(self, size: int):
        try:
            size = int(size)
        except Exception:
            return
        if size < 6:
            size = 6
        if size > 48:
            size = 48
        self.data["ui_font_size"] = size
        self.save()

    @property
    def ui_font_weight(self) -> int:
        try:
            weight = int(self.data.setdefault("ui_font_weight", 400))
        except Exception:
            weight = 400
        if weight < 1:
            return 1
        if weight > 1000:
            return 1000
        return weight

    def set_ui_font_weight(self, weight: int):
        try:
            weight = int(weight)
        except Exception:
            return
        if weight < 1:
            weight = 1
        if weight > 1000:
            weight = 1000
        self.data["ui_font_weight"] = weight
        self.save()

    @property
    def ui_font_italic(self) -> bool:
        return bool(self.data.setdefault("ui_font_italic", False))

    def set_ui_font_italic(self, italic: bool):
        self.data["ui_font_italic"] = bool(italic)
        self.save()
