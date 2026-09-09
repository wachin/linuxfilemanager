"""Disk thumbnail cache following the freedesktop.org Thumbnail Specification.

https://specifications.freedesktop.org/thumbnail-spec/latest/

Directory layout::

    ~/.cache/thumbnails/normal/    # 128×128 max (standard)
    ~/.cache/thumbnails/large/     # 256×256
    ~/.cache/thumbnails/fail/      # records of files that failed to thumbnail

File naming: ``{MD5(canonical_uri)}.png``

Metadata embedded as PNG tEXt chunks: ``Thumb::URI``, ``Thumb::MTime``,
``Thumb::Size``.

The service is a thin, stateless helper — pure functions for key computation,
disk I/O and validation, plus a small ``ThumbnailDiskCache`` class that wraps
the directory root and size limits.  It intentionally does **not** depend on
Qt so that it is testable without a display server.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image
from PIL.PngImagePlugin import PngInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CACHE_ROOT = Path.home() / ".cache" / "thumbnails"
_NORMAL_DIR = "normal"   # 128×128 max
_LARGE_DIR = "large"     # 256×256

# Supported image extensions (matches the model's set).
_IMAGE_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp",
}

# Default limits.
_MAX_CACHE_SIZE_MB = 256        # total size of our thumbnails on disk
_MAX_FILE_AGE_DAYS = 90         # delete entries older than this on cleanup
_NORMAL_MAX_PX = 128
_LARGE_MAX_PX = 256


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def canonical_uri(path: Path) -> str:
    """Return the freedesktop-canonical URI for *path*.

    ``file:///absolute/path`` — three slashes for local files, no trailing
    slash for directories.
    """
    return "file://" + str(path.resolve())


def cache_key(uri: str) -> str:
    """Return the 32-char hex MD5 of *uri* (freedesktop filename stem)."""
    return hashlib.md5(uri.encode("utf-8")).hexdigest()


def cache_filename(uri: str) -> str:
    """Return the full PNG filename for *uri* in the cache."""
    return cache_key(uri) + ".png"


def cache_path(uri: str, *, large: bool = False) -> Path:
    """Return the full filesystem path for the cached thumbnail of *uri*."""
    sub = _LARGE_DIR if large else _NORMAL_DIR
    return _CACHE_ROOT / sub / cache_filename(uri)


def is_supported_image(path: Path) -> bool:
    """Return *True* if *path* has an extension we can thumbnail."""
    return path.suffix.lower() in _IMAGE_EXTENSIONS


# ---------------------------------------------------------------------------
# Pure generation helpers (no disk I/O)
# ---------------------------------------------------------------------------

def _generate_thumbnail_bytes(
    source: Path,
    max_px: int,
    uri: str = "",
    mtime: float = 0.0,
    size: int = 0,
) -> bytes | None:
    """Read *source*, resize to *max_px*×*max_px*, return PNG bytes with metadata.

    Returns *None* on failure (corrupt image, unsupported format, …).
    """
    try:
        img = Image.open(source)
        img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        meta = _build_metadata(uri, mtime, size) if uri else PngInfo()
        buf = __import__("io").BytesIO()
        img.save(buf, format="PNG", optimize=True, pnginfo=meta)
        return buf.getvalue()
    except Exception:
        logger.debug("Failed to generate thumbnail for %s", source, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Disk I/O helpers
# ---------------------------------------------------------------------------

def _ensure_dirs() -> None:
    """Create the cache directories if they don't exist."""
    for sub in (_NORMAL_DIR, _LARGE_DIR, "fail"):
        d = _CACHE_ROOT / sub
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(d, 0o700)
            except OSError:
                pass


def _build_metadata(
    uri: str,
    mtime: float,
    size: int,
) -> PngInfo:
    """Build PNG tEXt metadata for the freedesktop thumbnail."""
    info = PngInfo()
    info.add_text("Thumb::URI", uri)
    info.add_text("Thumb::MTime", str(int(mtime)))
    info.add_text("Thumb::Size", str(size))
    info.add_text("Software", "Linux File Manager")
    return info


