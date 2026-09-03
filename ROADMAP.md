# ROADMAP.md — Linux File Manager

Last updated: 2026-09-02

It summarizes the real state of the project: what has already been achieved, what is pending, and where to look first.

## Project identity

- Project name: `linux-file-manager`
- Main Python package: `lfmapp`
- Goal: a lightweight file manager for Linux, written in Python + PyQt6
- Focus: performance, stability, user productivity, Debian packaging, and a practical user experience

Important note:
- It was internally renamed to `lfmapp` to avoid a conflict with the `lfm` package already available in Debian.

## Design principles

The file manager must be fast to use, with visible and accessible actions, without sacrificing clarity:

- Prioritize shortcuts and single-gesture actions for frequent operations.
- Preserve the user's context: accessible navigation, an editable location, and clear results.
- Avoid unnecessary interruptions: prefer inline feedback over excessive modals.
- Use consistent icons and text to reduce cognitive load.
- Offer a workflow that combines exploration and action without redundant steps.

## Interaction design

Key use cases to prioritize:

- Navigate between folders with keyboard and mouse without losing the selection or the context.
- Copy/move files with a clear conflict dialog, predictable actions, and "apply to all".
- Rename quickly from the `Details` view or with a direct command.
- Search and filter inside a folder with instant results and saved filters.
- Preview files without opening external applications, with the option to close the view quickly.
- Keep a stable side panel with quick access, operation status, and recent results.

## Key inspiration

The following subsections distill what was learned from the study of reference desktop file managers and their public documentation (see Sources of Inspiration at the end of this document) and rewrite it for Linux File Manager: no third-party ideas are transcribed; instead, the interaction logic behind each behavior is explained, translated to the Python + PyQt6 context and to the project's architecture, and closed with the operational requirements that should guide the implementation. Each subsection can be read independently and consulted when working on the associated phase.

### Distinction between filtering and structured search

Anyone working in a folder with many entries often needs to reduce the visible set until only what is relevant remains. The problem admits two distinct, complementary answers, and confusing them is the most common cause of frustration. **Filtering** acts on the list that is already on screen: it does not change location or scope, it simply hides the entries that do not meet the condition and stops hiding them as soon as the filter is removed; it is a cheap, immediate, and reversible operation, meant for the moment when you are inside a particular folder. **Searching**, by contrast, starts from a place and from broad criteria —the current folder, its tree, several paths, or the whole system— and builds a new results list that can bring together scattered files, at a higher cost in time and resources. If the interface does not maintain that separation, the user filters expecting results that only search can provide, or searches and loses sight of the fact that they are no longer inside a folder. That is why the quick filter must narrow only the current view, while search opens a results space of its own, with its scope and its query always visible. This distinction is developed in section 1.2.1 and in Phase 5.

- Distinguish between filtering and structured search: filtering acts on the current view and hides non-relevant items, while search builds results lists from a location and broader criteria.

### Structured search: criteria, scope, and refinement

A search that deserves to be called structured is not a single text box: it is a small workstation that answers four questions —**what** to look for (the criteria), **where** to do it (the locations), **what to skip** (the exclusions), and **what to do with the results** (a reusable collection). Separating these four pieces in the model is what makes it possible to offer both a quick single-field query and an attribute-based search capable of narrowing down thousands of files.

**Query criteria.** Simple mode builds the search by adding up independent conditions; all of them must be satisfied at once —conjunction— for an item to appear in the result, and each condition that has a value is visually distinguished so that the user can read at a glance what they are searching for:

- **Name**: with wildcards, regular expressions, or an "any word" mode (required terms with `+`, forbidden terms with `-`, and literal matching with `:`), plus options to ignore accents, distinguish case, and allow partial matches.
- **Content**: search for a string within the text of files, assuming UTF-8 when there is no byte order mark; it is the most expensive criterion and must be reserved for already-narrowed spaces, not for the whole disk.
- **Type**: restrict to files, folders, links, or a group of file types ("images", "documents") instead of forcing the user to enumerate extensions.
- **Date and time**: absolute operators (on, before, after, between, outside of) and relative ones ("within the last 7 days", "in the last half hour"), with the option to compare only the date, only the time, or both.
- **Size**: equal to, less than, greater than, between, outside of, or with tolerance (±25 % and ±50 %), to locate, for example, videos larger than one gigabyte without knowing the exact value.

**Simple mode and advanced mode.** Simple mode covers the criteria above for daily use. Advanced mode reuses the same filter engine as the view to add conditions on metadata that simple mode does not contemplate (image dimensions, audio duration, document author, etc.), sharing operators and rules with the Phase 5.2 filters so that learning one teaches the other.

**Search scope.** The user can specify one or several locations —the current folder with its tree, several paths, or an entire device— added with a button or by dragging folders into the list, and the list remembers previous searches. For convenience, the scope can stay linked to the active folder (if the user navigates elsewhere, the search follows it) or be disconnected to search "from here" without moving the panel. The usual options are descending into subfolders, entering compressed files, and silently skipping items without read permission.

**Exclusions.** What is never of interest —trash, hidden or system folders, version-control directories— is expressed separately by path, wildcard, or regular expression, with shortcuts to hide hidden and system folders. Excluding a folder not only filters the result: it avoids traversing it, which speeds up the search noticeably.

**Presets and reuse.** A complete query (criteria + scope + exclusions) must be saveable under a name and reloadable later, in addition to having a quick reset button and history of locations and exclusions. This connects with the saved searches of Phase 5.2 and with the collections of the "Results and duplicates as virtual collections" subsection.

**Results and refinement.** Results appear progressively in a virtual collection that can be directed to the current view, the other view, or a new tab, and that can be cleared before each query or accumulate several different queries. The **refine** operation repeats the search limiting the space to the previous results: it is the tool for the user who does not know exactly what they are looking for and keeps narrowing it down by trial and error ("first, everything containing 'report'; then, within that, whatever mentions 'audit'"), without having to formulate the final intent from the start.

**Implementation notes.** The query must be represented as a serializable object —a list of criteria with type, operator, and value, plus scope, exclusions, and options— executable in a service that emits progressive batches and cancels obsolete queries when a new one is written (Phase 5.1). The same criteria engine must feed the view filters, the advanced selection (Phase 6.1), and saved searches, so that a single evaluator explains all the behaviors and presets are stored with a version so they can be migrated in the future.

- Structured search combines name, content, type, date/time, and size criteria as a conjunction, with absolute and relative operators.
- It supports several locations, descending into subfolders and compressed files, with exclusions by path/pattern/regex that also avoid traversing folders.
- It allows saving named presets and refining previous results, showing the findings progressively in a virtual collection.
- The criteria engine is unique and shared by filters, selection, and search; queries are serializable and versioned.

### The quick filter: one gesture, one response

The most valuable filter is the one that requires no intermediate steps: the user thinks of a substring, types it, and the list responds instantly. To achieve that, the field must be invocable with a single key, accept immediate typing, and offer an equally short way out (`Esc` or a clear button). During the session it is worth keeping visible how many entries remain hidden: that number confirms that the filter is acting and indicates whether the criterion was too strict or too broad. The same quick-filter state can live in a popup bar or in a permanent field in the toolbar, but both surfaces must manipulate a single source of truth, without divergences. In addition, the quick filter stacks on top of global filters and folder formats without overriding them: what those layers hide stays hidden, so that the result is always predictable and the program never seems to "lose" files because of it.

- Offer a keyboard-accessible quick filter that activates immediately, shows the number of hidden items, and can be cleared with `Esc`.
- The filter field must be able to be persistent in the bar or popup, but it must always control the same quick-filter state and respect global filters and folder formats.

### The permanent filter field: quick filter or folder-format rules

The popup filter bar saves space, but there are users who prefer to always have a field in view in the toolbar. That **permanent filter field** is not a different filter: it shows the text of the active quick filter and, when edited, updates the same list and the same state that the popup bar would edit. That is why the product recommendation is that both surfaces be interchangeable in the interface, never two parallel states that could diverge. Pressing `Esc` clears the quick filter from either one, and the dropdown attached to the field offers useful shortcuts without typing anything: by default it lists the file types present in the current folder, which allows filtering by extension with a single click.

**One field, two possible destinations.** In addition to editing the quick filter, the field can be configured to edit the **folder-format rules**, that is, the persistent layers that decide which names are shown or hidden in that particular location. The configuration combines two decisions: **what** the pattern applies to (only files, only folders, or both) and **what effect** it produces (show only what matches, or hide what matches). Depending on that combination, the field writes to a different layer of the format:

| The pattern applies to… | With effect… | Writes to the format layer… | What the user sees |
| --- | --- | --- | --- |
| Only files | Show | File inclusion by name | The files that do not match are hidden; folders follow their own rules |
| Only folders | Show | Folder inclusion by name | Only the folders that match remain; files are not altered |
| Files and folders | Show | File and folder inclusion | Only what matches the pattern remains |
| Only files | Hide | File exclusion by name | The files that match are hidden; folders keep following their rules |
| Only folders | Hide | Folder exclusion by name | The folders that match are hidden and, with them, their content from this list |
| Files and folders | Hide | File and folder exclusion | Everything that matches disappears from the list |

