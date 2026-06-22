# Roadmap.md — Linux File Manager

## Project name

Project/package name:

```text
linux-file-manager
```

Command-line executable:

```text
linuxfm
```

The goal is to create a lightweight, fast, modular file manager for Linux, written in Python and PyQt6.

The objective is to provide a familiar and efficient file management workflow for Linux users without use visual effects or unnecessary animations.

The priority is to keep the application lightweight, responsive, and practical for everyday Linux desktop use.

Performance, stability, and usability are more important than appearance.

---

## Main goals

* [x] Lightweight file manager for Linux
* [x] Written in Python 3 and PyQt6
* [x] Modular architecture
* [x] Fast startup (startup path avoids duplicate model load; network discovery is deferred)
* [x] Responsive UI
* [x] Low memory usage (stdlib RSS/tracemalloc profiling added; startup tag/vault services are lazy)
* [x] No visual effects
* [x] No unnecessary animations
* [x] Debian-friendly packaging (package layout validates and uses Debian system paths)
* [x] Prepared for future inclusion in Debian repositories (packaging skeleton, policy paths, AppStream, lintian override, and upstream metadata are present)

---

## Core Features to Implement

The file manager should implement the core capabilities expected from a modern Linux desktop file manager:

### Interface Components (Required)

**Navigation Panel (Sidebar)**
* [x] Quick Access with dynamically pinned items
* [x] Known folders: Desktop, Documents, Downloads, Pictures, Music, Videos
* [x] This Computer: local drives
* [x] Network locations
* [x] Recent locations
* [x] Persistence of pinned items
* [x] Remember last visited location

**Toolbar (Ribbon/Toolbar - Contextual)**
* [x] Home ribbon:
  * [x] Clipboard: Copy, Cut, Paste, Copy Path
  * [x] Files: New folder, New item, Rename, Delete
  * [x] Properties and quick access options
* [x] View ribbon:
  * [x] View types: Large icons, List, Details, Compact
  * [x] Show/hide panels: Navigation, Preview
  * [x] Show hidden files
  * [x] Show file extensions
  * [x] Selection checkboxes
  * [x] Grouping and sorting UI
* [x] Share ribbon:
  * [x] Share files/folders
  * [x] Compress to ZIP
  * [x] Print
  * [x] Send by email
  * [x] Advanced security
* [x] Contextual ribbons: dynamic based on file type

**Main Area**
* [x] Configurable grid
* [x] Multiple selection: Ctrl+click, Shift+rangeripgrep
* [x] Drag and drop: copy, move
* [x] Inline editing: F2 to rename
* [x] Full context menu
* [x] Real-time information (status bar)

**Right Side Panel (Optional)**
* [x] Preview:
  * [x] Images: large thumbnail
  * [x] Videos: frame + info (thumbnail requires ffmpeg)
  * [x] Documents: first pages (PDF via pdftotext, DOCX/ODT/RTF text excerpt)
  * [x] Audio: metadata
* [x] Details: name, type, size, dates, owner, permissions

**Status Bar (Bottom)**
* [x] Total items, selected items
* [x] Selection size
* [x] Available/total disk space
* [x] Operation status (progress)

### Core File Operations

**Selection**
* [x] Single selection, multiple non-consecutive (Ctrl+click)
* [x] Range selection (Shift+click)
* [x] Optional selection checkboxes
* [x] Select all (Ctrl+A)
* [x] Deselect all (Ctrl+Shift+A)
* [x] Invert selection (Ctrl+Shift+I)

**Basic Operations**
* [x] Copy: Ctrl+C, context menu
* [x] Cut: Ctrl+X, context menu
* [x] Paste: Ctrl+V
* [x] Copy path: Ctrl+Shift+C
* [x] Rename: F2, context menu, menu bar
* [x] Delete: Delete (trash), Shift+Delete (permanent)
* [x] Move to, Copy to (with destination selector and multiple selection)

**Creation**
* [x] New folder: Ctrl+Shift+N
* [x] New file: Ctrl+N
* [x] Create multiple elements

**Smart Drag and Drop**
* [x] Drag and drop enabled on workspace
* [x] Ctrl+drag: copy on same drive
* [x] Drag: copy to another drive
* [x] Shift+drag: move between drives

### View and Display Options

**View Types**
* [x] Large icons view
* [x] Small icons view
* [x] List view (default)
* [x] Details view
* [x] Persistent view configuration per folder
* [x] Quick switch: Ctrl+1, Ctrl+2, Ctrl+3

