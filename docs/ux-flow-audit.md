# Auditoría de flujos UX — Linux File Manager

**Fecha:** 2026-09-02 · **Método:** revisión estática del código en el árbol de trabajo actual (commit `0ff550a` + cambios sin commitear, incluido el WIP de la Fase 1.2 en `lfmapp/actions/`).
**Alcance:** `lfmapp/ui/main_window.py` (3783 líneas), `lfmapp/ui/workspace.py`, `lfmapp/ui/menus.py`, `lfmapp/ui/sidebar.py`, `lfmapp/ui/preview_panel.py`, diálogos en `lfmapp/ui/`, servicios en `lfmapp/services/`, `lfmapp/models/file_system_model.py`.

**Convenciones.** Cada acción principal recibe un **identificador lógico único**. Cuando la acción ya existe en el catálogo WIP `lfmapp/actions/catalog.py` (Fase 1.2) se usa exactamente ese id (`nav.back`, `clip.copy`, `sel.all`, `file.rename`, `view.mode.icons`, …); el resto son propuestas de esta auditoría. Superficies: **Menú** (barra de menús), **Toolbar** (toolbar de navegación y toolbar contextual por tipo), **Contexto** (clic derecho; A=archivo, C=carpeta, F=fondo), **Atajo**, **Paleta** (paleta de comandos). La barra lateral actúa como superficie adicional (no entra en la matriz). Handlers = métodos de `MainWindow` salvo indicación.

## 1. Acciones principales por flujo

**Navegación** — motor: `go_to()` (L1509) aplica ruta + vista recordada por carpeta + historial por pestaña (`_tabs[]`, L1411-1473); `go_back/go_forward/go_up/go_home` (L1564-1582); estado atrás/adelante en `update_navigation_actions` (L1496).
- `nav.back` — Menú Go, toolbar, paleta · `Alt+Left` · `go_back`.
- `nav.forward` — Menú Go, toolbar, paleta · `Alt+Right` · `go_forward`.
- `nav.up` — Menú Go, toolbar, paleta · `Alt+Up`; además `Backspace` (`keyPressEvent` L3748-3763) · `go_up`.
- `nav.home` — Menú Go, toolbar, paleta · `Alt+Home` · `go_home`.
- `nav.goto_path` — solo paleta («Go to Path…», anuncia `Ctrl+L`) + barra de ruta con botón Go (L1285). Sin ítem en la barra de menús. El atajo real `Ctrl+L` enfoca la barra de ruta (`setup_shortcuts` L1401), no abre el diálogo → inconsistencia T4.
- `nav.open_recent` — Menú File › Recent Files (dinámico, L1094-1126) y paleta «Open Recent File…» · sin atajo · `show_recent_file_dialog`/`open_recent_file`.
- `nav.refresh` — Menú View, contexto F, paleta · `F5` · `refresh_view` (L3520).
- `nav.open_terminal` — contexto A/C/F y paleta (Selection/Navigation) · sin atajo · `open_terminal_in_directory`/`open_current_directory_in_terminal` (L3765-3783). No está en menú principal ni toolbar.
- Destinos rápidos (Home, XDG, fijos, frecuentes, recientes): superficie **sidebar** (tabs Quick Access / This Computer / Bookmarks / Recent) y espejo en paleta (`_navigation_palette_commands` L877-953, `command_id=quick_access::ruta`). No hay ítems de menú.

**Selección** — `ExtendedSelection` en las tres vistas; en Details solo cuenta la columna 0 (`selected_paths`, workspace L575-589). `sel.all` `select_all` (L3528), `sel.none` `deselect_all` (L3531), `sel.invert` `invert_selection` (L3535). Menú Edit con `Ctrl+A`, `Ctrl+Shift+A`, `Ctrl+Shift+I`; todos en paleta. No existen en toolbar ni en contexto F (falta Select All en menú de fondo → T8).

