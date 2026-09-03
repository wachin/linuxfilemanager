# CLAUDE.md — Quick guide for AI agents

This project follows the full guide in **AGENTS.md** (read it first; it is the
canonical reference for any agent working here).

Quick summary:

- **What it is**: Linux File Manager, a file manager for Linux in
  Python + PyQt6 (package `lfmapp`).
- **Planning**: `ROADMAP.md` (phases 0–13 + backlog P0–P3). Read the phase
  you are working on before implementing.
- **Golden rule**: do not re-develop what already exists — check `lfmapp/`,
  `tests/` and the ROADMAP before proposing new code.
- **Architecture**: `main_window.py` is a thin composer; logic lives in
  `lfmapp/controllers/` (pure controllers + `AppState`),
  `lfmapp/services/`, `lfmapp/actions/` (action registry) and per-concern UI
  mixins in `lfmapp/ui/`. Do not mix new logic into `MainWindow`.
- **Tests**: `python3 -m pytest -q` from the repository root (everything must
  stay green); GUI tests use `QT_QPA_PLATFORM=offscreen`.
- **Audit**: `docs/ux-flow-audit.md` lists known inconsistencies (T1–T18);
  `docs/performance-baseline.md` records timings and budgets.
- **Language**: user-visible strings must be translatable via `self.tr(...)`;
  repository documentation is written in English (only the audit notes under
  `docs/` are still in Spanish).