**Sorting**
* [x] By name, type, size, modified date
* [x] Ascending/descending
* [x] Grouping

**Visibility**
* [x] Show/hide hidden files (persistent)
* [x] Show file extensions (persistent toggle)
* [x] Selection checkboxes
* [x] Status bar


**Integrated Search**
* [x] Search in current folder with real-time results
* [x] Advanced search by type, size, date
* [x] Filters

**Navigation**
* [x] Editable address bar
* [x] Back, Forward, Up buttons
* [x] Navigation history
* [x] Quick access to frequent folders
* [x] Pin/unpin locations (bookmarks)

### File Management Advanced

**Special Files**
* [x] Shortcuts (.desktop files)
* [x] Compressed files (ZIP, TAR, 7z, RAR) — extraction only
* [x] Create compressed file (ZIP)
* [x] Extract from compressed file

**Properties**
* [x] Properties dialog
* [x] File information: size, location, dates
* [x] Security and permissions properties
* [x] Property editing (permissions)

**Trash**
* [x] Send to trash: Delete
* [x] Restore from trash
* [x] Empty trash
* [x] Integrated trash location in sidebar

### System Integration
* [x] Send to Desktop
* [x] Send to Email
**File Association**
* [x] Open with specific program (via xdg-open)  

### Core Keyboard Shortcuts

- [x] Alt+Up: Go to parent folder
- [x] Alt+Left: Go back
- [x] Ctrl+E: Focus search

- [x] Ctrl+Shift+I: Invert selection

- [x] Ctrl+V: Paste
- [x] Ctrl+Shift+C: Copy path
- [x] Delete: Move to trash
- [x] Shift+Delete: Delete permanently
View:
- [x] Ctrl+1/2/3: Change view

### Advanced Features (Future)


**History and Recents**
* [x] Recently opened files
* [x] Navigation history (back/forward)

**Multiple Operations**
* [x] Undo: Ctrl+Z (create, rename, move, file/folder copy, and trash operations)
* [x] Redo: Ctrl+Y (create, rename, move, file/folder copy, and trash operations)

**Compression**
* [x] Create ZIP (with CompressThread background)
* [x] Extract ZIP, TAR, 7z
* [x] Background extraction (ExtractThread)

---

## Reference folders

Another PyQt6 project with a useful Debian packaging example is available here:

```text
/xinput-plus/
```

---

## Current project structure

The project has been restructured into a modular architecture. Here is the current file structure with implementation status:

