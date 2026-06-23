"""Tag service for linux-file-manager.

Uses SQLite for persistent file tagging.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from lfmapp.core.paths import CONFIG_DIR

TAGS_DB_FILE = CONFIG_DIR / "tags.db"


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create the tag database schema."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
            UNIQUE(file_path, tag_id)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_tags_path
        ON file_tags(file_path)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_tags_tag
        ON file_tags(tag_id)
    """)
    conn.commit()


def initialize_tags_db(db_file: Path | None = None) -> Path:
    """Create the SQLite tag database and schema if they do not exist."""
    target = Path(db_file) if db_file is not None else TAGS_DB_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    try:
        _create_schema(conn)
    finally:
        conn.close()
    return target


class TagService:
    """Manages file tags using SQLite."""

    def __init__(self, db_file: Path | None = None):
        self._db_file = Path(db_file) if db_file is not None else TAGS_DB_FILE
        self._db_file.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_file))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist."""
        _create_schema(self._conn)

    def close(self):
        """Close the database connection."""
        self._conn.close()

    # --- Tag operations ---

    def create_tag(self, name: str, color: Optional[str] = None) -> int:
        """Create a new tag. Returns the tag ID."""
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO tags (name, color) VALUES (?, ?)",
            (name, color)
        )
        self._conn.commit()
        cursor.execute("SELECT id FROM tags WHERE name = ?", (name,))
        row = cursor.fetchone()
        return row["id"]

    def list_tags(self) -> list[dict]:
        """List all tags. Returns list of dicts with keys: id, name, color, count."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT t.id, t.name, t.color, COUNT(ft.file_path) as count
            FROM tags t
            LEFT JOIN file_tags ft ON t.id = ft.tag_id
            GROUP BY t.id
            ORDER BY t.name
        """)
        return [dict(row) for row in cursor.fetchall()]

    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag by ID. Also removes all file associations."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM file_tags WHERE tag_id = ?", (tag_id,))
        cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def rename_tag(self, tag_id: int, new_name: str) -> bool:
        """Rename a tag."""
        cursor = self._conn.cursor()
        cursor.execute("UPDATE tags SET name = ? WHERE id = ?", (new_name, tag_id))
        self._conn.commit()
        return cursor.rowcount > 0

    def set_tag_color(self, tag_id: int, color: Optional[str]) -> bool:
        """Set or clear a tag color."""
        cursor = self._conn.cursor()
        cursor.execute("UPDATE tags SET color = ? WHERE id = ?", (color, tag_id))
        self._conn.commit()
        return cursor.rowcount > 0

    # --- File-tag operations ---

    def add_tag_to_file(self, file_path: str, tag_name: str) -> bool:
        """Add a tag to a file. Creates the tag if it doesn't exist."""
        tag_id = self.create_tag(tag_name)
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO file_tags (file_path, tag_id) VALUES (?, ?)",
                (str(file_path), tag_id)
            )
            self._conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False

    def remove_tag_from_file(self, file_path: str, tag_name: str) -> bool:
        """Remove a tag from a file."""
        cursor = self._conn.cursor()
        cursor.execute(
            "DELETE FROM file_tags WHERE file_path = ? AND tag_id = "
            "(SELECT id FROM tags WHERE name = ?)",
            (str(file_path), tag_name)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def get_tags_for_file(self, file_path: str) -> list[dict]:
        """Get all tags for a file. Returns list of dicts with keys: id, name, color."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT t.id, t.name, t.color
            FROM tags t
            INNER JOIN file_tags ft ON t.id = ft.tag_id
            WHERE ft.file_path = ?
            ORDER BY t.name
        """, (str(file_path),))
        return [dict(row) for row in cursor.fetchall()]

    def get_files_for_tag(self, tag_name: str) -> list[str]:
        """Get all file paths that have a specific tag."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT ft.file_path
            FROM file_tags ft
            INNER JOIN tags t ON ft.tag_id = t.id
            WHERE t.name = ?
            ORDER BY ft.file_path
        """, (tag_name,))
        return [row["file_path"] for row in cursor.fetchall()]

    def search_by_tags(self, tag_names: list[str], match_all: bool = False) -> list[str]:
        """Search files by tags.

        If match_all is True, return files that have ALL specified tags.
        If match_all is False, return files that have ANY of the specified tags.
        """
        if not tag_names:
            return []

        cursor = self._conn.cursor()
        placeholders = ",".join("?" for _ in tag_names)

        if match_all:
            cursor.execute(f"""
                SELECT ft.file_path
                FROM file_tags ft
                INNER JOIN tags t ON ft.tag_id = t.id
                WHERE t.name IN ({placeholders})
                GROUP BY ft.file_path
                HAVING COUNT(DISTINCT t.name) = ?
            """, tag_names + [len(tag_names)])
        else:
            cursor.execute(f"""
                SELECT DISTINCT ft.file_path
                FROM file_tags ft
                INNER JOIN tags t ON ft.tag_id = t.id
                WHERE t.name IN ({placeholders})
                ORDER BY ft.file_path
            """, tag_names)

        return [row["file_path"] for row in cursor.fetchall()]

    def remove_all_tags_from_file(self, file_path: str) -> int:
        """Remove all tags from a file. Returns number of tags removed."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM file_tags WHERE file_path = ?", (str(file_path),))
        self._conn.commit()
        return cursor.rowcount
