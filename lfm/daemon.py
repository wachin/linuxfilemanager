"""Background maintenance daemon for linux-file-manager.

The first daemon implementation is intentionally small: it runs optional
maintenance tasks that must not be part of GUI startup.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from lfm.core.config import Config
from lfm.services.textindex_service import TextIndexService


@dataclass(frozen=True)
class DaemonRunResult:
    indexed_folders: int = 0
    indexed_files: int = 0
    skipped_folders: int = 0
    text_index_enabled: bool = False


class FileManagerDaemon:
    """Run lightweight background maintenance outside the PyQt UI process."""

    def __init__(
        self,
        config: Config | None = None,
        text_index_service: TextIndexService | None = None,
    ):
        self.config = config if config is not None else Config()
        self.text_index_service = text_index_service
        self._owns_text_index_service = text_index_service is None
        self._stop_requested = False

    def request_stop(self, *_args):
        self._stop_requested = True

    def close(self):
        if self._owns_text_index_service and self.text_index_service is not None:
            self.text_index_service.close()

    def configured_index_roots(self) -> list[Path]:
        roots = self.config.bookmarks
        seen = set()
        result: list[Path] = []
        for root in roots:
            path = Path(root).expanduser()
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            result.append(path)
        return result

    def run_once(
        self,
        roots: Iterable[Path] | None = None,
        recursive: bool = True,
        limit_per_folder: int = 50000,
    ) -> DaemonRunResult:
        if not self.config.text_index_enabled:
            return DaemonRunResult(text_index_enabled=False)

        service = self.text_index_service
        if service is None:
            service = TextIndexService()
            self.text_index_service = service

        indexed_folders = 0
        indexed_files = 0
        skipped_folders = 0

        for root in roots if roots is not None else self.configured_index_roots():
            path = Path(root).expanduser()
            if not path.is_dir():
                skipped_folders += 1
                continue
            indexed_files += service.index_folder(
                path,
                recursive=recursive,
                limit=limit_per_folder,
            )
            indexed_folders += 1

        return DaemonRunResult(
            indexed_folders=indexed_folders,
            indexed_files=indexed_files,
            skipped_folders=skipped_folders,
            text_index_enabled=True,
        )

    def run_forever(
        self,
        interval_seconds: int = 300,
        roots: Iterable[Path] | None = None,
        recursive: bool = True,
        limit_per_folder: int = 50000,
    ):
        while not self._stop_requested:
            self.run_once(
                roots=roots,
                recursive=recursive,
                limit_per_folder=limit_per_folder,
            )
            deadline = time.monotonic() + interval_seconds
            while not self._stop_requested and time.monotonic() < deadline:
                time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linuxfm-daemon",
        description="Run linux-file-manager background maintenance tasks.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one maintenance pass and exit",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="seconds between maintenance passes when not using --once",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="folder to index; may be passed more than once",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="index only direct child files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50000,
        help="maximum files to index per folder",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    roots = [Path(path) for path in args.paths] if args.paths else None
    daemon = FileManagerDaemon()
    signal.signal(signal.SIGTERM, daemon.request_stop)
    signal.signal(signal.SIGINT, daemon.request_stop)

    try:
        if args.once:
            result = daemon.run_once(
                roots=roots,
                recursive=not args.no_recursive,
                limit_per_folder=args.limit,
            )
            print(
                "text_index_enabled={enabled} indexed_folders={folders} "
                "indexed_files={files} skipped_folders={skipped}".format(
                    enabled=str(result.text_index_enabled).lower(),
                    folders=result.indexed_folders,
                    files=result.indexed_files,
                    skipped=result.skipped_folders,
                )
            )
            return 0

        daemon.run_forever(
            interval_seconds=max(1, args.interval),
            roots=roots,
            recursive=not args.no_recursive,
            limit_per_folder=args.limit,
        )
        return 0
    finally:
        daemon.close()


if __name__ == "__main__":
    sys.exit(main())