```text
linux-file-manager/
├── main.py                          [x] Entry point
├── pyproject.toml                   [x] Build configuration
├── README.md                        [x] Project readme
├── Roadmap.md                       [x] This file
├── lfm/
│   ├── __init__.py                  [x] Package init
│   ├── app.py                       [x] QApplication setup, translator loading
│   ├── core/
│   │   ├── __init__.py              [x] Package init
│   │   ├── config.py                [x] JSON config, bookmarks storage
│   │   ├── paths.py                 [x] Path constants (CONFIG_DIR, TRASH_DIR, VAULT_DIR, etc.)
│   │   └── translator.py            [x] QTranslator loader
│   ├── extensions/
│   │   ├── __init__.py              [x] Package init
│   │   └── manager.py               [x] Safe extension manifest discovery
│   ├── ui/
│   │   ├── __init__.py              [x] Package init
│   │   ├── main_window.py           [x] Main window with toolbar, menu bar, shortcuts, status bar
│   │   ├── sidebar.py               [x] Sidebar with Quick Access, This Computer, Bookmarks sections
│   │   ├── workspace.py             [x] QTreeView file listing with multi-selection
│   │   ├── preview_panel.py         [x] Right-side preview (text, images, metadata)
│   │   ├── property_dialog.py       [x] File/folder properties dialog
│   │   ├── create_multiple_dialog.py [x] Bulk file/folder creation dialog
│   │   ├── search_filter_dialog.py  [x] Advanced search filters dialog
│   │   └── menus.py                 [x] Context menu and toolbar menu classes
│   ├── services/
│   │   ├── __init__.py              [x] Package init, exports all services
│   │   ├── file_operations.py       [x] Copy, move, rename, delete, create folder/file
│   │   ├── trash_service.py         [x] FreeDesktop trash spec: send, restore, empty, list, count
│   │   ├── search_service.py        [x] Background search thread (current folder, recursive)
│   │   ├── extractor_service.py     [x] Archive extraction: ZIP, TAR, RAR, 7Z, DEB + ExtractThread
│   │   ├── bookmark_service.py      [x] Persistent bookmarks with JSON, XDG defaults
│   │   ├── tag_service.py           [x] SQLite-based file tagging: add, remove, search by tags
│   │   ├── operation_history.py     [x] Undo/redo stack for reversible and grouped operations
│   │   ├── operation_queue.py       [x] Background queue for file operation workers
│   │   ├── network_service.py       [x] Network mount discovery
│   │   ├── tpm_control.py           [x] TPM availability stub
│   │   └── vault_service.py         [x] Basic hidden-folder vault: lock/unlock, add/retrieve files
│   ├── models/
│   │   ├── __init__.py              [x] Package init
│   │   └── file_system_model.py     [x] Extended QFileSystemModel with human-readable sizes, type descriptions
│   └── utils/
│       ├── __init__.py              [x] Package init
│       └── open_with.py             [x] xdg-open wrapper, MIME type detection, default app setting
├── data/                            [x] Application metadata
│   ├── linux-file-manager.desktop   [x] Desktop entry file
│   ├── linux-file-manager.metainfo.xml [x] AppStream metadata
│   └── icons/
│       └── linux-file-manager.svg   [x] Application icon
├── translations/                    [x] Qt Linguist translation sources
│   ├── app_en.ts                    [x] English translation source
│   └── app_es.ts                    [x] Spanish translation source
├── scripts/
│   └── profile_memory.py            [x] Stdlib startup memory profiler
└── debian/                          [x] Debian packaging skeleton
    ├── changelog                    [x] Debian changelog
    ├── control                      [x] Debian control file
    ├── copyright                    [x] Debian copyright file
    ├── rules                        [x] Debian build rules
    ├── watch                        [x] Debian watch file
    ├── upstream/metadata            [x] Debian upstream metadata
    ├── linux-file-manager.desktop   [x] Debian desktop file
    ├── linux-file-manager.metainfo.xml [x] Debian AppStream metadata
    └── linuxfm.1                    [x] Manpage
```

---

## Modules to implement

### Core

```text
lfm-base        → lfm/core/         [x] config.py, paths.py, translator.py
lfm-framework   → lfm/app.py        [x] Application bootstrap
lfm-extension   → lfm/extensions/   [x] Plugin/extension manifest discovery
```

### Main application

```text
linux-file-manager       → lfm/      [x] Main application package
linux-file-manager-daemon → lfm/daemon.py [x] Minimal background maintenance daemon for optional text indexing
```

The daemon can be minimal at first, or simulated only for background tasks.

### UI

```text
workspace        → lfm/ui/workspace.py       [x] Main file view
sidebar          → lfm/ui/sidebar.py         [x] Left panel with sections
menu             → lfm/ui/menus.py           [x] Context and toolbar menus with Qt signal hooks
propertydialog   → lfm/ui/property_dialog.py [x] Properties dialog
```

### Features

```text
fileoperations   → lfm/services/file_operations.py  [x] Basic file operations
trash            → lfm/services/trash_service.py     [x] FreeDesktop trash spec
bookmark         → lfm/services/bookmark_service.py  [x] Persistent bookmarks
preview          → lfm/ui/preview_panel.py           [x] Text/image preview
search           → lfm/services/search_service.py    [x] Background search
tag              → lfm/services/tag_service.py       [x] SQLite file tagging
vault            → lfm/services/vault_service.py     [x] Basic hidden-folder vault
textindex        → lfm/services/textindex_service.py [x] Optional text indexing
operationqueue   → lfm/services/operation_queue.py   [x] Background operation queue
tpmcontrol       → lfm/services/tpm_control.py       [x] TPM availability stub only
extractor        → lfm/services/extractor_service.py [x] Archive extraction
```


---

## Feature details

### workspace

Main file view.

Requirements:

* [x] List view
* [x] Icon view
* [x] Path navigation
* [x] Open folders
* [x] Open files with default application
* [x] Keyboard navigation
* [x] Right-click menu
* [x] Multiple selection (Ctrl+click, Shift+range)

### sidebar

Left panel.

Requirements:

