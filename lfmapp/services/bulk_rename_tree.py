"""Recursive / template bulk rename (ROADMAP Phase 6.2 — pending items).

Complements ``bulk_rename.py`` (the flat, non-recursive engine) with:

* **Recursion** into subfolders (content only, or folders as well).
* **Templates** using printable tokens, so one pattern can generate subfolders
  or embed the parent folder's name, and renumber across the whole tree.

This is UI-independent: it computes ``old path -> new path`` (which may span
directories) and applies it non-destructively, reporting back each rename so
the caller can record reversible ``RenameOperation`` entries.

Template tokens (case-sensitive):

* ``{n}``      — counter (zero-padded when followed by ``:NN``, e.g. ``{n:03}``)
* ``{parent}`` — name of the parent folder (for files; also works for folders)
* ``{folder}`` — name of the folder itself (folders only)
* ``{ext}``    — the extension including the dot (files only)
* ``{date}``   — last-modified date, formatted with the ``--date-fmt`` option
* ``{name}``   — the current name (stem + extension)

Anything else in the template is literal text. A template that contains folder
separators ("/") creates the corresponding subdirectories.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from lfmapp.services.bulk_rename import sanitize_filename, split_name


DEFAULT_DATE_FMT = "%Y-%m-%d"
_NUMBER_TOKEN = re.compile(r"\{n(?::(\d+))?\}")


def collect_tree(
    root: Path,
    include_folders: bool = False,
    include_root: bool = False,
) -> list[Path]:
    """Return files (and optionally folders) under ``root`` in walk order."""
    if not root.is_dir():
        return []
    items: list[Path] = []
    for dirpath, dirnames, filenames in sorted(Path(root).walk()):
        dirnames.sort()
        for folder in dirnames:
            if include_folders:
                items.append(dirpath / folder)
        for filename in sorted(filenames):
            items.append(dirpath / filename)
    return items


@dataclass
class TreeRenameTarget:
    original: Path
    target: Path
    is_folder: bool
    moved_to_subfolder: bool = False


@dataclass
class TreePlan:
    items: list[TreeRenameTarget] = field(default_factory=list)

    @property
    def conflicts(self) -> list[TreeRenameTarget]:
        return [
            item
            for item in self.items
            if item.original != item.target and (
                not _valid_relpath(item.target)
                or item.target.exists()
            )
        ]


def _token_n(template: str, index: int) -> (str, int):
    """Render ``{n}``/``{n:NN}`` and return (rendered, default_width)."""

    def replace(match):
        width = int(match.group(1)) if match.group(1) else 0
        return str(index).zfill(width)

    return _NUMBER_TOKEN.sub(replace, template)


def render_template(
    template: str,
    path: Path,
    index: int,
    *,
    is_folder: bool,
    date_fmt: str = DEFAULT_DATE_FMT,
) -> str:
    """Render a template for ``path`` (a file or folder)."""
    parts = split_name(path.name)
    is_dir = path.is_dir() if path.exists() else is_folder
    extension = "" if is_dir else parts.extension
    stem = path.name if is_dir else parts.stem
    try:
        date_text = datetime.fromtimestamp(path.stat().st_mtime).strftime(date_fmt)
    except (OSError, ValueError):
        date_text = ""

    result = template
    result = _token_n(result, index)
    result = result.replace("{parent}", path.parent.name if path.parent.name else "")
    result = result.replace("{folder}", path.name if is_dir else "")
    result = result.replace("{ext}", extension)
    result = result.replace("{date}", date_text)
    result = result.replace("{name}", path.name)
    # Sanitize each path component, preserving "/" as a subfolder separator.
    components = result.split("/")
    components = [sanitize_filename(component) for component in components]
    return "/".join(component for component in components if component)


def _valid_relpath(path: Path) -> bool:
    """A (possibly relative) destination must not be empty or escape upward."""
    text = str(path)
    if not text or text in {".", "/"}:
        return False
    # Reject ".." components that would escape the tree root.
    if ".." in Path(text).parts:
        return False
    return True


def build_tree_plan(
    root: Path,
    template: str,
    *,
    include_folders: bool = False,
    date_fmt: str = DEFAULT_DATE_FMT,
    start_number: int = 1,
) -> TreePlan:
    """Compute old->new targets for every item in the tree."""
    items = collect_tree(root, include_folders=include_folders)
    plan = TreePlan()
    for index, path in enumerate(items):
        is_folder = path.is_dir()
        rendered = render_template(
            template,
            path,
            index + start_number,
            is_folder=is_folder,
            date_fmt=date_fmt,
        )
        if not rendered:
            continue
        # The target is relative to the file's own parent; a "/" builds subfolders.
        target = path.parent / rendered
        plan.items.append(
            TreeRenameTarget(
                original=path,
                target=target,
                is_folder=is_folder,
                moved_to_subfolder="/" in rendered,
            )
        )
    return plan


def apply_tree_plan(plan: TreePlan) -> list[tuple[Path, Path]]:
    """Apply the plan. Parent directories are created as needed.

    Returns ``(old_path, new_path)`` pairs for every item that moved/renamed.
    Raises ``ValueError`` if a target already exists.
    """
    # Folders first (so parent dirs exist before files move into them) and,
    # among files, deepest targets first to avoid nesting collisions.
    def sort_key(item: TreeRenameTarget):
        return (0 if item.is_folder else 1, -str(item.target).count("/"), str(item.original))

    renamed: list[tuple[Path, Path]] = []
    for item in sorted(plan.items, key=sort_key):
        if item.original == item.target:
            continue
        if item.target.exists():
            raise ValueError(f"Target already exists: {item.target}")
        item.target.parent.mkdir(parents=True, exist_ok=True)
        item.original.rename(item.target)
        renamed.append((item.original, item.target))
    return renamed