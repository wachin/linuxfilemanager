"""Pluggable indexing backend for linux-file-manager.

Provides an `IndexService` with a default SQLite FTS5 backend and a fallback
to simple SQLite tables when FTS5 is not available.
"""

from __future__ import annotations

import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from lfmapp.core.paths import CONFIG_DIR


INDEX_DB = CONFIG_DIR / "fulltext_index.db"


class IndexBackend(ABC):
    @abstractmethod
    def index_file(self, path: Path) -> None:
        pass

    @abstractmethod
    def remove_file(self, path: Path) -> None:
        pass

    @abstractmethod
    def index_folder(self, root: Path, recursive: bool = True, limit: int = 50000) -> int:
        pass

    @abstractmethod
    def search(self, query: str, folder: Optional[Path] = None, limit: int = 100) -> List[Path]:
        pass


class SQLiteFTSBackend(IndexBackend):
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path is not None else INDEX_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._use_fts = self._ensure_schema()

    def _ensure_schema(self) -> bool:
        cur = self._conn.cursor()
        # Try to create an FTS5 virtual table; if fails, fall back to plain table
        try:
            cur.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS file_index USING fts5(
                    path UNINDEXED, name, content, folder UNINDEXED, mtime UNINDEXED
                )
                """
            )
            self._conn.commit()
            return True
        except sqlite3.OperationalError:
            # FTS5 not available — create fallback tables and indices
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS file_index (
                    path TEXT PRIMARY KEY,
                    name TEXT,
                    content TEXT,
                    folder TEXT,
                    mtime REAL
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_file_index_name ON file_index(name)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_file_index_folder ON file_index(folder)")
            self._conn.commit()
            return False

    def _is_text_file(self, path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                chunk = f.read(4096)
            # crude heuristic: if NUL byte present, treat as binary
            return b"\x00" not in chunk
        except OSError:
            return False

    def index_file(self, path: Path) -> None:
        try:
            path = path.resolve()
            name = path.name
            mtime = path.stat().st_mtime
            folder = str(path.parent)

            content = ""
            if path.is_file() and self._is_text_file(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read(200_000)
                except OSError:
                    content = ""

            cur = self._conn.cursor()
            if self._use_fts:
                cur.execute(
                    "INSERT OR REPLACE INTO file_index (path, name, content, folder, mtime) VALUES (?, ?, ?, ?, ?)",
                    (str(path), name, content, folder, mtime),
                )
            else:
                cur.execute(
                    "INSERT OR REPLACE INTO file_index (path, name, content, folder, mtime) VALUES (?, ?, ?, ?, ?)",
                    (str(path), name.lower(), content, folder, mtime),
                )
            self._conn.commit()
        except Exception:
            # keep indexing robust — ignore failures per-file
            return

    def remove_file(self, path: Path) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM file_index WHERE path = ?", (str(path),))
        self._conn.commit()

    def index_folder(self, root: Path, recursive: bool = True, limit: int = 50000) -> int:
        root = root.resolve()
        cur = self._conn.cursor()
        # remove existing entries for folder
        cur.execute("DELETE FROM file_index WHERE folder = ?", (str(root),))
        count = 0
        walker: Iterable[Path]
        if recursive:
            walker = root.rglob("*")
        else:
            walker = root.iterdir()

        for p in walker:
            if count >= limit:
                break
            try:
                if p.is_file():
                    self.index_file(p)
                    count += 1
            except (OSError, PermissionError):
                continue

        return count

    def search(self, query: str, folder: Optional[Path] = None, limit: int = 100) -> List[Path]:
        cur = self._conn.cursor()
        results: List[Path] = []
        if self._use_fts:
            # use MATCH against name/content
            q = query.strip()
            stmt = "SELECT path FROM file_index WHERE file_index MATCH ?"
            if folder is not None:
                stmt += " AND folder = ?"
                cur.execute(stmt + " LIMIT ?", (q, str(folder.resolve()), limit))
            else:
                cur.execute(stmt + " LIMIT ?", (q, limit))
            rows = cur.fetchall()
            for r in rows:
                results.append(Path(r["path"]))
        else:
            q = f"%{query.lower()}%"
            if folder is None:
                cur.execute("SELECT path FROM file_index WHERE name LIKE ? OR content LIKE ? LIMIT ?", (q, q, limit))
            else:
                cur.execute(
                    "SELECT path FROM file_index WHERE folder = ? AND (name LIKE ? OR content LIKE ?) LIMIT ?",
                    (str(folder.resolve()), q, q, limit),
                )
            for r in cur.fetchall():
                results.append(Path(r[0]))

        return results


@dataclass
class IndexService:
    backend: IndexBackend

    @classmethod
    def default(cls, db_path: Optional[Path] = None) -> "IndexService":
        return cls(SQLiteFTSBackend(db_path=db_path))

    def index_folder(self, root: Path, recursive: bool = True, limit: int = 50000) -> int:
        return self.backend.index_folder(root, recursive=recursive, limit=limit)

    def index_file(self, path: Path) -> None:
        return self.backend.index_file(path)

    def remove_file(self, path: Path) -> None:
        return self.backend.remove_file(path)

    def search(self, query: str, folder: Optional[Path] = None, limit: int = 100) -> List[Path]:
        return self.backend.search(query, folder=folder, limit=limit)
