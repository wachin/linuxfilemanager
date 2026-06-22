import stat
import tempfile
import unittest
from pathlib import Path

from lfmapp.ui.property_dialog import AdvancedSecurityDialog, PropertyDialog


class PropertyDialogTests(unittest.TestCase):
    def test_permission_state_from_mode(self):
        state = PropertyDialog.permission_state_from_mode(0o754)

        self.assertTrue(state[("user", "read")])
        self.assertTrue(state[("user", "write")])
        self.assertTrue(state[("user", "execute")])
        self.assertTrue(state[("group", "read")])
        self.assertFalse(state[("group", "write")])
        self.assertTrue(state[("group", "execute")])
        self.assertTrue(state[("others", "read")])
        self.assertFalse(state[("others", "write")])
        self.assertFalse(state[("others", "execute")])

    def test_mode_from_permission_state(self):
        state = {
            ("user", "read"): True,
            ("user", "write"): True,
            ("user", "execute"): False,
            ("group", "read"): True,
            ("group", "write"): False,
            ("group", "execute"): False,
            ("others", "read"): False,
            ("others", "write"): False,
            ("others", "execute"): False,
        }

        self.assertEqual(PropertyDialog.mode_from_permission_state(state), 0o640)

    def test_permission_state_round_trip(self):
        state = PropertyDialog.permission_state_from_mode(0o705)

        self.assertEqual(PropertyDialog.mode_from_permission_state(state), 0o705)

    def test_apply_permission_state_to_path_changes_mode_bits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "file.txt"
            path.write_text("content", encoding="utf-8")
            path.chmod(0o600)

            state = PropertyDialog.permission_state_from_mode(0o754)
            new_mode = PropertyDialog.apply_permission_state_to_path(path, state)

            self.assertEqual(stat.S_IMODE(new_mode), 0o754)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o754)

    def test_advanced_security_mode_from_state_includes_special_bits(self):
        permissions = PropertyDialog.permission_state_from_mode(0o755)
        special = {"setuid": False, "setgid": True, "sticky": True}

        mode = AdvancedSecurityDialog.mode_from_security_state(permissions, special)

        self.assertEqual(mode, 0o3755)

    def test_advanced_security_parse_octal_mode(self):
        self.assertEqual(AdvancedSecurityDialog.parse_octal_mode("755"), 0o755)
        self.assertEqual(AdvancedSecurityDialog.parse_octal_mode("1755"), 0o1755)

        with self.assertRaises(ValueError):
            AdvancedSecurityDialog.parse_octal_mode("888")

    def test_advanced_security_apply_mode_to_path_changes_special_bits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "file.txt"
            path.write_text("content", encoding="utf-8")
            path.chmod(0o600)

            new_mode = AdvancedSecurityDialog.apply_mode_to_path(path, 0o1644)

            self.assertEqual(stat.S_IMODE(new_mode), 0o1644)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o1644)


if __name__ == "__main__":
    unittest.main()
