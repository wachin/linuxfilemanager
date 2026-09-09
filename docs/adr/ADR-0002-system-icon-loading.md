# ADR-0002 — System icon loading: use the toolkit theme engine, never scan the icon trees

- **Date:** 2026-09-09
- **Status:** **Accepted — LOCKED. Do not add startup scanning on top of this.**
- **Scope:** `lfmapp/ui/icons.py`, `lfmapp/models/file_system_model.py` (`FallbackIconProvider`), `lfmapp/app.py`
- **Reference studied:** Thunar source, pinned read-only under
  `third-party/thunar/` — `thunar/thunar-icon-factory.c`
  (`gtk_icon_theme_lookup_icon_for_scale`, `gtk_icon_theme_lookup_by_gicon_for_scale`)
  and `thunar/thunar-file.c` / `thunar-chooser-dialog.c`
  (`g_content_type_get_icon`). See also `docs/performance-baseline.md` §4.1.

## Decision

Linux File Manager resolves system/file-type icons **by logical name through the
toolkit's own icon-theme engine** — `QIcon.fromTheme(...)` (the Qt analogue of
Thunar's `gtk_icon_theme_lookup_*`) — exactly like Thunar/GTK do. The engine
reads the active theme's indexed `index.theme` and the `icon-theme.cache`
produced by the system tool `gtk-update-icon-cache`, so a lookup is O(1) and
**no code ever walks the icon directories**.

The correct sequence, already implemented and to be preserved:

1. `FallbackIconProvider.icon()` (model) derives a *themed icon name* from the
   MIME type / extension (`mime.replace("/", "-")`, the analogue of
   `g_content_type_get_icon`) and hands candidate names to `app_icon`.
2. `app_icon()` asks `QIcon.fromTheme` first (active theme). This is the
   primary, fast path.
3. Only if the active theme does not expose the name does it fall back to a
   persisted path, resolved **lazily** through `_icon_file_index()` and memoized,
   with both hits and misses persisted so the index is built **at most once per
   profile** (the same "build once, reuse" idea as GTK's cache). This lazy path
   exists solely for the documented bare-`hicolor`/qt6ct corner case.
4. `lfmapp/app.py:main()` calls only `initialize_icon_cache(config)` at startup —
   which loads persisted paths/misses and **performs no filesystem scan**.

## Consequences / rules for future work

- **Do NOT reintroduce a startup tree scan.** In particular, do not call
  `discover_system_icons()` (or any `Path.rglob`/`os.walk` over theme dirs) from
  the application entry point or window construction. That scan was added by
  commit `a32d2db` and caused an 8-27 s first launch on large icon themes while
  contradicting the whole point of using the theme engine.
- If a new surface needs a themed icon, add its **name** to the alias/candidate
  tables and resolve it through `app_icon`/`QIcon.fromTheme`. Do not precompute
  file paths by scanning.
- The lazy `_icon_file_index()` must stay lazy + memoized + self-healing
  (persist misses). It must never be forced eagerly at startup.
- This decision is machine-checked: `tests/test_ui_icons.py` contains
  `test_startup_entry_point_does_not_scan_icon_trees` and
  `test_themed_lookup_never_walks_icon_dirs`. If either fails, the rule above
  was violated — fix the code, do not weaken the test.

## Why this is the Thunar-correct way

Thunar never enumerates `~/.icons` or `/usr/share/icons`: it only ever names an
icon and lets `GtkIconTheme` (backed by `gtk-update-icon-cache`) do the lookup.
Doing the same in Qt (`QIcon.fromTheme`) inherits the system's indexed cache,
follows the user's active theme automatically, and keeps cold startup flat.
Any manual scan is strictly worse and redundant with what the OS already
provides.

## Credits

The correct approach was dictated by studying how Thunar loads icons — the same
"adapt the interaction logic, never copy code" method used across this project
(see "Sources of Inspiration" in [`README.md`](../../README.md) and
[`ROADMAP.md`](../../ROADMAP.md)). No Thunar code was copied; only its icon
loading strategy was read and re-expressed with Qt's theme engine.
