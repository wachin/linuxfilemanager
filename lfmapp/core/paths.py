from pathlib import Path

HOME_DIR = Path.home()
CONFIG_DIR = HOME_DIR / ".local" / "share" / "linux-file-manager"
CONFIG_FILE = CONFIG_DIR / "config.json"
TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "translations"
TRASH_DIR = HOME_DIR / ".local" / "share" / "Trash" / "files"
VAULT_DIR = CONFIG_DIR / "vault"
USER_EXTENSIONS_DIR = CONFIG_DIR / "extensions"
SYSTEM_EXTENSIONS_DIR = Path("/usr/share/linux-file-manager/extensions")
