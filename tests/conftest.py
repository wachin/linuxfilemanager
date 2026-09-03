"""Shared fixtures for Fase 0.3: critical-flow tests.

Provides a pytest fixture that builds a realistic temporary tree with:
- nested folders and files of several types,
- a symlink (when the platform allows it),
- a file with permissions removed (chmod 000),
- files with Unicode names,
- a hidden dotfile.
"""

import os
import stat
import sys

import pytest


def _make_tree(root):
    """Build the Fase 0.3 sample tree inside root and return its path."""
    root = root / "tree"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "readme.md").write_text("# Hola\n", encoding="utf-8")
    (root / "docs" / "manual.pdf").write_bytes(b"%PDF-1.4 fake")
    (root / "images").mkdir()
    (root / "images" / "foto_ñandú.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    (root / "images" / "foto áéíóú.jpg").write_bytes(b"\xff\xd8\xff\xe0 fake")
    (root / "data.bin").write_bytes(os.urandom(2048))
    (root / ".hidden").write_text("secret", encoding="utf-8")
    (root / "fotos finales").mkdir()  # name with space
    (root / "fotos finales" / "a.txt").write_text("a", encoding="utf-8")
    # Symlink target (skipped on platforms without symlink support).
    target = root / "docs" / "readme.md"
    link = root / "link_to_readme.md"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        link = None
    # A file without any permissions (only where chmod is meaningful).
    locked = root / "no_perm.txt"
    locked.write_text("locked", encoding="utf-8")
    try:
        os.chmod(locked, 0)
    except OSError:
        pass
    return {
        "root": root,
        "symlink": link,
        "locked": locked if os.access(locked, os.W_OK) is False and sys.platform != "win32" else None,
    }


@pytest.fixture
def sample_tree(tmp_path):
    """Return a dict describing the sample tree (see _make_tree)."""
    return _make_tree(tmp_path)


@pytest.fixture
def empty_folder(tmp_path):
    """A fresh, empty folder to use as a destination in copy/move tests."""
    dest = tmp_path / "destino_vacío"
    dest.mkdir()
    return dest


@pytest.fixture
def unicode_only_tree(tmp_path):
    """Tree with only Unicode and space-containing names (edge cases)."""
    root = tmp_path / "ñandú vuelo"
    root.mkdir()
    (root / "árbol de archivos").mkdir()
    (root / "árbol de archivos" / "día soleado.txt").write_text("x", encoding="utf-8")
    (root / "café_naïve.odt").write_text("y", encoding="utf-8")
    return root