**Copiar / mover / pegar** — motor: portapapeles **interno** `_clipboard_paths/_clipboard_mode` (L123-124) + `CopyWorker`/`MoveWorker` (`worker_threads.py`, copia con `shutil`, mover = copia+borrado) encolados en `BackgroundOperationQueue(max_concurrent=1)` con diálogo de progreso (L2743-2783, L2703).
- `clip.copy` `copy_selected` (L2238) · `clip.cut` `cut_selected` (L2246) · `clip.paste` `paste_from_clipboard` (L2254) — Menú Edit (`Ctrl+C/X/V` vía `QKeySequence.StandardKey`), contexto A/C (strip compacto; en modo tradicional solo F para Paste), paleta. **No usan el portapapeles del SO** → T1. Edit › Paste siempre habilitado (no hace nada sin clipboard) mientras paleta/contexto lo condicionan → T11.
- `clip.copy_path` `copy_path` (L2324) — Edit, contexto A/C, paleta · `Ctrl+Shift+C` (sí usa `QApplication.clipboard`).
- `file.copy_to`/`file.move_to` (L2957/2990) — solo contexto A/C y paleta; además de `move_copy_menu_show_bookmarks`, dependen de que `context_menu_selection_entries` incluya `copy_to`/`move_to`, claves **ausentes de los valores por defecto** (config.py L80-95) → ocultas en contexto y deshabilitadas en paleta por defecto → T18. Destino con `QFileDialog` (`FileOperations.choose_folder`).
- Sin diálogo de conflicto: los workers sobrescriben/fusionan destinos en silencio → T10.

**Eliminar / papelera** — motor: `TrashWorker` + `trash_service.py` (envío con `.trashinfo`, conteo), `DeleteWorker` para borrado permanente; operaciones registradas en `OperationHistory`.
- `file.trash` `trash_selected` (L2557) — solo contexto A/C, atajo `Delete` (`QShortcut`, L1395), paleta. **Ausente de menú principal y toolbar** → T2.
- `file.delete` `delete_selected` (L2923) — contexto A/C, atajo `Shift+Delete`, paleta; confirmación `QMessageBox.question`.
- `trash.empty` `on_empty_trash` (L3561) — solo Menú Tools (y paleta vía registro). **No hay navegación a la papelera ni restaurar**: la entrada Trash del sidebar navega a la carpeta cruda `~/.local/share/Trash/files` (sidebar L317-324) y `list_trash`/`restore_from_trash` están importados en `main_window` (L65-66) pero sin uso en UI → T9.

**Renombrar** — `file.rename`: **dos implementaciones**. `F2` → `rename_selected` (L2401, edición inline en la vista, registra `RenameOperation` vía `fileRenamed`); contexto y paleta → `rename_selected_dialog` (L2410, `QInputDialog`). La paleta anuncia `F2` pero ejecuta el diálogo → T3. Menú principal/toolbar: no existe.

**Buscar / filtrar** — motor: `SearchThread`/`SearchFilters` (`search_service.py`) no recursivo sobre la carpeta actual, **o** `TextIndexService` (índice previo) cuando `text_index_enabled` y no hay filtros (L3274-3297).
- Entrada: campo de búsqueda de la barra de ruta + botón Search (`on_search_requested`) + botón Filters… (`on_search_filters_requested` → `SearchFilterDialog` modal). Atajo `Ctrl+E` enfoca el campo (L1403), sin anuncio en menú/paleta.
- Resultados: se dibujan **en el panel de vista previa** (`preview.show_search_results`, L3287/3293; `preview_panel.py` L201-244); abrir un resultado usa `QDesktopServices.openUrl` (no registra recientes ni revela en carpeta). Búsqueda por etiqueta reutiliza ese mismo panel (L3612). Sin superficie propia → T12.

**Previsualizar** — motor: `PreviewWorker` (QThread; imagen, galería de carpeta, texto, fotograma de vídeo, PDF/docx/odt/rtf, metadatos) alimentando `PreviewPanel`.
- `prev.toggle` `toggle_preview` (L3395) — toolbar «Preview» (checkable), Menú View «Toggle Preview Panel», contexto F «Toggle preview panel», paleta. Tres títulos distintos para el mismo toggle (además «Preview» del toolbar contextual es otra acción, `preview_selected`) → T13.
- `prev.show` `preview_selected` (L488) — toolbar contextual (image/audio/video/document) y paleta (categoría «Context Toolbar»). Auto-preview al cambiar selección (`on_selection_changed` L1633).

