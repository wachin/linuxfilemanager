"""Bulk rename engine (ROADMAP Phase 6.2).

UI-independent: builds an ``old -> new`` plan from a set of draft names and
a list of ordered, accumulable transformations, validates the plan against
the filesystem and common naming pitfalls, and applies it non-destructively.
Every applied rename is reported back so the caller can record a reversible
``RenameOperation`` per file.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


class TransformType:
    SEARCH_REPLACE = "search_replace"
    REGEX = "regex"
    PREFIX = "prefix"
    SUFFIX = "suffix"
    NUMBERING = "numbering"
    CASE = "case"
    DATE = "date"
    EXIF = "exif"
    AUDIO = "audio"
    SANITIZE = "sanitize"


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
    grouped: bool = False
    # metadata options
    field: str = ""
    format: str = ""

    def apply_to(self, name: str, parts: "_NameParts", index: int, path: Path | None = None) -> str:
        handler = _TRANSFORM_HANDLERS[self.type]
        return handler(self, name, parts, index, path)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Transform":
        known = {
            "type", "value", "search", "replace", "case_sensitive",
            "start", "digits", "increment", "grouped", "field", "format",
        }
        return cls(**{k: v for k, v in data.items() if k in known})


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


def _apply_search_replace(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
    flags = 0 if transform.case_sensitive else re.IGNORECASE
    search = re.escape(transform.search)
    return re.sub(search, lambda m: transform.replace, name, flags=flags)


def _apply_regex(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
    flags = 0 if transform.case_sensitive else re.IGNORECASE
    try:
        return re.sub(transform.search, transform.replace, name, flags=flags)
    except re.error:
        return name


def _apply_prefix(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
    return transform.value + name


def _apply_suffix(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
    # Insert the suffix before the extension by default (ignore-extension).
    return parts.stem + transform.value + parts.extension if parts.extension else name + transform.value


def _apply_numbering(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
    number = transform.start + index * transform.increment
    formatted = str(number).zfill(transform.digits) if transform.digits > 0 else str(number)
    if transform.value:
        # Replace the first "{n}" placeholder, otherwise append.
        if "{n}" in name:
            return name.replace("{n}", formatted, 1)
        return parts.stem + transform.value + formatted + parts.extension
    return parts.stem + formatted + parts.extension


def _apply_case(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
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


def _apply_date(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
    if path is None:
        return name
    fmt = transform.format or "%Y-%m-%d"
    try:
        date_text = datetime.fromtimestamp(path.stat().st_mtime).strftime(fmt)
    except (OSError, ValueError):
        return name
    return parts.stem + transform.value + date_text + parts.extension


def _apply_exif(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
    if path is None:
        return name
    date_text = _exif_datetime(path)
    if date_text is None:
        return name
    try:
        fmt = transform.format or "%Y-%m-%d"
        date_text = datetime.strptime(date_text, "%Y:%m:%d %H:%M:%S").strftime(fmt)
    except ValueError:
        pass
    return parts.stem + transform.value + date_text + parts.extension


def _apply_audio(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
    if path is None:
        return name
    value = _audio_metadata(path, transform.field)
    if not value:
        return name
    return parts.stem + transform.value + value + parts.extension


# Characters that commonly break filesystems or desktop sharing.
_INVALID_FILENAME_CHARS = '\\/:*?"<>|'
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
                 "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4",
                 "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Replace characters invalid in file names and trim trailing dots/spaces.

    Operates on the raw string (not via ``split_name``, which reinterprets
    ``/`` as a directory separator). Neutralizes Windows reserved device names
    so generated files can be shared across platforms.
    """
    if not name:
        return replacement
    cleaned = "".join(
        replacement if ch in _INVALID_FILENAME_CHARS or ord(ch) < 32 else ch
        for ch in name
    )
    # Neutralize Windows reserved base names (case-insensitive), e.g. CON.txt.
    dot = cleaned.find(".")
    base = cleaned[:dot] if dot != -1 else cleaned
    if base.strip().upper() in _WIN_RESERVED:
        cleaned = base + replacement + cleaned[dot:]
    result = cleaned.rstrip(" .")
    return result or replacement