* [x] Home
* [x] Desktop
* [x] Documents
* [x] Downloads
* [x] Music
* [x] Pictures
* [x] Videos
* [x] Computer (File System root)
* [x] Trash (with item count)
* [x] Bookmarks
* [x] Mounted drives detection (/media, /mnt)
* [x] Network locations

### fileoperations

Basic file operations.

Requirements:

* [x] Copy
* [x] Move
* [x] Rename
* [x] Delete
* [x] Send to trash
* [x] Restore from trash
* [x] Create folder
* [x] Create empty file

Important:

* [x] File operations must not freeze the UI (copy/move/delete use worker threads)
* [x] Use worker threads where needed

### trash

Trash support.

Requirements:

* [x] Send files to trash (FreeDesktop spec with .trashinfo)
* [x] Show trash location
* [x] Empty trash
* [x] Restore files from trash
* [x] Trash item count in sidebar

Uses Linux FreeDesktop Trash specification.

### bookmark

Persistent bookmarks.

Requirements:

* [x] Add bookmark
* [x] Remove bookmark
* [x] Save bookmarks in config file (JSON)
* [x] Load bookmarks at startup
* [x] XDG default folders as initial bookmarks

### preview

Simple right-side preview panel.

Requirements:

* [x] Toggle preview on/off
* [x] Preview text files
* [x] Preview images
* [x] Show file details: name, type, size, dates, owner, permissions
* [x] Preview video frames (when ffmpeg is available)
* [x] Preview audio metadata
* [x] Do not block UI (preview loads in PreviewWorker)
* [x] Do not preview very large files automatically (text capped at 20000 chars)

### search

Basic file search.

Requirements:

* [x] Search in current folder
* [x] Optional recursive search
* [x] Must run in background thread
* [x] Do not freeze UI

### extractor

Archive extraction.

Supported formats:

```text
zip         [x] Python standard library
tar         [x] Python standard library
tar.gz      [x] Python standard library
tar.xz      [x] Python standard library
tar.bz2     [x] Python standard library
rar         [x] Requires unrar or rar command
7z          [x] Requires p7zip-full
deb         [x] Requires ar or dpkg-deb
```

* [x] Extract here (same directory)
* [x] Extract to... (choose destination)
* [x] Background extraction via ExtractThread
* [x] Create ZIP archives
* [x] Security: path traversal filtering for tar archives

### tag

Simple file tagging.

Requirements:

* [x] Use SQLite
* [x] Add tag to file
* [x] Remove tag from file
* [x] Search by tag (single tag)
* [x] Search by multiple tags (any or all match)
* [x] List all tags with file count
* [x] Context menu integration (add/remove tags)
* [x] Tag colors

### vault

Basic vault.

First implementation:

* [x] Hidden folder
* [x] Plain hidden-folder mode
* [x] Lock/unlock mechanism (marker file)
* [x] Add/move/retrieve/remove files
* [x] Vault size calculation
* [x] Destroy vault

Future implementation:

* [x] Optional encryption
* [x] Password protection

### textindex

Optional text indexing.

Requirements:

* [x] Disabled by default
* [x] Index only when user enables it
* [x] Must not slow down startup
* [x] Basic indexed filename search

### tpmcontrol

Ignore for now.

Create only a stub module if needed.

* [x] Stub module (TPM availability detection only; no TPM-backed vault behavior yet)


---

## Performance requirements

Very important:

* [x] Handle folders with 10,000+ files (covered by workspace regression test)
* [x] Do not freeze the interface (file operations, search, preview, and extraction use threads)
* [x] Avoid loading previews synchronously
* [x] Avoid recursive scanning unless requested
* [x] Avoid heavy icon processing (custom directory icon lookup disabled)
* [x] Use lazy loading where possible (initial network discovery is deferred)
* [x] Startup memory profiling baseline: `python3 scripts/profile_memory.py --path /tmp --json`
  measured ~65.7 MiB RSS after `MainWindow` creation in offscreen mode on the
  development environment.
* [x] Use worker threads for:
  * [x] copy (CopyWorker)
  * [x] move (MoveWorker)
  * [x] delete (DeleteWorker)
  * [x] search
  * [x] preview (PreviewWorker)
  * [x] extraction

The application must remain responsive.

---

## Internationalization

The application must be written in English by default.

But it must support translations using Qt Linguist.

Requirements:

* [x] Use `QTranslator`
* [x] All user-visible strings must use `self.tr()` (UI action labels and dialogs use Qt translation hooks)
* [x] Prepare `.ts` translation files
* [x] Load `.qm` files dynamically
* [x] Detect system language
* [x] Fallback to English if no translation is available