**Abrir / compartir** — motor: `open_with.py` (`xdg-open`/`gtk-launch`), `get_available_applications`; comprimir = `CompressThread` (`extractor_service.py`), extraer = `ExtractThread`.
- `file.open` `open_selected`/`open_file` (L1999/2038) — contexto A/C, doble clic, `Enter` (L3754), toolbar contextual, paleta. **Sin ítem en la barra de menús ni toolbar principal.**
- `file.open_with` (L2066), `file.set_default` (L2113) — contexto A, toolbar contextual, paleta; entrada por `QInputDialog.getItem`.
- `file.print` (L2008) — Menú File/Share y contexto A/C **incondicionales**, toolbar contextual (documentos); la entrada de paleta está gated por `selection/print` (no presente en defaults) → deshabilitada en la paleta por defecto → T18. Usa `QPrintDialog`.
- `file.send_to` — `send_selected_to_desktop` (L3084, copia al Escritorio XDG) y `send_selected_to_email` (L3143, `xdg-email`) — Menú Share dinámico, contexto › Send to, botón Share del strip compacto, paleta.
- `file.compress` (L3203-3226) — File/Share, contexto A/C, toolbar contextual, paleta; nombre por `QInputDialog` (sin diálogo de destino).
- `file.extract_here`/`file.extract_to` (L3169-3188) — contexto y toolbar contextual solo para archivos comprimidos, paleta (Selection).
- `file.properties` (L2152-2168) — toolbar principal, toolbar contextual, contexto A/C/F, paleta. Tres handlers equivalentes (`show_properties` exige selección; el botón de toolbar siempre habilitado cae a la carpeta actual → inconsistencia menor con la paleta).
- `file.advanced_security` (L2170) — contexto A/C, Share, toolbar contextual · diálogo `AdvancedSecurityDialog`.
- `file.quick_access_pin` (L2176-2234) — toolbar, toolbar contextual, contexto C, paleta. Tres rutas de código solapadas (`add_bookmark`, `toggle_quick_access_pin`) → T14.
- `file.tag_add` (L3628), `file.tag_remove` (contexto), `file.tag_manage` (L3588), `file.tag_search` (L3592) — Tools y/o contexto A › Tags; gestión y búsqueda son diálogos modales; resultados de búsqueda en el panel de vista previa.

**Pestañas** — `tab.new` `new_tab` (L1411, `Ctrl+T`), `tab.close` (L1429, `Ctrl+W`; cerrar la última cierra la ventana), `tab.next`/`tab.prev` (L1451-1459, `Ctrl+Tab`/`Ctrl+Shift+Tab`): Menú File + paleta + barra de pestañas. Sin atajos en toolbar ni contexto.

**Vista** — `view.mode.icons/list/details/compact` (L3431, `Ctrl+1..4`), `view.grid_size` (L3445), `view.sort`/`view.group` (L3454/3471), `view.hidden` (`Ctrl+H`), `view.extensions`, `view.checkboxes`, `view.sidebar`, `view.font` (`Ctrl++`/`Ctrl+-`/`Ctrl+0`), persistencia de vista por carpeta (L3488-3518). Superficies: Menú View (+ contexto F para hidden/extensions/grid/sort/group/refresh/preview), toolbar para sidebar/preview, paleta. Detalles y problemas en §3.

## 2. Matriz de superficies

Leyenda: ✓ = disponible; A/C/F = contexto según tipo de elemento; `(ctx)` = toolbar contextual por tipo de selección; `strip` = barra de iconos del menú contextual moderno (`modern_context_menu_enabled`); — = no expuesta. Los atajos son las cadenas reales registradas.