This distinction matters for the design because it separates two questions that are often confused: "what am I typing?" (the pattern) and "what layer am I writing to?" (the short-lived quick filter, or a persistent rule of that folder's format). The field must expose both dimensions clearly —for example, a menu or an icon next to the field— so that the user always knows whether their typing affects the current session or the folder's remembered configuration.

**Field behavior options.** The following options must exist and, unless stated otherwise, have a sensible default value:

- **Real-time filtering**: the list updates while typing. It is the preferred behavior to see the immediate effect, but with very large lists it can be activated on demand so as not to penalize every keystroke.
- **Partial matching**: the pattern can match as a substring of the name instead of requiring the full name; internally this is equivalent to surrounding the text with wildcards, which is how it must be implemented to keep a single matching semantics.
- **Dropdown content**: with "auto-content" enabled, the dropdown offers one pattern per type present in the folder; when disabled, it shows the history of previously used patterns.
- **Clear filters and clear history**: separate actions; the first resets the filters in effect on the current list (without touching the global preference filters), and the second empties the dropdown's pattern history.
- **Configuration persistence**: the settings chosen for the field must not be lost between sessions; they are saved as a user preference, not as part of a particular folder's format.

**Implementation notes.** The field is best modeled as a view over a single filtering state (pattern + destination), not as a widget that applies changes on its own: the pattern is validated and shared with the popup bar and with any other surface; the destination (quick filter or format layer) decides which service is notified of the input. The format layer lives in the persistent per-location configuration (see Phase 7.3), while the quick filter lives in the panel's session state. The table above thus becomes a pure, testable function: given "scope" (files, folders, both) and "effect" (show, hide), it returns the format layer to be modified.

- The permanent filter field shares the quick-filter state with the popup bar, supports `Esc` to clear, and offers a dropdown with the types present in the folder or the pattern history.
- The field must be redirectable to the folder-format rules, combining scope (files/folders/both) and effect (show/hide) according to the table above.
- Offer real-time filtering, partial matching, separate clearing of filters and history, and persistence of the field's configuration.
- Model the field as a view over a single filtering state; the choice between quick filter and format layer must be a pure, testable function.

### Show everything without giving up filters

Sometimes the user needs to check what a folder really contains without losing the effort invested in configuring its filters. The "Show all" mode answers that need: it temporarily deactivates the visual filtering layer of the current panel, shows the full contents and, when deactivated, restores the previous state without manual reconstruction. It is not about deleting the configuration, but about postponing it while inspecting; that is why its activation must be evident —a visible indicator while it is active— and its scope local to the panel or tab where it was used. This operation is especially useful before deciding mass actions: seeing the complete set avoids acting on a subset that was not perceived as such.

- Implement a "Show all" mode that temporarily deactivates the visual filters of the current panel without losing the underlying configuration.

### Matching options: from character to expression

The default filter should be simple —a substring that appears in the name— but frequent users need to control exactly how text is compared. The relevant options are: partial matching versus whole-word matching, distinguishing between uppercase and lowercase, ignoring diacritics (important in Spanish), an "any word" mode that works like a phrase finder with required and excluded terms, and regular expressions for those who master that language. On that basis, conditions can be elevated to file attributes —size, date, type, content— through evaluable clauses that combine several criteria at once. The goal is not to overwhelm but to scale: the occasional user never sees more than they need, and the advanced user finds the entry point in the same place where they started.

- Advanced filtering options must include partial matching, ignoring diacritics, "any word" mode, regular expressions, and complex clauses based on attributes.

### Selection as a first-class citizen

Most operations —copy, move, delete, rename, tag— are not executed on individual files but on a prior selection. If the selection is the argument of almost everything, it must be treated as first-class state and not as a passing detail of the view: the program must be able to say at any moment how many files and folders are selected and how much they add up to, without requiring additional gestures. Moreover, manual selection is only one of the ways to build that state: it should be possible to generate it by pattern, by extension, by duplicates, by empty folders, or by any other criterion, and to invert, extend, or restore it. A well-defined, visible selection turns batch actions into safe, reviewable operations instead of blind bets.

- The selection must be a source of truth: count the selected files/folders, show size totals, and offer automatic selection by pattern, extension, duplicates, and other useful criteria.

### Sorting and grouping at your fingertips

The order in which items are displayed is a reading tool: sorting by date helps find recent items, and sorting by size helps locate what takes up the most space. That tool should not be hidden in dialogs: the column header is the natural place to change the criterion with one click, invert the direction with another click or with a modifier key, and add sorting levels while holding down another one. Complementarily, grouping separates the list into blocks according to a field —the same one used for sorting or a different one— and each group can be collapsed or expanded to reduce visual noise and to operate on the whole set at once. Both sorting and grouping must be able to refer to fields that are not visible at that moment: one does not always want to show the column by which the list is organized.

- Sorting and grouping must be controllable from the column headers, with support for non-visible fields and keyboard modifiers to invert or add levels.

### Source and destination: an explicit model for operations

Copying or moving always involves two places: where the items come from and where they go. When that relationship is implicit, the user guesses; when it is explicit, the user acts with confidence. In dual view the assignment is natural —one panel is the source and the other is the destination— but the model must not be limited to it: in single view the user must be able to declare which is the active destination through focus, a shortcut, or a toggle, without losing the current selection in the process. The copy, move, and paste operations then consult that state and decide their target without guessing, and the source and the destination must remain visible and interchangeable so that the flow is identical with one view or two.

- The copy/move flow must explicitly handle source and destination: in dual panels, one panel is the source and the other is the destination; in single mode, the user must be able to activate the source/destination through focus, a shortcut, or a toggle without losing the selection.

### Operation queue with grouping rules

Running several transfers at once is not always faster: when two operations compete for the same physical disk or the same network link, parallel work can degrade overall performance below that of sequential execution. The operation queue resolves that trade-off: it automatically decides when a job must wait —same physical destination device, same removable drive, same network location, same file— and allows the user to intervene when the automatic criterion does not suit them, by reordering the waiting jobs, launching them immediately, or canceling them. The result is that the application takes advantage of parallelism where it is worthwhile and avoids it where it hurts, with transparency about what is queued and why.

- The operation queue must run jobs sequentially when appropriate, with prioritization rules based on device, destination, and source type, and allow manual management of waiting jobs.

### Favorites, quick access, aliases, and recent places

Much of navigation is repetition: the same few folders are visited over and over. Linux File Manager already has sections for quick access, bookmarks, and recent places in the sidebar; the ambition is for that location memory to be available on every surface where the user works: menus, toolbar, sidebar, and command palette. Frequent paths must be addable by dragging them, organizable by renaming them, and openable in the right context; aliases make it possible to refer to long paths with a short, stable name, so that changing the real path does not force updating every existing reference.

- Favorites and quick access must be available in toolbars, menus, and lists, with support for drag and drop, path aliases, and recent paths.
- Favorites, quick access, and aliases must be accessible from the sidebar, the toolbar, and the palette, with support for drag and drop, renaming, and opening in context.

### Global and per-panel navigation history

Returning to an already-visited folder should not require rebuilding the path from scratch. Navigation history fulfills that role if it exists on two scales: a global recent list for the program, useful for jumping between projects, and a local history per panel or tab that feeds the Back and Forward buttons. Both must be visible and manageable: the path control can unfold the lists, the back buttons can show the full trail, and the shortcuts must be clear and consistent. Keeping the history alive is also a way of preserving context when switching between tasks, because it allows returning to the exact point where the work was left.

- Navigation history must exist both globally and per panel, and be accessible from the path control, the Back/Forward buttons, and dropdown menus.
- Navigation history must be accessible both globally and per panel, with recent lists in the path bar and clearly visible back/forward shortcuts.

### Status bar with useful context

The status bar is the natural place for the context that is needed without asking for it: how many items there are and how many are selected, how much they add up to in size, whether there are entries hidden by filters, which display format is active, and how much free space is left on the device. That block of information turns potentially dangerous actions into informed decisions —deleting a group knowing its size, or filtering knowing how much is hidden— and it does not compete for attention when kept discreet and configurable.

- The status bar must show relevant information such as selection, total size, hidden items, current format, and free space on the device.

### Results and duplicates as virtual collections

Search and duplicate detection produce sets whose members can be scattered across many real folders. Presenting them inside a physical folder would force choosing a false location or losing the connection with the query. The alternative is a virtual space —a collection— that behaves like a folder: it allows browsing the results, opening the real location of each item, and running on them the same operations as on normal files, while keeping the query that originated them. Thus, the result of a search is not a dead end, but a workspace from which to keep acting.

- Search and duplicate results must be displayable in virtual spaces or collections that behave like folders without losing the original query.

### The utilities panel: tools that do not interrupt

Certain tools —structured search, folder synchronization, duplicate finding— are powerful but are not part of the daily navigation flow. Confining them to a reusable bottom panel allows invoking them when needed without hijacking the main window: the panel can share space with other utilities, collapse to let the user keep working while a long operation continues, and close without canceling what is in progress. In this way, auxiliary tools share a single container and a single non-interruption logic, consistent with the overall goal of reducing modals.

- The utilities panel must be able to hold tools such as advanced search, synchronization, and duplicate search without interrupting the main flow.

### The folder format: the visual memory of each location

The presentation of a folder —view, columns, order, grouping, and visibility rules— is information that the user adjusts once and expects to find again. Instead of treating each adjustment as an isolated change, it is better to group them into a **folder format**: an object that describes how a particular location is displayed and that can be saved, consulted, and reused. Thus, whoever always sorts their downloads folder by date, with specific columns, does not have to repeat the operation on every visit: when navigating there, the program applies the remembered format. The richness appears when formats stop being only "by path" and admit more sources: a format can apply to an exact path, to all its subfolders, or to paths that match a pattern; there can be a default format that is applied when no other more specific one fits; and there can be favorite formats that the user activates with a gesture from the folder menu.

**Automatic formats by content.** The file manager can decide the presentation by itself if allowed: if a folder contains mostly images, show it in thumbnail mode; if it contains music, highlight the duration columns. So that this change does not come as a surprise, activation must be optional and governed by explicit, visible rules: a group of file types (images, documents, audio), a percentage threshold of files belonging to that group, and a minimum or maximum number of files for the rule to trigger. The user must be able to see which rule was applied and why, and to turn it off for that folder without losing it entirely.

**Format locking and provenance.** Two mechanisms avoid the confusion caused by automatic changes: the **format lock**, which freezes the current presentation so that it does not change by itself while navigating (manual adjustments remain allowed, but nothing else modifies it), and the **provenance indicator**, a status bar element that explains how the current format was obtained —"it started as an automatically remembered format and then a column was added to it"— with direct access to format, lock, and reset commands. Without that indicator, a format that changes "by itself" is one of the most disconcerting experiences in a file manager.

**Implementation notes.** The format must be a serializable value independent of the widget (view, columns, order, grouping, visibility rules), resolved by a service that decides which one to apply according to a hierarchy of sources —path/pattern, content type, folder type, favorite, default user format—. The resolution must be deterministic and explainable to feed the provenance indicator; the lock is a flag that stops automatic resolution but not manual changes. The content-based format is computed from the existing file-type groups and from configurable thresholds, without rescanning on the main thread.

- The folder format groups view, columns, order, grouping, and visibility, and can be saved by path, subfolders, or pattern, with a default user format as the last resort.
- Allow automatic formats by content type (group of types + percentage threshold + minimums/maximums), optionally activatable and explainable.
- Offer format locking and a provenance indicator in the status bar with reset and management commands.

### Productive folder tabs: groups, colors, and drag destinations

Linux File Manager already navigates with tabs and keeps its own history for each one; the next level is turning the tab into an element that the user works with, not just a passive container. A tab must be **identifiable** (its own color and a custom name with tokens such as the path or the folder name), **openable in useful contexts** (the current folder, its parent, the selected folders, the parent of the selected items), **duplicable**, and **recoverable** after an accidental close. Keyboard and mouse must coexist: switch with `Ctrl+Tab` or directional shortcuts, close with the middle mouse button or double-click, and create a tab with `Alt` + double-click on a folder or from the context menu.

**Tab groups.** When a project is always worked on over the same set of folders, opening them one by one is repetitive. A **tab group** saves that set as a unit: when activated, the program opens all the folders in the group at once, preserving the assigned names and colors, and it can decide whether to close the existing tabs or coexist with them. It is the same memory as favorites, but applied to the complete working state, not to a single path. Groups must be saveable from the current tabs (of one panel or of both) and manageable from the preferences.

**The tab as a drag destination.** Dragging files over another tab must mean "copy or move to that folder": when the cursor is kept over the tab without releasing the button, that tab activates and allows dropping inside its subfolders. This interaction turns tabs into a destination as natural as the opposite panel or the sidebar, and it must work the same in single-panel mode and in dual view, where a tab on one side can be **linked** with a tab on the opposite side so that activating one activates the other, or remain in linked-navigation mode when the destination is meant to follow the source.

**Implementation notes.** The per-tab state already exists (path and history); it must be extended with a custom name, color, lock/link indicators, and group membership, without breaking the migration of previous sessions. Tab groups are serialized as lists of paths plus visual metadata. Dragging over tabs requires integrating the tab as a valid drag-and-drop destination of the file area, with hover as the activator, reusing the same source/destination logic as the rest of the operations.

- Each tab must be identifiable (color, custom name), duplicable, able to open selected folders, and recoverable after an accidental close.
- Tab groups store sets of folders with their visual identity and can be opened in a single operation, closing or keeping the previous tabs.
- Dragging files over a tab uses it as the destination (with hover activating the tab), and in dual view tabs can be linked or navigate in a synchronized way.

### Flat view: one folder and its whole tree, at a glance

Sometimes the user does not want to go down folder by folder to find a file: they want to see, in a single list, everything inside a folder and its subfolders, at any depth. The **flat view** answers that: it collapses the hierarchy into a single view that behaves like a normal folder —you can double-click, drag, copy, delete, and filter— with the advantage that the results of a quick filter also cover nested files. It must offer three degrees: mix files and folders from the whole tree; show only files, hiding the folders; or group the result preserving the tree structure, so that each subfolder appears as a collapsible block. This third form is also the natural space to show the result of a synchronization or a duplicate search, because it groups by real location without losing the overall view.

**Operating on nested files.** The real difference from a normal folder appears when copying or moving files that live in subfolders: the file manager must ask whether to **recreate** the relative source structure at the destination (copy `A/x/foto.jpg` to `Destino/x/foto.jpg`) or dump everything into the same destination folder. Dropping a file on the background of the view —not on a subfolder— must use the base folder as the destination; since that can accidentally move a nested file to the base, the operation must be undoable and the interface must remember the risk.

**Implementation notes.** The flat view is a way of presenting the result of walking the tree, not a second data model: an adapter that flattens the hierarchy on the fly and exposes the relative-location column so that the user knows where each item comes from. Filtering is applied to the flattened result and must decide explicitly whether a hidden folder drags its files along with it. Copy/move operations consult the same operations engine and add the structure mode (recreate or same folder).

- The flat view shows the contents of a folder and of its whole tree as a single list, in mixed mode, files-only mode, or grouped by structure.
- Copying or moving nested files offers recreating the source structure or dumping them into the same folder; dropping on the background uses the base folder as the destination.
- Filtering and search must operate on the flattened result, with the relative-location column visible and an explicit decision about hidden folders.

### Filtered operations: acting only on what matches

The file manager must be able to run a file operation **not only on the visible selection, but on the items of a folder (and its subfolders) that meet a criterion**. For example: copy only the images inside several subfolders, or delete all the `.tmp` leaving the rest intact. To that end, functions such as copy and delete accept an **operation filter** that is applied recursively: each potential item is compared against the filter and is processed only if it matches. The filter must be activatable from the menu of the action itself (e.g. "copy with filter"), stay active while the user needs it, and deactivate automatically when the function finishes if so chosen, so as not to leave a surprising state. Before executing, the user must be able to see what is going to happen: a button that applies the filter as a selection in the current view shows exactly which items would be affected.

**Clauses, not only wildcards.** A well-made operation filter is more than a name pattern: it is built with **clauses** that compare an attribute (name, size, date, type) against a value, each with a match or no-match state —the equivalent of negation—, linked with `and` or `or`, and with the possibility of grouping clauses into sub-levels that act like parentheses. That readable boolean structure makes it possible to express real cases such as "`.jpg` files larger than 100 KB, or `.gif` files smaller than 50 KB", and it must be saveable in a repository of reusable filters that search, advanced selection, synchronization, and duplicate search also access, so that a single filter model explains all the entry points.

**Implementation notes.** The operation filter is defined as a tree of clauses (attribute, operator, value, negation, logical link) evaluable against a file entry; the same tree feeds the search and selection criteria engine described in previous subsections. The operation filters item by item recursively before enqueuing the job, and the filter state (active / deactivate on completion / skip this time) lives in the operations controller, not in the dialog. "Apply as selection" is a low-cost bridge for the preview: evaluate the filter on the current list and select the result.

- Copy, move, delete, and attribute changes must accept a filter that decides which items of the folder and its subfolders are processed, activatable per operation and deactivatable on completion.
- Filters are built with boolean clauses (attribute + operator + value, with negation, `and`/`or`, and sub-levels) and are saved in a repository shared with search, selection, synchronization, and duplicates.
- Before executing, the interface allows previewing the scope by applying the filter as a selection in the current view.

### Folder synchronization in two phases

Keeping two folders up to date —a local project and its backup, a laptop and a desktop— is a frequent task that a file manager can solve with a **synchronization** tool executed in two separate phases, because the second one should only happen once the first has been reviewed. In the **comparison** phase, the program examines both locations and computes which files would have to be copied or deleted according to the chosen rules; in the **application** phase, it executes those changes once the user has verified the result. The comparison can be bidirectional (each file is copied toward the side holding the newest version) or unidirectional (always from source to destination), and in unidirectional mode the update criterion must be selectable: byte-by-byte comparison, different date, different date or size, size, or name —when only copying what does not exist matters—. In addition, the tool must decide what to do with the files in the destination that do not exist in the source: delete them (to the trash or permanently, and before or after copying) or leave them.

**Review as part of the flow.** The value of the tool lies in the comparison being reviewed before applying: the affected items appear marked with the recommended action —copy, delete, or nothing— and the user can change that action item by item, hide the unaffected ones to see only what is going to happen, and consult the conflicts (e.g. a file with the same name as a folder on the other side). Two practical details make it reliable in the real world: ignoring differences of one hour (due to seasonal clock changes on file systems that store local time) or of seconds (due to different resolutions between systems), and allowing locations or file types to be excluded so as not to synchronize junk such as version-control directories. The source and destination fields must be able to stay linked to the active folder of each panel, so that navigating automatically updates the scope of the synchronization.

**Implementation notes.** Comparison and application are two distinct jobs of the operations engine: the former produces a list of planned actions (with their criterion and their justification), the latter executes the confirmed ones through the usual queue, with its conflict rules. The review view can reuse the selection model with action states instead of binary selection. The result is a utilities-panel tool that shares the engine, rules, and registry with the rest of the program.

- Synchronization compares two locations in a first phase and applies, in a second phase, only the confirmed changes, with bidirectional or unidirectional mode.
- The update criterion is selectable (bytes, date, date/size, size, name) and the fate of orphan files is decided explicitly (delete to trash or permanently, before or after copying).
- The review shows the planned action per item, allows modifying it, hiding the unaffected ones, and viewing conflicts; it supports exclusion of locations and date/time tolerances.

### Folder sizes: how much each directory weighs

The file system does not know the total size of a folder: knowing how much a directory occupies requires walking through it and adding up its files, sometimes recursively. Even so, it is one of the most frequent questions —"what is eating the disk?"— and the file manager must be able to answer it by showing the size of the folders in the list just as it shows that of the files. The calculation must be able to be **triggered by hand** (select folders and ask for the calculation, or simply keep the cursor over a folder until its information appears) and, if configured, **automatically** when reading certain folders or when columns that depend on the contents of subfolders are shown, such as the total number of files. Since the calculation runs in the background, the displayed value must **update progressively** and be marked as approximate while it is not complete.

**Honesty about precision.** A folder size is a guide, not an exact figure: permissions can prevent some subfolders from being read, and symbolic links can be counted or ignored with very different results. The approximate marker must also appear when part of the tree could not be read, and the program must allow configuring whether links are counted or not. Without that honesty, the user would trust figures that depend on factors they cannot see.

**Implementation notes.** The calculation is a job of the operation queue or of a dedicated calculation pool: it walks the tree without blocking the interface, publishes partial results, and is cancelled when leaving the folder or changing the selection. The result is cached and invalidated when the contents change. The size column and the status bar indicator share the same service, so that what the list shows and what the total shows are consistent.

- Show the total size of the folders in the list, calculated by hand (selection or hover information) or automatically when columns that depend on subfolders are needed.
- Update the value progressively in the background and mark it as approximate while the calculation is not complete or part of the tree could not be read.
- Allow configuring whether symbolic links are counted, with an invalidatable cache and cancellation when the context changes.

### Folder tree: the hierarchy as a navigation surface

The current sidebar organizes shortcuts by categories, but the file system is above all a hierarchy, and there are users who think of it that way: go up, go down, compare branches, and drag from one branch to another. A **folder tree** in the sidebar offers that view as a single piece: each expandable folder reveals its children, selection navigates instantly, and the keyboard can handle everything —arrow keys to move, `→`/`←` to expand and collapse, `F2` to rename and `Del` to delete from the tree itself—. The relationship with the main view must be bidirectional: when navigating from the tree, the list changes; when navigating from the list or from a tab, the tree reveals and highlights the path to that folder, also marking the paths of the other open tabs so that it can be seen at a glance where work is being done. In a future dual view, the tree can be shared (it follows the active panel) or duplicated per panel.

**Tree health controls.** A large tree easily becomes messy, so it needs three hygiene tools: **locate**, which re-centers the view on the current folder when it has been lost from sight; **collapse everything except the current path**, to return to a manageable state in one gesture; and **expansion presets**, which remember which branches were open to restore them instantly. Tree items must also support persistent marking (for example, "pinning" a folder so that it is not collapsed) and renaming, deletion, and dragging with the same behavior as in the list.

**Implementation notes.** The tree is a second consumer of the same file model, with its own expansion state independent of navigation. Synchronization with the main view must be done through folder-change events (scroll to the index, expansion of the path, and highlighting), not through a full rebuild. Navigation from the tree reuses the existing `NavigationController`, and the rename/delete actions on the tree share the same services as the list so as not to duplicate logic.

- The sidebar must offer a hierarchical folder tree with click and keyboard navigation, expansion/collapse, and rename and delete actions consistent with the list.
- The tree must synchronize with the main view and the open tabs, highlighting the current path and allowing locate, collapse everything except the path, and saving expansion presets.
- In dual view, the tree can be shared (it follows the active panel) or independent per panel.

### Path bar with breadcrumbs: navigate the path, not just type it

The current path bar is an editable field: it serves its purpose, but it forces typing to jump to a higher level. A **breadcrumb** bar turns each component of the path into a button: clicking the corresponding crumb navigates directly to that level, with a right-click on it that opens that folder's menu and arrows next to each crumb that unfold its contents to jump to a subfolder without going through the list. The same bar supports two coexisting uses: breadcrumb mode for visual navigation and, by clicking on an empty area or pressing the shortcut, an **edit mode** where the full path is typed with autocomplete. This duality covers both types of user: whoever knows the exact path types; whoever explores, clicks.

**Details that make the difference.** The icon of the current folder on the left can be dragged to create shortcuts or be used as an "overflow" menu when the path does not fit: the bar shows the deepest levels and keeps the upper ones in a menu, so that no part of the path remains inaccessible. After navigating upward, the branches of the deepest visited point can be kept as **ghost breadcrumbs**, a visual reminder that allows returning to the same relative place within another sibling branch (for example, from one user's profile to another's with the same structure). The menu at the far right keeps access to the recent places, connecting the bar with the location memory described in previous subsections.

**Implementation notes.** The crumbs are buttons generated from the parts of the active path; the edit field shares the state of the bar (it switches between modes without losing the text) and reuses the current `path_edit` logic. Unfolding the contents of a crumb can be served with a light read of the corresponding directory. Overflow is a layout problem with a deterministic solution: show as many lower crumbs as fit and put the rest in the current icon's menu.

- The path bar must work as clickable breadcrumbs (navigate to the level, per-folder menu, unfold contents), with manual edit mode via shortcut or click on an empty area.
- Support overflow when the path does not fit, a draggable current-folder icon, and ghost breadcrumbs to return to the visited depth.
- The menu at the far end must link to the recent places and to path autocomplete, sharing state with the current editable bar.

### Automatic marking and highlighting by rules

Linux File Manager already has colored labels assigned by hand; what is missing is the layer that turns color into automatic information. An **appearance rule** system evaluates each item of the list and decides how to show it without the user having to mark it one by one: all `*.doc` in green, images larger than 1080p in bold, the folders of a project in a distinctive tone. Each rule defines a condition —name pattern, type, size, path, or any evaluable attribute— and an effect: text color, font style, overlaid icon, a status marker in its own column, or "pinning" the item to the beginning of the list. Rules are evaluated in order and can **stack** (a file can be green because of its type and bold because of its size), with a "stop at the first match" option when the user wants a rule to dominate the others.

**Deliberate and understandable use.** Automatic marking is useful only if it does not confuse: it must be clear why an item looks different, manual application must be able to **prevail over** the rules (or coexist with them depending on preference), and the whole system must be able to be turned off in one go to see the list without visual noise. On the technical side, it is worth distinguishing the data (which rules exist and in what order) from the visual effect (how each row is painted), and separating ephemeral marking —based on the session or on configuration— from any real persistence in the file, which corresponds to the existing label system.

**Implementation notes.** The rule engine can reuse the clause tree of the filter evaluator (subsection "Filtered operations"): each rule is a filter with an associated effect. The result is applied in the view's painting delegate (color/font/icon) and never modifies the data model. Evaluation must happen in the background or lazily for large folders, and be re-run only when the contents or the rules change.

- Add appearance rules evaluable by pattern, type, size, path, or attribute, with effects of color, font, icon, status marker, or pinning to the beginning of the list.
- Allow rule stacking with a "stop at the first match" option, prevalence of manual marking, and global deactivation.
- Reuse the filter clause engine to evaluate the rules and apply the effects only in the painting delegate, without touching the model.

### Duplicate finder: recovering space methodically

Duplicate files are one of the few problems that get worse on their own: the more the disk grows, the more redundant copies accumulate and the harder it is to tell them apart by hand. A **duplicate finder** automates the task with two complementary modes: find all the files that appear more than once in the chosen locations, or find duplicates of one or more specific files that the user points out. The comparison method must be scalable and explicit, because each level costs more and gets it more right: first only name, then name and size, then size and, only when certainty is needed, **content hash** —computed first on files of the same size and with the option of reducing the analyzed portion to speed it up, or of caching results for large files—. The scope is controlled as in search: several locations, subfolders, compressed files, and a filter to limit what is compared (for example, only `*.jpg`).

**Results that invite action.** Results must be grouped automatically so that each set of duplicates is a visible unit, and the tool must help decide what to keep: with a single gesture the duplicates are selected according to criteria ("keep the most recent", "keep the one with the shortest path") and the selected ones are deleted with the normal deletion and trash flow, never with a special destructive action. Thus the finder does not only inform: it delivers a reviewable selection ready for the usual operation.

**Implementation notes.** Content comparison is a heavy job of the operation queue or of a dedicated pool: first group by size (cheap) and only hash within groups of equal size. The results are dumped into a grouped virtual collection (reusing the subsection "Results and duplicates as virtual collections"), and the selection assistant produces a standard selection that the rest of the program already knows how to handle.

- The duplicate finder must support two modes (all duplicates, or duplicates of specific files) with a scope of several locations, subfolders, compressed files, and an optional filter.
- The comparison scales by level of certainty: name, name and size, size, and content hash with cache and speed-up option.
- Results are grouped automatically into a collection and an assistant selects what to keep, so that deletion uses the normal trash flow.

### Quick Show: the preview that does not interrupt

The side preview already shows the selected image; the next step is a **quick viewer** that responds instantly, without bars or menus, taking up all the available space to show the image at natural size: something similar to macOS's "Quick Look". It opens with a minimal gesture —the space bar over an image file, or holding down the mouse button—, closes with `Esc` or when releasing the key, and in that state almost all keys remain free for the only thing that matters: `←`/`→` to jump to the previous or next image in the folder. If the image is larger than the screen it is fitted, and keeping the button pressed allows seeing it at 100 % while inspecting.

**Implementation notes.** The quick viewer reuses the image loading pipeline of the preview panel (background reading, without blocking the interface) and the folder order for the previous/next sequence. It is a separate window or layer without decoration that opens over the content; its configuration —activation key, close on release, fit to screen— lives in the viewer preferences, and it must coexist with the side preview without duplicating the loading of the same image.

- Offer an undecorated quick viewer, invocable with a minimal gesture (e.g., space bar over the image) and closable with `Esc` or when releasing the gesture.
- Navigate between the folder's images with the arrows, fit to screen, and allow inspecting at 100 % while holding down.
- Reuse the loading pipeline of the preview panel so as not to duplicate decoding or block the interface.

### Productive inline rename (inline rename)

Renaming a single file —pressing `F2` and typing— already exists in Linux File Manager thanks to the file model editor. What is missing is turning it into a **complete keyboard session**, not a simple text field. The first convenience concerns selection: when entering rename mode it is advisable to select only the **name root**, not the extension (which one almost never wants to touch), with the possibility of switching to select the extension or the whole name with a key. That small detail removes the gesture of deselecting the extension on every file.

**On-the-fly transformations.** While renaming, the keys must offer immediate transformations on the selection: change to lowercase, to uppercase, capitalize words; convert dots and underscores into spaces (respecting the dots between numbers, such as those of a version `2.1.0.20`); and select parts of the name (all, root, extension) without letting go of the keyboard. These are operations that today would force rewriting the entire name and that in inline mode are resolved with a single keystroke, applied only to the selected portion.

**Flowing between files.** A batch of individual renames should be traversable without going back to the list: the up/down arrows (or `Tab`) apply the current change and move on to renaming the next or previous file, optionally preserving the cursor position. Memory also helps: a **history of used names** allows recovering a previous name with the arrows, and **copying the name of the neighboring file** —with or without extension— solves the cases in which a batch shares a root but differs in one detail. All of this must be configurable in the preferences, not a fixed set of shortcuts.

**Implementation notes.** Inline mode reuses the model editor but wraps it in its own control that intercepts the transformation keys before passing them to the field, keeps the root/extension/name selection, keeps the per-folder history, and manages advancing to the next file. The conversion of dots/underscores into spaces and the capitalizations are implemented over the current text selection, with the same character sanitization rules as batch rename.

- When entering inline rename mode, select the name root by default (not the extension), with keys to change the selection to extension or full name.
- Offer keyboard transformations on the selection: uppercase/lowercase/capitalization and conversion of dots and underscores into spaces (respecting numeric versions).
- Be able to walk through adjacent files applying each change, with a history of used names and copying of the neighbor's name, all configurable.

### Batch rename: a dialog that teaches before applying

Renaming many files at once is one of the tasks where the difference between a well-designed file manager and an improvised one is most noticeable. The key is separating three moments that today are confused in Linux File Manager: **define the transformation**, **see the result before executing**, and **apply as a single reversible operation**. The dialog must work as a living tool, not as a form that is filled in blindly.

**The preview is the heart of the dialog.** Before touching any file, the user sees a "before/after" table that updates with every configuration change; items can be **checked or unchecked** to exclude them from the batch, and a specific name can be corrected by editing it directly —that name remains "pinned" and visually marked (e.g., in color) so that the program does not touch it again with later transformations—. It must also be possible to **hide the items that are not going to change**, so that the table shows only what will really be modified. The difference between what changes and what does not is valuable information: a batch that changes nothing must look empty before pressing the button.

**Apply without closing and instant undo.** A dialog that forces accepting to see the result forces reopening it if something went wrong. It is worth offering **apply** (executes the batch and keeps the dialog open to keep adjusting) together with an **immediate undo** of the last applied batch, in addition to the program's normal operation log. Thus the "try, look, fix" flow does not require restarting the configuration on each attempt.

**Implementation notes.** The transformation is modeled as a pure name→name function (a chain of ordered, toggleable rules: find/replace, wildcards, regular expressions, numbering, uppercase/lowercase), applied to a list of items with the extension preserved by default. The preview is computed over that function without touching the file system; the names edited by hand are stored as a per-item exception. The apply button invokes the operations engine with a single operation per batch (recordable and reversible).

- The batch rename dialog shows an editable "before/after" preview: check/uncheck items, correct names by hand (visually pinned), and hide what does not change.
- Offer applying without closing the dialog and immediate undo of the last batch, in addition to the normal operation log.
- Model the transformation as a pure function with ordered rules (replacement, wildcards, regex, numbering, case) and extension preserved by default.

### Match modes and actions of batch rename

The name transformation is best expressed as **a match mode plus a set of actions**, because each user arrives with a different need. The mode defines how the "from" and "to" fields are interpreted: write the new name literally, with **wildcards** (the `*` marks which part of the original name is kept), with **find and replace** of plain text, or with **regular expressions** for those who need to capture and reorder parts of the name (e.g., turn `YYYY-MM-DD_nombre.txt` into `nombre DD-MM-YYYY.txt`). Two switches matter in all modes: **match case** when comparing, and **ignore the extension** so that the pattern does not have to guess it nor can break it by accident (option enabled by default).

**Combinable actions on the result.** In addition to the mode, the batch can apply transformations that run afterwards and accumulate: **capitalization** (all lowercase, all uppercase, capitalize each word, capitalize the first word, and separate treatment of the extension), **numbering** with starting number, number of digits (leading zeros), and increment, placed at an explicit marker in the name or, by default, at the end before the extension, and **text removal/insertion** at positions relative to the beginning or the end of the name (useful when names do not have the same length). These actions must be able to be activated and combined in any order and to be applied even if the main pattern did not match some file, if so requested.

**Implementation notes.** The modes share a single evaluator with the search criteria engine (previous subsections): the rename wildcard is the same pattern language as the quick filter, and the regular expression shares the same syntax. Numbering uses an explicit marker in the template (equivalent to a `[#]` placeholder) and applies zero padding. The relative text actions operate on anchors (start/end of the name) so as not to depend on equal lengths.

- Batch rename supports modes of literal name, wildcards with preservation of parts, find and replace, and regular expressions, with options of case sensitivity and ignore extension.
- Offer accumulating actions: capitalization with extension treatment, configurable numbering (start, digits, increment, position), and text editing by anchors.
- Share the pattern syntax with the search engine and express numbering with a placeholder in the template.

### Presets and memory of the rename

Configuring a good batch takes time, and it should not be lost when closing the dialog. A **preset** saves the complete transformation (mode, fields, actions, and options) under a name, to reuse it in another folder or within a periodic flow —"number the month's invoices", "normalize camera photos"—. Presets need minimal but sufficient management: save, save as new, group by categories, mark favorites so that they appear at the top, export and import to share them between machines, and reset the factory ones. Two details round out the memory of the rename: remembering the **last executed renames** (to repeat or inspect the most recent one) and allowing **creating a reusable action from a preset**, so that the same batch is available in the command palette, in the toolbar, or with a shortcut without opening the dialog.

**Clipboard as a bridge.** The clipboard connects the rename with the outside world: copy the current list of names to edit it in an editor or spreadsheet, and **paste new names** (one per line) to apply them to the batch. Pasting can replace the names or **add the content as a prefix or suffix**, with one line for all or one per file. It is the natural path for the cases that no pattern explains well, and complements the manual per-item editing.

**Implementation notes.** A preset is the same serializable object as the transformation (rules + options), stored with a version in the configuration to be able to migrate it. Presets are saved together with the rest of the program's data; the action created from a preset is registered in the `ActionRegistry` with its name, icon, and optional shortcut.

- Save, group, mark favorites, export/import, and reset rename presets, and remember the last executed batches.
- Create reusable actions from a preset, available in palette, toolbar, and shortcuts.
- Copy the list of names to the clipboard and paste new names per line, as replacement or as prefix/suffix.

### Renaming with metadata and recursion into folders

Many names carry within them the information that the file already stores in its metadata —an MP3 without a useful title in the name but with artist, album, and track inside—. Renaming must be able to **insert metadata into the template**: audio fields (artist, album, title, track), dates and times with free format (`AAAA-MM-DD`), or file attributes, with **automatic sanitization of illegal characters** (e.g., the colons of a time are converted into a safe character) and control of zero padding. Date insertions are especially useful for sorting by name what one wants to see chronologically.

**The folder can also be part of the result.** Sometimes renaming is reorganizing: a template can include the **name of the parent folder** to label the files according to where they live, or create **subfolders from the metadata** ("Album/Track - Title.mp3") moving the files while they are renamed. In addition, the batch must be able to **descend into the selected subfolders** —renaming the content instead of just the folder— with the option of also including the folders themselves and of warning that the preview then covers several levels. A quality subtlety: files with the same base name and a different extension (a photo `01012.JPG` and its RAW `01012.WAV`) must be able to **be renumbered as a single unit**, so that the pair never gets out of sync.

**Implementation notes.** Metadata insertion relies on the services already inventoried (`python3-mutagen` for audio, `python3-pymediainfo`/`mediainfo` for media, `python3-pil`/`exifread` for images), read in the background and with cache per file. The template codes are resolved with the same engine as the view columns (same source of truth for the data). The movement into subfolders and the recursion run through the operations engine, with preview and standard conflict rules.

- Insert metadata (audio, media, image, dates with format and character sanitization) into rename templates, with configurable zero padding.
- Allow the template to generate subfolders or include the name of the parent folder, and descend into subfolders renaming their content (with or without the folders).
- Renumber as a single unit files with the same base name and a different extension, so as not to desynchronize pairs such as photo and RAW.

### The informed replace dialog

When a copy finds a file with the same name at the destination, the program should not ask for a blind decision: it must **present the two files face to face** —the one that already exists at the destination and the one that is to be copied— with enough information to decide with confidence. Name, location, size, modification date, and, when possible, a description of the content (image dimensions, duration, etc.) must be shown for both, with the differences **highlighted in bold** so that they stand out; if possible, each side shows its **thumbnail or icon**, and over the thumbnail the user can hover to see it larger, open it with a double-click, or consult its context menu. The goal is that the question "do I replace this file?" is answered knowing exactly what is gained and what is lost.

**Decisions, not only yes/no.** A good conflict dialog offers a range of answers for the current case and for the rest of the batch: **replace**, **skip**, **keep the most recent** (replaces only if the incoming one is newer), **skip the identical ones** —when size and date coincide, without comparing content, so that truly equal files do not ask again—, **rename the new one** (keep both with an alternative name), and **rename the existing one**. Each decision must be applicable "only to this one" or "to all the following ones", with keyboard shortcuts for the frequent combinations, and the **name of the incoming file must be editable** directly in the dialog: if the user types another name, the button changes from "replace" to "rename and copy". The dialog must be able to abort the complete operation without closing the application.

**Implementation notes.** The dialog is the view of a conflict object independent of the UI (source, destination, type, size, dates, permissions), evaluated by the operations engine before each copy; the "to all" decisions become rules of that operation, and the rules by condition ("newer", "larger", "same size") are offered without the user having to repeat them file by file. The deferred information (descriptions, thumbnails) is loaded in the background and on demand, not when opening the dialog.

- On a name conflict, compare both files with name, location, size, date, description, and thumbnail, highlighting the differences.
- Offer decisions of replace, skip, keep the most recent, skip identical, rename the new one, and rename the existing one, with "only this one"/"all" variants and shortcuts.
- Allow editing the name of the incoming file in the dialog itself and aborting the complete operation.

### Copying and moving with intent: duplicate, copy as, and update

Copying does not always mean "bring the file with its same name to the destination": often one wants **an additional copy in the same folder** (duplicate), a copy **with another name** or transformed by a pattern, a copy **only of the files that are missing or have changed**, or a copy that leaves a **link** at the destination instead of the content. These variants turn the copy operation into a family of actions with the same basis: duplicate within the folder, duplicate with date in the name, copy as or move as (write the new name, or a pattern with `*` that preserves parts of the original), and update —copy only what does not exist at the destination or what is newer or different— as a light form of one-way synchronization as opposed to the full synchronization tool. The user should not have to copy and then rename in two steps what can be expressed in one.

**Implementation notes.** All these variants share the existing copy/move engine and differ only in the computation of the destination name and in the participation condition: duplicating generates the name with no-collision rules, "copy as" reuses the rename pattern evaluator, and "update" applies the date/size comparison before enqueueing. The links at the destination are created with system calls (`os.symlink`) and marked as such in the operation.

- Offer copy/move variants: duplicate in the same folder, duplicate with date, copy/move as with name or pattern, and update only what is missing or changed.
- Reuse the rename pattern evaluator for "copy as" and the date/size comparison for "update".
- Allow creating (symbolic) links at the destination instead of the content when requested.

### Productive drag and drop

Dragging files is the most natural gesture to move them, but it is only productive if its meaning is **predictable and controllable**. The classic rules must be fulfilled and explained: dropping within the same volume moves; dropping on another volume copies; holding `Shift` forces moving; holding `Ctrl` forces copying; holding `Alt` creates a link. And when the user drags with the **right button**, on releasing, a small menu should appear to choose the action —copy, move, or create link— instead of guessing. During the drag, the destination must be anticipated: highlight the folder that will receive the files when passing over it, and allow dropping on other useful surfaces —the sidebar, an open tab, or a breadcrumb— without losing the gesture. Dropping on a compressed folder could even offer "add to archive" as a contextual action.

**Implementation notes.** The default behavior depends on the source and destination devices (same file system or not), computed when starting the drag; the modifiers and the right-button menu adjust the action before enqueueing. The visual anticipation is implemented with the framework's drop indicators and the source/destination logic already defined in the ROADMAP, so that copying by drag and copying by clipboard share the same engine.

- Dragging follows predictable rules: same volume moves, different volume copies, with `Shift`/`Ctrl`/`Alt` to force move/copy/link.
- Dragging with the right button shows an action menu when releasing, and the destination is anticipated visually.
- Allow dropping on the sidebar, tabs, and breadcrumbs, with contextual actions depending on the destination.

### The clipboard with content: text, images, and accumulation

The file manager's clipboard does not have to be limited to file paths. If the system clipboard contains **text or an image**, pasting it into a folder should create a real file with that content (a `.txt` for the text, an image in the preferred format), just as pasting a file copies it. That gesture turns the desktop clipboard into a small file factory and avoids opening an editor to save a fragment. Another flow improvement is the **accumulative clipboard**: being able to keep adding files from several folders to the same copy batch ("copy these three from here, these two from over there") and paste everything together at the destination in a single operation. Both capabilities extend the mental model of "copy and paste" without changing its basic gesture.

**Implementation notes.** Content pasting consults the system clipboard when executing the action and writes the file with sensible default names and no-collision rules; the pasted image format (PNG/JPG) and the name are preferences. The accumulative mode maintains an internal list of paths that grows with each "add to clipboard", and is emptied when pasting or when copying from scratch.

- Pasting text or images from the system clipboard creates a real file in the active folder.
- Support an accumulative clipboard that collects files from several folders and pastes them together at the destination.
- The pasted image format and the default names are configurable.

### Deleting with knowledge: trash, permanent deletion, and secure wipe

Deleting is the most delicate operation, and the file manager must offer a **clear scale of permanence** instead of a single destructive button. The default path is the **trash**: the file can be recovered, and the file manager must make clear when the trash does not apply (network drives, removable media, archive contents) so that the user does not trust an impossible recovery. **Permanent deletion** —which skips the trash— must be an explicit action with confirmation, also accessible with a modifier key, and must bear in mind that the space is marked as free but the data remains physically on the disk until it is reused. For sensitive data there is **secure wipe**: overwrite the file's content a configurable number of passes before deleting it, so that it is practically impossible to recover, assuming that it is much slower because each byte is written several times. Emptying the trash itself must be able to be normal or secure, and the confirmations must be configurable without becoming noise.

**Implementation notes.** The three paths are distinct engine jobs: the trash reuses `trash_service.py`, permanent deletion reuses `delete_selected`, and secure wipe is its own job that overwrites the file (configurable passes, respecting large sizes with progress and cancellation) before deleting it. The decision of which path applies is made in the actions controller, and the interface always shows the scope of what is going to be deleted (count and size) before confirming.

- Distinguish trash (recoverable), permanent deletion (confirmed), and secure wipe (overwriting by passes), indicating when the trash is not possible.
- Secure wipe configures the number of passes, runs with progress/cancellation, and can also be applied when emptying the trash.
- Every confirmation shows the count and size of the scope, without turning each deletion into an unnecessary dialog.

### Compressed files that behave like folders

A compressed file is, in practice, a packaged folder: it contains files and subfolders, only enclosed in a container. The file manager should allow **entering it as if it were a folder** —double-click on a `.zip`, `.7z`, `.tar`, or `.iso` and navigate inside without extracting anything—, copying items from inside to outside with the normal operations (copy/paste, drag and drop) and, in the formats that allow it, **adding files to the container** with the same gesture that copies to a folder. When working inside a compressed file, the concept of source and destination extends naturally: extracting an item is "copying it from inside the archive", and the archive itself can be the destination of a copy. The boundary between "real folder" and "container" is deliberately blurred: the user thinks about the content, not the format.

**Implementation notes.** Entering a compressed file is a case of a read-only virtual collection (or read/write for ZIP) backed by an archive reader (`python3-libarchive-c` is installed; Ark/PeaZip of Phase 10.1 cover creating and extracting). The model exposes the members as virtual entries with their real location within the container, so that copying an item outwards runs the extraction of that member, and copying inwards invokes the addition to the archive. Read-only formats (e.g., many compressed `.tar` without repackaging) are shown the same but without allowing additions.

- Navigate inside the supported compressed files as if they were folders, without extracting beforehand, with copy/paste and drag and drop working from and into their interior.
- Copying an item from inside extracts only that member; copying inwards adds to the container when the format allows it.
- Rely on the installed readers (`libarchive`) for the view and on the configured tool (Ark/PeaZip) for the write operations.

### Libraries: a folder that joins several folders

Sometimes the unit that the user wants to see does not correspond to a single folder on disk: photos are spread over several paths, the documents of a project live in two locations, the music on two drives. A **library** is a virtual folder that shows the unified content of several real folders: it does not store references to individual files —that is a collection— but rather declares "this library is made up of these folders" and shows everything they contain, as if they were together. It differs from a collection in that no individual items are added: entire folders are included or excluded, and the content always reflects the current state of those folders. The normal operations work on the library, and a **real location** column allows distinguishing where each item comes from when several member folders contain files with the same name.

**Implementation notes.** The library is a virtual collection whose definition is an ordered list of member folders, with a default save folder for new files; it is created and edited with a properties dialog (include/remove folders, choose the save folder). Members can also be incorporated from the context menu of a folder ("include in library"). Linux does not have the native "Libraries" desktop concept, but the model fits the project's vision: it is a layer of user organization above the physical tree, like collections and saved searches.

- A library joins several real folders into a single virtual view, showing their current content without duplicating it and with a real location column.
- Member folders are included or excluded entirely, with a default save folder for new files.
- Creation and editing via a properties dialog and via "include in library" from the context menu of a folder.

### Saved searches that live: stored queries

The saved searches of Phase 5.2 store a query to reuse it; **stored queries** go one step further: they behave like persistent folders that **are re-executed when navigating** to them. Instead of a static set of results frozen at the moment of the search, the user enters the query and sees the updated results —the files that meet the criteria right now—, so that a query like "this month's invoices" or "downloads larger than one GB" becomes a view that is always up to date. The automatic re-execution when navigating is especially useful when the results are cheap to compute (indexed paths); if not, the query keeps the last batch of results and is only refreshed with an explicit action (update or `F5`). Creating a stored query must be possible from an existing search, without rewriting the criteria.

**Implementation notes.** A stored query is a virtual collection with a query definition (criteria + folders where to search + optional engine), created from the search dialog ("save as live query") or from the collections root. When navigating, the search engine re-executes the query if it is marked for automatic refresh or if the user asks for it; the results replace or accumulate depending on the configuration. It shares serialization and version with the saved searches.

- A stored query is a persistent collection that is re-executed when navigating to it, showing always-updated results or keeping the last batch until refreshed.
- Create it from an existing search and manage it like a collection (root, properties, default format).
- Reuse the search engine and the serialization of the saved searches.

### System folders that are not a single folder

Some locations that the user sees as "folders" do not correspond to a single physical directory, and the file manager must understand them as such instead of treating them as a normal tree. The **personal desktop folder** is the classic example: it contains real files of the `~/Desktop` folder but also items that the system composes (shortcuts to other locations), and on a system with several users it can be the union of several physical folders. On Linux, places like "This Computer", "Home", or the sections of the sidebar (`Quick Access`, `Bookmarks`, `Recents`, `Network`) are already aggregates: there is no single path that describes them. The file manager must distinguish between what is a real folder of the file system and what is a **virtual system folder**, applying to the latter coherent presentations and actions (icons, folder formats, drag) even though internally their content is composed of several sources or of queries.

**Implementation notes.** Each virtual system location is modeled as a content source with its own namespace (e.g., `this-computer:`, `quick-access:`, `recents:`), independent of the physical file model but with the same view interface. Folder formats and rule-based highlighting apply equally to these views, and navigating from them to a real item resolves its physical path so that the normal operations work.

- Recognize the system locations that are virtual aggregates (desktop, This Computer, Home, sidebar sections) and give them coherent presentation and actions.
- Model each virtual location with its own namespace but the same view interface and operations as the real folders.
- Apply folder formats, highlighting, and drag also over these views; resolve the physical path when operating on an item.

### File types and groups: an editable content taxonomy

Today the file manager decides what a file "is" by looking at its extension with fixed tables scattered throughout the code (`type_map` for the Type column, `extension_map` to classify the search, sets of extensions in preview and in the filters dialog) and with `mimetypes.guess_type` for the MIME. That information is the same everywhere, but it is duplicated and the user cannot adjust it. The alternative is an **editable and central taxonomy of file types**: each extension is assigned to a type with its description (what is shown in the Type column), its icon, and its MIME; and types are grouped into **groups** —"Images", "Music", "Documents", "Video", "Compressed files", "Programs"— that bring together extensions of the same family. All the points that today classify by extension (Type column, search by type, automatic content-based formats, rule-based highlighting, context menus, `Open with`) must read from that single taxonomy, so that changing an assignment or adding an extension to a group is reflected in the whole program at once.

**Special types.** In addition to the types by extension, it is worth modeling general classes that do not depend on a specific extension: "all files", "all folders", "all files and folders", "files without extension", and "unknown types". These classes allow applying default behaviors to the general and refining them in the specific —for example, giving "all files and folders" the standard copy/cut/paste actions, and later adding specific actions to the "Images" group— with an **inheritance from the most general to the most specific**: the file manager resolves what applies to a file by combining the concrete type, its group, and the general classes to which it belongs. Users must be able to create their own groups (e.g., "Project X" with `.md`, `.pdf`, `.drawio`) and reset the predefined ones to their original values.

**Implementation notes.** The taxonomy is a serializable catalog (types with extensions/description/icon/MIME, groups with their extensions and precedence order) stored in the configuration with versioning and resettable; a resolution service answers "given a path, which types and groups match", used by the model, the search, the content-based formats, the highlighting, and the menus. `python3-magic` (already installed) complements the extension with content-based MIME detection for the unknown types. The Type column, the search classification, and the view filters stop maintaining their own tables and consult the catalog.

- Centralize the classification by extension in an editable taxonomy of types and groups (description, icon, MIME, extensions), consumed by the Type column, search, content-based formats, highlighting, and menus.
- Support general classes ("all files", "all folders", "without extension", "unknown") with inheritance from the general to the specific, and resettable user groups of their own.
- Use content-based MIME (`python3-magic`) as a complement for unknown types or misleading extensions.

### Context menus and actions governed by type

A quality context menu does not show the same for a `.jpg`, a folder, or a `.zip`: its actions depend on **what type of item** it is and on the class to which it belongs. The file manager must be able to declare actions by type and by group —"open", "preview", "compress", "convert", "add to collection"— so that when pressing with the right button, the actions of **all the classes that match** the item are collected: those of the concrete type, those of the group to which it belongs (e.g., a common action for all image formats), and the general ones (copy, cut, paste for any file or folder). That same model must cover the **double-click** and its variants with modifier keys —normal double-click opens, `Ctrl`+double-click does something else— and the **drop menu** when dragging with the right button (copy here, move here, create link). Users must be able to add their own entries by type or group: run an external program with the file, run an internal function of the file manager, or group entries into submenus with separators, and reorder them.

**Implementation notes.** The actions by type are defined as data (label, icon, invocation type: external application with `%1`/placeholder, registered internal function, or submenu) and are resolved in the context menu by consulting the taxonomy; the current construction of the menu in `main_window.py`/`menus.py` goes from deciding by `kind` with fixed rules to consulting the type resolution. The entries defined by the user are saved in the type catalog and are integrated with the `ActionRegistry` of Phase 1.2 so that shortcuts, palette, and menus share the same definition.

- Build the context menu as the union of the actions of the concrete type, its group, and the general classes, with support for submenus, separators, and reordering.
- Allow defining actions per type/group that execute external applications (with the file as an argument), internal functions, or submenus.
- Cover double-click with modifiers and the drop menu (drag with the right button) with the same type-resolution mechanism.

### On-the-fly information by type: tooltips and rich labels

The tooltip that appears when hovering over a file is an opportunity to show **exactly the information that this type of file can offer**, without noise. A template per type defines the lines of the tooltip with field codes: the description and the size for almost everything, the dimensions and the camera for images, the duration for audio and video, the number of items and the total size for folders. Lines that use fields not available in the specific file are omitted (a `.bmp` has no EXIF metadata, so the camera line disappears), and if the template wants to show a **thumbnail** it can include it in the tooltip. The same template mechanism serves for the **informative labels** that accompany the icons or future mosaic modes: define which fields accompany the name depending on the type. Thus the information is contextual, it is composed by inheritance (group → concrete type), and it does not force the user to remember which columns to activate.

**Implementation notes.** The templates reuse the engine of field codes defined for renaming with metadata (same source of truth), with support for hideable sections when a field is missing and for simple computed values. The tooltip is generated in the background so as not to slow down the cursor, with cache per file; the thumbnails in the tooltip reuse the existing thumbnail pipeline. The resolution order of the template is the same as that of types: the most specific wins, the general one gives the default value.

- Tooltip templates per type/group with field codes, lines that are omitted when the field does not apply, and optional thumbnail.
- Same template mechanism for the informative labels next to the icons (or future mosaics), by inheritance from group to type.
- Background generation with cache, reusing the metadata field-code engine and the thumbnail pipeline.

### Saved filters as a central repository

Filters are used in many features —copy with filter, delete with filter, advanced search, selection, synchronization, duplicates— and in all of them they can be edited on the fly. What is missing is a **central repository of named filters**: a page where reusable filters can be saved, duplicated, renamed, described and deleted, and which then appear in a dropdown in every tool that uses them. The repository must allow **sharing a filter** by copying it to the clipboard as text (and pasting it on another machine) and **editing it as text** in addition to the visual editor, because the textual form is what travels well between installations. A saved named filter must be able to be invoked from any point that accepts filters without reopening or rebuilding it.

**Implementation notes.** The repository is a serializable store of filters (versioned clause tree) independent of the criteria engine; the tools that accept filters offer "new, load saved, save as…" with the same clause dialog. Sharing converts the filter to its canonical textual representation, and pasting it validates and imports it.

- Central repository of named filters: save, duplicate, rename, describe, delete and select from any tool that accepts filters.
- Share filters as text (clipboard/import) and edit them in text mode in addition to the visual editor.
- Versioned serialization and validation on import.

### Type to find: the field that pops up while you type

The fastest way to reach a file whose name is known is simply **to start typing**: without opening dialogs, without prior shortcuts, the list reacts to the letters. A pop-up "type-to-find" field (find-as-you-type) makes that implicit search visible: when a letter is pressed it appears at the edge of the view showing what has been typed, the closest match is selected and the rest that match are **highlighted in the list and in the scrollbar**, so the eye can see that there are more candidates. `F3`/`Shift+F3` jump between matches, and the text can be corrected without clearing everything. That same field can be extended with **modes** invoked by an initial key: navigate to a typed path (with autocomplete), select by pattern, filter the list instantly or search among the open tabs. A single gesture —typing— then covers jumping, going, selecting, filtering and switching tabs.

**Implementation notes.** The field is implemented as a lightweight overlay on the view that intercepts typing when the view has focus, keeps the searched text as state and communicates to the view the active match, the highlighting and the scrollbar markers. The modes are activated by a configurable prefix and share the same field; jumping reuses the normal selection and filtering shares the quick filter state so that `Esc` clears it.

- Typing in the view opens a visible field that selects the first match, highlights all the others and marks them in the scrollbar, with `F3`/`Shift+F3` to step through them.
- Extend the field with initial-key modes: go to a path with autocomplete, select by pattern, filter the list and search among tabs.
- Implement it as a lightweight overlay with its own state, integrated with the selection and with the quick filter.

### View modes that show more than the name

Changing the view mode is changing the question: in **icons** the question is "what is here?", in **details** "when, how much, of what type?" and in **thumbnails** "what does it look like?". Linux File Manager already offers four modes; the leap in quality lies in the **hybrid modes and in zoom as a continuous gesture**. "Details with thumbnails" adds an image column next to the name to see the content while reading the metadata; a **tiles** mode combines a large icon with two or three informative fields under the name (type, size, dimensions for images), showing more context than plain icons without the density of the table; and a **pure thumbnails** mode maximizes the visual area for images and video. In table modes, `Ctrl` + mouse wheel should adjust the font size; in thumbnail modes, the cell size —a continuous control that turns zoom into a natural part of navigation, not of configuration.

**Implementation notes.** The new modes are combinations of the existing model: "details with thumbnails" is the details view with an adjustable-width thumbnail column; "tiles" and "thumbnails" are variants of the `QListView` with painting delegates that compose image and fields. Wheel zoom adjusts a continuous per-view scale factor. The chosen mode and its zoom are saved per folder (Phase 7.3), and the tile content is defined per file type (1.2.2/7.1).

- Add hybrid modes: details with a thumbnail column and tiles with informative fields per type; pure thumbnails for images/video.
- Continuous zoom support with `Ctrl`+wheel (font in tables, cell size in thumbnails/tiles), saved per folder.
- Implement tiles/thumbnails with painting delegates that compose image and fields without duplicating the model.

### Window styles and dedicated panels

The file manager does not have to have a single layout for all tasks: the same folder is worked on differently depending on whether you are organizing photos, editing metadata or comparing two locations. A **style** is a complete window configuration —which panels are open (sidebar, tree, preview, metadata), in which arrangement (preview on the right or at the bottom), which view mode the main area uses— applicable with one action to change the "way of working" without losing the current folder. Useful predefined styles: one for **browsing** (no extra panels, dense view), a **filmstrip** one for photos (thumbnails at the top or narrow, with the viewer open next to them), a **metadata** one (details view with the metadata panel of the selected file) and a **dual-panel** one. The user must be able to save the current layout as their own style and switch with a menu or shortcuts.

**Implementation notes.** A style is a serializable description of the window state (visibility and position of panels, view mode, zoom), applied by the window composer without opening new windows; the predefined styles ship as editable default values. Persistence distinguishes between the active style and the per-folder settings (7.3): the style decides the layout, the folder decides its format.

- Define window styles as panel, layout and view configurations applicable without losing the current folder, with presets (browse, filmstrip, metadata, dual panel) and saveable custom styles.
- Apply them from a menu or shortcuts and separate the active style from the per-folder formats.

### Metadata panel and built-in viewer

File information does not have to live only in a properties dialog: an integrated **metadata panel** beside the list shows, when a file is selected, its relevant fields —dimensions and camera for a photo, duration and tracks for music, pages for a PDF— and allows **editing and saving them** without opening another window, with buttons to move to the next or previous file while keeping the changes. Beside it, the **built-in viewer** turns the selection into a live preview: as the list is browsed with the arrow keys, each file is shown in the panel, with zoom controls, fit to window, rotate view (without modifying the file) and a slideshow of the folder. Both panels share the idea that "what is selected is seen and can be consulted instantly", and they rely on the metadata services already inventoried (`python3-mutagen`, `pymediainfo`, `python3-pil`/EXIF) and on the existing image pipeline.

**Implementation notes.** The metadata panel reads the fields with the same services as the columns and the tooltip (same source of truth) and saves the editable ones with those same services, showing per-field applied/pending status. The built-in viewer is an extension of the preview panel with view controls; the slideshow uses the folder order and the timer, and the rotations/zoom are presentation transformations that do not touch the file.

- Integrated metadata panel that shows and allows editing the relevant fields of the selected file, with next/previous navigation and applied status.
- Built-in viewer that shows the selection while browsing the list, with zoom, fit, rotate view and slideshow without modifying the file.
- Share the metadata services with columns and tooltips, and the image pipeline with thumbnails.

### A visual customization mode: "if you don't like it, change it"

The file manager must be able to adapt to each user's flow without touching code. The basis is a **customization mode** entered with an action (e.g. "Customize bars…") that turns the interface into editable: the bars show their buttons as manipulable objects and the customization dialog offers tabs to manage **bars**, **interface context menus**, **shortcuts** and **commands**. While the mode is active, editing is direct: double-clicking a button opens its editor; dragging a button moves it from its place; dragging it with `Ctrl` duplicates it; dragging it out removes it; a small sideways drag inserts a separator. Leaving the mode with OK applies the changes and leaving with Cancel discards them —and an **undo of all the mode's changes** is advisable so that experimentation carries no risk. In that mode, the buttons that are actually fields (path, filter, search) appear as resizable frames, so the user sees how much of the bar each element occupies and can adjust it.

**Implementation notes.** The customization mode relies on the bars already being built from declarative definitions (Phase 1.2/1.2.2): editing a button means changing its definition and rebuilding the surface, with no logic scattered in the main window. The customization dialog shows the list of available commands from the `ActionRegistry` to drag onto the bars, and the changes are saved in the user configuration with an option to restore the default values.

- Enter a customization mode that makes the bars editable: move, duplicate, remove and separate buttons with the mouse, and edit each button with a double-click.
- Accept/Cancel of the mode, with undo of all changes and reset to default values.
- Show the fields (path, filter, search) as resizable frames inside the bar in customization mode.

### Buttons with one function or several: internal commands and external programs

A bar button does not have to run a single thing: it can have **several functions associated with different clicks** —the left button does one action, the right button another and the middle button a third—, so that a single element condenses three related operations. In addition, a button's function can be an **internal file manager command** (with its arguments) or an **external program**, and in the latter case the button must be able to pass it context information: the selected files, the current folder, the path of the item clicked on. This turns the bar into a small launcher ("open the selected files in this application") and allows each user to build their own buttons from the existing commands or from their favorite programs. A button can also be a **dropdown menu** (a vertical list of other buttons) or a "menu button" that executes its first function with a click and unfolds the rest with the arrow, nesting as many levels as desired.

**Implementation notes.** The button model is a serializable definition: one or more functions (each = internal command with arguments or external application with a files/folders template), icon, label, tooltip and optional shortcut. Internal commands are resolved against the `ActionRegistry`; external applications use the same placeholder expansion as the per-file-type actions (1.2.2). The dropdown menu is a list of button definitions, and the "menu button" combines a main function + list.

- Buttons with several functions per click (left/right/middle) and buttons that execute internal commands or external programs with the context's files/folders.
- Dropdown-menu-style buttons and "menu button" (main function + dropdown list), nestable.
- Model the button as a serializable definition resolved against the action registry and the external placeholder expansion.

### Visible shortcuts, editable and without collisions

Keyboard shortcuts are the user's muscle memory, and they must be able to be **seen, learned and adjusted** without risk. A shortcuts dialog lists all the combinations by category —list navigation, path bar, tree, viewer— with filters to search by key or by command, and allows **changing a combination** with a control that captures the keystroke, **adding new shortcuts** (even key-only, without an associated button) and **temporarily disabling** one without deleting it. The key lies in the **conflicts**: if two actions share the same combination, the dialog must show them grouped under "conflicts" and warn when assigning, so that the user decides which one wins in each context instead of discovering the collision when a key "doesn't work". The shortcuts must be able to be **exported and imported** (or shared as text), and every action with a shortcut shows its combination in menus and tooltips so that they are learned naturally.

**Implementation notes.** The shortcuts live as data in the action registry (1.2), not scattered in the window; the shortcuts dialog edits that registry and re-applies the combinations hot. Conflict detection is a query against the registry with scope (context) and precedence, and export serializes action→combination with version.

- Shortcuts dialog with categories, search by key/command, keystroke capture, key-only shortcuts and temporary disabling without deleting.
- Conflict detection and presentation per context before assigning, and export/import of shortcuts as data.
- Show the combination in menus and tooltips, and apply changes hot without restarting.

### Links that point without duplicating

Not every access to a file needs a copy: sometimes what is wanted is **another entry that points to the same content**. The file manager must offer the link types that the file system supports natively, with their semantics explained in the interface. On Linux, the **symbolic link** can point to a file or a folder, even on another volume, and can be stored as an **absolute** or **relative** path —the relative one keeps the link alive if the common set of folders is moved—; the **hard link** points only to files, within the same volume, and is not distinguishable from the original (the file only disappears when the last link is deleted). Creating a link must be a first-class operation, as natural as copying: from the drop menu when dragging with the right button ("create link here"), from "copy as link" or from the copy variants to the destination. The conceptual difference is key and must be shown without ambiguity: copying duplicates the content, moving relocates it and linking creates a reference; deleting a link does not delete the destination (except for a file's last hard link), and it is worth warning when the user could confuse it.

**Implementation notes.** Link creation relies on the system calls (`os.symlink`, `os.link`) and is integrated as one more variant of the copy/move engine (2.1): "link at the destination" computes the relative path when requested and creates the link without copying content. Links are shown as such in the list (icon and destination description) and deleting a link is handled with the same confirmation scale as the rest.

- Offer creating symbolic links (absolute or relative) and hard links to files/folders as copy variants, accessible from the drop menu and from "copy as".
- Distinguish clearly between copying (duplicates content), moving (relocates) and linking (creates a reference), and warn when deleting a link could be confused with deleting its destination.
- Use `os.symlink`/`os.link`, compute relative paths when requested and show the links with icon and destination in the list.

### The standalone viewer and image marking

To select photographs —which ones stay, which ones are uploaded, which ones are printed— the built-in viewer inside the window is not enough: a **standalone viewer** is advisable, one that opens the image in its own window, automatically lists the other images of the folder and allows browsing them with the wheel or space, with zoom, fit, view rotation and slideshow, respecting EXIF orientation when displaying. Its most valuable function is **marking**: pressing `M` (or `Insert`) marks the current image —with a star as indicator— and adds it to a collection; a side panel shows the thumbnails of the marked ones and allows jumping between them, and the collection persists between sessions to copy, delete or upload later what was chosen. Shortcuts such as `Ctrl+←/→` jump between marked images, `Shift+M` swaps the mark with the previous one (useful with several photos of the same scene) and `Ctrl+Space` returns to the previous position in the list. Thus reviewing hundreds of photos becomes a tour with one-key decisions.

**Implementation notes.** The standalone viewer is the separate window of the existing image pipeline, with its own shortcut registry (reusing 1.2.3); marking writes into a virtual collection (5.3) with a configurable name (e.g. the folder name or the date). The marked panel is a view of that collection with thumbnails from the existing pipeline.

- Standalone image viewer that lists the folder, respects EXIF orientation and offers zoom/fit/view rotation/slideshow.
- Marking with `M`/`Insert` that accumulates the chosen images in a persistent collection with a thumbnails panel, jumping between marked ones and mark swapping.
- Marking shares the collection with the rest of the file manager to copy, delete or upload later what was selected.

### Exporting the content: the folder listing

Sometimes what is needed from a folder is not the files but **the information about them**: a printable inventory, a list for a spreadsheet or a textual backup of the contents. The file manager must be able to generate a **folder listing** with the same columns as the view —name, size, type, date, attributes— and send it to a printer, to a file or to the clipboard, in plain text, tab-separated or CSV (the latter ready to import into a spreadsheet). The listing can include the contents of the subfolders (flattened or as an indented tree, like the flat view), apply a filter to limit what goes in, compute subfolder sizes when requested and carry a header/footer with the folder and the date. It is the complementary operation to printing the file: there the content of the file is printed, here what the folder contains is printed.

**Implementation notes.** The listing generator reuses the file model and the visible columns to produce rows; the destinations (printer via the existing `QPrinter`, file or clipboard) and formats (text/CSV/TSV) are output options. The filter and the subfolder mode reuse the already defined components (saved filters and flat view). The subfolder size column uses the folder size calculation (Phase 9.2) when it is active.

- Generate a folder listing with the view's columns, exportable to printer, file or clipboard in text, TSV or CSV.
- Support subfolder inclusion (flattened or as a tree), optional filter, subfolder sizes and header/footer.
- Reuse the file model, the saved filters and the folder size calculation to produce the rows.

### Type summary: reading the folder at a glance

A folder full of files raises the question "what is here, as a whole?" in addition to "what is each file?". The **type summary** answers the first one with a compact representation of the content mix: how many files and how much space each group of types (or each extension) occupies, displayable as a breakdown in the status bar information and, with a click, as an interactive dialog that allows toggling between selected or all files, between counting files or summing sizes, and between grouping by extension or by type group. It is a quick orientation tool —"this folder is mostly 2 GB of images"— and an entry point to filter or act on a specific type.

**Implementation notes.** The summary queries the type taxonomy (1.2.2) to classify each item and accumulates counts and sizes per group/extension without blocking the view (deferred background computation for large folders). The interactive dialog reuses those totals and offers filtering or selection actions for the chosen type.

- Show a type breakdown (count and size per group or extension) as a folder summary, in the status bar information and in an interactive dialog.
- Toggle between selected or all, count or size, and group by extension or by type group.
- Classify with the type taxonomy, compute in the background for large folders and allow filtering or selecting from the summary.

### Paired folders: the other side of the work

There are flows that always move between two places: a project in "draft" and its "published" version, the source files and their production copy, the folder of raw photos and the one of the selected ones. The file manager can recognize that pattern with **paired folders**: two paths (or two patterns that generate a path from the other) that are treated as sides of the same task. If the panel is showing one side of the pair, an action —or navigation itself in dual view— opens the other side in the opposite panel, without looking for it in the tree. The pairs can be fixed absolute paths or **regular** ones: for example, every path containing `/borrador/` has its pair in the same path with `/publicado/`, covering all the subfolders at once. The pair thus becomes the natural destination for copying, the default target for synchronizing and the companion of the linked tabs described before.

**Implementation notes.** A pair is a serializable rule: two absolute paths or a "match/replace" expression evaluated in order; the pairs service returns "given a path, which one is its partner", with rules about what to do if the partner does not exist. Dual navigation and synchronization query that service to propose the other side as destination.

- Define folder pairs by absolute paths or by regular matching (replacement over the path), applicable to subfolders, with pair management and sharing.
- Offer "open the other side" when navigating, use the pair as the default copy/sync destination and link the tabs of both sides.
- Evaluate the rules in order and decide the behavior when the partner does not exist.

### Preserving what matters when copying

Copying is not only moving bytes: each file drags along information that should be **preserved or discarded depending on the operation**. On Linux, copying must decide whether the **permissions**, the modification and access **times**, the **owner** and the **extended attributes** are preserved —including the file manager's own labels if they are stored in xattrs— and it must know what happens when the destination does not support them (a USB with another file system, a network drive). The default policy must preserve as much as makes sense (permissions and times almost always; owner only when possible; extended attributes when the destination allows it), but the user must be able to adjust it: for example, decide whether a copy to an external medium carries along the local attributes that mean nothing there. Another subtlety is that of **sparse files**: a giant file full of zeros should not occupy that space when copied if the file system can recreate the empty regions.

**Implementation notes.** The preservation policy is an option of the copy engine applied per destination: use `shutil.copy2` (which already preserves permissions and times) as the base, add xattrs with `python3-xattr` when the destination allows it, and apply the chosen policy per operation (copy, move, duplicate, variants of 2.1). Sparse detection uses the system API and specialized copying only when requested.

- Copying preserves permissions and times by default, with a configurable policy for owner and extended attributes depending on the destination.
- Preserve or discard the file manager's attributes stored in xattrs according to the destination and the operation.
- Handle sparse files so they do not occupy unnecessary space when copied, when the destination supports it.

### The configurable status bar: what is seen and what is decided

The status bar does not have to be a fixed set of labels decided by the program: its content can be a **configurable definition** where the user chooses, by sections, which information appears —file and folder counts (totals and selected), size of the selection, items hidden by filters, content type, free space with a usage graph, current format, format lock—. Each section can be aligned, take more or less space and be hidden under simple conditions; the result is seen in a live preview while editing. It is the same spirit as the tooltips and the per-type templates: the contextual information is composed with reusable field codes, and what is not of interest is removed. Such a bar can even be different in single-panel mode and in dual view (or per panel), and the folder format icon in it offers quick access to change, reset or lock the format.

**Implementation notes.** The status bar is generated from a definition (lines = sections, with field codes and alignment/hiding options) evaluated by the same metadata field-code engine; the live preview reuses the current definition. The clickable items (format, lock, hidden) keep their actions even when the definition changes.

- User-defined status bar by sections (field codes, alignment, conditional hiding) with live preview while editing.
- Separate definitions for single mode and dual view (or per panel) when applicable.
- Integrated interactive items: format icon with change/reset/lock and access to show everything.

### Background, color and look per location

The presentation of a folder does not end with columns and order: the **visual look of the file area** —background color, background image, opacity— can remind the user where they are and what kind of content to expect. A photos folder may have a dark background that favors the thumbnails; a documents folder, a neutral one; a results collection, a distinctive tone. As with the folder format, the rule is defined by exact path or by pattern, by folder type (local, network, removable, results collection) or by content group, and it is applied in order of specificity; the image supports fit modes (tile, stretch, fit, fill keeping the aspect ratio), opacity and fill color, and it can be inherited by the subfolders unless there is an own rule.

**Implementation notes.** The per-location background is another layer of the presentation resolved by the same hierarchical service as the folder format (7.3): path/pattern, folder type, content group, default value. The color is applied on the view widget and the image is painted behind the list without blocking interaction, reusing the image pipeline.

- Assign background color and image by path, pattern, folder type or content group, with fit modes, opacity and fill color.
- Resolve the background with the same specificity hierarchy as the folder format and allow inheritance to subfolders.
- Paint the background behind the list without blocking the view and reusing the image pipeline.

### Intentional double-click by type

Double-clicking a file should not always have the same meaning: it depends on **what type of file it is and which application will open it**. The file manager must allow deciding per type and group what the double-click does —open with the default application, open in the file manager's built-in viewer (for images, for example), play, or show properties— and for the **unknown types** it must be able to inspect the content: if a file without an extension or with an unregistered extension looks like plain text, offer it to the file manager's text viewer instead of sending it to an application that would not recognize it. Thus the double-click becomes "smart" without surprises: it respects what the user configured for each family and resolves with common sense the cases that have no associated application.

**Implementation notes.** The double-click behavior is resolved with the type taxonomy (1.2.2) and with modifiers (1.2.2), using as destination commands from the action registry or external applications; the "looks like text" detection reuses the text preview logic (`PreviewWorker`) without opening the whole file. The per-family preference is stored in the per-type/group double-click configuration.

- Configure what the double-click does per type and group (default application, built-in viewer, play, properties), with priority to the user configuration.
- For unknown or extension-less types, detect whether the content looks like text and open it in the file manager's text viewer.
- Resolve with the type taxonomy and show in the context menu which action the double-click will execute.

### Expandable folders in the list itself: the hierarchy without changing folder

Between the flat view —which flattens the whole tree at once— and the side tree —which shows the hierarchy in a separate column— there is a middle ground that many users miss: **expanding a subfolder right where the list is**, without navigating to it. Each folder shows a small expansion control to the left of the name; when pressed, its children appear interleaved under it, and the user can keep going down level by level only where it is of interest. The result is a folder that behaves like a partial tree: the context of the current folder remains visible while a specific branch is inspected, and files can be copied or moved to and from those expanded subfolders without losing sight of the starting point. The expansion is optional and reversible: a shortcut (`Alt`+`↓`/`Alt`+`↑`) controls it from the keyboard, and the user can decide that the expansion controls remain hidden until at least one subfolder is open, so that the normal list is not polluted with glyphs.

**Expansion in the service of drag and drop.** This mode boosts drag and drop: with a subfolder expanded, dropping a file onto a child folder is as explicit a destination as the opposite panel, and when dragging over a still-collapsed folder the file manager can **open it automatically** while the drag is held above it —and close it again on drop or cancel— to allow leaving the file two levels deeper without releasing the button. The visual anticipation of the destination and the right-button drop menu already defined in "Productive drag and drop" are extended here to the intermediate levels.

**Copying files that live inside branches.** When files that come from expanded subfolders are copied, the destination must interpret the structure: recreate the relative source path at the destination or dump all the files into the same folder. It is the same decision that the flat view already poses when copying nested files, so that both surfaces share the rule and dialog instead of duplicating it.

**Implementation notes.** The basis is already in the main view (`QTreeView` + `QFileSystemModel` with `setRootIndex`), so expanding branches is a matter of presentation of the same hierarchical model and not of a second data model; it must be avoided that expansion is confused with navigation (expanding does not change the active folder or the history) and it must be defined how the quick filter (a folder hidden by the filter drags its children along or not, same rule as the flat view) and the copy/move operations that already resolve structure (Phase 2) coexist. Drag with automatic opening reuses the framework's destination indicators and the existing source/destination logic.

- Expand subfolders in the list itself, level by level, with an expansion control and the `Alt`+`↓`/`Alt`+`↑` shortcut, without changing the active folder or the history.
- Automatically open the folder being dragged over (and close it when finished) to drop at deep levels; extend the anticipation of the destination to the expanded branches.
- Copy files coming from expanded branches with the same "recreate structure or same folder" choice as the flat view.
- Be able to hide the expansion controls until at least one subfolder is open.

### Being the manager the system opens for folders

In some reference desktop file managers it is possible to take the place of the native explorer: when any system action asks to open a folder, the file manager opens in its place. On Linux there is no single process that "is" the file manager, but there is a practical equivalent: the **desktop consults the registered file manager to open folders**, and Linux File Manager can offer itself as that option. Double-clicking a folder on the desktop, "open containing folder" from another application or `xdg-open` on a directory should be able to resolve to the file manager chosen by the user. For this, the application registers itself as a handler of the `inode/directory` type (and of the `file://` scheme) in the system MIME database and declares itself as the preferred file manager, in an **optional, reversible and explained** way, because changing the desktop's file manager affects the whole environment and must be undoable with a click or from the desktop's own preferences dialog.

**Honest limits of the integration.** As happens in the reference file manager, the substitution is not total: the file manager does not replace the desktop itself or the file pickers (open/save) of the other applications, which on Linux are handled by the desktop portals. The integration is concentrated on folders: receiving paths and `file://` URLs as an argument, opening them in the correct instance and responding quickly, because the system expects that "opening a folder" is immediate. Whoever does not want to substitute anything simply leaves the option off and Linux File Manager remains a file manager that opens at will.

**Implementation notes.** The registration uses the XDG utilities already present (`xdg-mime`, `mimeapps.list` files and the Phase 10 integration), with a setting in Preferences that writes and restores the association and shows which file manager was there before. Receiving folders requires handling the command-line arguments and `file://` URLs in a single entry point that decides between opening a new window or **activating the already-open instance** and navigating in it, together with the session startup described in the next subsection.

- Offer in Preferences "use Linux File Manager to open folders" (`inode/directory`/`file://` registration), reversible and with notice of the previous file manager.
- Accept paths and `file://` URLs on the command line and activate the open instance instead of duplicating it; open folders quickly.
- Document that the file manager does not replace other applications' file pickers or the desktop.

### Session startup, immediate response and clean shutdown

A file manager can live in two ways: as an application that opens when needed, or as a resident service that starts with the session and is always ready. For a user who has made Linux File Manager their system file manager, the second option has real advantages: opening a folder from the desktop or from another application is instantaneous because the process is already in memory, and the global shortcuts or custom launchers can only respond if the application is alive. For that reason the file manager must offer an **optional session startup** (through the desktop's standard autostart mechanism) for whoever wants that behavior, without imposing it on those who prefer the traditional model of opening and closing.

**Living and dying with cleanliness.** Both in resident mode and in the traditional one, shutdown must be orderly: when the last window is closed, the file manager decides whether to terminate completely —and in that case it **does not abandon half-finished operations**: it waits for or asks about the ones still active in the queue— or whether to remain in the tray to keep responding to folder openings. Force-terminating the process is not a way to exit: there is a risk of losing configuration or leaving operations inconsistent, so forced shutdown is detected and the next execution recovers the state (windows, tabs and pending operations) as the context restoration already provides for.

**Implementation notes.** Autostart is implemented with the standard `.desktop` file in the user's autostart directory, created and removed from Preferences without touching anything else in the system. The "single instance" with activation —a second invocation reuses the live process and passes the path to it— is the same mechanism that the integration as the system file manager needs and must exist before the resident mode. Shutdown is coordinated with the operation queue (Phase 2): knowing what is in progress and deciding between waiting, warning or letting it finish in the background, always saving the state before exiting.

- Optionally start with the session from Preferences (desktop autostart file), without affecting those who do not want it.
- Single instance with activation: a second invocation with a path navigates in the already-open instance instead of launching another one.
- Shutdown coordinated with the operation queue: do not close with unfinished work without warning; save state and recover windows/tabs on the next execution.
- Detect forced terminations and protect the configuration against abrupt shutdowns.

### Checkbox mode: a selection that is not lost with the next click

Classic selection has a known fragility: a single click on an empty area —or a double-click to open a file— is enough to undo it. **Checkbox mode** offers an independent marking layer: next to each item a checkbox appears, and the operations that normally act on the selection (copy, move, delete) then act on the **checked** items, which survive any later click. Thus a long sweep can be done —previewing one by one the photos of a folder and checking the ones of interest with the space bar— and at the end a single operation can be run on the whole set, without the risk of losing the accumulated work due to an accidental click. Space also checks and unchecks, and the checkboxes coexist with the selection: dragging keeps using the selection, while copy/delete uses the checks.

**Bridges between both states.** Selection and checkboxes should not be isolated worlds: the user must be able to **convert the current selection into checks** (when they decide halfway that the checkboxes are the best method) and **convert the checks into selection** (when they want to drag what is checked). Inverting the checks is the natural way of "deleting everything except what I reviewed". Linux File Manager already has the basis of this mode —the `selection_checkboxes` setting and the set of checked paths in the model (`checked_paths`)—, so the task is to complete its operational semantics, not to create it from scratch.

**Implementation notes.** The model already stores the checked paths and exposes them (`checked_paths()`); what remains is to decide that the copy/move/delete operations consult the checks when the mode is active and to keep both views of the state (selection and checks) coherent when filtering or hiding items. The selection↔checks conversion is a pair of trivial commands over that same set, and checking with `Space` must work with the same logic as inline rename so as not to conflict with editing.

- Checkbox mode per folder (part of the folder format): operations act on what is checked, not on what is selected; `Space` checks/unchecks the selected items.
- Double-click, selection and drag do not destroy the checks; the checkboxes survive clicks on empty areas.
- Convert selection into checks and checks into selection; invert checks as a method for "deleting what was not reviewed".
- Complete it on the existing basis (`selection_checkboxes`/`checked_paths`), not create a parallel mechanism.

### Opening with a single click: the mouse as a pointer, not a presser

For a part of the users, double-click is an uncomfortable or simply unnecessary gesture: they prefer the files to behave like links on a web page. **Single-click mode** turns that preference into behavior: hovering over an item and stopping for half a second **selects** it without pressing anything, and a left click **opens** it. Multiple selection keeps its grammar —`Ctrl` adds items when hovering over them, `Shift` does range selection— and the only real change is that the physical act of "pressing to select" disappears. It is not a global or default option: each user activates it in their mouse configuration, and it coexists with the rest of the gestures (double-click, right-click, drag) without altering them.

**Why it matters for accessibility and speed.** Reducing the number of clicks is not only an aesthetic preference: for whoever works with the keyboard or with motor difficulties, or simply in long sorting sessions, every avoided click is avoided fatigue. The option must be where the rest of the mouse behaviors are configured and be documented without ambiguity (a click opens; hovering and waiting selects), because changing the semantics of the main gesture without warning would be a surprise.

**Implementation notes.** It is an interaction preference resolved in the view's click handler: with the mode active, `mousePressEvent` with the left button opens the item under the cursor and prolonged hover (a ~500 ms timer with `Ctrl`/`Shift` for adding/range) updates the selection. The rest of the mouse events do not change. It must be guaranteed that draggable items are not opened when starting a drag and that the hover delay is configurable.

- "Open with a single click" option in the mouse configuration: left click opens, hovering and waiting selects (with `Ctrl`/`Shift` for multiple/range).
- The mode does not alter right-click, drag or the other gestures; configurable hover delay and no conflict with drag.

### The list can also be copied: cells and columns as data

A details view does not only show files: it shows **data** —names, dates, sizes, types, attributes— organized in rows and columns. Sometimes what the user needs is not the file but that datum: a list of names to paste into an email, the modification dates for a spreadsheet, the sizes for a report. The file manager must allow **selecting cells or whole columns** —with `Ctrl`+right-click on a cell or on the column header, or by dragging a lasso over a block— and **copying their content to the clipboard** in the useful formats: a column of names as a list of lines, or the whole block as a table with separators to paste it into a spreadsheet. Cell selection is independent of file selection: a block of cells can be highlighted while the row selection remains what governs the file operations.

**A bridge towards export.** This capability is the lightweight version of the exportable folder listing: without opening any dialog, the user copies exactly the fragment of data that is in view. It must share with the listing the same notion of columns and output formats (text, tabulated, CSV) so that the behavior is predictable, and the visual highlighting of the chosen cells must be clear and configurable.

**Implementation notes.** On the existing details view, cell selection uses a mode of the `QTableView`/`QTreeView` with its own highlighting independent of the row selection; copying serializes the highlighted block according to the chosen separator (newline per row, tab or semicolon per column) reusing the clipboard with content. The option must respect the hidden columns (not copy what is not seen) and also work in modes with a visible column header.

- Select cells, columns or blocks with `Ctrl`+right-click (or lasso) in the details view, with own highlighting independent of the file selection.
- Copy the highlighted content to the clipboard as lines, or as a table with separators (text/TSV/CSV), respecting the visible columns.
- Share columns and output formats with the exportable folder listing.

### An order that the user decides: persistent manual ordering

Sorting by name, date or size covers most cases, but not all: sometimes the right order is **the one the user has in mind** —a working sequence, a priority, a presentation— and no automatic criterion can express it. **Manual ordering** allows rearranging the items freely, by dragging them or with the keyboard (`Shift`+`Alt`+arrows), and **saving that order** as part of the folder format so that it is kept between visits. When activated, the list abandons the automatic order and comes to reflect exactly the position of each item; a command allows returning to the automatic order at any time and, if automatic saving is not wanted, saving the order explicitly only when convenient.

**Limits that must be explained.** Manual ordering cannot persist everywhere: it makes no sense in folders where the order cannot be written (compressed archives, read-only remote locations, or where the permissions prevent it) nor in views that by definition mix origins, such as the flat view or the grouped lists. The interface must distinguish between "the order cannot be saved" (allowed temporarily or disabled, depending on preference) and "the order is saved", showing with an indicator when the current order is not yet saved, so that the user does not believe their work will be kept when it is not possible.

**Implementation notes.** Manual order is a state of the folder format: an ordered list of paths (or of stable identifiers) that the view respects above any automatic criterion and that is serialized with the format persistence (Phase 7.3). Dragging to reorder shares the existing drag-and-drop infrastructure but with internal semantics (moving within the list, not copying/moving files), and the keyboard with `Shift`+`Alt`+arrows covers those who do not use the mouse. The limits (flat view, grouping, destinations without write permission) are resolved by disabling or degrading the mode with a notice.

- Enable manual ordering per folder (part of the format): reorder by dragging or with `Shift`+`Alt`+arrows and keep the order when returning.
- Automatic saving of the order when the destination allows it; clear indicator when the order changed and was not yet saved or cannot be saved.
- Restore the automatic order at any time; disable or degrade the mode in the flat view, groupings and read-only locations.

### Frozen columns: the name always in view

A details table with many columns forces horizontal scrolling, and in doing so the most important datum —the **file name**— usually leaves the screen. **Frozen columns** fix a group of columns on the left (normally the name and perhaps the type) that remain visible while the rest slides beneath them when scrolling horizontally. Freezing is a simple gesture: up to the point of the column you want to fix, with `Ctrl`+`Alt`+click on its header or from the header menu, and repeating the gesture unfreezes. As it is part of the folder format, the decision of which columns stay fixed is saved per location like the rest of the presentation.

**When it is worth it.** Not every table needs frozen columns: the feature shines when there are wide columns or many columns (locations, dates, permissions, metadata) and the user needs to compare the name against the datum at the far right. The option must be within reach of the header menu, discoverable next to the rest of the column commands, and persist with the folder format.

**Implementation notes.** Qt's `QTableView` supports freezing columns natively; the task is to expose the control (`Ctrl`+`Alt`+click on the header and a menu command), save the number of frozen columns in the folder format and restore it when navigating. It must interact well with the existing column reordering (if the user moves a frozen column, the freezing point is reinterpreted) and with the views that have no column header, where the command simply does not apply.

- Freeze columns up to a point with `Ctrl`+`Alt`+click on the header or from the header menu; repeating the gesture unfreezes.
- Save the number of frozen columns with the folder format and restore it per location; compatible with movable columns.

### Notes attached to files: descriptions that travel with them

Sometimes what is missing next to a file is not a technical datum but **a human note**: what this folder contains, what this photo is of, which version this document is. The file manager must allow **assigning a description or comment to a file or folder** —from the properties dialog, the metadata panel or the menu— and show it as a tooltip or column when appropriate. The underlying decision is **where the note lives**: in a sidecar file (`descript.ion` inside the same folder, a format that other tools can share) or in extended attributes of the file itself. On Linux both paths exist (sidecar files or `xattr`), with the same dilemma as in the originating system: the sidecar file is portable and shareable but clutters the listing (and must be hideable); extended attributes are elegant and invisible but depend on the file system and do not travel when copying to another kind of disk. What matters is that the choice is configurable and that when **copying or moving** it is explicitly decided whether the description is preserved.

**A layer of meaning over the file system.** Descriptions are not embedded metadata (those are managed by the metadata editor per media type): they are an independent layer, with its own dialog and its own copy rules, that can be applied to several items at once (same note for an entire selection, or recursively inside folders) and that is edited from the same places where the user already looks at properties and metadata.

**Implementation notes.** The descriptions service chooses its backend by configuration (a `descript.ion` sidecar file hideable from the listing, or `xattr` on the file systems that support it), exposes an assignment dialog with apply-to-selection and recursion, and integrates into the description column/tooltip and into the conservation rules when copying (Phase 3) alongside the metadata policy already defined. When using `xattr` on Linux one must keep in mind that not all file systems support it and degrade with a warning.

- Assign description/comment to files and folders from properties and the metadata panel, with apply to the selection and recursion into folders.
- Configurable backend: `descript.ion` sidecar file (hideable from the listing, shareable) or extended attributes (`xattr`) with degradation on systems without support.
- Show the description in a tooltip or column and decide its preservation when copying/moving as part of the metadata policy.

### The file manager's vocabulary: internal commands, arguments and external programs

A file manager can be thought of as a **language**: a small, well-designed set of internal commands —navigate, select, copy, move, delete, rename, create folder, search, change attributes— that combine with **arguments** to express almost any operation, and that constitute the common vocabulary of all the surfaces: menus, bars, shortcuts, command palette, custom buttons and, later on, extensions (Phase 13). The command reference of the originating file manager teaches the design of that vocabulary: each command declares which arguments it accepts and of what type —**flag** (on/off), **with value**, **optional**, **numeric**, **multiple** (a list) or **raw** (consumes the rest of the line)—, so that the same operation serves the simple case ("copy the selection to the current destination") and the declarative one ("copy the selected `.jpg` files to this specific path, asking if it exists"). Typed arguments are not bureaucracy: they are what lets a button editor, the palette or a script describe an action without reimplementing its logic.

**Passing context to external programs.** When an action launches a program from outside the file manager, the command needs **control codes** that insert the context into the command line: the selected files —with full path or name only, one by one or all at once, and with the "mandatory" variant that does not run if there is no selection—, the current folder, the destination folder, a formatted date (for generated names such as "Report-2025-09-02"), the sanitized clipboard contents or the result of a **runtime dialog** (choose a file or folder, ask for a text). It is the same mechanism that the file-type actions and the external-program buttons already anticipate, elevated to a single marker expansion engine reused by all the surfaces: whoever learns the marker of an "open with" action also uses it in a button or in a name template.

**Modifiers: the behavior around the command.** In addition to arguments, the reference defines **modifiers** that alter how an action runs without touching its logic: restrict the operand (only files, only folders, only the first selection), condition enablement or visibility (disable when there is no selection, hide depending on the folder type), ask for confirmation with its own text or run silently, keep the selection after operating, run synchronously or asynchronously, and vary the effect according to the modifier key pressed (the same button copies on a normal click, moves with `Shift`, links with `Ctrl`). These declared behaviors —not scattered among ad hoc confirmation dialogs— are what make the action registry consistent and the palette capable of explaining why an action is disabled.

**Implementation notes.** The `ActionRegistry` (Phase 1.2) moves to modeling each action with a schema of typed arguments and declarative modifiers (operand, enablement conditions, confirmation, per-key variants), keeping the callback as a last resort. The marker expansion engine is a single module shared by type-based actions (1.2.2), buttons (1.2.3) and generated names (create folder, duplicate), with a documented minimal subset: selection (with the mandatory variant), current/destination and XDG paths, formatted date/time, counter, clipboard and input dialogs. The argument types studied in the reference file managers are translated into a per-action specification that validates invocations from the palette, the button editor or extensions.

- The action registry declares the argument schema of each command (flag, with value, optional, numeric, multiple, raw) and the modifiers (operand, enablement by context, confirm/silent, variants by modifier key, synchronous/asynchronous).
- Minimum vocabulary of registerable internal commands: navigate, select (all/none/invert/pattern), clipboard, copy/move/duplicate, delete (trash/permanent), rename, create folder, search, change basic attributes and empty trash.
- Single marker expansion engine shared by "open with" actions, buttons and generated names: selection (one/all, name/path, mandatory), current and destination folder, date/time, counter, clipboard and runtime dialogs.
- The palette explains why an action is disabled by consulting the declarative modifiers, without scattered logic.

### A single field registry: status bar, columns, tooltips and renaming share vocabulary

The information about a file —name, size, date, type, owner, and content-based metadata such as dimensions, duration or artist— is displayed in many surfaces: view columns, per-type tooltips, renaming with metadata, type summary, exportable listing and the **status bar**. The technical reference of the originating file manager teaches two design lessons so that this information does not become fragmented: there is a **catalog of status bar codes** (counts of files/folders/selected items and totals, selection size, items hidden by filter, used/free disk space with a graph, cumulative audio and video duration, percentages and bars) and a **catalog of metadata keywords** for columns (dates, name and path, sizes, attributes, image EXIF, music tags, video, documents). The product decision for Linux File Manager is to unify both into a **single registry of typed fields** that is the single source of truth for all surfaces: each field has a canonical identifier, a type (text, number, size, date/time, duration), a context (list item, selection aggregate, folder aggregate, disk, window) and a provider —and the surfaces only decide which fields they show and how they format them, never how they are obtained.

**A vocabulary that the evaluator also speaks.** If the fields have stable identifiers, those same names are the **evaluator variables** of Phase 13: `{size}` in a tooltip template and `size` in a filter expression are the same datum. The markup can use clear namespaces —`item.*` for the file, `sel.*` for selection aggregates, `dir.*` for the folder, `disk.*` for the volume, `win.*` for the window state— and explicit formatters after the field (`{size|auto}`, `{modified|date:yyyy-MM-dd}`), instead of inventing one code per variant. Thus learning a field serves for columns, tooltips, renaming, the status bar and expressions; the catalog is generated from the registry itself and documented with examples per surface.

**The status bar as a consequence, not an exception.** With a field registry, the configurable status bar is simply a definition of sections (template, visibility condition, alignment) resolved by the same engine as the columns. The reference contributes concrete UX refinements: **automatically hide empty sections** (do not show a permanent "0 selected" or "0 hidden"), separate counts and sizes by category (files versus folders), show how many items the active filter hides, include the **disk usage graph with color threshold** and, when there are no visible columns (icons/thumbnails), a detail of the last selected file with its dates and size.

**Implementation notes.** The field registry (`FieldRegistry`) is built by migrating the columns of the existing model (`COLUMN_KEYS` of `file_system_model`) and the fields of `metadata_for_path`, and separately adding the costly fields as **lazy**: they are only resolved when a column/tooltip requests them, with per-file cache and in the background (dimensions and EXIF with PIL/exifread, duration/tags with mutagen/pymediainfo, size on disk and links with `stat`). The status bar moves from fixed, imperative labels to a widget that renders the JSON definition of sections with live preview (Phase 7.1), and the same identifiers feed the evaluator variables (Phase 13.5). The policy for empty and error cases is common: an unavailable field produces an empty string, an empty tooltip line is omitted, an empty status bar section is hidden.

- Single registry of typed fields as the source of truth of columns, tooltips, renaming, type summary, listing and status bar; stable identifiers with namespaces (`item.*`, `sel.*`, `dir.*`, `disk.*`, `win.*`) and explicit formatters.
- Costly fields as lazy with cache and background (EXIF/image, audio, video, size on disk, links), activated only when a surface requests them.
- Status bar as a definition of sections resolved by the registry: hide empty/zero sections, separate counts and sizes by category, indicator of items hidden by filter, disk graph with threshold, and detail of the last selected item when there are no columns.
- The registry identifiers are the evaluator variables of Phase 13, so that a template and an expression use the same vocabulary.

## Current state summary

The project already has a broad functional base. It is not in its initial phase. The following already exist:

- Main window with menu bar, toolbar, status bar and panels.
- Tabbed sidebar with `Quick Access`, `This Computer`, `Network`, `Bookmarks` and `Recents`.
- History navigation and editable location bar.
- Keyboard experience and command palette started, with focus on quick access to key actions.
- File operations: copy, cut, paste, rename, delete, send to trash.
- `Icons`, `List`, `Details` and `Compact` views.
- Configurable modern context menu.
- XDG support for localized user folders.
- Functional side preview.
- Image thumbnails in the main area of the file manager.
- Configuration persistence and automatic recreation of missing data files.
- Foundation oriented to Debian packaging.

## Confirmed achievements

- [x] Technical rename of the project to `lfmapp` to avoid conflict with `lfm` from Debian.
- [x] Runtime icon helper to prefer system icons with a safe fallback.
- [x] Use of system icons from `/usr/share/icons/` instead of depending on Tabler.
- [x] Application icon fixed so it also appears in the task bar.
- [x] Sidebar redesigned into compact tabs with icons for the five main sections.
- [x] Correct XDG User Directories support for `Desktop`, `Documents`, `Downloads`, `Music`, `Pictures` and `Videos`.
- [x] `Quick Access` uses the real system paths and no longer duplicates those folders inside `Bookmarks`.
- [x] `This Computer` and `Bookmarks` are now better separated conceptually.
- [x] "Open in Terminal" fixed to respect the terminal configured in preferences.
- [x] Removal of the behavior that opened terminals maximized or in fullscreen.
- [x] Default terminal priority changed to prefer `qterminal`.
- [x] Documentation added about the configuration location and how to reset the program by deleting `~/.local/share/linux-file-manager/`.
- [x] Automatic recreation at startup of missing data files and folders, such as `config.json`, `bookmarks.json`, `tags.db`, `extensions/` and `vault/`.
- [x] `Details` columns are now movable and resizable.
- [x] `List Columns` menu accessible with right-click on the header.
- [x] New columns implemented in `Details`: `Created - Time`, `Date Accessed`, `Date Created`, `Detailed Type`, `Group`, `Location`, `MIME Type`, `Octal Permissions`, `Owner`, `Permissions`, `SELinux Context` and `Modified - Time`.
- [x] File icons are shown only in the `Name` column, not in the other columns.
- [x] Improved modern context menu with `Cut`, `Copy`, `Paste`, `Rename`, `Share` and `Delete` actions.
- [x] Option in Preferences to enable or disable the modern context menu.
- [x] Initial state fixed so `Paste` appears disabled when there is nothing in the clipboard.
- [x] Robust configuration loading with automatic backfill of new keys in old configurations.
- [x] Side image preview fixed using `QImageReader` in the background and `QPixmap` only in the UI thread.
- [x] Side preview support for a selected image.
- [x] Image gallery support in the side panel for folders with several images.
- [x] Image thumbnails directly in the main area of the file manager, independent of the side panel.
- [x] Thumbnails visible in `Icons`, `List`, `Details` and `Compact`.
- [x] Thumbnail cache for `png`, `jpg`, `jpeg`, `gif`, `bmp`, `svg` and `webp` formats.

## Important technical decisions already made

- No embedded Tabler icons will be used as the main source.
- The program must use the system icons to respect the user's active theme.
- Icon resolution uses the **same system that Thunar uses** to find the icon themes of the system: both delegate the lookup to the toolkit's native theme engine, which reads the user's **active system icon theme** from its indexed `index.theme` files — in Thunar that is GTK's `GtkIconTheme` (`gtk_icon_theme_lookup_icon_for_scale`), in Linux File Manager it is Qt's `QIcon.fromTheme`. Neither application walks the theme directories by itself nor probes other icon themes, which is what makes lookup fast and lets the UI follow theme changes. The implementation was studied from the Thunar sources listed below; as with every idea in this roadmap, only the interaction logic was re-expressed for Qt/PyQt6, **no code was copied** (Thunar is GPL-2+, this project GPL-3.0-or-later):
  - https://github.com/xfce-mirror/thunar/blob/master/thunar/thunar-icon-factory.c
  - https://github.com/xfce-mirror/thunar/blob/master/thunar/thunar-file.c

  **For developers** — how the pieces map between Thunar and `lfmapp/ui/icons.py`:
  - *Which icons the active theme provides*: Thunar asks the theme object with `gtk_icon_theme_has_icon()` before committing to a name; Qt exposes the same check implicitly — `QIcon.fromTheme(name)` returns a null icon when the active theme lacks the name. Both engines are indexed and cache their theme data, so the check is cheap.
  - *Where the "active system theme" comes from*: the platform theme (qt6ct, portal or desktop settings) reports it. Qt exposes it through `QIcon.themeName()` and searches `QIcon.themeSearchPaths()` (`~/.icons`, `~/.local/share/icons`, `/usr/local/share/icons`, `/usr/share/icons`, …); the GTK equivalents live in `GtkIconTheme`'s search paths. If the app does not follow the desktop theme, check `qt6ct`/the desktop icon-theme setting first (`gsettings get org.gnome.desktop.interface icon-theme` or the XFCE setting).
  - *Caching*: Thunar caches loaded pixmaps keyed by (name, size, scale, symbolic, foreground color) and clears the cache when the theme emits `changed`; `app_icon()` keeps a per-process `_ICON_CACHE` keyed by icon name and clears it whenever `QIcon.themeName()` changes (`_refresh_cache_on_theme_change`). Known misses are cached too, so each name is asked once per theme.
  - *Icon names per file*: Thunar picks a themed name from the file role or MIME content type and only uses it if the theme ships it (`thunar-file.c`: `/` → `drive-harddisk`, home → `user-home`, folders → `folder`, trash → `user-trash`, …). Linux File Manager follows the same convention for its UI icon names (see `_ADDITIONAL_ICON_NAMES` and `_ICON_ALIASES` in `lfmapp/ui/icons.py`); prefer standard freedesktop names so any theme provides them.
  - *Persisted paths are a last resort, never an override*: `initialize_icon_cache()` restores file paths found in earlier sessions only for names the active theme lacks; when the theme does provide a name, the live engine wins, so changing the system icon theme is reflected like in Thunar.
  - *Debugging*: `python3 -c "from PyQt6.QtGui import QIcon; print(QIcon.themeName(), QIcon.themeSearchPaths())"` shows what Qt sees; `lfmapp.ui.icons.app_icon("folder")` returns the icon exactly as the running app would resolve it.

  Baseline finding #1: `MainWindow` construction dropped from ~11.5 s to ~1.0 s on the reference machine (≈1.4 s including `show()` with a clean profile).
- To change the icon theme in Qt environments, the user may need `qt6ct`.
- The relevant configuration/data storage is at:
  - `~/.local/share/linux-file-manager/`
- During development it is sometimes convenient to delete that folder to force the new default values to show up if an old config hides them.
- The project aims to comply with Debian policies, so name conflicts must be avoided, licenses reviewed and dependencies taken care of.

## Inventory of packages and utilities worth using (Debian 13)

General rule: **do not build code when the system already offers a proven utility**; first integrate what is already installed and only declare new dependencies when they bring clear value. The `packages_available_debian13_pyqt6.txt` inventory lists the available PyQt6 modules; `packages_available_debian13_python3.txt` is the complete catalog of the system's `python3` packages (5567 entries). This section summarizes the decision made after reviewing both and contrasting them with the real code of `lfmapp`.

### Available PyQt6 modules and verdict

- **Installed and worth using today**: `python3-pyqt6` (base), `python3-pyqt6.qtsvg` (SVG thumbnails via `QImageReader`) and `python3-pyqt6.qtpdf`. The latter opens the door to **PDF preview with `QPdfDocument`** without additional dependencies (backlog P3 "Video/PDF/document previews").
- **Optional with future value** (do not declare yet): `python3-pyqt6.qtmultimedia` (audio and video playback/preview inside the file manager, backlog P3), `python3-pyqt6.qsci` (editor with syntax highlighting if script editing or advanced renaming with text preview is ever integrated), `python3-dbus.mainloop.pyqt6` (D-Bus integration with the Qt event loop: portals, notifications, MPRIS — Phase 10) and `python3-superqt` (auxiliary widgets: *flow layout* for filter chips, collapsible panels — Phases 5.2/7.1).
- **Discarded**: `qtwebengine`, `qtquick`/`qtqml`, `qtcharts`, bluetooth/NFC/sensors/positioning/serial/websockets/remoteobjects modules (they do not contribute to a file manager; `qtwebengine` is also very heavy); `python3-qtpy` (the project is already locked to PyQt6 for Debian; an abstraction layer adds surface without benefit); `python3-qtawesome` (decision already made: system icons, not embedded); `qdarkstyle`/`qt-material` (decision already made: respect the system Qt theme); and `pyqt6-dev`/`pyqt6-examples`/`*-dev` (development only).

### `python3` libraries already installed that the code does not yet take advantage of

Verified with `dpkg` on this system; several of them solve things that today are done by hand or via extension and should be adopted when their area is touched:

- `python3-magic` → **MIME detection by content** (today `models/file_system_model.py` uses `mimetypes.guess_type`, which only looks at the extension). Basis for a reliable `MIME Type` column, a correct `Open with` and groupings by real type.
- `python3-chardet` / `python3-charset-normalizer` → **encoding detection** for the text preview (today `preview_worker.py` reads with `utf-8`, `errors="replace"` and shows "�" in non-UTF-8 files); detect first and then decode.
- `python3-docx` and `python3-openpyxl` → **text extraction from `.docx`/`.xlsx`** without parsing XML by hand (today `preview_worker.py` unpacks the `.docx` with `zipfile` and `_text_from_xml`); useful for document previews and content search (Phase 5.1, `search_service`).
- `python3-pil` → **EXIF metadata and orientation** of images (rotate thumbnails according to EXIF, expose dimensions/camera in properties), without depending on extensions.
- `python3-psutil` → disk space, mounts and system resources for the status bar and the properties dialog, with a single API instead of scattered queries.
- `python3-pypdf` → PDF metadata and text in pure Python, alternative/complement to `poppler-utils` and `qtpdf` for previews without depending on external binaries.
- `python3-puremagic` → second source of type detection by pure magic signature, without libmagic, as a fallback for `python3-magic`.
- `python3-dateutil` → flexible parsing and formatting of dates (useful for renaming with date, relative-date filters and presets).
- `python3-libarchive-c` → read listings/content of archive formats (zip, tar, 7z, cpio…) for property views and collections, complementary to Phase 10.1 (Ark/PeaZip for the write/extract operations).
- `python3-brotli` and `python3-zstandard`/`python3-zstd` → Brotli/Zstandard compression support if "compressed" size columns or reads of formats using those codecs are ever offered.

### Installed `python3` candidates (Groups A and B already present on the system)

The user installed these packages to unlock future capabilities; the code must use them with runtime detection (`shutil.which` or conditional import) and degrade with a clear message if they are missing.

**Group A — recommended with clear value:**
- `python3-natsort` → "natural" sorting of names (`foto2` before `foto10`) if Qt does not cover the case (today it sorts by simple name).
- `python3-watchdog` / `python3-pyinotify` → file system change watching more powerful than `QFileSystemWatcher` if automatic refresh of folders or of the index is needed.
- `python3-keyring` + `python3-secretstorage` → store network credentials (SFTP, Phase 10) in the desktop keyring instead of in plain text.
- `python3-pymediainfo` → access to `mediainfo` from Python without subprocesses for media columns/properties (today the binary is used).
- `python3-piexif` / `python3-exifread` → specific EXIF editing/reading if the future photographic metadata editing is done in pure Python.
- `python3-filetype` → lightweight alternative to `python3-magic` for type detection.
- `python3-xxhash` → fast hashes for the duplicate finder of backlog P2.
- `python3-av` → FFmpeg wrapper for video metadata/sampling without spawning subprocesses (alternative to calling `ffmpeg`).
- `python3-zstandard` → Zstandard compression support.

**Group B — optional / future (installed):**
- `python3-qrcode` / `python3-svglib` / `python3-cairosvg` → QR code generation and SVG conversion/reading if actions such as "share as QR code" or additional SVG preview are added (low value today).
- `python3-send2trash` + `trash-cli` → complementary XDG trash utilities.
- `rclone` / `python3-paramiko` → remote/cloud backends if a remote provider of its own without mounts is decided.
- `ffmpegthumbnailer` → video thumbnail generation via CLI, alternative/complement to `ffmpeg`.
- `rmlint` / `fdupes` / `rdfind` → hash/duplicate engines for the duplicate finder of backlog P2, behind the in-house review interface.
- `python3-eyed3` → **not installed**: `mutagen` is already installed and covers more formats.

### System utilities already installed that the program must invoke

- `ffmpeg` → video thumbnails, duration and media metadata; already used in `services/preview_worker.py`; extend to the thumbnail cache of the main area (Phase 9.1) and to audio/video previews (P3).
- `python3-mutagen` → reading/editing of audio metadata (ID3/FLAC/MP4 tags); basis for the music columns and future metadata editing without writing own parsers.
- `mediainfo` → video/audio/document metadata in `Details` columns and in the properties view; accompanied by `python3-pymediainfo` only if access from Python without subprocesses is needed.
- `poppler-utils` (`pdfinfo`, `pdftoppm`, `pdftotext`) → PDF metadata, rendering and text extraction; complements `python3-pyqt6.qtpdf` (visual preview) with content and page search.
- `rsync` → engine of the already planned two-phase synchronization tool: `rsync --dry-run` produces the reviewable comparison phase and `rsync` applies the confirmed phase, reusing its maturity (date/size criteria, deletion, exclusions) instead of reimplementing the comparison.
- `ripgrep` → backend of text content search (Phase 5.1) for local folders, much faster than a homemade SQLite indexer; the current index (`textindex_service.py`) remains for names/locations.
- `sshfs` (+ `gvfs`, `udisks2`) → mounting of remote locations and removable media; `sshfs` allows treating an SFTP as a local folder without coupling to the UI (Phase 10). `rclone`/`python3-paramiko` remain candidates only if a remote provider of its own without mounts is decided.
- `7z` and `unrar` → format backends for Ark/PeaZip (see Phase 10.1); do not invoke directly from the UI.
- `gio` (glib) → desktop utilities (`gio trash`, `gio mount`, `gio open`) as the standard alternative to manual trash/network implementations when the environment supports them.
- `python3-magic` and `python3-pil` → **already installed**: MIME detection by content and EXIF metadata of images; see their intended use in "`python3` libraries already installed that the code does not yet take advantage of".
- `ultracopier` (`/usr/bin/ultracopier`, package `ultracopier` 2.2.6.0) → **external copy tool with a queue**: pause/resume, speed control, advanced collision and error management. CLI: `ultracopier cp <origen...> <destino>`, `ultracopier mv <origen...> <destino>`, and `?` as destination so that Ultracopier asks the user. It is integrated as an **optional alternative copy/move** next to the native engine of the file manager (see Phase 10.2). Man page: `/usr/share/man/man1/ultracopier.1.gz`; menu entry in `/usr/share/menu/ultracopier`.
- `rmlint`/`fdupes` → optional candidates as hash engine for the duplicate finder of backlog P2, behind the in-house review interface.

**Note:** batch image conversion is **not** contemplated (project decision: on Linux there are already dedicated tools). Groups A and B of `python3` libraries are already installed on the reference system (2026-09-02), as is `ultracopier`; the code must use them with runtime detection (`shutil.which` or conditional import) and each capability must degrade with a clear message when the utility is not present.

## Key files for continuing

### Configuration and paths core

- `lfmapp/core/config.py`
- `lfmapp/core/paths.py`
- `lfmapp/core/app_data.py`

### Main UI

- `lfmapp/ui/main_window.py`
- `lfmapp/ui/workspace.py`
- `lfmapp/ui/sidebar.py`
- `lfmapp/ui/preview_panel.py`
- `lfmapp/ui/preferences_dialog.py`

### File model and thumbnails

- `lfmapp/models/file_system_model.py`
- `lfmapp/services/preview_worker.py`

### File services and external tools

- `lfmapp/services/extractor_service.py` (internal compressor; removed from the UI, see Phase 10.1)
- `lfmapp/services/archive_tool_service.py` (new: Ark/PeaZip backends for compression and delegated extraction)
- `lfmapp/services/file_operations.py`
- `lfmapp/services/operation_queue.py`

### Documentation and planning

- `README.md`
- `ROADMAP.md`

## What to review first after a reformat

1. Restore the repository and open this file.
2. Run the project and verify that it starts with the automatically recreated configuration.
3. Visually verify:
   - Tabbed sidebar
   - Modern context menu
   - Respect for the configured terminal
   - Image thumbnails in the four views
   - XDG User Directories in `Quick Access`
4. If something "does not reflect" recent changes, delete:
   - `~/.local/share/linux-file-manager/`
5. Run the minimum test battery.

## Minimum tests recommended when resuming

- `pytest -q tests/test_file_system_model.py`
- `pytest -q tests/test_preview_worker.py`
- `pytest -q tests/test_main_window.py`
- `python3 -m compileall lfmapp`

## Strategic product objective

The project can already be described as a functional, practical Linux file manager well integrated with the platform. The next stage does not consist simply of adding more features, but of transforming that base into a fast, reliable, coherent and pleasant productivity experience.

The product vision is:

> Create the best Linux file manager focused on productivity: fast with keyboard and mouse, safe on delicate operations, capable in batch workflows, unobtrusive and sustainable at the architecture level.

Every new feature must improve at least one of these five outcomes:

1. Reduce time, clicks or keystrokes to complete frequent tasks.
2. Avoid errors or loss of context during file operations.
3. Keep actions and behaviors consistent across all views.
4. Replace unnecessary modals with inline interaction and persistent feedback.
5. Reduce technical coupling so that the project can grow without degrading.

## Overall success criteria

The vision will be considered achieved when the program meets, at minimum, these criteria:

- Usual operations can be completed entirely with the keyboard.
- Copying or moving hundreds of files does not block the interface and offers pause, cancellation, retry and history.
- Name conflicts are resolved predictably, with preview and "apply to all" rules.
- Search shows progressive results and allows saving and reusing filters.
- Mass renaming includes preview, validation and undo.
- Multiple selection and batch actions are visible, coherent and reversible when possible.
- Most non-critical messages appear in bars, banners, panels or non-modal notifications.
- Focus, selection, scroll position and history are preserved when switching views or refreshing a folder.
- Key features have unit, integration and GUI tests.
- `MainWindow` stops being the center of all logic and works mainly as a composer of components.

## Execution rules for agents

Each task of this roadmap must be carried out with these rules:

1. Read `ROADMAP.md`, `README.md` and the related tests first.
2. Do not introduce new business logic directly into `MainWindow` except for minimal wiring.
3. Separate in each change: model/service, controller or coordinator, widget and tests.
4. Maintain compatibility with Debian, X11 and Wayland, unless a task documents an explicit limitation.
5. Respect the theme icons through `QIcon.fromTheme()` and centralized fallbacks.
6. Do not block the UI thread with I/O, indexing, thumbnails or long operations.
7. Add automated acceptance criteria and a brief list of manual tests.
8. Keep translations prepared for Spanish and English; do not introduce visible texts without `tr()`.
9. Do not remove an existing feature without a migration, a documented replacement or a test justifying the change.
10. Update this roadmap when finishing a task, including modified files, tests and known limitations.

## Recommended implementation order

Do not run all initiatives at once. Follow this order:

1. Architecture foundations, actions and UI state.
2. Reliable operations engine and conflict resolution.
3. Keyboard productivity and command palette.
4. Search, filtering and advanced selection.
5. Batch workflows.
6. Visual polish, accessibility and reduction of modals.
7. Performance, compatibility and release preparation.

---

# Phase 0 — Baseline, metrics and regression protection

## 0.1 Functional inventory and flow map

- [x] Document the current navigation, selection, copy, move, paste, delete, rename, search and preview flows.
- [x] Create a matrix indicating which actions exist in the menu, toolbar, context menu, shortcut and command palette.
- [x] Identify the distinct behaviors among `Icons`, `List`, `Details` and `Compact`.
- [x] Record the existing modal dialogs and classify them as essential, replaceable or removable.

**Deliverable:** `docs/ux-flow-audit.md` (59 logical identifiers, surface matrix, classified modal dialogs, 18 tasks T1–T18).

**Acceptance criteria:**

- Each main action has a single logical identifier.
- Every known inconsistency is turned into a concrete task.
- The document includes screenshots or reproducible descriptions of the problems.

## 0.2 Experience and performance metrics

- [x] Measure cold and warm startup time.
- [x] Measure folder opening with 100, 1.000 and 10.000 entries.
- [x] Measure time to the first search result.
- [x] Measure memory consumption during thumbnails and long operations.
- [x] Define performance budgets and record a baseline.

**Deliverable:** `docs/performance-baseline.md` and reproducible scripts in `scripts/` (`bench_startup.py`, `bench_folder_open.py`, `bench_search.py`, `bench_memory.py`).

## 0.3 Tests for critical flows

- [x] Add GUI tests for navigation, selection, view switching, copy/paste, conflict, operation cancellation, rename and search (`tests/test_critical_flows.py`, `tests/test_search_controller.py`).
- [x] Add fixtures with temporary file trees and cases for permissions, symbolic links and Unicode names (`tests/conftest.py`).
- [x] Verify that a cancelled operation does not leave unrecorded partial files (cancellation covered in `test_search_controller.py`; partial cleanup is the responsibility of the Phase 2 queue).

---

# Phase 1 — Modular architecture and unified action system

## 1.1 Reduce `MainWindow` responsibilities

Verified current situation: `lfmapp/ui/main_window.py` went from 3.849 lines to ~1.400. It must become a high-level composer and coordinator; the decomposition advances with pure controllers (logic testable without a window) and UI mixins by concern.

- [x] Create `lfmapp/controllers/` or an equivalent package (`lfmapp/controllers/`: AppState, NavigationController, SearchController, SelectionController, ViewController).
- [x] Extract `NavigationController` for paths, history, back, forward, up and refresh (per-tab history delegated; tests in `test_navigation_controller.py`).
- [x] Extract `SelectionController` for the current selection, multi-selection and derived state (summary in the status bar; tests in `test_selection_controller.py`).
- [x] Extract `FileActionController` for open, copy, cut, paste, rename, trash and delete (the domain logic lives in already existing, tested services —`FileOperations`, `CopyWorker`/`MoveWorker`/`TrashWorker`/`DeleteWorker`, `operation_queue`— and the UI mixins `file_actions_mixin.py`/`transfer_actions_mixin.py` are only UI → services wiring; no redundant pure layer is created, per the criterion "do not artificially split code without cohesion").
- [x] Extract `ViewController` for view switching, zoom, columns and visual persistence (`lfmapp/controllers/view_controller.py`: per-folder persistence policy, restoration when navigating, clear; `set_view_mode`/`go_to`/`toggle_folder_view_persistence` delegate to it; tests in `test_view_controller.py`).
- [x] Extract `SearchController` for queries, filters, cancellation and results (integrated with indexed text and thread; tests in `test_search_controller.py`).
- [x] Extract `PreviewController` for the preview lifecycle (`PreviewWorker` separated into `lfmapp/services/`, `PreviewPanel` in `lfmapp/ui/` — the preview lifecycle no longer lives in `MainWindow`; wiring in `central_status_mixin.py`/related mixins).
- [x] Extract `OperationCenterController` for the queue, progress, errors and history (mixins `operation_center_mixin.py` + `history_actions_mixin.py` + `BackgroundOperationQueue`; AppState exposes an operation counter).
- [x] Move the construction of menus and toolbars to declarative components or factories (mixins by block: `palette_actions`, `menu_bar`, `context_menu`, `search_actions`, `transfer_actions`, `file_actions`, `operation_center`, `history_actions`, `toolbar`, `central_status`, `tabs_navigation`, `view_controls`, `archive_tag_vault`).

**Acceptance criteria:**

- `MainWindow` does not contain copy, search, filtering, conflict resolution or thumbnail algorithms.
- The controllers can be tested without showing the entire main window.
- There are no duplicate signal connections when switching workspaces or recreating widgets.
- Initial goal: reduce `main_window.py` below 1.500 lines; final goal: below 900, without artificially splitting code without cohesion. **Status: `main_window.py` went from 3.849 to ~333 lines (initial and final goals met), decomposed into 13 per-concern UI mixins in `lfmapp/ui/` plus the pure controllers in `lfmapp/controllers/`.**

## 1.2 Central action registry

- [x] Create an `ActionRegistry` with stable identifiers, translatable text, icon, shortcut, enabled state and callback (`lfmapp/actions/registry.py`; `ActionSpec` and `ActionRegistry` UI-agnostic).
- [x] Make the menu, toolbar, context menu and palette reuse the same `QAction`s or definitions (adapter `lfmapp/actions/qt.py`; `MainWindow.action_registry` populated with the core catalog from `catalog.py` with real callbacks).
- [x] Centralize the enablement conditions based on selection, clipboard, permissions, view and active operation (predicates `enabled_when` + `enablement_map` in `catalog.py`/`registry.py`; `MainWindow.refresh_registry_enablement()` builds the real context and applies `apply_enablement` to Edit › Copy/Cut/Paste and Undo/Redo — resolves audit inconsistency T11; extending to more surfaces remains as a refinement).
- [ ] Avoid duplicate actions with contradictory states (the registry rejects duplicate ids; harmonizing the legacy surfaces is pending).
- [ ] Allow the user to view and customize shortcuts without creating silent collisions.
- [ ] Model each action with a typed argument schema (flag, with value, optional, numeric, multiple, raw) and declarative modifiers: operand (files/folders/only the first), enablement by context, confirmation/silent, modifier-key variants and synchronous/asynchronous — resolved against the same engine, not with ad hoc dialogs.
- [ ] Implement the single marker expansion engine shared by "Open with" actions, buttons and generated names: selection (one/all, name/path, mandatory variant), current/destination folder, XDG paths, date/time, counter, clipboard and runtime input dialogs.

**Acceptance criteria:**

- "Rename", "Delete", "Paste" and other actions show the same state on all surfaces.
- Changing a shortcut is reflected without restarting when it is technically safe.
- Shortcut collisions are detected and clearly explained.

### 1.2.1 Filtering, search and selection
- [ ] Define a unified state for quick filtering and structured search shared by the filter bar, the permanent filter field and the search menu.
- [ ] The quick filter must be activatable with a single key, update the view immediately, show the number of hidden items and be clearable with `Esc`.
- [ ] Implement a "Show all" mode that temporarily disables the filters of the current panel without losing the underlying filter configuration.
- [ ] Support an optional persistent filter field in the bar with history and a filter menu, controlling the same state as the popup filter bar.
- [ ] Model the filter field as a view over a single state (pattern + destination), and allow redirecting it to the visibility rules of the folder format.
- [ ] Support the visibility rules of the folder format (inclusion/exclusion by name, applicable to files, folders or both) as a pure scope × effect function, according to the table in the inspiration section.
- [ ] Support advanced filtering options: partial matching, ignore diacritics, "any word" mode, regular expressions and evaluator-style complex conditions.
- [ ] The selection state must be central, with clear counts and automatic selection commands by pattern, extension, duplicates, empty folders and similar criteria.
- [ ] Define source/destination state for copy/move operations in dual panels and in single mode, so that the flow does not depend on a single main view.
- [ ] The action model must expose the active source/destination as a first-class value, so that Copy/Move/Paste can decide their target without scattered logic.
- [ ] The view controller must allow sorting and grouping by multiple fields, with support for non-visible fields and direction changes via modifier keys.

### 1.2.2 File type taxonomy, groups and per-type actions

- [ ] Create a central, editable catalog of file types (extensions with description, icon, MIME) and type groups ("Images", "Music", "Documents", "Video", "Compressed files", "Programs" and the user's own groups), serializable with a version and resettable to default values.
- [ ] Support general classes ("all files", "all folders", "all files and folders", "no extension", "unknown") with resolution by inheritance from the general to the specific.
- [ ] Add a resolution service, "given a path, which types and groups match", consumed by the Type column, the search, automatic formats by content, rule-based highlighting and the menus (removing the duplicated extension tables from the current code).
- [ ] Define actions per type and group (external application with the file as argument, internal function, or submenu with separators) resolved in the context menu as a union of all the matching classes, integrated with the `ActionRegistry` (1.2) for shortcuts and palette.
- [ ] Support double-click with modifiers and the drop menu (right-button drag) with the same per-type resolution mechanism.
- [ ] Configure what double-click does per type/group (default application, built-in viewer, play, properties), with "looks like text" detection for unknown types and opening in the file manager's text viewer.
- [ ] Support an optional "open with a single click" mode in the mouse settings (left click opens, hover and wait selects, with `Ctrl`/`Shift` for multiple/range), without altering right click or dragging.
- [ ] Use `python3-magic` (installed) as a content-based MIME complement for unknown types or misleading extensions.
- [ ] Allow references to type groups in patterns (token `grp:NombreGrupo`): select/filter by "all images" or "all documents" without enumerating extensions, and have the pattern automatically reflect changes to the group.

### 1.2.3 Visual customization of bars, buttons and shortcuts

- [ ] Add a customization mode: enter/edit bars with the mouse (move, duplicate with `Ctrl`, remove by dragging out, insert a separator with a short drag), double-click to edit each button, and OK/Cancel with undo of all changes.
- [ ] Define the button as a serializable object (one or more functions per click, icon, label, tooltip, shortcut), with internal commands from the `ActionRegistry` or external programs with markers of the selected files/folders.
- [ ] Support nestable dropdown menu buttons and "menu buttons" (main function + list), and resizable fields (path, filter, search) inside the bar.
- [ ] Shortcut dialog with categories, search by key/command, keystroke capture, key-only shortcuts and temporary disablement; context-based conflict detection and shortcut export/import.
- [ ] Show the shortcut combination in menus and tooltips, and apply shortcut changes on the fly without restarting.

## 1.3 Explicit UI state model

- [x] Define an observable state for path, selection, view, search, preview and operations (`lfmapp/controllers/app_state.py`: `AppState` with path, selection, view, search and operation counter; per-key listeners; synchronized in `go_to`, `on_selection_changed`, `set_view_mode`, search and the operation queue).
- [ ] Avoid widgets directly querying multiple services to rebuild the same state (progressive migration to `AppState`; legacy surfaces still read services).
- [ ] Preserve focus, selection and scroll when refreshing or switching views.
- [ ] Model the virtual locations of the system with their own namespace (`this-computer:`, `home:`, `quick-access:`, `recents:`, `network:`, collections/libraries/queries) but with the same view and operations interface as real folders (`classify_location` prepares the classification; virtual namespaces pending).
- [ ] Distinguish in the model between physical folder, collection (loose references), library (union of folders), stored query (re-runnable results) and navigable compressed file, without breaking the common operations.

---

# Phase 2 — Reliable file operations and activity center

## 2.1 Asynchronous operations engine

- [ ] Convert copy, move, delete, restore and extract into jobs of a common queue.
- [ ] Support copy/move variants with the same engine: duplicate in the same folder, duplicate with date, copy/move as (name or pattern with `*`) and update only what is missing or changed (date/size).
- [ ] Support creating symbolic links (absolute and relative, with `os.symlink`) and hard links (with `os.link`) at the destination as variants of "copy", also accessible from the drop menu ("create link here").
- [ ] Apply a preservation policy when copying: permissions and timestamps by default (`shutil.copy2`), extended attributes (`python3-xattr`) and owner depending on the destination, with a per-operation option; handle sparse files when the destination supports it.
- [ ] Add secure deletion by overwriting (configurable passes) as its own job with progress and cancellation, in addition to the trash and permanent deletion.
- [ ] Support filtered operations: copy, move, delete and change attributes, processing only the items (recursive) that match a clause filter, activatable per operation and deactivatable when finished.
- [ ] Expose states: pending, preparing, running, paused, cancelling, completed, failed and completed with warnings.
- [ ] Add real pause and resume where the backend allows it.
- [ ] Add cooperative cancellation and safe cleanup of partial files.
- [ ] Add retry of an entire operation or only of failed items.
- [ ] Compute progress by bytes and by items, speed and estimated time without blocking the UI.
- [ ] Limit concurrency to avoid saturating disk or network.
- [ ] Record source, destination, conflict decisions, errors and outcome.

## 2.2 Non-modal Operation Center

- [ ] Create a drop-down or persistent bottom panel for active and recent operations.
- [ ] Add a compact jobs bar at the bottom edge: one button per active job with action, source/destination, progress bar and status color (running, paused, error); click opens/closes the detail, right-click allows pause/resume/abort.
- [ ] Show aggregate progress and per-job detail.
- [ ] Allow pausing, resuming, cancelling, retrying, hiding and clearing completed ones.
- [ ] Allow opening the source or destination location from an operation.
- [ ] Keep discreet notifications when completing, failing or requiring intervention.
- [ ] Minimize individual progress indicators when there are several jobs (or only when the jobs bar is visible), preventing dialogs from covering the window; minimized indicators do not appear in the taskbar.
- [ ] Do not use a modal progress dialog as the main interface.
- [ ] Coordinate application exit with the queue: when closing with active jobs, warn and wait, allow continuing in the background or cancelling, without abandoning half-done operations or losing configuration (forced termination detected and recovered on the next startup).

**Acceptance criteria:**

- The user can continue navigating while files are being copied.
- Closing the panel does not cancel the operation.
- An individual error does not hide the result of the rest of the batch.
- The interface keeps responding with simulated multi-gigabyte operations.

## 2.3 History, undo and redo

- [ ] Integrate the queue with `operation_history.py`.
- [ ] Define which operations are reversible and under which conditions.
- [ ] Implement undo for rename, move, create, send to trash and restore when it is safe.
- [ ] Clearly show when an operation cannot be undone.
- [ ] Allow redoing failed or recurring operations with prior review.

---

# Phase 3 — Robust conflict resolution

## 3.1 Conflict model

- [ ] Create UI-independent conflict objects with source, destination, type, size, dates, permissions and optional checksum.
- [ ] Support file–file, folder–folder, file–folder and non-writable destination conflicts.
- [ ] Separate the decisions for replacement, skipping, renaming, folder merging and keeping both.

## 3.2 Productive conflict UI

- [ ] Show a side-by-side comparison of source and destination: name, location, size, date, content description and thumbnail/icon per side, with differences highlighted in bold.
- [ ] Offer `Replace`, `Skip`, `Keep Both`, `Rename`, `Merge` and `Cancel` only when they apply, plus `Keep Newer`, `Skip Identical` (same size and date, without comparing content) and `Rename Old` (rename the existing one).
- [ ] Add “apply to all remaining conflicts” with an explicit scope and keyboard shortcuts for frequent combinations (replace all, skip all, etc.).
- [ ] Allow editing the name of the incoming file directly in the dialog; while editing, the button changes from “Replace” to “Rename and copy”.
- [ ] Allow rules by condition: newer, larger, same size, same date or same content.
- [ ] Show a preview of the generated name for “Keep Both”.
- [ ] Load descriptions and thumbnails lazily in the background (on demand) without blocking the decision.
- [ ] Allow reviewing a conflict queue before confirming large batches.
- [ ] Remember decisions only during the current operation, unless the user has an explicit preference.

**Acceptance criteria:**

- A file is never overwritten without an explicit decision or a visible rule.
- “Apply to all” states exactly which conflict types it affects.
- Canceling from the dialog returns control to the Operation Center without freezing the application.
- All decisions are recorded in the operation history.

---

# Phase 4 — Keyboard productivity and quick commands

## 4.1 Full keyboard navigation

- [ ] Audit the focus order and initial focus in each view and dialog.
- [ ] Implement consistent shortcuts for the location bar, sidebar, view, preview, operations and search.
- [ ] Allow switching panels without losing the selection.
- [ ] Support full keyboard-driven tab navigation: `Ctrl+Tab`, directional shortcuts, open the selection in new tabs, duplicate and close a tab.
- [ ] Add a visual tab switcher (`Ctrl+Tab`) with the list of open tabs, keyboard selection and most-recently-activated ordering (like `Alt+Tab` for windows).
- [ ] Add a keyboard-navigable folder tree to the sidebar (arrows, expand/collapse with `→`/`←`, rename with `F2`, delete with `Del`), with reveal of the current folder, collapse all except the path and expansion presets.
- [ ] Support paired folders (pairs by absolute path or by regular expression match): open the other side in the opposite panel when navigating, use it as the default destination for copy/sync and link the tabs of both sides.
- [ ] Turn the path bar into clickable breadcrumbs with a manual edit mode accessible by keyboard, overflow into a menu and links with recents.
- [ ] Add keyboard selection: range, toggle, select by pattern, invert and restore selection.
- [ ] Ensure `Enter`, `Space`, `F2`, `Delete`, `Shift+Delete`, `Ctrl+L`, `Ctrl+F`, `Ctrl+H` and the navigation keys have consistent semantics.
- [ ] Enrich the inline rename mode (`F2`) with keyboard: selecting root/extension/name, case transformations and converting dots/hyphens to spaces, cycling through neighboring files, name history and copying the adjacent name.
- [ ] Add “type-ahead” navigation: typing selects quickly by name.
- [ ] Implement the “type to find” field (find-as-you-type): visible overlay with the first match selected, all matches highlighted and scrollbar markers, `F3`/`Shift+F3` to cycle through them, and modes by first key (go to path, select by pattern, filter, search tabs).
- [ ] In details/tiles/thumbnails, adjust font or cell size with `Ctrl`+wheel as a continuous gesture.

## 4.2 Command palette

- [ ] Add a palette invocable with a configurable shortcut.
- [ ] Search actions by name, alias and translated keywords.
- [ ] Show the current shortcut, icon and reason for being disabled.
- [ ] Include contextual actions according to the selection and path.
- [ ] Record recent and favorite commands without mixing sensitive data.
- [ ] Allow navigation commands: go to path, open recent, change view and toggle panels.
- [ ] Allow user ad-hoc commands in the palette (internal command with arguments or external program with the selected files), reusing the button definition from 1.2.3.

## 4.3 Quick actions and a coherent context menu

- [ ] Reduce the context menu to relevant actions and move secondary actions into clear submenus.
- [ ] Build the context menu as the union of the actions of the concrete type, its type group and the general classes (per 1.2.2), with separators, submenus and reordering.
- [ ] Allow defining custom context actions per type/group (external application with the file as argument, internal function or submenu), stored in the type catalog.
- [ ] Make the quick actions row configurable.
- [ ] Prevent the same operation from being named or behaving differently depending on the view.
- [ ] Show immediate feedback when running actions without an obvious visual result.

---

# Phase 5 — Productive-level search and filtering

## 5.1 Instant, cancellable search

- [ ] Separate search by name, content and metadata.
- [ ] Emit progressive results in small batches.
- [ ] Cancel previous queries when typing a new one.
- [ ] Prevent late results from overwriting a more recent query.
- [ ] Show scope, time, result count and indexing status.
- [ ] Allow searching in the current folder, subfolders, chosen locations or “This Computer”.
- [ ] Represent the query as a serializable object (criteria with type/operator/value + scope + exclusions + options), executable in a service that emits progressive batches.
- [ ] Combine criteria in conjunction (all must be met) with absolute and relative operators: name with wildcards/regex/“any word”, textual content, type or type group, date/time (“before”, “between”, “within the last 7 days”) and size with tolerances (±25 %, ±50 %).
- [ ] Support excluding locations by path, wildcard or regular expression, with shortcuts for hidden and system folders, so that excluding a folder avoids traversing it.

## 5.2 Powerful filters

- [ ] Add combinable filters by type, extension, size, date, owner, permissions, tags, hidden and content.
- [ ] Include understandable operators: is, is not, contains, starts with, greater than, less than, before and after.
- [ ] Show active filters as removable chips in the interface.
- [ ] Allow editing filters without reopening a complex modal dialog.
- [ ] Allow saving searches with name, scope and order.
- [ ] Add saved searches to the sidebar or a dedicated section.
- [ ] Serialize filters with a version to allow future migrations.
- [ ] Create a central repository of named saved filters (save, duplicate, rename, describe, delete), available in a dropdown in every tool that accepts filters (copy, delete, search, selection, sync, duplicates).
- [ ] Allow sharing filters as text (clipboard and import) and editing them in text mode in addition to the visual editor, with validation on import.
- [ ] The permanent filter field's dropdown must offer “auto-content” (one pattern per type present in the folder) or pattern history, with separate clearing of filters and history.
- [ ] Support persistent per-folder visibility rules (include/exclude by name for files and folders) that the filter field can edit in addition to the quick filter.
- [ ] Add automatic highlighting by evaluable rules (pattern, type, size, path or attribute) with color, font, icon or pinning effects, stackable and with “stop at the first match”, applied only in the paint delegate.

## 5.3 Results as a workspace

- [ ] Allow opening the containing location without losing the results.
- [ ] Allow directing the results to the current view, the other view or a new tab.
- [ ] Allow refining a search by limiting the space to the previous results, and accumulating or clearing results between queries.
- [ ] Allow copying, moving, renaming, tagging and deleting from the results.
- [ ] Group by folder, type, date or tag.
- [ ] Highlight matches without altering the real name.
- [ ] Keep the query when going back.
- [ ] Support persistent virtual collections as folders: collection root, properties (name, description, icon), sub-collections and default folder format with a location column.
- [ ] Support stored queries: collections that re-execute when navigating to them (automatic or manual refresh) and are created from an existing search.
- [ ] Support libraries: a virtual folder that joins several real folders, with member include/exclude, a default save folder and a real location column.
- [ ] Support navigating inside compressed files as folders (see Phase 10.1 and the inspiration subsection): enter `.zip`/`.7z`/`.tar`/`.iso`, copy members out, add into them when the format allows it.

**Acceptance criteria:**

- First results visible quickly in large trees.
- Saved filters survive restarts and configuration migrations.
- All actions on results use the same controllers and conflict rules as the normal view.
- A stored query shows updated results when navigating to it (or the last batch until refreshed, according to its configuration).
- Libraries reflect the current state of their member folders and distinguish provenance via the location column.

---

# Phase 6 — Advanced selection and batch workflows

## 6.1 Advanced selection

- [ ] Select by glob pattern, optional regular expression, extension, type, size and date.
- [ ] Invert, save, restore and name temporary selection sets.
- [ ] Show a selection bar with the count, total size and relevant actions.
- [ ] Keep the selection when sorting or changing views while the items are still present.
- [ ] Avoid invisible or ambiguous selections after filtering.
- [ ] Support per-folder checkbox mode (part of the folder format) on the existing foundation (`selection_checkboxes`/`checked_paths`): operations act on the checked items, `Space` checks/unchecks, double click and drag do not destroy the checks, and selection↔checks conversion and inversion.
- [ ] Select cells, columns or blocks in the details view (`Ctrl`+right click or lasso) and copy their content to the clipboard as lines or as a table (text/TSV/CSV), independent of the file selection and respecting visible columns.

## 6.2 Bulk rename

- [ ] Create a non-destructive bulk rename flow with a “before/after” preview that updates live and allows checking/unchecking items, hiding those that do not change and manually fixing names (visually pinned).
- [ ] Support transformation modes: literal name, wildcards with part preservation, search/replace and regular expressions, with case sensitivity options and ignore extension by default.
- [ ] Offer accumulable, reorderable actions: prefix/suffix, replacement, configurable numbering (start, digits, increment, placeholder), upper/lowercase with extension handling and text editing by anchors.
- [ ] Apply the batch without closing the dialog, with immediate undo of the last batch, in addition to running as a single recordable and reversible operation.
- [ ] Detect empty, duplicate, reserved, too long or invalid names before applying, highlight conflicts and offer automatic correction.
- [ ] Save presets with groups, favorites, export/import and reset; remember the latest batches and allow creating reusable actions from a preset.
- [ ] Support renaming with metadata (audio/media/image/dates with formatting and character sanitization), supported by the already installed services (`python3-mutagen`, `pymediainfo`, `python3-pil`).
- [ ] Allow templates that generate subfolders or include the parent folder, and recursion into subfolders (content only or folders as well) with multi-level preview.
- [ ] Renumber as a single unit the files that share the same base name and differ in extension (e.g., photo and RAW) so that pairs are not desynchronized.
- [ ] Clipboard: copy the list of names, paste names line by line as replacement or as prefix/suffix.

## 6.3 Other batch actions

- [ ] Create multiple folders or files from a pattern.
- [ ] Change permissions and owner with clear warnings.
- [ ] Apply tags to groups.
- [ ] Compress, extract or compute checksum in batch through the configured external tool (Ark or PeaZip, see 10.1).
- [ ] Open with a chosen application or run a safe custom action.

---

# Phase 7 — Polished, consistent, less modal UI

## 7.1 Visual system and reusable components

- [ ] Define sizes, margins, density, icons, hover/focus/disabled states and typographic hierarchy.
- [ ] Create common components for banners, empty messages, errors, selection bars, chips and progress rows.
- [ ] Remove contradictory local styles and respect the system Qt theme.
- [ ] Test light, dark and high-contrast themes.
- [ ] Audit truncated texts, tooltips, spacing and HiDPI scaling.
- [ ] Support per-file-type tooltips with field code templates (lines omitted if the field does not apply, optional thumbnail) and informative per-type labels next to the icons, generated in the background with caching.
- [ ] Add hybrid view modes and continuous zoom: details with a thumbnail column, tiles with per-type fields and pure thumbnails; `Ctrl`+wheel adjusts font or cell size depending on the mode.
- [ ] Define window styles (panel configuration, layout and view applicable without losing the folder) with browse/filmstrip/metadata/dual-panel presets and saveable custom styles.
- [ ] Integrated metadata panel: show and edit the fields of the selected file (audio/image/PDF) with next/previous navigation and applied state; integrated viewer with zoom, fit, rotate view and slideshow without modifying the file.
- [ ] File descriptions (human comment): assign from properties/metadata panel with apply to the selection and recursion, configurable backend (hideable `descript.ion` or `xattr` with degradation) and preservation when copying according to the metadata policy.
- [ ] Standalone image viewer (separate window that lists the folder and respects EXIF) with marking (`M`/`Insert`) that accumulates into a persistent collection, thumbnail panel of marked images, jumping between them and `Shift+M` to toggle the mark.
- [ ] Folder type summary (count and size per group or extension) in the status bar information and in an interactive dialog, computed in the background with the type taxonomy.
- [ ] Status bar configurable by sections (field codes, alignment, conditional hiding) with live preview, separate definitions for single-pane/dual-view modes and interactive elements (format, lock, hidden).
- [ ] Register the fields in a single typed registry (`FieldRegistry`) as the source of truth for columns, tooltips, rename, type summary, listing and bar; stable identifiers with namespaces (`item.*`, `sel.*`, `dir.*`, `disk.*`, `win.*`) and explicit formatters — the same names feed the expression evaluator's variables (Phase 13.5).
- [ ] Status bar from section definitions resolved by the registry: hide empty/zero sections, separate counts and sizes by category (files/folders), indicator of filter-hidden items, disk chart with color threshold and detail of the last selected file when there are no columns.
- [ ] Expensive fields as lazy with cache and background (EXIF/image, audio, video, size on disk, links), enabled only when a surface requests them.

## 7.2 Reducing modal dialogs

- [ ] Replace informational confirmations with undo banners when the operation is reversible.
- [ ] Use inline banners for recoverable errors and permission problems.
- [ ] Reserve modals for destructive decisions, complex conflicts or essential input.
- [ ] Keep messages accessible long enough and allow reviewing them in an activity center.

## 7.3 Context persistence

- [ ] Persist per folder: view, zoom, visible columns, order, width and sort criterion.
- [ ] Implement the folder format as a serializable object (view, columns, order, grouping, visibility) with hierarchical sources: path/pattern, content type, folder type, favorite and default user format.
- [ ] Support automatic formats by content type (type group + percentage threshold + minimums/maximums), opt-in and explainable.
- [ ] Assign background color and image by path, pattern, folder type or content group (fit modes, opacity, fill color, inheritance to subfolders), resolved with the same hierarchy as the folder format.
- [ ] Add format lock and a provenance indicator in the status bar, with reset and management commands.
- [ ] Enrich tabs: custom name, color, duplicate, open selected folders, restore closed tab and saveable tab groups.
- [ ] Support locked tabs: pin a folder (navigating from it opens a new tab without moving the locked one), lock modes with reuse of an unlocked tab and protection against accidental closing.
- [ ] Allow dragging files onto a tab as a destination (hover activates the tab) and linking tabs between panels in dual view.
- [ ] Restore tabs or workspaces according to preference.
- [ ] Keep the selection and scroll when refreshing.
- [ ] Do not automatically jump to another folder after an operation unless explicitly requested.
- [ ] Persistent per-folder manual ordering (drag or `Shift`+`Alt`+arrows) saved with the folder format, with restoration of automatic order and an indicator when the order cannot be saved (flat view, groupings, read-only).
- [ ] Frozen columns up to a point in the details view (`Ctrl`+`Alt`+click on the header or the header menu), saved with the folder format and compatible with movable columns.

## 7.4 Empty states and helpful errors

- [ ] Design empty states for folders, results, network, bookmarks and recents.
- [ ] Explain errors with cause, effect and recommended action.
- [ ] Add contextual buttons: retry, authenticate, open permissions, show details or copy diagnostics.

---

# Phase 8 — Accessibility

- [ ] Define accessible names, descriptions and roles for custom controls.
- [ ] Ensure visible focus indicators in all themes.
- [ ] Do not convey state through color alone.
- [ ] Review contrast and minimum sizes.
- [ ] Test full navigation without a mouse.
- [ ] Test with a screen reader available on Linux, for example Orca.
- [ ] Announce the start, progress, conflict, completion and failure of operations without generating excessive noise.
- [ ] Respect reduced-motion preferences when available.
- [ ] Document shortcuts in an accessible and searchable view.

**Acceptance criteria:**

- The critical flows can be completed with a screen reader and the keyboard.
- No dialog traps the focus without a clear way out.
- Icon-only controls have an accessible name and a translated tooltip.

---

# Phase 9 — Performance, thumbnails and scalability

## 9.1 Thumbnail pipeline

- [ ] Implement a limited worker pool prioritized by visible items.
- [ ] Cancel requests when leaving a folder or changing the view.
- [ ] Add a versioned disk cache with size limits and cleanup.
- [ ] Avoid regenerating thumbnails when the file and parameters have not changed.
- [ ] Add progressive support for video, PDF and documents through secure optional backends.
- [ ] Respect privacy settings, remote drives and maximum sizes.

## 9.2 Large folders

- [ ] Load entries in batches and keep the UI interactive.
- [ ] Avoid sorting or computing expensive metadata on the main thread.
- [ ] Defer expensive columns until they are visible or requested.
- [ ] Compute folder sizes in the background (manual or automatic) with progressive updates, an approximate marker and an invalidatable cache.
- [ ] Test with 10,000, 100,000 and more entries through simulation.

## 9.3 Search and indexing

- [ ] Define CPU, memory and I/O limits.
- [ ] Pause or reduce priority when the system is under load.
- [ ] Exclude configurable paths and respect remote mounts.
- [ ] Offer indexing status and control without relying on a terminal.

---

# Phase 10 — Linux integration, networking and compatibility

- [ ] Improve X11/Wayland compatibility for drag and drop, clipboard, window activation and positioning.
- [ ] Apply the predictable drag rules (same volume moves, a different one copies; `Shift`/`Ctrl`/`Alt` force move/copy/link), an action menu on right-button drop, visual anticipation of the destination and dropping on sidebar/tabs/breadcrumbs.
- [ ] Support pasting text and images from the system clipboard as real files, and an accumulating clipboard that gathers files from several folders before pasting.
- [ ] Test XFCE, KDE Plasma, GNOME, LXQt, Fluxbox and minimal environments when possible.
- [ ] Keep XDG integration for folders, MIME, default applications, trash and portals.
- [ ] Offer "use Linux File Manager to open folders" in Preferences (`inode/directory`/`file://` registration), optional, reversible and with a notice about the previous file manager; document that it does not replace the file selectors of other applications or the desktop.
- [ ] Accept paths and `file://` URLs on the command line and activate the already-open instance instead of duplicating it; open folders quickly (immediate response when being the system file manager).
- [ ] Offer optional start with the session from Preferences (desktop autostart) and single instance with activation for those who use it as the system file manager.
- [ ] Implement SFTP behind a remote providers interface, without coupling it to the UI.
- [ ] Design credential handling through secure desktop services; do not store passwords in plain text.
- [ ] Treat remote operations with the same queue, progress, cancellation and conflicts as local ones.
- [ ] Add clear states for disconnection, reconnection and expired authentication.
- [ ] Access MTP devices (cameras, phones, tablets) as virtual folders via `gvfs`/`gio` (`mtp://`), with the same operations as a local folder (copy, delete, create folders, thumbnails).

## 10.3 Remote providers: SFTP/FTP architecture with paramiko and gvfs

Product decision (recorded): Linux File Manager will offer remote access through a **providers interface** that the UI consumes without knowing whether it navigates local or remote content. **`python3-paramiko`** (in-process SFTP, already installed) and **`gvfs`/`gio`** (multiprotocol: FTP, SMB, WebDAV, MTP — already installed) are adopted as the main pair; **`rclone`** and **`sshfs`** (already installed) remain as optional complements for cloud and for "mount and exit" from the file manager. No client is built from scratch for each protocol.

### 10.3.1 Verifying packages on the system

- `python3-paramiko` 3.5.1-1 — installed. Pure Python SFTP/SSH client, without mounts; the foundation of the in-process SFTP provider (address book, log, resumption, connection states).
- `gvfs-backends` / `gvfs-fuse` 1.57.2 — installed, with daemons `gvfsd-ftp`, `gvfsd-sftp`, `gvfsd-smb`, `gvfsd-dav`, `gvfsd-mtp`, `gvfsd-nfs`, `gvfsd-http`, `gvfsd-google`, etc. They are invoked with `gio mount`/`gio list` (and accessed via `mtp://`, `ftp://`, `sftp://`, `smb://`, `dav://`).
- `rclone` 1.60.1 — installed. `rclone mount`/`serve` for cloud (S3, Drive…) and an additional remote.
- `sshfs` 3.7.3 — installed. FUSE mounting of SFTP as a local folder (occasional use, not the foundation of the architecture).
- `davfs2` — installed (WebDAV mounted; its dialog is already documented in the README).
- Available if wanted: `lftp` (batch-transfer CLI), `curlftpfs` (classic FUSE FTP), `python3-aioftp` (asynchronous FTP client) and `ftplib` (stdlib, dependency-free FTP).

### 10.3.2 Model and planned integration

- [ ] Define a `RemoteProvider` interface (connect, list, read, write, rename, delete, create folder, status) with interchangeable backends; the UI and the operations engine work against the interface without coupling to the protocol.
- [ ] Implement `SftpProvider` with `python3-paramiko`: connection with a key or SSH agent, sites address book, activity log, transfer resumption and disconnection/reconnection/expired-authentication states.
- [ ] Implement `GvfsProvider` with `gio` for FTP/SMB/WebDAV/MTP when the paramiko provider does not apply, mounting/querying `gio` locations and delegating credential management to the desktop keyring.
- [ ] Register remote operations in the same queue with progress, cancellation and conflicts as local ones (Phase 2), with latency detection and concurrency limits.
- [ ] Add a remote sites address book (name, protocol, host, user, initial folder, authentication method) accessible from the sidebar and the location bar; do not store passwords in plain text (use `python3-secretstorage`/keyring or `paramiko` with an SSH agent).
- [ ] Indicate the remote origin in the interface (icon/location type, latency, status) and allow disconnecting without losing the selection or the history.

**Acceptance criteria:**

- Navigating, copying, moving, renaming and deleting on an SFTP site work from the same interface as local, with progress and cancellation.
- The FTP/SMB/WebDAV/MTP locations available through `gio` are accessible without manual mounts and without typing passwords into the file manager.
- Disconnection, reconnection and expired authentication show clear states and do not leave the queue in limbo.
- The sites address book persists between sessions and credentials are delegated to the keyring or the SSH agent.

### 10.3.3 The sites address book: the product model

The reference desktop file managers mostly showcase the **address book model** that makes working with many servers comfortable; that model is independent of the protocol and is what Linux File Manager should adopt on top of its providers interface. The address book is an editable catalog of sites (name, comment, protocol, host, port, user, authentication method, initial folder and per-site options) shown in the sidebar and the location bar; it serves both to connect with a single click and to use the site as the **destination of an operation** without having it open. Three product decisions shape the address book: **organization** (sites are grouped into folders, duplicated to try out variants, and each entry can carry a comment that is shown as a description when navigating it), **default-value inheritance** (a special "defaults" entry defines the global values —password policy, connection mode, network— and each site can inherit them or set its own, by sections, without duplicating configuration) and **portability with privacy** (exporting and importing the address book between machines with three modes —to a new folder, merge, or replace— and with the option to **omit the passwords when exporting**, to share site configurations with colleagues without revealing credentials).

**Adding a site is a dialog, not a technical form.** The sign-up asks for the essentials —visible name, host, protocol, user, authentication— and leaves the rest at the default values; the same dialog appears when connecting to a site that is not yet in the address book ("save as entry"), so that any manual connection can be promoted to a permanent site without retyping the data. Credentials support three policies per site, which in our case are delegated to the keyring (Phase 10.3): **ask for the password on every connection**, **use the stored one**, or **use a private key** (for SFTP, with the passphrase asked or stored). The file manager must never write passwords in plain text into its configuration; the desktop keyring is the only store.

**Implementation notes.** The address book is a serializable model (`sites.json` in the user data) independent of the backend: each entry stores protocol + connection parameters, and the `RemoteProvider` is built from it. The add/edit dialog shares its form with the ad-hoc connection and with "save as site" from an active connection. Default-value inheritance is implemented with per-section resolution (default → site), the same pattern of hierarchical sources already used by the folder format (Phase 7.3), avoiding copied values. Export/import reuses the address book format with the option to clear credentials.

- [ ] Persistent and editable remote sites address book (name, comment, protocol, host, port, user, authentication, initial folder), groupable into folders, with duplication and the comment visible as a description.
- [ ] "Defaults" entry with per-section inheritance (network, credentials, display) and default → site resolution, without duplicating configuration.
- [ ] Per-site credential policies delegated to the keyring: ask each time, use the stored one, or a private key with a passphrase; never passwords in plain text in the configuration.
- [ ] Promote any manual connection to a site of the address book ("save as entry") without retyping data; the sign-up shares its form with the ad-hoc connection.
- [ ] Export/import the address book (to a new folder, merge or replace) with the option to omit credentials when exporting.

### 10.3.4 Connecting, paths and remembering where you left off

With a mature address book, connecting has to be almost invisible. The reference desktop file managers distinguish **three connection paths** that Linux File Manager must replicate: **quick connect** (a minimal dialog with host, protocol and credentials, which remembers the last used site and offers the address book in a dropdown —useful for entering a known site with a different user), **connect by URL** (typing `sftp://usuario@host:puerto/ruta` or `ftp://...` in the location bar and entering, including anonymous connection without credentials), and **access from the address book** (a click on the sidebar navigates to the site). Added to this is an important convenience nuance: **remembering the last visited folder** —the site stores the initial directory, but if the option is enabled, disconnecting updates that field with the directory where the user left off, so that reconnecting returns the user to where they were, not to the start—. The protocol distinction of those file managers (classic FTP, explicit/implicit FTPS, SFTP) is resolved by construction in our architecture: `paramiko` covers SFTP and `gvfs`/`gio` covers the rest (including FTPS), so the connection dialog offers "SFTP (paramiko)" and "FTP/FTPS and others (gvfs)" as transport modes, not as reinventions.

**Discover without configuring.** The Network section of the sidebar already detects mounted gvfs locations; the address book adds the upper level: own sites that connect on demand (with `gio mount` for gvfs or with the paramiko session) and appear at the same level as the already mounted locations, distinguishing status (connected/available/error). Navigating inside a remote site uses the same folder interface as local; the remote origin is indicated with icon and status, as the 10.3 criteria already require.

**Implementation notes.** The quick connect dialog is a form shared with the site sign-up (10.3.3); connect by URL is resolved in the locations controller by recognizing `sftp://`, `ftp://`, `smb://`, etc. schemes and delegating to the appropriate provider. "Remember the last folder" is implemented by updating the initial-folder field of the entry on disconnection (only if the entry exists and the option is active). The per-site status (connected/disconnected/authentication error) is exposed to the sidebar and the status bar with the same status vocabulary of Phase 2.

- [ ] Quick connect remembering the last site and with an address book dropdown; connect by URL (`sftp://`, `ftp://`, etc.) from the location bar, including anonymous.
- [ ] The address book appears in the sidebar next to the mounted gvfs locations, with visible status (connected/available/error) and a remote origin icon.
- [ ] Per-site "remember the last folder" option: update the initial folder on disconnection to reconnect where the user left off.

### 10.3.5 Per-site log: monitoring what happens on the connection

Working with remote servers produces a kind of information that local operations do not need: which commands were sent, what the server replied, why an authentication failed or a connection was lost. The reference file managers keep **a log per site** in addition to a unified view of all the activity, and that separation is the key product decision: each site can enable its own logging (with a debug mode that adds diagnostic detail), the log appears in the utility panel with a selector to switch site or view the **combined activity** when there are several simultaneous connections, and it can be shown **automatically when connecting** when a particular site gives trouble. The log can be saved to a text file, the selection copied or cleared (one or all). In Linux File Manager this remote activity panel must live where the Operation Center and the extensions log are already planned (Phases 2 and 13): the remote log is one more tab with the same ergonomics, and connection errors also feed the queue states (disconnection, reconnection, expired authentication) already defined in 10.3.

**Implementation notes.** Each `RemoteProvider` emits activity events (connect, list, transfer, error, command/response in debug mode) that a log service tags per site and dumps into the panel; the log size limits and the font format are configured globally. The per-site debug mode is stored in the address book entry and only adds detail when the user asks for it.

- [ ] Per-site activity log in the utility panel (site selector + unified view of all the activity), with save to text, copy and clear (one or all).
- [ ] Per-site options: enable log, enable debug and show the log automatically when connecting; maximum size and font configurable globally.
- [ ] Connection errors in the log feed the queue states (disconnection, reconnection, expired authentication) without duplicating the Phase 2 error mechanism.

### 10.3.6 Network reliability and per-site limits

The concern of making the connection **robust and polite** is recurring in the reference file managers, and their ideas adapt with little effort to our architecture: **configurable retries** (how many times and at what interval before giving up and reporting an error), **automatic reconnection** when the connection is lost due to an outage or a server timeout, and **keeping the connection alive** by sending periodic packets when the server tends to cut off idle connections —with the caveat that many sites advise against staying connected indefinitely, so this option is per site and reasonable by default. Also relevant is the **rescan after upload**: after copying files to a server, the local view of its content can fall out of sync with reality (especially if the server does not preserve dates), so the file manager automatically refreshes the directory listing after writing. Finally, the **per-site speed limits** (upload and download separately, optionally on a schedule —e.g. unlimited at night) prevent a transfer from hogging the bandwidth; it fits with the concurrency limits already planned in Phase 2.

**What is not carried over.** The reference file managers include classic FTP protocol options that our architecture already resolves or delegates: active/passive mode and server commands (`MLST`, `MDTM`, `LIST`, `FEAT`) are handled by the client (`paramiko` for SFTP, `gio` for FTP), automatic binary/ASCII mode by extension is handled by the transport, and site-to-site transfer (without going through the local machine) is a luxury that few servers support and that is discarded in the first version. Transfer compression (zlib) neither applies to SFTP (already encrypted and compressible over SSH) nor adds value on already-compressed files.

**Implementation notes.** Retries/reconnection and "keep alive" are configured per site in the address book and implemented by the provider (paramiko exposes timeouts and keepalive; gvfs/gio manages its own retries, so our own layer is limited to states and policy). The rescan after upload is a model update after remote write operations (the same invalidation as the local watcher, Phase 9). The per-site speed limits are applied in the transfers engine (Phase 2) before enqueuing, with an optional schedule.

- [ ] Configurable per-site retries (number and interval), automatic reconnection after loss and a "keep alive" option with interval, per site and with a courtesy warning.
- [ ] Automatically refresh the remote directory listing after writing to it (rescan after upload), reusing the model invalidation.
- [ ] Per-site upload/download speed limits, optionally by schedule, integrated into the Phase 2 transfers engine.
- [ ] Explicitly discard what the transport already resolves (passive/active, server commands, ASCII/binary mode, site-to-site, transfer compression) and leave a record in the code and in this section.

## 10.1 Compression and extraction delegated to Ark and PeaZip

Product decision: extraction and compression are not executed by the file manager's internal code, but by an **external desktop archiver application** chosen by the user. Mature tools already exist on Linux for this task; reinventing them duplicates maintenance and formats. Linux File Manager will offer **Ark** (default) and **PeaZip**, both as interchangeable backends. Right-clicking a compressed file —or a selection that is to be compressed— will show a **submenu with the actions of the active tool**, and the tool can be changed from **Preferences**. The current internal actions of the program (`Extract Here`, `Extract to...`, `Compress to ZIP` and `Send to → Compress to ZIP`, based on `extractor_service.py`) are removed from the menu surfaces and replaced by this delegated submenu.

### 10.1.1 System files verified for the integration

Paths verified on the reference system (Debian, packages `ark 4:25.04.3-1` and `peazip`). The Agent must use these paths to detect availability, launch processes, resolve icons and understand the supported formats; it must not rely on internal plugin paths that only report capabilities.

**Ark (KDE)** — detect with `shutil.which("ark")` and launch by its name:

- Executable: `/usr/bin/ark` (package `ark`).
- Desktop entry and icon: `/usr/share/applications/org.kde.ark.desktop` (`Exec=ark %U`, `Icon=ark`, `MimeType=...` with the full list of formats Ark opens: `application/zip`, `application/x-7z-compressed`, `application/vnd.rar`, `application/x-tar`, `application/gzip`, `application/x-xz`, `application/x-bzip2`, `application/x-cpio`, `application/vnd.debian.binary-package`, etc.).
- Icons: `/usr/share/icons/hicolor/{48x48,64x64,128x128}/apps/ark.png` and `scalable/apps/ark.svgz`.
- Global configuration (do not edit): `/etc/xdg/arkrc` and schema `/usr/share/config.kcfg/ark.kcfg`.
- Libraries and plugins that define the supported formats (reference only, not invoked directly): `/usr/lib/x86_64-linux-gnu/libkerfuffle.so.25.04.3` and `/usr/lib/x86_64-linux-gnu/qt6/plugins/kerfuffle/*.so` (`kerfuffle_cli7z`, `kerfuffle_cliarj`, `kerfuffle_clirar`, `kerfuffle_cliunarchiver`, `kerfuffle_clizip`, `kerfuffle_libarchive`, `kerfuffle_libarchive_readonly`, `kerfuffle_libzip`).
- Dolphin/KIO menu services that show the action naming to replicate (not loaded from LFM): `/usr/lib/x86_64-linux-gnu/qt6/plugins/kf6/kfileitemaction/compressfileitemaction.so` (the "Compress" submenu with *Compress to...* and *Compress to "%1"*), `extractfileitemaction.so` (the "Extract" submenu) and `kf6/kio_dnd/extracthere.so` ("Ark Extract Here").

**Ark CLI** (according to `man ark`):

- `ark -b [opciones] <archivo...>` → batch-extracts without a GUI; if `-o` is not passed, it uses the current working directory.
- `-a, --autosubfolder` → if the content is not a single folder, it creates a subfolder with the name of the file.
- `-o, --destination <dir>` → extraction directory; if not passed, the current path is used.
- `-O, --opendestination` → opens the destination when finished.
- `-e, --autodestination` → the destination is the path of the first file.
- `-c, --add` → asks the user for the name of a file and adds the indicated files to it.
- `-t, --add-to <archivo>` → adds the indicated files to a specific file; creates it if it does not exist.
- `-f, --autofilename <sufijo>` → chooses an automatic name with the indicated suffix (e.g. `zip`).
- `-d, --dialog` → shows an options dialog before the batch operation.

Documented examples: `ark --batch archivo.tar.bz2` extracts into the current directory; `ark --add-to mi-archivo.zip foto1.jpg texto.txt` creates or updates the ZIP.

**PeaZip** — detect with `shutil.which("peazip")` (and the CLI with `shutil.which("pea")`); always launch by the executable name:

- Executables: `/usr/bin/peazip` (GUI), `/usr/bin/pea` (CLI), real binary at `/usr/lib/peazip/peazip` and `/usr/lib/peazip/pea`.
- PeaZip's own backends (capability information; not invoked): `/usr/lib/peazip/res/bin/7z/7z`, `arc/arc`, `zstd/zstd`, `zpaq/zpaq`, `brotli/brotli`, `upx/upx`, etc.
- Desktop entry: `/usr/share/applications/peazip.desktop`.
- Icons: `/usr/share/pixmaps/peazip.png`, `peazip_add.png`, `peazip_extract.png` and `/usr/share/peazip/icons/peazip*.png`.
- Menu actions reference (the most reliable source of the CLI): `/usr/share/peazip/batch/freedesktop_integration/KDE-servicemenus/KDE6-dolphin/peazip-kde6.desktop`, which defines the "PeaZip" submenu with:

| Visible action | Real command |
| --- | --- |
| Archive… (create/update archive) | `peazip -add2archive %F` |
| Add to 7Z / Add to ZIP / Add to GZIP | `peazip -add27z %F` / `-add2zip %F` / `-add2gzip %F` |
| Convert… | `peazip -add2convert %F` |
| Extract… (full dialog) | `peazip -ext2full %F` |
| Extract here | `peazip -ext2here %F` |
| Extract here to a new folder | `peazip -ext2folder %F` |
| Open with PeaZip… | `peazip -ext2browse %F` |
| Test | `peazip -ext2test %f` |

- More integration templates (GNOME/Nautilus, Cinnamon/Nemo, additional .desktop files and `.sh` scripts) in `/usr/share/peazip/batch/freedesktop_integration/`, useful as a reference for "extract to Desktop/Documents/Downloads" behaviors.

### 10.1.2 Service model and preference

- [ ] Create an `ArchiveToolService` service (or extend `lfmapp/services/`) that abstracts the active tool and exposes at least: `extract_here(archivo)`, `extract_into_new_folder(archivo)`, `extract_to(archivo, destino)`, `open_archive(archivo)`, `create_archive(archivos)`, `quick_add(archivos, formato)`, `test_archive(archivo)`.
- [ ] Implement two backends with the same interface: `ArkBackend` and `PeaZipBackend`, which build the real commands of the table above and launch them in the background without blocking the UI; `ArkBackend` must be the one selected by default.
- [ ] Add the `archive_tool` key to `core/config.py` with values `"ark"` | `"peazip"` (default `"ark"`), with automatic backfill in old configurations (same mechanism as the rest of the keys).
- [ ] In `preferences_dialog.py`, add an "Archives" section (or next to the behavior section) with a `QComboBox` selector ("Tool for compressing and extracting: Ark (recommended) | PeaZip") that saves `archive_tool`, plus an indication of whether the tool is installed (with `shutil.which`).
- [ ] Keep in `ui/icons.py` the needed icon names (`package-x-generic`, `archive-extract`, `archive-insert`…) with fallback, and try the theme's `ark`/`peazip` icon through `QIcon.fromTheme` with a safe fallback to the generic icons.

### 10.1.3 Context submenu and removal of internal actions

- [ ] Replace in the context menu (traditional and modern, `main_window.py`/`menus.py`) the current actions `Extract Here`, `Extract to...`, `Compress to ZIP`, `Send to → Compress to ZIP` and the "Archive Tools" group with a single submenu with the name of the active tool (e.g. "Ark" or "PeaZip") that offers its equivalent actions.
- [ ] On a compressed file (according to `is_archive`/MIME): the submenu shows "Extract here", "Extract into a new folder" and "Extract to…" (Ark: `-b -a` / `-b` with `-o`; PeaZip: `-ext2here` / `-ext2folder` / `-ext2full`). "Extract to…" in PeaZip uses its own dialog; in Ark the file manager can ask for the folder with the existing `FileOperations` dialog and pass `-o`.
- [ ] On any selection (files or folders): the submenu offers "Add to archive…" (Ark: `-c` or `-t`; PeaZip: `-add2archive`) and, when it makes sense, format shortcuts ("Add to ZIP" in PeaZip; `-f zip` in Ark) using the name of the selection as the base.
- [ ] Add "Open with the tool" (Ark: `ark <archivo>`; PeaZip: `peazip -ext2browse <archivo>`) and, in PeaZip, "Check integrity" (`-ext2test`).
- [ ] Remove the menu exposure of the internal compressor (`extract_here`, `extract_to`, `create_zip` and their threads) or keep it only as an internal fallback outside the UI; the visible surface must always delegate to the chosen tool. Document the change in `tests` (adapt `test_extractor_service.py`, `test_main_window.py`, `test_menus.py`).
- [ ] If the active tool is not installed, show an inline notice with the installation suggestion (`sudo apt install ark` or the PeaZip package) and a direct link to the preference; do not show an empty submenu.

**Acceptance criteria:**

- With Ark installed and `archive_tool="ark"`, extract here, extract into a new folder, extract to… and add to archive work from the right click without opening internal compression code.
- Changing the preference to `peazip`, the same submenu switches to using the `peazip -ext2…`/`-add2…` commands and opens PeaZip.
- No menu surface offers the file manager's internal compression/extraction actions anymore.
- The preferences selector reflects the installed tool and the change persists between sessions.
- Unit tests for the command construction of both backends and GUI tests of the submenu with the default tool and with the alternative.

## 10.2 Optional alternative copy/move with Ultracopier

Ultracopier is an external copy tool with **queue and advanced control** —pause/resume, speed limit, elaborate collision and error handling— that complements the native operations engine of Linux File Manager. The user asked that, in addition to the native system, Ultracopier can be used when needed for demanding copy/move tasks (for example, large volumes where pausing, limiting speed or reviewing collisions matters). The file manager's native engine **is kept** as the default option; Ultracopier is a selectable alternative path, not a replacement.

### 10.2.1 System files verified

- Executable: `/usr/bin/ultracopier` (package `ultracopier` 2.2.6.0; `dpkg -l` confirms it installed).
- Documentation: `/usr/share/man/man1/ultracopier.1.gz`; menu entry in `/usr/share/menu/ultracopier`; copyright in `/usr/share/doc/ultracopier/`.
- The package **does not install** a `.desktop` file in `/usr/share/applications/` (only the man page and the menu), so the launcher icon must be resolved with a fallback if it is to be shown.
- **Supported CLI** (according to `ultracopier --help`):
  - `ultracopier cp <origen...> <destino>` → copies the sources to the destination.
  - `ultracopier mv <origen...> <destino>` → moves the sources to the destination.
  - If `<destino>` is `?`, Ultracopier **asks the user** for the destination.
  - `ultracopier Transfer-list <archivo>` → opens a saved transfer list.
  - `ultracopier quit` → closes other running instances (useful before relaunching with new parameters if a clean session is wanted).

### 10.2.2 Planned integration

- [ ] Create an `UltracopierCopyBackend` inside a delegated copy service (e.g. extend `lfmapp/services/` with `CopyToolService` or an `external_copy.py` module) that builds `ultracopier cp|mv <rutas...> <destino>` and launches it in the background without blocking the UI.
- [ ] Add a `copy_tool` key to `core/config.py` with values `"native"` | `"ultracopier"` (default `"native"`), with automatic backfill for old configurations.
- [ ] In `preferences_dialog.py`, add the selector "Copy/move tool: native (recommended) | Ultracopier" in the same area as the archive tool preference, with availability detection (`shutil.which("ultracopier")`).
- [ ] In the context menu and in `Copy to...`/`Move to...`, when `copy_tool="ultracopier"` the operation delegates to Ultracopier; in `"native"` mode the current flow is used. Always keep an explicit "Copy with Ultracopier…" action accessible in the context submenu if the tool is installed, regardless of the preference.
- [ ] With destination `?` when the user chooses "…" (so Ultracopier asks), or pass the destination chosen by the existing `FileOperations.choose_folder` dialog when it is already known.
- [ ] Document in the UI that Ultracopier manages its own queue, pauses and speed; the file manager must not duplicate those controls when it delegates.
- [ ] Unit tests for the command-line construction (spaces in paths, several sources, `?` destination) and a manual test with real copy and move via Ultracopier on X11 and Wayland.

**Acceptance criteria:**

- With `copy_tool="ultracopier"` and the tool installed, copying and moving from the file manager launch Ultracopier with the correct items and destination.
- With `copy_tool="native"` (default) the current behavior does not change.
- The explicit "Copy with Ultracopier…" action is available and does not appear empty if the binary is missing.
- The preference persists between sessions and the change takes effect without restarting when it is safe.

---

# Phase 11 — Quality, local telemetry and diagnostics

- [ ] Add structured logging with levels and rotation.
- [ ] Create a "Copy Diagnostic Information" action that excludes paths or private data unless explicit consent is given.
- [ ] Add a diagnostics mode for signals, operations, thumbnails and search.
- [ ] Keep telemetry disabled; any metric must be local unless an explicit and transparent future decision is made.
- [ ] Add tests for configuration and database migration.
- [ ] Add failure tests: full disk, permissions, disconnection, deleted destination and file changed during the operation.
- [ ] Run static, unit, integration, GUI and packaging tests in CI.

---

# Phase 12 — Debian, distribution and release

- [ ] Review the real dependencies and separate required, recommended and optional ones (ark and peazip are recommended for delegated compression/extraction, see 10.1).
- [ ] Confirm the `qt6ct` strategy in documentation and metadata, without imposing it when the environment already manages Qt.
- [ ] Audit all icon names and fallbacks in `lfmapp/ui/icons.py`.
- [ ] Review licenses, copyright, AppStream, desktop file and manpage.
- [ ] Validate with `lintian`, clean-install tests and upgrade from a previous version.
- [ ] Add a release checklist, versioning, changelog and migration notes.
- [ ] Create CI for the Debian source and binary package in compatible environments.
- [ ] Clearly document optional features and external dependencies for previews, network or extraction.

---

# Phase 13 — Native scripting engine and expression evaluator

Product decision (recorded): Linux File Manager will include **two complementary automation capabilities**, because they answer different needs that should not be mixed into a single tool: a **scripting engine** that executes complete sequences of actions —written in native Python—, and an **expression evaluator** that computes a value or a condition within a bounded and safe domain. Scripting is for automating flows (e.g. "move everything from yesterday to a folder, rename it with a template and generate a summary"); the evaluator provides point-specific expressive power in fields where today only fixed values or simple templates fit: filter conditions, rename patterns, highlighting rules and selection criteria.

No new language is adopted nor a third-party interpreter embedded. Scripting builds on the extension discovery layer that already exists —`lfmapp/extensions/manager.py`, today limited by design to reading manifests— and adds the executable loading that its own header reserves as a later step. The evaluator is built on **`python3-simpleeval`** (available in Debian 13), which evaluates expressions with a whitelist of functions and without exposing `eval`/`exec`; **`python3-asteval`** remains as an extensible alternative if custom AST visitors are needed later, and **`python3-lupa`** (LuaJIT) is discarded for the first version: it would only be a future isolated language if Python scripting proved insufficient. Both pieces join what the roadmap already planned —the "single evaluator" that feeds filters, search, selection and renaming— instead of competing with it.

## 13.1 Native Python scripting on top of the extension manager

**Scripting, not a new language.** The user already knows Python and the project already lives in Python; inventing a custom macro syntax would force writing, documenting and debugging a new interpreter. A script is a Python module with a manifest (id, version, `api_version`, `entry_point`, capabilities) placed in the system or user extension directories, and exposes an entry point that receives a bounded context. No access is given to the UI or to internal models: the script can only invoke the public actions namespace, which in turn delegates to the services that already exist (copy/move, rename, selection, printing, open with, list/filter). This way a script cannot break the window state nor bypass the operation queue.

**Safe and visible execution.** Scripts are imported in a controlled way (validating the declared `api_version` and `capabilities` before loading anything, with a clear error if they do not match) and run in a worker thread with progress and cancellation integrated into the Phase 2 operation queue, never writing directly to the models from a foreign thread. Exceptions are caught in a dialog + log and leave the queue consistent, just like any other failed operation.

**Implementation notes:**

- Extend `lfmapp/extensions/manager.py` with an executable loader on top of the current discovery: verify `api_version`, `capabilities` and `entry_point` before importing; keep the discovery phase pure and tested (`tests/test_extension_manager.py` stays green).
- Define `lfm.actions.*` as the only public namespace, exposing thin wrappers over the real services —not over `MainWindow`— so scripts are not coupled to the UI.
- Run each script in a worker thread with progress signals, cooperative cancellation and exception handling that routes to the existing error queue (Phase 2) and to `logging`.

- [ ] Add executable loading of extensions on top of `lfmapp/extensions/manager.py` (validate `api_version`, `capabilities` and `entry_point`; reject with a clear message).
- [ ] Define `lfm.actions.*` with thin wrappers over existing services (copy/move, rename, select, print, open with, list/filter), without access to the UI or internal models.
- [ ] Run scripts in a worker thread with progress/cancellation integrated into the Phase 2 queue; errors caught in dialog + log without leaving the queue half-finished.
- [ ] Load scripts from the user and system extension directories and list them in a management surface (run, stop, view output).

## 13.2 Safe expression evaluator with `simpleeval`

**Expressions, not `eval`.** Python's `eval` is a problematic security boundary, and the file manager's domain is small and well defined: names, paths, sizes, dates, extensions, comparisons and simple arithmetic. `python3-simpleeval` parses and evaluates a single expression allowing only the registered names and functions, with node and time limits; `python3-asteval` offers an extensible AST as an alternative if custom constructs are needed. The domain evaluator registers a whitelist of functions (name/path helpers, size, dates, strings, comparisons, pattern presence) and removes any name or builtin not listed.

**A single evaluator for all surfaces.** This evaluator is the one the rest of the roadmap was already asking for: complex filter/search conditions (Phase 5.1), advanced selection (Phase 6.1), batch rename templates, highlighting rules and conditions inside scripts share the same grammar and the same whitelist, so that learning one expression works everywhere and no implementation is duplicated.

**Implementation notes:**

- Subclass `SimpleEval` with the default builtins and names removed; register the domain whitelist in a single module importable by all surfaces.
- Enforce node and evaluation-time limits (for large folders and recursive expressions) and translate syntax/semantic errors into clear user messages.
- Verify and install the base package: `python3-simpleeval` 1.0.3 is available in the Debian 13 repositories (not installed yet); `python3-asteval` 1.0.6 is available as an alternative; `python3-lupa` 2.4 stays documented as an isolated future option, not as a dependency.

- [ ] Install `python3-simpleeval` and create the domain evaluator with a whitelist of functions and node/time limits; forbid names and builtins not listed.
- [ ] Integrate the evaluator into the surfaces that already envisioned a single evaluator: filters/search (5.1), advanced selection (6.1), rename patterns, highlighting rules and script conditions.
- [ ] Test the rejection of dangerous accesses (`os`, `sys`, `__import__`, `open`, `eval`, long loops/recursion) with explicit cases in `tests/`.
- [ ] Evaluate `python3-asteval` as an alternative only if a concrete need demands a custom AST; record the decision in the code and in this roadmap.

## 13.3 Scripting: lifecycle, events, commands and extension columns

Reference desktop file managers with a scripting engine teach that the difference between a "loose script" and a product capability lies in the **lifecycle**: an extension is not only a file that runs, but a citizen with state —discovered, loaded, enabled, running or in error— that can **contribute capabilities** to the file manager instead of merely acting when asked. That is the leap Linux File Manager must take over the current `ExtensionManager` (which today only discovers and validates manifests): from "knowing that an extension exists" to "letting it exist inside the program".

**The extension as a provider of capabilities.** The valuable thing is not that a script does one thing when a button is pressed, but that it can **register new capabilities** that integrate as if they were native: commands that appear in the palette and in the menus with their metadata (stable name, label, description, icon) and receive the active tab's context; computed information columns that are added to the details view and are computed per file; and subscriptions to **navigation lifecycle events** —before and after changing folder, when the selection changes, the view mode, when a panel is activated or a window is opened/closed— with a read-only context object (previous/new paths, panel, selection). A "before" event allows reacting with the previous state intact, which is where useful automation lives (sorting differently by folder type, recording visits, preparing caches).

**Errors that do not spread and visible states.** Each phase of the lifecycle (manifest validation, module import, initialization, registration) must catch its own error and leave it associated with the extension: `ok|error` state with message and traceback, visible in the management surface, with reload without bringing down the rest. Event dispatch is multicast and isolated: an extension that fails does not prevent the others from handling the same event. Enabling is a user state stored apart from the manifest (which belongs to the author): disabling an extension unloads it or simply stops dispatching events to it, without deleting it.

**Implementation notes.** The runtime builds on the current `manager.py` discovery and adds: import of the `entry_point` (importlib) with `api_version` validation; a central event bus that bridges the existing Qt signals (folder change, selection, view mode, window open/close) to subscribers with individual `try/except`; and two registration points —commands (inserted into the app's action registry, `ActionRegistry` or equivalent, so that palette/menus/shortcuts see them) and columns (registered in the details view's column model with a per-file callback and its sort value separated from the displayed value)—. Columns are evaluated in the background or with a cache keyed by `(column, path, modification mark)` so the view is not blocked by thousands of rows.

- [ ] Add executable loading of the `entry_point` to the runtime with per-phase states (validation, import, init, registration), error + traceback per extension, reload and isolation (a broken extension does not block the rest).
- [ ] Create a navigation lifecycle event bus with before/after pairs (folder change, selection, view mode, active panel, window open/close), read-only context and isolated multicast dispatch.
- [ ] Allow extensions to register commands with metadata (stable name, label, icon) integrated into palette/menus/shortcuts, receiving the active tab and typed arguments.
- [ ] Allow extension-computed columns: a per-file callback that returns the displayed value and the sort key separately, with caching and invalidation on changes.
- [ ] Persist enable/disable as user state (separate from the manifest) and add the optional fields to the schema: `description`, `homepage`, `default_enabled`, `group`.

## 13.4 Scripting: management, installation, configuration and extension log

An extension that cannot be managed comfortably is an extension that is not used. The scripting documentation teaches that the counterpoint to power is **governance**: a management dialog that lists extensions with state, version and file; that shows on selection what each one contributes (commands, columns, events) and which actions it allows (enable, disable, view About, configure, edit, delete); and that groups visually by the declared group. Installing must be as easy as **dragging** the package onto the list, and sharing as easy as packaging the extension into a self-contained file (code + manifest + resources) that another user imports with preview, version comparison and selective choice of what to install.

**Declared configuration, not programmed.** When an extension declares options, the list flags it and the Configure button generates a form from a declarative schema (fields, types, default values), saving into preferences by `extension_id`; only if it declares its own UI does it contribute its widget. The "New extension" dialog is the adoption vector: it asks for name, description and which capabilities to implement, and **generates** the manifest and the module with the skeleton of each chosen event/command/column. The getting-started documentation is not read: it is created.

**A log that brings everything together.** Scripts and the evaluator share an output destination: a log panel tagged by `extension_id` with levels and filters by extension, level and type (load, event, expression), to which the scripts' `output()` output and the evaluator's errors are written. The engine's trust piece is being able to answer "what happened and where?" without guessing.

**Implementation notes.** The management dialog is new UI on top of the manager's registry plus runtime state; install/delete/package are manager operations with `zipfile`/`shutil` (the package is a standard zip with a known internal structure, no suffix magic). Per-extension configuration uses a store keyed by `extension_id` (QSettings with namespace) and a form generator from a JSON schema. The log reuses Python's standard logging with a handler that tags the extension; the filters are UI over the same buffer. Everything tied to JScript/ActiveX/COM and the proprietary IDE with multi-language `.ini` templates is discarded: shared modules are resolved with normal Python imports/packages, resources with the extension's own files, and dialog UI is built in Qt from code.

- [ ] Create the extension management dialog: list (name, state, version, file), detail on selection (description, contributions), enable/disable/About/configure/edit/delete actions and grouping by declared group.
- [ ] Support installing by dragging (folder or package), packaging the extension into a self-contained zip and importing with preview, version comparison and selective choice.
- [ ] Configuration by declarative schema: generated form + persistence by `extension_id`; optional custom widget hook.
- [ ] "New extension" dialog that generates `manifest.json` + `entry_point` module with skeletons according to the chosen capabilities/events (including N commands and M named columns).
- [ ] Central log panel with a tag per extension, levels and filters by extension/level/type, collecting loads, events, output and evaluator errors.

## 13.5 The evaluator by surface: where an expression decides and computes

The evaluator's value is not in the grammar, but in the **places where a short expression replaces a fixed value or a rigid condition**. That surface map is well travelled in the reference file managers with expression-based renaming and filters, and the product decision for Linux File Manager is to walk it with a single engine (`simpleeval`) and per-surface profiles: same grammar and same whitelist, but each context injects its variables and declares what it returns. The most valuable surfaces, in order: **filters and search** (a boolean expression per file decides whether it is shown, whether it takes part in a filtered operation or whether it enters the search, including whether each subfolder is descended into), **batch rename** (an expression marker inside the template computes the piece of the new name, and can "skip" a file by returning a sentinel value), **computed columns** in the folder format (a column whose per-row value comes from an expression, distinguishing the displayed value from the sort value) and **grouping** (the group key is returned by the expression instead of a fixed rule). Then come highlighting rules (the condition becomes an expression), the status bar (a custom field that re-evaluates when the path or selection changes) and per-type tooltips (computed insertion and conditional sections). The rest —context menus and actions, generated duplicate names— is deferrable without loss.

**Markup convention.** In a field that today accepts fixed text, the expression is marked with a `=` prefix (the whole field is an expression) or a marker inside the template (equivalent to the `{=...=}` used by the expression-based renamers of the reference file managers, e.g. `{{expression}}`) to insert the result in the middle of literal text. This way simple values and computation coexist in the same place, and the rename grammar and the filter grammar are the same —as the roadmap already requires.

**Security, limits and user errors.** The domain evaluator exposes only pure whitelist functions (no side effects, no network, no dialogs: that belongs to scripting), with node and time limits, and each surface defines a deterministic policy for empty values and per-file errors (a failing row does not raise a thousand warnings: in a filter it is excluded with a single notice, in a column it stays empty, in renaming the original name is kept and it is reported at the end). An editor with "live test" against the selected file or the current folder turns the syntax error into a message with a cause, not a mystery.

**Implementation notes.** A single module creates the evaluator: a `SimpleEval` subclass without implicit builtins, pure domain wrapper functions, and an adapter that normalizes the "item" (name, root, extension, path, size, dates, `is_dir`, attributes and already-indexed metadata) without exposing internal objects. The initial whitelist is grouped by domains —strings (extraction, case, padding), pattern matching with wildcards and regular expressions with capture, file paths/names over `pathlib`, filesystem facts with cache, dates, conversion/formatting, arithmetic and conditionals— and the context variables are documented per surface. Compiling the expression once and reusing the tree across all files is what makes per-row evaluation viable.

- [ ] Implement the domain evaluator with per-surface profiles: injected variables and expected return type per context (filter/search, rename, column, grouping, highlighting, status bar, tooltip), sharing grammar and whitelist.
- [ ] Integrate it into filters/search (boolean per file, with recursion decision), rename templates (expression marker and file skip), computed columns (displayed value vs. sorting) and grouping by expression.
- [ ] Define the markup convention (`=` for a whole field, marker in templates), the per-file empty/error policy and the editor with live test against the current context.
- [ ] Compile once and cache per file+expression, evaluating only what is visible or necessary; node/time limits and zero side effects in the whitelist (no network, no dialogs, no writes).
- [ ] Document the grammar and the per-surface variables alongside the rename ones, with runnable examples.

## 13.6 Documentation, acceptance criteria and staged delivery

**Example documentation.** A minimal script (manifest + `entry_point`) and the evaluator's function list must be documented with real runnable examples, because this capability only has value if the user can start without reading the source code. The expression grammar is documented alongside the rename one, since they share a language.

**Acceptance criteria:**

- A script placed in the user extension directory appears listed and can be run from the UI using only `lfm.actions.*`, with progress and cancellation.
- The evaluator resolves domain conditions and values without `eval`/`exec` and without system access beyond what is allowed; an escape attempt produces a controlled error recorded in the log.
- Batch rename, filters and highlighting rules use the same expression grammar without duplicating implementation.
- Extension loading and the evaluator do not break startup or existing tests; invalid manifests or incompatible versions are rejected with a clear message.
- An extension that fails to load or to handle an event stays in a visible error state with its traceback and does not block the others or navigation.
- A command, a column or an event registered by an extension appear at the usual integration points (palette/menus, details columns) without manual steps.
- The evaluator's expressions can only use the domain whitelist; the per-file empty/error policy is honored without warning spam or view breakage.

**Staged delivery (value ladder):** the first iteration prioritizes trust and adoption over the complete surface: (1) context API + intents (`ctx`, `Item`, `salida`/actions, visible log) and loading state with clear errors; (2) enable/disable with persistence and a minimal management dialog; (3) "New extension" generator and modal dialog helpers; (4) script-based renaming with custom fields as a transformation mode of batch rename; (5) extension-registered commands with typed arguments in the actions system; then (6) navigation lifecycle events, computed columns with cache and the evaluator integrated per surface, and finally (7) packaging/import, schema-based configuration and log with filters. Each step is useful on its own and does not require the following ones.

---

# Prioritized backlog

These tasks must be tackled first because they unlock the rest of the roadmap.

## Priority P0 — Foundations

- [ ] Create the actions and flows audit (`docs/ux-flow-audit.md`).
- [ ] Implement `ActionRegistry` and migrate at least navigation, clipboard, rename and delete.
- [ ] Extract `NavigationController`, `SelectionController` and `FileActionController` from `MainWindow`.
- [ ] Audit Quick Access, bookmarks/favorites, aliases and recents to integrate them with the command palette and the path bar.
- [ ] Audit the utility panel architecture and the display of search results as virtual collections.
- [ ] Define the operation engine's contract and states.
- [ ] Add GUI tests for copy/move and selection preservation.

## Priority P1 — Highest user impact

- [ ] Integrate Ark and PeaZip as the delegated compression/extraction tool (context submenu, `archive_tool` preference, removal of internal actions — Phase 10.1).
- [ ] Integrate Ultracopier as an optional alternative copy/move alongside the native engine (`copy_tool` preference, "Copy with Ultracopier…" action — Phase 10.2).
- [ ] Non-modal Operation Center with cancel and retry.
- [ ] Conflict dialog with `Replace`, `Skip`, `Keep Both`, `Rename` and "Apply to all".
- [ ] Command palette and consistent shortcut map.
- [ ] Progressive search with visible filters and cancellation of stale queries.
- [ ] Bulk rename with preview and validation.

## Priority P2 — Competitive refinement

- [ ] Per-folder visual persistence (folder format saved and automatic by content).
- [ ] Flat View with mixed, files-only and grouped modes, and rules for copying nested files.
- [ ] Expandable folders in the list itself (inline tree with expansion control and `Alt`+`↓`/`Alt`+`↑`), with automatic opening of the folder being dragged over and optional hiding of the controls.
- [ ] Two-phase folder synchronization (compare → review → apply) in the utility panel.
- [ ] Duplicate finder with scalable comparison (name → size → hash) and a wizard to choose what to keep.
- [ ] Automatic highlighting by rules (color, font, icon or pinning) on the paint delegate.
- [ ] Advanced selection and batch action bar.
- [ ] Audit of modals and replacement with banners/undo.
- [ ] Full accessibility by keyboard and screen reader.
- [ ] Thumbnail cache on disk and viewport-based prioritization.

## Priority P3 — Expansion

- [ ] SFTP and remote providers.
- [ ] Optional integrated terminal, decoupled from the external terminal.
- [ ] Video/PDF/document previews with optional backends.
- [ ] Quick image viewer (Quick Show) invocable with the space bar, reusing the preview pipeline.
- [ ] Standalone image viewer with selection marking in collections (M/Insert, marked panel, mark swapping).
- [ ] Export the folder listing to printer, file or clipboard (text, TSV, CSV) with optional subfolders and filter.
- [ ] Folder type summary (count/size by group or extension) in the status bar and in an interactive dialog.
- [ ] Create symbolic links (absolute/relative) and hard links as variants of copy/move and from the drop menu.
- [ ] Split and join files by part size (with reordering and checksum on the join).
- [ ] Configurable event sounds (operations, errors, completion) if decided.
- [ ] Workspaces and advanced saved searches.

---

# Definition of Done for each initiative

An initiative must not be marked as completed until all of the following are met:

- [ ] Code split according to clear responsibilities.
- [ ] Visible texts translatable.
- [ ] Coherent shortcuts, menu, toolbar, context and palette when applicable.
- [ ] Unit tests for logic and GUI tests for the main flow.
- [ ] Manual test documented on at least X11 and Wayland when the feature depends on the compositor.
- [ ] Error handling and cancellation defined.
- [ ] No perceptible blocking of the main thread.
- [ ] Migratable configuration and safe defaults.
- [ ] Documentation updated.
- [ ] No regressions in the existing tests.

# Known risks and constraints

- Persisted configuration can hide recent changes if no proper migration exists; stop relying on manually deleting the data directory as the usual workaround.
- Desktop environments, icon themes, window managers and terminals produce different behaviors.
- Wayland restricts some capabilities historically available on X11; use the appropriate APIs and portals.
- Pausing or resuming certain operations may not be atomic; the UI must represent the limitations honestly.
- Undoing remote operations, overwrites or permanent deletions may be impossible; never promise nonexistent reversibility.
- Automatic checksums on conflicts can be costly; offer them selectively or deferred.
- An overly fragmented architecture also harms maintenance; extract modules by cohesion, not only to reduce line counts.

# Documentation status

- `README.md` contains information about configuration and data reset.
- `ROADMAP.md` is the main source of strategic direction, priorities and acceptance criteria.
- Important architectural decisions must be recorded in `docs/adr/` through brief ADRs.

# Instruction for the next session or agent

Read in this order:

1. `ROADMAP.md`
2. `README.md`
3. `docs/ux-flow-audit.md`, when it exists
4. Relevant ADRs in `docs/adr/`

Then review:

1. `lfmapp/ui/main_window.py`
2. `lfmapp/ui/workspace.py`
3. `lfmapp/services/file_operations.py`
4. `lfmapp/services/operation_queue.py`
5. `lfmapp/services/operation_history.py`
6. `lfmapp/services/search_service.py`
7. `lfmapp/models/file_system_model.py`
8. the related tests

The first agent must start with Phase 0 and Phase 1. It must not try to implement advanced search, SFTP and bulk rename simultaneously before stabilizing actions, controllers and operations.

# Inspiration status and next step

## Inspiration gathered (concluded)

The "Key Inspiration" section of this document gathers, in thematic subsections with a homogeneous format (adapted prose, bullets, implementation notes and closing bullets), the productivity ideas studied in reference desktop file managers. Each subsection translates the interaction logic into the Python + PyQt6 context and the project's architecture and can be consulted when working on its associated phase. The extraction is **concluded**: there is no remaining material left to study; the sources consulted are cited in the "Sources of Inspiration" section to give the corresponding credit and link their public documentation. A second, code-level reference — the Thunar sources pinned under `third-party/thunar/` — is documented in the section below; those ideas are still open for study.

## Next step: implement

The next agent must **implement**, not extract more inspiration. The prioritized work is in this document's phases and in the prioritized backlog. Order recommendation:

1. Review "What to review first after formatting" and the "Minimum recommended tests when resuming" (run `python3 -m pytest -q`).
2. Start with Phase 0 and Phase 1 (baseline, metrics and modular architecture) if they are not yet stable; then follow the phase order and the P0 → P3 backlog order.
3. Do not try to implement advanced search, SFTP and bulk rename simultaneously before stabilizing actions, controllers and operations.

Each implementation must respect the golden rule: first check in `lfmapp/` and in `tests/` that the capability does not already exist, so it is not developed twice, and keep the defined architecture (controllers in `lfmapp/controllers/`, action registry in `lfmapp/actions/`, services in `lfmapp/services/`, UI mixins by concern in `lfmapp/ui/`).

# Thunar as a study reference (`third-party/thunar` submodule)

Linux File Manager pins the sources of **Thunar** —a mature GTK/GIO file manager— as a git submodule under `third-party/thunar/` (clone instructions in the README, "Reference sources: the Thunar git submodule"). **All source paths below are relative to `third-party/thunar/`.** Use it the same way the icon-theme study used it: read the interaction logic there and **re-express it in Python + PyQt6 for this project; never copy code or text** (Thunar is GPL-2+; this project is GPL-3.0-or-later). Ideas are ordered by real value for Linux File Manager and cross-referenced with the phases below so nothing already planned is re-developed from scratch.

**1. Single instance + D-Bus `org.freedesktop.FileManager1` (highest value).**
- Sources: `thunar/thunar-dbus-service.c` and the `*.service.in` files at the repository root of the submodule.
- What to learn: Thunar activates over D-Bus — if an instance is already running, a second invocation (from the system, a browser, or the terminal) hands it the path and that instance opens the tab. This is exactly what a manager needs to *be the manager the system opens folders with*, which this roadmap already requires (the "single instance with activation" implementation note in the "Being the manager the system opens for folders" area, and the optional `python3-dbus.mainloop.pyqt6` dependency of Phase 10).
- Status in Linux File Manager: nothing exists in code yet; it is the natural next step and fits the architecture (activate over D-Bus and reuse the window through the action registry).

**2. Understand what "gvfs" is in Thunar — and adopt its model (high conceptual value).**
- Sources: `thunar/thunar-file.c`, `thunar/thunar-folder.c`.
- What to learn: Thunar does **not** call "gvfs" directly. It uses the GIO layer: everything is a `GFile` (a URI), and gvfs is only the backend that makes `trash://`, `network://`, `recent://`, `computer://` and `sftp://` work at runtime. That is why it handles a local folder, the trash, or an SMB server without mounting, all through the same code. Studying these files shows how each scheme is treated uniformly (icon, actions, drag, size).
- Idea for Linux File Manager: introduce a "location = URI/scheme" layer for the virtual system folders (trash, recent, computer, network — already in this roadmap) instead of today's 100 % `pathlib` model. It is an architectural change, so it comes after item 1, but it unlocks the rest.

**3. Volume monitor and safe unmount (USB/network sidebar).**
- Sources: `thunar/thunar-device-monitor.c`, `thunar/thunar-device.c`.
- What to learn: `GVolumeMonitor` emits `volume/mount added/removed/changed` and `pre_unmount`: the sidebar reacts when a USB drive is plugged in, allows mount/unmount/eject, and warns if transfers are active before unmounting (which ties into the operation queue).
- Status in Linux File Manager: the sidebar already has `network_service`, but the live-volumes layer is missing. Fits Phase 10 and the Linux-integration backlog.

**4. Per-volume trash (not only the home one).**
- Sources: `thunar/thunar-io-jobs.c` (it calls `g_file_trash`) and `thunar/thunar-file.c`.
- Status in Linux File Manager: `lfmapp/services/trash_service.py` implements the freedesktop spec only for the home trash. Thunar delegates to GIO, which manages `trash://` per volume (USB → `.Trash-$uid` when the filesystem allows it) and marks when the trash "does not apply". This closes the gap this roadmap already names ("make clear when the trash does not apply — network drives, removable media"). It is a contained refinement of the existing service.

**5. Interoperable thumbnails: shared cache and `Thumbnailer1`.**
- Sources: `thunar/thunar-thumbnail-cache.c`, `thunar/thunar-thumbnailer.c` (they use the `org.freedesktop.thumbnails` spec: the common cache in `~/.cache/thumbnails/{normal,large}` keyed by hash and, when tumbler is present, delegate over D-Bus).
- Idea for Linux File Manager: Phase 9.1 defines its own pipeline; if Linux File Manager reads/writes the **same cache as Thunar and Nautilus**, thumbnails they already generated are reused and vice versa (no duplicate generation). Low risk, high payoff.

**6. Progressive loading of large folders.**
- Source: `thunar/thunar-io-scan-directory.c`.
- What to learn: it does a fast scan and then populates incrementally (first rows in milliseconds). This is the direct answer to the Phase 0.2 finding — a 10,000-entry folder takes 8–12 s to fully populate with `QFileSystemModel`. Fits Phase 9.2 and its ≤ 8 s budget.

**7. Lower priority (but worth noting).**
- Operation/event notifications: `thunar/thunar-notify.c` (libnotify) → connects to the Operation Center.
- New document from `~/Templates` (XFCE "Create Document") — a small, very used feature.
- Clipboard with persistent cut/copy semantics: `thunar/thunar-clipboard-manager.c` — this roadmap already covers a content-aware clipboard.
- Default-application chooser: `thunar/thunar-chooser-dialog.c` (mimeapps) for "Open with…".
- Column/context-menu order editors: the `*order-editor.c` files — already planned by Phases 1.2.3 and 7.

**Recommended order (opinion):** (1) D-Bus `FileManager1` + single instance — closes the "the system opens Linux File Manager" goal and is self-contained and testable, with no new dependency if `python3-dbus.mainloop.pyqt6` is used; then (2) the URI/virtual-folders model + the volume monitor (Thunar's gvfs foundation); then (3) per-volume trash; and in parallel (4) the shared thumbnail cache, as a quick win.

# Sources of Inspiration

This project is an original implementation in Python + PyQt6 for Linux. The interaction and productivity ideas gathered in the "Key Inspiration" section and in the phases were studied and adapted from the public documentation of the following file managers, whose work is appreciated. It is recommended to consult their sites and documentation to go deeper into each concept:


1. **Directory Opus**
   - [https://www.gpsoft.com.au/](https://www.gpsoft.com.au/)
   - [https://docs.dopus.com/doku.php](https://docs.dopus.com/doku.php)
2. **Deepin Linux File Manager**
   - [https://github.com/linuxdeepin/dde-file-manager](https://github.com/linuxdeepin/dde-file-manager)
3. **Dolphin File Manager**
   - [https://github.com/kde/dolphin](https://github.com/kde/dolphin)
   - [https://userbase.kde.org/Dolphin/File_Management](https://userbase.kde.org/Dolphin/File_Management)
   - [https://wiki.archlinux.org/title/Dolphin](https://wiki.archlinux.org/title/Dolphin)
4. **Thunar File Manager**
   - [https://github.com/xfce-mirror/thunar](https://github.com/xfce-mirror/thunar)
   - [https://docs.xfce.org/xfce/thunar/4.20/the-file-manager-window#customizing_the_appearance](https://docs.xfce.org/xfce/thunar/4.20/the-file-manager-window#customizing_the_appearance)
5. **Nemo File Manager**
   - [https://github.com/linuxmint/nemo](https://github.com/linuxmint/nemo)
6. **Caja File Manager**
   - [https://github.com/mate-desktop/caja](https://github.com/mate-desktop/caja)

