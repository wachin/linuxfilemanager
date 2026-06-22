"""Network location discovery for linux-file-manager."""

import os
from pathlib import Path


NETWORK_FILESYSTEM_TYPES = {
    "cifs",
    "smb3",
    "nfs",
    "nfs4",
    "sshfs",
    "fuse.sshfs",
    "davfs",
    "fuse.gvfsd-fuse",
}


def _decode_mount_path(path: str) -> Path:
    return Path(path.replace("\\040", " "))


def gvfs_root_for_user(uid: int | None = None) -> Path:
    """Return the GVfs mount root for a user."""
    return Path("/run/user") / str(os.getuid() if uid is None else uid) / "gvfs"


def discover_gvfs_locations(gvfs_root: Path | None = None) -> list[Path]:
    """Return mounted GVfs network locations."""
    root = Path(gvfs_root) if gvfs_root is not None else gvfs_root_for_user()
    if not root.is_dir():
        return []

    locations = []
    try:
        for path in root.iterdir():
            if path.exists():
                locations.append(path)
    except OSError:
        return []
    return sorted(locations, key=lambda path: str(path).lower())


def discover_proc_mount_network_locations(proc_mounts: Path | None = None) -> list[Path]:
    """Return network filesystem mount points from a proc mounts file."""
    mounts_file = Path(proc_mounts or "/proc/mounts")
    try:
        lines = mounts_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    locations = []
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        mount_point = _decode_mount_path(parts[1])
        filesystem_type = parts[2]
        if filesystem_type in NETWORK_FILESYSTEM_TYPES:
            locations.append(mount_point)

    return sorted(locations, key=lambda path: str(path).lower())


def discover_network_locations(
    gvfs_root: Path | None = None,
    proc_mounts: Path | None = None,
) -> list[Path]:
    """Return discovered network locations without duplicates."""
    locations = []
    seen = set()
    for path in (
        *discover_gvfs_locations(gvfs_root),
        *discover_proc_mount_network_locations(proc_mounts),
    ):
        key = str(path)
        if key not in seen:
            seen.add(key)
            locations.append(path)
    return locations
