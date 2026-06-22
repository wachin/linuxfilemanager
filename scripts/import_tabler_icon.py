#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLER_ROOT = PROJECT_ROOT / "third-party" / "tabler-icons"
SOURCE_ROOT = TABLER_ROOT / "icons"
DESTINATION_ROOT = PROJECT_ROOT / "lfmapp" / "assets" / "icons" / "tabler"
VALID_VARIANTS = ("outline", "filled")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy selected Tabler icon SVGs from the development submodule into "
            "linuxfilemanager's shipped asset directory."
        )
    )
    parser.add_argument("icon_name", help="Upstream icon basename, for example 'folder' or 'home'.")
    parser.add_argument(
        "--variant",
        choices=("outline", "filled", "both"),
        default="both",
        help="Which Tabler icon style to import. Default: both.",
    )
    parser.add_argument(
        "--dest-name",
        default="",
        help="Optional local basename override. Default: use the upstream icon name.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing destination file.",
    )
    return parser.parse_args()


def expected_source(icon_name: str, variant: str) -> Path:
    return SOURCE_ROOT / variant / f"{icon_name}.svg"


def expected_destination(dest_name: str, variant: str) -> Path:
    return DESTINATION_ROOT / variant / f"{dest_name}.svg"


def import_icon(icon_name: str, variant: str, dest_name: str, force: bool = False) -> Path:
    source_path = expected_source(icon_name, variant)
    if not source_path.is_file():
        raise FileNotFoundError(f"Tabler icon not found: {source_path}")

    destination_path = expected_destination(dest_name, variant)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if destination_path.exists() and not force:
        raise FileExistsError(
            f"Destination already exists: {destination_path}. Use --force to overwrite."
        )

    shutil.copy2(source_path, destination_path)
    return destination_path


def main() -> int:
    args = parse_args()
    icon_name = args.icon_name.strip()
    if not icon_name:
        print("Icon name must not be empty.", file=sys.stderr)
        return 2

    dest_name = args.dest_name.strip() or icon_name
    variants = VALID_VARIANTS if args.variant == "both" else (args.variant,)

    if not TABLER_ROOT.is_dir():
        print(
            f"Tabler Icons submodule not found at {TABLER_ROOT}. "
            "Initialize the submodule before importing icons.",
            file=sys.stderr,
        )
        return 2

    copied_paths: list[Path] = []
    try:
        for variant in variants:
            copied_paths.append(
                import_icon(
                    icon_name=icon_name,
                    variant=variant,
                    dest_name=dest_name,
                    force=args.force,
                )
            )
    except (FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for path in copied_paths:
        print(path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
