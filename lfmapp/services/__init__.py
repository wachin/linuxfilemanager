"""Service package for linux-file-manager."""

from .file_operations import FileOperations
from .search_service import SearchFilters, SearchThread
from .trash_service import (
    send_to_trash,
    restore_from_trash,
    empty_trash,
    list_trash,
    trash_size,
    trash_count,
)
from .bookmark_service import BookmarkService
from .extractor_service import (
    extract_here,
    extract_to,
    is_archive,
    detect_archive_type,
    create_zip,
    ExtractThread,
    CompressThread,
)
from .tag_service import TagService
from .network_service import discover_network_locations
from .textindex_service import TextIndexService
from .tpm_control import TpmControlService, TpmControlStatus
from .vault_service import VaultService
from .worker_threads import CopyWorker, MoveWorker, DeleteWorker, TrashWorker
from .operation_queue import BackgroundOperationQueue
from .operation_history import (
    CompositeOperation,
    CopyOperation,
    CreateOperation,
    MoveOperation,
    OperationHistory,
    RenameOperation,
    TrashOperation,
)

__all__ = [
    "FileOperations",
    "SearchThread",
    "SearchFilters",
    "send_to_trash",
    "restore_from_trash",
    "empty_trash",
    "list_trash",
    "trash_size",
    "trash_count",
    "BookmarkService",
    "extract_here",
    "extract_to",
    "is_archive",
    "detect_archive_type",
    "ExtractThread",
    "create_zip",
    "CompressThread",
    "TagService",
    "discover_network_locations",
    "TextIndexService",
    "TpmControlService",
    "TpmControlStatus",
    "VaultService",
    "CopyWorker",
    "MoveWorker",
    "DeleteWorker",
    "TrashWorker",
    "BackgroundOperationQueue",
    "OperationHistory",
    "RenameOperation",
    "CreateOperation",
    "MoveOperation",
    "CopyOperation",
    "TrashOperation",
    "CompositeOperation",
]

# New indexing service (full-text)
from .indexing import IndexService

__all__.append("IndexService")
from .indexer import IndexerService

__all__.append("IndexerService")
from .terminal_service import TerminalService

__all__.append("TerminalService")
