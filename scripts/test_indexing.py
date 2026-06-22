#!/usr/bin/env python3
"""Quick smoke test for IndexService.

Run from the project root. It will index `README.md` and perform a sample search.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lfm.services import IndexService


def main():
    svc = IndexService.default()
    target = ROOT / "README.md"
    if target.exists():
        svc.index_file(target)
        print(f"Indexed: {target}")
    else:
        print("README.md not found; skipping indexing.")

    results = svc.search("file", limit=10)
    print("Search results (sample):")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
