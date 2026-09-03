# GitHub Copilot instructions

This repository is **Linux File Manager**, a file manager for Linux written
in Python + PyQt6 (package `lfmapp`).

Before suggesting or generating code, read the full conventions in
[`AGENTS.md`](../AGENTS.md) (canonical for AI agents working in this repo).

Key points:

- The authoritative plan lives in [`ROADMAP.md`](../ROADMAP.md) (phases 0-13
  plus a prioritized backlog P0-P3). Read the phase you are working on.
- Golden rule: do not re-develop what already exists — check `lfmapp/`,
  `tests/` and the ROADMAP before proposing new code.
- Architecture: `lfmapp/ui/main_window.py` is a thin composer; logic belongs
  in `lfmapp/controllers/` (pure controllers + `AppState`),
  `lfmapp/services/`, `lfmapp/actions/` (action registry) and per-concern UI
  mixins in `lfmapp/ui/`. Do not add new logic to `MainWindow`.
- Run `python3 -m pytest -q` from the repository root; keep the full suite
  green. GUI tests use `QT_QPA_PLATFORM=offscreen`.
- `docs/ux-flow-audit.md` documents known inconsistencies (T1-T18);
  `docs/performance-baseline.md` records timings and budgets.
- User-visible strings must be translatable via `self.tr(...)`. Repository
  documentation is written in English (only the audit notes under `docs/` are
  still in Spanish); commit messages and code identifiers in English.
