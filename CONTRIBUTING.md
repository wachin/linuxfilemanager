# Contributing to Linux File Manager

Thank you for contributing! This project is a file manager for Linux in
Python + PyQt6 and is under active development. Every contribution — code,
tests, documentation, translations or ideas — is welcome.

> If you are an AI agent (or use one) working in this repo, read first
> **[`AGENTS.md`](AGENTS.md)** and **[`CLAUDE.md`](CLAUDE.md)**; they contain
> the conventions every agent must follow. The planning lives in
> **[`ROADMAP.md`](ROADMAP.md)**.

## Getting started

```bash
git clone <repository-url>
cd linuxfilemanager
python3 -m pip install -e ".[dev]"
python3 -m pytest -q        # check the suite passes before touching anything
```

## Basic rules

1. **Do not repeat previous work.** Check `lfmapp/`, `tests/` and
   `ROADMAP.md` before implementing: if the capability already exists,
   improve it, do not duplicate it.
2. **Respect the architecture.** `main_window.py` is a thin composer: pure
   logic in `lfmapp/controllers/` and `lfmapp/services/`; action registry in
   `lfmapp/actions/`; per-concern UI in the mixins of `lfmapp/ui/`. Do not
   mix new logic into `MainWindow`.
3. **All code with tests.** Add or update the tests for what you touch. The
   full suite must stay green (`python3 -m pytest -q`).
4. **Visible texts translatable.** Use `self.tr(...)` for UI strings; do not
   embed user-facing text in code.
5. **Follow the ROADMAP.** If you bring in a new idea, align it with the
   phases and the backlog; tick the completed checkboxes.

## What is needed most

- UI and workflow polish (see `docs/ux-flow-audit.md`, tasks T1–T18: known
  inconsistencies ready to be resolved).
- Cold-start optimization (icon resolution in `lfmapp/ui/icons.py` dominates
  startup time; see `docs/performance-baseline.md`).
- Phase-by-phase implementation of the ROADMAP (start with the early phases
  and the P0/P1 backlog).
- Additional tests and coverage improvements.
- Linux desktop integration (XDG, portals, network).
- Debian packaging and release automation.

## How to submit changes

1. Create a branch with a descriptive name (`fix/…`, `feat/…`).
2. Make small, reviewable changes with clear commit messages in English.
3. Run the full suite and `python3 -m compileall lfmapp`.
4. Open a *pull request* describing what changes, why, and how it was
   verified.

## Reporting issues

When opening an *issue*, include:

- the version or commit where it happens,
- steps to reproduce,
- what you expected and what happened,
- environment (distribution, Python/PyQt6 version, desktop).

## License

Contributing implies accepting that your contribution falls under the
project's license (GPL-3.0-or-later). When incorporating ideas from the file
managers cited in "Sources of Inspiration" (README), respect their licenses
and do not copy code or literal text: only the interaction logic, rewritten.
