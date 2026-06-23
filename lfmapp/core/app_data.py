"""Application data bootstrap helpers for linux-file-manager."""

from lfmapp.core.config import Config
from lfmapp.core.paths import CONFIG_FILE, CONFIG_DIR, USER_EXTENSIONS_DIR, VAULT_DIR
from lfmapp.services.bookmark_service import ensure_bookmarks_file
from lfmapp.services.tag_service import initialize_tags_db


def ensure_app_data(config: Config | None = None) -> Config:
    """Create the core app data expected to exist after first launch.

    This keeps startup predictable after the user deletes
    ``~/.local/share/linux-file-manager/``. Optional or heavy data such as the
    text index remains lazy and is only created when the related feature is
    actually used.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    cfg = config or Config()
    if not CONFIG_FILE.exists():
        cfg.save()

    ensure_bookmarks_file()
    initialize_tags_db()
    return cfg
