import json
import tempfile
import unittest
from pathlib import Path

from lfmapp.extensions import ExtensionManager


class ExtensionManagerTests(unittest.TestCase):
    def test_discovers_extension_manifests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            extensions_dir = Path(tmpdir)
            extension_dir = extensions_dir / "sample"
            extension_dir.mkdir()
            (extension_dir / "extension.json").write_text(
                json.dumps(
                    {
                        "id": "sample.extension",
                        "name": "Sample Extension",
                        "version": "1.0",
                        "api_version": 1,
                        "description": "Adds sample actions.",
                        "entry_point": "sample_extension:register",
                        "capabilities": ["context-menu"],
                    }
                ),
                encoding="utf-8",
            )

            manager = ExtensionManager(search_paths=[extensions_dir])
            manifests = manager.discover()

        self.assertEqual(len(manifests), 1)
        self.assertEqual(manifests[0].extension_id, "sample.extension")
        self.assertEqual(manifests[0].name, "Sample Extension")
        self.assertEqual(manifests[0].capabilities, ("context-menu",))
        self.assertEqual(manager.errors, [])

    def test_enabled_manifests_return_empty_when_extensions_are_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            extensions_dir = Path(tmpdir)
            extension_dir = extensions_dir / "sample"
            extension_dir.mkdir()
            (extension_dir / "extension.json").write_text(
                json.dumps(
                    {
                        "id": "sample.extension",
                        "name": "Sample Extension",
                        "version": "1.0",
                    }
                ),
                encoding="utf-8",
            )

            manager = ExtensionManager(
                search_paths=[extensions_dir],
                enabled_extensions=["sample.extension"],
                extensions_enabled=False,
            )

            self.assertEqual(manager.enabled_manifests(), [])

    def test_enabled_manifests_only_include_configured_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            extensions_dir = Path(tmpdir)
            for extension_id, name in (
                ("enabled.extension", "Enabled"),
                ("disabled.extension", "Disabled"),
            ):
                extension_dir = extensions_dir / extension_id
                extension_dir.mkdir()
                (extension_dir / "extension.json").write_text(
                    json.dumps(
                        {
                            "id": extension_id,
                            "name": name,
                            "version": "1.0",
                        }
                    ),
                    encoding="utf-8",
                )

            manager = ExtensionManager(
                search_paths=[extensions_dir],
                enabled_extensions=["enabled.extension"],
                extensions_enabled=True,
            )
            manifests = manager.enabled_manifests()

        self.assertEqual(
            [manifest.extension_id for manifest in manifests], ["enabled.extension"]
        )

    def test_invalid_manifests_are_reported_and_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            extensions_dir = Path(tmpdir)
            invalid_dir = extensions_dir / "invalid"
            valid_dir = extensions_dir / "valid"
            invalid_dir.mkdir()
            valid_dir.mkdir()
            (invalid_dir / "extension.json").write_text(
                '{"name": "Missing ID"}', encoding="utf-8"
            )
            (valid_dir / "extension.json").write_text(
                json.dumps(
                    {
                        "id": "valid.extension",
                        "name": "Valid",
                        "version": "1.0",
                    }
                ),
                encoding="utf-8",
            )

            manager = ExtensionManager(search_paths=[extensions_dir])
            manifests = manager.discover()

        self.assertEqual([manifest.extension_id for manifest in manifests], ["valid.extension"])
        self.assertEqual(len(manager.errors), 1)
        self.assertIn("missing id", manager.errors[0])

    def test_first_manifest_wins_for_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_dir = Path(first) / "sample"
            second_dir = Path(second) / "sample"
            first_dir.mkdir()
            second_dir.mkdir()
            for path, name in (
                (first_dir / "extension.json", "First"),
                (second_dir / "extension.json", "Second"),
            ):
                path.write_text(
                    json.dumps(
                        {
                            "id": "sample.extension",
                            "name": name,
                            "version": "1.0",
                        }
                    ),
                    encoding="utf-8",
                )

            manager = ExtensionManager(search_paths=[Path(first), Path(second)])
            manifests = manager.discover()

        self.assertEqual(len(manifests), 1)
        self.assertEqual(manifests[0].name, "First")


if __name__ == "__main__":
    unittest.main()
