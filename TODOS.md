# ROADMAP TODOs — actionable follow-up work

Purpose: keep only forward-looking tasks that are suitable for issues and incremental pull requests.

## How to use
- Keep each item small enough for one PR or one issue.
- Prefer tasks that improve maintainability, packaging, or user-visible workflows.
- Use labels such as `feature`, `cleanup`, `ux`, `tests`, and `good-first-issue`.

## Workflow and UX tasks
- [x] Startup location preference: let users choose `Home`, `Last visited`, or a fixed custom folder.
- [ ] System icon theme audit: review icon names used via `QIcon.fromTheme()` so the UI follows the active desktop icon theme with sensible fallbacks.
- [ ] Quick Access reset/restore action: restore default known folders after users unpin them.
- [ ] Per-folder details columns persistence: remember visible columns, widths, and order in Details view.
- [ ] Better conflict resolution dialog for copy/move: replace/skip/rename/apply to all.
- [ ] Batch rename workflow: add predictable multi-file renaming rules with preview.
- [ ] Disk space warning UX: show low-space warnings and make thresholds configurable.
- [ ] File-type actions audit: review contextual actions by type so archive, document, media, and folder actions stay consistent.
- [ ] Terminal workflow polish: finish preferred-terminal UX and consider an optional embedded terminal panel with cwd sync.
- [ ] Safe user extensions/scripts: add a permission-aware extension model before exposing scripting to end users.
- [ ] Optional Git-aware workflow: show repository status in folders under version control without making Git a hard dependency.

## Public repository cleanup follow-ups
- [ ] Add a release checklist for public publishing: metadata, screenshots, docs, packaging, tests, and license review.
- [ ] Add CI for tests plus package validation on pushes and pull requests.
- [ ] Replace broad `except Exception: pass` blocks with targeted handling and logging.
- [ ] Continue splitting `MainWindow` into smaller controllers/widgets.

## High-priority engineering tasks
- [ ] Full-text indexing backend: pluggable backend interface and a production-ready adapter.
- [ ] Async thumbnailer: worker pool, disk cache, and image/video thumbnail providers.
- [ ] Async file operation queue improvements: resume, retry, clearer progress, and checksum verification.
- [ ] Accessibility improvements: keyboard navigation audit and better Qt accessibility metadata.
- [ ] Comprehensive GUI tests: add common copy/move/rename/navigation flows.
- [ ] Wayland and X11 drag/drop compatibility fixes.

## Medium-priority tasks
- [ ] Command palette / quick actions.
- [ ] Remote protocol connectors: start with SFTP.
- [ ] Document previews: PDF/Markdown/Office with graceful fallbacks.
- [ ] Encrypted vault hardening: system keyring integration and clearer recovery behavior.

## Low-priority / stretch
- [ ] Snapshot/restore hooks for btrfs or LVM environments.
- [ ] Packaging expansion: Flatpak and AppImage after Debian packaging is stable.
