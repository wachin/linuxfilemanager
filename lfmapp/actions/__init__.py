"""Action registry package for linux-file-manager."""

from .registry import (
    ActionRegistry,
    ActionSpec,
    DuplicateActionError,
    UnknownActionError,
)

__all__ = [
    "ActionRegistry",
    "ActionSpec",
    "DuplicateActionError",
    "UnknownActionError",
]
