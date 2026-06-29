# ROADMAP TODOs — actionable follow-up work

Purpose: keep only forward-looking tasks that are suitable for issues and incremental pull requests.

## Completed achievements
- [x] Project rename to `lfmapp` to avoid conflict with Debian's existing `lfm` package name.
- [x] Runtime icon helper added so UI code can prefer system theme icons with safe fallbacks.
- [x] Switched application icon loading to the system icon theme path (`/usr/share/icons/`) instead of vendored Tabler assets.
- [x] Sidebar redesigned to use icon tabs for `Quick Access`, `This Computer`, `Network`, `Bookmarks`, and `Recents`, with a more compact layout.
- [x] XDG user directories support implemented for localized/customized `Desktop`, `Documents`, `Downloads`, `Music`, `Pictures`, and `Videos`.
- [x] Quick Access now uses actual XDG paths and those default folders are no longer duplicated into Bookmarks.
- [x] Documentation updated to record the XDG user directories repair.
- [x] "Open in Terminal" fixed so the configured terminal preference is honored and launch commands no longer force maximized/fullscreen behavior.
- [x] Default terminal detection priority changed to prefer `qterminal` first, while keeping other supported terminals available in Preferences.
- [x] Configuration/data directory behavior documented in `README.md`, including how to delete saved files to reset the application.
- [x] Application startup now recreates required app-data files and folders such as `config.json`, `bookmarks.json`, `tags.db`, `extensions/`, and `vault/` when missing.
- [x] Details view columns made resizable and movable, and right-clicking the header now opens a `List Columns` chooser dialog.
- [x] Additional Details columns implemented: `Created - Time`, `Date Accessed`, `Date Created`, `Detailed Type`, `Group`, `Location`, `MIME Type`, `Octal Permissions`, `Owner`, `Permissions`, `SELinux Context`, and `Modified - Time`.
- [x] File icons are now shown only in the `Name` column and suppressed in all other Details columns.
- [x] Taskbar/window icon integration fixed so Linux File Manager shows its application icon correctly outside the About dialog too.
- [x] Compact modern context menu added with top-row actions for `Cut`, `Copy`, `Paste`, `Rename`, `Share`, and `Delete`.
- [x] Modern context menu made configurable in Preferences, enabled by default, and duplicate middle-menu entries suppressed when modern mode is active.
- [x] First-run context-menu state corrected so `Paste` stays disabled until there is actually something in the clipboard.
- [x] Config loading now backfills newly added settings keys into older saved config files.
- [x] README updated to mention that deleting `~/.local/share/linux-file-manager/` can help expose new defaults during active development.
- [x] Preview worker moved image decoding to `QImageReader` in a background thread and converts to `QPixmap` only in the UI thread for safer image previews.
- [x] Single-image preview support fixed in the right preview panel.
- [x] Folder preview gallery support added in the preview panel for directories containing multiple images.
- [x] Main workspace image thumbnails implemented so image files preview directly in `Icons`, `List`, `Details`, and `Compact` views, independent of the preview panel.
- [x] Workspace thumbnail caching added for common image formats including `png`, `jpg`, `jpeg`, `gif`, `bmp`, `svg`, and `webp`.

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
