#!/usr/bin/env python3
"""Profile linux-file-manager startup memory usage.

This script intentionally uses only the Python standard library plus the
project's runtime dependencies so it remains usable on Debian 12 systems.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import resource
import sys
import tempfile
import tracemalloc
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def rss_bytes() -> int:
    """Return max resident set size in bytes for the current process."""
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(value)
    return int(value) * 1024


def format_mib(value: int) -> str:
    return f"{value / (1024 * 1024):.1f} MiB"


def memory_sample(label: str, baseline_rss: int) -> dict[str, Any]:
    current, peak = tracemalloc.get_traced_memory()
    rss = rss_bytes()
    return {
        "label": label,
        "rss_bytes": rss,
        "rss_mib": round(rss / (1024 * 1024), 2),
        "rss_delta_bytes": rss - baseline_rss,
        "rss_delta_mib": round((rss - baseline_rss) / (1024 * 1024), 2),
        "python_current_bytes": current,
        "python_current_mib": round(current / (1024 * 1024), 2),
        "python_peak_bytes": peak,
        "python_peak_mib": round(peak / (1024 * 1024), 2),
    }


def configure_isolated_home(home: Path) -> None:
    os.environ["HOME"] = str(home)
    os.environ["XDG_CONFIG_HOME"] = str(home / ".config")
    os.environ["XDG_DATA_HOME"] = str(home / ".local" / "share")
    os.environ["XDG_CACHE_HOME"] = str(home / ".cache")


def profile_startup(initial_path: Path | None, offscreen: bool) -> list[dict[str, Any]]:
    if offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    tracemalloc.start()
    baseline = rss_bytes()
    samples = [memory_sample("baseline", baseline)]

    from PyQt6.QtWidgets import QApplication

    from lfm.ui.main_window import MainWindow

    samples.append(memory_sample("after_imports", baseline))

    app = QApplication.instance()
    if app is None:
        app = QApplication([sys.argv[0]])
    samples.append(memory_sample("after_qapplication", baseline))

    window = MainWindow()
    if initial_path is not None:
        window.go_to(initial_path)
    app.processEvents()
    samples.append(memory_sample("after_main_window", baseline))

    window.close()
    window.deleteLater()
    app.processEvents()
    gc.collect()
    samples.append(memory_sample("after_window_close", baseline))
    return samples


def print_text(samples: list[dict[str, Any]]) -> None:
    print("linux-file-manager memory profile")
    for sample in samples:
        print(
            "{label:>20}: rss={rss} delta={delta} "
            "python_current={current} python_peak={peak}".format(
                label=sample["label"],
                rss=format_mib(sample["rss_bytes"]),
                delta=format_mib(sample["rss_delta_bytes"]),
                current=format_mib(sample["python_current_bytes"]),
                peak=format_mib(sample["python_peak_bytes"]),
            )
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Optional folder to open after startup.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    parser.add_argument(
        "--no-offscreen",
        action="store_true",
        help="Use the current Qt platform instead of forcing offscreen mode.",
    )
    parser.add_argument(
        "--use-real-home",
        action="store_true",
        help="Use the real HOME/XDG paths instead of a temporary isolated home.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.path is not None and not args.path.is_dir():
        print(f"Not a directory: {args.path}", file=sys.stderr)
        return 2

    if args.use_real_home:
        samples = profile_startup(args.path, offscreen=not args.no_offscreen)
    else:
        with tempfile.TemporaryDirectory(prefix="lfm-memory-profile-") as tmpdir:
            configure_isolated_home(Path(tmpdir))
            samples = profile_startup(args.path, offscreen=not args.no_offscreen)

    if args.json:
        print(json.dumps(samples, indent=2))
    else:
        print_text(samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
