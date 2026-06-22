import tempfile
import unittest
from pathlib import Path

from lfm.services.vault_service import VaultService


class VaultServiceTests(unittest.TestCase):
    def test_plain_vault_keeps_existing_lock_behavior(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = VaultService(Path(tmpdir) / "vault")

            self.assertTrue(vault.initialize())
            self.assertTrue(vault.is_accessible())
            self.assertTrue(vault.lock())
            self.assertFalse(vault.is_accessible())
            self.assertTrue(vault.unlock())
            self.assertTrue(vault.is_accessible())

    def test_encrypted_vault_locks_and_restores_contents_with_password(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_file = root / "secret.txt"
            source_file.write_text("classified vault text", encoding="utf-8")
            source_dir = root / "folder"
            source_dir.mkdir()
            (source_dir / "nested.txt").write_text("nested secret", encoding="utf-8")
            (source_dir / "empty").mkdir()

            vault = VaultService(root / "vault")
            self.assertTrue(vault.initialize(password="correct horse", encrypted=True))
            self.assertTrue(vault.add_file(source_file))
            self.assertTrue(vault.add_file(source_dir))

            self.assertTrue(vault.lock("correct horse"))
            self.assertFalse((vault.vault_path / "secret.txt").exists())
            self.assertFalse((vault.vault_path / "folder").exists())
            encrypted_payload = b"".join(
                path.read_bytes() for path in (vault.vault_path / ".vault_data").iterdir()
            )
            self.assertNotIn(b"classified vault text", encrypted_payload)
            self.assertNotIn(b"nested secret", encrypted_payload)

            self.assertFalse(vault.unlock("wrong horse"))
            self.assertFalse(vault.is_accessible())

            self.assertTrue(vault.unlock("correct horse"))
            self.assertTrue(vault.is_accessible())
            self.assertEqual(
                (vault.vault_path / "secret.txt").read_text(encoding="utf-8"),
                "classified vault text",
            )
            self.assertEqual(
                (vault.vault_path / "folder" / "nested.txt").read_text(encoding="utf-8"),
                "nested secret",
            )
            self.assertTrue((vault.vault_path / "folder" / "empty").is_dir())

    def test_enable_encryption_for_existing_vault(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "note.txt"
            source.write_text("existing content", encoding="utf-8")

            vault = VaultService(root / "vault")
            self.assertTrue(vault.initialize())
            self.assertTrue(vault.add_file(source))
            self.assertFalse(vault.encryption_enabled())

            self.assertTrue(vault.enable_encryption("password"))
            self.assertTrue(vault.encryption_enabled())
            self.assertTrue(vault.lock("password"))
            self.assertTrue(vault.unlock("password"))
            self.assertEqual(
                (vault.vault_path / "note.txt").read_text(encoding="utf-8"),
                "existing content",
            )


if __name__ == "__main__":
    unittest.main()