| Acción (id) | Menú | Toolbar | Contexto | Atajo | Paleta |
|---|---|---|---|---|---|
| nav.back | ✓ Go | ✓ | — | Alt+Left | ✓ |
| nav.forward | ✓ Go | ✓ | — | Alt+Right | ✓ |
| nav.up | ✓ Go | ✓ | — | Alt+Up · Backspace | ✓ |
| nav.home | ✓ Go | ✓ | — | Alt+Home | ✓ |
| nav.goto_path | — | — | — | Ctrl+L¹ | ✓ |
| nav.open_recent | ✓ File | — | — | — | ✓ |
| nav.refresh | ✓ View | — | ✓ F | F5 | ✓ |
| nav.open_terminal | — | — | ✓ A/C/F | — | ✓ |
| sel.all | ✓ Edit | — | — | Ctrl+A | ✓ |
| sel.none | ✓ Edit | — | — | Ctrl+Shift+A | ✓ |
| sel.invert | ✓ Edit | — | — | Ctrl+Shift+I² | ✓ |
| clip.copy | ✓ Edit | — | ✓ A/C | Ctrl+C | ✓ |
| clip.cut | ✓ Edit | — | ✓ A/C | Ctrl+X | ✓ |
| clip.paste | ✓ Edit | — | ✓ strip; F (tradicional) | Ctrl+V | ✓³ |
| clip.copy_path | ✓ Edit | — | ✓ A/C | Ctrl+Shift+C | ✓ |
| file.copy_to | — | — | ✓ A/C (oculto por defecto) | — | ✓ (deshabilitada por defecto) |
| file.move_to | — | — | ✓ A/C (oculto por defecto) | — | ✓ (deshabilitada por defecto) |
| file.rename | — | — | ✓ A/C | F2⁴ | ✓ |
| file.trash | — | — | ✓ A/C | Delete⁵ | ✓ |
| file.delete | — | — | ✓ A/C | Shift+Delete⁵ | ✓ |
| file.new_folder | ✓ File | — | ✓ C/F | Ctrl+Shift+N | ✓ |
| file.new_file | ✓ File | — | ✓ C/F | Ctrl+N | ✓ |
| file.new_multiple | ✓ File | — | ✓ C/F | — | ✓ |
| file.open | — | (ctx) | ✓ A/C (+doble clic, Enter) | — | ✓ |
| file.open_with | — | (ctx) | ✓ A | — | ✓ |
| file.set_default | — | (ctx) documento/archivo | ✓ A | — | ✓ |
| file.print | ✓ File/Share | (ctx) documento | ✓ A/C | — | ✓ (deshabilitada por defecto) |
| file.send_to_desktop | ✓ Share | — | ✓ A/C | — | ✓ |
| file.send_to_email | ✓ Share | — | ✓ A/C | — | ✓ |
| file.compress | ✓ File/Share | (ctx) | ✓ A/C | — | ✓ |
| file.extract_here | — | (ctx) comprimido | ✓ archivo comprimido | — | ✓ |
| file.extract_to | — | (ctx) comprimido | ✓ archivo comprimido | — | ✓ |
| file.properties | — | ✓ y (ctx) | ✓ A/C/F | — | ✓ |
| file.advanced_security | ✓ Share | (ctx) | ✓ A/C | — | ✓ |
| file.quick_access_pin | ✓ Tools⁶ | ✓ y (ctx) | ✓ C | — | ✓ |
| file.tag_add/remove | ✓ Tools | — | ✓ A | — | ✓ |
| file.tag_manage | ✓ Tools | — | — | — | ✓ |
| file.tag_search | ✓ Tools | — | — | — | ✓ |
| trash.empty | ✓ Tools | — | — | — | ✓ |
| hist.undo | ✓ Edit | — | — | Ctrl+Z | ✓ |
| hist.redo | ✓ Edit | — | — | Ctrl+Y | ✓ |
| tab.new | ✓ File | — | — | Ctrl+T | ✓ |
| tab.close | ✓ File | — | — | Ctrl+W | ✓ |
| tab.next / tab.prev | ✓ File | — | — | Ctrl+Tab / Ctrl+Shift+Tab | ✓ |
| prev.toggle | ✓ View | ✓ | ✓ F | — | ✓ |
| prev.show | — | (ctx) | — | — | ✓ |
| view.mode.icons | ✓ View | — | — | Ctrl+1 | ✓ |
| view.mode.list | ✓ View | — | — | Ctrl+2 | ✓ |
| view.mode.details | ✓ View | — | — | Ctrl+3 | ✓ |
| view.mode.compact | ✓ View | — | — | Ctrl+4 | ✓ |
| view.grid_size | ✓ View | — | ✓ F | — | ✓ |
| view.sort | ✓ View | — | ✓ F | — | ✓ |
| view.group | ✓ View | — | ✓ F | — | ✓ |
| view.hidden | ✓ View | — | ✓ F | Ctrl+H | ✓ |
| view.extensions | ✓ View | — | ✓ F | — | ✓ |
| view.checkboxes | ✓ View | — | — | — | ✓ |
| view.sidebar | ✓ View | ✓ | — | — | ✓ |
| view.font | ✓ View | — | — | Ctrl++/Ctrl+-/Ctrl+0 | ✓ |

