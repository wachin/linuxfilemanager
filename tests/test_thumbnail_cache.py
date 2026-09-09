"""Tests for the thumbnail disk cache (backlog P2).

Covers:
- Pure helpers: canonical_uri, cache_key, cache_filename, cache_path, is_supported_image.
- Thumbnail generation: _generate_thumbnail_bytes produces valid PNG.
- Disk I/O: write_thumbnail, read_thumbnail, freshness validation.
- Cache management: cleanup_cache, cache_stats.
- Failure recording: _record_failure.
"""

import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

from lfmapp.services.thumbnail_cache_service import (
    _CACHE_ROOT,
    _generate_thumbnail_bytes,
    _record_failure,
    cache_filename,
    cache_key,
    cache_path,
    cache_stats,
    canonical_uri,
    cleanup_cache,
    is_supported_image,
    read_thumbnail,
    write_thumbnail,
)


def _make_image(path: Path, size: tuple[int, int] = (200, 200), color: str = "red") -> None:
    """Create a minimal test image at *path*."""
    img = Image.new("RGB", size, color=color)
    img.save(path)


class CanonicalUriTests(unittest.TestCase):
    def test_local_file(self):
        uri = canonical_uri(Path("/home/user/photo.jpg"))
        self.assertTrue(uri.startswith("file:///"))
        self.assertIn("photo.jpg", uri)

    def test_no_trailing_slash(self):
        uri = canonical_uri(Path("/tmp"))
        self.assertFalse(uri.endswith("/"))


class CacheKeyTests(unittest.TestCase):
    def test_deterministic(self):
        uri = "file:///home/user/photo.jpg"
        self.assertEqual(cache_key(uri), cache_key(uri))

    def test_different_uris_different_keys(self):
        k1 = cache_key("file:///a.txt")
        k2 = cache_key("file:///b.txt")
        self.assertNotEqual(k1, k2)

    def test_length(self):
        k = cache_key("file:///test")
        self.assertEqual(len(k), 32)  # MD5 hex digest


class CacheFilenameTests(unittest.TestCase):
    def test_ends_with_png(self):
        self.assertTrue(cache_filename("file:///test").endswith(".png"))

    def test_length(self):
        fn = cache_filename("file:///test")
        # 32 hex + ".png" = 36
        self.assertEqual(len(fn), 36)


class CachePathTests(unittest.TestCase):
    def test_normal_path(self):
        p = cache_path("file:///test", large=False)
        self.assertIn("normal", str(p))

    def test_large_path(self):
        p = cache_path("file:///test", large=True)
        self.assertIn("large", str(p))


class IsSupportedImageTests(unittest.TestCase):
    def test_supported(self):
        for ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"):
            self.assertTrue(is_supported_image(Path(f"test{ext}")), f"{ext} should be supported")

    def test_unsupported(self):
        for ext in (".txt", ".pdf", ".py", ".mp4", ".zip"):
            self.assertFalse(is_supported_image(Path(f"test{ext}")), f"{ext} should not be supported")

    def test_case_insensitive(self):
        self.assertTrue(is_supported_image(Path("test.JPG")))
        self.assertTrue(is_supported_image(Path("test.Png")))


class GenerateThumbnailBytesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)

    def test_generates_valid_png(self):
        src = self.root / "img.jpg"
        _make_image(src, (300, 300))
        data = _generate_thumbnail_bytes(src, 128)
        self.assertIsNotNone(data)
        img = Image.open(__import__("io").BytesIO(data))
        self.assertEqual(img.format, "PNG")
        self.assertLessEqual(max(img.size), 128)

    def test_preserves_aspect_ratio(self):
        src = self.root / "wide.jpg"
        _make_image(src, (400, 200))
        data = _generate_thumbnail_bytes(src, 128)
        self.assertIsNotNone(data)
        img = Image.open(__import__("io").BytesIO(data))
        w, h = img.size
        self.assertLessEqual(w, 128)
        self.assertLessEqual(h, 128)
        self.assertAlmostEqual(w / h, 2.0, places=1)

    def test_nonexistent_returns_none(self):
        result = _generate_thumbnail_bytes(self.root / "nope.jpg", 128)
        self.assertIsNone(result)


class WriteReadThumbnailTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.src = self.root / "photo.jpg"
        _make_image(self.src, (300, 300))
        self.uri = canonical_uri(self.src)
        # Patch _CACHE_ROOT to use temp dir.
        import lfmapp.services.thumbnail_cache_service as svc
        self._orig_root = svc._CACHE_ROOT
        svc._CACHE_ROOT = Path(self._tmp) / "thumb_cache"
        self.addCleanup(setattr, svc, "_CACHE_ROOT", self._orig_root)

    def test_write_and_read(self):
        self.assertTrue(write_thumbnail(self.src, self.uri))
        data = read_thumbnail(self.src, self.uri)
        self.assertIsNotNone(data)
        img = Image.open(__import__("io").BytesIO(data))
        self.assertEqual(img.format, "PNG")

    def test_read_returns_none_on_miss(self):
        data = read_thumbnail(self.src, "file:///nonexistent")
        self.assertIsNone(data)

    def test_stale_mtime_invalidates(self):
        """If the source file's mtime changes, the cached entry is invalidated."""
        self.assertTrue(write_thumbnail(self.src, self.uri))
        # Change mtime to a different value (set explicitly to avoid sub-second issues).
        old_mtime = self.src.stat().st_mtime
        os.utime(self.src, (old_mtime + 10, old_mtime + 10))
        data = read_thumbnail(self.src, self.uri)
        self.assertIsNone(data)  # cache invalidated

    def test_stale_size_invalidates(self):
        """If the source file's size changes, the cached entry is invalidated."""
        self.assertTrue(write_thumbnail(self.src, self.uri))
        self.src.write_bytes(b"extra content here")
        data = read_thumbnail(self.src, self.uri)
        self.assertIsNone(data)

    def test_wrong_uri_invalidates(self):
        """If the cached URI doesn't match, the entry is invalidated."""
        self.assertTrue(write_thumbnail(self.src, self.uri))
        data = read_thumbnail(self.src, "file:///wrong/uri")
        self.assertIsNone(data)

    def test_unsupported_extension_skipped(self):
        txt = self.root / "notes.txt"
        txt.write_text("hello")
        self.assertFalse(write_thumbnail(txt, canonical_uri(txt)))

    def test_large_thumbnail(self):
        self.assertTrue(write_thumbnail(self.src, self.uri, large=True))
        data = read_thumbnail(self.src, self.uri, large=True)
        self.assertIsNotNone(data)
        img = Image.open(__import__("io").BytesIO(data))
        self.assertLessEqual(max(img.size), 256)

    def test_failed_source_records_failure(self):
        """A corrupt file should be recorded as a failure, not generate a thumbnail."""
        corrupt = self.root / "corrupt.jpg"
        corrupt.write_bytes(b"not an image")
        self.assertFalse(write_thumbnail(corrupt, canonical_uri(corrupt)))
        # The failure file should exist.
        key = cache_key(canonical_uri(corrupt))
        fail_path = Path(self._tmp) / "thumb_cache" / "fail" / (key + ".png")
        self.assertTrue(fail_path.exists())


class CleanupCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        import lfmapp.services.thumbnail_cache_service as svc
        self._orig_root = svc._CACHE_ROOT
        svc._CACHE_ROOT = Path(self._tmp)
        self.addCleanup(setattr, svc, "_CACHE_ROOT", self._orig_root)

    def test_removes_oldest_when_over_limit(self):
        """Create several small thumbnails and verify cleanup removes oldest."""
        normal_dir = Path(self._tmp) / "normal"
        normal_dir.mkdir(parents=True)
        # Create 5 tiny files.
        for i in range(5):
            (normal_dir / f"{i:032x}.png").write_bytes(b"\x89PNG" + b"\x00" * 100)
            time.sleep(0.01)  # ensure different mtimes
        # Set a very small limit.
        removed = cleanup_cache(max_size_mb=0)
        # With limit 0, all should be removed.
        remaining = list(normal_dir.glob("*.png"))
        self.assertEqual(len(remaining), 0)
        self.assertGreater(removed, 0)


class CacheStatsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        import lfmapp.services.thumbnail_cache_service as svc
        self._orig_root = svc._CACHE_ROOT
        svc._CACHE_ROOT = Path(self._tmp)
        self.addCleanup(setattr, svc, "_CACHE_ROOT", self._orig_root)

    def test_empty_cache(self):
        stats = cache_stats()
        self.assertEqual(stats["total_count"], 0)
        self.assertEqual(stats["total_bytes"], 0)

    def test_counts_entries(self):
        normal_dir = Path(self._tmp) / "normal"
        normal_dir.mkdir(parents=True)
        (normal_dir / "a.png").write_bytes(b"\x89PNG" + b"\x00" * 50)
        (normal_dir / "b.png").write_bytes(b"\x89PNG" + b"\x00" * 60)
        stats = cache_stats()
        self.assertEqual(stats["normal"]["count"], 2)
        self.assertEqual(stats["total_count"], 2)


if __name__ == "__main__":
    unittest.main()
