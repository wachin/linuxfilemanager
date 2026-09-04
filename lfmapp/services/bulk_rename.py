"""Bulk rename engine (ROADMAP Phase 6.2).

UI-independent: builds an ``old -> new`` plan from a set of draft names and
a list of ordered, accumulable transformations, validates the plan against
the filesystem and common naming pitfalls, and applies it non-destructively.
Every applied rename is reported back so the caller can record a reversible
``RenameOperation`` per file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class TransformType:
    SEARCH_REPLACE = "search_replace"
    REGEX = "regex"
    PREFIX = "prefix"
    SUFFIX = "suffix"
    NUMBERING = "numbering"
    CASE = "case"


@dataclass(frozen=True)
class Transform:
    """A single accumulable transformation applied left-to-right."""

    type: str
    value: str = ""
    # search/replace options
    search: str = ""
    replace: str = ""
    case_sensitive: bool = False
    # numbering options
    start: int = 1
    digits: int = 1
    increment: int = 1

    def apply_to(self, name: str, parts: "_NameParts", index: int) -> str:
        handler = _TRANSFORM_HANDLERS[self.type]
        return handler(self, name, parts, index)


@dataclass(frozen=True)
class _NameParts:
    stem: str
    extension: str

    @property
    def full(self) -> str:
        return self.stem + self.extension


def split_name(name: str) -> _NameParts:
    """Split a file name into stem and extension (extension includes the dot)."""
    path = Path(name)
    suffixes = path.suffixes
    if not suffixes:
        return _NameParts(name, "")
    if len(suffixes) == 1:
        return _NameParts(path.stem, path.suffix)
    # Multi-part extension like ".tar.gz": keep the last two parts together.
    extension = "".join(suffixes[-2:])
    stem = name[: -len(extension)] if name.endswith(extension) else path.stem
    return _NameParts(stem, extension)


def _apply_search_replace(transform: Transform, name: str, parts: _NameParts, index: int) -> str:
    flags = 0 if transform.case_sensitive else re.IGNORECASE
    search = re.escape(transform.search)
    return re.sub(search, lambda m: transform.replace, name, flags=flags)


def _apply_regex(transform: Transform, name: str, parts: _NameParts, index: int) -> str:
    flags = 0 if transform.case_sensitive else re.IGNORECASE
    try:
        return re.sub(transform.search, transform.replace, name, flags=flags)
    except re.error:
        return name


def _apply_prefix(transform: Transform, name: str, parts: _NameParts, index: int) -> str:
    return transform.value + name


def _apply_suffix(transform: Transform, name: str, parts: _NameParts, index: int) -> str:
    # Insert the suffix before the extension by default (ignore-extension).
    return parts.stem + transform.value + parts.extension if parts.extension else name + transform.value


def _apply_numbering(transform: Transform, name: str, parts: _NameParts, index: int) -> str:
    number = transform.start + index * transform.increment
    formatted = str(number).zfill(transform.digits) if transform.digits > 0 else str(number)
    if transform.value:
        # Replace the first "{n}" placeholder, otherwise append.
        if "{n}" in name:
            return name.replace("{n}", formatted, 1)
        return parts.stem + transform.value + formatted + parts.extension
    return parts.stem + formatted + parts.extension


def _apply_case(transform: Transform, name: str, parts: _NameParts, index: int) -> str:
    mode = transform.value
    if transform.search == "extension":
        # Apply to the extension only.
        ext = parts.extension
        if mode == "upper":
            return parts.stem + ext.upper()
        if mode == "lower":
            return parts.stem + ext.lower()
        return name
    if mode == "upper":
        return name.upper()
    if mode == "lower":
        return name.lower()
    if mode == "title":
        return parts.stem.title() + parts.extension
    return name


_TRANSFORM_HANDLERS = {
    TransformType.SEARCH_REPLACE: _apply_search_replace,
    TransformType.REGEX: _apply_regex,
    TransformType.PREFIX: _apply_prefix,
    TransformType.SUFFIX: _apply_suffix,
    TransformType.NUMBERING: _apply_numbering,
    TransformType.CASE: _apply_case,
}


@dataclass
class PlannedRename:
    original_name: str
    new_name: str
    original_path: Path
    new_path: Path
    changed: bool = False
    conflict: str | None = None
    enabled: bool = True

    @property
    def valid(self) -> bool:
        return self.conflict is None and bool(self.new_name)


@dataclass
class RenamePlan:
    items: list[PlannedRename] = field(default_factory=list)

    @property
    def conflicts(self) -> list[PlannedRename]:
        return [item for item in self.items if item.conflict is not None]


def _is_invalid_name(name: str) -> bool:
    if not name or name in {".", ".."}:
        return True
    if name != name.strip():
        return True
    if "/" in name or "\x00" in name:
        return True
    return False


def _detect_conflict(
    new_name: str,
    original_path: Path,
    existing_names: set[str],
    planned_names: dict[str, Path],
) -> str | None:
    if _is_invalid_name(new_name):
        return "invalid"
    if new_name in planned_names:
        return "duplicate"
    parent = original_path.parent
    target = parent / new_name
    # A target that already exists and is not the item itself is a real conflict.
    if (target.exists() or new_name in existing_names) and new_name != original_path.name:
        return "exists"
    return None


def build_plan(
    paths: list[Path],
    transforms: list[Transform],
) -> RenamePlan:
    """Apply transforms to each path and validate the resulting names."""
    plan = RenamePlan()
    existing_names = {p.name for p in paths}
    planned_names: dict[str, Path] = {}
    original_by_name: dict[str, Path] = {p.name: p for p in paths}

    for index, path in enumerate(paths):
        original_name = path.name
        parts = split_name(original_name)
        new_name = original_name
        for transform in transforms:
            new_name = transform.apply_to(new_name, _NameParts(*_split_current(new_name)), index)

        changed = new_name != original_name
        conflict = _detect_conflict(new_name, path, existing_names, planned_names) if changed else None
        new_path = path.with_name(new_name) if conflict != "invalid" else path

        item = PlannedRename(
            original_name=original_name,
            new_name=new_name,
            original_path=path,
            new_path=new_path,
            changed=changed,
            conflict=conflict,
        )
        if changed and conflict is None:
            planned_names[new_name] = path
        plan.items.append(item)

    return plan


def _split_current(name: str) -> tuple[str, str]:
    parts = split_name(name)
    return parts.stem, parts.extension


def apply_plan(plan: RenamePlan, include_unchanged: bool = False) -> list[tuple[Path, Path]]:
    """Rename files on disk. Returns (old_path, new_path) pairs for changed items.

    Raises ``ValueError`` if any enabled item still has a conflict.
    """
    ordered = sorted(plan.items, key=lambda item: item.original_path)
    renamed: list[tuple[Path, Path]] = []
    for item in ordered:
        if not item.enabled:
            continue
        if item.conflict is not None:
            raise ValueError(f"Unresolved conflict for {item.original_name}: {item.conflict}")
        if not item.changed:
            continue
        item.original_path.rename(item.new_path)
        renamed.append((item.original_path, item.new_path))
    return renamed