¹ `Ctrl+L` enfoca la barra de ruta; la paleta anuncia «Go to Path… (Ctrl+L)». ² Registrado dos veces (QAction de menú + `QShortcut`). ³ Solo aparece en la paleta si el portapapeles interno no está vacío. ⁴ F2 = edición inline; contexto/paleta abren diálogo. ⁵ Atajos por `QShortcut`; las entradas de paleta no muestran Delete/Shift+Delete. ⁶ Tools › «Add Current Folder to Bookmarks» siempre usa la carpeta actual, distinto del pin de la toolbar/selección.

## 3. Diferencias entre modos de vista (verificado en `workspace.py`)

Hay **tres widgets** en el `QStackedWidget` (L93-147): `icon_view`, `list_view`, `details_view`; **Compact no es una vista propia**: `set_view_mode` (L483-508) reutiliza `icon_view` en `IconMode` con iconos/grid pequeños (32 px base × `compact_view_zoom_percent`). `_get_current_view` (L474-481) solo distingue DETAILS/LIST, el resto cae en `icon_view`.
- **Details** (`QTreeView`): columnas del modelo `FileSystemModel.COLUMN_KEYS` (16 claves, L33-50); visibles por defecto name/size/type/modified, configurables por carpeta (ancho/orden/visibilidad persistidos en `list_columns_by_folder`, L240-283). Ordenación visible con indicador en el header; clic derecho en el header abre el diálogo modal «List Columns» (L328-406). Iconos 22 px.
- **List** (`QListView ListMode`): una columna, filas con icono 48 px base escalado por `list_view_zoom_percent` (L543-546); sin columnas de tamaño/fecha; `uniformItemSizes`.
- **Icons** (`QListView IconMode`): cuadrícula con tamaños SMALL 48 / MEDIUM 64 / LARGE 96 px y `wordWrap`; miniaturas de imagen vía modelo.
- **Compact**: misma cuadrícula que Icons con iconos ≈32 px; zoom propio `compact_view_zoom_percent`.
- Comunes a las cuatro: mismo `FileSystemModel` (raíz, ordenación `model.sort`, drag&drop, edición inline por `EditKeyPressed`, menú contextual reenviado), casillas de selección y ocultación de extensiones (columna 0 del modelo, L160-168/238-258), `selected_paths` fusiona selección de vista + casillas (L575-589).
- **Comportamientos distintos/rotos entre modos:**
  1. `view.grid_size` solo se aplica en ICON (`set_icon_grid_size` L514-520); en Compact el submenú «Icon grid size» es un **no-op silencioso** (mensaje de estado sí cambia) → T6.
  2. **«Group by» no agrupa en ningún modo**: `group_by` (L646-658) solo reordena (`sort_by` sobre la misma columna); no hay proxy/agrupación visual → T7.
  3. El indicador y la interfaz de ordenación existen solo en Details; en Icons/List/Compact se ordena sin retroalimentación.
  4. `invert_selection` (main_window L3535-3557) enumera filas sobre `details_view.rootIndex()` y no sincroniza `_checked_paths`: con casillas activas, tras invertir siguen contando los elementos marcados por casilla en estado, copia y papelera → T16.
  5. En Icons/Compact no hay forma de ver tamaño/fecha sin tooltip (statusbar solo resume la selección).

## 4. Inventario de diálogos modales

