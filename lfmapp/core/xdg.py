from __future__ import annotations

import os
import re
import subprocess
from collections import OrderedDict
from pathlib import Path

from lfmapp.core.paths import HOME_DIR


XDG_USER_DIR_KEYS = OrderedDict(
    [
        ("desktop", "DESKTOP"),
        ("downloads", "DOWNLOAD"),
        ("documents", "DOCUMENTS"),
        ("music", "MUSIC"),
        ("pictures", "PICTURES"),
        ("videos", "VIDEOS"),
    ]
)

_USER_DIRS_PATTERN = re.compile(r"^XDG_([A-Z_]+)_DIR=(.*)$")


def _expand_xdg_path(value: str, home: Path, env: dict[str, str] | None = None) -> Path:
    env_map = dict(os.environ if env is None else env)
    env_map["HOME"] = str(home)
    expanded = value.strip().strip('"').strip("'").replace("~", str(home), 1)
    for key, env_value in env_map.items():
        expanded = expanded.replace(f"${key}", env_value)
        expanded = expanded.replace(f"${{{key}}}", env_value)
    return Path(expanded).expanduser()


def _read_xdg_user_dir_command(
    xdg_key: str,
    *,
    home: Path,
    env: dict[str, str] | None = None,
) -> Path | None:
    try:
        command_env = dict(os.environ if env is None else env)
        command_env["HOME"] = str(home)
        result = subprocess.run(
            ["xdg-user-dir", xdg_key],
            check=False,
            capture_output=True,
            text=True,
            env=command_env,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    output = result.stdout.strip()
    if not output:
        return None
    return _expand_xdg_path(output, home, env=env)


def _parse_user_dirs_file(
    path: Path,
    *,
    home: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Path]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    parsed: dict[str, Path] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _USER_DIRS_PATTERN.match(line)
        if not match:
            continue
        key, value = match.groups()
        parsed[key.casefold()] = _expand_xdg_path(value, home, env=env)
    return parsed


def get_xdg_user_dirs(
    *,
    home: Path | None = None,
    env: dict[str, str] | None = None,
    user_dirs_file: Path | None = None,
) -> OrderedDict[str, Path]:
    """Return existing XDG user directories following the FreeDesktop spec.

    Resolution priority:
    1. `xdg-user-dir`
    2. `~/.config/user-dirs.dirs`

    Only existing directories are returned, and duplicate resolved paths are omitted.
    """

    home_dir = Path(home) if home is not None else HOME_DIR
    config_file = user_dirs_file or home_dir / ".config" / "user-dirs.dirs"
    file_values = _parse_user_dirs_file(config_file, home=home_dir, env=env)

    resolved_dirs: OrderedDict[str, Path] = OrderedDict()
    seen: set[Path] = set()

    for name, xdg_key in XDG_USER_DIR_KEYS.items():
        path = _read_xdg_user_dir_command(xdg_key, home=home_dir, env=env)
        if path is None:
            path = file_values.get(f"{xdg_key.casefold()}")
        if path is None:
            continue
        if not path.exists() or not path.is_dir():
            continue
        try:
            normalized = path.resolve()
        except OSError:
            normalized = path
        if normalized in seen:
            continue
        seen.add(normalized)
        resolved_dirs[name] = path

    return resolved_dirs


def get_xdg_directory(
    name: str,
    *,
    home: Path | None = None,
    env: dict[str, str] | None = None,
    user_dirs_file: Path | None = None,
) -> Path | None:
    return get_xdg_user_dirs(home=home, env=env, user_dirs_file=user_dirs_file).get(
        str(name).strip().casefold()
    )
