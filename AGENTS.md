# AGENTS.md

Working guide for AI agents and collaborators who continue the development of **Linux File Manager** (a file manager for Linux in Python + PyQt6). Read it in full before touching any code.

## Project goal

Build the best file manager for Linux focused on productivity: fast with keyboard and mouse, safe on delicate operations, capable in batch workflows, unobtrusive, and sustainable at the architecture level. The strategy, phases, backlog and decisions made live in **`ROADMAP.md`** (the main planning document).

## Golden rule

**Do not repeat previous work or re-develop what already exists.** Before implementing or proposing anything, check:

- `ROADMAP.md` (what is planned, decided or discarded).
- `README.md` (overview, installation, structure).
- `lfmapp/` (whether the capability already exists in code).
- `tests/` (what behaviour is already covered by tests).
- `docs/ux-flow-audit.md` and `docs/performance-baseline.md` (workflow audit and performance baseline).

## Current architecture (important)

`lfmapp/ui/main_window.py` is now a **thin composer** (~370 lines). All logic lives in modules with a single responsibility:

| Layer | Location | Contents |
|---|---|---|
| Action registry | `lfmapp/actions/` | `ActionRegistry` (stable ids, enablement predicates), core command catalog (`catalog.py`), Qt adapter (`qt.py`) |
| Pure controllers | `lfmapp/controllers/` | `NavigationController`, `SelectionController`, `SearchController`, `ViewController` (per-folder view persistence), `AppState` (observable state) — no QMainWindow dependency, testable in isolation |
| Services | `lfmapp/services/` | `file_operations.py`, `operation_queue.py`, `trash_service.py`, `search_service.py`, `preview_worker.py`, tags, vault, network, terminal, etc. |
| UI widgets and mixins | `lfmapp/ui/` | `MainWindow` + per-concern mixins: `menu_bar_mixin`, `toolbar_mixin`, `context_menu_mixin`, `file_actions_mixin`, `transfer_actions_mixin`, `operation_center_mixin`, `history_actions_mixin`, `search_actions_mixin`, `palette_actions`, `central_status_mixin`, `tabs_navigation_mixin`, `view_controls_mixin`, `archive_tag_vault_mixin` |
| Model | `lfmapp/models/` | `file_system_model.py` |
| Core | `lfmapp/core/` | `config.py` (with key backfill), `paths.py`, `xdg.py`, `translator.py` |

Architecture rules:

- **Do not mix logic into `MainWindow`** (or a mixin) when it can live in a service or controller: pure logic goes to `controllers/` or `services/`; the mixin only wires UI → logic.
- The surfaces (menu, toolbar, context menu, palette, shortcuts) must consume the **same action registry** (`lfmapp/actions/`) and the same observable state (`AppState`), avoiding duplicated actions with contradictory states.
- Every new capability must be testable **without showing the whole window** (controller/service tests) in addition to the GUI tests.
- No ideas enter the roadmap without being aligned with the phases and architecture already defined.

## Design inspiration

The interaction ideas in the roadmap come from reference desktop file managers, originally adapted to Python + PyQt6 (see "Sources of Inspiration" in the README and at the end of the ROADMAP). **No code or text is copied from those sources**: only the interaction logic is studied and rewritten for this project.

## How to test

Run from the repository root:

```bash
python3 -m pytest -q                 # full suite (minimum requirement: everything green before finishing)
python3 -m pytest tests/test_X.py    # a specific test file
python3 -m compileall lfmapp         # verify the whole package compiles
```

GUI tests use `QT_QPA_PLATFORM=offscreen` (headless). When you add a function, add its test too; when you refactor, keep the full suite green.

## Practical tips

- User configuration lives in `~/.local/share/linux-file-manager/config.json`. If something "does not reflect" recent changes, that directory can be deleted so it regenerates with the default values.
- `docs/ux-flow-audit.md` documents 18 known inconsistencies (T1–T18) found in the audit: they are task candidates when you touch their area.
- `docs/performance-baseline.md` records the measured timings and budgets; cold startup is dominated by icon resolution in `lfmapp/ui/icons.py` (optimization target #1).

## How to deliver work

- Leave a clear summary of what was done, verified (green tests), including the paths of the files touched.
- If applicable, update `ROADMAP.md`, ticking the completed checkboxes and noting the real state.
- Respect the language of visible texts (translations via `self.tr(...)`). Repository documentation is written in English; the audit notes under `docs/` (`ux-flow-audit.md`, `performance-baseline.md`) are the only Spanish documents left.
