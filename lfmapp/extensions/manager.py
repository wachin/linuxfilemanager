"""Safe extension manifest discovery.

The first extension layer intentionally reads metadata only. Executable plugin
loading can be added later on top of this without changing how extensions are
found or enabled.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from lfmapp.core.paths import SYSTEM_EXTENSIONS_DIR, USER_EXTENSIONS_DIR


class ExtensionDiscoveryError(ValueError):
    """Raised when an extension manifest is present but invalid."""


@dataclass(frozen=True)
class ExtensionManifest:
    extension_id: str
    name: str
    version: str
    api_version: int
    path: Path
    description: str = ""
    entry_point: str | None = None
    capabilities: tuple[str, ...] = ()

    @classmethod
    def from_file(cls, manifest_path: Path) -> "ExtensionManifest":
        try:
            raw_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ExtensionDiscoveryError(f"Invalid JSON in {manifest_path}") from exc

        if not isinstance(raw_data, dict):
            raise ExtensionDiscoveryError(f"Manifest {manifest_path} must contain an object")

        extension_id = _required_text(raw_data, "id", manifest_path)
        name = _required_text(raw_data, "name", manifest_path)
        version = _required_text(raw_data, "version", manifest_path)
        api_version = raw_data.get("api_version", 1)
        if not isinstance(api_version, int) or api_version < 1:
            raise ExtensionDiscoveryError(
                f"Manifest {manifest_path} has invalid api_version"
            )

        capabilities = raw_data.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(
            isinstance(item, str) for item in capabilities
        ):
            raise ExtensionDiscoveryError(
                f"Manifest {manifest_path} has invalid capabilities"
            )

        entry_point = raw_data.get("entry_point")
        if entry_point is not None and not isinstance(entry_point, str):
            raise ExtensionDiscoveryError(
                f"Manifest {manifest_path} has invalid entry_point"
            )

        description = raw_data.get("description", "")
        if not isinstance(description, str):
            raise ExtensionDiscoveryError(
                f"Manifest {manifest_path} has invalid description"
            )

        return cls(
            extension_id=extension_id,
            name=name,
            version=version,
            api_version=api_version,
            path=manifest_path.parent,
            description=description,
            entry_point=entry_point,
            capabilities=tuple(capabilities),
        )


class ExtensionManager:
    """Discover available extensions and expose config-enabled manifests."""

    MANIFEST_NAME = "extension.json"

    def __init__(
        self,
        search_paths: Iterable[Path] | None = None,
        enabled_extensions: Iterable[str] | None = None,
        extensions_enabled: bool = False,
    ):
        self.search_paths = tuple(
            Path(path)
            for path in (
                search_paths
                if search_paths is not None
                else (USER_EXTENSIONS_DIR, SYSTEM_EXTENSIONS_DIR)
            )
        )
        self.enabled_extensions = frozenset(
            str(item) for item in (enabled_extensions or ())
        )
        self.extensions_enabled = bool(extensions_enabled)
        self.errors: list[str] = []

    def discover(self) -> list[ExtensionManifest]:
        self.errors.clear()
        manifests: dict[str, ExtensionManifest] = {}
        for manifest_path in self._manifest_paths():
            try:
                manifest = ExtensionManifest.from_file(manifest_path)
            except ExtensionDiscoveryError as exc:
                self.errors.append(str(exc))
                continue
            if manifest.extension_id not in manifests:
                manifests[manifest.extension_id] = manifest
        return sorted(manifests.values(), key=lambda item: item.name.casefold())

    def enabled_manifests(self) -> list[ExtensionManifest]:
        if not self.extensions_enabled:
            self.errors.clear()
            return []
        return [
            manifest
            for manifest in self.discover()
            if manifest.extension_id in self.enabled_extensions
        ]

    def _manifest_paths(self) -> list[Path]:
        manifests: list[Path] = []
        for search_path in self.search_paths:
            if not search_path.is_dir():
                continue
            direct_manifest = search_path / self.MANIFEST_NAME
            if direct_manifest.is_file():
                manifests.append(direct_manifest)
            try:
                child_paths = sorted(search_path.iterdir(), key=lambda item: item.name)
            except OSError as exc:
                self.errors.append(f"Cannot read extension directory {search_path}: {exc}")
                continue
            manifests.extend(
                path / self.MANIFEST_NAME
                for path in child_paths
                if path.is_dir() and (path / self.MANIFEST_NAME).is_file()
            )
        return manifests


def _required_text(data: dict, key: str, manifest_path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExtensionDiscoveryError(f"Manifest {manifest_path} is missing {key}")
    return value.strip()
