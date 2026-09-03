"""TPM control placeholder service.

This module intentionally avoids TPM-specific dependencies. It gives the rest
of the application a stable place to query basic TPM availability while keeping
future hardware-backed vault work isolated from the current implementation.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_TPM_DEVICE_PATHS = (Path("/dev/tpmrm0"), Path("/dev/tpm0"))


@dataclass(frozen=True)
class TpmControlStatus:
    """Basic TPM availability information."""

    available: bool
    device_path: Path | None = None
    message: str = "TPM support is not configured."


class TpmControlService:
    """Minimal TPM control stub for future hardware-backed features."""

    def __init__(self, device_paths: Iterable[Path | str] | None = None):
        paths = device_paths if device_paths is not None else DEFAULT_TPM_DEVICE_PATHS
        self.device_paths = tuple(Path(path) for path in paths)

    def status(self) -> TpmControlStatus:
        """Return whether a TPM device node is visible on this system."""

        for path in self.device_paths:
            if path.exists():
                return TpmControlStatus(
                    available=True,
                    device_path=path,
                    message="TPM device node is present.",
                )
        return TpmControlStatus(
            available=False,
            device_path=None,
            message="No TPM device node was found.",
        )

    def is_available(self) -> bool:
        """Return True when a TPM device node is visible."""

        return self.status().available

    def seal_secret(self, secret: bytes) -> bytes:
        """Placeholder for future TPM-backed secret sealing."""

        raise NotImplementedError("TPM-backed secret sealing is not implemented yet.")

    def unseal_secret(self, sealed_secret: bytes) -> bytes:
        """Placeholder for future TPM-backed secret unsealing."""

        raise NotImplementedError("TPM-backed secret unsealing is not implemented yet.")