| Diálogo | Invocado desde | Clasificación | Justificación (1 línea) |
|---|---|---|---|
| `PreferencesDialog` (851 L) | Tools › Preferences (`Ctrl+,`) | Imprescindible | Centro de configuración; único punto de ajustes de vista/zoom/columnas/tema. |
| `PropertyDialog` | toolbar/contexto/paleta | Reemplazable | Información + permisos podría ser inspector no modal o columnas ya presentes en Details. |
| `AdvancedSecurityDialog` | contexto/Share/toolbar ctx | Imprescindible | Edición crítica de ACL/SELinux, uso poco frecuente; confirmación modal apropiada. |
| `CommandPaletteDialog` | Tools › Command Palette / `Ctrl+Shift+P` | Reemplazable | Modal por `exec()` pero debería ser overlay no bloqueante (paleta de teclado, roadmap P1). |
| `SearchFilterDialog` | botón Filters… | Reemplazable | El estado de filtros debe vivir en la barra de búsqueda no modal (roadmap 1.2.1). |
| `CreateMultipleDialog` | File/contexto › New › Multiple | Reemplazable | Creación por lote podría ser flujo no modal (entrada secuencial/banner). |
| `TagManagementDialog` | Tools › Manage Tags | Imprescindible | Único CRUD de etiquetas; no hay superficie alternativa. |
| `TagSearchDialog` | Tools › Search by Tag | Reemplazable | Es un caso de búsqueda; debería compartir el estado de búsqueda/filtros. |
| `AboutDialog` | Help › About | Eliminable | Sin valor modal; basta una ventana no modal o `QMessageBox.about`. |
| Diálogo «List Columns» (inline en workspace L332-406) | clic derecho en header Details | Reemplazable | Debería ser un submenú de columnas con casillas, no modal. |
| Diálogo de progreso de operaciones (`_show_progress`, L2703-2741) | cualquier worker (copiar/mover/papelera/…), `setModal(True)` | Reemplazable | Bloquea la ventana durante la operación; roadmap P1 lo convierte en centro de operaciones no modal. |
| Diálogo de indexado de carpeta (L3329-3376) | Tools › Index Current Folder | (referencia) | Ya es **no modal** (`setModal(False)`); buen patrón a generalizar. |
| `QInputDialog` (nombres nuevos/renombrar, ir a ruta, recientes, abrir con, app por defecto, comprimir, etiqueta, contraseñas de bóveda, tamaño de fuente) | flujos varios | Reemplazable | Entrada que el motor de acciones 1.2 y la edición inline deberían absorber. |
| `QMessageBox` (confirmar borrado permanente, vaciar papelera, errores de worker) | `file.delete`, `trash.empty`, fallos | Imprescindible (hoy) | Confirmación destructiva; a medio plazo sustituible por undo/banners (P2). |
| `QPrintDialog` | `file.print` | Imprescindible | Diálogo nativo del sistema, fuera de nuestro control. |

## 5. Inconsistencias detectadas → tareas

