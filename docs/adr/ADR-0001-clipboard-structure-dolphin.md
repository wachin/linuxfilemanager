# ADR-0001 — Clipboard with captured structure: two real bugs found by studying Dolphin's paste flow

- **Date:** 2026-09-08
- **Status:** Accepted and implemented (backlog P2 — Flat View)
- **Scope:** `lfmapp/ui/file_actions_mixin.py`, `lfmapp/services/worker_threads.py`
- **Reference studied:** Dolphin (KDE) source code, pinned read-only under
  `third-party/dolphin/` — specifically
  [`third-party/dolphin/src/views/dolphinview.cpp`](../../third-party/dolphin/src/views/dolphinview.cpp)
  (`DolphinView::paste`, `DolphinView::pasteToUrl`, `DolphinView::duplicateSelectedItems`).

## Context

While implementing the **Flat View** (backlog P2), Linux File Manager needed a
rule for **copying files that live in subfolders**: when the user copies
`docs/readme.md` from a flattened listing and pastes it somewhere else, the
destination must be able to *recreate the relative source structure*
(`dest/docs/readme.md`) or *dump everything into the same folder*
(`dest/readme.md`).

The first implementation attempt computed the "nested" relationship **at
paste time**, by comparing each source's parent against the paste
destination. During testing, the GUI test suite froze twice with no visible
error. Studying how Dolphin — the KDE file manager — solves the same
problem revealed that the design itself was wrong, and uncovered a second,
independent bug.

## What Dolphin's code taught us

Dolphin's paste flow lives in `src/views/dolphinview.cpp` (paths relative to
`third-party/dolphin/`):

```cpp
void DolphinView::paste()
{
    pasteToUrl(url());
}

void DolphinView::pasteToUrl(const QUrl &url)
{
    KIO::PasteJob *job = KIO::paste(QApplication::clipboard()->mimeData(), url);
    ...
}
```

Two design lessons were extracted from it (logic only — **no code or text was
copied**; Dolphin is GPL-2+/GPL-3, this project is GPL-3.0-or-later, and the
final implementation below is an original Python/PyQt6 re-expression):

1. **The clipboard transports full context, not just names.** Dolphin's
   clipboard carries the complete source URLs, and the paste job resolves
   everything else. The relationship "where did this file come from" is
   **recorded at copy time**, never guessed at paste time.
2. **Never copy onto yourself.** Dolphin's jobs validate the resolved
   destination before asking the user anything; an item that would land on
   itself is not a conflict to ask about.

## Bug 1 — Self-copy deadlock (`source == dest`)

**Symptom.** A paste of a nested file *inside its own base folder* froze the
application. Stack captured with `faulthandler`:

```
Thread (worker):  conflict_dialog.py:220  __call__        ← waiting for a decision
Thread (GUI):     conflict_dialog.py:225  _show_dialog    ← modal dialog.exec()
```

**Root cause.** When the flat view of `/root` shows `docs/readme.md` and the
item is pasted back into `/root` (or the structure-recreate path computes
`root/docs` as the destination), the copy target resolves to the **exact
same path as the source**. The old `_resolve_conflict()` in
`lfmapp/services/worker_threads.py` saw `dest.exists()` — true, because the
destination *is* the source file — and asked the conflict dialog, which
blocks the worker forever in a headless/automated context.

**Fix (original implementation, inspired by lesson 2).** In
`lfmapp/services/worker_threads.py`, `_resolve_conflict()` now treats
`source == dest` as a **no-op and skips it without asking**:

```python
def _resolve_conflict(self, source: Path, dest: Path) -> Path | None:
    if source == dest:
        # Copying onto itself is a no-op (can happen when pasting flat-view
        # selections inside their own base folder): skip without asking.
        return None
    ...
```

## Bug 2 — Structure computed at paste time (and the `"."` trap)

**Symptom.** The regression suite froze in `test_copy_paste_flow` — a plain
copy/paste of a direct child, with no subfolders involved at all.

**Root cause.** The first design asked "is this source nested?" by computing
`src.parent.relative_to(destination)` **when pasting**. Two problems:

1. The relationship the user actually cares about is relative to the folder
   the copy was made **from** (the flat view's base folder), not to the
   paste destination. Computing it at paste time gives wrong answers in both
   directions: real nested copies go undetected when pasting elsewhere, and
   unrelated layouts get asked about.
2. A subtle Python trap: `Path("/a").relative_to(Path("/a"))` returns
   `Path(".")`, whose `str()` is **`"."`, not `""`**. Every direct child of
   the destination was therefore classified as "nested" with a relative
   parent of `"."`, and the paste triggered the nested-structure question on
   every ordinary copy.

**Fix (original implementation, inspired by lesson 1).** The clipboard now
**captures the structure at copy time** as `(path, relative_parent)` tuples,
exactly like Dolphin's clipboard carries full source URLs so the paste job
can resolve structure afterwards:

```python
# lfmapp/ui/file_actions_mixin.py
def _clipboard_capture(self) -> list[tuple]:
    paths = self.workspace.selected_paths()
    base = self.workspace.current_path()
    captured = []
    for path in paths:
        rel_parent = ""
        try:
            rel = path.parent.relative_to(base)
            # A direct child of the base has no structure (Path(".")
            # stringifies as "."; normalize it away).
            rel_parent = "" if rel == Path(".") else str(rel)
        except ValueError:
            rel_parent = ""   # not under the base folder
        captured.append((path, rel_parent))
    return captured
```

At paste time, `_resolve_nested_structure_mode()` only asks the question
when there is real captured structure and the destination is a **different
folder than the base**; pasting back into the same base folder is a silent
no-op for the nested items themselves (Bug 1's guard skips them).

## Outcome

- The nested-file paste rule works as the roadmap specified: one question
  (recreate / same folder / cancel), asked only when meaningful.
- Two genuine bugs fixed that would have hit real users (self-copy freeze;
  spurious structure dialog on every paste).
- Full suite green: 459 tests passing, including 18 new flat-view tests
  (`tests/test_flat_view.py`) that cover the three paste answers.

## Credits

The diagnosis and design were possible because the KDE community publishes
Dolphin's source code for the whole world to study. No code or text was
copied from Dolphin — only the interaction logic was read and re-expressed
in Python + PyQt6 for this project, which is precisely the way this project
uses its reference sources (see "Sources of Inspiration" in
[`ROADMAP.md`](../../ROADMAP.md)). Thanks to the Dolphin developers for
their work; if one of them reads this note: your public code turned a
two-day debugging session into a one-hour fix.