def write_thumbnail(
    source: Path,
    uri: str,
    *,
    large: bool = False,
) -> bool:
    """Generate a thumbnail for *source* and write it to the disk cache.

    Returns *True* on success.
    """
    if not is_supported_image(source):
        return False

    try:
        stat = source.stat()
    except OSError:
        return False

    max_px = _LARGE_MAX_PX if large else _NORMAL_MAX_PX
    png_bytes = _generate_thumbnail_bytes(
        source, max_px, uri=uri, mtime=stat.st_mtime, size=stat.st_size,
    )
    if png_bytes is None:
        _record_failure(uri)
        return False

    _ensure_dirs()
    dest = cache_path(uri, large=large)
    try:
        # Write atomically via a temp file.
        tmp = dest.with_suffix(".tmp")
        with open(tmp, "wb") as fh:
            fh.write(png_bytes)
        tmp.replace(dest)
        os.chmod(dest, 0o600)
        return True
    except OSError:
        logger.debug("Failed to write thumbnail %s", dest, exc_info=True)
        return False


def read_thumbnail(
    source: Path,
    uri: str,
    *,
    large: bool = False,
) -> Optional[bytes]:
    """Read the cached thumbnail for *uri*, validating freshness.

    Returns the raw PNG bytes if the cache entry is valid, *None* otherwise.
    """
    dest = cache_path(uri, large=large)
    if not dest.exists():
        return None

    try:
        stat = source.stat()
    except OSError:
        # Source gone — remove stale entry.
        _remove_if_exists(dest)
        return None

    try:
        with Image.open(dest) as img:
            meta = img.info or {}
            cached_mtime = int(meta.get("Thumb::MTime", "0"))
            cached_size = int(meta.get("Thumb::Size", "0"))
            cached_uri = meta.get("Thumb::URI", "")
    except Exception:
        _remove_if_exists(dest)
        return None

    # Validate freshness.
    if cached_uri != uri:
        _remove_if_exists(dest)
        return None
    if cached_mtime != int(stat.st_mtime):
        _remove_if_exists(dest)
        return None
    if cached_size != 0 and cached_size != stat.st_size:
        _remove_if_exists(dest)
        return None

    try:
        return dest.read_bytes()
    except OSError:
        return None


def _record_failure(uri: str) -> None:
    """Record that thumbnail generation failed for *uri*."""
    _ensure_dirs()
    fail_dir = _CACHE_ROOT / "fail"
    key = cache_key(uri)
    fail_file = fail_dir / (key + ".png")
    try:
        # Empty file with the right name; spec says "MTime" should be set.
        fail_file.touch(exist_ok=True)
        os.chmod(fail_file, 0o600)
    except OSError:
        pass


def _remove_if_exists(path: Path) -> None:
    """Silently remove *path* if it exists."""
    try:
        path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def cleanup_cache(max_size_mb: int = _MAX_CACHE_SIZE_MB) -> int:
    """Remove oldest entries until total cache size ≤ *max_size_mb*.

    Returns the number of entries removed.
    """
    _ensure_dirs()
    entries: list[Path] = []
    total = 0
    for sub in (_NORMAL_DIR, _LARGE_DIR):
        d = _CACHE_ROOT / sub
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.suffix == ".png":
                try:
                    sz = f.stat().st_size
                    entries.append(f)
                    total += sz
                except OSError:
                    continue

    # Sort oldest first (by mtime).
    entries.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)

    removed = 0
    target = max_size_mb * 1024 * 1024
    while total > target and entries:
        victim = entries.pop(0)
        try:
            sz = victim.stat().st_size
            victim.unlink()
            total -= sz
            removed += 1
        except OSError:
            continue
    return removed


def cache_stats() -> dict:
    """Return summary statistics about the on-disk thumbnail cache."""
    _ensure_dirs()
    stats: dict = {"normal": {"count": 0, "bytes": 0}, "large": {"count": 0, "bytes": 0}}
    for sub, key in ((_NORMAL_DIR, "normal"), (_LARGE_DIR, "large")):
        d = _CACHE_ROOT / sub
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.suffix == ".png":
                try:
                    sz = f.stat().st_size
                    stats[key]["count"] += 1
                    stats[key]["bytes"] += sz
                except OSError:
                    continue
    stats["total_count"] = stats["normal"]["count"] + stats["large"]["count"]
    stats["total_bytes"] = stats["normal"]["bytes"] + stats["large"]["bytes"]
    return stats