Translation folder:

```text
translations/
├── app_en.ts    [x] English translation source
└── app_es.ts    [x] Spanish translation source
```

---

## Debian packaging requirements

The package name must be:

```text
linux-file-manager
```

The executable command must be:

```text
linuxfm
```

Install command:

```text
/usr/bin/linuxfm
```

Python modules should be installed according to Debian Python policy:

```text
/usr/lib/python3/dist-packages/lfm/
```

Data files should go under:

```text
/usr/share/linux-file-manager/
```

Desktop file:

```text
/usr/share/applications/linux-file-manager.desktop
```

AppStream metadata:

```text
/usr/share/metainfo/linux-file-manager.metainfo.xml
```

Icon:

```text
/usr/share/icons/hicolor/scalable/apps/linux-file-manager.svg
```

Translations:

```text
/usr/share/linux-file-manager/i18n/
```

Manpage:

```text
/usr/share/man/man1/linuxfm.1.gz
```

---

## Debian dependencies

Initial dependencies:

```text
python3
python3-pyqt6
python3-pyqt6.qtsvg
xdg-utils
shared-mime-info
desktop-file-utils
gvfs
gvfs-common
gvfs-daemons
gvfs-fuse
gvfs-libs
gvfs-backends
cifs-utils
nfs-common
sshfs
davfs2
p7zip-full
unrar-free
zip
unzip
binutils
qt6-translations-l10n
python3-setuptools
dh-python
debhelper-compat (= 13)
```

Development/build dependencies:

```text
python3-setuptools
dh-python
debhelper-compat (= 13)
pyqt6-dev-tools
qt6-tools-dev-tools
python3-pytest
```

MX Linux 23 / Debian 12 integration command:

```bash
sudo apt install \
  python3 python3-pyqt6 python3-pyqt6.qtsvg \
  xdg-utils shared-mime-info desktop-file-utils \
  gvfs gvfs-common gvfs-daemons gvfs-fuse gvfs-libs gvfs-backends \
  cifs-utils nfs-common sshfs davfs2 \
  p7zip-full unrar-free zip unzip binutils \
  qt6-translations-l10n
```

GVfs and `gvfs-backends` enable network locations such as SMB, SFTP, WebDAV,
and other mounted shares on Debian-based systems including MX Linux 23.
`cifs-utils`, `nfs-common`, `sshfs`, and `davfs2` support network mounts that
also appear through `/proc/mounts`. MIME/default-application integration uses
`xdg-utils`, `shared-mime-info`, and `desktop-file-utils`. Archive support uses
Python's standard library for ZIP/TAR and external tools for RAR, 7z, and DEB
archives where needed.

Optional/future Debian packages to evaluate:

```text
libimage-exiftool-perl
poppler-utils
ffmpeg
python3-filetype
python3-puremagic
python3-pyqt6.qtpdf
python3-pyqt6.qtmultimedia
python3-dbus.mainloop.pyqt6
python3-watchdog
python3-pyinotify
python3-send2trash
python3-py7zr
python3-rarfile
python3-mediafile
python3-pymediainfo
python3-taglib
python3-pyqt6.qsci
python3-sphinx
python3-sphinx-qt-documentation
python3-pytest-timeout
python3-pytestqt
```

Notes for future use:

* `libimage-exiftool-perl`: installed locally for future advanced metadata/EXIF
  extraction in images, documents, audio, and video. Add it to `README.md` and
  Debian package metadata only after the application calls `exiftool`.
* `poppler-utils`: useful for PDF text previews through `pdftotext`; currently
  optional because PDF preview already degrades gracefully when missing.
* `ffmpeg`: useful for video thumbnails and metadata through `ffmpeg`/`ffprobe`;
  currently optional because video preview already degrades gracefully when
  missing.
* `python3-filetype` or `python3-puremagic`: candidates if file type detection
  moves from extension/MIME guesses to binary signature inspection.
* `python3-pyqt6.qtpdf`: candidate if PDF preview is moved from `pdftotext` to a
  native Qt PDF viewer widget.
* `python3-pyqt6.qtmultimedia`: candidate for native audio/video preview inside
  the PyQt6 UI.
* `python3-dbus.mainloop.pyqt6`: candidate for deeper desktop integration over
  D-Bus, such as portals, notifications, or richer freedesktop workflows.
