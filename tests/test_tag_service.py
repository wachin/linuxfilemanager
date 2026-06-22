import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lfm.services.tag_service as tag_service_module
from lfm.services.tag_service import TagService


class TagServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_file = self.temp_dir / "tags.db"
        self.patcher = patch("lfm.services.tag_service.TAGS_DB_FILE", self.db_file)
        self.patcher.start()
        self.service = TagService()

    def tearDown(self):
        self.service.close()
        self.patcher.stop()
        for file in self.temp_dir.rglob("*"):
            if file.is_file():
                file.unlink()
        for folder in sorted(self.temp_dir.rglob("*"), reverse=True):
            if folder.is_dir():
                folder.rmdir()
        if self.temp_dir.exists():
            self.temp_dir.rmdir()

    def test_create_and_list_tags(self):
        self.service.create_tag("work")
        self.service.create_tag("personal", color="#00ff00")

        tags = self.service.list_tags()
        self.assertEqual(len(tags), 2)
        self.assertEqual({tag["name"] for tag in tags}, {"personal", "work"})

    def test_add_tag_to_file_and_get_files(self):
        file_path = self.temp_dir / "document.txt"
        file_path.write_text("content", encoding="utf-8")

        added = self.service.add_tag_to_file(str(file_path), "project")
        self.assertTrue(added)

        files = self.service.get_files_for_tag("project")
        self.assertEqual(files, [str(file_path)])

        tags = self.service.get_tags_for_file(str(file_path))
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["name"], "project")

    def test_rename_tag(self):
        self.service.create_tag("old-name")
        tags = self.service.list_tags()
        self.assertEqual(len(tags), 1)
        tag_id = tags[0]["id"]

        renamed = self.service.rename_tag(tag_id, "new-name")
        self.assertTrue(renamed)

        tags = self.service.list_tags()
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["name"], "new-name")

    def test_set_tag_color(self):
        tag_id = self.service.create_tag("colorful")

        updated = self.service.set_tag_color(tag_id, "#ff0000")

        self.assertTrue(updated)
        tags = self.service.list_tags()
        self.assertEqual(tags[0]["color"], "#ff0000")

        cleared = self.service.set_tag_color(tag_id, None)

        self.assertTrue(cleared)
        tags = self.service.list_tags()
        self.assertIsNone(tags[0]["color"])

    def test_delete_tag(self):
        self.service.create_tag("temp-tag")
        tags = self.service.list_tags()
        self.assertEqual(len(tags), 1)
        tag_id = tags[0]["id"]

        deleted = self.service.delete_tag(tag_id)
        self.assertTrue(deleted)
        self.assertEqual(self.service.list_tags(), [])

    def test_remove_tag_from_file(self):
        file_path = self.temp_dir / "image.png"
        file_path.write_text("binarydata", encoding="utf-8")

        self.service.add_tag_to_file(str(file_path), "photos")
        removed = self.service.remove_tag_from_file(str(file_path), "photos")

        self.assertTrue(removed)
        self.assertEqual(self.service.get_files_for_tag("photos"), [])

    def test_search_by_tags_match_any(self):
        one = self.temp_dir / "one.txt"
        two = self.temp_dir / "two.txt"
        one.write_text("1", encoding="utf-8")
        two.write_text("2", encoding="utf-8")

        self.service.add_tag_to_file(str(one), "red")
        self.service.add_tag_to_file(str(two), "blue")
        self.service.add_tag_to_file(str(two), "red")

        results = self.service.search_by_tags(["red"])
        self.assertEqual(set(results), {str(one), str(two)})

        results = self.service.search_by_tags(["blue"])
        self.assertEqual(results, [str(two)])

    def test_search_by_tags_match_all(self):
        one = self.temp_dir / "one.txt"
        two = self.temp_dir / "two.txt"
        one.write_text("1", encoding="utf-8")
        two.write_text("2", encoding="utf-8")

        self.service.add_tag_to_file(str(one), "red")
        self.service.add_tag_to_file(str(one), "blue")
        self.service.add_tag_to_file(str(two), "red")

        results = self.service.search_by_tags(["red", "blue"], match_all=True)
        self.assertEqual(results, [str(one)])

    def test_remove_all_tags_from_file(self):
        file_path = self.temp_dir / "notes.txt"
        file_path.write_text("hello", encoding="utf-8")

        self.service.add_tag_to_file(str(file_path), "archive")
        self.service.add_tag_to_file(str(file_path), "important")

        removed_count = self.service.remove_all_tags_from_file(str(file_path))
        self.assertEqual(removed_count, 2)
        self.assertEqual(self.service.get_tags_for_file(str(file_path)), [])


if __name__ == "__main__":
    unittest.main()
