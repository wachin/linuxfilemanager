import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "profile_memory.py"


def load_profile_memory_module():
    spec = importlib.util.spec_from_file_location("profile_memory", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemoryProfileScriptTests(unittest.TestCase):
    def test_configure_isolated_home_sets_xdg_paths(self):
        profile_memory = load_profile_memory_module()
        old_values = {
            key: os.environ.get(key)
            for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")
        }
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                home = Path(tmpdir)
                profile_memory.configure_isolated_home(home)

                self.assertEqual(os.environ["HOME"], str(home))
                self.assertEqual(os.environ["XDG_CONFIG_HOME"], str(home / ".config"))
                self.assertEqual(os.environ["XDG_DATA_HOME"], str(home / ".local" / "share"))
                self.assertEqual(os.environ["XDG_CACHE_HOME"], str(home / ".cache"))
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_parse_args_defaults_to_isolated_offscreen_profile(self):
        profile_memory = load_profile_memory_module()

        args = profile_memory.parse_args([])

        self.assertFalse(args.no_offscreen)
        self.assertFalse(args.use_real_home)
        self.assertIsNone(args.path)


if __name__ == "__main__":
    unittest.main()
