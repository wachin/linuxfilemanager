"""Palette command actions extracted from MainWindow (Fase 1.1).

Pure mixin: methods keep ``self`` = MainWindow, so moving them here changes
no behaviour; MainWindow inherits this mixin to keep one class per concern.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QInputDialog

from lfmapp.core.xdg import get_xdg_user_dirs
from lfmapp.ui.command_palette_dialog import CommandPaletteDialog
from lfmapp.ui.sidebar import Sidebar


class PaletteActionsMixin:
    def _format_shortcut(self, shortcut):
        if isinstance(shortcut, QKeySequence):
            return shortcut.toString(QKeySequence.SequenceFormat.NativeText)
        return str(shortcut) if shortcut is not None else ""

    def _default_command_aliases(self, title: str, category: str) -> list[str]:
        normalized = title.replace("...", "").replace("&", "")
        words = [word.lower() for word in normalized.split() if word]
        aliases = set(words)
        aliases.update(
            " ".join(words[i : i + 2]) for i in range(len(words) - 1)
        )
        aliases.add(category.lower())
        synonym_map = {
            self.tr("Preferences...").replace("...", "").lower(): [
                self.tr("settings"),
                self.tr("prefs"),
            ],
            self.tr("Command Palette...").replace("...", "").lower(): [
                self.tr("palette"),
                self.tr("commands"),
                self.tr("cmd"),
            ],
            self.tr("Back").lower(): [self.tr("previous")],
            self.tr("Forward").lower(): [self.tr("next")],
            self.tr("Up").lower(): [self.tr("parent"), self.tr("above")],
            self.tr("Home").lower(): [self.tr("start")],
            self.tr("Properties").lower(): [self.tr("info"), self.tr("details")],
            self.tr("Refresh").lower(): [self.tr("reload")],
            self.tr("New Folder").lower(): [self.tr("mkdir"), self.tr("folder")],
            self.tr("New File").lower(): [self.tr("touch"), self.tr("file")],
            self.tr("Copy").lower(): [self.tr("duplicate")],
            self.tr("Paste").lower(): [self.tr("insert")],
            self.tr("Cut").lower(): [self.tr("move"), self.tr("delete")],
            self.tr("Undo").lower(): [self.tr("revert")],
            self.tr("Redo").lower(): [self.tr("repeat")],
            self.tr("Toggle Preview Panel").lower(): [
                self.tr("preview"),
                self.tr("panel"),
            ],
            self.tr("Toggle Sidebar").lower(): [self.tr("sidebar"), self.tr("panel")],
            self.tr("Open in Terminal").lower(): [
                self.tr("terminal"),
                self.tr("shell"),
                self.tr("bash"),
            ],
            self.tr("Go to Path...").replace("...", "").lower(): [
                self.tr("goto"),
                self.tr("cd"),
                self.tr("path"),
            ],
            self.tr("Open Recent File...").replace("...", "").lower(): [
                self.tr("recent"),
                self.tr("history"),
                self.tr("open recent"),
            ],
            self.tr("Clear Recent Files").lower(): [
                self.tr("clear recent"),
                self.tr("history"),
                self.tr("recent"),
            ],
            self.tr("Send to Desktop").lower(): [
                self.tr("desktop"),
                self.tr("send"),
            ],
            self.tr("Send by Email").lower(): [
                self.tr("email"),
                self.tr("send"),
            ],
            self.tr("Add Current Folder to Bookmarks").lower(): [
                self.tr("bookmark"),
                self.tr("favorite"),
            ],
            self.tr("Add Tag to File").lower(): [
                self.tr("tag"),
                self.tr("label"),
            ],
            self.tr("Manage Tags...").replace("...", "").lower(): [
                self.tr("tags"),
                self.tr("label"),
            ],
            self.tr("Search by Tag...").replace("...", "").lower(): [
                self.tr("tags"),
                self.tr("search"),
            ],
            self.tr("Open Vault").lower(): [
                self.tr("vault"),
                self.tr("secure"),
            ],
        }
        aliases.update(synonym_map.get(normalized.lower(), []))
        return [alias for alias in sorted(aliases) if alias]

    def _register_command_action(
        self,
        action: QAction,
        category: str = "",
        shortcut: str = "",
        alias: list[str] | None = None,
        command_id: str | None = None,
    ):
        title = action.text().replace("&", "")
        if not shortcut and action.shortcut():
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        if alias is None:
            alias = []
        alias = list(dict.fromkeys(alias + self._default_command_aliases(title, category)))
        key = (title, category, shortcut, command_id or "")
        if key in self._command_action_keys:
            return
        self._command_action_keys.add(key)
        record = {
            "title": title,
            "callback": lambda action=action: action.trigger(),
            "shortcut": shortcut,
            "category": category,
            "action": action,
            "alias": alias,
            "command_id": command_id,
        }
        self._command_actions.append(record)
        if action is not None:
            self._command_action_by_action[action] = record

    def _palette_commands(self) -> list[dict]:
        commands = []
        for info in self._command_actions:
            action = info.get("action")
            title = action.text().replace("&", "") if action else info.get("title", "")
            if action is not None:
                info["title"] = title
            enabled = action.isEnabled() if action is not None else info.get("enabled", True)
            category = info.get("category", "")
            alias = list(dict.fromkeys((info.get("alias", []) or []) + self._default_command_aliases(title, category)))
            commands.append(
                {
                    "title": title,
                    "callback": info["callback"],
                    "shortcut": info.get("shortcut", ""),
                    "category": category,
                    "enabled": enabled,
                    "alias": alias,
                    "command_id": info.get("command_id", ""),
                }
            )

        commands.extend(self._navigation_palette_commands())
        commands.extend(self._contextual_palette_commands())
        return self._unique_commands(commands)

    def _contextual_palette_commands(self) -> list[dict]:
        commands: list[dict] = []
        selected_path = self.workspace.selected_path()
        current_path = self.workspace.current_path()
        can_paste = self._clipboard_mode in {"copy", "cut"} and bool(self._clipboard_paths)

        if selected_path is not None and selected_path.exists():
            commands.append(
                {
                    "title": self.tr("Open"),
                    "callback": self.open_selected,
                    "shortcut": "",
                    "category": self.tr("Selection"),
                    "enabled": True,
                }
            )
            if selected_path.is_file():
                commands.append(
                    {
                        "title": self.tr("Open with..."),
                        "callback": self.open_with_dialog,
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    }
                )
                commands.append(
                    {
                        "title": self.tr("Set default application..."),
                        "callback": self.set_default_application_dialog,
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    }
                )
            commands.append(
                {
                    "title": self.tr("Rename"),
                    "callback": self.rename_selected_dialog,
                    "shortcut": "F2",
                    "category": self.tr("Selection"),
                    "enabled": True,
                }
            )
            commands.extend(
                [
                    {
                        "title": self.tr("Copy path"),
                        "callback": self.copy_path,
                        "shortcut": "Ctrl+Shift+C",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    },
                    {
                        "title": self.tr("Cut"),
                        "callback": self.cut_selected,
                        "shortcut": "Ctrl+X",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    },
                    {
                        "title": self.tr("Copy"),
                        "callback": self.copy_selected,
                        "shortcut": "Ctrl+C",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    },
                    {
                        "title": self.tr("Copy to..."),
                        "callback": self.copy_selected_to,
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": self._context_entry_enabled("selection", "copy_to") and self.config.data.get("move_copy_menu_show_bookmarks", True),
                    },
                    {
                        "title": self.tr("Move to..."),
                        "callback": self.move_selected_to,
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": self._context_entry_enabled("selection", "move_to") and self.config.data.get("move_copy_menu_show_bookmarks", True),
                    },
                ]
            )

            if self._context_entry_enabled("selection", "open_in_terminal"):
                commands.append(
                    {
                        "title": self.tr("Open in Terminal"),
                        "callback": lambda: self.open_terminal_in_directory(selected_path.parent if selected_path.is_file() else selected_path),
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": True,
                        "alias": ["terminal", "shell"],
                    }
                )

            if selected_path.is_dir() and self._context_entry_enabled("selection", "pin"):
                commands.append(
                    {
                        "title": self.tr("Add folder to Quick Access"),
                        "callback": self.add_bookmark,
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    }
                )

            if selected_path.is_file() and selected_path.suffix.lower() in {".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2"}:
                commands.append(
                    {
                        "title": self.tr("Extract Here"),
                        "callback": lambda: self.extract_archive(selected_path),
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    }
                )
                commands.append(
                    {
                        "title": self.tr("Extract to..."),
                        "callback": lambda: self.extract_archive_to(selected_path),
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    }
                )

            commands.extend(
                [
                    {
                        "title": self.tr("Compress to ZIP"),
                        "callback": lambda: self.compress_to_zip(selected_path),
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    },
                    {
                        "title": self.tr("Print"),
                        "callback": self.print_selected,
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": self._context_entry_enabled("selection", "print"),
                    },
                    {
                        "title": self.tr("Move to Trash"),
                        "callback": self.trash_selected,
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": self._context_entry_enabled("selection", "move_to_trash"),
                    },
                    {
                        "title": self.tr("Delete Permanently"),
                        "callback": self.delete_selected,
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": self.config.data.get("show_delete_bypassing_trash", True),
                    },
                    {
                        "title": self.tr("Add tag..."),
                        "callback": lambda: self.on_add_tag_to_file(selected_path),
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    },
                    {
                        "title": self.tr("Properties"),
                        "callback": self.show_properties,
                        "shortcut": "",
                        "category": self.tr("Selection"),
                        "enabled": True,
                    },
                ]
            )

        if current_path is not None and current_path.exists():
            commands.append(
                {
                    "title": self.tr("Open in Terminal"),
                    "callback": lambda: self.open_current_directory_in_terminal() if current_path.is_dir() else None,
                    "shortcut": "",
                    "category": self.tr("Navigation"),
                    "enabled": True,
                    "alias": ["terminal", "shell"],
                }
            )
            commands.append(
                {
                    "title": self.tr("Refresh"),
                    "callback": self.refresh_view,
                    "shortcut": "F5",
                    "category": self.tr("View"),
                    "enabled": True,
                    "alias": ["reload", "refresh view"],
                }
            )
            if can_paste:
                commands.append(
                    {
                        "title": self.tr("Paste"),
                        "callback": self.paste_from_clipboard,
                        "shortcut": "Ctrl+V",
                        "category": self.tr("Clipboard"),
                        "enabled": True,
                    }
                )

        return commands

    def _navigation_palette_commands(self) -> list[dict]:
        recent_files = [Path(path) for path in self.config.recent_files if Path(path).exists() and Path(path).is_file()]
        commands = [
            {
                "title": self.tr("Go to Path..."),
                "callback": self.show_go_to_path_dialog,
                "shortcut": "Ctrl+L",
                "category": self.tr("Navigation"),
                "enabled": True,
                "alias": ["cd", "goto", "path"],
            },
            {
                "title": self.tr("Open Recent File..."),
                "callback": self.show_recent_file_dialog,
                "shortcut": "",
                "category": self.tr("Navigation"),
                "enabled": bool(recent_files),
                "alias": ["recent", "recent file", "open recent"],
            },
        ]

        sidebar_items = [
            (self.tr("Home"), str(Path.home()), self.tr("Quick Access")),
        ]
        xdg_dirs = get_xdg_user_dirs()
        for key, label in (
            ("desktop", self.tr("Desktop")),
            ("downloads", self.tr("Downloads")),
            ("documents", self.tr("Documents")),
            ("music", self.tr("Music")),
            ("pictures", self.tr("Pictures")),
            ("videos", self.tr("Videos")),
        ):
            path = xdg_dirs.get(key)
            if path is not None:
                sidebar_items.append((label, str(path), self.tr("Quick Access")))

        pinned = [
            (Sidebar._bookmark_label(bookmark), Sidebar._bookmark_path(bookmark), self.tr("Quick Access"))
            for bookmark in self.bookmark_service.bookmarks
            if Sidebar._bookmark_is_pinned(bookmark)
            and Sidebar._bookmark_path(bookmark)
        ]
        for label, path, category in pinned:
            if path and Path(path).exists() and Path(path).is_dir():
                sidebar_items.append((label, path, category))

        frequent = [
            (Path(path).name or path, path, self.tr("Quick Access"))
            for path in self.config.frequent_folders()
            if Path(path).exists() and Path(path).is_dir()
        ]
        for label, path, category in frequent:
            sidebar_items.append((label, path, category))

        recent = [
            (Path(path).name or path, path, self.tr("Quick Access"))
            for path in self.config.recent_locations
            if Path(path).exists() and Path(path).is_dir()
        ]
        for label, path, category in recent:
            sidebar_items.append((label, path, category))

        for label, path, category in sidebar_items:
            commands.append(
                {
                    "title": self.tr("Open {name}").format(name=label),
                    "callback": lambda path=Path(path): self.go_to(path),
                    "shortcut": "",
                    "category": category,
                    "enabled": True,
                    "alias": [label.lower(), str(path), "quick access", "recent"],
                    "command_id": f"quick_access::{path}",
                }
            )

        return commands

    def _unique_commands(self, commands: list[dict]) -> list[dict]:
        seen = set()
        unique_commands: list[dict] = []
        for command in commands:
            command_id = command.get("command_id", "")
            key = (
                command_id or command.get("title", ""),
                command.get("category", ""),
                command.get("shortcut", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            unique_commands.append(command)
        return unique_commands

    def show_command_palette(self):
        commands = self._palette_commands()
        dialog = CommandPaletteDialog(commands, self)
        dialog.exec()

    def show_go_to_path_dialog(self):
        path_text, ok = QInputDialog.getText(
            self,
            self.tr("Go to Path"),
            self.tr("Path:"),
            text=str(self.workspace.current_path() or Path.home()),
        )
        if ok and path_text:
            self.go_to(Path(path_text).expanduser())

    def show_recent_file_dialog(self):
        recent_files = [Path(path) for path in self.config.recent_files if Path(path).exists() and Path(path).is_file()]
        if not recent_files:
            return

        choices = [str(path) for path in recent_files]
        selection, ok = QInputDialog.getItem(
            self,
            self.tr("Open Recent File"),
            self.tr("Choose a recent file:"),
            choices,
            0,
            False,
        )
        if ok and selection:
            self.open_recent_file(Path(selection))