def _apply_sanitize(transform: Transform, name: str, parts: _NameParts, index: int, path: Path | None = None) -> str:
    return sanitize_filename(name, transform.value or "_")


def _exif_datetime(path: Path) -> str | None:
    """Return the EXIF DateTimeOriginal of an image, or None."""
    try:
        from PIL import Image

        with Image.open(path) as image:
            exif = image.getexif()
            if not exif:
                return None
            # DateTimeOriginal = 36867, DateTime = 306
            for tag in (36867, 306):
                value = exif.get(tag)
                if value:
                    return str(value)
    except Exception:
        return None
    return None


def _audio_metadata(path: Path, field: str) -> str:
    """Return an audio tag value via mutagen, or the empty string."""
    if not field:
        return ""
    try:
        import mutagen

        audio = mutagen.File(str(path))
        if audio is None or audio.tags is None:
            return ""
    except Exception:
        return ""
    mapping = {
        "title": "title",
        "artist": "artist",
        "album": "album",
        "track": "tracknumber",
        "year": "date",
        "genre": "genre",
    }
    tag = mapping.get(field)
    if not tag:
        return ""
    try:
        value = audio.tags.get(tag)
    except Exception:
        return ""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value)


_TRANSFORM_HANDLERS = {
    TransformType.SEARCH_REPLACE: _apply_search_replace,
    TransformType.REGEX: _apply_regex,
    TransformType.PREFIX: _apply_prefix,
    TransformType.SUFFIX: _apply_suffix,
    TransformType.NUMBERING: _apply_numbering,
    TransformType.CASE: _apply_case,
    TransformType.DATE: _apply_date,
    TransformType.EXIF: _apply_exif,
    TransformType.AUDIO: _apply_audio,
    TransformType.SANITIZE: _apply_sanitize,
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

    # Resolve grouped-numbering indices: files that share the base name (differ
    # only in extension) receive the same number so pairs stay in sync.
    group_index = _compute_group_indices(paths)

    for index, path in enumerate(paths):
        original_name = path.name
        parts = split_name(original_name)
        new_name = original_name
        effective_index = group_index.get(_base_of(path.name), index)
        for transform in transforms:
            idx = effective_index if (transform.type == TransformType.NUMBERING and transform.grouped) else index
            new_name = transform.apply_to(new_name, _NameParts(*_split_current(new_name)), idx, path)

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


def _base_of(name: str) -> str:
    """Return the base name without any extension (photo.jpg -> photo)."""
    parts = split_name(name)
    return parts.stem


def _compute_group_indices(paths: list[Path]) -> dict[str, int]:
    """Map base name -> group index (appearance order of distinct bases)."""
    bases: list[str] = []
    for path in paths:
        base = _base_of(path.name)
        if base not in bases:
            bases.append(base)
    return {base: i for i, base in enumerate(bases)}


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


# ─── Presets ─────────────────────────────────────────────────────


@dataclass
class BulkRenamePreset:
    name: str
    transforms: list[Transform]

    def to_dict(self) -> dict:
        return {"name": self.name, "transforms": [t.to_dict() for t in self.transforms]}

    @classmethod
    def from_dict(cls, data: dict) -> "BulkRenamePreset":
        return cls(
            name=str(data.get("name", "")),
            transforms=[Transform.from_dict(t) for t in data.get("transforms", [])],
        )


def apply_names_list(names: list[str], mode: str, paths: list[Path]) -> dict[Path, str]:
    """Apply a pasted list of names to the given paths.

    ``mode`` is one of ``replace``, ``prefix``, ``suffix``; returns a mapping
    of path -> resulting name. Extra names are ignored; missing names leave the
    original untouched.
    """
    result: dict[Path, str] = {}
    for path, name in zip(paths, names):
        current = path.name
        if mode == "replace":
            new_name = name
        elif mode == "prefix":
            new_name = name + current
        elif mode == "suffix":
            parts = split_name(current)
            new_name = parts.stem + name + parts.extension
        else:
            new_name = current
        result[path] = new_name
    return result