- [ ] **T1** `clip.copy/cut/paste` usan solo el portapapeles interno (`_clipboard_paths`, L123-124): copiar en LFM y pegar en otra app (o viceversa) no funciona. Reproducible: `Ctrl+C` sobre un archivo y `Ctrl+V` en un editor → no se pega nada. Tarea: integrar `QClipboard` con MIME `text/uri-list` y definir semántica interna/externa.
- [ ] **T2** Eliminar y papelera no existen en la barra de menús ni en toolbar (solo contexto, atajos y paleta), y los atajos `Delete`/`Shift+Delete` (`QShortcut`, L1395-1397) no se anuncian en menú ni paleta. Tarea: añadir `file.trash`/`file.delete` a Editar con sus atajos y sincronizar la paleta (id ya en `catalog.py`).
- [ ] **T3** Renombrar tiene dos implementaciones: F2 = edición inline (`rename_selected`) vs contexto/paleta = diálogo (`rename_selected_dialog`); la paleta anuncia F2 pero ejecuta el diálogo. Reproducible: seleccionar, `F2` vs menú contextual › Rename → UX distinta. Tarea: una sola acción `file.rename` con comportamiento único.
- [ ] **T4** `Ctrl+L` enfoca la barra de ruta (`focus_path_bar`) mientras la paleta anuncia «Go to Path… (Ctrl+L)» que abre `QInputDialog`. Tarea: unificar (barra de ruta como destino, eliminar el diálogo o reasignar tecla).
- [ ] **T5** Atajos registrados dos veces: `Ctrl+Shift+I` y `Ctrl+Shift+P` como QAction de menú y además `QShortcut` en `setup_shortcuts` (L1392-1407). Tarea: un único registro (ActionRegistry) y eliminar los `QShortcut` redundantes; audit de colisiones.
- [ ] **T6** «Icon grid size» no tiene efecto en modo Compact (`set_icon_grid_size` solo aplica si `_view_mode == ICON`, workspace L519). Reproducible: Compact → View › Icon grid size › Large → el estado dice «large» y la cuadrícula no cambia. Tarea: deshabilitar/ocultar el submenú en Compact o aplicarlo también allí.
- [ ] **T7** «Group by» no agrupa: `group_by` (workspace L646-658) es una reordenación. Reproducible: View › Group by › Type → solo cambia el orden. Tarea: implementar agrupación real o retirar el submenú hasta entonces.
- [ ] **T8** Menú contextual de fondo no ofrece cambio de modo de vista ni acciones de selección (Select All/Deselect/Invert), pese a que `lfmapp/ui/menus.py::ContextMenu` (L118-132) sí lo hace — pero ese módulo es **código muerto**: solo lo importan `lfmapp/ui/__init__.py` y `tests/test_menus.py`; `MainWindow` construye sus menús con `QMenu` directo (L1656-1958). Tarea: eliminar `menus.py` o cablearlo (evitar dos fuentes de verdad) y añadir Select All al contexto de fondo.
- [ ] **T9** Papelera sin restaurar: `list_trash`/`restore_from_trash` importados (L65-66) y sin uso en UI; la entrada del sidebar navega a `~/.local/share/Trash/files` (sin `.trashinfo`, nombres renombrados ilegibles). Tarea: vista de papelera con Restore/Empty (o retirar imports muertos y documentar la limitación).
- [ ] **T10** Sin resolución de conflictos: `CopyWorker`/`MoveWorker` sobrescriben con `shutil` sin consultar (worker_threads L29-54, L76-94). Reproducible: copiar una carpeta sobre otra con un subarchivo homónimo → se sobrescribe/fusiona en silencio. Tarea: motor de conflictos Replace/Skip/Keep Both (P1) y, mientras tanto, confirmación única.
- [ ] **T11** `Paste` siempre habilitado en Editar (no hace nada sin clipboard) vs paleta/contexto condicionados; el contexto tradicional de A/C no ofrece Paste (solo el strip compacto o el fondo). Tarea: enablement centralizado `can_paste` (ya en `catalog.py`) en todas las superficies.
- [ ] **T12** Los resultados de búsqueda se muestran en el panel de vista previa y abrir un resultado usa `QDesktopServices.openUrl` sin registrar recientes ni revelar la carpeta; con índice activo el mismo texto busca subtree indexado y sin índice solo la carpeta actual (dos motores, distinto alcance). Tarea: superficie/colección de resultados dedicada y estado de búsqueda único (roadmap 1.2.1).
- [ ] **T13** Misma acción lógica con títulos distintos según superficie: «Preview» (toolbar) = toggle, «Toggle Preview Panel» (View) = toggle, «Toggle preview panel» (contexto F) = toggle, y «Preview» del toolbar contextual = `preview_selected` (mostrar archivo); «Compress Selection to ZIP» vs «Compress to ZIP». La paleta los lista como comandos separados. Tarea: normalizar títulos/ids por acción (1.2) y deduplicar la paleta por `command_id`.
- [ ] **T14** Quick Access con tres rutas solapadas: `add_bookmark` (contexto C y paleta), `toggle_quick_access_pin` (toolbar/toolbar ctx), Tools › «Add Current Folder to Bookmarks» (usa siempre la carpeta actual aunque haya selección). Tarea: una única acción con contexto «carpeta seleccionada o actual».
- [ ] **T15** `Properties` incoherente entre superficies: `show_properties` exige selección (paleta lo oculta sin selección) mientras el botón de toolbar cae a la carpeta actual (`show_context_properties`) y el contexto de fondo abre la carpeta (`show_folder_properties`). Tarea: unificar handler y enablement por contexto.
- [ ] **T16** `invert_selection` ignora las casillas de selección: con `view.checkboxes` activo, los marcados por casilla permanecen en `_checked_paths` y siguen contando tras invertir (estado, copia, papelera). Tarea: que invertir/desmarcar sincronice también `checked_paths`.
- [ ] **T17** Registro de acciones efímeras en la paleta: las acciones de etiquetas y «Share with» creadas dentro de menús contextuales transitorios se registran con `command_id` por ruta/desktop y quedan referenciadas en `_command_actions` sin limpieza (L1859-1869, L1981-1986). Tarea: revisar ciclo de vida al migrar al ActionRegistry (evitar referencias a QAction destruidas).
- [ ] **T18** Desajuste entre las claves por defecto de `context_menu_selection_entries`/`context_menu_background_entries` (config.py L79-111) y las claves que el código consulta de verdad: `copy_to`, `move_to` y `print` (paleta) se comprueban pero no están en los defaults (quedan ocultos/deshabilitados), mientras que `open_in_new_tab`, `open_in_new_window`, `scripts`, `favorite`, `open_as_root`, `arrange_items`, `customize` están en los defaults pero **nunca se consultan** (funcionalidad inexistente o no cableada). Reproducible: contexto de un archivo no muestra «Copy to…» pese a existir el código. Tarea: alinear defaults↔código o implementar/retirar las claves huérfanas.

