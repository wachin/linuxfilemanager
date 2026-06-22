"""Text indexing service for linux-file-manager.

Provides optional folder indexing and fast name search.
"""

import os
import sqlite3
from pathlib import Path
from typing import List

from lfmapp.core.paths import CONFIG_DIR

TEXT_INDEX_DB = CONFIG_DIR / "text_index.db"


class TextIndexService:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else TEXT_INDEX_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS indexed_files (
                path TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mtime REAL NOT NULL,
                folder TEXT NOT NULL
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexed_files_name ON indexed_files(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexed_files_folder ON indexed_files(folder)")
        self._conn.commit()

    def close(self):
        self._conn.close()

    def index_folder(self, root: Path, recursive: bool = True, limit: int = 50000) -> int:
        root = root.resolve()
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM indexed_files WHERE folder = ?", (str(root),))

        count = 0
        if recursive:
            walker = root.rglob("*")
        else:
            walker = root.iterdir()

        for path in walker:
            if count >= limit:
                break
            try:
                if path.is_file():
                    cursor.execute(
                        "INSERT OR REPLACE INTO indexed_files (path, name, mtime, folder) VALUES (?, ?, ?, ?)",
                        (str(path), path.name.lower(), path.stat().st_mtime, str(root)),
                    )
                    count += 1
            except (OSError, PermissionError):
                continue

        self._conn.commit()
        return count

    def search(self, query: str, folder: Path = None, limit: int = 300) -> List[str]:
        query = f"%{query.lower()}%"
        cursor = self._conn.cursor()
        if folder is None:
            cursor.execute(
                "SELECT path FROM indexed_files WHERE name LIKE ? ORDER BY name LIMIT ?",
                (query, limit),
            )
        else:
            cursor.execute(
                "SELECT path FROM indexed_files WHERE folder = ? AND name LIKE ? ORDER BY name LIMIT ?",
                (str(folder.resolve()), query, limit),
            )
        return [row["path"] for row in cursor.fetchall()]

    def clear_index(self, folder: Path = None) -> int:
        cursor = self._conn.cursor()
        if folder is None:
            cursor.execute("DELETE FROM indexed_files")
        else:
            cursor.execute("DELETE FROM indexed_files WHERE folder = ?", (str(folder.resolve()),))
        deleted = cursor.rowcount
        self._conn.commit()
        return deleted