* `python3-watchdog` or `python3-pyinotify`: candidates if directory refreshes
  need explicit filesystem event monitoring beyond `QFileSystemModel`.
* `python3-send2trash`: candidate if trash support should delegate more of the
  freedesktop trash specification to a maintained Python library.
* `python3-py7zr` and `python3-rarfile`: candidates only if archive extraction
  is moved from external `7z`/`unrar` commands to Python libraries.
* `python3-mediafile`, `python3-pymediainfo`, and `python3-taglib`: candidates
  for richer audio/video tag display or editing.
* `python3-pyqt6.qsci`: candidate if the preview panel grows into a code/text
  preview with syntax highlighting.
* `python3-sphinx` and `python3-sphinx-qt-documentation`: candidates if the
  project adds generated developer/API documentation.
* `python3-pytest-timeout`: candidate if tests involving threads or external
  tools begin to hang.
* `python3-pytestqt`: candidate if tests start using pytest-style Qt fixtures
  such as `qtbot`.

---

## Debian quality targets

The package should be clean enough to test with:

```bash
dpkg-buildpackage -us -uc
lintian
appstreamcli validate
```

---

## Development phases

### Phase 1 — Basic usable file manager [COMPLETED]

* [x] Main window
* [x] Sidebar
* [x] Workspace
* [x] Path bar
* [x] Back
* [x] Forward
* [x] Up
* [x] Home
* [x] Open folder
* [x] Open file
* [x] Basic right-click menu

### Phase 2 — File operations [COMPLETED]

* [x] Copy
* [x] Move
* [x] Rename
* [x] Delete
* [x] Send to trash
* [x] Create folder
* [x] Create empty file

### Phase 3 — Usability [COMPLETED]

* [x] Bookmarks
* [x] Properties dialog
* [x] Preview panel
* [x] Search in current folder

### Phase 4 — Advanced features [COMPLETED]

* [x] Extract archives (ZIP, TAR, RAR, 7Z, DEB)
* [x] Tags with SQLite
* [x] Basic vault (hidden folder, optional password-backed encryption)
* [x] Optional text index
* [x] Full keyboard shortcuts
* [x] Menu bar (File, Edit, View, Go, Tools, Help)
* [x] Enhanced context menus (file, folder, empty area)
* [x] Status bar with item count, selection size, disk space
* [x] Clipboard operations (copy/cut/paste internal)
* [x] Toggle hidden files
* [x] Toggle preview panel

### Phase 4 remaining tasks

* [x] Move copy/move/delete to worker threads
* [x] Move preview loading to worker thread
* [x] Icon view mode
* [x] Drag and drop support (enabled on workspace)
* [x] Inline rename (F2 in-place editing)
* [x] Invert selection (Ctrl+Shift+I)
* [x] Show file extensions toggle (persistent)
* [x] Create ZIP archives (with CompressThread background)
* [x] Undo/Redo support (create, rename, move, file/folder copy, trash, grouped create-multiple, grouped paste, grouped drag/drop, grouped Copy to/Move to, grouped Send to Desktop, and grouped trash operations)
* [x] Use self.tr() for all user-visible strings
* [x] Create .ts translation files
* [x] Reusable context and toolbar menu classes emit Qt signals for integration tests

### Phase 5 — Debian packaging [COMPLETED]

* [x] `debian/` folder
* [x] Desktop file
* [x] AppStream metadata
* [x] Manpage
* [x] Application icon (SVG)
* [x] Upstream metadata for Debian repository tooling
* [x] Lintian fixes (desktop/AppStream metadata and launcher install cleaned up)
* [x] Build `.deb` (verified local binary package build)

---

## How to run

The first working version runs with:

```bash
python3 main.py
```

After installing the package it must run as:

```bash
linuxfm
```

---

## Notes for Developers continuing this project

1. Read this Roadmap.md first to understand project status.
2. Check the `[x]` and `[ ]` markers to know what is done and what remains.
3. The project structure is in `lfm/` with subpackages: `core/`, `ui/`, `services/`, `models/`, `utils/`.
4. All code and comments must be in English.
5. User-visible strings should use `self.tr()` for future translation support.
6. Performance is critical: never block the UI thread for file operations.
8. The Debian packaging reference is in `/xinput-plus/debian/`.
9. When adding new features, update this Roadmap.md with the appropriate `[x]` or `[ ]` markers.