## 6. Fuente de verificación (rutas y líneas aproximadas)

- `lfmapp/ui/main_window.py`: toolbar L319-426; registro de comandos y paleta L612-969 (`_register_command_action` 612, `_palette_commands` 643, contextuales 669, navegación 877); menú contextual L1656-1958 (compacto 1676, archivo 1801, carpeta 1875, fondo 1924); `rebuild_share_menu` L1128; barra de menús L1145-1270; `setup_shortcuts` L1392-1407; pestañas L1411-1459; navegación L1496-1593; clipboard L2238-2328; crear L2332-2397; renombrar L2401-2429; historial L2519-2555; papelera L2557-2609; drop L2611-2701; progreso modal L2703-2741 y cola L2743-2793; borrar L2923-2955; copy/move to L2957-3070; enviar L3084-3165; extraer/comprimir L3169-3257; búsqueda L3261-3308; indexado L3310-3382; vistas/toggles L3395-3526; selección L3528-3557; etiquetas L3583-3643; bóveda L3647-3738; `keyPressEvent` L3748-3763.
- `lfmapp/ui/workspace.py`: vistas L93-155; columnas por carpeta L240-406; `set_view_mode` L483-508 (Compact = icon_view); grid solo ICON L514-537; zoom list/compact L538-552; `group_by` L646-658; selección L575-589; drag&drop L412-460.
- `lfmapp/models/file_system_model.py`: `COLUMN_KEYS`/labels L33-68; casillas columna 0 L160-168 y L238-258.
- `lfmapp/ui/menus.py`: L16-354 (código muerto; solo `__init__.py` y `tests/test_menus.py`).
- `lfmapp/ui/sidebar.py`: secciones L92-110; Trash = ruta cruda L317-324; conteo L425-436.
- `lfmapp/ui/preview_panel.py`: resultados de búsqueda L201-244.
- Diálogos: `command_palette_dialog.py` L12-159 (modal por `exec` L156-159); `search_filter_dialog.py` L18-114; `preferences_dialog.py` L34+; `property_dialog.py` L20/192; `create_multiple_dialog.py`; `tag_management_dialog.py`; `tag_search_dialog.py`; `about_dialog.py`.
- `lfmapp/services/`: `worker_threads.py` L14-218 (sin conflictos); `operation_queue.py` L8-63 (`max_concurrent=1` en main_window L132); `trash_service.py` L20-204; `search_service.py` L83-122; `extractor_service.py` L37-278; `preview_worker.py` L23-525; `file_operations.py` L11-121.
- `lfmapp/core/config.py`: valores por defecto L33-116 (`context_menu_*_entries` L79-111, toggles L36/50/79) — base de la tarea T18.
- Catálogo WIP: `lfmapp/actions/catalog.py` L30-112 (ids estables ya definidos) — alinear esta auditoría con él.
